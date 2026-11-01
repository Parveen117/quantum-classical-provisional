"""Exact tests separating moving coordinates from record-dependent interactions.

The signal, measurement axis and retained record are distinct variables. No
antiunitary conjugation is installed as a gate on an unknown quantum state.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from math import pi
from pathlib import Path

from .calculator import display, run_calculation
from .certify import exact_value, flat_field
from .delta_ogmt import _phase, digest
from .phase_interop import phase_name


def request(operations, width=1, queries=None):
    return dict(schema="nrqc-calculator-v1", backend="cyclotomic_pow2", n_qubits=width,
                operations=operations, decimal_places=12,
                limits=dict(max_work=1_000_000, max_branches=64, max_coefficient_bits=4096),
                queries=queries or [dict(id="readout", kind="distribution", qubits=[0])])


def relative_request(signal_steps, observer_steps, *, mixed=False):
    """An equatorial state read in a moving X-Y axis; angles are 2*pi/16 steps."""
    ops = [["h", [0]]]
    if mixed:
        ops.append(["cx", [0, 1]])  # Trace the untouched Bell partner at readout.
    _phase(ops, [0], signal_steps)
    _phase(ops, [0], -observer_steps)
    ops.append(["h", [0]])
    return request(ops, 2 if mixed else 1)


def frame_request(axes, *, representation="lab"):
    """V_j^dagger U_j V_(j-1), including the time-dependent frame connection."""
    if len(axes) != 5 or any(type(a) is not int for a in axes):
        raise ValueError("five integer phase-axis settings required")
    if representation not in ("lab", "moving", "missing_connection"):
        raise ValueError("unknown frame representation")
    blocks = []
    for angle in (1, 3, -2, 5):
        block = [["h", [0]]]
        _phase(block, [0], angle)
        blocks.append(block)
    ops = [["h", [0]]]
    _phase(ops, [0], 3)
    if representation != "lab":
        _phase(ops, [0], -axes[0])
    for j, block in enumerate(blocks, 1):
        if representation != "lab":
            _phase(ops, [0], axes[j-1] if representation == "moving" else axes[j])
        ops.extend(block)
        if representation != "lab":
            _phase(ops, [0], -axes[j])
    if representation == "lab":
        _phase(ops, [0], -axes[-1])
    ops.append(["h", [0]])
    return request(ops)


def feedback_request(*, source_feedback=0, observer_feedback=0, record=True,
                     signal_steps=4, first_axis=0, drift_steps=4, second_axis=0):
    """Two ideal projective reads with feedback from the first recorded bit.

    q0 is signal, q1 first record, q2 second record. Deferred measurement is
    valid because q1 is used only as a computational-basis control and is never
    mixed or erased. Records are included in the final joint distribution.
    """
    if any(type(v) is not int for v in (source_feedback, observer_feedback, signal_steps,
                                       first_axis, drift_steps, second_axis)) or type(record) is not bool:
        raise ValueError("integer phase steps and a boolean record switch required")
    ops = [["h", [0]]]
    _phase(ops, [0], signal_steps)
    if record:
        _phase(ops, [0], -first_axis)
        ops += [["h", [0]], ["cx", [0, 1]], ["h", [0]]]
        _phase(ops, [0], first_axis)
    # First bit affects actual signal evolution and/or the next measurement axis.
    _phase(ops, [1, 0], source_feedback)
    _phase(ops, [0], drift_steps)
    _phase(ops, [0], -second_axis)
    _phase(ops, [1, 0], -observer_feedback)
    ops += [["h", [0]], ["cx", [0, 2]]]
    return request(ops, 3, [dict(id="records", kind="distribution", qubits=[1, 2]),
                            dict(id="second", kind="distribution", qubits=[2])])


def analytic_joint(*, source_feedback=0, observer_feedback=0, signal_steps=4,
                   first_axis=0, drift_steps=4, second_axis=0):
    """Independent sequential-projector formula, not a circuit simulation."""
    F = flat_field()
    cosine = lambda k: (F.root(4*k) + F.root(-4*k)) * Fraction(1, 2)
    result = {}
    for first in (0, 1):
        prior = (1 + (-1)**first * cosine(signal_steps-first_axis)) * Fraction(1, 2)
        delta = first_axis + drift_steps - second_axis + first*(source_feedback-observer_feedback)
        for second in (0, 1):
            conditional = (1 + (-1)**(first+second)*cosine(delta)) * Fraction(1, 2)
            result[str(first)+str(second)] = prior * conditional
    return result


def cases():
    entries = {}
    for step in range(16):
        entries[f"common_rotation_{step:02d}"] = relative_request(3+step, 1+step)
        entries[f"relative_rotation_{step:02d}"] = relative_request(step, 0)
    for angle in (0, 1, 3, 7):
        entries[f"mixed_axis_{angle}"] = relative_request(3, angle, mixed=True)
    for schedule, axes in (("moving", (2, 5, 1, 7, 4)), ("static", (2,)*5)):
        for representation in ("lab", "moving", "missing_connection"):
            entries[f"frame_{schedule}_{representation}"] = frame_request(axes, representation=representation)
    for name, source, observer in (("none", 0, 0), ("observer", 0, 4),
                                   ("source", 4, 0), ("both", 4, 4)):
        entries["feedback_"+name] = feedback_request(source_feedback=source, observer_feedback=observer)
    entries["record_disabled"] = feedback_request(record=False, observer_feedback=4)
    return entries


def law(result, query="readout"):
    if result.get("status") != "completed":
        raise ValueError("incomplete calculation")
    answer = next(a for a in result["answers"] if a["id"] == query)
    return {k: exact_value(v["exact"]) for k, v in answer["probabilities"].items()}


def check_results(results):
    F = flat_field()
    checks = {}
    common = law(results["common_rotation_00"])
    checks["common_rotation_invariant"] = all(law(results[f"common_rotation_{k:02d}"]) == common for k in range(16))
    checks["relative_rotation_cosine_law"] = all(
        law(results[f"relative_rotation_{k:02d}"])["0"] == (2+F.root(4*k)+F.root(-4*k))*Fraction(1, 4)
        for k in range(16))
    checks["mixed_state_axis_independent"] = all(
        law(results[f"mixed_axis_{k}"]) == {"0": F(Fraction(1, 2)), "1": F(Fraction(1, 2))} for k in (0, 1, 3, 7))
    for schedule in ("moving", "static"):
        checks["frame_covariance_"+schedule] = law(results[f"frame_{schedule}_lab"]) == law(results[f"frame_{schedule}_moving"])
    checks["missing_connection_fails_when_frame_moves"] = law(results["frame_moving_lab"]) != law(results["frame_moving_missing_connection"])
    checks["missing_connection_invisible_for_static_frame"] = law(results["frame_static_lab"]) == law(results["frame_static_missing_connection"])
    for name, source, observer in (("none", 0, 0), ("observer", 0, 4), ("source", 4, 0), ("both", 4, 4)):
        checks["sequential_instrument_"+name] = law(results["feedback_"+name], "records") == analytic_joint(source_feedback=source, observer_feedback=observer)
    checks["matched_feedback_cancels_relatively"] = law(results["feedback_none"], "records") == law(results["feedback_both"], "records")
    checks["recording_has_backaction"] = law(results["feedback_none"], "second") != law(results["record_disabled"], "second")
    return checks


def qiskit_check(document, result):
    from qiskit import QuantumCircuit, __version__
    from qiskit.quantum_info import Statevector
    circuit = QuantumCircuit(document["n_qubits"])
    for name, wires in document["operations"]:
        if name in ("h", "cx"):
            getattr(circuit, name)(*wires)
        else:
            turns, controlled = phase_name(name)
            (circuit.cp if controlled else circuit.p)(2*pi*float(turns), *wires)
    state = Statevector.from_instruction(circuit)
    error = 0.0
    for query in document["queries"]:
        probabilities = state.probabilities(qargs=list(reversed(query["qubits"])))
        for label, value in law(result, query["id"]).items():
            error = max(error, abs(probabilities[int(label, 2)]-float(display(value)["decimal"])))
    return dict(passed=bool(error < 2e-10), max_absolute_error=float(error), qiskit_version=__version__, hardware_job_id=None)


def audit(output, *, compare=False, timeout=30):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for directory in ("inputs", "results"):
        (output/directory).mkdir()
    def save(path, value):
        path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+"\n")
    inputs = cases()
    save(output/"plan.json", dict(schema="moving-observer-plan-v1", cases=list(inputs),
                                 angle_step="2*pi/16", physical_rotation_required=False,
                                 measurement="ideal projective instrument with retained deferred records",
                                 selection="fixed algebraic examples; no parameter optimization"))
    for label, document in inputs.items():
        save(output/"inputs"/(label+".json"), document)
    results, references = {}, {}
    try:
        for label, document in inputs.items():
            result = run_calculation(document, timeout_seconds=timeout)
            save(output/"results"/(label+".json"), result)
            if result["status"] != "completed":
                raise RuntimeError(label+": "+result["status"])
            results[label] = result
            if compare:
                references[label] = qiskit_check(document, result)
                if not references[label]["passed"]:
                    raise ArithmeticError("Qiskit disagreement: "+label)
        checks = check_results(results)
        if not all(checks.values()):
            raise ArithmeticError("moving-frame identity failed: "+repr(checks))
        feedback = {name: display(law(result, "second")["1"]) for name, result in results.items()
                    if name.startswith("feedback_") or name == "record_disabled"}
        source = Path(__file__)
        report = dict(schema="moving-observer-audit-v1", status="completed", verification_passed=True,
                      evidence_class="DECLARED_IDEAL_CIRCUIT_MODEL", hardware_validated=False,
                      universal_rotation_effect_established=False, computational_advantage_established=False,
                      exact_requests=len(results), checks=checks, numeric_references=references,
                      feedback_second_bit_one=feedback, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                      request_sha256={k:digest(v) for k,v in inputs.items()})
        save(output/"summary.json", report)
        save(output/"manifest.sha256.json", {p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                                             for p in sorted(output.rglob("*.json"))})
        return report
    except Exception as error:
        save(output/"status.json", dict(status="incomplete", verification_passed=False, error=str(error)))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compare-qiskit", action="store_true")
    args = parser.parse_args()
    result = audit(args.out, compare=args.compare_qiskit)
    print(json.dumps({k: result[k] for k in ("status", "verification_passed", "exact_requests", "checks")}, indent=2))


if __name__ == "__main__":
    main()
