"""Train/freeze/test the declared Delta OGMT family with equal search/shot budgets."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_relational_qc.calculator import run_calculation
from native_relational_qc.delta_ogmt import compare_qiskit, digest
from native_relational_qc.delta_ogmt_learning import (
    MODES, PROFILES, PROJECTIONS, SHOTS, Parameters, ProposalEvaluator,
    build_request, check_frozen, decision_scores, fit, freeze_model,
    make_splits, rounded_bounds, success_bounds,
)

PROTOCOL_PATH = ROOT / "benchmarks/protocols/delta_ogmt_learning_v1.json"


def protocol():
    return dict(schema="delta-ogmt-learning-protocol-v1", dataset=make_splits(),
                seed=20261031, history_length=12, task="transition count >=7 versus <=5",
                equal_input_counts="six A and six B; endpoints A then B",
                grouping="reverse-complement twins remain in the same split",
                dynamics_profiles=[list(v) for v in PROFILES],
                projection_pairs=[list(v) for v in PROJECTIONS], observer_steps=list(range(16)),
                modes=list(MODES), shots_per_decision=SHOTS,
                count_thresholds=list(range(SHOTS + 2)), orientations=[1, -1],
                training_configs_per_mode=len(PROFILES) * len(PROJECTIONS) * 16,
                shortlist="best readout per dynamics profile; four profiles ranked on training",
                selection="validation score, then training score, then stable candidate order",
                proposal_arithmetic="native NumPy gate algebra; ranking rounded to 12 decimal places",
                exact_verification="all train/validation/test probabilities for frozen models via calculator",
                primary_success_rule={"M3_test_expected_balanced_accuracy_min": "7/10",
                                      "M3_gain_over_both_M1_M2_min": "1/20",
                                      "paired_group_bootstrap_lower_bound_positive": True},
                uncertainty="arithmetic enclosures plus separate exploratory grouped bootstrap; no physical confidence claim",
                bootstrap_repeats=2000, bootstrap_seed=20261031,
                extra_controls=["fixed original M3 dynamics/readout with train-only count threshold",
                                "remove CA from frozen M3 without any retuning",
                                "boundary-only, equal-input, commuting and disabled-projection checks"],
                physical_calibration=False, classical_clean_symbol_counter_accuracy="1",
                audit_version=1)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def grouped_bootstrap(left, right, repeats=2000, seed=20261031):
    right = {r["history"]: r for r in right}
    rng = np.random.default_rng(seed)
    distributions = []
    for target in (0, 1):
        groups = {}
        for row in left:
            if row["target"] != target:
                continue
            other = right[row["history"]]
            groups.setdefault(row["group"], []).append(row["expected_correct_midpoint"] - other["expected_correct_midpoint"])
        values = [groups[key] for key in sorted(groups)]
        sums, sizes = np.array([sum(v) for v in values]), np.array([len(v) for v in values])
        choices = rng.integers(0, len(values), size=(repeats, len(values)))
        distributions.append(sums[choices].sum(axis=1) / sizes[choices].sum(axis=1))
    delta = (distributions[0] + distributions[1]) / 2
    return dict(lower=float(np.quantile(delta, 0.025)), upper=float(np.quantile(delta, 0.975)),
                resamples=repeats, seed=seed,
                scope="exploratory input-group resampling on this task family, not physical-device uncertainty")


def audit(output, protocol_commit, *, compare=False, timeout=60, workers=4):
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("exact replay workers must be 1..4")
    if len(protocol_commit) != 40 or any(c not in "0123456789abcdef" for c in protocol_commit):
        raise ValueError("protocol commit SHA required")
    plan = json.loads(PROTOCOL_PATH.read_text())
    if plan != protocol():
        raise ValueError("checked-in protocol differs from this implementation")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for directory in ("search", "inputs", "results"):
        (output / directory).mkdir()
    write_json(output / "protocol.json", plan)
    write_json(output / "status.json", dict(status="running", protocol_commit=protocol_commit,
                                           started_at_utc=datetime.now(timezone.utc).isoformat()))
    started = time.perf_counter()
    splits = plan["dataset"]
    train, validation = splits["train"], splits["validation"]
    models, search = {}, {}
    try:
        for mode in MODES:
            result = fit(train, validation, mode)
            seen = set(result["histories_evaluated"])
            if seen & {r["history"] for r in splits["test"] + splits["reserve"]}:
                raise AssertionError("held-out history entered proposal search")
            models[mode] = result["model"]
            search[mode] = {k: result[k] for k in ("selected_training_score", "selected_validation_score", "native_gate_applications")}
            write_json(output / "search" / (mode + ".json"), result)
            print(mode, "train", result["selected_training_score"], "validation", result["selected_validation_score"],
                  "parameters", models[mode]["parameters"], flush=True)
        # Reference: previous dynamics/readout fixed; only count threshold and
        # orientation fitted on the new training data, never its test outcomes.
        fixed_params = Parameters(observer_step=3)
        values = ProposalEvaluator().probabilities([r["history"] for r in train], "M3", fixed_params)
        scores = decision_scores(values, [r["target"] for r in train])[0]
        direction, cut = np.unravel_index(int(np.argmax(np.round(scores, 12))), scores.shape)
        models["M3_reference"] = freeze_model("M3", fixed_params, 1 if direction == 0 else -1, int(cut), train, validation)
        full = models["M3"]
        models["M3_fixed_CA_cut"] = freeze_model("E_CA", check_frozen(full), full["orientation"], full["cutoff"], train, validation)
        frozen = dict(schema="delta-ogmt-frozen-campaign-v1", models=models,
                      protocol_sha256=digest(plan), protocol_commit=protocol_commit,
                      frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                      test_or_reserve_used_for_selection=False, search_summary=search)
        write_json(output / "frozen_models.json", frozen)
        frozen_bytes = (output / "frozen_models.json").read_bytes()
        # Test data are first evaluated below, after every model has been frozen.
        print("ALL MODELS FROZEN; starting exact replay including held-out test.", flush=True)
        evaluations, aggregate_bounds = {}, {}
        total_requests = 0
        max_proposal_error = max_reference_error = 0.0
        numeric_reference_count = 0
        proposal = ProposalEvaluator()

        def one(payload):
            label, request = payload
            return label, run_calculation(request, timeout_seconds=timeout)

        for name, model in models.items():
            params = check_frozen(model)
            evaluations[name], aggregate_bounds[name] = {}, {}
            for split in (("test",) if name == "M3_fixed_CA_cut" else ("train", "validation", "test")):
                rows = splits[split]
                pending, encodings, requests = [], {}, {}
                for row in rows:
                    label = name + "__" + split + "__" + row["history"]
                    request, encoding = build_request(row["history"], model["mode"], params)
                    write_json(output / "inputs" / (label + ".json"), request)
                    pending.append((label, request))
                    encodings[label], requests[label] = encoding, request
                records, exact_intervals = [], {0: [], 1: []}
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    for row, (label, result) in zip(rows, pool.map(one, pending)):
                        write_json(output / "results" / (label + ".json"), result)
                        if result["status"] != "completed":
                            raise RuntimeError(label + " did not complete: " + result["status"])
                        probability = result["answers"][0]["probabilities"]["1"]
                        bounds = success_bounds(probability, row["target"], model)
                        exact_intervals[row["target"]].append(bounds)
                        predicted = proposal.probabilities([row["history"]], model["mode"], params)[0]
                        discrepancy = abs(float(predicted) - float(probability["decimal"]))
                        max_proposal_error = max(max_proposal_error, discrepancy)
                        if discrepancy > 2e-10:
                            raise ArithmeticError("proposal/exact disagreement: " + label)
                        reference = None
                        if compare:
                            reference = compare_qiskit(requests[label], encodings[label], result)
                            if not reference["passed"]:
                                raise ArithmeticError("independent reference disagreement: " + label)
                            max_reference_error = max(max_reference_error, reference["max_absolute_error"])
                            numeric_reference_count += 1
                        records.append(dict(row, probability=probability, expected_correct_bounds=rounded_bounds(*bounds),
                                            expected_correct_midpoint=float(sum(bounds) / 2),
                                            proposal_probability=float(predicted), proposal_discrepancy=discrepancy,
                                            numeric_reference=reference, request_sha256=digest(requests[label]),
                                            gates=result["gates"], peak_branches=result["statistics"]["peak_branches"]))
                        total_requests += 1
                low = sum(sum(x[0] for x in exact_intervals[y]) / len(exact_intervals[y]) for y in (0, 1)) / 2
                high = sum(sum(x[1] for x in exact_intervals[y]) / len(exact_intervals[y]) for y in (0, 1)) / 2
                aggregate_bounds[name][split] = (low, high)
                evaluations[name][split] = dict(cases=len(records), expected_balanced_accuracy=rounded_bounds(low, high),
                                                records=records)
                print(name, split, "exact expected balanced accuracy", float((low + high) / 2), flush=True)
                write_json(output / ("evaluation_" + name + ".json"), evaluations[name])
        if (output / "frozen_models.json").read_bytes() != frozen_bytes:
            raise AssertionError("model file changed during evaluation")
        comparisons = {}
        full_low, full_high = aggregate_bounds["M3"]["test"]
        for name in ("M1", "M2", "E_CA", "M3_reference", "M3_fixed_CA_cut"):
            low, high = aggregate_bounds[name]["test"]
            comparisons[name] = dict(exact_expected_accuracy_difference=rounded_bounds(full_low - high, full_high - low),
                                    grouped_bootstrap=grouped_bootstrap(evaluations["M3"]["test"]["records"], evaluations[name]["test"]["records"]))
        # Representative opposite-label controls. The entire family has equal
        # counts, length and endpoints; do not present these as 64 physical runs.
        representatives = [next(r for r in splits["test"] if r["target"] == y) for y in (0, 1)]
        controls = {}
        for variant in ("boundary_only", "equal_inputs", "commuting_updates", "projection_off"):
            probabilities = []
            for row in representatives:
                mode = "M0" if variant == "boundary_only" else "M3"
                request, encoding = build_request(row["history"], mode, check_frozen(models["M3"]),
                                                  variant="nominal" if variant == "boundary_only" else variant)
                label = "negative__" + variant + "__" + row["history"]
                write_json(output / "inputs" / (label + ".json"), request)
                result = run_calculation(request, timeout_seconds=timeout)
                write_json(output / "results" / (label + ".json"), result)
                if result["status"] != "completed":
                    raise RuntimeError("negative control did not complete")
                probabilities.append(result["answers"][0]["probabilities"]["1"]["exact"])
                total_requests += 1
            controls[variant] = dict(opposite_label_probabilities_identical=probabilities[0] == probabilities[1],
                                     representative_histories=[r["history"] for r in representatives])
        if not all(row["opposite_label_probabilities_identical"] for row in controls.values()):
            raise ArithmeticError("negative control unexpectedly distinguished matched histories")
        primary = full_low >= Fraction(7, 10) and all(
            full_low - aggregate_bounds[name]["test"][1] >= Fraction(1, 20)
            and comparisons[name]["grouped_bootstrap"]["lower"] > 0 for name in ("M1", "M2"))
        sources = ("native_relational_qc/delta_ogmt_learning.py", "native_relational_qc/delta_ogmt.py",
                   "native_relational_qc/calculator.py", "native_relational_qc/phase_backend.py",
                   "native_relational_qc/cyclotomic_pow2.py", "native_relational_qc/algebra.py",
                   "benchmarks/delta_ogmt_learning_audit.py", "benchmarks/protocols/delta_ogmt_learning_v1.json")
        report = dict(schema="delta-ogmt-heldout-audit-v1", status="completed", verification_passed=True,
                      primary_topology_advantage_passed=bool(primary), evidence_class="DECLARED_IDEAL_CIRCUIT_MODEL",
                      hardware_job_id=None, hardware_validated=False, computational_advantage_established=False,
                      protocol_commit=protocol_commit, protocol_sha256=digest(plan), frozen_models_sha256=hashlib.sha256(frozen_bytes).hexdigest(),
                      models=models, search_summary=search, test_histories_used_for_selection=False,
                      split_counts={key: len(value) for key, value in splits.items()}, shots_per_decision=SHOTS,
                      scores={name: {split: value["expected_balanced_accuracy"] for split, value in split_rows.items()} for name, split_rows in evaluations.items()},
                      comparisons=comparisons, negative_controls=controls, exact_requests=total_requests,
                      numeric_reference_checks=numeric_reference_count, max_numeric_reference_error=max_reference_error,
                      max_proposal_exact_error=max_proposal_error, workers=workers,
                      ideal_classical_symbol_counter_accuracy="1", wall_seconds=time.perf_counter() - started,
                      python=platform.python_version(), numpy=np.__version__,
                      source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources},
                      scope="Expected performance with 64 independent ideal readouts per decision, on unseen strings from one declared family; not sampled accuracy or a calibrated physical device.")
        write_json(output / "summary.json", report)
        write_json(output / "status.json", dict(status="completed", completed_at_utc=datetime.now(timezone.utc).isoformat()))
        hashes = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob("*.json"))}
        write_json(output / "manifest.sha256.json", hashes)
        return report
    except Exception as exc:
        write_json(output / "status.json", dict(status="incomplete", error=str(exc), failed_at_utc=datetime.now(timezone.utc).isoformat()))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--protocol-commit", required=True)
    parser.add_argument("--compare-qiskit", action="store_true")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    result = audit(args.out, args.protocol_commit, compare=args.compare_qiskit, timeout=args.timeout, workers=args.workers)
    print(json.dumps({k: result[k] for k in ("status", "verification_passed", "primary_topology_advantage_passed", "exact_requests", "wall_seconds")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
