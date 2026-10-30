"""Bounded, proof-traced gate-word reduction for lowered modular arithmetic.

This is a small Panini-style typed rewrite adapter, not an import or blanket
certification of the general RKF compiler. X/CX/CCX are involutions. Two such
gates commute if neither target changes a control of the other. All other
gates are barriers. Every deletion carries its original source positions and
the exact surviving context crossed; an independent replay checks the proof.
"""
from dataclasses import dataclass

from .compact import CompactCircuit,ResourceLimit,_integer

SCHEMA='nrqc-modular-rewrite-v1'
ARITY={'x':1,'cx':2,'ccx':3}


def _empty_like(circuit):
    """Same circuit class and declared field order, with no operations."""
    order=getattr(circuit,'order',None)
    return type(circuit)(circuit.n_qubits) if order is None else type(circuit)(circuit.n_qubits,order)


def _validate(circuit):
    if not isinstance(circuit,CompactCircuit):raise TypeError('a declared circuit is required')
    cap=getattr(circuit,'max_gates',100_000)
    if len(circuit.operations)>cap:raise ResourceLimit(f'rewrite input exceeds {cap} gates')
    checked=_empty_like(circuit)
    for name,qs in circuit.operations:checked.add(name,*qs)


def _binding(circuit):
    from .calculator import _digest
    return _digest(dict(n_qubits=circuit.n_qubits,
                        operations=[[name,list(qs)] for name,qs in circuit.operations]))


def _commute(a,b):
    name,qs=a;other,rs=b
    return (name in ARITY and other in ARITY and
            qs[-1] not in rs[:-1] and rs[-1] not in qs[:-1])


@dataclass(frozen=True)
class RewriteResult:
    circuit: CompactCircuit
    certificate: dict
    statistics: dict


def rewrite_circuit(circuit,*,lookback=64,max_checks=1_000_000):
    """Remove a pair only after proving it commutes through the surviving gap.

    The bounded search is deterministic but does not claim confluence or a
    globally minimum word. A budget failure returns no circuit/certificate.
    """
    _validate(circuit)
    _integer(lookback,'lookback',1,512);_integer(max_checks,'max_checks',1,10_000_000)
    active=[];steps=[];checks=0;ops=circuit.operations
    for right,op in enumerate(ops):
        cancelled=False
        if op[0] in ARITY:
            for position in range(len(active)-1,max(-1,len(active)-lookback-1),-1):
                checks+=1
                if checks>max_checks:raise ResourceLimit('rewrite search budget exceeded; no result returned')
                left=active[position];previous=ops[left]
                if previous==op:
                    steps.append(dict(left=left,right=right,crossed=active[position+1:].copy()))
                    del active[position];cancelled=True;break
                if not _commute(previous,op):break
        if not cancelled:active.append(right)
    output=_empty_like(circuit)
    for index in active:
        name,qs=ops[index];output.add(name,*qs)
    certificate=dict(schema=SCHEMA,source_sha256=_binding(circuit),
                     result_sha256=_binding(output),steps=steps)
    return RewriteResult(output,certificate,dict(input_gates=len(ops),output_gates=len(active),
        removed_gates=2*len(steps),cancellations=len(steps),search_checks=checks,
        crossed_gates=sum(len(s['crossed']) for s in steps),lookback=lookback,
        scope='exact full-register equality including global phase; no clean-ancilla assumption'))


def verify_rewrite(source,result,certificate,*,max_crossings=1_000_000):
    """Check a supplied derivation without invoking the rewrite search."""
    from .calculator import _object
    _validate(source);_validate(result)
    _integer(max_crossings,'max_crossings',0,10_000_000)
    _object(certificate,('schema','source_sha256','result_sha256','steps'))
    if (certificate['schema']!=SCHEMA or source.n_qubits!=result.n_qubits or
        certificate['source_sha256']!=_binding(source) or
        certificate['result_sha256']!=_binding(result)):
        raise ValueError('rewrite certificate binding mismatch')
    steps=certificate['steps'];ops=source.operations
    if not isinstance(steps,list) or len(steps)>len(ops)//2:raise ValueError('invalid rewrite step count')
    by_right={};crossings=0;last=-1
    for step in steps:
        _object(step,('left','right','crossed'))
        left=_integer(step['left'],'left source index',0,len(ops)-1)
        right=_integer(step['right'],'right source index',0,len(ops)-1)
        if not left<right or right<=last:raise ValueError('rewrite steps must have increasing right indices')
        last=right;crossed=step['crossed']
        if not isinstance(crossed,list):raise ValueError('crossed source indices must be a list')
        crossings+=len(crossed)
        if crossings>max_crossings:raise ResourceLimit('rewrite proof crossing budget exceeded')
        for index in crossed:_integer(index,'crossed source index',left+1,right-1)
        by_right[right]=step
    active=[];positions={}
    for right,op in enumerate(ops):
        step=by_right.get(right)
        if step is None:
            positions[right]=len(active);active.append(right);continue
        left=step['left']
        if left not in positions:raise ValueError('rewrite deletes an unavailable source gate')
        position=positions[left]
        if op[0] not in ARITY or ops[left]!=op:raise ValueError('rewrite pair is not a declared involution')
        context=active[position+1:]
        if context!=step['crossed']:raise ValueError('rewrite context witness mismatch')
        # Independent dependency test: each control predicate must be invariant
        # under the other XOR. Shared targets/controls alone do not forbid it.
        for index in context:
            name,qs=ops[index]
            if name not in ARITY or op[1][-1] in qs[:-1] or qs[-1] in op[1][:-1]:
                raise ValueError('rewrite crossed a noncommuting gate or barrier')
        del positions[left];del active[position]
        for at in range(position,len(active)):positions[active[at]]=at
    if tuple(ops[i] for i in active)!=result.operations:raise ValueError('rewrite result does not match the replay')
    return dict(status='verified',cancellations=len(steps),crossed_gates=crossings,
                source_sha256=certificate['source_sha256'],result_sha256=certificate['result_sha256'])
