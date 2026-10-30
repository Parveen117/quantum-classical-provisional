"""Guarded, exact circuit reduction with an explicit global-phase ledger.

Only disjoint gates may be crossed. A pair is replaced by a named gate (or
identity) only through an exact matrix identity. This is a deterministic local
reduction strategy, not a canonical form for all equivalent quantum circuits.
"""
from dataclasses import dataclass
from functools import lru_cache

from .compact import CompactCircuit, _integer
from .exact import ONE, ZERO, OMEGA, exact_gate


_SINGLES = ('id', 'x', 'y', 'z', 'h', 's', 'sdg', 't', 'tdg', 'sx', 'sxdg')
_CONTROLLED = {('cx', 'cx'): 'id', ('cz', 'cz'): 'id',
               ('ch', 'ch'): 'id', ('cs', 'cs'): 'cz',
               ('ct', 'ct'): 'cs', ('swap', 'swap'): 'id',
               ('ccx', 'ccx'): 'id'}


def _multiply(later, earlier):
    return tuple(tuple(sum((later[i][k] * earlier[k][j] for k in range(2)), ZERO)
                       for j in range(2)) for i in range(2))


def _phase(exponent):
    out = ONE
    for _ in range(exponent % 8):
        out *= OMEGA
    return out


@lru_cache(maxsize=1)
def _pair_table():
    # U_later U_earlier = omega**e U_replacement, as full matrices, not
    # equality of probabilities, determinants, or absolute values.
    matrices = {name: exact_gate(name) for name in _SINGLES}
    lookup = {}
    for exponent in range(8):
        phase = _phase(exponent)
        for name, matrix in matrices.items():
            key = tuple(tuple(phase * x for x in row) for row in matrix)
            lookup[key] = (name, exponent)
    return {(earlier, later): lookup[product]
            for earlier, a in matrices.items() for later, b in matrices.items()
            if (product := _multiply(b, a)) in lookup}


def _canonical(name, qubits):
    phase = 0
    if name in ('k', 'rk', 'r'):
        phase = 6 if name == 'r' else 0  # R = -i Y, not Y.
        name = {'k': 'z', 'rk': 'x', 'r': 'y'}[name]
    if name in ('cz', 'swap'):
        qubits = tuple(sorted(qubits))
    elif name == 'ccx':
        qubits = (*sorted(qubits[:2]), qubits[2])
    return name, qubits, phase


@dataclass(frozen=True)
class Reduction:
    circuit: CompactCircuit
    input_gates: int
    pair_rewrites: int
    canonicalized_gates: int
    explicit_identities_removed: int
    phase_exponent: int

    @property
    def phase(self):
        return _phase(self.phase_exponent)

    def to_dict(self):
        return dict(method='exact-local-v1', input_gates=self.input_gates,
                    output_gates=len(self.circuit.operations),
                    removed_gates=self.input_gates-len(self.circuit.operations),
                    pair_rewrites=self.pair_rewrites,
                    canonicalized_gates=self.canonicalized_gates,
                    explicit_identities_removed=self.explicit_identities_removed,
                    phase_exponent_mod_8=self.phase_exponent,
                    global_phase=self.phase.to_dict(),
                    operator_relation='U_input = global_phase * U_reduced',
                    crossed_gates='disjoint support only',
                    globally_canonical=False)


def reduce_circuit(circuit, *, max_input_gates=100_000):
    """Return a new circuit and the phase needed for full operator equality.

    A stack per wire identifies the last surviving gate on every operand. Pair
    reduction requires one common predecessor on exactly the same operands;
    hence all crossed surviving gates act on disjoint wires. Every rewrite
    removes at least one gate. Work and storage are linear in input length for
    this fixed gate alphabet (apart from one fixed-size exact table setup).

    The ledger is necessary for amplitudes and for coherently controlling the
    complete program. Terminal probabilities/expectations ignore only this
    recorded *global* phase; conditional and relative phases are retained.
    """
    if not isinstance(circuit, CompactCircuit):
        raise TypeError('exact reduction requires CompactCircuit')
    cap = _integer(max_input_gates, 'max_input_gates', 0, 1_000_000)
    operations = circuit.operations
    if len(operations) > cap:
        raise ValueError('exact reduction input gate cap exceeded')
    table = _pair_table()
    stacks = [[] for _ in range(circuit.n_qubits)]
    retained = []
    phase = rewrites = aliases = identities = 0
    for original_name, original_qubits in operations:
        name, qubits, delta = _canonical(original_name, original_qubits)
        phase = (phase + delta) % 8
        aliases += (name, qubits) != (original_name, original_qubits)
        if name == 'id':
            identities += 1
            continue
        while True:
            predecessor = stacks[qubits[0]][-1] if stacks[qubits[0]] else None
            if predecessor is None or any(not stacks[q] or stacks[q][-1] != predecessor for q in qubits):
                break
            earlier, operands = retained[predecessor]
            if operands != qubits:
                break
            rule = table.get((earlier, name)) if len(qubits) == 1 else (
                (_CONTROLLED[earlier, name], 0) if (earlier, name) in _CONTROLLED else None)
            if rule is None:
                break
            retained[predecessor] = None
            for q in qubits:
                stacks[q].pop()
            rewrites += 1
            name, delta = rule
            phase = (phase + delta) % 8
            if name == 'id':
                break
            name, qubits, delta = _canonical(name, qubits)
            phase = (phase + delta) % 8
        if name != 'id':
            index = len(retained)
            retained.append((name, qubits))
            for q in qubits:
                stacks[q].append(index)
    out = type(circuit)(circuit.n_qubits)
    for operation in retained:
        if operation is not None:
            out.add(operation[0], *operation[1])
    return Reduction(out, len(operations), rewrites, aliases, identities, phase)
