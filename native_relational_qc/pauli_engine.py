"""Exact bit-packed Clifford pullback and bounded Clifford+T observations.

Clifford joint probabilities use commuting generator elimination, not 2^k
projector enumeration. The T extension retains every Pauli coefficient and
ordered phase. Both algorithms are iterative and use the declared EMK gates.
"""
from dataclasses import dataclass
from fractions import Fraction
import sys

from .compact import CompactCircuit, ResourceLimit, _integer
from .exact import Exact, ONE, ZERO, INV_SQRT2
from .large_register import MAX_LARGE_QUBITS

CLIFFORD_GATES = frozenset(('id','x','y','z','h','s','sdg','sx','sxdg','r','k','rk','cx','cz','swap'))
T_GATES = frozenset(('t','tdg'))


def compile_plan(circuit, allow_t=False):
    if not isinstance(circuit,CompactCircuit):
        raise TypeError('exact Pauli execution requires a declared circuit')
    _integer(circuit.n_qubits,'qubits',1,MAX_LARGE_QUBITS)
    operations=circuit.operations
    if len(operations)>100_000:
        raise ValueError('large-register circuit exceeds 100000 gates')
    allowed=CLIFFORD_GATES | (T_GATES if allow_t else frozenset())
    result=[]
    for name,qs in reversed(operations):
        if name not in allowed:
            raise ValueError(('clifford_t' if allow_t else 'stabilizer')+' backend does not support gate '+name)
        result.append((name,1<<qs[0],1<<qs[1] if len(qs)==2 else 0))
    return result


def _conjugate(x,z,p,gate):
    """U† (i^p X^x Z^z) U for an admitted Clifford gate."""
    name,a,b=gate
    xa,za=bool(x&a),bool(z&a)
    if name=='h':
        if xa and za:p+=2
        if xa!=za:x^=a;z^=a
    elif name in ('s','sdg'):
        if xa:z^=a;p+=-1 if name=='s' else 1
    elif name in ('sx','sxdg'):
        if za:x^=a;p+=1 if name=='sx' else -1
    elif name in ('x','rk'):
        if za:p+=2
    elif name in ('z','k'):
        if xa:p+=2
    elif name in ('y','r'):
        if xa!=za:p+=2
    elif name=='cx':
        if xa:x^=b
        if z&b:z^=a
    elif name=='cz':
        xb=bool(x&b)
        if xa and xb:p+=2
        if xa:z^=b
        if xb:z^=a
    elif name=='swap':
        if xa!=bool(x&b):x^=a|b
        if za!=bool(z&b):z^=a|b
    elif name!='id':
        raise ValueError('not a Clifford gate')
    return x,z,p%4


def _multiply(a,b):
    x,z,p=a;u,v,q=b
    return x^u,z^v,(p+q+2*((z&u).bit_count()%2))%4


def _sign(x,z,p):
    phase=(p-(x&z).bit_count())%4
    if phase not in (0,2):
        raise ArithmeticError('Hermitian Pauli acquired an imaginary sign')
    return 1 if phase==0 else -1


@dataclass(frozen=True)
class Observation:
    value: Exact
    statistics: dict

    def to_dict(self):
        return dict(self.statistics,value=self.value.to_dict())


class _Budget:
    def __init__(self,circuit,mode,max_work,max_bits,max_terms,progress=None):
        self.max_work=_integer(max_work,'max_work',1,1_000_000_000)
        self.max_bits=_integer(max_bits,'coefficient bits',2,1_000_000)
        self.max_terms=_integer(max_terms,'max_terms',1,1_000_000)
        self.progress=progress
        self.stats=dict(backend=mode,input_qubits=circuit.n_qubits,input_gates=len(circuit.operations),
                        term_visits=0,row_products=0,peak_terms=0,peak_generators=0,
                        max_coefficient_bits=1,statevector_constructed=False,truncated_terms=0,
                        non_clifford_gates=sum(name in T_GATES for name,_ in circuit.operations),
                        non_clifford_term_splits=0,pauli_bit_width_limit=circuit.n_qubits,
                        representation='iterative exact bit-packed Pauli pullback',
                        work_definition='gate-term visits plus generator row products')

    def fail(self,message):
        error=ResourceLimit(message)
        error.statistics=dict(self.stats,event='resource_limit')
        if self.progress:self.progress(error.statistics)
        raise error

    def tick(self,rows=False):
        key='row_products' if rows else 'term_visits'
        self.stats[key]+=1
        if self.stats['term_visits']+self.stats['row_products']>self.max_work:
            self.fail('exact Pauli work budget exceeded; no approximation performed')

    def inspect(self,value):
        self.stats['max_coefficient_bits']=max(self.stats['max_coefficient_bits'],value.max_bits)
        if value.max_bits>self.max_bits:
            self.fail('exact Pauli coefficient bit budget exceeded')
        return value

    def finish(self,value):
        self.inspect(value)
        if value.c or value.d:
            raise ArithmeticError('Hermitian observation is not real')
        if self.progress:self.progress(dict(self.stats,event='completed'))
        return Observation(value,dict(self.stats,algebraically_exact=True))


def _word(paulis,n):
    if not isinstance(paulis,dict):
        paulis=dict(paulis)
    x=z=0
    for q,letter in paulis.items():
        _integer(q,'qubit',0,n-1)
        if letter not in ('I','X','Y','Z'):
            raise ValueError('Pauli readings must be I/X/Y/Z')
        if letter in ('X','Y'):x|=1<<q
        if letter in ('Z','Y'):z|=1<<q
    return x,z


def _pullback(row,plan,budget):
    x,z,p=row
    for gate in plan:
        budget.tick()
        x,z,p=_conjugate(x,z,p,gate)
    budget.stats['peak_terms']=max(budget.stats['peak_terms'],1)
    return x,z,p


def _expand(terms,plan,budget):
    def add(out,key,value):
        value=budget.inspect(out.get(key,ZERO)+value)
        if value:out[key]=value
        else:out.pop(key,None)
        budget.stats['peak_terms']=max(budget.stats['peak_terms'],len(out))
        if len(out)>budget.max_terms:
            budget.fail('exact Clifford+T term budget exceeded; no truncation performed')
    budget.stats['peak_terms']=len(terms)
    for gate in plan:
        name,mask,_=gate;out={}
        for (x,z),coefficient in terms.items():
            budget.tick()
            p=(x&z).bit_count()%4
            if name in T_GATES:
                if not x&mask:
                    add(out,(x,z),coefficient)
                else:
                    budget.stats['non_clifford_term_splits']+=1
                    value=budget.inspect(coefficient*INV_SQRT2)
                    add(out,(x,z),value)
                    nz=z^mask
                    np=(p+(-1 if name=='t' else 1))%4
                    add(out,(x,nz),value*_sign(x,nz,np))
            else:
                nx,nz,np=_conjugate(x,z,p,gate)
                add(out,(nx,nz),coefficient*_sign(nx,nz,np))
        terms=out
        if not terms:break
    budget.stats['final_terms']=len(terms)
    value=ZERO
    for (x,_),coefficient in terms.items():
        if not x:value=budget.inspect(value+coefficient)
    return value


def expectation(circuit,paulis,*,allow_t=False,max_work=10_000_000,
                max_coefficient_bits=4096,max_terms=100_000,max_generators=2056,progress=None):
    plan=compile_plan(circuit,allow_t)
    _integer(max_generators,'max_generators',1,MAX_LARGE_QUBITS)
    budget=_Budget(circuit,'clifford_t' if allow_t else 'stabilizer',max_work,
                   max_coefficient_bits,max_terms,progress)
    x,z=_word(paulis,circuit.n_qubits)
    budget.stats['query_support']=(x|z).bit_count()
    if allow_t:
        value=_expand({(x,z):ONE},plan,budget)
    else:
        x,z,p=_pullback((x,z,(x&z).bit_count()%4),plan,budget)
        value=ZERO if x else Exact(1 if p==0 else -1)
        if not x and p not in (0,2):raise ArithmeticError('invalid diagonal Pauli phase')
    return budget.finish(value)


def probability(circuit,assignments,*,allow_t=False,max_work=10_000_000,
                max_coefficient_bits=4096,max_terms=100_000,max_generators=2056,progress=None):
    plan=compile_plan(circuit,allow_t)
    max_generators=_integer(max_generators,'max_generators',1,MAX_LARGE_QUBITS)
    budget=_Budget(circuit,'clifford_t' if allow_t else 'stabilizer',max_work,
                   max_coefficient_bits,max_terms,progress)
    assignments=dict(assignments)
    for q,bit in assignments.items():
        _integer(q,'qubit',0,circuit.n_qubits-1);_integer(bit,'outcome',0,1)
    k=len(assignments);budget.stats['query_support']=k
    if allow_t:
        if (1<<k)>budget.max_terms:
            budget.fail('Clifford+T initial projector exceeds term budget; use bounded marginals')
        scale=budget.inspect(Exact(Fraction(1,1<<k)))
        terms={(0,0):scale}
        for q,bit in assignments.items():
            for (x,z),value in list(terms.items()):
                terms[x,z^(1<<q)]=-value if bit else value
        return budget.finish(_expand(terms,plan,budget))
    if k>max_generators:
        budget.fail('stabilizer observation exceeds generator-count budget')
    # Pull back commuting measurement generators with their requested signs.
    # Row elimination preserves their subgroup and every operator phase.
    pivots={}
    budget.stats['measurement_generators']=k
    for q,bit in assignments.items():
        row=_pullback((0,1<<q,2*bit),plan,budget)
        while row[0]:
            pivot=row[0].bit_length()-1
            if pivot not in pivots:
                pivots[pivot]=row
                budget.stats['peak_generators']=max(budget.stats['peak_generators'],len(pivots))
                break
            budget.tick(rows=True)
            row=_multiply(row,pivots[pivot])
        if not row[0]:
            if row[2] not in (0,2):raise ArithmeticError('commuting stabilizer product is non-Hermitian')
            if row[2]==2:
                budget.stats.update(x_rank=len(pivots),inconsistent_diagonal_constraint=True)
                return budget.finish(ZERO)
    budget.stats.update(x_rank=len(pivots),inconsistent_diagonal_constraint=False,
                        representation='commuting stabilizer-generator pullback and exact GF(2) elimination',
                        retained_generator_record_bytes=sum(sum(sys.getsizeof(x) for x in row) for row in pivots.values()))
    return budget.finish(Exact(Fraction(1,1<<len(pivots))))
