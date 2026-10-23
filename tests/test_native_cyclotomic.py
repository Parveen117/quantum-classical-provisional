import copy
from decimal import Decimal,localcontext
from fractions import Fraction as F
import importlib.util
import random
import unittest

from native_relational_qc.exact import Exact,OMEGA,INV_SQRT2
from native_relational_qc.cyclotomic import Cyclotomic as C,ZERO,ONE,ZETA,BASIS
from native_relational_qc.phase_backend import PhaseCircuit,prepare
from native_relational_qc.calculator import calculate,run_calculation,validate,display,real_sign
from native_relational_qc.compact import ResourceLimit
from native_relational_qc.shor import build,assess,append_inverse_qft,decode,exact_phase_law


def document(c,queries=None):
    return dict(schema='nrqc-calculator-v1',n_qubits=c.n_qubits,backend='cyclotomic',
        operations=[[n,list(q)] for n,q in c.operations],queries=queries or
        [dict(id='p',kind='distribution',qubits=list(reversed(range(c.n_qubits))))])


class CyclotomicTests(unittest.TestCase):
    def test_field_basis_against_independent_polynomial_multiplication(self):
        # An independent Q[z]/(z^8+1) representation, not the pair-field formula.
        def pmul(a,b):
            out=[F(0)]*8
            for i,x in enumerate(a):
                for j,y in enumerate(b):out[(i+j)%8]+=x*y*(1 if i+j<8 else -1)
            return out
        poly=[[F(i==j) for i in range(8)] for j in range(8)]
        def padd(a,b):return [x+y for x,y in zip(a,b)]
        s2=[F(0),0,1,0,0,0,-1,0]
        old_basis=[poly[0],s2,poly[4],pmul(poly[4],s2)]
        new_basis=old_basis+[pmul(poly[1],v) for v in old_basis]
        def coords(v):
            out=[F(0)]*8
            for coefficient,basis in zip(v.coefficients,new_basis):out=padd(out,[coefficient*x for x in basis])
            return out
        objects=[C(Exact(*[int(k==j) for k in range(4)])) for j in range(4)]
        objects += [C(0,v.lo) for v in objects]
        for a in objects:
            for b in objects:self.assertEqual(coords(a*b),pmul(coords(a),coords(b)))
        self.assertEqual(ZETA**2,C(OMEGA));self.assertEqual(ZETA**8,-ONE);self.assertEqual(ZETA**16,ONE)

    def test_inverse_conjugation_exact_embedding_and_serialization(self):
        rng=random.Random(16)
        for _ in range(20):
            a,b=(Exact(*(F(rng.randint(-4,4),rng.randint(1,5)) for _ in range(4))) for _ in range(2))
            v=C(a,b)
            self.assertEqual(v*v.inverse(),ONE)
            self.assertEqual(v.conjugate().conjugate(),v)
            self.assertEqual(v.norm2(),v.norm2().conjugate())
            self.assertEqual(C(a)*C(b),C(a*b))
            self.assertEqual(C.from_dict(v.to_dict()),v)
            self.assertEqual(C.from_dict(a.to_dict()),C(a))
        with self.assertRaises(ZeroDivisionError):ZERO.inverse()
        for v in (0.1,True,complex(1)):
            with self.assertRaises(TypeError):C(v)
        with self.assertRaises(TypeError):ZETA**True
        with self.assertRaises(ValueError):C.from_dict(dict(basis='unknown',coefficients=['0']*8))

    def test_real_bounds_sign_and_severe_cancellation(self):
        cosine=(ZETA+ZETA.conjugate())*F(1,2)
        with localcontext() as ctx:
            ctx.prec=160
            target=(Decimal(2)+Decimal(2).sqrt()).sqrt()/2
            for places in (0,12,60):
                result=display(cosine,places)['decimal_enclosure']
                self.assertLessEqual(Decimal(result['lower']),target)
                self.assertGreaterEqual(Decimal(result['upper']),target)
            scale=10**70;floor=int(target*scale)
            for sign,v in ((1,cosine*scale-C(floor)),(-1,cosine*scale-C(floor+1))):
                self.assertEqual(real_sign(v),sign)
                interval=display(v,60)['decimal_enclosure'];number=target*scale-(floor if sign==1 else floor+1)
                self.assertLessEqual(Decimal(interval['lower']),number)
                self.assertGreaterEqual(Decimal(interval['upper']),number)
        self.assertEqual(real_sign(ZERO),0)
        with self.assertRaises(ValueError):display(ZETA)
        with self.assertRaises(ValueError):real_sign(ZETA)

    def test_new_phase_has_a_new_exact_observable(self):
        c=PhaseCircuit(1).add('h',0).add('p16',0).add('h',0)
        result=calculate(document(c));value=C.from_dict(result['answers'][0]['probabilities']['0']['exact'])
        self.assertEqual(value,(ONE+(ZETA+ZETA.conjugate())*F(1,2))*F(1,2))
        self.assertTrue(value.hi)
        self.assertEqual(result['statistics']['preparation_count'],1)

    def test_phase_gate_full_basis_action_and_inverses(self):
        for name,width,power in (('p16',1,1),('p16dg',1,-1),('cp16',2,1),('cp16dg',2,-1)):
            for x in range(1<<width):
                c=PhaseCircuit(width)
                for q in range(width):
                    if x&(1<<q):c.add('x',q)
                c.add(name,*range(width));s=prepare(c)
                self.assertEqual(s.amplitudes,{x:ZETA**power if x==(1<<width)-1 else ONE})
        c=PhaseCircuit(2).add('h',0).add('h',1).add('cp16',0,1).add('cp16dg',0,1)
        self.assertEqual(prepare(c).amplitudes,{x:C(F(1,2)) for x in range(4)})

    def test_four_bit_qft_complete_matrix_phase_and_clean_scratch(self):
        for x in range(16):
            c=PhaseCircuit(5)
            for q in range(4):
                if x&(1<<q):c.add('x',q)
            append_inverse_qft(c,range(4),clean_ancilla=4)
            s=prepare(c)
            self.assertEqual(set(s.amplitudes),set(range(16)))
            for y in range(16):self.assertEqual(s.amplitudes[y],ZETA**(-x*y)*F(1,4))
            self.assertEqual(s.probability({4:0}),ONE)

    def test_calculator_batch_reuses_preparation_and_pauli_y_order(self):
        c=PhaseCircuit(2).add('h',0).add('s',0).add('x',1)
        queries=[dict(id='d',kind='distribution',qubits=[0,1]),
                 dict(id='p',kind='probability',outcomes={'1':1}),
                 dict(id='y',kind='expectation',paulis={'0':'Y','1':'Z'})]
        r=calculate(document(c,queries));self.assertEqual(r['status'],'completed')
        self.assertEqual(r['statistics']['preparation_count'],1)
        self.assertEqual(C.from_dict(r['answers'][0]['probabilities']['01']['exact']),C(F(1,2)))
        self.assertEqual(C.from_dict(r['answers'][1]['value']['exact']),ONE)
        self.assertEqual(C.from_dict(r['answers'][2]['value']['exact']),-ONE)

    def test_original_frame_agreement_at_three_bits(self):
        p=build(15,2,precision=3)
        reports=[calculate(p.request(b)) for b in ('clifford_frame','cyclotomic')]
        for y,v in reports[0]['answers'][0]['probabilities'].items():
            self.assertEqual(C.from_dict(v['exact']),C.from_dict(reports[1]['answers'][0]['probabilities'][y]['exact']))
        self.assertEqual(assess(p,reports[1])['status'],'verified')

    def test_shor_four_bit_precision_boundary_and_actual_success(self):
        p=build(21,2,precision=4,oracle='table');r=calculate(p.request('cyclotomic'));a=assess(p,r)
        self.assertEqual(a['status'],'verified')
        self.assertEqual(C.from_dict(a['policies']['convergents_only']['exact_success_probability']),ZERO)
        self.assertEqual(C.from_dict(a['policies']['convergents_and_doubles']['exact_success_probability']),C(Exact(F(3,16),F(5,64))))
        self.assertEqual(decode(5,21,2,4,double_denominators=True)['factors'],[3,7])
        with self.assertRaises(ValueError):p.request('clifford_frame')
        with self.assertRaises(ValueError):build(21,2,precision=6,oracle='table')

    def test_resource_rejections_discard_batch_including_completed_prefix(self):
        c=PhaseCircuit(3).add('h',0).add('h',1).add('h',2)
        for limits in ({'max_work':1},{'max_branches':2},{'max_coefficient_bits':2}):
            d=document(c);d['limits']=limits;r=calculate(d)
            self.assertEqual(r['status'],'incomplete');self.assertEqual(r['answers'],[])
            self.assertIn('statistics',r)
        queries=[dict(id='first',kind='expectation',paulis={'0':'X'}),dict(id='second',kind='distribution',qubits=[0,1,2])]
        d=document(c,queries);first=calculate(document(c,queries[:1]))
        d['limits']={'max_work':first['statistics']['work_used']}
        r=calculate(d);self.assertEqual(r['status'],'incomplete');self.assertEqual(r['answers'],[])
        self.assertEqual(run_calculation(document(c),timeout_seconds=1e-9)['status'],'time_limit')

    def test_explicit_gate_backend_and_input_boundaries(self):
        d=document(PhaseCircuit(1).add('p16',0))
        for backend in ('clifford_frame','jya_frame','observer','factored'):
            wrong=copy.deepcopy(d);wrong['backend']=backend
            with self.assertRaises(ValueError):validate(wrong)
        for extra in ({'simplify':'exact'},{'contraction':'integer'},{'n_qubits':257}):
            with self.assertRaises(ValueError):validate(dict(d,**extra))
        with self.assertRaises(ValueError):PhaseCircuit(2).add('cp16',0,0)
        with self.assertRaises(ValueError):PhaseCircuit(2).add('p16',True)
        with self.assertRaises(ValueError):PhaseCircuit(2).add('p32',0)
        with self.assertRaises(ValueError):validate(document(PhaseCircuit(1),[dict(id='g',kind='geometry',generators=[dict(paulis={'0':'Z'})])]))

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional independent Qiskit reference')
    def test_random_complete_states_against_qiskit_without_phase_alignment(self):
        import numpy as np
        from qiskit.quantum_info import Statevector
        from native_relational_qc.compact_qiskit import to_qiskit
        rng=random.Random(1616)
        for n in (2,3,4):
            for _ in range(4):
                c=PhaseCircuit(n)
                for _ in range(24):
                    name=rng.choice(('h','s','tdg','sx','r','p16','p16dg','cx','cp16','cp16dg','swap'))
                    qs=rng.sample(range(n),2 if name in ('cx','cp16','cp16dg','swap') else 1)
                    c.add(name,*qs)
                native=prepare(c).amplitudes;expected=Statevector.from_instruction(to_qiskit(c)).data
                np.testing.assert_allclose([complex(native.get(x,ZERO)) for x in range(1<<n)],expected,atol=2e-12,rtol=0)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional independent Qiskit reference')
    def test_four_bit_shor_full_states_against_direct_fourier_formula(self):
        import numpy as np
        from qiskit.quantum_info import Statevector
        from native_relational_qc.compact_qiskit import to_qiskit
        for n,a,oracle,iqft in ((15,2,'rotation15',True),(15,7,'table',True),
                (21,2,'table',True),(15,14,'table',True),(21,2,'table',False)):
            p=build(n,a,precision=4,oracle=oracle,inverse_qft=iqft);native=prepare(p.circuit).amplitudes
            expected=np.zeros(1<<p.circuit.n_qubits,dtype=complex)
            for x in range(16):
                value=pow(a,x,n)
                if iqft:
                    for y in range(16):expected[y+(value<<4)]+=np.exp(-2j*np.pi*x*y/16)/16
                else:expected[x+(value<<4)]=1/4
            np.testing.assert_allclose([complex(native.get(x,ZERO)) for x in range(len(expected))],expected,atol=3e-12,rtol=0)
            np.testing.assert_allclose(Statevector.from_instruction(to_qiskit(p.circuit)).data,expected,atol=3e-12,rtol=0)


if __name__=='__main__':unittest.main()
