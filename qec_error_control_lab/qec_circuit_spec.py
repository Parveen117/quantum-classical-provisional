"""Dependency-free circuit specification plus an optional Qiskit materializer.

The exact specification is always testable.  Qiskit is imported only when a
caller explicitly requests materialization, so the core certificate remains
reproducible in a clean Python environment.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from typing import Iterable, Sequence

from qec_repetition import normalize_logical_state, sha256_payload
from qec_shor import SHOR_STABILIZERS, encode_shor, fidelity


PROTOCOL = "qec-shor-ancilla-circuit-spec-v1"
DATA_QUBITS = 9
SYNDROME_QUBITS = 8
TOTAL_QUBITS = DATA_QUBITS + SYNDROME_QUBITS


class QiskitUnavailable(RuntimeError):
    """Raised when optional Qiskit circuit materialization is requested without Qiskit."""


@dataclass(frozen=True)
class Operation:
    gate: str
    qubits: tuple[int, ...]

    def to_dict(self) -> dict[str, object]:
        return {"gate": self.gate, "qubits": list(self.qubits)}


def shor_encoding_operations() -> tuple[Operation, ...]:
    """Encode an input on data qubit 0 into three GHZ blocks."""

    operations = [
        Operation("cx", (0, 3)),
        Operation("cx", (0, 6)),
        Operation("h", (0,)),
        Operation("h", (3,)),
        Operation("h", (6,)),
    ]
    for block_start in (0, 3, 6):
        operations.append(Operation("cx", (block_start, block_start + 1)))
        operations.append(Operation("cx", (block_start, block_start + 2)))
    return tuple(operations)


def shor_syndrome_operations() -> tuple[Operation, ...]:
    """Return one non-repeated eight-ancilla stabilizer-extraction round."""

    operations: list[Operation] = []
    for stabilizer_index, stabilizer in enumerate(SHOR_STABILIZERS):
        ancilla = DATA_QUBITS + stabilizer_index
        paulis = {pauli for _, pauli in stabilizer}
        if paulis == {"Z"}:
            for data_qubit, _ in stabilizer:
                operations.append(Operation("cx", (data_qubit, ancilla)))
        elif paulis == {"X"}:
            operations.append(Operation("h", (ancilla,)))
            for data_qubit, _ in stabilizer:
                operations.append(Operation("cx", (ancilla, data_qubit)))
            operations.append(Operation("h", (ancilla,)))
        else:
            raise ValueError("v1 supports only pure-X or pure-Z stabilizer generators")
    return tuple(operations)


def _validate_operation(operation: Operation) -> None:
    if operation.gate not in {"h", "cx"}:
        raise ValueError(f"unsupported circuit-spec gate {operation.gate!r}")
    required = 1 if operation.gate == "h" else 2
    if len(operation.qubits) != required:
        raise ValueError(f"{operation.gate} requires {required} qubit operand(s)")
    if any(qubit < 0 or qubit >= TOTAL_QUBITS for qubit in operation.qubits):
        raise ValueError("operation references a qubit outside the 17-qubit register")
    if len(set(operation.qubits)) != len(operation.qubits):
        raise ValueError("operation cannot repeat a qubit operand")


def build_circuit_specification() -> dict[str, object]:
    encoding = shor_encoding_operations()
    syndrome = shor_syndrome_operations()
    for operation in (*encoding, *syndrome):
        _validate_operation(operation)
    body: dict[str, object] = {
        "protocol": PROTOCOL,
        "registers": {
            "data_qubits": list(range(0, 9)),
            "syndrome_ancillas": list(range(9, 17)),
            "syndrome_classical_bits": list(range(0, 8)),
            "data_readout_bits": list(range(8, 17)),
        },
        "encoding_operations": [operation.to_dict() for operation in encoding],
        "syndrome_operations": [operation.to_dict() for operation in syndrome],
        "stabilizers": [
            [{"qubit": qubit, "pauli": pauli} for qubit, pauli in stabilizer]
            for stabilizer in SHOR_STABILIZERS
        ],
        "measurement_policy": (
            "Measure all eight ancillas after the commuting extraction network, then measure "
            "the nine data qubits. Recovery is evaluated in declared classical post-processing."
        ),
        "claim_boundary": (
            "One ancilla per stabilizer is not a fault-tolerant ancilla construction; a single "
            "ancilla fault can propagate. The circuit is an extraction prototype, not a "
            "fault-tolerant hardware claim."
        ),
    }
    return {**body, "spec_sha256": sha256_payload(body)}


def _apply_h(state: Sequence[complex], qubit: int) -> tuple[complex, ...]:
    mask = 1 << (DATA_QUBITS - 1 - qubit)
    output = list(state)
    scale = math.sqrt(2)
    for index in range(len(state)):
        if index & mask:
            continue
        paired = index | mask
        zero_amplitude = state[index]
        one_amplitude = state[paired]
        output[index] = (zero_amplitude + one_amplitude) / scale
        output[paired] = (zero_amplitude - one_amplitude) / scale
    return tuple(output)


def _apply_cx(state: Sequence[complex], control: int, target: int) -> tuple[complex, ...]:
    control_mask = 1 << (DATA_QUBITS - 1 - control)
    target_mask = 1 << (DATA_QUBITS - 1 - target)
    output = [0j] * len(state)
    for index, amplitude in enumerate(state):
        destination = index ^ target_mask if index & control_mask else index
        output[destination] = amplitude
    return tuple(output)


def execute_encoding_spec(alpha: complex, beta: complex) -> tuple[complex, ...]:
    """Execute only the 9-data-qubit encoder operations in the exact local simulator."""

    alpha, beta = normalize_logical_state(alpha, beta)
    state = [0j] * (1 << DATA_QUBITS)
    state[0] = alpha
    state[1 << (DATA_QUBITS - 1)] = beta
    output: tuple[complex, ...] = tuple(state)
    for operation in shor_encoding_operations():
        if operation.gate == "h":
            output = _apply_h(output, operation.qubits[0])
        else:
            output = _apply_cx(output, operation.qubits[0], operation.qubits[1])
    return output


def cross_check_encoding_spec(states: Iterable[tuple[complex, complex]]) -> bool:
    return all(
        fidelity(execute_encoding_spec(alpha, beta), encode_shor(alpha, beta)) == 1.0
        for alpha, beta in states
    )


def qiskit_available() -> bool:
    try:
        import qiskit  # noqa: F401
    except ImportError:
        return False
    return True


def materialize_qiskit_experiment(
    alpha: complex = 1,
    beta: complex = 0,
    *,
    injected_error: tuple[int, str] | None = None,
):
    """Build the 17-qubit extraction circuit without submitting or simulating it."""

    try:
        from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
    except ImportError as exc:
        raise QiskitUnavailable(
            "Install requirements-qiskit.txt to materialize the optional Qiskit circuit"
        ) from exc

    alpha, beta = normalize_logical_state(alpha, beta)
    data = QuantumRegister(DATA_QUBITS, "data")
    ancilla = QuantumRegister(SYNDROME_QUBITS, "syndrome_ancilla")
    syndrome_bits = ClassicalRegister(SYNDROME_QUBITS, "syndrome")
    data_bits = ClassicalRegister(DATA_QUBITS, "data_readout")
    circuit = QuantumCircuit(data, ancilla, syndrome_bits, data_bits, name=PROTOCOL)

    if abs(alpha - 1) > 1e-15 or abs(beta) > 1e-15:
        circuit.initialize([alpha, beta], data[0])

    def qref(index: int):
        return data[index] if index < DATA_QUBITS else ancilla[index - DATA_QUBITS]

    for operation in shor_encoding_operations():
        if operation.gate == "h":
            circuit.h(qref(operation.qubits[0]))
        else:
            circuit.cx(qref(operation.qubits[0]), qref(operation.qubits[1]))

    if injected_error is not None:
        qubit, pauli = injected_error
        if qubit < 0 or qubit >= DATA_QUBITS or str(pauli).upper() not in {"X", "Y", "Z"}:
            raise ValueError("injected_error must be (data_qubit 0..8, X|Y|Z)")
        getattr(circuit, str(pauli).lower())(data[qubit])

    for operation in shor_syndrome_operations():
        if operation.gate == "h":
            circuit.h(qref(operation.qubits[0]))
        else:
            circuit.cx(qref(operation.qubits[0]), qref(operation.qubits[1]))

    circuit.measure(ancilla, syndrome_bits)
    circuit.measure(data, data_bits)
    return circuit


def credential_free_ibm_plan() -> dict[str, object]:
    """Describe, but never submit, the future IBM Runtime job interface."""

    backend = os.environ.get("IBM_QUANTUM_BACKEND", "<required>")
    shots_text = os.environ.get("IBM_QUANTUM_SHOTS", "4096")
    try:
        shots = int(shots_text)
    except ValueError as exc:
        raise ValueError("IBM_QUANTUM_SHOTS must be an integer") from exc
    if shots <= 0:
        raise ValueError("IBM_QUANTUM_SHOTS must be positive")
    return {
        "protocol": PROTOCOL,
        "backend": backend,
        "shots": shots,
        "required_environment": ["IBM_QUANTUM_BACKEND"],
        "credential_policy": (
            "Use QiskitRuntimeService account discovery or environment configuration; "
            "never place an IBM token in source, plan, certificate, or command output."
        ),
        "submission_performed": False,
    }
