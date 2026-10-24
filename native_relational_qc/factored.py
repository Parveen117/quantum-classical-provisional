"""Exact product-observer return plus sparse MPS boundary contraction.

Backward propagation consumes the product-preserving suffix without expanding
its global Pauli sum. The remaining circuit is contracted with division-free
matrix-product state factors and the returned local observers. This is a hybrid
tensor-network evaluator, not a purely Heisenberg MPO solver or a new complexity
claim. The default boundary contraction uses exact packed integer matrix products;
the original sparse scalar contraction remains selectable. Optional streaming
constructs one site at a time and uses bounded integer limbs whose binary64 dot
products are provably exact. No SVD, numerical rank decision, truncation, or dense
statevector is used.
"""
from dataclasses import dataclass
from functools import lru_cache
from math import prod

from .compact import CompactCircuit, ResourceLimit, _integer
from .dyadic import Dyadic, DZERO, DONE, DIMAG
from .exact import ZERO, ONE, HALF, exact_gate
from .observer import _conjugate


@dataclass(frozen=True)
class FactoredObservation:
    value: object
    statistics: dict

    def to_dict(self):
        return {'value': self.value.to_dict(), **self.statistics,
                'algebraically_exact': True, 'truncated_terms': 0,
                'statevector_constructed': False,
                'representation': ('product-observer suffix + streamed exact MPS boundary contraction'
                                   if self.statistics.get('contraction') == 'streaming' else
                                   'product-observer suffix + exact MPS boundary contraction')}


def _add_into(target, key, value):
    if value:
        updated = target.get(key, DZERO) + value
        if updated:
            target[key] = updated
        else:
            target.pop(key, None)


@lru_cache(maxsize=32)
def _gate(name):
    return tuple(tuple(Dyadic.from_exact(x) for x in row) for row in exact_gate(name))


def _local_matrix(factor):
    # P(x,z)=i^(xz) X^x Z^z, with physical rows/columns in |0>,|1> order.
    out = [[DZERO,DZERO],[DZERO,DZERO]]
    for (x,z), coefficient in factor.items():
        v = Dyadic.from_exact(coefficient)
        for bit in (0,1):
            phase = DIMAG if x and z else DONE
            if z and bit:
                phase = -phase
            out[bit ^ x][bit] = out[bit ^ x][bit] + v*phase
    return tuple(map(tuple,out))


class _Budget:
    def __init__(self, max_bond, max_coefficients, max_work, max_coefficient_bits, progress):
        self.max_bond = _integer(max_bond, 'max_bond', 1, 65536)
        self.max_coefficients = _integer(max_coefficients, 'max_coefficients', 1, 10000000)
        self.max_work = _integer(max_work, 'max_work', 1, 1000000000)
        self.max_bits = _integer(max_coefficient_bits, 'coefficient bits', 2, 1000000)
        self.progress = progress
        self.stats = dict(peak_bond=1, peak_stored_coefficients=0, peak_temporary_coefficients=0,
                          scalar_products=0, max_coefficient_bits=1,
                          product_suffix_gates=0, prefix_local_coefficients=0,
                          prefix_expanded_terms=1, forward_gates=0, contracted_sites=0)

    def emit(self, event):
        if self.progress is not None:
            self.progress({'event':event, **self.stats})

    def fail(self, message):
        error = ResourceLimit(message)
        error.statistics = {'event':'resource_limit', **self.stats}
        self.emit('resource_limit')
        raise error

    def tick(self, amount=1):
        self.stats['scalar_products'] += amount
        if self.stats['scalar_products'] > self.max_work:
            self.fail('exact factored scalar-product budget exceeded; no truncation performed')

    def inspect(self, values, temporary=False):
        size = len(values)
        bits = max((v.max_bits for v in values),default=1)
        self.inspect_summary(size,bits,temporary)

    def inspect_summary(self, size, bits, temporary=False):
        field = 'peak_temporary_coefficients' if temporary else 'peak_stored_coefficients'
        self.stats[field] = max(self.stats[field],size)
        if size > self.max_coefficients:
            self.fail('exact factored coefficient-count budget exceeded')
        self.stats['max_coefficient_bits'] = max(self.stats['max_coefficient_bits'],bits)
        if bits > self.max_bits:
            self.fail('exact factored coefficient-bit budget exceeded')

    def bond(self, size):
        self.stats['peak_bond'] = max(self.stats['peak_bond'],size)
        if size > self.max_bond:
            self.fail('exact factored bond budget exceeded; no truncation performed')


def _cone(circuit, factors):
    active = {q for q,f in enumerate(factors) if f != {(0,0):ONE}}
    kept = []
    for name,qs in reversed(circuit.operations):
        if active.intersection(qs):
            active.update(qs)
            kept.append((name,qs))
    sites = sorted(active)
    position = {q:i for i,q in enumerate(sites)}
    return [(name,tuple(position[q] for q in qs)) for name,qs in reversed(kept)], [factors[q] for q in sites], sites


def _suffix(operations, factors, budget):
    """Consume only gates proved to preserve this product representation."""
    factors = [dict(f) for f in factors]
    remaining = len(operations)
    for name,qs in reversed(operations):
        budget.emit('suffix_gate_start')
        if len(qs)==1:
            q=qs[0]; out={}
            for (x,z),v in factors[q].items():
                for nx,nz,k in _conjugate(name,1,x,z):
                    budget.tick()
                    key=(nx,nz);out[key]=out.get(key,ZERO)+v*k
            factors[q]={key:v for key,v in out.items() if v}
        elif len(qs)==2 and all(len(factors[q])==1 for q in qs):
            (x0,z0),v0=next(iter(factors[qs[0]].items()))
            (x1,z1),v1=next(iter(factors[qs[1]].items()))
            image=_conjugate(name,2,x0|(x1<<1),z0|(z1<<1))
            if len(image)!=1:
                break
            x,z,v=image[0]
            budget.tick(2)
            factors[qs[0]]={(x&1,z&1):v0*v1*v}
            factors[qs[1]]={((x>>1)&1,(z>>1)&1):ONE}
        elif name=='cz' and all(all(x==0 for x,z in factors[q]) for q in qs):
            # Diagonal local observers commute with CZ exactly.
            pass
        else:
            break
        remaining -= 1
        budget.stats['product_suffix_gates'] += 1
        budget.stats['prefix_local_coefficients'] = sum(map(len,factors))
        budget.stats['prefix_expanded_terms'] = prod(map(len,factors))
        budget.inspect([Dyadic.from_exact(v) for f in factors for v in f.values()])
    return operations[:remaining], factors


def _contract_integer_site(boundary, matrices, nonempty, factor, budget, *, reuse=False):
    from .integer_matrix import IntegerMatrix
    local = _local_matrix(factor)
    updated = None
    for a in (0,1):
        ket = None
        for b in (0,1):
            if local[a][b] and nonempty[b]:
                term = matrices[b].scale(local[a][b])
                ket = term if ket is None else ket.add(term)
        if ket is not None and nonempty[a]:
            ket.inspect(budget)
            term = matrices[a].adjoint().matmul(
                boundary.matmul(ket,budget,reuse=reuse),budget,reuse=reuse)
            updated = term if updated is None else updated.add(term)
    if updated is None:
        return None
    entries = updated.inspect(budget)
    return IntegerMatrix.from_sparse(entries,updated.shape)


class _StateFactors:
    def __init__(self, n, budget):
        self.sites = [[{(0,0):DONE},{}] for _ in range(n)]
        self.bonds = [1]*(n+1)
        self.budget = budget
        self._site_sizes = [0]*n
        self._site_bits = [1]*n
        self._inspect()

    def _inspect(self, changed=None):
        # A local gate only changes its own sites. Reuse exact counts/bit
        # maxima for the untouched sites instead of rescanning the whole MPS.
        for q in range(len(self.sites)) if changed is None else changed:
            values = [v for matrix in self.sites[q] for v in matrix.values()]
            self._site_sizes[q] = len(values)
            self._site_bits[q] = max((v.max_bits for v in values),default=1)
        self.budget.inspect_summary(sum(self._site_sizes),max(self._site_bits,default=1))

    def single(self, name, q):
        u=_gate(name); old=self.sites[q]; new=[{},{}]
        for a in (0,1):
            for b in (0,1):
                if u[a][b]:
                    for key,value in old[b].items():
                        self.budget.tick()
                        _add_into(new[a],key,u[a][b]*value)
        self.sites[q]=new
        self._inspect((q,))

    def controlled(self, name, control, target):
        if abs(control-target)!=1:
            raise ValueError('factored backend requires adjacent two-qubit gates; route explicitly')
        lo,hi=sorted((control,target))
        old_bond=self.bonds[hi]
        self.budget.bond(2*old_bond)  # Check before allocation.
        a,b=self.sites[lo],self.sites[hi]
        new_a=[{},{}];new_b=[{},{}]
        u=_gate(name)
        if control==lo:
            # P0 tensor I + P1 tensor U; shared label is (old label,control).
            for bit in (0,1):
                for (l,r),v in a[bit].items():
                    new_a[bit][l,2*r+bit]=v
                for (l,r),v in b[bit].items():
                    new_b[bit][2*l,r]=v
                    for out in (0,1):
                        if u[out][bit]:
                            self.budget.tick()
                            _add_into(new_b[out],(2*l+1,r),u[out][bit]*v)
        else:
            for bit in (0,1):
                for (l,r),v in b[bit].items():
                    new_b[bit][2*l+bit,r]=v
                for (l,r),v in a[bit].items():
                    new_a[bit][l,2*r]=v
                    for out in (0,1):
                        if u[out][bit]:
                            self.budget.tick()
                            _add_into(new_a[out],(l,2*r+1),u[out][bit]*v)
        self.sites[lo],self.sites[hi]=new_a,new_b
        self.bonds[hi]*=2
        self._inspect((lo,hi))

    def run(self, operations):
        for name,qs in operations:
            self.budget.emit('forward_gate_start')
            if len(qs)==1:
                self.single(name,qs[0])
            elif name in ('cx','cz','ch','cs','ct'):
                self.controlled(name[1:],*qs)
            elif name=='swap':
                a,b=qs
                self.controlled('x',a,b); self.controlled('x',b,a); self.controlled('x',a,b)
            else:
                raise ValueError(f'gate {name} not supported by factored contraction')
            self.budget.stats['forward_gates']+=1

    def read_sparse(self, factors):
        boundary={(0,0):DONE}
        for site,factor in zip(self.sites,factors):
            self.budget.emit('boundary_start')
            local=_local_matrix(factor)
            rows=[]
            for matrix in site:
                index={}
                for (l,r),v in matrix.items():
                    index.setdefault(l,[]).append((r,v))
                rows.append(index)
            updated={}
            # A_a^dagger E A_b, two sparse matrix products instead of a
            # four-index Cartesian expansion. Keep every nonzero entry.
            for b in (0,1):
                if not any(local[a][b] for a in (0,1)):
                    continue
                temporary={}
                for (l,m),v in boundary.items():
                    for s,w in rows[b].get(m,()):
                        self.budget.tick()
                        _add_into(temporary,(l,s),v*w)
                self.budget.inspect(list(temporary.values()),temporary=True)
                for a in (0,1):
                    if not local[a][b]:
                        continue
                    for (l,s),v in temporary.items():
                        v=v*local[a][b]
                        for r,w in rows[a].get(l,()):
                            self.budget.tick()
                            _add_into(updated,(r,s),w.conjugate()*v)
            self.budget.inspect(list(updated.values()),temporary=True)
            boundary=updated
            self.budget.stats['contracted_sites']+=1
        value=boundary.get((0,0),DZERO).to_exact()
        if value.c or value.d:
            raise ArithmeticError('Hermitian readout acquired an imaginary value')
        return value

    def read_integer(self, factors, *, reuse=False):
        """Same boundary identity, with bounded exact integer dot products."""
        from .integer_matrix import IntegerMatrix
        boundary = IntegerMatrix.from_sparse({(0,0):DONE}, (1,1))
        for q, (site, factor) in enumerate(zip(self.sites, factors)):
            self.budget.emit('boundary_start')
            shape = (self.bonds[q], self.bonds[q+1])
            if shape[0]*shape[1] > self.budget.max_coefficients:
                self.budget.fail('exact integer site allocation exceeds coefficient-count budget')
            matrices = [IntegerMatrix.from_sparse(matrix, shape) for matrix in site]
            boundary = _contract_integer_site(boundary,matrices,[bool(s) for s in site],
                                              factor,self.budget,reuse=reuse)
            if boundary is None:
                return ZERO
            self.budget.stats['contracted_sites'] += 1
        value = boundary.entries().get((0,0),DZERO).to_exact()
        if value.c or value.d:
            raise ArithmeticError('Hermitian readout acquired an imaginary value')
        return value


def _evaluate(circuit,factors,*,max_bond=256,max_coefficients=1000000,max_work=10000000,
              max_coefficient_bits=4096,progress=None,causal_pruning=True,product_suffix=True,
              contraction='integer'):
    if not isinstance(circuit,CompactCircuit):
        raise TypeError('factored execution requires CompactCircuit')
    _integer(circuit.n_qubits,'factored qubits',1,256)
    if contraction not in ('integer','sparse','reuse','streaming'):
        raise ValueError('contraction must be integer, sparse, reuse or streaming')
    # Reject unsupported gates even when an observer would make them invisible.
    for name,qs in circuit.operations:
        if len(qs)>2 or (len(qs)==2 and (name not in ('cx','cz','ch','cs','ct','swap') or abs(qs[0]-qs[1])!=1)):
            raise ValueError('factored backend supports named single-site and adjacent cx/cz/ch/cs/ct/swap gates')
    budget=_Budget(max_bond,max_coefficients,max_work,max_coefficient_bits,progress)
    if causal_pruning:
        operations,factors,sites=_cone(circuit,factors)
    else:
        operations=list(circuit.operations);sites=list(range(circuit.n_qubits))
    budget.stats.update(input_qubits=circuit.n_qubits,active_qubits=len(sites),
                        input_gates=len(circuit.operations),causal_gates=len(operations),
                        causal_pruning=bool(causal_pruning),product_suffix=bool(product_suffix),
                        contraction=contraction,
                        prefix_local_coefficients=sum(map(len,factors)),prefix_expanded_terms=prod(map(len,factors)))
    if product_suffix:
        operations,factors=_suffix(operations,factors,budget)
    if contraction == 'streaming':
        from .streaming import read
        value = read(operations,factors,budget)
    else:
        state=_StateFactors(len(sites),budget)
        state.run(operations)
        value=(state.read_sparse(factors) if contraction=='sparse' else
               state.read_integer(factors,reuse=contraction=='reuse'))
    budget.emit('completed')
    return FactoredObservation(value,dict(budget.stats))


def expectation(circuit,paulis,**options):
    factors=[{(0,0):ONE} for _ in range(circuit.n_qubits)]
    for q,p in dict(paulis).items():
        _integer(q,'qubit',0,circuit.n_qubits-1)
        if p not in ('I','X','Y','Z'):
            raise ValueError('observer labels must be I/X/Y/Z')
        factors[q]={(int(p in ('X','Y')),int(p in ('Z','Y'))):ONE}
    return _evaluate(circuit,factors,**options)


def probability(circuit,assignments,**options):
    factors=[{(0,0):ONE} for _ in range(circuit.n_qubits)]
    for q,bit in dict(assignments).items():
        _integer(q,'qubit',0,circuit.n_qubits-1)
        _integer(bit,'outcome',0,1)
        factors[q]={(0,0):HALF,(0,1):-HALF if bit else HALF}
    return _evaluate(circuit,factors,**options)
