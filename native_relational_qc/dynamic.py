"""Exact selected queries for quantum circuits with classical outcome memory.

The dual observable uses Pauli strings times classical Walsh characters. Complete
coefficients are retained through measurement, overwrite, reset and feedforward.
This is standard quantum-instrument duality in an explicit native representation;
no trajectory, density matrix or statevector is constructed by this evaluator.
"""
from dataclasses import dataclass
from fractions import Fraction

from .compact import ResourceLimit, _integer, operation_plan
from .exact import Exact, ZERO, ONE, HALF
from .observer import _conjugate


@dataclass(frozen=True)
class Instruction:
    kind: str
    qargs: tuple
    name: str = ''
    condition: tuple = ()
    cbit: int = -1
    weights: tuple = ()


class DynamicCircuit:
    """Straight-line program, initially |0...0> and all classical bits zero.

    Conditions are conjunctions of bit equalities on the current memory. A
    measurement overwrites its destination bit, including on repeated rounds.
    """
    def __init__(self, n_qubits, n_clbits=0):
        self.n_qubits = _integer(n_qubits, 'qubits', 1, 256)
        self.n_clbits = _integer(n_clbits, 'classical bits', 0, 256)
        self._operations = []

    @property
    def operations(self):
        return tuple(self._operations)

    def _assignments(self, values, classical=False):
        limit = self.n_clbits if classical else self.n_qubits
        out = dict(values)
        for index, bit in out.items():
            _integer(index, 'classical bit' if classical else 'qubit', 0, limit - 1)
            _integer(bit, 'outcome', 0, 1)
        return tuple(sorted(out.items()))

    def add(self, name, *qargs, condition=None):
        operation_plan(self.n_qubits, name, qargs)
        condition = self._assignments({} if condition is None else condition, True)
        self._operations.append(Instruction('gate', tuple(qargs), name, condition))
        return self

    def measure(self, qubit, cbit):
        _integer(qubit, 'qubit', 0, self.n_qubits - 1)
        _integer(cbit, 'classical bit', 0, self.n_clbits - 1)
        self._operations.append(Instruction('measure', (qubit,), cbit=cbit))
        return self

    def reset(self, qubit):
        _integer(qubit, 'qubit', 0, self.n_qubits - 1)
        self._operations.append(Instruction('reset', (qubit,)))
        return self

    def pauli_channel(self, qubit, weights):
        """Independent Pauli mixture per invocation; rational probabilities only."""
        _integer(qubit, 'qubit', 0, self.n_qubits - 1)
        weights = dict(weights)
        if not weights or any(label not in ('I', 'X', 'Y', 'Z') for label in weights):
            raise ValueError('Pauli channel requires I/X/Y/Z weights')
        for value in weights.values():
            if isinstance(value, bool) or not isinstance(value, (int, Fraction)) or value < 0:
                raise ValueError('channel weights must be nonnegative rational probabilities')
        if sum(weights.values(), Fraction()) != 1:
            raise ValueError('Pauli channel weights must sum to one exactly')
        self._operations.append(Instruction('pauli', (qubit,),
            weights=tuple((label, Fraction(value)) for label, value in sorted(weights.items()) if value)))
        return self


@dataclass(frozen=True)
class DynamicObservation:
    value: Exact
    peak_terms: int
    final_terms: int
    work_units: int
    max_coefficient_bits: int
    instructions_examined: int
    invariant_instructions: int
    measurements: int
    resets: int
    conditioned_gates: int
    pauli_channels: int

    def to_dict(self):
        return {**{key: value for key, value in self.__dict__.items() if key != 'value'},
                'value': self.value.to_dict(), 'statevector_constructed': False,
                'density_matrix_constructed': False, 'trajectories_enumerated': 0,
                'truncated_terms': 0}


class _Budget:
    def __init__(self, max_terms, max_work, max_coefficient_bits):
        self.terms = _integer(max_terms, 'max_terms', 1, 10_000_000)
        self.work = _integer(max_work, 'max_work', 1, 1_000_000_000)
        self.bits = _integer(max_coefficient_bits, 'coefficient bits', 2, 1_000_000)
        self.peak = self.used = 0
        self.peak_bits = 1

    def tick(self, count=1):
        self.used += count
        if self.used > self.work:
            raise ResourceLimit('exact dynamic observer work budget exceeded')

    def coefficient(self, value):
        self.peak_bits = max(self.peak_bits, value.max_bits)
        if self.peak_bits > self.bits:
            raise ResourceLimit('exact dynamic coefficient bit budget exceeded')

    def put(self, result, key, value):
        self.tick()
        self.coefficient(value)
        value = result.get(key, ZERO) + value
        self.coefficient(value)
        if value:
            result[key] = value
        else:
            result.pop(key, None)
        self.peak = max(self.peak, len(result))
        if self.peak > self.terms:
            raise ResourceLimit('exact dynamic term budget exceeded; no truncation performed')


def _gate_image(op, x, z):
    mask = sum(1 << q for q in op.qargs)
    local_x = sum(((x >> q) & 1) << j for j, q in enumerate(op.qargs))
    local_z = sum(((z >> q) & 1) << j for j, q in enumerate(op.qargs))
    for new_x, new_z, factor in _conjugate(op.name, len(op.qargs), local_x, local_z):
        yield ((x & ~mask) | sum(((new_x >> j) & 1) << q for j, q in enumerate(op.qargs)),
               (z & ~mask) | sum(((new_z >> j) & 1) << q for j, q in enumerate(op.qargs)), factor)


def _predicate(condition, budget):
    if 2**len(condition) > budget.terms:
        raise ResourceLimit('classical predicate exceeds term budget before allocation')
    result = {0: ONE}
    for bit, outcome in condition:
        following = {}
        for mask, coefficient in result.items():
            budget.put(following, mask, coefficient*HALF)
            budget.put(following, mask | (1 << bit), coefficient*(-HALF if outcome else HALF))
        result = following
    return result


def _run(circuit, terms, budget):
    invariant = 0
    kinds = {'measure': 0, 'reset': 0, 'pauli': 0}
    conditioned = 0
    for op in reversed(circuit.operations):
        budget.tick(1 + len(terms))
        result = {}
        if op.kind == 'gate':
            conditioned += bool(op.condition)
            if op.condition:
                # U is applied only when the current classical predicate is true:
                # O -> O + delta(c) * (U^dagger O U - O).
                delta = {}
                for (x, z, memory), value in terms.items():
                    budget.put(delta, (x, z, memory), -value)
                    for new_x, new_z, factor in _gate_image(op, x, z):
                        budget.put(delta, (new_x, new_z, memory), value*factor)
                result = terms.copy()
                if delta:
                    predicate = _predicate(op.condition, budget)
                    for (x, z, memory), value in delta.items():
                        for mask, factor in predicate.items():
                            budget.put(result, (x, z, memory ^ mask), value*factor)
            else:
                for (x, z, memory), value in terms.items():
                    for new_x, new_z, factor in _gate_image(op, x, z):
                        budget.put(result, (new_x, new_z, memory), value*factor)
        else:
            kinds[op.kind] += 1
            mask = 1 << op.qargs[0]
            for (x, z, memory), value in terms.items():
                if op.kind == 'measure':
                    if x & mask:
                        continue
                    record = 1 << op.cbit
                    budget.put(result, (x, z ^ (mask if memory & record else 0), memory & ~record), value)
                elif op.kind == 'reset':
                    if not x & mask:
                        budget.put(result, (x, z & ~mask, memory), value)
                elif op.kind == 'pauli':
                    # Conjugation by a Pauli changes only the sign of a Pauli.
                    factor = Fraction()
                    for label, weight in op.weights:
                        anti = ((label in ('X', 'Y') and bool(z & mask))
                                ^ (label in ('Z', 'Y') and bool(x & mask)))
                        factor += -weight if anti else weight
                    budget.put(result, (x, z, memory), value*Exact(factor))
        invariant += result == terms
        terms = result
    value = ZERO
    for (x, _, _), coefficient in terms.items():
        budget.tick()
        if x == 0:  # all classical characters also equal +1 on initial c=0
            value += coefficient
            budget.coefficient(value)
    if value.c or value.d:
        raise ArithmeticError('Hermitian dynamic observation acquired an imaginary value')
    return DynamicObservation(value, budget.peak, len(terms), budget.used, budget.peak_bits,
        len(circuit.operations), invariant, kinds['measure'], kinds['reset'], conditioned, kinds['pauli'])


def _prepare(circuit, paulis, quantum, classical, limits):
    if not isinstance(circuit, DynamicCircuit):
        raise TypeError('dynamic observation requires DynamicCircuit')
    budget = _Budget(**limits)
    quantum = circuit._assignments(quantum)
    classical = circuit._assignments(classical, True)
    if 2**(len(quantum) + len(classical)) > budget.terms:
        raise ResourceLimit('joint outcome projector exceeds term budget before allocation')
    x = z = 0
    for q, label in dict(paulis).items():
        _integer(q, 'qubit', 0, circuit.n_qubits - 1)
        if label not in ('I', 'X', 'Y', 'Z'):
            raise ValueError('Pauli observer labels must be I/X/Y/Z')
        x |= (1 << q) if label in ('X', 'Y') else 0
        z |= (1 << q) if label in ('Z', 'Y') else 0
    terms = {}
    budget.put(terms, (x, z, 0), ONE)
    for is_classical, assignments in ((False, quantum), (True, classical)):
        for q, bit in assignments:
            following = {}
            for (x, z, memory), coefficient in terms.items():
                budget.put(following, (x, z, memory), coefficient*HALF)
                key = (x, z, memory ^ (1 << q)) if is_classical else (x, z ^ (1 << q), memory)
                budget.put(following, key, coefficient*(-HALF if bit else HALF))
            terms = following
    return _run(circuit, terms, budget)


def probability(circuit, quantum=None, classical=None, *, max_terms=100_000,
                max_work=2_000_000, max_coefficient_bits=4096):
    """Exact JOINT probability of final quantum outcomes and classical memory.

    Unspecified outputs are marginalized. This is not postselection or division
    by a classical event's probability. An empty query evaluates total mass.
    """
    return _prepare(circuit, {}, {} if quantum is None else quantum,
        {} if classical is None else classical, dict(max_terms=max_terms,
        max_work=max_work, max_coefficient_bits=max_coefficient_bits))


def expectation(circuit, paulis, *, classical=None, max_terms=100_000,
                max_work=2_000_000, max_coefficient_bits=4096):
    """Exact Pauli expectation, optionally multiplied by a classical event.

    With classical=..., the result is an unnormalized joint moment. Divide by
    that event's probability explicitly to obtain a conditional expectation.
    """
    return _prepare(circuit, paulis, {}, {} if classical is None else classical,
        dict(max_terms=max_terms, max_work=max_work, max_coefficient_bits=max_coefficient_bits))
