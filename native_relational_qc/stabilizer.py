"""Exact Clifford observations on up to the declared register bound (default 2056) of ideal circuit qubits."""
from . import pauli_engine


def expectation(circuit,paulis,**options):
    return pauli_engine.expectation(circuit,paulis,allow_t=False,**options)


def probability(circuit,assignments,**options):
    return pauli_engine.probability(circuit,assignments,allow_t=False,**options)
