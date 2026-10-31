"""Delta OGMT event-order audit through the existing exact calculator.

This is a declared coherent circuit encoding of the double-triangle roles,
not a calibrated electrical/thermal device model. No quantum service is used.
Replay every saved input with ``nrqc calculate INPUT.json``.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import time

from .calculator import display, real_sign, run_calculation
from .certify import exact_value
from .phase_interop import phase_operations

SCHEMA = "nrqc-delta-ogmt-order-audit-v1"
ORDER = 16
ROLES = dict(A_channel=0, B_gate=1, C_return=2,
             C1_electrical_ledger=3, C2_thermal_role_ledger=4,
             C3_retention_role_ledger=5, drain_readout=6)
HISTORIES = {"ABAB": ("A", "B", "A", "B"), "AABB": ("A", "A", "B", "B")}
INPUT_STEPS = {"A": 1, "B": 3, "hold": 0, "R": 2}
OUTER = (("AB", 0, 1, 2), ("BC", 1, 2, 1), ("CA", 2, 0, 2))
INNER = (("12", 3, 4, 1), ("23", 4, 5, 2), ("31", 5, 3, 1))
BRIDGES = (("A1", 0, 3, 2), ("B2", 1, 4, 1), ("C3", 2, 5, 1))
MODES = ("M0", "M1", "M2", "M3", "E_CA")
RESETS = {"reset_C1": (3,), "reset_C2": (4,), "reset_C3": (5,),
          "reset_all_ledgers": (3, 4, 5)}
NEGATIVE = ("equal_inputs", "commuting_updates", "projection_off")
VARIANTS = ("nominal", *RESETS, *NEGATIVE)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _phase(ops, wires, steps):
    ops.extend([[name, list(qs)] for name, qs in
                phase_operations(Fraction(steps, ORDER), tuple(wires))])


def _mix(ops, wire, steps, commuting):
    # H P(theta) H is exp(i theta/2) Rx(theta). Its scalar phase is global:
    # it is never used as a controlled Rx or silently discarded inside one.
    if not commuting:
        ops.append(["h", [wire]])
    _phase(ops, [wire], steps)
    if not commuting:
        ops.append(["h", [wire]])


def build_request(history, mode="M3", variant="nominal"):
    """Return a replayable calculator request and an explicit encoding record.

    The six data wires are coherent ledgers, not carrier densities or kelvins.
    A reset swaps a ledger into a fresh |0> environment wire; all observations
    marginalize that environment, implementing trace-and-prepare, not postselection.
    """
    if isinstance(history, str):
        history = tuple(history)
    if not isinstance(history, (tuple, list)) or len(history) != 4 or any(t not in ("A", "B") for t in history):
        raise ValueError("history must contain four A/B events")
    if mode not in MODES or variant not in VARIANTS:
        raise ValueError("unknown mode or variant")
    if variant != "nominal" and mode != "M3":
        raise ValueError("interventions are defined on M3 only")
    commuting = variant == "commuting_updates"
    active = (3,) if mode == "M1" else (() if mode == "M0" else (3, 4, 5))
    edges = list(OUTER)
    edges += [edge for edge in BRIDGES if edge[2] in active]
    if mode in ("M3", "E_CA"):
        edges += list(INNER)
    if mode == "E_CA":
        edges = [edge for edge in edges if edge[0] != "CA"]
    initial_h = tuple(range(6)) if commuting else (0,)
    ops = [["h", [wire]] for wire in initial_h]

    def event(token):
        steps = INPUT_STEPS[token]
        if variant == "equal_inputs" and token in ("A", "B"):
            steps = INPUT_STEPS["A"]
        _mix(ops, 1, steps, commuting)
        _mix(ops, 0, 1, commuting)
        _mix(ops, 2, 2, commuting)
        for wire in active:
            _mix(ops, wire, {3: 2, 4: 1, 5: 1}[wire], commuting)
            _phase(ops, [wire], wire - 2)
        for _, a, b, weight in edges:
            _phase(ops, [a, b], weight)

    # M0 is explicitly a boundary-only preparation, not a purported history-
    # free unitary evolution of unreset coherent data wires.
    if mode != "M0":
        for token in history:
            event(token)
    reset_indices = []
    reset_wires = RESETS.get(variant, ())
    for offset, wire in enumerate(reset_wires):
        reset_indices.append(len(ops))
        ops.append(["swap", [wire, 7 + offset]])
    event("hold")
    event("R")
    ops.append(["h", [6]])
    if variant != "projection_off":
        _phase(ops, [0, 6], 4)
        _phase(ops, [2, 6], 2)
    ops.append(["h", [6]])
    request = dict(schema="nrqc-calculator-v1", backend="cyclotomic_pow2",
                   n_qubits=7 + len(reset_wires), operations=ops, decimal_places=12,
                   limits=dict(max_work=100_000_000, max_branches=4096,
                               max_coefficient_bits=4096),
                   queries=[dict(id="drain", kind="distribution", qubits=[6]),
                            dict(id="memory", kind="distribution", qubits=[3, 4, 5]),
                            dict(id="core", kind="distribution", qubits=[0, 1, 2])])
    record = dict(history=list(history), mode=mode, variant=variant,
                  active_memory_wires=list(active), coupling_edges=[list(e) for e in edges],
                  reset_wires=list(reset_wires), reset_operation_indices=reset_indices,
                  reset_environment_wires=list(range(7, 7 + len(reset_wires))),
                  initial_h_wires=list(initial_h),
                  input_steps=dict(INPUT_STEPS), phase_order=ORDER,
                  common_suffix=["hold", "R"], boundary_only=mode == "M0")
    return request, record


def _abs(value):
    return -value if real_sign(value) < 0 else value


def _law(result, query_id):
    if result.get("status") != "completed":
        raise ValueError("cannot summarize an incomplete calculator result")
    answer = next(a for a in result["answers"] if a["id"] == query_id)
    if answer.get("status") != "completed" or not answer.get("algebraically_exact"):
        raise ValueError("query is not an exact completed result")
    return {k: exact_value(v["exact"]) for k, v in answer["probabilities"].items()}


def pair_summary(target, control):
    """Exact separation; the single-shot score is model-optimal, not fitted accuracy."""
    a, b = _law(target, "drain")["1"], _law(control, "drain")["1"]
    gap = _abs(a - b)
    row = dict(target_p1=display(a), control_p1=display(b),
               drain_gap=display(gap),
               model_optimal_equal_prior_single_shot_success=display((1 + gap) / 2))
    for name in ("memory", "core"):
        left, right = _law(target, name), _law(control, name)
        total = sum((_abs(left[k] - right[k]) for k in left), a * 0) / 2
        row[name + "_distribution_TV"] = display(total)
    return row


def compare_qiskit(request, encoding, result, tolerance=2e-10):
    """Local numerical check; replace SWAP dilation by true density-matrix reset.

    Gate matrices and floating-point evolution are Qiskit's, independent of the
    calculator field arithmetic. This checks the declared circuit, not its
    mapping to electronic or thermal physics.
    """
    from math import pi
    import qiskit
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import DensityMatrix, Statevector
    from .phase_interop import phase_name

    qc = QuantumCircuit(7)
    reset_indices = set(encoding["reset_operation_indices"])
    for index, (name, wires) in enumerate(request["operations"]):
        if index in reset_indices:
            if name != "swap" or wires[1] < 7:
                raise ValueError("invalid reset dilation record")
            qc.reset(wires[0])
        elif name == "h":
            qc.h(*wires)
        else:
            phase = phase_name(name)
            if phase is None:
                raise ValueError("unsupported reference gate: " + name)
            turns, controlled = phase
            (qc.cp if controlled else qc.p)(2 * pi * float(turns), *wires)
    state = (DensityMatrix if reset_indices else Statevector).from_instruction(qc)
    max_error = 0.0
    for query in request["queries"]:
        probabilities = state.probabilities(qargs=list(reversed(query["qubits"])))
        exact = _law(result, query["id"])
        for label, value in exact.items():
            midpoint = float(display(value)["decimal"])
            max_error = max(max_error, abs(float(probabilities[int(label, 2)]) - midpoint))
    return dict(passed=max_error <= tolerance, max_absolute_error=max_error,
                tolerance=tolerance, qiskit_version=qiskit.__version__,
                reference="DensityMatrix with reset" if reset_indices else "Statevector",
                hardware_job_id=None)


def audit(output, *, compare=False, timeout_seconds=60):
    """Persist all inputs first, then compute every frozen case without selection."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "inputs").mkdir()
    (output / "results").mkdir()
    cases = [(mode, "nominal") for mode in MODES]
    cases += [("M3", variant) for variant in (*RESETS, *NEGATIVE)]
    inputs, records = {}, {}
    for mode, variant in cases:
        for history in HISTORIES:
            label = f"{mode}__{variant}__{history}"
            request, encoding = build_request(history, mode, variant)
            inputs[label] = request
            records[label] = encoding
            (output / "inputs" / (label + ".json")).write_text(json.dumps(request, indent=2) + "\n")
    model = dict(schema=SCHEMA, evidence_class="DECLARED_IDEAL_CIRCUIT_MODEL",
                 calibrated_device_model=False, roles=ROLES, encodings=records,
                 input_sha256={key: digest(value) for key, value in inputs.items()},
                 planned_cases=len(inputs), phase_order=ORDER,
                 parameter_search_performed=False,
                 physical_units_and_relaxation_constants_unassigned=True,
                 device_protocol_commit="4fa17c10c19aea5447fdea6c83e070826c1742a6",
                 calculator_base_commit="89fc3fc8fac09343f01770749c5863acfecd1ad9")
    (output / "model.json").write_text(json.dumps(model, indent=2, sort_keys=True) + "\n")
    started = time.perf_counter()
    results, references, failures = {}, {}, []
    for label, request in inputs.items():
        result = run_calculation(request, timeout_seconds=timeout_seconds)
        results[label] = result
        (output / "results" / (label + ".json")).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(label, result["status"], f"{result.get('wall_seconds', 0):.3f}s", flush=True)
        if result["status"] != "completed":
            failures.append(label)
        elif compare:
            references[label] = compare_qiskit(request, records[label], result)
    pairs = {}
    for mode, variant in cases:
        key = f"{mode}__{variant}"
        left, right = (results[key + "__" + h] for h in HISTORIES)
        if left["status"] == right["status"] == "completed":
            pairs[key] = pair_summary(left, right)
    checks = {}
    for key in ("M0__nominal", *("M3__" + x for x in NEGATIVE)):
        checks[key + "_zero_drain_gap"] = (
            exact_value(pairs[key]["drain_gap"]["exact"]) == 0 if key in pairs else None)
    for variant in ("equal_inputs", "commuting_updates"):
        key = "M3__" + variant
        checks[key + "_zero_core_and_memory_TV"] = (
            all(exact_value(pairs[key][name + "_distribution_TV"]["exact"]) == 0
                for name in ("core", "memory")) if key in pairs else None)
    comparisons = {}
    if "M3__nominal" in pairs:
        full = exact_value(pairs["M3__nominal"]["drain_gap"]["exact"])
        for mode in ("M1", "M2", "E_CA"):
            key = mode + "__nominal"
            if key in pairs:
                difference = full - exact_value(pairs[key]["drain_gap"]["exact"])
                comparisons["M3_minus_" + mode] = dict(gap_difference=display(difference),
                                                       larger_gap=real_sign(difference) > 0)
    root = Path(__file__).resolve().parents[1]
    source_paths = ("native_relational_qc/delta_ogmt.py", "native_relational_qc/calculator.py",
                    "native_relational_qc/phase_backend.py", "native_relational_qc/cyclotomic_pow2.py",
                    "native_relational_qc/phase_interop.py", "native_relational_qc/certify.py")
    checks_pass = all(value is True for value in checks.values())
    refs_pass = (len(references) == len(inputs) and all(v["passed"] for v in references.values())) if compare else None
    summary = dict(schema=SCHEMA, status="incomplete" if failures else "completed",
                   verification_passed=not failures and checks_pass and refs_pass is not False,
                   evidence_class="DECLARED_IDEAL_CIRCUIT_MODEL", hardware_job_id=None,
                   model_sha256=digest(model), planned_cases=len(inputs), completed_cases=len(inputs) - len(failures),
                   failures=failures, pairs=pairs, negative_checks=checks,
                   comparisons=comparisons, independent_numeric_comparison=references,
                   independent_numeric_comparison_passed=refs_pass,
                   qiskit_comparison_requested=compare, wall_seconds=time.perf_counter() - started,
                   python=platform.python_version(),
                   source_sha256={p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in source_paths},
                   assumptions=["All couplings are declared coherent phase gates; no fitted transistor law.",
                                "Memory wires carry phase/state, not measured charge or temperature.",
                                "No dissipative relaxation, energy, drift or noise model has been calibrated.",
                                "Single-shot success is a model-optimal two-hypothesis score, not measured accuracy.",
                                "Selective ledger reset does not erase history already transferred into other wires."],
                   hardware_validated=False, computational_advantage_established=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    manifest = {str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(output.rglob("*.json"))}
    (output / "manifest.sha256.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new directory; existing data is never overwritten")
    parser.add_argument("--compare-qiskit", action="store_true", help="optional local numeric cross-check; no service")
    parser.add_argument("--timeout", type=float, default=60, help="wall seconds per calculator request")
    args = parser.parse_args(argv)
    result = audit(args.out, compare=args.compare_qiskit, timeout_seconds=args.timeout)
    print(json.dumps({key: result[key] for key in ("status", "verification_passed", "completed_cases", "wall_seconds")}, indent=2))
    return 0 if result["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
