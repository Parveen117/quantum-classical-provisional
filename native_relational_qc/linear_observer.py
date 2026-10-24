"""Bounded exact MR-04 row-space closure, with a checkable minimality witness.

Minimality is among homogeneous linear observers on the full operator carrier,
for one Pauli seed and the exact declared wire-labelled action alphabet.
It is not minimum RAM, affine state-specific compression, or a speedup theorem.
"""
import re

from .calculator import _digest,_site_map,_object
from .compact import _integer
from .cyclotomic32 import Cyclotomic32 as C,BASIS,ZERO,ONE
from .observer32 import Budget,Engine,word
from .phase_backend import Phase32Circuit

SCHEMA='nrqc-linear-future-bank-v1'
SCOPE='minimum homogeneous K-linear observer dimension on the full operator carrier; K=Q(zeta_32); declared seed and alphabet only'


class LinearBudget(Budget):
    def __init__(self,max_rank=128,max_coefficients=65536,**limits):
        super().__init__(**limits)
        self.max_rank=_integer(max_rank,'max_rank',1,1024)
        self.max_coefficients=_integer(max_coefficients,'max_coefficients',1,1_000_000)
        self.stats.update(row_reductions=0,basis_scans=0,field_inversions=0,parsed_terms=0,
            reading_steps=0,stored_coefficients=0,basis_nonzeros=0,transition_nonzeros=0,
            provenance_nonzeros=0,rank=0)
    def inverse(self,v):
        self.tick('field_inversions')
        return self.inspect(v.inverse())
    def reserve(self,kind,count):
        if self.stats['stored_coefficients']+count>self.max_coefficients:
            self.fail('linear observer stored coefficient limit')
        self.stats['stored_coefficients']+=count;self.stats[kind]+=count


def _setup(circuit,paulis,limits):
    if not isinstance(circuit,Phase32Circuit):raise TypeError('linear bank requires Phase32Circuit')
    if not isinstance(paulis,dict):raise ValueError('Pauli seed must be a site map')
    canonical={str(q):v for q,v in paulis.items()}
    if len(canonical)!=len(paulis):raise ValueError('duplicate Pauli seed site')
    seed=word(_site_map(canonical,circuit.n_qubits,paulis=True))
    if len(circuit.operations)>100_000:raise ValueError('at most 100000 operations')
    engine=Engine(circuit);engine.b=LinearBudget(**limits)
    actions=tuple(dict.fromkeys(circuit.operations))
    return engine,actions,seed


def _mask(key):return dict(x=str(key[0]),z=str(key[1]))
def _terms(row):return [dict(_mask(k),coefficient=v.to_dict()) for k,v in sorted(row.items())]
def _weights(row):return [dict(column=k,coefficient=v.to_dict()) for k,v in sorted(row.items())]


def _reduce(row,basis,pivots,b):
    """Insertion-order echelon reduction: later rows vanish on earlier pivots."""
    b.tick('row_reductions');residual=dict(row);weights={}
    for i,(vector,pivot) in enumerate(zip(basis,pivots)):
        b.tick('basis_scans');factor=residual.get(pivot,ZERO)
        if not factor:continue
        b.put(weights,i,factor)
        for key,v in vector.items():b.put(residual,key,-b.mul(factor,v))
    return residual,weights


def linear_future_bank(circuit,paulis,**limits):
    """Generate the exact minimum linear future space without coordinate closure.

    On any resource failure, raises ResourceLimit and returns no certificate.
    The old coordinate bank is not a prerequisite and is never allocated here.
    """
    e,actions,seed=_setup(circuit,paulis,limits);b=e.b
    basis=[];pivots=[];origins=[]
    def insert(candidate,parent=None,action=None):
        residual,weights=_reduce(candidate,basis,pivots,b)
        if not residual:return
        if len(basis)>=b.max_rank:b.fail('linear observer rank limit')
        pivot=min(residual);divisor=residual[pivot]
        inverse=ONE if divisor==ONE else b.inverse(divisor)
        vector={}
        for key,v in residual.items():b.put(vector,key,v if inverse==ONE else b.mul(v,inverse))
        # All permanent coefficient slots, including provenance, count.
        b.reserve('basis_nonzeros',len(vector));b.reserve('provenance_nonzeros',len(weights)+1)
        basis.append(vector);pivots.append(pivot)
        origins.append(dict(parent=parent,action=action,subtracted=_weights(weights),divisor=divisor.to_dict()))
        b.stats['rank']=len(basis)
    insert({seed:ONE})
    cursor=0
    while cursor<len(basis):
        for action,gate in enumerate(actions):insert(e.step(basis[cursor],gate),cursor,action)
        cursor+=1
    transitions=[]
    for gate in actions:
        rows=[]
        for vector in basis:
            residual,weights=_reduce(e.step(vector,gate),basis,pivots,b)
            if residual:raise ArithmeticError('closure construction lost a direction')
            b.reserve('transition_nonzeros',len(weights));rows.append(_weights(weights))
        transitions.append(rows)
    serial_actions=[[name,list(qs)] for name,qs in actions]
    return dict(schema=SCHEMA,n_qubits=circuit.n_qubits,actions=serial_actions,
        action_sha256=_digest(serial_actions),seed=_mask(seed),basis=[_terms(v) for v in basis],
        pivots=[_mask(p) for p in pivots],origins=origins,transition_rows=transitions,
        retained_dimension=len(basis),minimality_scope=SCOPE,statistics=dict(b.stats))


def _read_mask(value,n):
    _object(value,('x','z'))
    out=[]
    for name in ('x','z'):
        s=value[name]
        if not isinstance(s,str) or len(s)>80 or not s.isascii() or not s.isdecimal() or str(int(s))!=s:
            raise ValueError('noncanonical Pauli mask')
        x=int(s)
        if x>=1<<n:raise ValueError('Pauli mask outside register')
        out.append(x)
    return tuple(out)


def _read_coefficient(obj,b):
    _object(obj,('basis','coefficients'))
    items=obj['coefficients']
    if obj['basis']!=BASIS or not isinstance(items,list) or len(items)!=16:
        raise ValueError('certificate needs sixteen rational coefficients')
    for s in items:
        if not isinstance(s,str) or len(s)>2*b.max_bits+3 or re.fullmatch(r'-?[0-9]+(?:/[1-9][0-9]*)?',s) is None:
            raise ValueError('invalid or oversized rational certificate coefficient')
    v=b.inspect(C.from_dict(obj))
    if not v or v!=v.conjugate() or v.to_dict()!=obj:raise ValueError('nonzero canonical real coefficient required')
    b.tick('parsed_terms');return v


def _read_weights(items,rank,b):
    if not isinstance(items,list) or len(items)>b.max_terms:b.fail('linear certificate row term limit')
    out={}
    for item in items:
        _object(item,('column','coefficient'));i=_integer(item['column'],'column',0,rank-1)
        if i in out:raise ValueError('duplicate transition column')
        b.put(out,i,_read_coefficient(item['coefficient'],b))
    return out


def _combination(weights,basis,b):
    result={}
    for i,coefficient in weights.items():
        for key,v in basis[i].items():b.put(result,key,b.mul(coefficient,v))
    return result


def _verify(circuit,paulis,certificate,limits):
    """Check identities directly; no Gaussian eliminator is used here."""
    e,actions,seed=_setup(circuit,paulis,limits);b=e.b;c=certificate
    _object(c,('schema','n_qubits','actions','action_sha256','seed','basis','pivots',
        'origins','transition_rows','retained_dimension','minimality_scope','statistics'))
    serial_actions=[[name,list(qs)] for name,qs in actions]
    if (c['schema']!=SCHEMA or type(c['n_qubits']) is not int or c['n_qubits']!=circuit.n_qubits or
        c['actions']!=serial_actions or _digest(c['actions'])!=_digest(serial_actions) or c['action_sha256']!=_digest(serial_actions) or
        c['seed']!=_mask(seed) or c['minimality_scope']!=SCOPE):raise ValueError('certificate binding mismatch')
    rank=_integer(c['retained_dimension'],'retained_dimension',1,1024)
    if rank>b.max_rank:b.fail('linear certificate rank limit')
    if any(not isinstance(c[k],list) or len(c[k])!=rank for k in ('basis','pivots','origins')):
        raise ValueError('certificate rank/row mismatch')
    if not isinstance(c['transition_rows'],list) or len(c['transition_rows'])!=len(actions):
        raise ValueError('certificate action/transition mismatch')
    basis=[];pivots=[]
    for i,(items,pivot_obj,origin) in enumerate(zip(c['basis'],c['pivots'],c['origins'])):
        if not isinstance(items,list) or not items or len(items)>b.max_terms:b.fail('linear certificate basis term limit')
        vector={}
        for item in items:
            _object(item,('x','z','coefficient'));key=_read_mask(dict(x=item['x'],z=item['z']),circuit.n_qubits)
            if key in vector:raise ValueError('duplicate basis Pauli')
            b.put(vector,key,_read_coefficient(item['coefficient'],b))
        b.reserve('basis_nonzeros',len(vector))
        pivot=_read_mask(pivot_obj,circuit.n_qubits)
        if vector.get(pivot)!=ONE or pivot!=min(vector) or any(p in vector for p in pivots):
            raise ValueError('basis independence witness failed')
        _object(origin,('parent','action','subtracted','divisor'))
        divisor=_read_coefficient(origin['divisor'],b)
        if i==0:
            if origin['parent'] is not None or origin['action'] is not None or origin['subtracted']:
                raise ValueError('invalid seed provenance')
            weights={};generated={seed:ONE}
        else:
            parent=_integer(origin['parent'],'parent',0,i-1)
            action=_integer(origin['action'],'action',0,len(actions)-1)
            weights=_read_weights(origin['subtracted'],i,b)
            generated=e.step(basis[parent],actions[action])
        b.reserve('provenance_nonzeros',len(weights)+1)
        reconstructed=_combination(weights,basis,b)
        for key,v in vector.items():b.put(reconstructed,key,b.mul(divisor,v))
        if reconstructed!=generated:raise ValueError('basis reachability witness failed')
        basis.append(vector);pivots.append(pivot);b.stats['rank']=len(basis)
    transfers=[]
    for gate,rows in zip(actions,c['transition_rows']):
        if not isinstance(rows,list) or len(rows)!=rank:raise ValueError('transition matrix size mismatch')
        parsed=[]
        for vector,items in zip(basis,rows):
            weights=_read_weights(items,rank,b);b.reserve('transition_nonzeros',len(weights))
            if _combination(weights,basis,b)!=e.step(vector,gate):raise ValueError('future closure witness failed')
            parsed.append(weights)
        transfers.append(parsed)
    # The first basis row equals the seed divided by the recorded scalar.
    seed_scale=_read_coefficient(c['origins'][0]['divisor'],b)
    return e,basis,transfers,seed_scale


def verify_linear_bank(circuit,paulis,certificate,**limits):
    """Validate binding, independence, reachability and closure exactly."""
    e,basis,_,_=_verify(circuit,paulis,certificate,limits)
    return dict(status='verified',retained_dimension=len(basis),minimality_scope=SCOPE,statistics=dict(e.b.stats))


def run_linear_bank(circuit,paulis,certificate,*,action_sequence=None,input_basis=0,**limits):
    """Verify, then evolve retained readings from a computational basis state.

    action_sequence is an optional list of alphabet indices in chronological
    order. Omission executes circuit.operations. Returns no partial result on
    failure. Verification and evolution share one work budget.
    """
    e,basis,transfers,seed_scale=_verify(circuit,paulis,certificate,limits);b=e.b
    input_basis=_integer(input_basis,'input_basis',0,(1<<circuit.n_qubits)-1)
    actions=tuple(dict.fromkeys(circuit.operations))
    if action_sequence is None:
        positions={gate:i for i,gate in enumerate(actions)}
        sequence=[positions[gate] for gate in circuit.operations]
    else:
        if not isinstance(action_sequence,list) or len(action_sequence)>100_000:raise ValueError('action sequence must be a list of at most 100000 indices')
        sequence=[_integer(i,'action index',0,len(actions)-1) for i in action_sequence]
    values=[]
    for row in basis:
        value=ZERO
        for (x,z),v in row.items():
            b.tick('reading_steps')
            if not x:value=b.add(value,-v if (z&input_basis).bit_count()%2 else v)
        values.append(value)
    for action in sequence:
        updated=[]
        for row in transfers[action]:
            value=ZERO
            for i,v in row.items():
                b.tick('reading_steps');value=b.add(value,b.mul(v,values[i]))
            updated.append(value)
        values=updated
    result=b.mul(seed_scale,values[0])
    return dict(status='completed',algebraically_exact=True,value=result.to_dict(),
        input_state='computational_basis',input_basis=str(input_basis),retained_dimension=len(basis),word_length=len(sequence),
        statistics=dict(b.stats))
