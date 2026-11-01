"""Retained 16-angle readout diagnostic for the declared Delta OGMT circuit.

The grid uses the same two known histories in every mode. Its best angle is a
model diagnostic selected on those histories, never held-out learning accuracy.
"""
from __future__ import annotations

import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time

from .calculator import display, real_sign, run_calculation
from .certify import exact_value, flat_field
from .delta_ogmt import HISTORIES, MODES, build_request, compare_qiskit, digest, _abs
from .phase_interop import phase_operations


def probability_at_angle(y, z, steps):
    """P(1) after Rx(2*pi*steps/16): (1 - Z*cos(theta) - Y*sin(theta))/2."""
    if type(steps) is not int or not 0 <= steps < 16:
        raise ValueError("observer steps must be an integer in 0..15")
    field = flat_field()
    root = field.root(4 * steps)
    cosine = (root + root.conjugate()) / 2
    sine = (root - root.conjugate()) * field.root(-16) / 2
    probability = (1 - z * cosine - y * sine) / 2
    if real_sign(probability) < 0 or real_sign(1 - probability) < 0:
        raise ValueError("Bloch moments produced an invalid probability")
    return probability


def rotated_request(request, steps, wire=6):
    result = copy.deepcopy(request)
    result["operations"].append(["h", [wire]])
    result["operations"].extend([[name, list(qs)] for name, qs in
                                  phase_operations(Fraction(steps, 16), (wire,))])
    result["operations"].append(["h", [wire]])
    return result


def scan(output, *, compare=False, timeout_seconds=60):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "inputs").mkdir()
    (output / "results").mkdir()
    plan = dict(schema="nrqc-delta-ogmt-observer-plan-v1", modes=list(MODES),
                histories=list(HISTORIES), phase_steps=list(range(16)), phase_order=16,
                unchanged_couplings=True, optimization_scope="readout angle only",
                evaluation_scope="same known histories; no held-out accuracy claim")
    (output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    started = time.perf_counter()
    rows, direct_checks, references = {}, {}, {}

    def run(label, request):
        (output / "inputs" / (label + ".json")).write_text(json.dumps(request, indent=2) + "\n")
        result = run_calculation(request, timeout_seconds=timeout_seconds)
        (output / "results" / (label + ".json")).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        if result["status"] != "completed":
            raise RuntimeError("Observer scan incomplete: " + label + ": " + result["status"])
        return result

    for mode in MODES:
        moments, originals, encodings = {}, {}, {}
        for history in HISTORIES:
            request, encodings[history] = build_request(history, mode)
            originals[history] = copy.deepcopy(request)
            request["queries"] = [dict(id=axis, kind="expectation", paulis={"6": axis}) for axis in ("Y", "Z")]
            result = run(mode + "__moments__" + history, request)
            moments[history] = {a["id"]: exact_value(a["value"]["exact"]) for a in result["answers"]}
        grid, exact_gaps = [], []
        for steps in range(16):
            probabilities = {h: probability_at_angle(v["Y"], v["Z"], steps) for h, v in moments.items()}
            gap = _abs(probabilities["ABAB"] - probabilities["AABB"])
            exact_gaps.append(gap)
            grid.append(dict(steps=steps, turns=str(Fraction(steps, 16)),
                             target_p1=display(probabilities["ABAB"]),
                             control_p1=display(probabilities["AABB"]),
                             gap=display(gap),
                             model_optimal_equal_prior_single_shot_success=display((1 + gap) / 2)))
        best = 0
        for steps in range(1, 16):
            if real_sign(exact_gaps[steps] - exact_gaps[best]) > 0:
                best = steps
        # Recalculate the selected readout as actual appended circuit gates,
        # rather than relying only on the analytical moment reconstruction.
        for history in HISTORIES:
            label = mode + "__direct_selected__" + history
            request = rotated_request(originals[history], best)
            result = run(label, request)
            actual = exact_value(result["answers"][0]["probabilities"]["1"]["exact"])
            predicted = probability_at_angle(moments[history]["Y"], moments[history]["Z"], best)
            direct_checks[label] = actual == predicted
            if compare:
                references[label] = compare_qiskit(request, encodings[history], result)
        rows[mode] = dict(grid=grid, selected_steps=best, selected=grid[best],
                          moments={h: {axis: display(v) for axis, v in axes.items()} for h, axes in moments.items()})
        print(mode, "selected", best, "gap", grid[best]["gap"]["decimal"], flush=True)
    full = exact_value(rows["M3"]["selected"]["gap"]["exact"])
    comparisons = {mode: display(full - exact_value(rows[mode]["selected"]["gap"]["exact"]))
                   for mode in ("M1", "M2", "E_CA")}
    reference_passed = all(r["passed"] for r in references.values()) if compare else None
    root = Path(__file__).resolve().parents[1]
    source_files = ("native_relational_qc/delta_ogmt.py", "native_relational_qc/delta_ogmt_observer.py")
    summary = dict(schema="nrqc-delta-ogmt-observer-scan-v1", status="completed",
                   verification_passed=all(direct_checks.values()) and reference_passed is not False,
                   evidence_class="DECLARED_IDEAL_CIRCUIT_MODEL", hardware_job_id=None,
                   plan_sha256=digest(plan), plan=plan, modes=rows,
                   direct_exact_checks=direct_checks, qiskit_checks=references,
                   full_minus_comparator_with_same_angle_grid=comparisons,
                   wall_seconds=time.perf_counter() - started,
                   source_sha256={p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in source_files},
                   scope="Readout-only diagnosis on known sequences. No physical calibration, training generalization, or quantum advantage established.")
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    hashes = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(output.rglob("*.json"))}
    (output / "manifest.sha256.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compare-qiskit", action="store_true")
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args(argv)
    report = scan(args.out, compare=args.compare_qiskit, timeout_seconds=args.timeout)
    print(json.dumps({k: report[k] for k in ("status", "verification_passed", "wall_seconds")}, indent=2))
    return 0 if report["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
