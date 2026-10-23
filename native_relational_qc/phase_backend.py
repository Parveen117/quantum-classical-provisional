"""Bounded exact sparse computational-basis execution in Q(zeta_16).

Explicit backend, one preparation per calculator batch. Every amplitude and
interference term is retained. Support can grow exponentially; no dense array,
Clifford-frame compression, prime oracle, or universal speedup is claimed.
"""
from time import perf_counter

from .compact import CompactCircuit,ResourceLimit,_integer,operation_plan
from .exact import exact_gate,IMAG
from .cyclotomic import Cyclotomic,ZERO,ONE,ZETA

PHASE_GATES={'p16':(1,1),'p16dg':(1,-1),'cp16':(2,1),'cp16dg':(2,-1)}


class PhaseCircuit(CompactCircuit):
    def add(self,name,*qargs):
        if name not in PHASE_GATES:return super().add(name,*qargs)
        width,_=PHASE_GATES[name]
        if len(qargs)!=width or len(set(qargs))!=width:raise ValueError('phase gate requires distinct wires of declared arity')
        for q in qargs:_integer(q,'qubit',0,self.n_qubits-1)
        self._operations.append((name,tuple(qargs)))
        return self

    def state(self,**limits):return prepare(self,**limits)


class Budget:
    def __init__(self,max_work=10_000_000,max_coefficient_bits=4096,max_branches=4096):
        self.max_work=_integer(max_work,'max_work',1,1_000_000_000)
        self.max_bits=_integer(max_coefficient_bits,'max_coefficient_bits',2,8192)
        self.max_branches=_integer(max_branches,'max_branches',1,65_536)
        self.stats=dict(backend='cyclotomic',work_used=0,peak_branches=1,max_coefficient_bits=1,
            preparation_count=0,gate_visits=0,readout_visits=0,field_products=0,field_sums=0,
            budget_scope='whole batch including preparation and all readouts',
            representation='sparse computational-basis amplitudes in Q(zeta_16)',
            work_definition='one unit per gate, amplitude/readout visit, field product or field sum',
            dense_statevector_constructed=False,truncated_amplitudes=0)

    def tick(self,kind):
        self.stats[kind]+=1;self.stats['work_used']+=1
        if self.stats['work_used']>self.max_work:self.fail('cyclotomic batch work budget exceeded')

    def fail(self,message):
        error=ResourceLimit(message);error.statistics=dict(self.stats)
        raise error

    def inspect(self,value):
        self.stats['max_coefficient_bits']=max(self.stats['max_coefficient_bits'],value.max_bits)
        if value.max_bits>self.max_bits:self.fail('cyclotomic coefficient bit budget exceeded')
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
    def __init__(self,circuit,budget,amplitudes):
        self.n_qubits=circuit.n_qubits;self.budget=budget;self.amplitudes=amplitudes

    def probability(self,outcomes):
        from .calculator import _site_map
        outcomes=_site_map({str(q):v for q,v in outcomes.items()},self.n_qubits)
        total=ZERO;b=self.budget
        for ket,value in self.amplitudes.items():
            b.tick('readout_visits')
            if all((ket>>q)&1==v for q,v in outcomes.items()):
                total=b.add(total,b.mul(value.conjugate(),value))
        return total

    def distribution(self,sites):
        sites=tuple(sites)
        if not 1<=len(sites)<=8 or len(set(sites))!=len(sites):raise ValueError('distribution needs 1..8 distinct wires')
        for q in sites:_integer(q,'qubit',0,self.n_qubits-1)
        out={format(y,f'0{len(sites)}b'):ZERO for y in range(1<<len(sites))};b=self.budget
        for ket,value in self.amplitudes.items():
            b.tick('readout_visits');label=''.join(str((ket>>q)&1) for q in sites)
            out[label]=b.add(out[label],b.mul(value.conjugate(),value))
        total=ZERO
        for value in out.values():total=b.add(total,value)
        if total!=ONE:raise ArithmeticError('phase distribution not normalized')
        return out

    def expectation(self,paulis):
        from .calculator import _site_map
        paulis=_site_map({str(q):v for q,v in paulis.items()},self.n_qubits,paulis=True)
        x=z=ny=0
        for q,p in paulis.items():
            if p in ('X','Y'):x|=1<<q
            if p in ('Z','Y'):z|=1<<q
            if p=='Y':ny+=1
        phase=Cyclotomic(IMAG**ny);out=ZERO;b=self.budget
        for ket,value in self.amplitudes.items():
            b.tick('readout_visits');bra=self.amplitudes.get(ket^x,ZERO).conjugate()
            coefficient=-phase if (ket&z).bit_count()%2 else phase
            out=b.add(out,b.mul(b.mul(bra,coefficient),value))
        if out!=out.conjugate():raise ArithmeticError('Pauli expectation is not real')
        return out


def prepare(circuit,**limits):
    if not isinstance(circuit,CompactCircuit):raise TypeError('phase backend requires a declared circuit')
    _integer(circuit.n_qubits,'phase backend qubits',1,256)
    b=Budget(**limits);b.stats['preparation_count']=1;state={0:ONE}
    for name,qs in circuit.operations:
        b.tick('gate_visits')
        if name in PHASE_GATES:
            width,power=PHASE_GATES[name]
            # Revalidate even if called directly with another circuit implementation.
            PhaseCircuit(circuit.n_qubits).add(name,*qs)
            phase=ZETA**power;out={}
            for ket,value in state.items():
                b.tick('gate_visits')
                b.put(out,ket,b.mul(value,phase) if all(ket&(1<<q) for q in qs) else value)
            state=out
        else:
            for basic,target,controls in operation_plan(circuit.n_qubits,name,qs):
                matrix=tuple(tuple(Cyclotomic(v) for v in row) for row in exact_gate(basic));out={}
                for ket,value in state.items():
                    b.tick('gate_visits')
                    if not all(ket&(1<<q) for q in controls):b.put(out,ket,value);continue
                    bit=(ket>>target)&1;base=ket&~(1<<target)
                    for reading in (0,1):
                        if matrix[reading][bit]:b.put(out,base|(reading<<target),b.mul(matrix[reading][bit],value))
                state=out
    norm=ZERO
    for value in state.values():norm=b.add(norm,b.mul(value.conjugate(),value))
    if norm!=ONE:raise ArithmeticError('phase state not exactly normalized')
    return Prepared(circuit,b,state)


def calculate_request(circuit,request):
    from .calculator import _digest,OUTPUT_SCHEMA,display,real_sign
    start=perf_counter()
    report=dict(schema=OUTPUT_SCHEMA,status='completed',evidence_class='LOCAL_IDEAL_CALCULATION',
        hardware_job_id=None,input_state='all_zero',backend='cyclotomic',
        circuit_sha256=_digest(dict(n_qubits=circuit.n_qubits,operations=request['operations'])),
        request_sha256=_digest(request),n_qubits=circuit.n_qubits,gates=len(circuit.operations),
        limits_per_batch=request['limits'],answers=[])
    prepared=None
    try:
        prepared=prepare(circuit,**request['limits']);report['preparation_seconds']=perf_counter()-start
        for query in request['queries']:
            qstart=perf_counter();row=dict(id=query['id'],kind=query['kind'],status='completed',algebraically_exact=True)
            if query['kind']=='distribution':
                values=prepared.distribution(query['qubits'])
                for value in values.values():
                    if real_sign(value)<0 or real_sign(ONE-value)<0:raise ArithmeticError('invalid probability')
                row.update(probabilities={label:display(v,request['decimal_places']) for label,v in values.items()},
                    bitstring_qubits_left_to_right=query['qubits'],normalization=ONE.to_dict())
            else:
                expectation=query['kind']=='expectation';field='paulis' if expectation else 'outcomes'
                target={int(k):v for k,v in query[field].items()}
                value=prepared.expectation(target) if expectation else prepared.probability(target)
                if real_sign(value-(-ONE if expectation else ZERO))<0 or real_sign(ONE-value)<0:
                    raise ArithmeticError('observation outside range')
                row['value']=display(value,request['decimal_places'])
            row['execution_seconds']=perf_counter()-qstart;report['answers'].append(row)
        report['statistics']=dict(prepared.budget.stats)
    except ResourceLimit as error:
        report.update(status='incomplete',answers=[],algebraically_exact=False,error=str(error),
                      failure_contract='whole batch discarded; no partial results')
        report['statistics']=dict(prepared.budget.stats) if prepared is not None else getattr(error,'statistics',{})
    report['execution_seconds']=perf_counter()-start
    return report
