"""Exact measurement pullback and bounded future-closed Pauli banks.

MR-04 specialization to unitary conjugation on density operators. Coordinate
closure is sufficient, not generally a minimum linear realization. No dense
state, unbounded closure, approximate rank decision or amplitude truncation.
"""
from fractions import Fraction
from time import perf_counter
from .compact import ResourceLimit,_integer
from .cyclotomic32 import Cyclotomic32 as C,ZERO,ONE
from .exact import IMAG
from .observer import _conjugate as old_image
from .phase_backend import Phase32Circuit


class Budget:
    def __init__(self,max_work=10_000_000,max_terms=4096,max_coefficient_bits=4096):
        self.max_work=_integer(max_work,'max_work',1,1_000_000_000)
        self.max_terms=_integer(max_terms,'max_terms',1,1_000_000)
        self.max_bits=_integer(max_coefficient_bits,'max_coefficient_bits',2,8192)
        self.stats=dict(work_used=0,gate_scans=0,term_visits=0,transition_terms=0,
            field_products=0,field_sums=0,peak_terms=0,max_coefficient_bits=1,
            local_images_built=0,disjoint_term_visits=0,cache_hits=0,
            statevector_constructed=False,truncated_terms=0)
    def fail(self,message):
        e=ResourceLimit(message);e.statistics=dict(self.stats);raise e
    def tick(self,key):
        self.stats[key]+=1;self.stats['work_used']+=1
        if self.stats['work_used']>self.max_work:self.fail('observer32 whole-batch work limit')
    def inspect(self,v):
        self.stats['max_coefficient_bits']=max(self.stats['max_coefficient_bits'],v.max_bits)
        if v.max_bits>self.max_bits:self.fail('observer32 coefficient bit limit')
        return v
    def add(self,a,b):self.tick('field_sums');return self.inspect(a+b)
    def mul(self,a,b):self.tick('field_products');return self.inspect(a*b)
    def put(self,d,key,v):
        if not v:return
        if key in d:v=self.add(d[key],v)
        if v:
            if key not in d and len(d)>=self.max_terms:self.fail('observer32 retained term limit')
            d[key]=self.inspect(v);self.stats['peak_terms']=max(self.stats['peak_terms'],len(d))
        else:d.pop(key,None)


class Engine:
    def __init__(self,circuit,**limits):
        if not isinstance(circuit,Phase32Circuit):raise TypeError('observer32 requires Phase32Circuit')
        self.circuit=circuit;self.b=Budget(**limits);self.cache={}
    def local_image(self,name,width,x,z):
        key=(name,width,x,z)
        if key in self.cache:self.b.stats['cache_hits']+=1;return self.cache[key]
        self.b.stats['local_images_built']+=1
        if x==z==0:result=((0,0,ONE),)
        elif name not in Phase32Circuit.phase_gates:
            result=tuple((a,b,C(v)) for a,b,v in old_image(name,width,x,z))
        else:
            # Diagonal conjugation preserves the X mask. Trace against all Z
            # masks; phase conventions retain the signs of Hermitian Y words.
            _,phase=Phase32Circuit.phase_gates[name];phase=C.coerce(phase)
            dim=1<<width;diag=[ONE]*(dim-1)+[phase];out=[]
            original=C(IMAG**((x&z).bit_count()))
            for nz in range(dim):
                target=C(IMAG**((x&nz).bit_count()));total=ZERO
                for j in range(dim):
                    v=self.b.mul(self.b.mul(original,target),self.b.mul(diag[j^x].conjugate(),diag[j]))
                    if ((j&z).bit_count()+((j^x)&nz).bit_count())%2:v=-v
                    total=self.b.add(total,v)
                v=self.b.mul(total,C(Fraction(1,dim)))
                if v:
                    if v!=v.conjugate():raise ArithmeticError('nonreal Hermitian Pauli coefficient')
                    out.append((x,nz,v))
            result=tuple(out)
        for _,_,v in result:self.b.inspect(v)
        self.cache[key]=result;return result
    def image(self,key,gate):
        name,qs=gate;x,z=key;mask=sum(1<<q for q in qs)
        self.b.tick('term_visits')
        if not (x|z)&mask:
            self.b.stats['disjoint_term_visits']+=1;return ((x,z,ONE),)
        lx=sum(((x>>q)&1)<<i for i,q in enumerate(qs));lz=sum(((z>>q)&1)<<i for i,q in enumerate(qs))
        return tuple(((x&~mask)|sum(((a>>i)&1)<<q for i,q in enumerate(qs)),
            (z&~mask)|sum(((b>>i)&1)<<q for i,q in enumerate(qs)),v)
            for a,b,v in self.local_image(name,len(qs),lx,lz))
    def step(self,terms,gate):
        out={};self.b.tick('gate_scans')
        for key,coefficient in terms.items():
            for x,z,factor in self.image(key,gate):
                self.b.tick('transition_terms')
                self.b.put(out,(x,z),coefficient if factor==ONE else self.b.mul(coefficient,factor))
        return out
    def pullback(self,terms):
        checked={}
        for k,v in terms.items():self.b.put(checked,k,v)
        for gate in reversed(self.circuit.operations):checked=self.step(checked,gate)
        return checked
    def evaluate(self,terms):
        value=ZERO
        for (x,z),v in self.pullback(terms).items():
            # A zero source expectation is discarded only after all gates.
            if not x:value=self.b.add(value,v)
        return value
    def projector(self,outcomes):
        if (1<<len(outcomes))>self.b.max_terms:self.b.fail('observer32 initial projector exceeds term limit')
        scale=self.b.inspect(C(Fraction(1,1<<len(outcomes))));terms={(0,0):scale}
        for q,bit in outcomes.items():
            for (x,z),v in list(terms.items()):self.b.put(terms,(x,z|(1<<q)),-v if bit else v)
        return terms


def word(paulis):
    x=z=0
    for q,p in paulis.items():
        if p in ('X','Y'):x|=1<<q
        if p in ('Z','Y'):z|=1<<q
    return x,z


def future_bank(circuit,paulis,**limits):
    """Close a Pauli coordinate bank under EVERY word of the declared alphabet.

    This may exceed the minimum MR-04 row space, but exact sparse transition
    rows certify closure. Failure returns no partial certificate. The entire
    density-operator carrier is represented implicitly, never allocated.
    """
    from .calculator import _site_map,_digest
    if not isinstance(circuit,Phase32Circuit):raise TypeError('observer32 requires Phase32Circuit')
    if not isinstance(paulis,dict):raise ValueError('Pauli seed must be a site map')
    canonical={str(q):v for q,v in paulis.items()}
    if len(canonical)!=len(paulis):raise ValueError('duplicate Pauli seed site')
    paulis=_site_map(canonical,circuit.n_qubits,paulis=True)
    engine=Engine(circuit,**limits);b=engine.b
    actions=tuple(dict.fromkeys(circuit.operations));keys=[word(paulis)];seen=set(keys);images={}
    b.stats['peak_terms']=1;cursor=0
    while cursor<len(keys):
        key=keys[cursor];cursor+=1
        for index,gate in enumerate(actions):
            b.tick('gate_scans');result=engine.image(key,gate);images[key,index]=result
            for x,z,v in result:
                b.tick('transition_terms');b.inspect(v);new=(x,z)
                if new not in seen:
                    if len(keys)>=b.max_terms:b.fail('observer32 future bank exceeds term limit')
                    seen.add(new);keys.append(new);b.stats['peak_terms']=len(keys)
    positions={key:i for i,key in enumerate(keys)}
    return dict(schema='nrqc-future-observer-bank-v1',status='closed',
        n_qubits=circuit.n_qubits,action_sha256=_digest([[g,list(q)] for g,q in actions]),
        actions=[[g,list(q)] for g,q in actions],seed_index=0,
        basis=[dict(x=str(x),z=str(z)) for x,z in keys],
        transition_rows=[[[dict(column=positions[x,z],coefficient=v.to_dict()) for x,z,v in images[key,j]] for key in keys] for j in range(len(actions))],
        retained_dimension=len(keys),ambient_operator_dimension=str(4**circuit.n_qubits),
        minimality_claim=False,scope='all words over the exact declared wire-labelled action alphabet; all density operators',
        statistics=dict(b.stats))


def calculate_request(circuit,request):
    from .calculator import _digest,OUTPUT_SCHEMA,display,real_sign
    started=perf_counter();e=Engine(circuit,**request['limits']);answers=[]
    report=dict(schema=OUTPUT_SCHEMA,status='completed',backend='observer32',
        evidence_class='LOCAL_IDEAL_CALCULATION',hardware_job_id=None,input_state='all_zero',
        circuit_sha256=_digest(dict(n_qubits=circuit.n_qubits,operations=request['operations'])),
        request_sha256=_digest(request),n_qubits=circuit.n_qubits,gates=len(circuit.operations),
        limits_per_batch=request['limits'],answers=[],
        recognition_scope='exact selected observations along the declared circuit; no all-future closure asserted')
    try:
        for query in request['queries']:
            row=dict(id=query['id'],kind=query['kind'],status='completed',algebraically_exact=True)
            if query['kind']=='distribution':
                sites=query['qubits'];values={};total=ZERO
                for i in range(1<<len(sites)):
                    label=format(i,f'0{len(sites)}b')
                    v=e.evaluate(e.projector({q:int(bit) for q,bit in zip(sites,label)}))
                    if real_sign(v)<0 or real_sign(ONE-v)<0:raise ArithmeticError('invalid probability')
                    total=e.b.add(total,v);values[label]=display(v,request['decimal_places'])
                if total!=ONE:raise ArithmeticError('distribution normalization failed')
                row.update(probabilities=values,normalization=ONE.to_dict(),bitstring_qubits_left_to_right=sites)
            else:
                expectation=query['kind']=='expectation';target={int(k):v for k,v in query['paulis' if expectation else 'outcomes'].items()}
                v=e.evaluate({word(target):ONE} if expectation else e.projector(target))
                if real_sign(v-(-ONE if expectation else ZERO))<0 or real_sign(ONE-v)<0:raise ArithmeticError('observation outside range')
                row['value']=display(v,request['decimal_places'])
            answers.append(row)
        report['answers']=answers
        report['error_ledger']=dict(arithmetic_error='0',analytic_truncation_error='0',
            display_rounding='per-value outward decimal_enclosure',
            scope='completed ideal-circuit algebraic observations only')
    except ResourceLimit as error:
        report.update(status='incomplete',answers=[],algebraically_exact=False,error=str(error),failure_contract='whole batch discarded')
    report.update(statistics=dict(e.b.stats),execution_seconds=perf_counter()-started)
    return report
