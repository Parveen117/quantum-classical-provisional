"""Record-conditioned exact phase estimation on the flat field.

One control wire is prepared in |+>, entangled with the work register by the
same reversible controlled modular multiplier that the full-register Shor
program uses, corrected by a phase that depends only on the readings already
taken, turned by a Hadamard, read in the Z basis and reused. Both outcomes of
every reading are followed with unnormalized branch states, so the result is
the exact distribution over complete m-bit records, not a sample.

The semiclassical Fourier transform theorem (Griffiths and Niu, 1996) says
this record has the same law as the Z readout of the full inverse-QFT control
register. RECORD_PHASE.md states the exact algebraic form used here, and every
run is checked instance by instance against the independent Fourier law. The
memory is O(m * orbit) amplitudes instead of O(2**m * orbit); the leaf cost,
one |amplitude|**2 per work label per record, is the same as a full readout.
"""
import argparse
from collections import Counter
from dataclasses import dataclass
import json
from math import gcd
from pathlib import Path
from time import perf_counter

from .calculator import _digest,display,real_sign
from .compact import ResourceLimit,_integer
from .cyclotomic_pow2 import field_of_order
from .modular_arithmetic import append_multiplier,multiplier_workspace
from .phase_backend import Budget,PowerPhaseCircuit,PERMUTATIONS,execute
from .shor import MAX_PRECISION,decode,exact_phase_law

SCHEMA='nrqc-record-phase-v1'


@dataclass(frozen=True)
class RecordProgram:
    modulus: int
    base: int
    precision: int
    order: int
    control: int
    work: tuple
    scratch: tuple
    rounds: tuple      # (j, multiplier a**(2**j) mod N, controlled-multiplier circuit), executed in this order

    @property
    def field(self):return field_of_order(self.order)

    @property
    def n_qubits(self):return 1+len(self.work)+len(self.scratch)

    def correction_exponent(self,level,readings):
        """Exponent e with R=zeta_M**e applied to the |1> branch before reading number level.

        The branch carries exp(2*pi*i*2**j*theta) with j=m-1-level. The readings
        y_0..y_(level-1) already fix the binary digits of 2**j*theta below the
        half digit, so they are removed: e = -(M/2**m) * sum_t y_t 2**(t+j).
        """
        j=self.precision-1-level
        return -(self.order>>self.precision)*sum(y<<(t+j) for t,y in enumerate(readings[:level]))

    def metadata(self):
        gates=[len(c.operations) for _,_,c in self.rounds]
        return dict(modulus=self.modulus,base=self.base,precision_bits=self.precision,field_order=self.order,
            n_qubits=self.n_qubits,control_wire=self.control,work_lsb_first=list(self.work),scratch=list(self.scratch),
            rounds=[dict(reading=t,power_of_two=j,multiplier=b,gates=g) for t,((j,b,_),g) in enumerate(zip(self.rounds,gates))],
            total_multiplier_gates=sum(gates),gate_counts=dict(sum((Counter(n for n,_ in c.operations) for _,_,c in self.rounds),Counter())),
            oracle='arithmetic',factors_or_order_supplied=False,
            protocol='one control wire reused for every reading; correction from retained readings only; both outcomes followed exactly',
            scope='small exact order-finding demonstration; ideal operations, perfect reset, no noise or hardware claim')


def build_record(modulus=15,base=2,*,precision=3):
    n=_integer(modulus,'modulus',3,255);a=_integer(base,'base',2,n-1)
    m=_integer(precision,'record length',1,MAX_PRECISION)
    if n%2==0 or gcd(a,n)!=1:raise ValueError('choose an odd modulus and a coprime base')
    width=(n-1).bit_length();control=0;work=tuple(range(1,1+width))
    scratch=tuple(range(1+width,1+width+multiplier_workspace(width)));size=1+width+len(scratch)
    order=max(8,1<<m);rounds=[]
    for j in reversed(range(m)):
        circuit=PowerPhaseCircuit(size,order)
        append_multiplier(circuit,control,work,scratch,pow(a,1<<j,n),n)
        if any(name not in PERMUTATIONS for name,_ in circuit.operations):
            raise ValueError('the multiplier must be a permutation circuit')
        rounds.append((j,pow(a,1<<j,n),circuit))
    return RecordProgram(n,a,m,order,control,work,scratch,tuple(rounds))


class _Images:
    """Work-label images under one round's controlled multiplier.

    The circuit is run once for every label it is asked to move, with the
    control wire set; a permutation of labels does not depend on amplitudes,
    so the relabeling is reused on every branch of that round.
    """
    def __init__(self,program,budget):
        self.program=program;self.b=budget;self.tables=[{} for _ in program.rounds]
        self.one=program.field(1);self.mask=1<<program.control

    def move(self,level,psi):
        _,_,circuit=self.program.rounds[level];table=self.tables[level];out={}
        for ket,amplitude in psi.items():
            if ket not in table:
                result=execute(circuit,{ket|self.mask:self.one},self.b)
                if len(result)!=1:raise ArithmeticError('multiplier did not act as a permutation')
                (image,value),=result.items()
                if value!=self.one or not image&self.mask:raise ArithmeticError('multiplier changed the amplitude or the control')
                table[ket]=image^self.mask
                if any((table[ket]>>q)&1 for q in self.program.scratch):raise ArithmeticError('multiplier left workspace dirty')
            out[table[ket]]=amplitude
        return out


def run_record(program,*,max_work=100_000_000,max_coefficient_bits=4096,max_branches=4096):
    """Exact distribution over the m-bit record; raises ResourceLimit on any budget failure."""
    F=program.field;m=program.precision;b=Budget(max_work=max_work,max_coefficient_bits=max_coefficient_bits,max_branches=max_branches)
    b.stats.update(backend='record_phase',preparation_count=1,permutation_visits=0,nodes=0,leaves=0,peak_support=1,pruned_records=0,
        representation=f'unnormalized sparse work-register amplitudes in flat Q(zeta_{program.order}), one branch per record prefix',
        budget_scope='whole record tree including every multiplier execution and leaf readout')
    images=_Images(program,b);one=F(1);half=program.field(1)/2
    distribution={};readings=[0]*m
    def leaf(psi):
        total=F()
        for value in psi.values():
            b.tick('readout_visits');total=b.add(total,b.mul(value.conjugate(),value))
        return total
    def descend(level,psi):
        if not psi:
            # Every completion of this prefix has probability zero exactly.
            tail=m-level;prefix=sum(y<<t for t,y in enumerate(readings[:level]))
            for rest in range(1<<tail):distribution[prefix|(rest<<level)]=F()
            b.stats['pruned_records']+=1<<tail;return
        if level==m:
            b.stats['leaves']+=1;distribution[sum(y<<t for t,y in enumerate(readings))]=leaf(psi);return
        b.stats['nodes']+=1
        moved=images.move(level,psi)
        rho=F.root(program.correction_exponent(level,readings))
        for bit in (0,1):
            child={}
            for ket in psi.keys()|moved.keys():
                value=psi.get(ket);turned=moved.get(ket)
                if turned is not None:
                    turned=b.mul(turned,rho)
                    if bit:turned=-turned
                    value=turned if value is None else b.add(value,turned)
                b.put(child,ket,b.mul(value,half))
            b.stats['peak_support']=max(b.stats['peak_support'],len(child))
            readings[level]=bit;descend(level+1,child)
        readings[level]=0
    descend(0,{1<<program.work[0]:one})
    total=F()
    for value in distribution.values():total=b.add(total,value)
    if total!=one:raise ArithmeticError('record distribution not exactly normalized')
    return distribution,b


def assess_record(program,distribution):
    """Compare every record probability with the independent Fourier law, then decode."""
    F=program.field;m=program.precision
    if set(distribution)!=set(range(1<<m)):raise ValueError('assessment requires the complete record distribution')
    law=exact_phase_law(program.modulus,program.base,m,field='flat')
    for y,value in distribution.items():
        if value!=law[y]:raise AssertionError('record distribution disagrees with the exact Fourier law')
    policies={}
    for doubled in (False,True):
        success=F();readings=[]
        for y in range(1<<m):
            outcome=decode(y,program.modulus,program.base,m,double_denominators=doubled)
            if outcome['status']=='factored':success=success+distribution[y]
            readings.append(dict(outcome,probability=distribution[y].to_dict()))
        policies['convergents_and_doubles' if doubled else 'convergents_only']=dict(
            exact_success_probability=success.to_dict(),readings=readings)
    return dict(status='verified',exact_fourier_law_agrees=True,policies=policies,
        success_interpretation='ideal single-record probability for this fixed base and record length; no hardware shots')


def calculate_record(program,*,decimal_places=12,**limits):
    start=perf_counter()
    report=dict(schema=SCHEMA,status='completed',evidence_class='LOCAL_IDEAL_CALCULATION',hardware_job_id=None,
        program=program.metadata(),program_sha256=_digest(dict(program.metadata(),
            rounds=[[name,list(qs)] for _,_,c in program.rounds for name,qs in c.operations])),
        limits_per_tree=dict(limits))
    try:
        distribution,b=run_record(program,**limits)
        one=program.field(1)
        for value in distribution.values():
            if real_sign(value)<0 or real_sign(one-value)<0:raise ArithmeticError('invalid probability')
        report['record']=dict(bit_order='reading t is bit t of the record; reading 0 is taken first',
            probabilities={format(y,f'0{program.precision}b'):display(v,decimal_places) for y,v in sorted(distribution.items())},
            normalization=one.to_dict())
        report['assessment']=assess_record(program,distribution)
        report['statistics']=dict(b.stats)
    except ResourceLimit as error:
        report.update(status='incomplete',error=str(error),failure_contract='whole record tree discarded; no partial results',
                      statistics=getattr(error,'statistics',{}))
    report['execution_seconds']=perf_counter()-start
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modulus',type=int,default=15);parser.add_argument('--base',type=int,default=2)
    parser.add_argument('--precision',type=int,default=3)
    parser.add_argument('--max-work',type=int,default=100_000_000);parser.add_argument('--max-branches',type=int,default=4096)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    program=build_record(args.modulus,args.base,precision=args.precision)
    report=calculate_record(program,max_work=args.max_work,max_branches=args.max_branches)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(output=str(args.out),status=report['status'],program=report['program']),sort_keys=True))


if __name__=='__main__':main()
