"""Exact observer-first evaluation using an untruncated Pauli expansion.

Propagate the requested observation backwards through the circuit, retaining
every coefficient and cancellation. Only evaluate the |0...0> boundary at the
end. No statevector or state decision diagram is constructed by this module.
This is an exact member of the known Heisenberg/Pauli-propagation method family.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from fractions import Fraction

from .compact import CompactCircuit, ResourceLimit, _integer, operation_plan
from .exact import Exact, ZERO, ONE, IMAG, HALF, exact_gate


@lru_cache(maxsize=64)
def _matrix(name, width):
    """Exact local operator (at most three qubits), from the native gate rules."""
    dim = 2**width
    values = [[ONE if row == col else ZERO for col in range(dim)] for row in range(dim)]
    for basic, target, controls in operation_plan(width, name, tuple(range(width))):
        u = exact_gate(basic)
        for lo in range(dim):
            if (lo >> target) & 1 or not all((lo >> control) & 1 for control in controls):
                continue
            hi = lo | (1 << target)
            a, b = values[lo], values[hi]
            values[lo] = [u[0][0]*x + u[0][1]*y for x, y in zip(a, b)]
            values[hi] = [u[1][0]*x + u[1][1]*y for x, y in zip(a, b)]
    return tuple(tuple(row) for row in values)


@lru_cache(maxsize=2048)
def _conjugate(name, width, x, z):
    """Exact Pauli coefficients of U^dagger P(x,z) U."""
    if x == z == 0:
        return ((0, 0, ONE),)
    u = _matrix(name, width)
    dim = len(u)
    phase = IMAG**((x & z).bit_count())
    pu = [[ZERO] * dim for _ in range(dim)]
    for j in range(dim):
        signed = -phase if (j & z).bit_count() % 2 else phase
        pu[j ^ x] = [signed * a for a in u[j]]
    v = [[sum((u[k][row].conjugate()*pu[k][col] for k in range(dim)), ZERO)
          for col in range(dim)] for row in range(dim)]
    out = []
    for out_x in range(dim):
        for out_z in range(dim):
            phase = IMAG**((out_x & out_z).bit_count())
            trace = sum(((-phase if (j & out_z).bit_count() % 2 else phase)
                         * v[j][j ^ out_x] for j in range(dim)), ZERO)
            coefficient = trace * Exact(Fraction(1, dim))
            if coefficient:
                if coefficient.c or coefficient.d:
                    raise ArithmeticError("Hermitian Pauli image acquired an imaginary coefficient")
                out.append((out_x, out_z, coefficient))
    return tuple(out)


@dataclass(frozen=True)
class Observation:
    value: Exact
    peak_terms: int
    final_terms: int
    term_visits: int
    max_coefficient_bits: int
    source_boundary_terms: int
    gates_examined: int
    gates_proved_invariant: int

    def to_dict(self):
        return {
            "value": self.value.to_dict(), "peak_terms": self.peak_terms,
            "final_terms": self.final_terms, "term_visits": self.term_visits,
            "max_coefficient_bits": self.max_coefficient_bits,
            "source_boundary_terms": self.source_boundary_terms,
            "gates_examined": self.gates_examined,
            "gates_proved_invariant": self.gates_proved_invariant,
            "statevector_constructed": False, "truncated_terms": 0,
        }


def _propagate(circuit, terms, *, max_terms, max_work, max_coefficient_bits, progress=None):
    if not isinstance(circuit, CompactCircuit):
        raise TypeError("observer execution requires a declared CompactCircuit")
    max_terms = _integer(max_terms, "max_terms", 1, 10_000_000)
    max_work = _integer(max_work, "max_work", 1, 1_000_000_000)
    max_coefficient_bits = _integer(max_coefficient_bits, "coefficient bits", 2, 1_000_000)
    peak, visits = len(terms), 0
    peak_bits = max((coefficient.max_bits for coefficient in terms.values()), default=1)
    if peak > max_terms:
        raise ResourceLimit("observation projector exceeds term budget")
    if peak_bits > max_coefficient_bits:
        raise ResourceLimit("initial observation coefficients exceed bit budget")
    gates_examined = gates_proved_invariant = 0
    current_gate = None

    def snapshot(event):
        return {'event': event, 'peak_terms': peak, 'committed_terms': len(terms),
                'term_visits': visits, 'max_coefficient_bits': peak_bits,
                'gates_examined': gates_examined, 'gates_proved_invariant': gates_proved_invariant,
                'current_gate': current_gate}

    def fail(message):
        error = ResourceLimit(message)
        error.statistics = snapshot('resource_limit')
        if progress is not None:
            progress(error.statistics)
        raise error

    for name, qargs in reversed(circuit.operations):
        gates_examined += 1
        current_gate = (name, qargs)
        if progress is not None:
            progress(snapshot('gate_start'))
        visits += len(terms)
        if visits > max_work:
            fail("exact observer work budget exceeded")
        mask = sum(1 << q for q in qargs)
        if not any((x | z) & mask for x, z in terms):
            gates_proved_invariant += 1
            continue
        transitions = {}
        unchanged = True
        for x, z in terms:
            local_x = sum(((x >> q) & 1) << j for j, q in enumerate(qargs))
            local_z = sum(((z >> q) & 1) << j for j, q in enumerate(qargs))
            image = _conjugate(name, len(qargs), local_x, local_z)
            transitions[(x, z)] = image
            unchanged = unchanged and image == ((local_x, local_z, ONE),)
        if unchanged:
            gates_proved_invariant += 1
            continue
        result = {}
        for (x, z), coefficient in terms.items():
            for new_x, new_z, factor in transitions[(x, z)]:
                global_x = (x & ~mask) | sum(((new_x >> j) & 1) << q for j, q in enumerate(qargs))
                global_z = (z & ~mask) | sum(((new_z >> j) & 1) << q for j, q in enumerate(qargs))
                key = (global_x, global_z)
                value = result.get(key, ZERO) + coefficient * factor
                peak_bits = max(peak_bits, value.max_bits)
                if peak_bits > max_coefficient_bits:
                    fail("exact observer coefficient bit budget exceeded")
                if value:
                    result[key] = value
                else:
                    result.pop(key, None)
                peak = max(peak, len(result))
                if peak > max_terms:
                    fail("exact observer term budget exceeded; no truncation performed")
        if result == terms:
            # The complete observable can be invariant even when its individual
            # Pauli terms are permuted or mixed by the operation.
            gates_proved_invariant += 1
        terms = result
    # Only now is it lawful to discard X/Y readings against the all-zero source.
    surviving = [coefficient for (x, _), coefficient in terms.items() if x == 0]
    value = sum(surviving, ZERO)
    peak_bits = max(peak_bits, value.max_bits)
    if peak_bits > max_coefficient_bits:
        fail("exact observation result exceeds coefficient bit budget")
    if value.c or value.d:
        raise ArithmeticError("expected a real observation")
    if progress is not None:
        progress(snapshot('completed'))
    return Observation(value, peak, len(terms), visits, peak_bits, len(surviving),
                       gates_examined, gates_proved_invariant)


def probability(circuit, assignments, *, max_terms=100_000, max_work=2_000_000,
                max_coefficient_bits=4096, progress=None):
    """Exact joint/marginal probability in the final Z basis on |0...0> input."""
    max_terms = _integer(max_terms, "max_terms", 1, 10_000_000)
    assignments = dict(assignments)
    for q, bit in assignments.items():
        _integer(q, "qubit", 0, circuit.n_qubits - 1)
        _integer(bit, "outcome", 0, 1)
    if 2**len(assignments) > max_terms:
        raise ResourceLimit("observation projector exceeds term budget before allocation")
    terms = {(0, 0): ONE}
    for q, bit in assignments.items():
        terms = {new_key: value for (x, z), coefficient in terms.items()
                 for new_key, value in (((x, z), coefficient*HALF),
                                        ((x, z | (1 << q)), coefficient*(-HALF if bit else HALF)))}
    return _propagate(circuit, terms, max_terms=max_terms, max_work=max_work,
                      max_coefficient_bits=max_coefficient_bits, progress=progress)


def expectation(circuit, paulis, *, max_terms=100_000, max_work=2_000_000,
                max_coefficient_bits=4096, progress=None):
    """Exact Hermitian Pauli-string expectation, including arbitrary X/Y/Z observers."""
    x = z = 0
    for q, letter in dict(paulis).items():
        _integer(q, "qubit", 0, circuit.n_qubits - 1)
        if letter not in ("I", "X", "Y", "Z"):
            raise ValueError("observer labels must be I/X/Y/Z")
        if letter in ("X", "Y"):
            x |= 1 << q
        if letter in ("Z", "Y"):
            z |= 1 << q
    return _propagate(circuit, {(x, z): ONE}, max_terms=max_terms, max_work=max_work,
                      max_coefficient_bits=max_coefficient_bits, progress=progress)
