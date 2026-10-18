"""Offline static-circuit bridge. Imports Qiskit only when called.

This module never constructs a Runtime service or submits jobs. The evaluator
uses NumPy; Qiskit supplies gate semantics at import and an independent reference.
"""
from __future__ import annotations

import numpy as np
from .algebra import MAX_GATE_QUBITS
from .circuit import Circuit


def from_qiskit(qc) -> Circuit:
    from qiskit import QuantumCircuit
    from qiskit.circuit import Barrier, Gate, Measure
    from qiskit.quantum_info import Operator

    if not isinstance(qc, QuantumCircuit):
        raise TypeError("expected a QuantumCircuit")
    if qc.parameters:
        raise ValueError("bind every circuit parameter before import")
    if getattr(qc, "num_vars", 0) or getattr(qc, "num_stretches", 0):
        raise ValueError("classical variables and timing stretches require a different engine")
    out = Circuit(qc.num_qubits, qc.num_clbits).phase(float(qc.global_phase))
    for item in qc.data:
        instruction = item.operation
        if getattr(instruction, "condition", None) is not None:
            raise ValueError("classical conditional execution is not supported in v1")
        if isinstance(instruction, Barrier):
            continue
        qargs = tuple(qc.find_bit(q).index for q in item.qubits)
        if isinstance(instruction, Measure):
            out.measure(qargs[0], qc.find_bit(item.clbits[0]).index)
            continue
        if not isinstance(instruction, Gate) or item.clbits:
            raise ValueError(f"unsupported nonunitary/dynamic/timed instruction: {instruction.name}")
        if instruction.num_qubits > MAX_GATE_QUBITS:
            raise ValueError("decompose large gates before import; gate-matrix resource limit")
        # Full operator phase is essential when a gate is controlled.
        try:
            matrix = Operator(instruction).data
        except Exception as exc:
            raise ValueError(f"cannot resolve a finite unitary for {instruction.name}") from exc
        if instruction.num_qubits == 0:
            if matrix.shape != (1, 1) or not np.isfinite(matrix).all() or abs(abs(matrix[0, 0]) - 1) > 1e-12:
                raise ValueError("invalid scalar phase operation")
            out.phase(float(np.angle(matrix[0, 0])))
            continue
        out.append(matrix, qargs, instruction.name)
    return out


def to_qiskit(circuit: Circuit):
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import UnitaryGate

    qc = QuantumCircuit(circuit.n_qubits, circuit.n_clbits)
    qc.global_phase = circuit.global_phase
    for op in circuit.operations:
        # The matrix is authoritative, not an unchecked human-readable gate label.
        qc.append(UnitaryGate(op.matrix, label=op.name), list(op.qargs))
    for q, c in circuit.measurements:
        qc.measure(q, c)
    return qc


def compile_for_target(circuit: Circuit, target, *, seed_transpiler=117, optimization_level=1):
    """Compile offline against a supplied Target; this is not job submission.

    The returned Qiskit circuit carries the physical layout and classical map.
    Target/calibration provenance must accompany any later hardware result.
    """
    from qiskit import transpile
    if target is None:
        raise ValueError("an explicit backend Target is required")
    return transpile(to_qiskit(circuit), target=target,
                     seed_transpiler=seed_transpiler, optimization_level=optimization_level)


def compare_qiskit(qc, *, tolerance=1e-10):
    """Deterministic local software comparison on this circuit's physical indices."""
    from qiskit.quantum_info import Statevector
    import qiskit

    if not np.isfinite(tolerance) or not 0 < tolerance <= 1e-6:
        raise ValueError("comparison tolerance must be in (0, 1e-6]")
    native = from_qiskit(qc)
    reference = Statevector.from_instruction(qc.remove_final_measurements(inplace=False))
    actual = native.state().amplitudes
    error = float(np.max(np.abs(actual - reference.data)))
    fidelity = min(1.0, float(abs(np.vdot(reference.data, actual)) ** 2))
    if native.measurements:
        pairs = sorted(native.measurements, key=lambda pair: pair[1])
        marginal = reference.probabilities(qargs=[q for q, _ in pairs])
        expected = {format(i, f"0{native.n_clbits}b"): 0.0
                    for i in range(2**native.n_clbits)}
        for index, p in enumerate(marginal):
            bits = ["0"] * native.n_clbits
            for j, (_, c) in enumerate(pairs):
                bits[native.n_clbits - 1 - c] = str((index >> j) & 1)
            expected["".join(bits)] = float(p)
    else:
        expected = {format(i, f"0{native.n_qubits}b"): float(p)
                    for i, p in enumerate(reference.probabilities())}
    observed = native.probabilities()
    tvd = sum(abs(observed[k] - expected[k]) for k in expected) / 2
    norm_error = abs(float(np.vdot(actual, actual).real) - 1)
    passed = all(np.isfinite(x) and x <= tolerance for x in (error, tvd, norm_error))
    return {
        "evidence_class": "LOCAL_IDEAL_UNITARY_SOFTWARE_COMPARISON",
        "passed": bool(passed), "circuit_sha256": native.digest(),
        "qubits": native.n_qubits, "gates": len(native.operations),
        "qiskit_version": qiskit.__version__, "numpy_version": np.__version__,
        "max_amplitude_error_including_global_phase": error,
        "state_fidelity": fidelity, "probability_tvd": tvd,
        "norm_error": norm_error, "tolerance": tolerance,
        "native_probabilities": observed, "reference_probabilities": expected,
        "hardware_job_id": None,
    }
