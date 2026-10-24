"""Complete sparse classical output laws from exact native marginal queries.

Globally deterministic bits are proved by their marginals before branching over
the remaining bits. No outcomes are sampled or assigned by an error label.
"""
from dataclasses import dataclass

from .compact import ResourceLimit, _integer
from .dynamic import DynamicCircuit, probability
from .exact import Exact, ZERO, ONE


def real_sign(value):
    """Exact order test in Q(sqrt(2)); no floating comparison or tolerance."""
    if not isinstance(value, Exact) or value.c or value.d:
        raise ValueError('expected a real exact value')
    a, b = value.a, value.b
    sign = lambda x: (x > 0) - (x < 0)
    if not a: return sign(b)
    if not b or sign(a) == sign(b): return sign(a)
    return sign(a) * sign(a*a - 2*b*b)


@dataclass(frozen=True)
class ReadoutDistribution:
    bits_low_first: tuple
    probabilities: tuple
    deterministic_bits: tuple
    native_queries: int
    peak_query_terms: int
    total_query_work: int

    def to_dict(self):
        return {'bits_low_first': list(self.bits_low_first),
            'probabilities': {key: value.to_dict() for key, value in self.probabilities},
            'deterministic_bits': dict(self.deterministic_bits), 'native_queries': self.native_queries,
            'peak_query_terms': self.peak_query_terms, 'total_query_work': self.total_query_work,
            'sampled': False, 'complete_distribution': True}


def classical_distribution(circuit, bits=None, *, max_outcomes=1024, max_queries=10000, **observer_limits):
    """Exact complete distribution on selected classical bits, subject to guards.

    Display strings list the requested bits in reverse order, like Qiskit bit
    strings. Budgets for the underlying observer apply separately to each query.
    No incomplete distribution is returned on a resource-limit failure.
    """
    if not isinstance(circuit, DynamicCircuit):
        raise TypeError('expected DynamicCircuit')
    bits = tuple(range(circuit.n_clbits)) if bits is None else tuple(bits)
    for bit in bits: _integer(bit, 'classical bit', 0, circuit.n_clbits-1)
    if len(set(bits)) != len(bits): raise ValueError('requested bits must be unique')
    max_outcomes = _integer(max_outcomes, 'max_outcomes', 1, 1_000_000)
    max_queries = _integer(max_queries, 'max_queries', 1, 100_000_000)
    count = peak = work = 0

    def query(assignments):
        nonlocal count, peak, work
        if count >= max_queries:
            raise ResourceLimit('complete readout query budget exceeded')
        result = probability(circuit, classical=assignments, **observer_limits)
        count += 1
        peak = max(peak, result.peak_terms)
        work += result.work_units
        return result.value

    if query({}) != ONE: raise ArithmeticError('readout source is not normalized')
    fixed, active, marginals = {}, [], {}
    for bit in bits:
        pzero = query({bit: 0})
        if real_sign(pzero) < 0 or real_sign(ONE-pzero) < 0:
            raise ArithmeticError('invalid probability in exact readout')
        if pzero == ONE: fixed[bit] = 0
        elif pzero == ZERO: fixed[bit] = 1
        else:
            active.append(bit)
            marginals[bit] = pzero
    stack = [(0, {}, ONE)]
    outcomes = {}
    while stack:
        index, prefix, mass = stack.pop()
        if index == len(active):
            if len(outcomes) >= max_outcomes:
                raise ResourceLimit('complete readout outcome budget exceeded')
            values = {**fixed, **prefix}
            key = ''.join(str(values[bit]) for bit in reversed(bits))
            outcomes[key] = mass
            continue
        bit = active[index]
        pzero = marginals[bit] if not prefix else query({**prefix, bit: 0})
        pone = mass-pzero
        if real_sign(pzero) < 0 or real_sign(pone) < 0:
            raise ArithmeticError('inconsistent exact readout marginals')
        for value, weight in ((1, pone), (0, pzero)):
            if weight:
                stack.append((index+1, {**prefix, bit: value}, weight))
    if sum(outcomes.values(), ZERO) != ONE:
        raise ArithmeticError('complete readout lost probability mass')
    return ReadoutDistribution(bits, tuple(sorted(outcomes.items())), tuple(sorted(fixed.items())),
                               count, peak, work)
