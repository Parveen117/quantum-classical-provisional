"""Exact finite-cut information/curvature tensor from the native EMK product.

Source contract: CID-D2 equation (2), restricted to a rank-one circuit cut,
with B_a = -i H_a and signed Pauli-word H_a. This is an explicit adapter,
not a derivation of spacetime, a full UGD numeral algebra, or an MPS replacement.
"""
from __future__ import annotations

from dataclasses import dataclass

from .compact import CompactCircuit, ResourceLimit, _integer
from .exact import Exact, ZERO, ONE, IMAG


@dataclass(frozen=True)
class EMKBlock:
    """a I + b K + c R + d RK; K²=I, R²=-I, KR=-RK."""
    a: Exact = ZERO
    b: Exact = ZERO
    c: Exact = ZERO
    d: Exact = ZERO

    def __post_init__(self):
        for name in ('a', 'b', 'c', 'd'):
            object.__setattr__(self, name, Exact.coerce(getattr(self, name)))

    @property
    def coefficients(self):
        return self.a, self.b, self.c, self.d

    def __mul__(self, other):
        if not isinstance(other, EMKBlock):
            return EMKBlock(*(v*other for v in self.coefficients))
        result = [ZERO]*4
        # Ordered basis R^r K^k. Moving K past R and reducing R² retain signs.
        for i, x in enumerate(self.coefficients):
            r, k = divmod(i, 2)
            for j, y in enumerate(other.coefficients):
                s, t = divmod(j, 2)
                index = 2*(r ^ s)+(k ^ t)
                result[index] += x*y*(-1 if (k*s+r*s) % 2 else 1)
        return EMKBlock(*result)

    def dagger(self):
        a,b,c,d = (v.conjugate() for v in self.coefficients)
        return EMKBlock(a,b,-c,d)

    def matrix(self):
        a,b,c,d = self.coefficients
        return ((a+b,d-c),(d+c,a-b))


_PAULI = {'I':EMKBlock(1), 'X':EMKBlock(d=1),
          'Y':EMKBlock(c=IMAG), 'Z':EMKBlock(b=1)}


def _product_table():
    table = {}
    for a, left in _PAULI.items():
        for b, right in _PAULI.items():
            product = left*right
            matches = [(phase, name) for name, block in _PAULI.items()
                       for phase in (ONE, -ONE, IMAG, -IMAG) if block*phase == product]
            if len(matches) != 1:
                raise ArithmeticError('EMK product has no unique Pauli presentation')
            table[a,b] = matches[0]
    return table


_PRODUCT = _product_table()


def word_product(left, right):
    """Ordered product, keeping its central phase; inputs are Pauli site maps."""
    phase, word = ONE, {}
    for q in sorted(set(left) | set(right)):
        local_phase, local_word = _PRODUCT[left.get(q,'I'), right.get(q,'I')]
        phase *= local_phase
        if local_word != 'I':
            word[q] = local_word
    return phase, word


def validate_generators(generators, n):
    if not isinstance(generators,(list,tuple)) or not 1 <= len(generators) <= 8:
        raise ValueError('geometry requires 1..8 signed Pauli generators')
    out = []
    for item in generators:
        if not isinstance(item,(list,tuple)) or len(item)!=2:
            raise ValueError('generator must be (sign, Pauli site map)')
        sign, word = item
        _integer(sign,'generator sign',-1,1)
        if sign == 0 or not isinstance(word,dict):
            raise ValueError('generator sign must be -1 or 1, with a Pauli site map')
        clean = {}
        for q, letter in word.items():
            _integer(q,'qubit',0,n-1)
            if letter not in ('I','X','Y','Z'):
                raise ValueError('generator entries must be I/X/Y/Z')
            if letter != 'I':
                clean[q] = letter
        out.append((sign,clean))
    return out


def evaluation_count(generators):
    """Exact number of distinct nonidentity Pauli expectations needed."""
    words = {tuple(sorted(word.items())) for _,word in generators}
    for a, (_,left) in enumerate(generators):
        for _,right in generators[a+1:]:
            words.add(tuple(sorted(word_product(left,right)[1].items())))
    words.discard(())
    return len(words)


def _guard(value, max_bits):
    if value.max_bits > max_bits:
        raise ResourceLimit('exact geometry postprocessing coefficient bit budget exceeded')
    return value


def _factor(matrix, max_bits):
    """Exact column dependencies from RREF, with no tolerance or rank cutoff."""
    size = len(matrix)
    rows = [list(row) for row in matrix]
    basis = []
    for col in range(size):
        pivot = next((i for i in range(len(basis),size) if rows[i][col]), None)
        if pivot is None:
            continue
        r = len(basis)
        rows[r], rows[pivot] = rows[pivot], rows[r]
        scale = rows[r][col]
        rows[r] = [_guard(v/scale,max_bits) for v in rows[r]]
        for i in range(size):
            if i != r and rows[i][col]:
                factor = rows[i][col]
                rows[i] = [_guard(v-_guard(factor*w,max_bits),max_bits)
                           for v,w in zip(rows[i],rows[r])]
        basis.append(col)
    coordinates = rows[:len(basis)]
    nullspace = []
    for free in range(size):
        if free in basis:
            continue
        vector = [ZERO]*size
        vector[free] = ONE
        for r,b in enumerate(basis):
            vector[b] = -coordinates[r][free]
        nullspace.append(vector)
    return dict(rank=len(basis),basis_indices=basis,coordinates=coordinates,nullspace=nullspace)


def _reconstruct(matrix, factor, max_bits):
    basis, coordinates = factor['basis_indices'],factor['coordinates']
    result = []
    for i in range(len(matrix)):
        row = []
        for j in range(len(matrix)):
            value = ZERO
            for a,p in enumerate(basis):
                for b,q in enumerate(basis):
                    term = _guard(coordinates[a][i].conjugate()*matrix[p][q],max_bits)
                    value = _guard(value+_guard(term*coordinates[b][j],max_bits),max_bits)
            row.append(value)
        result.append(row)
    return result


def geometry(circuit, generators, *, backend='factored', **options):
    """Return Q_ab = <H_a H_b> - <H_a><H_b> and real tangent dependencies.

    Every scalar expectation uses the selected exact backend and its budgets.
    Expectations are reused only for identical complete Pauli words. The full
    ordered product phase survives. Postprocessing is capped at 8 directions
    and the same coefficient-bit budget. No partial tensor is returned.
    """
    if not isinstance(circuit,CompactCircuit):
        raise TypeError('geometry requires a CompactCircuit')
    generators = validate_generators(generators,circuit.n_qubits)
    if backend == 'factored':
        from .factored import expectation
    elif backend == 'observer':
        from .observer import expectation
    else:
        raise ValueError('geometry backend must be factored or observer')
    max_bits = _integer(options.get('max_coefficient_bits',4096),'coefficient bits',2,1_000_000)
    cache, observations = {():ONE}, []

    def read(word):
        key = tuple(sorted(word.items()))
        if key not in cache:
            observation = expectation(circuit,word,**options)
            value = observation.value
            if value.c or value.d:
                raise ArithmeticError('Hermitian generator acquired an imaginary expectation')
            cache[key] = _guard(value,max_bits)
            observations.append(observation.to_dict())
        return cache[key]

    try:
        means = [sign*read(word) for sign,word in generators]
        size = len(generators)
        tensor = [[ZERO]*size for _ in range(size)]
        for a,(sa,left) in enumerate(generators):
            for b in range(a,size):
                sb,right = generators[b]
                phase,word = word_product(left,right)
                product_mean = phase*sa*sb*read(word)
                value = _guard(product_mean-_guard(means[a]*means[b],max_bits),max_bits)
                tensor[a][b],tensor[b][a] = value,value.conjugate()
        metric = [[Exact(v.a,v.b) for v in row] for row in tensor]
        curvature = [[Exact(v.c,v.d) for v in row] for row in tensor]
        dependencies = _factor(metric,max_bits)
        # A real null tangent must vanish in BOTH halves, not only the metric.
        if _reconstruct(tensor,dependencies,max_bits) != tensor:
            raise ArithmeticError('metric dependency failed full information-curvature reconstruction')
        complex_rank = _factor(tensor,max_bits)['rank']
    except ResourceLimit as error:
        error.statistics = dict(getattr(error,'statistics',{}),
                                completed_geometry_scalar_evaluations=len(observations),
                                partial_tensor_discarded=True)
        raise
    return dict(tensor=tensor,metric=metric,curvature=curvature,means=means,
                dependencies=dependencies,complex_gram_rank=complex_rank,
                full_tensor_reconstruction_exact=True,
                scalar_evaluations=len(observations),scalar_statistics=observations,
                generators=generators)


def serialize(result, real_display):
    exact_matrix = lambda matrix: [[v.to_dict() for v in row] for row in matrix]
    factor = result['dependencies']
    return dict(
        contract='CID-D2 finite rank-one cut; B_a=-i H_a; X_a=[B_a,P]',
        tensor=exact_matrix(result['tensor']),
        metric=[[real_display(v) for v in row] for row in result['metric']],
        curvature=[[real_display(v) for v in row] for row in result['curvature']],
        means=[real_display(v) for v in result['means']],
        real_tangent_rank=factor['rank'],complex_gram_rank=result['complex_gram_rank'],
        dependencies=dict(basis_indices=factor['basis_indices'],
                          coordinates=exact_matrix(factor['coordinates']),
                          nullspace=exact_matrix(factor['nullspace']),
                          full_tensor_reconstruction_exact=True),
        scalar_evaluations=result['scalar_evaluations'],
        history_scope='Circuit retained in request; final-cut tensor does not reconstruct transport history')
