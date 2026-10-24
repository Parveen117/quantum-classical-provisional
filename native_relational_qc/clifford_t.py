"""Bounded exact Clifford+T observations, retaining every Pauli coefficient."""
from . import pauli_engine


def expectation(circuit,paulis,**options):
    return pauli_engine.expectation(circuit,paulis,allow_t=True,**options)


def probability(circuit,assignments,**options):
    return pauli_engine.probability(circuit,assignments,allow_t=True,**options)
