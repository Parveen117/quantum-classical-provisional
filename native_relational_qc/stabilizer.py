"""Exact Clifford observations on up to 2056 ideal circuit qubits."""
from . import pauli_engine


def expectation(circuit,paulis,**options):
    return pauli_engine.expectation(circuit,paulis,allow_t=False,**options)


def probability(circuit,assignments,**options):
    return pauli_engine.probability(circuit,assignments,allow_t=False,**options)
