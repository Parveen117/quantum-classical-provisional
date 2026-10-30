import importlib.util
import random
import unittest
from fractions import Fraction

from native_relational_qc.calculator import calculate,run_calculation,validate
from native_relational_qc.compact import ResourceLimit
from native_relational_qc.cyclotomic32 import Cyclotomic32 as C,ZERO,ONE,ZETA
from native_relational_qc.observer32 import Engine,future_bank
from native_relational_qc.phase_backend import Phase32Circuit


def document(c,queries=None,backend='observer32',**limits):
    return dict(schema='nrqc-calculator-v1',backend=backend,n_qubits=c.n_qubits,
        operations=[[g,list(q)] for g,q in c.operations],limits=limits,
        queries=queries or [dict(id='x',kind='expectation',paulis={'0':'X'})])


def graph(n):
    c=Phase32Circuit(n)
    for q in range(n):c.add('h',q)
    for q in range(n-1):c.add('cz',q,q+1)
    for q in range(n):c.add('p32',q)
    return c


def dense_pauli(n,x,z):
    import numpy as np
    p=np.zeros((1<<n,1<<n),complex)
    for j in range(1<<n):p[j^x,j]=1j**((x&z).bit_count())*(-1)**((j&z).bit_count())
    return p


class Observer32Tests(unittest.TestCase):
    def test_all_new_local_images_against_independent_complex_matrices(self):
        import numpy as np
        for width,prefix in ((1,'p'),(2,'cp')):
            e=Engine(Phase32Circuit(width))
            for denominator in (16,32):
                for suffix,sign in (('',1),('dg',-1)):
                    name=f'{prefix}{denominator}{suffix}'
                    diagonal=np.ones(1<<width,complex)
                    diagonal[-1]=np.exp(sign*2j*np.pi/denominator)
                    u=np.diag(diagonal)
                    for x in range(1<<width):
                        for z in range(1<<width):
                            actual=sum((complex(v)*dense_pauli(width,a,b) for a,b,v in e.local_image(name,width,x,z)),np.zeros_like(u))
                            expected=u.conj().T@dense_pauli(width,x,z)@u
                            np.testing.assert_allclose(actual,expected,atol=3e-15,rtol=0)

    def test_exact_all_gate_agreement_with_sparse_state_and_query_order(self):
        rng=random.Random(3204)
        names=('h','x','y','z','s','sdg','t','tdg','sx','sxdg','r','id','rk','k',
               'cx','cz','ch','cs','ct','swap','ccx','p16','p16dg','cp16','cp16dg','p32','p32dg','cp32','cp32dg')
        # Include non-adjacent/reversed qargs, mixed Y signs, all new phase gates.
        for trial in range(3):
            c=Phase32Circuit(3)
            for q in range(3):c.add('h',q)
            for name in rng.sample(names,len(names)):
                width=3 if name=='ccx' else 2 if name in ('cx','cz','ch','cs','ct','swap') or name.startswith('cp') else 1
                c.add(name,*rng.sample(range(3),width))
            queries=[dict(id='d',kind='distribution',qubits=[2,0]),
                dict(id='p',kind='probability',outcomes={'1':1}),
                dict(id='y',kind='expectation',paulis={'0':'Y','1':'X','2':'Z'}),
                dict(id='i',kind='expectation',paulis={})]
            a,b=[calculate(document(c,queries,backend)) for backend in ('observer32','cyclotomic32')]
            self.assertEqual(a['status'],'completed');self.assertEqual(b['status'],'completed')
            for answer in b['answers']:answer.pop('execution_seconds',None)
            self.assertEqual(a['answers'],b['answers'])

    def test_no_early_source_boundary_discard(self):
        # X has zero expectation on |0>, but H pulls it to Z at an earlier cut.
        c=Phase32Circuit(1).add('h',0).add('h',0)
        q=[dict(id='z',kind='expectation',paulis={'0':'Z'})]
        r=calculate(document(c,q))
        self.assertEqual(C.from_dict(r['answers'][0]['value']['exact']),ONE)
        # |+> and |-> have the same current Z reading; a future H separates them.
        values=[]
        for minus in (False,True):
            c=Phase32Circuit(1).add('h',0)
            if minus:c.add('z',0)
            before=calculate(document(c,q))
            self.assertEqual(C.from_dict(before['answers'][0]['value']['exact']),ZERO)
            c.add('h',0);after=calculate(document(c,q))
            values.append(C.from_dict(after['answers'][0]['value']['exact']))
        self.assertEqual(values,[ONE,-ONE])

    def test_connected_50_qubit_graph_analytic_reference_and_sparse_boundary(self):
        c=graph(50);q=[dict(id='k0',kind='expectation',paulis={'0':'X','1':'Z'})]
        r=calculate(document(c,q));self.assertEqual(r['status'],'completed')
        self.assertEqual(C.from_dict(r['answers'][0]['value']['exact']),(ZETA+ZETA.conjugate())*Fraction(1,2))
        self.assertEqual(r['statistics']['peak_terms'],2)
        self.assertFalse(r['statistics']['statevector_constructed'])
        self.assertEqual(r['error_ledger']['analytic_truncation_error'],'0')
        self.assertEqual(r['error_ledger']['arithmetic_error'],'0')
        sparse=calculate(document(c,q,'cyclotomic32',max_branches=4096))
        self.assertEqual(sparse['status'],'incomplete');self.assertEqual(sparse['answers'],[])

    def test_complementary_failure_observer_growth_sparse_completes(self):
        c=Phase32Circuit(7)
        for q in range(7):c.add('h',q).add('p32',q)
        queries=[dict(id='global',kind='expectation',paulis={str(q):'X' for q in range(7)})]
        r=calculate(document(c,queries,max_terms=64))
        self.assertEqual(r['status'],'incomplete');self.assertEqual(r['answers'],[])
        s=calculate(document(c,queries,'cyclotomic32',max_branches=128))
        self.assertEqual(s['status'],'completed')
        self.assertEqual(C.from_dict(s['answers'][0]['value']['exact']),((ZETA+ZETA.conjugate())*Fraction(1,2))**7)

    def test_whole_batch_failure_work_bits_projector_and_timeout(self):
        c=Phase32Circuit(3).add('h',0).add('p32',0)
        queries=[dict(id='first',kind='expectation',paulis={}),dict(id='later',kind='expectation',paulis={'0':'X'})]
        first=calculate(document(c,queries[:1]))
        for limits in ({'max_work':first['statistics']['work_used']},{'max_coefficient_bits':2},{'max_terms':1}):
            r=calculate(document(c,queries,**limits))
            self.assertEqual(r['status'],'incomplete');self.assertEqual(r['answers'],[])
            self.assertNotIn('error_ledger',r)
        q=[dict(id='d',kind='distribution',qubits=[0,1,2])]
        r=calculate(document(c,q,max_terms=4));self.assertIn('initial projector',r['error'])
        self.assertEqual(run_calculation(document(c),timeout_seconds=1e-9)['status'],'time_limit')

    def test_explicit_backend_validation(self):
        c=Phase32Circuit(1).add('p32',0);d=document(c)
        for extra in ({'backend':'observer'},{'simplify':'exact'},{'contraction':'integer'},
                      {'n_qubits':257},{'limits':{'max_branches':10}},
                      {'queries':[dict(id='g',kind='geometry',generators=[dict(paulis={'0':'Z'})])]}):
            with self.assertRaises(ValueError):validate(dict(d,**extra))
        self.assertEqual(validate(d)[1]['limits']['max_terms'],4096)

    def test_future_bank_large_implicit_carrier_and_action_binding(self):
        c=Phase32Circuit(50)
        for q in range(50):c.add('h',q).add('p32',q)
        a=future_bank(c,{0:'Z'});self.assertEqual(a['retained_dimension'],3)
        self.assertEqual(a['ambient_operator_dimension'],str(4**50))
        self.assertFalse(a['minimality_claim']);self.assertEqual(len(a['transition_rows']),100)
        b=future_bank(Phase32Circuit(50).add('h',1).add('p32',1),{0:'Z'})
        self.assertEqual(b['retained_dimension'],1)
        self.assertNotEqual(a['action_sha256'],b['action_sha256'])
        # An all-future bank can be larger than a fixed-circuit pullback.
        self.assertEqual(len(Engine(Phase32Circuit(1).add('h',0).add('p32',0)).pullback({(0,1):ONE})),1)
        self.assertEqual(future_bank(Phase32Circuit(1).add('h',0).add('p32',0),{0:'Z'})['retained_dimension'],3)

    def test_future_bank_limits_empty_identity_and_delayed_growth(self):
        c=Phase32Circuit(1).add('h',0).add('p32',0)
        for limits in ({'max_terms':2},{'max_work':1},{'max_coefficient_bits':2}):
            with self.assertRaises(ResourceLimit):future_bank(c,{0:'Z'},**limits)
        bank=future_bank(c,{})
        self.assertEqual(bank['retained_dimension'],1)
        empty=future_bank(Phase32Circuit(1),{0:'Z'})
        self.assertEqual(empty['transition_rows'],[])
        self.assertEqual(empty['retained_dimension'],1)
        with self.assertRaises(ValueError):future_bank(c,{1:'Z'})
        with self.assertRaises(ValueError):future_bank(c,{0:'Z','0':'X'})

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional independent Qiskit reference')
    def test_future_bank_independent_matrix_closure_and_chronological_replay(self):
        import numpy as np
        from qiskit.quantum_info import Operator
        from native_relational_qc.compact_qiskit import to_qiskit
        c=Phase32Circuit(2).add('h',0).add('cp32',0,1).add('cx',1,0)
        bank=future_bank(c,{0:'Z'})
        basis=[dense_pauli(2,int(p['x']),int(p['z'])) for p in bank['basis']]
        transfers=[];unitaries=[]
        for (name,qs),rows in zip(bank['actions'],bank['transition_rows']):
            u=Operator(to_qiskit(Phase32Circuit(2).add(name,*qs))).data;unitaries.append(u)
            t=np.zeros((len(basis),len(basis)),complex)
            for i,row in enumerate(rows):
                for term in row:t[i,term['column']]=complex(C.from_dict(term['coefficient']))
                actual=sum((t[i,j]*p for j,p in enumerate(basis)),np.zeros((4,4),complex))
                np.testing.assert_allclose(actual,u.conj().T@basis[i]@u,atol=3e-15,rtol=0)
            transfers.append(t)
        rng=np.random.default_rng(3204);v=rng.normal(size=4)+1j*rng.normal(size=4);v/=np.linalg.norm(v)
        rho=.7*np.outer(v,v.conj())+.3*np.eye(4)/4
        observations=np.array([np.trace(p@rho) for p in basis])
        for k in rng.integers(0,3,size=40):
            rho=unitaries[k]@rho@unitaries[k].conj().T
            observations=transfers[k]@observations
            np.testing.assert_allclose(observations,[np.trace(p@rho) for p in basis],atol=2e-14,rtol=0)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional independent Qiskit reference')
    def test_small_graph_and_y_responses_against_qiskit(self):
        import numpy as np
        from qiskit.quantum_info import Statevector
        from native_relational_qc.compact_qiskit import to_qiskit
        c=graph(5).add('cp32',4,0).add('ccx',3,0,2).add('s',1)
        queries=[dict(id=str(i),kind='expectation',paulis=p) for i,p in enumerate((
            {'0':'X','1':'Z'},{'4':'Y','0':'Y'},{'3':'X','2':'Y','1':'Z'}))]
        r=calculate(document(c,queries));self.assertEqual(r['status'],'completed')
        v=Statevector.from_instruction(to_qiskit(c)).data
        for q,a in zip(queries,r['answers']):
            x=sum(1<<int(k) for k,p in q['paulis'].items() if p in ('X','Y'))
            z=sum(1<<int(k) for k,p in q['paulis'].items() if p in ('Z','Y'))
            np.testing.assert_allclose(complex(C.from_dict(a['value']['exact'])),v.conj()@dense_pauli(5,x,z)@v,atol=3e-13,rtol=0)


if __name__=='__main__':unittest.main()
