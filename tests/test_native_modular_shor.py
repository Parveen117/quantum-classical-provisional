import copy
from decimal import Decimal,localcontext
from fractions import Fraction as F
from math import gcd
import importlib.util
import random
import unittest
from unittest.mock import patch

from native_relational_qc.exact import Exact,INV_SQRT2
from native_relational_qc.cyclotomic import Cyclotomic as C16,BASIS as B16
from native_relational_qc.cyclotomic32 import Cyclotomic32 as C,ZERO,ONE,ZETA,BASIS
from native_relational_qc.phase_backend import PhaseCircuit,Phase32Circuit,prepare
from native_relational_qc.modular_arithmetic import multiplier_operations,multiplier_workspace,_modadd
from native_relational_qc.shor import build,assess,append_inverse_qft,decode,exact_phase_law
from native_relational_qc.calculator import calculate,run_calculation,validate,display
from native_relational_qc.compact import ResourceLimit


def basis_run(ops,bits):
    # Independent classical interpreter for the emitted elementary permutation.
    for name,qs in ops:
        if name not in ('x','cx','ccx'):raise AssertionError('non-permutation primitive')
        if all((bits>>q)&1 for q in qs[:-1]):bits^=1<<qs[-1]
    return bits


def request(c,queries=None):
    return dict(schema='nrqc-calculator-v1',n_qubits=c.n_qubits,backend=c.backend,
        operations=[[name,list(qs)] for name,qs in c.operations],queries=queries or
        [dict(id='d',kind='distribution',qubits=list(reversed(range(min(4,c.n_qubits)))))])


class ModularShorTests(unittest.TestCase):
    def test_all_256_field_basis_products_in_independent_polynomial_ring(self):
        def mul(a,b):
            out=[F(0)]*16
            for i,x in enumerate(a):
                for j,y in enumerate(b):out[(i+j)%16]+=x*y*(1 if i+j<16 else -1)
            return out
        def monomial(k):return [F(i==k) for i in range(16)]
        rt=[F(0)]*16;rt[4]=1;rt[12]=-1
        old=[monomial(0),rt,monomial(8),mul(monomial(8),rt)]
        eight=old+[mul(monomial(2),p) for p in old]
        basis=eight+[mul(monomial(1),p) for p in eight]
        values=[]
        for j in range(16):values.append(C.from_dict(dict(basis=BASIS,coefficients=[str(int(i==j)) for i in range(16)])))
        def coords(v):return [sum(c*p[i] for c,p in zip(v.coefficients,basis)) for i in range(16)]
        for a in values:
            for b in values:self.assertEqual(coords(a*b),mul(coords(a),coords(b)))
        self.assertEqual(ZETA**32,ONE);self.assertEqual(ZETA**16,-ONE)
        self.assertEqual((ZETA**2).hi,C16())

    def test_field_inverse_conjugation_embedding_and_serialization(self):
        rng=random.Random(32)
        for _ in range(8):
            v=C.from_dict(dict(basis=BASIS,coefficients=[str(F(rng.randint(-3,3),rng.randint(1,4))) for _ in range(16)]))
            self.assertEqual(v*v.inverse(),ONE)
            self.assertEqual(v.conjugate().conjugate(),v)
            self.assertEqual(v.norm2(),v.norm2().conjugate())
            self.assertEqual(C.from_dict(v.to_dict()),v)
        for v in (Exact(2,3,4,5),C16(Exact(2,3),Exact(4,5))):
            self.assertEqual(C.from_dict(v.to_dict()),C(v))
        for v in (True,0.125,1j):
            with self.assertRaises(TypeError):C(v)
        with self.assertRaises(ZeroDivisionError):ZERO.inverse()
        for d in (dict(basis='unknown',coefficients=['0']*16),dict(basis=BASIS,coefficients=['0']*8),dict(basis=BASIS,coefficients=[0]*16)):
            with self.assertRaises(ValueError):C.from_dict(d)

    def test_certified_nested_radical_bounds_and_severe_cancellation(self):
        cosine=(ZETA+ZETA.conjugate())*F(1,2)
        with localcontext() as ctx:
            ctx.prec=180
            number=((1+(Decimal(2)+Decimal(2).sqrt()).sqrt()/2)/2).sqrt()
            for places in (0,12,60):
                result=display(cosine,places)['decimal_enclosure']
                self.assertLessEqual(Decimal(result['lower']),number)
                self.assertGreaterEqual(Decimal(result['upper']),number)
            integer=int(number*10**70)
            for offset,sign in ((integer,1),(integer+1,-1)):
                v=cosine*10**70-offset;self.assertEqual(v.real_sign(),sign)
                bounds=v.display(60)['decimal_enclosure'];actual=number*10**70-offset
                self.assertLessEqual(Decimal(bounds['lower']),actual)
                self.assertGreaterEqual(Decimal(bounds['upper']),actual)
        with self.assertRaises(ValueError):ZETA.real_sign()

    def test_phase32_complete_actions_and_new_observable(self):
        for name,n,power in (('p32',1,1),('p32dg',1,-1),('cp32',2,1),('cp32dg',2,-1)):
            for x in range(1<<n):
                c=Phase32Circuit(n)
                for q in range(n):
                    if (x>>q)&1:c.add('x',q)
                c.add(name,*range(n))
                self.assertEqual(prepare(c).amplitudes,{x:ZETA**power if x==(1<<n)-1 else ONE})
        c=Phase32Circuit(1).add('h',0).add('p32',0).add('h',0)
        r=calculate(request(c));v=C.from_dict(r['answers'][0]['probabilities']['0']['exact'])
        self.assertEqual(v,(ONE+(ZETA+ZETA.conjugate())*F(1,2))*F(1,2));self.assertTrue(v.hi)

    def test_full_1024_entry_five_bit_qft_matrix_with_clean_scratch(self):
        roots=[ZETA**k for k in range(32)];scale=C(INV_SQRT2**5)
        for x in range(32):
            c=Phase32Circuit(6)
            for q in range(5):
                if (x>>q)&1:c.add('x',q)
            append_inverse_qft(c,range(5),clean_ancilla=5)
            self.assertEqual(prepare(c).amplitudes,{y:roots[(-x*y)%32]*scale for y in range(32)})

    def test_modular_addition_every_small_valid_input_and_inverse(self):
        for n in (2,3,4):
            for modulus in range(3,1<<n,2):
                for a in range(modulus):
                    ops=_modadd(tuple(range(n+1)),a,modulus,(n+2,),n+1,tuple(range(n+3,2*n+3)))
                    for x in range(modulus):
                        for enabled in (0,1):
                            bits=x+(enabled<<(n+2));out=basis_run(ops,bits)
                            self.assertEqual(out,((x+a)%modulus if enabled else x)+(enabled<<(n+2)))
                            self.assertEqual(basis_run(reversed(ops),out),bits)

    def test_multipliers_5712_full_label_actions_and_clean_workspace(self):
        count=0
        for n in (2,3,4,5):
            for modulus in (range(3,1<<n,2) if n<=4 else (21,25,31)):
                for a in range(1,modulus):
                    if gcd(a,modulus)!=1:continue
                    ops=multiplier_operations(0,range(1,n+1),range(n+1,n+1+multiplier_workspace(n)),a,modulus)
                    for x in range(1<<n):
                        for control in (0,1):
                            self.assertEqual(basis_run(ops,control+2*x),control+2*((a*x)%modulus if control and x<modulus else x))
                            count+=1
        self.assertEqual(count,5712)

    def test_arithmetic_construction_avoids_truth_tables_and_has_polynomial_bound(self):
        with patch('native_relational_qc.shor.compile_oracle',side_effect=AssertionError('truth table called')):
            for n in range(3,9):
                p=build((1<<n)-1,2,precision=5,oracle='arithmetic')
                self.assertEqual(len(p.scratch),2*n+4)
                self.assertLess(p.oracle_gates,5*(60*(n+2)**4+20*(n+2)**3))
                self.assertFalse(p.metadata()['factors_or_order_supplied'])
        with self.assertRaises(ValueError):multiplier_operations(0,range(1,5),range(5,17),3,15)
        with self.assertRaises(ValueError):multiplier_operations(0,range(4),range(4,16),2,15)
        with patch('native_relational_qc.modular_arithmetic.MAX_GATES',10):
            with self.assertRaises(ResourceLimit):multiplier_operations(0,range(1,5),range(5,17),2,15)

    def test_complete_arithmetic_shor_states_against_independent_function_fourier_sum(self):
        for n,a,m,iqft in ((15,7,5,True),(21,2,5,True),(35,2,5,True),(21,2,5,False)):
            p=build(n,a,precision=m,oracle='arithmetic',inverse_qft=iqft)
            state=prepare(p.circuit);expected={};size=1<<m;roots=[ZETA**k for k in range(size)]
            for x in range(size):
                work=pow(a,x,n)
                for y in (range(size) if iqft else (x,)):
                    key=y+(work<<m);term=roots[(-x*y)%size]*F(1,size) if iqft else C(INV_SQRT2**m)
                    expected[key]=expected.get(key,ZERO)+term
            expected={k:v for k,v in expected.items() if v}
            self.assertEqual(state.amplitudes,expected)
            self.assertEqual(state.probability(dict.fromkeys(p.scratch,0)),ONE)

    def test_oracle_agreement_and_strict_cf_precision_gain(self):
        for m in (4,5):
            backend='cyclotomic32' if m==5 else 'cyclotomic'
            reports=[]
            for oracle in ('table','arithmetic'):
                p=build(21,2,precision=m,oracle=oracle);r=calculate(p.request(backend));assessment=assess(p,r)
                self.assertEqual(assessment['status'],'verified');reports.append(r['answers'][0]['probabilities'])
                success=C.from_dict(assessment['policies']['convergents_only']['exact_success_probability'])
                expected=sum((C.coerce(v) for y,v in exact_phase_law(21,2,m).items() if y in (5,27)),ZERO) if m==5 else ZERO
                self.assertEqual(success,expected)
            self.assertEqual(reports[0],reports[1])
        self.assertEqual(decode(5,21,2,5)['factors'],[3,7])
        self.assertEqual(decode(27,21,2,5)['factors'],[3,7])
        self.assertEqual(decode(5,21,2,5)['attempts'][-1]['candidate_period'],6)

    def test_explicit_backend_limits_and_no_partial_results(self):
        c=Phase32Circuit(3).add('h',0).add('h',1).add('h',2);d=request(c)
        for limit in ({'max_work':1},{'max_branches':2},{'max_coefficient_bits':2}):
            r=calculate(dict(d,limits=limit));self.assertEqual(r['status'],'incomplete');self.assertEqual(r['answers'],[])
        self.assertEqual(run_calculation(d,timeout_seconds=1e-9)['status'],'time_limit')
        queries=[dict(id='p',kind='probability',outcomes={'0':0}),dict(id='y',kind='expectation',paulis={'0':'Y'})]
        limit=calculate(request(c,queries[:1]))['statistics']['work_used']
        r=calculate(dict(request(c,queries),limits={'max_work':limit}));self.assertEqual(r['answers'],[])
        for b in ('cyclotomic','clifford_frame'):
            wrong=request(Phase32Circuit(1).add('p32',0));wrong['backend']=b
            with self.assertRaises(ValueError):validate(wrong)
        with self.assertRaises(ValueError):build(21,2,precision=7,oracle='arithmetic')
        with self.assertRaises(ValueError):build(21,2,precision=5,oracle='arithmetic').request('cyclotomic')
        with self.assertRaises(ValueError):validate(dict(d,simplify='exact'))
        with self.assertRaises(ValueError):validate(dict(d,n_qubits=257))

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional independent Qiskit reference')
    def test_phase32_and_permutations_against_independent_full_complex_states(self):
        import numpy as np
        from qiskit.quantum_info import Statevector
        from native_relational_qc.compact_qiskit import to_qiskit
        rng=random.Random(3232)
        for n in (3,4):
            for _ in range(6):
                c=Phase32Circuit(n)
                for _ in range(30):
                    name=rng.choice(('h','r','s','tdg','p16','p32','p32dg','cp32','cp32dg','cx','ccx','swap','rk'))
                    width=3 if name=='ccx' else 2 if name in ('cp32','cp32dg','cx','swap') else 1
                    c.add(name,*rng.sample(range(n),width))
                s=prepare(c).amplitudes;ref=Statevector.from_instruction(to_qiskit(c)).data
                np.testing.assert_allclose([complex(s.get(k,ZERO)) for k in range(1<<n)],ref,atol=4e-12,rtol=0)
        p=build(21,2,precision=5,oracle='table');s=prepare(p.circuit).amplitudes
        ref=Statevector.from_instruction(to_qiskit(p.circuit)).data
        np.testing.assert_allclose([complex(s.get(k,ZERO)) for k in range(len(ref))],ref,atol=5e-12,rtol=0)


if __name__=='__main__':unittest.main()
