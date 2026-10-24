import copy
from decimal import Decimal,localcontext
from fractions import Fraction as F
import importlib.util
import itertools
import random
import unittest
from unittest.mock import patch

from native_relational_qc.exact import Exact
from native_relational_qc.cyclotomic import Cyclotomic
from native_relational_qc.cyclotomic32 import Cyclotomic32
from native_relational_qc.cyclotomic64 import Cyclotomic64 as C,ZETA,ZERO,ONE,BASIS
from native_relational_qc.phase_backend import PhaseCircuit,Phase32Circuit,Phase64Circuit,prepare
from native_relational_qc.calculator import calculate,validate,run_calculation,display
from native_relational_qc.compact import ResourceLimit
from native_relational_qc.shor import build,assess,decode,exact_phase_law,append_inverse_qft
from native_relational_qc.modular_rewrite import rewrite_circuit,verify_rewrite


def request(c,queries=None):
    return dict(schema='nrqc-calculator-v1',n_qubits=c.n_qubits,backend=c.backend,
        operations=[[n,list(q)] for n,q in c.operations],queries=queries or
        [dict(id='d',kind='distribution',qubits=list(reversed(range(min(c.n_qubits,6)))))])


def basis_run(ops,bits):
    for name,qs in ops:
        if name not in ('x','cx','ccx'):raise AssertionError('not a permutation')
        if all((bits>>q)&1 for q in qs[:-1]):bits^=1<<qs[-1]
    return bits


class Phase64RewriteTests(unittest.TestCase):
    def test_all_1024_basis_products_in_independent_polynomial_ring(self):
        def mul(a,b):
            out={}
            for i,x in a.items():
                for j,y in b.items():out[(i+j)%32]=out.get((i+j)%32,F(0))+x*y*(1 if i+j<32 else -1)
            return {k:v for k,v in out.items() if v}
        old=[{0:F(1)},{8:F(1),24:F(-1)},{16:F(1)},{24:F(1),8:F(1)}]
        for power in (4,2,1):old=old+[mul({power:F(1)},v) for v in old]
        values=[C.from_dict(dict(basis=BASIS,coefficients=[str(int(i==j)) for i in range(32)])) for j in range(32)]
        def coords(value):
            out={}
            for coeff,base in zip(value.coefficients,old):
                if coeff:
                    for k,v in base.items():out[k]=out.get(k,F(0))+coeff*v
            return {k:v for k,v in out.items() if v}
        for i,a in enumerate(values):
            for j,b in enumerate(values):self.assertEqual(coords(a*b),mul(old[i],old[j]))
        self.assertEqual(ZETA**64,ONE);self.assertEqual(ZETA**32,-ONE)

    def test_field_inverse_embedding_conjugation_and_strict_serialization(self):
        rng=random.Random(64)
        for _ in range(4):
            v=C.from_dict(dict(basis=BASIS,coefficients=[str(F(rng.randint(-2,2),rng.randint(1,4))) for _ in range(32)]))
            self.assertEqual(v*v.inverse(),ONE)
            self.assertEqual(v.conjugate().conjugate(),v)
            self.assertEqual(v.norm2(),v.norm2().conjugate())
            self.assertEqual(C.from_dict(v.to_dict()),v)
        for v in (Exact(1,2,3,4),Cyclotomic(1,2),Cyclotomic32(1,2)):
            self.assertEqual(C.from_dict(v.to_dict()),C(v))
        for v in (True,0.5,1j):
            with self.assertRaises(TypeError):C(v)
        with self.assertRaises(ZeroDivisionError):ZERO.inverse()
        for d in (dict(basis='unknown',coefficients=['0']*32),dict(basis=BASIS,coefficients=['0']*16),dict(basis=BASIS,coefficients=[0]*32)):
            with self.assertRaises(ValueError):C.from_dict(d)

    def test_rational_enclosures_and_severe_cancellation(self):
        cosine=(ZETA+ZETA.conjugate())*F(1,2)
        with localcontext() as ctx:
            ctx.prec=180;number=Decimal(2).sqrt()/2
            for _ in range(3):number=((1+number)/2).sqrt()
            for places in (0,12,60):
                bounds=display(cosine,places)['decimal_enclosure']
                self.assertLessEqual(Decimal(bounds['lower']),number)
                self.assertGreaterEqual(Decimal(bounds['upper']),number)
            floor=int(number*10**70)
            for offset,sign in ((floor,1),(floor+1,-1)):
                v=cosine*10**70-offset;self.assertEqual(v.real_sign(),sign)
                bounds=display(v,60)['decimal_enclosure'];expected=number*10**70-offset
                self.assertLessEqual(Decimal(bounds['lower']),expected)
                self.assertGreaterEqual(Decimal(bounds['upper']),expected)
        with self.assertRaises(ValueError):ZETA.real_sign()

    def test_new_gate_complete_actions_and_interference(self):
        for name,width,power in (('p64',1,1),('p64dg',1,-1),('cp64',2,1),('cp64dg',2,-1)):
            for x in range(1<<width):
                c=Phase64Circuit(width)
                for q in range(width):
                    if (x>>q)&1:c.add('x',q)
                c.add(name,*range(width))
                self.assertEqual(prepare(c).amplitudes,{x:ZETA**power if x==(1<<width)-1 else ONE})
        c=Phase64Circuit(1).add('h',0).add('p64',0).add('h',0)
        value=C.from_dict(calculate(request(c))['answers'][0]['probabilities']['0']['exact'])
        self.assertEqual(value,(ONE+(ZETA+ZETA.conjugate())*F(1,2))*F(1,2));self.assertTrue(value.hi)

    def test_complete_4096_entry_six_bit_inverse_qft_and_clean_scratch(self):
        roots=[ZETA**k for k in range(64)]
        for x in range(64):
            c=Phase64Circuit(7)
            for q in range(6):
                if (x>>q)&1:c.add('x',q)
            append_inverse_qft(c,range(6),clean_ancilla=6)
            self.assertEqual(prepare(c).amplitudes,{y:roots[(-x*y)%64]*F(1,8) for y in range(64)})

    def test_six_bit_arithmetic_full_state_and_clean_scratch(self):
        for iqft in (True,False):
            p=build(21,2,precision=6,oracle='arithmetic',inverse_qft=iqft,rewrite='panini')
            expected={};roots=[ZETA**k for k in range(64)]
            for x in range(64):
                for y in (range(64) if iqft else (x,)):
                    key=y+(pow(2,x,21)<<6)
                    value=roots[(-x*y)%64]*F(1,64) if iqft else C(F(1,8))
                    expected[key]=expected.get(key,ZERO)+value
            state=prepare(p.circuit)
            self.assertEqual(state.amplitudes,{k:v for k,v in expected.items() if v})
            self.assertEqual(state.probability(dict.fromkeys(p.scratch,0)),ONE)

    def test_141_boundary_and_verified_factor_witness(self):
        self.assertEqual(set(exact_phase_law(141,2,5).values()),{Cyclotomic32(F(1,32))})
        for doubled in (False,True):
            self.assertFalse(any(decode(y,141,2,5,double_denominators=doubled)['factors'] for y in range(32)))
        successful=[y for y in range(64) if decode(y,141,2,6,double_denominators=True)['factors']]
        self.assertEqual(successful,[25,39])
        for y in successful:
            d=decode(y,141,2,6,double_denominators=True);self.assertEqual(d['factors'],[3,47])
            last=d['attempts'][-1];self.assertEqual(last['candidate_period'],46)
            self.assertEqual(last['half_power'],95);self.assertTrue(last['period_verified'])
        self.assertFalse(any(decode(y,141,5,6,double_denominators=True)['factors'] for y in range(64)))

    def test_older_fields_embed_and_backend_contracts_remain_explicit(self):
        p=build(15,2,precision=3)
        reports=[calculate(p.request(b)) for b in ('cyclotomic','cyclotomic32','cyclotomic64')]
        values=[{k:C.from_dict(v['exact']) for k,v in r['answers'][0]['probabilities'].items()} for r in reports]
        self.assertTrue(all(v==values[0] for v in values))
        for r in reports:self.assertEqual(assess(p,r)['status'],'verified')
        for cls in (PhaseCircuit,Phase32Circuit):
            with self.assertRaises(ValueError):cls(1).add('p64',0)
        for b in ('cyclotomic','cyclotomic32'):
            with self.assertRaises(ValueError):build(141,2,precision=6,oracle='arithmetic').request(b)
        with self.assertRaises(ValueError):build(141,2,precision=7,oracle='arithmetic')
        with self.assertRaises(ValueError):build(141,2,oracle='arithmetic',rewrite='guess')

    def test_resource_guards_discard_all_results(self):
        c=Phase64Circuit(3).add('h',0).add('h',1).add('h',2)
        for limits in ({'max_work':1},{'max_branches':2},{'max_coefficient_bits':2}):
            r=calculate(dict(request(c),limits=limits));self.assertEqual(r['status'],'incomplete');self.assertEqual(r['answers'],[])
        self.assertEqual(run_calculation(request(c),timeout_seconds=1e-9)['status'],'time_limit')
        queries=[dict(id='first',kind='probability',outcomes={'0':0}),dict(id='later',kind='expectation',paulis={'0':'Y'})]
        limit=calculate(request(c,queries[:1]))['statistics']['work_used']
        r=calculate(dict(request(c,queries),limits={'max_work':limit}));self.assertEqual(r['answers'],[])

    def test_rewrite_crossing_and_barrier_negative_controls(self):
        c=Phase64Circuit(3).add('cx',0,1).add('cx',0,2).add('cx',0,1)
        r=rewrite_circuit(c);self.assertEqual(r.circuit.operations,(('cx',(0,2)),))
        self.assertEqual(r.certificate['steps'],[dict(left=0,right=2,crossed=[1])])
        with patch('native_relational_qc.modular_rewrite.rewrite_circuit',side_effect=AssertionError('search called')):
            self.assertEqual(verify_rewrite(c,r.circuit,r.certificate)['status'],'verified')
        for middle,qs in (('cx',(1,2)),('p64',(1,)),('h',(2,))):
            c=Phase64Circuit(3).add('cx',0,1).add(middle,*qs).add('cx',0,1)
            self.assertEqual(rewrite_circuit(c).circuit.operations,c.operations)
        c=Phase64Circuit(2).add('x',0).add('x',1).add('x',0)
        self.assertEqual(rewrite_circuit(c,lookback=1).circuit.operations,c.operations)
        with self.assertRaises(ResourceLimit):rewrite_circuit(c,max_checks=1)

    def test_all_small_permutation_gate_pair_relations_on_every_input(self):
        # Exhaustively test both shared-control and target/control dependencies,
        # including dirty auxiliary wires. No state or clean-ancilla assumptions.
        gates=[(name,qs) for name,width in (('x',1),('cx',2),('ccx',3)) for qs in itertools.permutations(range(3),width)]
        for a,b in itertools.product(gates,repeat=2):
            c=Phase64Circuit(3)
            for name,qs in (a,b,a):c.add(name,*qs)
            r=rewrite_circuit(c);verify_rewrite(c,r.circuit,r.certificate)
            for x in range(8):self.assertEqual(basis_run(c.operations,x),basis_run(r.circuit.operations,x))

    def test_certificate_tampering_rejected(self):
        c=Phase64Circuit(3).add('x',0).add('x',1).add('x',0)
        r=rewrite_circuit(c)
        bads=[]
        for key,value in (('left',1),('right',1),('crossed',[]),('left',False)):
            bad=copy.deepcopy(r.certificate);bad['steps'][0][key]=value;bads.append(bad)
        bad=copy.deepcopy(r.certificate);bad['steps']=[];bads.append(bad)
        bad=copy.deepcopy(r.certificate);bad['source_sha256']='0'*64;bads.append(bad)
        for bad in bads:
            with self.assertRaises(ValueError):verify_rewrite(c,r.circuit,bad)
        with self.assertRaises(ResourceLimit):verify_rewrite(c,r.circuit,r.certificate,max_crossings=0)
        with self.assertRaises(ValueError):verify_rewrite(c,Phase64Circuit(3),r.certificate)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional independent Qiskit reference')
    def test_random_complex_states_and_rewrites_without_phase_alignment(self):
        import numpy as np
        from qiskit.quantum_info import Statevector
        from native_relational_qc.compact_qiskit import to_qiskit
        rng=random.Random(6464)
        for _ in range(12):
            c=Phase64Circuit(4)
            for _ in range(25):
                name=rng.choice(('h','r','s','p16','p32dg','p64','p64dg','cp64','cp64dg','cx','ccx','swap'))
                width=3 if name=='ccx' else 2 if name in ('cp64','cp64dg','cx','swap') else 1
                qs=rng.sample(range(4),width);c.add(name,*qs)
                if name in ('cx','ccx'):c.add('x',next(q for q in range(4) if q not in qs)).add(name,*qs)
            r=rewrite_circuit(c);verify_rewrite(c,r.circuit,r.certificate)
            state=prepare(r.circuit).amplitudes;reference=Statevector.from_instruction(to_qiskit(c)).data
            np.testing.assert_allclose([complex(state.get(k,ZERO)) for k in range(16)],reference,atol=5e-12,rtol=0)


if __name__=='__main__':unittest.main()
