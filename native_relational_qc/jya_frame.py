"""Exact local-return recurrence feeding the bounded Clifford-frame evaluator.

SE44's retained two-channel recurrence motivates this adapter. A named
single-qubit word has U²=tr(U) U-det(U) I, so U^m stays in span{I,U}.
Binary composition evaluates that recurrence without expanding m matrices.
The determinant retains global phase; changing words keep chronological order
as required by SE45. This is standard two-by-two algebra, not a new universal
simulation theorem. See JYA_FRAME.md for source pins and scope.
"""
from . import clifford_frame as frame
from .compact import _integer
from .exact import ONE, ZERO, HALF, IMAG, exact_gate
from .pauli_engine import compile_plan, T_GATES, _word

IDENTITY=((ONE,ZERO),(ZERO,ONE))


class _Budget(frame._Budget):
    def __init__(self,*args):
        super().__init__(*args)
        self.stats.update(backend='jya_frame',local_blocks=0,repeated_blocks=0,
            folded_gates=0,largest_repeat=1,compile_gates=0,period_comparisons=0,
            local_products=0,recurrence_products=0,local_unitarity_checks=0,
            compiled_blocks=0,compressed_repetitions=0,
            representation='ordered exact local returns plus Clifford frame and sparse residual',
            work_definition=self.stats['work_definition']+
                '; input scan, period comparisons, exact local/recurrence scalar products and unitarity checks')


def _mul(a,b,budget,kind='local_products'):
    budget.tick(kind)
    return budget.inspect(a*b)


def _sum(values,budget):
    out=ZERO
    for value in values:out=budget.inspect(out+value)
    return out


def _matmul(a,b,budget):
    return tuple(tuple(_sum((_mul(a[i][k],b[k][j],budget) for k in range(2)),budget)
                       for j in range(2)) for i in range(2))


def _unitary(matrix,budget):
    adjoint=tuple(tuple(matrix[j][i].conjugate() for j in range(2)) for i in range(2))
    budget.tick('local_unitarity_checks')
    if _matmul(adjoint,matrix,budget)!=IDENTITY:
        raise ArithmeticError('local return is not exactly unitary')


def _period(names,budget):
    """Linear prefix-function scan; recognizes a repeated prefix and its tail."""
    prefix=[0]*len(names)
    for i in range(1,len(names)):
        j=prefix[i-1]
        while True:
            budget.tick('period_comparisons')
            if names[i]==names[j]:j+=1;break
            if not j:break
            j=prefix[j-1]
        prefix[i]=j
    return len(names)-prefix[-1]


def _power(matrix,exponent,budget):
    """Evaluate U^m=a I+b U in Q(sqrt(2),i)[U]/(U²-tU+dI).

    No division by sine, determinant root, inverse angle or eigenvalue gap.
    Identity, half-turn, repeated eigenvalue and nontrivial phase cases use
    the same rule. Intermediate coefficient growth remains budgeted.
    """
    trace=budget.inspect(matrix[0][0]+matrix[1][1])
    determinant=budget.inspect(_mul(matrix[0][0],matrix[1][1],budget)-
                              _mul(matrix[0][1],matrix[1][0],budget))
    def compose(left,right):
        a,b=left;c,d=right
        bd=_mul(b,d,budget,'recurrence_products')
        scalar=budget.inspect(_mul(a,c,budget,'recurrence_products')-
                             _mul(determinant,bd,budget,'recurrence_products'))
        linear=_sum((_mul(a,d,budget,'recurrence_products'),
                     _mul(b,c,budget,'recurrence_products'),
                     _mul(trace,bd,budget,'recurrence_products')),budget)
        return scalar,linear
    result=(ONE,ZERO);power=(ZERO,ONE)
    while exponent:
        if exponent&1:result=compose(result,power)
        exponent>>=1
        if exponent:power=compose(power,power)
    a,b=result
    return tuple(tuple(budget.inspect(_mul(b,matrix[i][j],budget)+(a if i==j else ZERO))
                       for j in range(2)) for i in range(2))


def _local_return(names,budget,*,fold=True):
    period=_period(names,budget) if fold else len(names)
    count=len(names)//period
    matrix=IDENTITY
    for name in names[:period]:matrix=_matmul(exact_gate(name),matrix,budget)
    if count>1:
        matrix=_power(matrix,count,budget)
        budget.stats['repeated_blocks']+=1
        budget.stats['largest_repeat']=max(budget.stats['largest_repeat'],count)
        budget.stats['compressed_repetitions']+=count-1
    for name in names[count*period:]:matrix=_matmul(exact_gate(name),matrix,budget)
    _unitary(matrix,budget)
    budget.stats['local_blocks']+=1
    budget.stats['folded_gates']+=len(names)
    return matrix


def _events(plan,budget,*,fold=True):
    """Only adjacent single-site gates on the same wire form a local block.

    An entangler or another wire ends the block; no operation is reordered.
    Pure Clifford words retain the original efficient skeleton.
    """
    forward=list(reversed(plan));i=0
    while i<len(forward):
        name,mask,other=forward[i]
        if other:
            budget.tick('compile_gates');yield ('clifford',forward[i]);i+=1;continue
        j=i+1
        while j<len(forward) and forward[j][1]==mask and not forward[j][2]:j+=1
        names=[]
        for gate in forward[i:j]:
            budget.tick('compile_gates');names.append(gate[0])
        if len(names)>1 and any(n in T_GATES for n in names):
            matrix=_local_return(names,budget,fold=fold)
            budget.stats['compiled_blocks']+=1
            # Full Pauli expansion of this exact 2x2 return, including phase.
            a,b=matrix[0];c,d=matrix[1]
            coefficients=(budget.inspect((a+d)*HALF),budget.inspect((b+c)*HALF),
                          budget.inspect((c-b)*HALF*(-IMAG)),budget.inspect((a-d)*HALF))
            rows=((0,0,0),(mask,0,0),(mask,mask,1),(0,mask,0))
            yield ('local',tuple((row,value) for row,value in zip(rows,coefficients) if value))
        else:
            for gate in forward[i:j]:
                if gate[0] in T_GATES:
                    m=exact_gate(gate[0]);omega=m[1][1]
                    yield ('local',(((0,0,0),budget.inspect((ONE+omega)*HALF)),
                                     ((0,mask,0),budget.inspect((ONE-omega)*HALF))))
                else:yield ('clifford',gate)
        i=j


def _prepare(plan,budget,*,fold=True):
    cliffords=[];amplitudes={0:ONE}
    for kind,event in _events(plan,budget,fold=fold):
        budget.tick('plan_gates')
        if kind=='clifford':cliffords.append(event);continue
        pulled=[(frame._pullback(row,cliffords,budget) if row[:2]!=(0,0) else row,value)
                for row,value in event]
        out={}
        for ket,coefficient in amplitudes.items():
            for row,value in pulled:
                budget.tick('branch_updates')
                budget.add(out,ket^row[0],coefficient*value*frame._phase(row,ket))
        amplitudes=out
    norm=ZERO
    for coefficient in amplitudes.values():
        budget.tick('normalization_terms')
        norm=budget.inspect(norm+budget.inspect(coefficient.norm2()))
    if norm!=ONE:raise ArithmeticError('jya-frame residual is not exactly normalized')
    budget.stats.update(final_branches=len(amplitudes),clifford_gates=len(cliffords),
                        normalization_exact=True,processed_t_gates=budget.stats['non_clifford_gates'])
    return cliffords,amplitudes


def expectation(circuit,paulis,*,max_work=10_000_000,max_coefficient_bits=4096,
                max_branches=4096,max_pairs=1_000_000,max_generators=2056,progress=None):
    plan=compile_plan(circuit,allow_t=True)
    budget=_Budget(circuit,max_work,max_coefficient_bits,max_branches,max_pairs,max_generators,progress)
    x,z=_word(paulis,circuit.n_qubits)
    budget.stats['query_support']=(x|z).bit_count()
    cliffords,amplitudes=_prepare(plan,budget)
    return frame._expectation(cliffords,amplitudes,x,z,budget)


def probability(circuit,assignments,*,max_work=10_000_000,max_coefficient_bits=4096,
                max_branches=4096,max_pairs=1_000_000,max_generators=2056,progress=None):
    plan=compile_plan(circuit,allow_t=True)
    budget=_Budget(circuit,max_work,max_coefficient_bits,max_branches,max_pairs,max_generators,progress)
    assignments=dict(assignments)
    for q,bit in assignments.items():
        _integer(q,'qubit',0,circuit.n_qubits-1);_integer(bit,'outcome',0,1)
    k=len(assignments)
    budget.stats.update(query_support=k,measurement_generators=k,projector_expansion_avoided=True)
    if k>budget.max_generators:budget.fail('jya-frame observation exceeds generator-count budget')
    cliffords,amplitudes=_prepare(plan,budget)
    return frame._probability(cliffords,amplitudes,assignments,budget)
