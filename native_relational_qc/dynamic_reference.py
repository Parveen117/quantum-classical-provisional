"""Small independent forward density/branch reference, for verification only.

This deliberately uses a different representation from dynamic.py: unnormalized
density matrices grouped by actual classical memory values. It is capped at six
qubits and six classical bits. No exact observer transfer code is imported.
"""
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import DensityMatrix, Operator, Pauli

from .compact import CompactCircuit
from .compact_qiskit import to_qiskit
from .dynamic import DynamicCircuit


def branches(circuit):
    if not isinstance(circuit, DynamicCircuit):
        raise TypeError('expected DynamicCircuit')
    if circuit.n_qubits > 6 or circuit.n_clbits > 6:
        raise ValueError('independent dense reference is limited to six quantum/classical bits')
    dim = 2**circuit.n_qubits
    start = np.zeros((dim, dim), dtype=complex)
    start[0, 0] = 1
    current = {0: start}
    for op in circuit.operations:
        following = {}

        def retain(memory, matrix):
            if memory in following:
                following[memory] += matrix
            else:
                following[memory] = matrix.copy()

        if op.kind == 'gate':
            local = to_qiskit(CompactCircuit(len(op.qargs)).add(op.name, *range(len(op.qargs))))
            unitary = Operator(local)
        for memory, matrix in current.items():
            if op.kind == 'gate':
                if all(((memory >> bit) & 1) == value for bit, value in op.condition):
                    matrix = DensityMatrix(matrix).evolve(unitary, list(op.qargs)).data
                retain(memory, matrix)
            elif op.kind == 'measure':
                q = op.qargs[0]
                for value in (0, 1):
                    selector = ((np.arange(dim) >> q) & 1) == value
                    projected = matrix * selector[:, None] * selector[None, :]
                    updated = (memory & ~(1 << op.cbit)) | (value << op.cbit)
                    retain(updated, projected)
            elif op.kind == 'reset':
                retain(memory, DensityMatrix(matrix).reset(list(op.qargs)).data)
            elif op.kind == 'pauli':
                mixed = np.zeros_like(matrix)
                for label, weight in op.weights:
                    mixed += float(weight) * DensityMatrix(matrix).evolve(Pauli(label), list(op.qargs)).data
                retain(memory, mixed)
        current = following
    return current


def probability(circuit, quantum=None, classical=None, *, evaluated=None):
    quantum = {} if quantum is None else dict(quantum)
    classical = {} if classical is None else dict(classical)
    result = 0.0
    for memory, matrix in (branches(circuit) if evaluated is None else evaluated).items():
        if all(((memory >> q) & 1) == bit for q, bit in classical.items()):
            for index, value in enumerate(matrix.diagonal()):
                if all(((index >> q) & 1) == bit for q, bit in quantum.items()):
                    result += float(value.real)
    return result


def expectation(circuit, paulis, classical=None, *, evaluated=None):
    classical = {} if classical is None else dict(classical)
    label = ''.join(paulis.get(q, 'I') for q in reversed(range(circuit.n_qubits)))
    operator = Pauli(label).to_matrix()
    return float(sum(np.trace(matrix @ operator).real for memory, matrix in
        (branches(circuit) if evaluated is None else evaluated).items()
        if all(((memory >> q) & 1) == bit for q, bit in classical.items())))
