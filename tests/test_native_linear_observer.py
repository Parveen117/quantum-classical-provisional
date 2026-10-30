import copy
import importlib.util
import random
import unittest

from native_relational_qc.compact import ResourceLimit
from native_relational_qc.cyclotomic32 import Cyclotomic32 as C,ZERO,ONE,ZETA
from native_relational_qc.linear_observer import linear_future_bank,verify_linear_bank,run_linear_bank
from native_relational_qc.observer32 import future_bank
from native_relational_qc.phase_backend import Phase32Circuit,prepare
from tests.test_native_observer32 import dense_pauli


def independent_ccx(k,n=None):
    c=Phase32Circuit(n or (2*k+1))
    for j in range(k):c.add('ccx',2*j,2*j+1,2*k)
    return c,{2*k:'Z'}


class LinearObserverTests(unittest.TestCase):
    def test_involution_and_phase_exact_rank_reduction(self):
        for name,n,qs,seed,rank in (('ch',2,(0,1),{1:'Z'},2),
                ('ccx',3,(0,1,2),{2:'Z'},2),('cp32',2,(0,1),{1:'X'},3)):
            c=Phase32Circuit(n).add(name,*qs);linear=linear_future_bank(c,seed)
            self.assertEqual(future_bank(c,seed)['retained_dimension'],4)
            self.assertEqual(linear['retained_dimension'],rank)
            self.assertEqual(verify_linear_bank(c,seed,linear)['status'],'verified')

    def test_multiple_commuting_controls_and_no_coordinate_preconstruction(self):
        c,seed=independent_ccx(3,50)
        self.assertEqual(future_bank(c,seed)['retained_dimension'],64)
        linear=linear_future_bank(c,seed,max_rank=8)
        self.assertEqual(linear['retained_dimension'],8)
        self.assertFalse(linear['statistics']['statevector_constructed'])
        self.assertEqual(verify_linear_bank(c,seed,linear)['status'],'verified')
        # A coordinate-bank cap is different from a per-vector cap. Here the
        # exact row basis closes within the same numeric term limit of 48.
        with self.assertRaises(ResourceLimit):future_bank(c,seed,max_terms=48)
        reduced=linear_future_bank(c,seed,max_terms=48)
        self.assertEqual(verify_linear_bank(c,seed,reduced,max_terms=48)['status'],'verified')

    def test_no_reduction_and_delayed_revelation_control(self):
        c=Phase32Circuit(1).add('h',0).add('p32',0);seed={0:'Z'}
        linear=linear_future_bank(c,seed)
        self.assertEqual(linear['retained_dimension'],3)
        self.assertEqual(future_bank(c,seed)['retained_dimension'],3)
        for sequence,expected in (([],ONE),([0],ZERO),([0,0],ONE)):
            r=run_linear_bank(c,seed,linear,action_sequence=sequence)
            self.assertEqual(C.from_dict(r['value']),expected)

    def test_runtime_exact_agreement_with_sparse_states_and_old_coordinate_bank(self):
        rng=random.Random(3245)
        cases=[(Phase32Circuit(2).add('ch',0,1),{1:'Z'}),
               (Phase32Circuit(2).add('cp32',1,0).add('h',0).add('x',1),{0:'X'}),
               independent_ccx(2)]
        for c,seed in cases:
            linear=linear_future_bank(c,seed);old=future_bank(c,seed)
            for _ in range(4):
                sequence=[rng.randrange(len(old['actions'])) for _ in range(12)]
                initial=rng.randrange(1<<c.n_qubits)
                ref=Phase32Circuit(c.n_qubits)
                for q in range(c.n_qubits):
                    if initial&(1<<q):ref.add('x',q)
                values=[]
                for p in old['basis']:
                    x,z=int(p['x']),int(p['z'])
                    values.append(ZERO if x else -ONE if (z&initial).bit_count()%2 else ONE)
                for k in sequence:
                    name,qs=old['actions'][k];ref.add(name,*qs)
                    values=[sum((C.from_dict(t['coefficient'])*values[t['column']] for t in row),ZERO) for row in old['transition_rows'][k]]
                r=run_linear_bank(c,seed,linear,action_sequence=sequence,input_basis=initial)
                self.assertEqual(C.from_dict(r['value']),prepare(ref).expectation(seed))
                self.assertEqual(C.from_dict(r['value']),values[0])

    def test_exact_phase_orbit_polynomial(self):
        # CP32 conjugation has frequencies 0,+theta,-theta on this orbit.
        c=Phase32Circuit(2).add('cp32',0,1);bank=linear_future_bank(c,{1:'X'})
        t=[[ZERO]*3 for _ in range(3)]
        for i,row in enumerate(bank['transition_rows'][0]):
            for term in row:t[i][term['column']]=C.from_dict(term['coefficient'])
        def mul(a,b):return [[sum((a[i][k]*b[k][j] for k in range(3)),ZERO) for j in range(3)] for i in range(3)]
        t2=mul(t,t);t3=mul(t,t2);s=ONE+ZETA+ZETA.conjugate()
        self.assertEqual([[t3[i][j]-s*t2[i][j]+s*t[i][j]-(ONE if i==j else ZERO) for j in range(3)] for i in range(3)],[[ZERO]*3 for _ in range(3)])

    def test_certificate_rejects_wrong_transition_reachability_and_binding(self):
        c=Phase32Circuit(2).add('ch',0,1);seed={1:'Z'};bank=linear_future_bank(c,seed)
        for mutation in ('transition','origin','basis','pivot','seed','action','rank','scope'):
            bad=copy.deepcopy(bank)
            if mutation=='transition':bad['transition_rows'][0][0][0]['coefficient']=C(2).to_dict()
            if mutation=='origin':bad['origins'][1]['divisor']=C(3).to_dict()
            if mutation=='basis':bad['basis'][1][0]['coefficient']=C(7).to_dict()
            if mutation=='pivot':bad['pivots'][1]=bad['pivots'][0]
            if mutation=='seed':bad['seed']={'x':'1','z':'0'}
            if mutation=='action':bad['actions'][0][1]=[1,0]
            if mutation=='rank':bad['retained_dimension']=3
            if mutation=='scope':bad['minimality_scope']='minimum memory for every circuit'
            with self.assertRaises(ValueError,msg=mutation):verify_linear_bank(c,seed,bad)

    def test_inflated_closed_space_is_not_accepted_as_minimal(self):
        # X,Y,Z is closed under H/p32, but for an I seed none is reachable.
        c=Phase32Circuit(1).add('h',0).add('p32',0)
        bank=linear_future_bank(c,{0:'Z'});bank['seed']={'x':'0','z':'0'}
        with self.assertRaisesRegex(ValueError,'reachability'):verify_linear_bank(c,{},bank)

    def test_rank_work_bits_term_and_total_storage_limits(self):
        c=Phase32Circuit(2).add('cp32',0,1);seed={1:'X'}
        for limits in ({'max_rank':2},{'max_work':1},{'max_terms':2},{'max_coefficient_bits':2},{'max_coefficients':5}):
            with self.assertRaises(ResourceLimit):linear_future_bank(c,seed,**limits)
        bank=linear_future_bank(c,seed)
        for limits in ({'max_rank':2},{'max_work':1},{'max_terms':2},{'max_coefficient_bits':2},{'max_coefficients':5}):
            with self.assertRaises(ResourceLimit):verify_linear_bank(c,seed,bank,**limits)
        used=verify_linear_bank(c,seed,bank)['statistics']['work_used']
        with self.assertRaises(ResourceLimit):run_linear_bank(c,seed,bank,max_work=used)

    def test_identity_empty_alphabet_strict_input_and_certificate_encoding(self):
        c=Phase32Circuit(2);bank=linear_future_bank(c,{})
        self.assertEqual(bank['retained_dimension'],1)
        self.assertEqual(C.from_dict(run_linear_bank(c,{},bank)['value']),ONE)
        for seed in ({0:'Z','0':'X'},{True:'Z'},{2:'Z'},{0:'bad'}):
            with self.assertRaises(ValueError):linear_future_bank(c,seed)
        for args in ({'action_sequence':[0]},{'input_basis':True},{'input_basis':4}):
            with self.assertRaises(ValueError):run_linear_bank(c,{},bank,**args)
        for coefficient in ('1e999999','01','1/0','-'+'9'*10000):
            bad=copy.deepcopy(bank);bad['basis'][0][0]['coefficient']['coefficients'][0]=coefficient
            with self.assertRaises(ValueError):verify_linear_bank(c,{},bad)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional independent Qiskit reference')
    def test_independent_operator_closure_and_arbitrary_mixed_state_replay(self):
        import numpy as np
        from qiskit.quantum_info import Operator
        from native_relational_qc.compact_qiskit import to_qiskit
        rng=np.random.default_rng(3245)
        cases=[(Phase32Circuit(2).add('ch',0,1),{1:'Z'}),
               (Phase32Circuit(2).add('cp32',1,0),{0:'X'}),independent_ccx(2)]
        for c,seed in cases:
            bank=linear_future_bank(c,seed);rank=bank['retained_dimension'];d=1<<c.n_qubits
            basis=[sum((complex(C.from_dict(t['coefficient']))*dense_pauli(c.n_qubits,int(t['x']),int(t['z'])) for t in row),np.zeros((d,d),complex)) for row in bank['basis']]
            self.assertEqual(np.linalg.matrix_rank(np.array([p.ravel() for p in basis]),tol=1e-10),rank)
            unitaries=[];transfers=[]
            for (name,qs),rows in zip(bank['actions'],bank['transition_rows']):
                u=Operator(to_qiskit(Phase32Circuit(c.n_qubits).add(name,*qs))).data;unitaries.append(u)
                t=np.zeros((rank,rank),complex)
                for i,row in enumerate(rows):
                    for item in row:t[i,item['column']]=complex(C.from_dict(item['coefficient']))
                    np.testing.assert_allclose(sum((t[i,j]*p for j,p in enumerate(basis)),np.zeros((d,d),complex)),u.conj().T@basis[i]@u,atol=2e-14,rtol=0)
                transfers.append(t)
            v=rng.normal(size=d)+1j*rng.normal(size=d);v/=np.linalg.norm(v)
            rho=.6*np.outer(v,v.conj())+.4*np.eye(d)/d
            readings=np.array([np.trace(p@rho) for p in basis])
            for k in rng.integers(0,len(transfers),size=40):
                rho=unitaries[k]@rho@unitaries[k].conj().T;readings=transfers[k]@readings
                np.testing.assert_allclose(readings,[np.trace(p@rho) for p in basis],atol=3e-13,rtol=0)


if __name__=='__main__':unittest.main()
