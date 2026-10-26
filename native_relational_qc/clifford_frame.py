"""Exact Clifford frame with a bounded sparse computational-basis residual.

State semantics are C sum_x c_x|x>, where C is the ordered Clifford skeleton.
Joint probabilities eliminate commuting measurement generators and evaluate
their sparse matrix elements, without expanding the 2^k-term projector.
"""
from fractions import Fraction

from .compact import ResourceLimit, _integer
from .exact import Exact, ONE, ZERO, IMAG, HALF, OMEGA
from . import large_register as _large_register
from .pauli_engine import Observation, T_GATES, compile_plan, _conjugate, _multiply, _word

PHASES=(ONE,IMAG,-ONE,-IMAG)


class _Budget:
    def __init__(self,circuit,max_work,max_coefficient_bits,max_branches,max_pairs,max_generators,progress):
        self.max_work=_integer(max_work,'max_work',1,1_000_000_000)
        self.max_bits=_integer(max_coefficient_bits,'coefficient bits',2,1_000_000)
        self.max_branches=_integer(max_branches,'max_branches',1,65_536)
        self.max_pairs=_integer(max_pairs,'max_pairs',1,10_000_000)
        self.max_generators=_integer(max_generators,'max_generators',1,_large_register.register_bound())
        self.progress=progress
        self.stats=dict(backend='clifford_frame',input_qubits=circuit.n_qubits,
            input_gates=len(circuit.operations),work_used=0,plan_gates=0,gate_visits=0,
            branch_updates=0,normalization_terms=0,row_products=0,constraint_checks=0,pair_visits=0,
            peak_branches=1,peak_generators=0,max_coefficient_bits=1,
            non_clifford_gates=sum(name in T_GATES for name,_ in circuit.operations),processed_t_gates=0,
            dense_statevector_constructed=False,sparse_residual_constructed=True,truncated_terms=0,
            representation='Clifford skeleton plus exact sparse basis residual',
            work_definition='plan gates, gate visits, branch updates, normalization terms, row products, constraint checks and pair visits')

    def fail(self,message):
        error=ResourceLimit(message)
        error.statistics=dict(self.stats,event='resource_limit')
        if self.progress:self.progress(error.statistics)
        raise error

    def tick(self,kind):
        self.stats[kind]+=1;self.stats['work_used']+=1
        if self.stats['work_used']>self.max_work:
            self.fail('exact Clifford-frame work budget exceeded; no approximation performed')

    def inspect(self,value):
        self.stats['max_coefficient_bits']=max(self.stats['max_coefficient_bits'],value.max_bits)
        if value.max_bits>self.max_bits:self.fail('exact Clifford-frame coefficient bit budget exceeded')
        return value

    def add(self,out,key,value):
        value=self.inspect(out.get(key,ZERO)+self.inspect(value))
        if value:out[key]=value
        else:out.pop(key,None)
        self.stats['peak_branches']=max(self.stats['peak_branches'],len(out))
        if len(out)>self.max_branches:
            self.fail('exact Clifford-frame branch budget exceeded; no truncation performed')

    def finish(self,value):
        self.inspect(value)
        if value.c or value.d:raise ArithmeticError('Hermitian frame observation is not real')
        if self.progress:self.progress(dict(self.stats,event='completed'))
        return Observation(value,dict(self.stats,algebraically_exact=True))


def _pullback(row,cliffords,budget):
    for gate in reversed(cliffords):
        budget.tick('gate_visits')
        row=_conjugate(*row,gate)
    return row


def _phase(row,ket):
    _,z,p=row
    return PHASES[(p+2*((z&ket).bit_count()%2))%4]


def _prepare(plan,budget):
    cliffords=[];amplitudes={0:ONE}
    for gate in reversed(plan):
        budget.tick('plan_gates')
        name,mask,_=gate
        if name not in T_GATES:
            cliffords.append(gate);continue
        budget.stats['processed_t_gates']+=1
        row=_pullback((0,mask,0),cliffords,budget)
        omega=OMEGA if name=='t' else OMEGA.conjugate()
        a=budget.inspect((ONE+omega)*HALF);b=budget.inspect((ONE-omega)*HALF)
        out={}
        for ket,coefficient in amplitudes.items():
            budget.tick('branch_updates')
            budget.add(out,ket,coefficient*a)
            budget.add(out,ket^row[0],coefficient*b*_phase(row,ket))
        amplitudes=out
    norm=ZERO
    for coefficient in amplitudes.values():
        budget.tick('normalization_terms')
        norm=budget.inspect(norm+budget.inspect(coefficient.norm2()))
    if norm!=ONE:raise ArithmeticError('Clifford-frame residual is not exactly normalized')
    budget.stats.update(final_branches=len(amplitudes),clifford_gates=len(cliffords),
                        normalization_exact=True)
    return cliffords,amplitudes


def _basis(generators,cliffords,budget):
    pivots={};diagonal=[]
    for q,bit in generators.items():
        row=_pullback((0,1<<q,2*bit),cliffords,budget)
        while row[0]:
            pivot=row[0].bit_length()-1
            if pivot not in pivots:
                pivots[pivot]=row;break
            budget.tick('row_products')
            row=_multiply(row,pivots[pivot])
        if not row[0]:
            if row[2] not in (0,2):raise ArithmeticError('diagonal projector generator is not Hermitian')
            diagonal.append(row)
        budget.stats['peak_generators']=max(budget.stats['peak_generators'],len(pivots)+len(diagonal))
    budget.stats.update(x_rank=len(pivots),diagonal_constraints=len(diagonal))
    return pivots,diagonal


def _transition(delta,pivots,budget):
    row=(0,0,0)
    while delta:
        pivot=delta.bit_length()-1
        if pivot not in pivots:return None
        generator=pivots[pivot]
        delta^=generator[0]
        budget.tick('row_products')
        row=_multiply(row,generator)
    return row


def expectation(circuit,paulis,*,max_work=10_000_000,max_coefficient_bits=4096,
                max_branches=4096,max_pairs=1_000_000,max_generators=2056,progress=None):
    plan=compile_plan(circuit,allow_t=True)
    budget=_Budget(circuit,max_work,max_coefficient_bits,max_branches,max_pairs,max_generators,progress)
    x,z=_word(paulis,circuit.n_qubits)
    budget.stats['query_support']=(x|z).bit_count()
    cliffords,amplitudes=_prepare(plan,budget)
    return _expectation(cliffords,amplitudes,x,z,budget)


def _expectation(cliffords,amplitudes,x,z,budget):
    """Shared exact readout after a backend has certified its frame state."""
    row=_pullback((x,z,(x&z).bit_count()%4),cliffords,budget)
    if len(amplitudes)>budget.max_pairs:
        budget.fail('exact Clifford-frame expectation exceeds pair budget')
    value=ZERO
    for ket,coefficient in amplitudes.items():
        budget.tick('pair_visits')
        bra=amplitudes.get(ket^row[0])
        if bra is not None:
            term=budget.inspect(bra.conjugate()*coefficient*_phase(row,ket))
            value=budget.inspect(value+term)
    return budget.finish(value)


def probability(circuit,assignments,*,max_work=10_000_000,max_coefficient_bits=4096,
                max_branches=4096,max_pairs=1_000_000,max_generators=2056,progress=None):
    plan=compile_plan(circuit,allow_t=True)
    budget=_Budget(circuit,max_work,max_coefficient_bits,max_branches,max_pairs,max_generators,progress)
    assignments=dict(assignments)
    for q,bit in assignments.items():
        _integer(q,'qubit',0,circuit.n_qubits-1);_integer(bit,'outcome',0,1)
    k=len(assignments)
    # Eligibility precedes the generator cap, even if a query would be trivial.
    budget.stats.update(query_support=k,measurement_generators=k,projector_expansion_avoided=True)
    if k>budget.max_generators:budget.fail('Clifford-frame observation exceeds generator-count budget')
    cliffords,amplitudes=_prepare(plan,budget)
    return _probability(cliffords,amplitudes,assignments,budget)


def _probability(cliffords,amplitudes,assignments,budget):
    """Shared commuting-projector readout; the caller validates the query."""
    if not assignments:
        budget.stats.update(x_rank=0,diagonal_constraints=0,accepted_branches=len(amplitudes),pair_candidates=0)
        return budget.finish(ONE)
    pivots,diagonal=_basis(assignments,cliffords,budget)
    accepted=[]
    for ket,coefficient in amplitudes.items():
        for row in diagonal:
            budget.tick('constraint_checks')
            if (row[2]+2*((row[1]&ket).bit_count()%2))%4:break
        else:accepted.append((ket,coefficient))
    count=len(accepted)
    candidates=count*(count+1)//2
    budget.stats.update(accepted_branches=count,pair_candidates=candidates)
    if candidates>budget.max_pairs:
        budget.fail('exact Clifford-frame probability exceeds pair budget before summation')
    if not accepted:return budget.finish(ZERO)
    scale=budget.inspect(Exact(Fraction(1,1<<len(pivots))))
    value=ZERO
    for i,(ket,coefficient) in enumerate(accepted):
        budget.tick('pair_visits')
        value=budget.inspect(value+budget.inspect(coefficient.norm2()))
        for j in range(i+1,count):
            budget.tick('pair_visits')
            bra,bcoef=accepted[j]
            row=_transition(ket^bra,pivots,budget)
            if row is not None:
                term=budget.inspect(bcoef.conjugate()*coefficient*_phase(row,ket))
                # Both ordered off-diagonal entries, with their complex phase.
                value=budget.inspect(value+budget.inspect(term+term.conjugate()))
    return budget.finish(value*scale)
