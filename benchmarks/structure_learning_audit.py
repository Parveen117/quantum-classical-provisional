"""Frozen-protocol topology search, phase compilation and held-out comparison."""
import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import time

assert sys.version_info[:2] == (3, 12), sys.version
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from native_relational_qc.circuit import Circuit
from native_relational_qc.learning_tasks import curvature_splits, classical_baselines
from native_relational_qc.self_learning import (
    DEFAULT_ENTANGLERS, FIELD, Evaluator, assess, circuit, digest, load_packet,
)
from native_relational_qc.structure_learning import fit_structure


def score(model, rows, compiler):
    edges = model.get("entanglers", DEFAULT_ENTANGLERS)
    evaluator = Evaluator(entanglers=edges, compiler=compiler)
    start = time.perf_counter()
    assessment = assess(model, rows, evaluator=evaluator)
    return dict(assessment=assessment, resources=dict(evaluator.stats),
                seconds=time.perf_counter() - start)


def dense_probability(features, parameters, edges):
    reference = Circuit(4)
    for q, step in enumerate(features):
        reference.add("ry", q, theta=step * np.pi / 32)
    for q, step in enumerate(parameters[:4]):
        reference.add("ry", q, theta=step * np.pi / 32)
    for control, target in edges:
        reference.add("cx", control, target)
    reference.add("ry", 3, theta=parameters[4] * np.pi / 32)
    return sum(abs(a) ** 2 for k, a in enumerate(reference.state().amplitudes) if k & 8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    splits, source = curvature_splits()
    print("Training five admitted topologies with seeds 17,41,73 and three sweeps", flush=True)
    fitted = fit_structure(splits["train"], view="first_layer",
                           progress=lambda row: print(json.dumps(row), flush=True))
    # Selection has finished before any validation/test inference below.
    frozen = copy.deepcopy(fitted["model"])
    fingerprint = digest(fitted)
    baseline = fitted["candidates"][fitted["baseline_candidate"]]["model"]
    models = dict(fixed_raw=(baseline, "raw"), fixed_fused=(baseline, "fused"),
                  searched_fused=(frozen, "fused"))
    comparisons = {}
    for name, (model, compiler) in models.items():
        comparisons[name] = {part: score(model, rows, compiler)
                             for part, rows in splits.items()}
    controls = []
    canonical_controls = []
    reference_error = 0.0
    for model in (baseline, frozen):
        parameters = load_packet(model)
        edges = model.get("entanglers", DEFAULT_ENTANGLERS)
        raw, fused = Evaluator(entanglers=edges), Evaluator(entanglers=edges, compiler="fused")
        for row in splits["test"]:
            old = raw.probability(row.features, parameters)
            new = fused.probability(row.features, parameters)
            assert old == new
            error = abs(complex(new).real - dense_probability(row.features, parameters, edges))
            reference_error = max(reference_error, error)
            assert error < 1e-12
        controls.append(dict(model_fingerprint=model["fingerprint"], exact_probability_pairs=64,
                             raw_resources=dict(raw.stats), fused_resources=dict(fused.stats)))
    for item in fitted["candidates"]:
        if not item["readout_canonicalization"]["zeroed_phase_coordinates"]:
            continue
        original = item["training"]["model"]
        canonical = item["model"]
        edges = canonical.get("entanglers", DEFAULT_ENTANGLERS)
        a = Evaluator(entanglers=edges, compiler="fused")
        b = Evaluator(entanglers=edges, compiler="fused")
        for row in (*splits["train"], *splits["validation"], *splits["test"]):
            assert a.probability(row.features, load_packet(original)) == b.probability(row.features, load_packet(canonical))
        canonical_controls.append(dict(source_model_fingerprint=original["fingerprint"],
                                       result_model_fingerprint=canonical["fingerprint"],
                                       exact_probability_pairs=84))
    assert frozen == fitted["model"] and digest(fitted) == fingerprint
    summary = {}
    for name, results in comparisons.items():
        row = results["test"]
        model = models[name][0]
        summary[name] = dict(accuracy=row["assessment"]["accuracy"],
                             brier_loss=row["assessment"]["brier_loss"],
                             cx_per_prediction=len(model.get("entanglers", DEFAULT_ENTANGLERS)),
                             total_native_gates=row["resources"]["total_executed_gates"],
                             exact_executor_work=row["resources"]["engine_work"],
                             inference_seconds=row["seconds"])
    paths = ("native_relational_qc/self_learning.py", "native_relational_qc/structure_learning.py",
             "native_relational_qc/learning_tasks.py", "native_relational_qc/phase_backend.py",
             "native_relational_qc/pauli_engine.py", "benchmarks/structure_learning_audit.py")
    report = dict(schema="nrqc-structure-learning-audit-v1", author="Monty",
                  python=sys.version.split()[0], evidence_class="LOCAL_IDEAL_CALCULATION",
                  training_search=fitted, comparisons=comparisons, summary=summary,
                  exact_compilation_controls=controls,
                  readout_canonicalization_controls=canonical_controls,
                  maximum_numpy_probability_error=reference_error,
                  task_source=source, data_sizes={name: len(rows) for name, rows in splits.items()},
                  same_feature_classical_baseline=classical_baselines(splits["train"], splits["test"]),
                  held_out_used_after_selection=True, hardware_jobs=0,
                  source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths})
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
                        encoding="utf-8")
    print(json.dumps(dict(summary=summary, search_resources=fitted["resources"],
                          search_seconds=fitted["wall_seconds"],
                          maximum_numpy_probability_error=reference_error), indent=2), flush=True)


if __name__ == "__main__":
    main()
