"""Small executable dynamic workloads, including recovery negative controls."""
from fractions import Fraction

from .dynamic import DynamicCircuit, expectation
from .exact import ONE, Exact


def teleport(preparation=('h', 't'), *, corrections=True):
    c = DynamicCircuit(3, 2)
    for gate in preparation:
        c.add(gate, 0)
    c.add('h', 1).add('cx', 1, 2).add('cx', 0, 1).add('h', 0)
    c.measure(0, 0).measure(1, 1)
    if corrections:
        c.add('x', 2, condition={1: 1}).add('z', 2, condition={0: 1})
    c.reset(0).reset(1)
    return c


def _parity(circuit, support, ancilla, bit, axis='Z'):
    circuit.reset(ancilla)
    if axis == 'X':
        circuit.add('h', ancilla)
        for q in support:
            circuit.add('cx', ancilla, q)
        circuit.add('h', ancilla)
    else:
        for q in support:
            circuit.add('cx', q, ancilla)
    circuit.measure(ancilla, bit)


def bitflip_recovery(*, rounds=1, probability=Fraction(1, 10), corrections=True):
    """Reference-entangled logical qubit, independent X noise each round.

    Data=0,1,2; reused syndrome ancilla=3; external reference=4. Classical bits
    are overwritten on each round. Final data qubit 0 is decoded.
    """
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= 128:
        raise ValueError('rounds must be 1..128')
    c = DynamicCircuit(5, 2).add('h', 4).add('cx', 4, 0)
    c.add('cx', 0, 1).add('cx', 0, 2)
    for _ in range(rounds):
        for q in range(3):
            c.pauli_channel(q, {'I': 1-probability, 'X': probability})
        _parity(c, (0, 1), 3, 0)
        _parity(c, (1, 2), 3, 1)
        if corrections:
            c.add('x', 0, condition={0: 1, 1: 0})
            c.add('x', 1, condition={0: 1, 1: 1})
            c.add('x', 2, condition={0: 0, 1: 1})
    c.reset(3).add('cx', 0, 2).add('cx', 0, 1)
    return c


def shor_recovery(error=None, *, corrections=True):
    """Nine-data-qubit Shor code with one reused syndrome ancilla and reference.

    This is a new ideal recovery workload, not a replay of recorded IBM jobs.
    error=(qubit, 'x'/'y'/'z'), or None. q10 is external Bell reference.
    """
    c = DynamicCircuit(11, 8).add('h', 10).add('cx', 10, 0)
    c.add('cx', 0, 3).add('cx', 0, 6)
    for start in (0, 3, 6):
        c.add('h', start).add('cx', start, start+1).add('cx', start, start+2)
    if error is not None:
        q, name = error
        if isinstance(q, bool) or not isinstance(q, int) or not 0 <= q < 9 or name not in ('x', 'y', 'z'):
            raise ValueError('Shor error must be one X/Y/Z on a data qubit')
        c.add(name, q)
    for block, start in enumerate((0, 3, 6)):
        _parity(c, (start, start+1), 9, 2*block)
        _parity(c, (start+1, start+2), 9, 2*block+1)
    _parity(c, tuple(range(6)), 9, 6, 'X')
    _parity(c, tuple(range(3, 9)), 9, 7, 'X')
    if corrections:
        for block, start in enumerate((0, 3, 6)):
            a, b = 2*block, 2*block+1
            c.add('x', start, condition={a: 1, b: 0})
            c.add('x', start+1, condition={a: 1, b: 1})
            c.add('x', start+2, condition={a: 0, b: 1})
        c.add('z', 0, condition={6: 1, 7: 0})
        c.add('z', 3, condition={6: 1, 7: 1})
        c.add('z', 6, condition={6: 0, 7: 1})
    c.reset(9)
    for start in (0, 3, 6):
        c.add('cx', start, start+2).add('cx', start, start+1).add('h', start)
    c.add('cx', 0, 6).add('cx', 0, 3)
    return c


def bell_fidelity(circuit, logical, reference, **limits):
    """Expectation of (II + XX - YY + ZZ)/4 on the decoded/reference pair."""
    readings = {axis: expectation(circuit, {logical: axis, reference: axis}, **limits)
                for axis in ('X', 'Y', 'Z')}
    value = (ONE + readings['X'].value - readings['Y'].value + readings['Z'].value) / Exact(4)
    return value, readings
