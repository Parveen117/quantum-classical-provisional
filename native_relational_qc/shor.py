"""Small exact Shor order-finding integration on the existing calculator.

No factors or order are supplied to the builder. Precision is deliberately
limited to 1..12 control bits; the sixth requires cyclotomic64 or
cyclotomic_pow2, and seven to twelve require the flat cyclotomic_pow2 field
Q(zeta_2**m). The arithmetic
oracle constructs modular multipliers from reversible additions. The bounded
truth-table and special N=15 rotation oracles remain explicit alternatives.
"""
import argparse
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import json
from math import gcd
from pathlib import Path

from .calculator import run_calculation,_digest
from .compact import _integer
from .exact import Exact,ONE,ZERO,OMEGA
from .large_register import LargeCircuit
from .reversible_logic import BooleanMap,compile_oracle
from .cyclotomic import Cyclotomic,ZETA,ZERO as C0,ONE as C1
from .phase_backend import PhaseCircuit,Phase32Circuit,Phase64Circuit,PowerPhaseCircuit
from .cyclotomic_pow2 import field_of_order

MAX_PRECISION=12
from .cyclotomic32 import Cyclotomic32,ZETA as ZETA32
from .cyclotomic64 import Cyclotomic64,ZETA as ZETA64
from .modular_arithmetic import append_multiplier,multiplier_workspace


def append_ccx(circuit,a,b,target):
    """Exact seven-T Toffoli, including phase on every basis input."""
    if len({a,b,target})!=3:raise ValueError('Toffoli requires three distinct wires')
    for name,qs in (
        ('h',(target,)),('cx',(b,target)),('tdg',(target,)),('cx',(a,target)),
        ('t',(target,)),('cx',(b,target)),('tdg',(target,)),('cx',(a,target)),
        ('t',(b,)),('t',(target,)),('h',(target,)),('cx',(a,b)),
        ('t',(a,)),('tdg',(b,)),('cx',(a,b))):
        circuit.add(name,*qs)


def append_controlled_swap(circuit,control,a,b):
    if len({control,a,b})!=3:raise ValueError('controlled swap requires distinct wires')
    circuit.add('cx',b,a)
    append_ccx(circuit,control,a,b)
    circuit.add('cx',b,a)


def append_inverse_phase(circuit,a,b,distance,*,clean_ancilla=None):
    """diag(1,1,1,exp(-i*pi/2**distance)); distance 1..5.

    The distance-two construction requires a distinct ancilla initially zero
    and restores it. It is not a dirty-ancilla controlled-T identity.
    """
    if a==b:raise ValueError('controlled phase requires distinct wires')
    if isinstance(circuit,PowerPhaseCircuit):
        # Flat field: one native controlled phase exp(-i*pi/2**distance); no ancilla.
        _integer(distance,'phase distance',1,MAX_PRECISION-1)
        if 2<<distance>circuit.order:raise ValueError('phase distance exceeds the declared field order')
        circuit.add(f'cp{2<<distance}dg',a,b)
        return
    _integer(distance,'phase distance',1,5)
    if distance==5:
        if not isinstance(circuit,Phase64Circuit):raise ValueError('distance-five phase needs Phase64Circuit')
        circuit.add('cp64dg',a,b)
        return
    if distance==4:
        if not isinstance(circuit,Phase32Circuit):raise ValueError('distance-four phase needs Phase32Circuit')
        circuit.add('cp32dg',a,b)
        return
    if distance==3:
        if not isinstance(circuit,PhaseCircuit):raise ValueError('distance-three phase needs PhaseCircuit and cyclotomic execution')
        circuit.add('cp16dg',a,b)
        return
    if distance==1:
        circuit.add('tdg',a).add('tdg',b).add('cx',a,b).add('t',b).add('cx',a,b)
    else:
        if clean_ancilla is None or clean_ancilla in (a,b):
            raise ValueError('controlled T-dagger requires a distinct clean ancilla')
        append_ccx(circuit,a,b,clean_ancilla)
        circuit.add('tdg',clean_ancilla)
        append_ccx(circuit,a,b,clean_ancilla)


def append_inverse_qft(circuit,controls,*,clean_ancilla=None):
    controls=tuple(controls)
    if isinstance(circuit,PowerPhaseCircuit):
        _integer(len(controls),'exact QFT width',1,MAX_PRECISION)
        if len(set(controls))!=len(controls):raise ValueError('QFT wires must be distinct')
        for q in range(len(controls)//2):circuit.add('swap',controls[q],controls[-q-1])
        for j in range(len(controls)):
            for k in range(j):append_inverse_phase(circuit,controls[j],controls[k],j-k)
            circuit.add('h',controls[j])
        return
    _integer(len(controls),'exact QFT width',1,6)
    if len(controls)==6 and not isinstance(circuit,Phase64Circuit):
        raise ValueError('six-bit exact QFT requires Phase64Circuit')
    if len(controls)>=5 and not isinstance(circuit,Phase32Circuit):
        raise ValueError('five-bit exact QFT requires Phase32Circuit')
    if len(controls)>=4 and not isinstance(circuit,PhaseCircuit):
        raise ValueError('four-bit exact QFT requires PhaseCircuit')
    if len(set(controls))!=len(controls):raise ValueError('QFT wires must be distinct')
    if len(controls)>=3 and (clean_ancilla is None or clean_ancilla in controls):
        raise ValueError('three-to-six-bit exact QFT needs a clean ancilla')
    for q in range(len(controls)//2):circuit.add('swap',controls[q],controls[-q-1])
    for j in range(len(controls)):
        for k in range(j):
            append_inverse_phase(circuit,controls[j],controls[k],j-k,clean_ancilla=clean_ancilla)
        circuit.add('h',controls[j])


def append_mod15_multiplier(circuit,control,work,multiplier):
    """Controlled M_b on all 16 work labels, with 0 and 15 fixed.

    For b in {1,2,4,8}, multiplication modulo 15 is a cyclic bit rotation.
    Which b is used comes from modular repeated squaring, never a known order.
    """
    work=tuple(work)
    if len(work)!=4 or len(set((control,*work)))!=5:
        raise ValueError('mod-15 rotation needs four distinct work wires and a control')
    if multiplier==1:return
    if multiplier==2:pairs=((3,2),(2,1),(1,0))
    elif multiplier==4:pairs=((0,2),(1,3))
    elif multiplier==8:pairs=((0,1),(1,2),(2,3))
    else:raise ValueError('rotation multiplier must be 1,2,4 or 8')
    for a,b in pairs:append_controlled_swap(circuit,control,work[a],work[b])


@dataclass(frozen=True)
class ShorProgram:
    circuit: LargeCircuit
    modulus: int
    base: int
    precision: int
    controls: tuple
    work: tuple
    scratch: tuple
    oracle: str
    inverse_qft: bool
    oracle_gates: int
    rewrite: str='none'
    rewrite_certificate: dict | None=None
    rewrite_statistics: dict | None=None

    def metadata(self):
        return dict(modulus=self.modulus,base=self.base,precision_bits=self.precision,
            n_qubits=self.circuit.n_qubits,controls_lsb_first=list(self.controls),
            work_lsb_first=list(self.work),scratch=list(self.scratch),
            scratch_precondition='all zero',scratch_postcondition='all zero',
            oracle=self.oracle,inverse_qft=self.inverse_qft,
            oracle_lowered_gates=self.oracle_gates,total_gates=len(self.circuit.operations),
            oracle_count_scope='before optional whole-circuit rewrite',rewrite=self.rewrite,
            rewrite_statistics=self.rewrite_statistics,
            gate_counts=dict(Counter(name for name,_ in self.circuit.operations)),
            factors_or_order_supplied=False,
            scope='small exact order-finding demonstration; low precision has no general Shor success guarantee',
            oracle_scaling='O(m*n^4) elementary gates, O(n) workspace; polynomial construction, bounded simulator' if self.oracle=='arithmetic' else
                           'bounded exponential truth table' if self.oracle=='table' else
                           'special N=15 controlled cyclic bit rotations on the full work register')

    def request(self,backend='jya_frame'):
        if backend not in ('clifford_frame','jya_frame','clifford_t','cyclotomic','cyclotomic32','cyclotomic64','cyclotomic_pow2'):
            raise ValueError('unsupported Shor backend')
        if isinstance(self.circuit,PowerPhaseCircuit) and backend!='cyclotomic_pow2':
            raise ValueError('a flat-field program requires the cyclotomic_pow2 backend')
        if backend=='cyclotomic_pow2':
            return dict(schema='nrqc-calculator-v1',n_qubits=self.circuit.n_qubits,backend=backend,
                operations=[[name,list(qs)] for name,qs in self.circuit.operations],
                queries=[dict(id='phase',kind='distribution',qubits=list(reversed(self.controls)))])
        if self.precision==6 and backend!='cyclotomic64':
            raise ValueError('six phase bits require explicit cyclotomic64 backend')
        if self.precision==5 and backend not in ('cyclotomic32','cyclotomic64'):
            raise ValueError('five phase bits require explicit cyclotomic32 or cyclotomic64 backend')
        if self.precision==4 and backend not in ('cyclotomic','cyclotomic32','cyclotomic64'):
            raise ValueError('four phase bits require explicit cyclotomic backend')
        if self.oracle=='arithmetic' and backend not in ('cyclotomic','cyclotomic32','cyclotomic64','cyclotomic_pow2'):
            raise ValueError('arithmetic oracle requires an explicit backend supporting native CCX')
        return dict(schema='nrqc-calculator-v1',n_qubits=self.circuit.n_qubits,backend=backend,
            operations=[[name,list(qs)] for name,qs in self.circuit.operations],
            queries=[dict(id='phase',kind='distribution',qubits=list(reversed(self.controls)))])


def build(modulus=15,base=2,*,precision=3,oracle='rotation15',inverse_qft=True,rewrite='none',field='nested'):
    """field='nested' keeps the earlier 1..6-bit circuits unchanged; field='flat'
    builds for cyclotomic_pow2 with native controlled phases, 1..12 bits."""
    n=_integer(modulus,'modulus',3,255);a=_integer(base,'base',2,n-1)
    if field not in ('nested','flat'):raise ValueError('field must be nested or flat')
    m=_integer(precision,'exact phase-estimation width',1,MAX_PRECISION if field=='flat' else 6)
    if n%2==0 or gcd(a,n)!=1:raise ValueError('choose an odd modulus and a coprime base')
    if type(inverse_qft) is not bool:raise ValueError('inverse_qft must be boolean')
    if oracle not in ('table','rotation15','arithmetic'):raise ValueError('unknown modular oracle')
    if rewrite not in ('none','panini'):raise ValueError('rewrite must be none or panini')
    width=(n-1).bit_length();controls=tuple(range(m));work=tuple(range(m,m+width))
    logic=None
    if oracle=='table':
        # This is bounded function synthesis from N,a,x; no period or factors.
        logic=compile_oracle(BooleanMap(m,width,tuple(pow(a,x,n) for x in range(1<<m))))
        size=logic.circuit.n_qubits
    elif oracle=='arithmetic':
        size=m+width+multiplier_workspace(width)
    else:
        if n!=15 or a not in (2,4,8):raise ValueError('rotation15 supports N=15 and bases 2,4,8')
        size=m+width
    if field=='nested' and inverse_qft and m>=3 and size==m+width:size+=1
    scratch=tuple(range(m+width,size))
    if field=='flat':circuit=PowerPhaseCircuit(size,max(8,1<<m))
    else:circuit=(Phase64Circuit if m==6 else Phase32Circuit if m==5 else PhaseCircuit if m==4 or oracle=='arithmetic' else LargeCircuit)(size)
    for q in controls:circuit.add('h',q)
    start=len(circuit.operations)
    if logic is not None:
        for name,qs in logic.circuit.operations:
            if name=='ccx':append_ccx(circuit,*qs)
            else:circuit.add(name,*qs)
    else:
        circuit.add('x',work[0])
        for q,control in enumerate(controls):
            if oracle=='arithmetic':append_multiplier(circuit,control,work,scratch,pow(a,1<<q,n),n)
            else:append_mod15_multiplier(circuit,control,work,pow(a,1<<q,n))
    oracle_gates=len(circuit.operations)-start
    if inverse_qft:append_inverse_qft(circuit,controls,clean_ancilla=scratch[0] if scratch else None)
    certificate=statistics=None
    if rewrite=='panini':
        from .modular_rewrite import rewrite_circuit,verify_rewrite
        # Flat circuits may exceed 100000 gates; the search and proof budgets scale with them.
        budgets=dict(max_checks=10_000_000) if field=='flat' else {}
        reduced=rewrite_circuit(circuit,**budgets)
        verify_rewrite(circuit,reduced.circuit,reduced.certificate,**(dict(max_crossings=10_000_000) if field=='flat' else {}))
        circuit,certificate,statistics=reduced.circuit,reduced.certificate,reduced.statistics
    return ShorProgram(circuit,n,a,m,controls,work,scratch,oracle,inverse_qft,oracle_gates,
                       rewrite,certificate,statistics)


def exact_phase_law(modulus,base,precision,*,inverse_qft=True,field='nested'):
    """Independent finite Fourier sum; uses f(x)=a**x mod N, no order input.

    field='flat' returns values in Q(zeta_max(8,2**m)). It groups x by the
    value f(x) and counts, for every difference d, the pairs (u,v) with
    f(u)=f(v) and v-u=d mod size; then P(y)=sum_d pairs(d) zeta**(y*d)/size**2,
    the same double sum over equal-value pairs used for the nested fields.
    """
    if field=='flat':
        import numpy as np
        m=_integer(precision,'exact Fourier width',1,MAX_PRECISION);size=1<<m
        F=field_of_order(max(8,size));step=F.ORDER//size;n=F.N
        if not inverse_qft:return {y:F(Fraction(1,size)) for y in range(size)}
        classes={}
        for x in range(size):classes.setdefault(pow(base,x,modulus),[]).append(x)
        pairs=np.zeros(size,dtype=np.int64)
        for xs in classes.values():
            xs=np.array(xs,dtype=np.int64)
            pairs+=np.bincount(((xs[None,:]-xs[:,None])%size).ravel(),minlength=size)
        d=np.arange(size,dtype=np.int64);law={}
        for y in range(size):
            e=((y*d)%size)*step;wrap=e>=n
            # pair counts total at most size**2 < 2**53, so float64 weights stay exact.
            weights=np.bincount(np.where(wrap,e-n,e),weights=np.where(wrap,-pairs,pairs),minlength=n)
            law[y]=F._build(np.rint(weights).astype(np.int64),size*size)
        return law
    _integer(precision,'exact Fourier width',1,6)
    size=1<<precision
    field,zero,root=(Cyclotomic64,Cyclotomic64(),ZETA64) if precision==6 else (Cyclotomic32,Cyclotomic32(),ZETA32) if precision==5 else (Cyclotomic,C0,ZETA) if precision==4 else (Exact,ZERO,OMEGA**(8//size))
    if not inverse_qft:return {y:field(Fraction(1,size)) for y in range(size)}
    table=[pow(base,x,modulus) for x in range(size)];powers=[root**k for k in range(size)]
    return {y:sum((powers[(y*(v-u))%size] for u in range(size) for v in range(size)
                   if table[u]==table[v]),zero)*field(Fraction(1,size*size)) for y in range(size)}


def convergents(numerator,denominator):
    p0,p1,q0,q1=0,1,1,0
    while denominator:
        quotient,remainder=divmod(numerator,denominator)
        p0,p1=p1,quotient*p1+p0;q0,q1=q1,quotient*q1+q0
        yield p1,q1
        numerator,denominator=denominator,remainder


def decode(reading,modulus,base,precision,*,double_denominators=False):
    """Test only continued-fraction denominators (optionally also twice each).

    Every candidate is checked by modular exponentiation before a gcd step.
    No search over all orders, factor hints, or replacement by the true order.
    A verified period multiple can still yield only trivial gcds and fail.
    """
    n=_integer(modulus,'modulus',3,255);a=_integer(base,'base',2,n-1)
    m=_integer(precision,'precision',1,MAX_PRECISION);y=_integer(reading,'phase reading',0,(1<<m)-1)
    if gcd(a,n)!=1:raise ValueError('postprocessing requires a coprime base')
    if type(double_denominators) is not bool:raise ValueError('double_denominators must be boolean')
    if y==0:return dict(reading=y,status='no_information',attempts=[],factors=None)
    attempts=[];seen=set()
    for numerator,denominator in convergents(y,1<<m):
        if not numerator:continue
        for multiplier in (1,2) if double_denominators else (1,):
            r=multiplier*denominator
            if r in seen or r>=n:continue
            seen.add(r);verified=pow(a,r,n)==1
            record=dict(denominator=denominator,multiplier=multiplier,candidate_period=r,period_verified=verified)
            attempts.append(record)
            if not verified or r%2:continue
            half=pow(a,r//2,n);g1,g2=gcd(half-1,n),gcd(half+1,n)
            record.update(half_power=half,gcd_minus=g1,gcd_plus=g2)
            for divisor in (g1,g2):
                if 1<divisor<n:
                    factors=sorted((divisor,n//divisor))
                    return dict(reading=y,status='factored',attempts=attempts,factors=factors)
    return dict(reading=y,status='no_nontrivial_factor',attempts=attempts,factors=None)


def assess(program,report):
    """Read actual completed calculator probabilities, then apply postprocessing."""
    if report['status']!='completed':return dict(status='unavailable',reason=report['status'])
    expected_digest=_digest(dict(n_qubits=program.circuit.n_qubits,
        operations=[[name,list(qs)] for name,qs in program.circuit.operations]))
    if report.get('circuit_sha256')!=expected_digest:raise ValueError('assessment circuit mismatch')
    if (len(report['answers'])!=1 or report['answers'][0]['id']!='phase' or
        report['answers'][0].get('bitstring_qubits_left_to_right')!=list(reversed(program.controls))):
        raise ValueError('assessment readout mismatch')
    probabilities=report['answers'][0]['probabilities']
    if set(probabilities)!={format(y,f'0{program.precision}b') for y in range(1<<program.precision)}:
        raise ValueError('assessment requires the complete phase distribution')
    flat=report.get('backend')=='cyclotomic_pow2'
    reference=exact_phase_law(program.modulus,program.base,program.precision,inverse_qft=program.inverse_qft,
                              field='flat' if flat else 'nested')
    policies={}
    for doubled in (False,True):
        backend=report.get('backend')
        program.request(backend)  # Reject an undeclared or insufficient field.
        field=field_of_order(max(8,1<<program.precision)) if flat else {'cyclotomic':Cyclotomic,'cyclotomic32':Cyclotomic32,'cyclotomic64':Cyclotomic64}.get(backend,Exact)
        success=field();readings=[]
        for label,probability in probabilities.items():
            y=int(label,2)
            if field is Exact:
                parsed=Cyclotomic.from_dict(probability['exact'])
                if parsed.hi:raise ValueError('original backend returned an extended-field result')
                value=parsed.lo
            else:value=field.from_dict(probability['exact'])
            if value!=field.coerce(reference[y]):raise AssertionError('calculator disagrees with exact Fourier law')
            outcome=decode(y,program.modulus,program.base,program.precision,double_denominators=doubled)
            if outcome['status']=='factored':success+=value
            readings.append(dict(outcome,probability=value.to_dict()))
        policies['convergents_and_doubles' if doubled else 'convergents_only']=dict(
            exact_success_probability=success.to_dict(),readings=readings)
    return dict(status='verified',exact_fourier_law_agrees=True,policies=policies,
                success_interpretation='ideal single-readout probability for this fixed base and low-precision circuit; no hardware shots')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modulus',type=int,default=15);parser.add_argument('--base',type=int,default=2)
    parser.add_argument('--precision',type=int,default=3)
    parser.add_argument('--oracle',choices=('rotation15','table','arithmetic'),default='rotation15')
    parser.add_argument('--backend',choices=('clifford_frame','jya_frame','clifford_t','cyclotomic','cyclotomic32','cyclotomic64','cyclotomic_pow2'),default='jya_frame')
    parser.add_argument('--field',choices=('nested','flat'),default='nested')
    parser.add_argument('--rewrite',choices=('none','panini'),default='none')
    parser.add_argument('--timeout',type=float,default=20)
    parser.add_argument('--example',action='store_true');parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();program=build(args.modulus,args.base,precision=args.precision,oracle=args.oracle,rewrite=args.rewrite,field=args.field)
    if args.example:result=program.request(args.backend)
    else:
        report=run_calculation(program.request(args.backend),timeout_seconds=args.timeout)
        result=dict(program=program.metadata(),calculation=report,assessment=assess(program,report),
                    rewrite_certificate=program.rewrite_certificate)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(output=str(args.out),program=program.metadata(),status='example' if args.example else result['calculation']['status']),sort_keys=True))


if __name__=='__main__':main()
