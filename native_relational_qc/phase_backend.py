"""Bounded exact sparse computational-basis execution in Q(zeta_16).

Explicit backend, one preparation per calculator batch. Every amplitude and
interference term is retained. Support can grow exponentially; no dense array,
Clifford-frame compression, prime oracle, or universal speedup is claimed.
"""
from time import perf_counter
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
from threading import RLock

import numpy as np

from .compact import CompactCircuit,ResourceLimit,_integer,operation_plan
from .exact import exact_gate,IMAG
from .cyclotomic import Cyclotomic,ZERO,ONE,ZETA

PHASE_GATES={'p16':(1,1),'p16dg':(1,-1),'cp16':(2,1),'cp16dg':(2,-1)}


class PhaseCircuit(CompactCircuit):
    field=Cyclotomic
    backend='cyclotomic'
    phase_gates={name:(width,ZETA**power) for name,(width,power) in PHASE_GATES.items()}

    def add(self,name,*qargs):
        if name not in self.phase_gates:return super().add(name,*qargs)
        width,_=self.phase_gates[name]
        if len(qargs)!=width or len(set(qargs))!=width:raise ValueError('phase gate requires distinct wires of declared arity')
        for q in qargs:_integer(q,'qubit',0,self.n_qubits-1)
        self._operations.append((name,tuple(qargs)))
        return self

    def state(self,**limits):return prepare(self,**limits)


class Phase32Circuit(PhaseCircuit):
    from .cyclotomic32 import Cyclotomic32 as field,ZETA as root
    backend='cyclotomic32'
    phase_gates=dict(PhaseCircuit.phase_gates)
    for name,width,power in (('p32',1,1),('p32dg',1,-1),('cp32',2,1),('cp32dg',2,-1)):
        phase_gates[name]=(width,root**power)


class Phase64Circuit(Phase32Circuit):
    from .cyclotomic64 import Cyclotomic64 as field,ZETA as root
    backend='cyclotomic64'
    phase_gates=dict(Phase32Circuit.phase_gates)
    for name,width,power in (('p64',1,1),('p64dg',1,-1),('cp64',2,1),('cp64dg',2,-1)):
        phase_gates[name]=(width,root**power)


class PowerPhaseCircuit(PhaseCircuit):
    """Sparse exact execution in flat Q(zeta_M), M=2**k, 8<=M<=4096.

    Phase gates pK/pKdg/cpK/cpKdg mean diag(1,exp(+-2*pi*i/K)) for every power
    of two 2<=K<=M; p16/p32/p64 keep their earlier meanings.
    """
    backend='cyclotomic_pow2'
    max_gates=1_000_000   # declared-operation cap for this backend; others keep 100000

    def __init__(self,n_qubits,order=64):
        from .cyclotomic_pow2 import field_of_order
        super().__init__(n_qubits)
        self.field=field_of_order(order);self.order=order
        self.phase_gates={}
        K=2
        while K<=order:
            for name,width,power in ((f'p{K}',1,1),(f'p{K}dg',1,-1),(f'cp{K}',2,1),(f'cp{K}dg',2,-1)):
                self.phase_gates[name]=(width,self.field.root(power*(order//K)))
            K*=2

    def revalidate(self,name,qs):PowerPhaseCircuit(self.n_qubits,self.order).add(name,*qs)


def required_order(operations):
    """Smallest supported power-of-two order containing every declared phase gate."""
    import re
    order=8
    for name,_ in operations:
        match=re.fullmatch(r'c?p([1-9][0-9]*)(dg)?',name)
        if match:
            K=int(match.group(1))
            if K&(K-1) or K<2:raise ValueError('phase gate order must be a power of two')
            order=max(order,K)
    return order


class Budget:
    def __init__(self,max_work=10_000_000,max_coefficient_bits=4096,max_branches=4096):
        self.max_work=_integer(max_work,'max_work',1,1_000_000_000)
        self.max_bits=_integer(max_coefficient_bits,'max_coefficient_bits',2,8192)
        self.max_branches=_integer(max_branches,'max_branches',1,1_048_576)
        self.lock=nullcontext()
        self.failure=None
        self.stats=dict(backend='cyclotomic',work_used=0,peak_branches=1,max_coefficient_bits=1,
            preparation_count=0,gate_visits=0,readout_visits=0,field_products=0,field_sums=0,
            budget_scope='whole batch including preparation and all readouts',
            representation='sparse computational-basis amplitudes in Q(zeta_16)',
            work_definition='one unit per gate, amplitude/readout visit, field product or field sum',
            dense_statevector_constructed=False,truncated_amplitudes=0)

    def tick(self,kind):
        self.tick_many(kind,1)

    def tick_many(self,kind,count):
        """Account count unit visits at once; fails at exactly the same unit as tick."""
        with self.lock:
            if self.failure:self.fail(self.failure)
            used=self.stats['work_used']
            if used+count>self.max_work:
                self.stats[kind]+=self.max_work+1-used;self.stats['work_used']=self.max_work+1
                self.fail('cyclotomic batch work budget exceeded')
            self.stats[kind]+=count;self.stats['work_used']=used+count

    def fail(self,message):
        self.failure=message
        error=ResourceLimit(message);error.statistics=dict(self.stats)
        raise error

    def inspect(self,value):
        bits=value.max_bits
        with self.lock:
            if self.failure:self.fail(self.failure)
            self.stats['max_coefficient_bits']=max(self.stats['max_coefficient_bits'],bits)
            if bits>self.max_bits:self.fail('cyclotomic coefficient bit budget exceeded')
        return value

    def mul(self,a,b):self.tick('field_products');return self.inspect(a*b)
    def add(self,a,b):self.tick('field_sums');return self.inspect(a+b)

    def put(self,state,key,value):
        value=self.inspect(value)
        if key in state:value=self.add(state[key],value)
        if value:
            if key not in state and len(state)>=self.max_branches:self.fail('cyclotomic amplitude support budget exceeded')
            state[key]=value;self.stats['peak_branches']=max(self.stats['peak_branches'],len(state))
        else:state.pop(key,None)


class Prepared:
    def __init__(self,circuit,budget,amplitudes,norms=None):
        self.n_qubits=circuit.n_qubits;self.budget=budget;self.amplitudes=amplitudes
        self.field=getattr(circuit,'field',Cyclotomic);self.order=getattr(circuit,'order',None)
        # Flat backend: |amplitude|^2 computed once for the normalization check
        # is reused by probability readouts instead of being recomputed.
        self.norms=norms

    def _norm(self,ket,value):
        return self.norms[ket] if self.norms is not None else self.budget.mul(value.conjugate(),value)

    def probability(self,outcomes):
        from .calculator import _site_map
        outcomes=_site_map({str(q):v for q,v in outcomes.items()},self.n_qubits)
        total=self.field();b=self.budget
        for ket,value in self.amplitudes.items():
            b.tick('readout_visits')
            if all((ket>>q)&1==v for q,v in outcomes.items()):
                total=b.add(total,self._norm(ket,value))
        return total

    def distribution(self,sites):
        sites=tuple(sites);width=12 if getattr(self,'order',None) else 8
        if not 1<=len(sites)<=width or len(set(sites))!=len(sites):raise ValueError(f'distribution needs 1..{width} distinct wires')
        for q in sites:_integer(q,'qubit',0,self.n_qubits-1)
        out={format(y,f'0{len(sites)}b'):self.field() for y in range(1<<len(sites))};b=self.budget
        for ket,value in self.amplitudes.items():
            b.tick('readout_visits');label=''.join(str((ket>>q)&1) for q in sites)
            out[label]=b.add(out[label],self._norm(ket,value))
        total=self.field()
        for value in out.values():total=b.add(total,value)
        if total!=self.field(1):raise ArithmeticError('phase distribution not normalized')
        return out

    def expectation(self,paulis):
        from .calculator import _site_map
        paulis=_site_map({str(q):v for q,v in paulis.items()},self.n_qubits,paulis=True)
        x=z=ny=0
        for q,p in paulis.items():
            if p in ('X','Y'):x|=1<<q
            if p in ('Z','Y'):z|=1<<q
            if p=='Y':ny+=1
        phase=self.field(IMAG**ny);out=self.field();b=self.budget
        for ket,value in self.amplitudes.items():
            b.tick('readout_visits');bra=self.amplitudes.get(ket^x,self.field()).conjugate()
            coefficient=-phase if (ket&z).bit_count()%2 else phase
            out=b.add(out,b.mul(b.mul(bra,coefficient),value))
        if out!=out.conjugate():raise ArithmeticError('Pauli expectation is not real')
        return out


PERMUTATIONS=('id','x','rk','cx','ccx','swap')


def _permute_run(circuit,operations,index,state,b):
    """Apply a maximal run of permutation gates to all kets at once (flat backend).

    Amplitudes are untouched; only the basis labels move, as NumPy int64 bit
    operations. Work accounting is identical to the per-ket loop: one gate
    visit per gate and one permutation visit per ket per gate.
    """
    kets=np.fromiter(state.keys(),dtype=np.int64,count=len(state));values=list(state.values())
    count=len(kets)
    while index<len(operations) and operations[index][0] in PERMUTATIONS:
        name,qs=operations[index];b.tick('gate_visits')
        operation_plan(circuit.n_qubits,name,qs)
        b.tick_many('permutation_visits',count)
        if name in ('x','rk'):kets^=np.int64(1<<qs[0])
        elif name=='cx':kets^=((kets>>np.int64(qs[0]))&np.int64(1))<<np.int64(qs[1])
        elif name=='ccx':kets^=((kets>>np.int64(qs[0]))&(kets>>np.int64(qs[1]))&np.int64(1))<<np.int64(qs[2])
        elif name=='swap':
            differ=((kets>>np.int64(qs[0]))^(kets>>np.int64(qs[1])))&np.int64(1)
            kets^=(differ<<np.int64(qs[0]))|(differ<<np.int64(qs[1]))
        index+=1
    return dict(zip(kets.tolist(),values)),index


def execute(circuit,state,b):
    """Apply circuit.operations to a sparse basis-label -> amplitude state.

    Shared by prepare (from the all-zero label) and by executors that start
    from another exact state, such as the record-conditioned phase estimation.
    """
    field=getattr(circuit,'field',Cyclotomic)
    phase_gates=getattr(circuit,'phase_gates',PhaseCircuit.phase_gates)
    flat=isinstance(circuit,PowerPhaseCircuit)
    vectorize=flat and circuit.n_qubits<=62
    operations=circuit.operations;index=0
    while index<len(operations):
        name,qs=operations[index]
        if vectorize and name in PERMUTATIONS:
            state,index=_permute_run(circuit,operations,index,state,b);continue
        index+=1;b.tick('gate_visits')
        if name in PERMUTATIONS:
            # These declared gates are phase-free permutations. Copy the exact
            # amplitudes unchanged; no multiplication by one is necessary.
            operation_plan(circuit.n_qubits,name,qs)
            out={}
            for ket,value in state.items():
                b.tick('permutation_visits');target=ket
                if name in ('x','rk'):target^=1<<qs[0]
                elif name in ('cx','ccx') and all(ket&(1<<q) for q in qs[:-1]):target^=1<<qs[-1]
                elif name=='swap' and ((ket>>qs[0])^(ket>>qs[1]))&1:target^=(1<<qs[0])|(1<<qs[1])
                out[target]=value
            state=out
        elif name in phase_gates:
            width,phase=phase_gates[name];phase=field.coerce(phase)
            # Revalidate even if called directly with another circuit implementation.
            if isinstance(circuit,PowerPhaseCircuit):circuit.revalidate(name,qs)
            else:(Phase64Circuit if field is Phase64Circuit.field else Phase32Circuit if field is Phase32Circuit.field else PhaseCircuit)(circuit.n_qubits).add(name,*qs)
            root_power=None
            if isinstance(circuit,PowerPhaseCircuit) and phase.den==1:
                terms=phase.terms
                if len(terms)==1 and abs(terms[0][1])==1:
                    root_power=terms[0][0]+(field.N if terms[0][1]<0 else 0)
            out={}
            for ket,value in state.items():
                b.tick('gate_visits')
                if all(ket&(1<<q) for q in qs):
                    if root_power is None or getattr(value,'ORDER',None)!=field.ORDER:value=b.mul(value,phase)
                    else:
                        b.tick('field_products');value=value.times_root(root_power)
                        # put checks the identical coefficient bound immediately
                        # after the product, including externally supplied states.
                b.put(out,ket,value)
            state=out
        else:
            for basic,target,controls in operation_plan(circuit.n_qubits,name,qs):
                matrix=tuple(tuple(field(v) for v in row) for row in exact_gate(basic));out={}
                for ket,value in state.items():
                    b.tick('gate_visits')
                    if not all(ket&(1<<q) for q in controls):b.put(out,ket,value);continue
                    bit=(ket>>target)&1;base=ket&~(1<<target)
                    if flat and basic=='h':
                        # Retain the two logical matrix products and the original
                        # put order for work, bit and transient-support budgets.
                        # Their magnitudes agree, so compute the common value once.
                        b.tick('field_products');half=field.coerce(value).times_inv_sqrt2()
                        b.put(out,base,half)
                        b.tick('field_products')
                        b.put(out,base|(1<<target),half.times_root(field.N) if bit else half)
                        continue
                    for reading in (0,1):
                        if matrix[reading][bit]:b.put(out,base|(reading<<target),b.mul(matrix[reading][bit],value))
                state=out
    return state


def prepare(circuit,**limits):
    if not isinstance(circuit,CompactCircuit):raise TypeError('phase backend requires a declared circuit')
    _integer(circuit.n_qubits,'phase backend qubits',1,256)
    field=getattr(circuit,'field',Cyclotomic);zero,one=field(),field(1)
    flat=isinstance(circuit,PowerPhaseCircuit)
    if not flat and limits.get('max_branches',4096)>65_536:
        raise ValueError('legacy phase backend max_branches must be <=65536')
    b=Budget(**limits);b.stats['preparation_count']=1;state={0:one}
    b.stats.update(backend=getattr(circuit,'backend','cyclotomic'),
        representation='sparse computational-basis amplitudes in '+(f'flat Q(zeta_{circuit.order})' if isinstance(circuit,PowerPhaseCircuit) else 'Q(zeta_64)' if field is Phase64Circuit.field else 'Q(zeta_32)' if field is Phase32Circuit.field else 'Q(zeta_16)'),
        permutation_visits=0)
    state=execute(circuit,state,b)
    norm=zero;norms={} if flat else None
    for ket,value in state.items():
        squared=b.mul(value.conjugate(),value);norm=b.add(norm,squared)
        if flat:norms[ket]=squared
    if norm!=one:raise ArithmeticError('phase state not exactly normalized')
    return Prepared(circuit,b,state,norms)


def calculate_request(circuit,request):
    from .calculator import _digest,OUTPUT_SCHEMA,display,real_sign
    start=perf_counter()
    zero,one=circuit.field(),circuit.field(1)
    report=dict(schema=OUTPUT_SCHEMA,status='completed',evidence_class='LOCAL_IDEAL_CALCULATION',
        hardware_job_id=None,input_state='all_zero',backend=request['backend'],
        circuit_sha256=_digest(dict(n_qubits=circuit.n_qubits,operations=request['operations'])),
        request_sha256=_digest(request),n_qubits=circuit.n_qubits,gates=len(circuit.operations),
        limits_per_batch=request['limits'],answers=[])
    prepared=None
    try:
        prepared=prepare(circuit,**request['limits']);report['preparation_seconds']=perf_counter()-start
        def read(query):
            qstart=perf_counter();row=dict(id=query['id'],kind=query['kind'],status='completed',algebraically_exact=True)
            if query['kind']=='distribution':
                values=prepared.distribution(query['qubits'])
                for value in values.values():
                    if real_sign(value)<0 or real_sign(one-value)<0:raise ArithmeticError('invalid probability')
                row.update(probabilities={label:display(v,request['decimal_places']) for label,v in values.items()},
                    bitstring_qubits_left_to_right=query['qubits'],normalization=one.to_dict())
            else:
                expectation=query['kind']=='expectation';field='paulis' if expectation else 'outcomes'
                target={int(k):v for k,v in query[field].items()}
                value=prepared.expectation(target) if expectation else prepared.probability(target)
                if real_sign(value-(-one if expectation else zero))<0 or real_sign(one-value)<0:
                    raise ArithmeticError('observation outside range')
                row['value']=display(value,request['decimal_places'])
            row['execution_seconds']=perf_counter()-qstart
            return row
        workers=request.get('readout_workers',1)
        if workers>1:
            prepared.budget.lock=RLock()
            # The immutable amplitude/norm dictionaries are shared. Only work
            # accounting is mutable and is protected by one batch-wide lock.
            # map retains input order; a failure discards the entire batch.
            with ThreadPoolExecutor(max_workers=workers) as pool:
                report['answers']=list(pool.map(read,request['queries']))
        else:
            report['answers']=[read(query) for query in request['queries']]
        report['readout_workers']=workers
        report['statistics']=dict(prepared.budget.stats)
    except ResourceLimit as error:
        report.update(status='incomplete',answers=[],algebraically_exact=False,error=str(error),
                      failure_contract='whole batch discarded; no partial results')
        report['statistics']=dict(prepared.budget.stats) if prepared is not None else getattr(error,'statistics',{})
    report['execution_seconds']=perf_counter()-start
    return report
