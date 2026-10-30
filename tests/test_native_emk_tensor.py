from fractions import Fraction as F
import copy
import random
import unittest

import numpy as np

from native_relational_qc.calculator import calculate, run_calculation, validate
from native_relational_qc.compact import CompactCircuit, ResourceLimit
from native_relational_qc.exact import Exact, ONE, ZERO, IMAG, exact_gate
from native_relational_qc.emk_tensor import EMKBlock, geometry, word_product, _factor, _reconstruct


def mm(a,b):
    return [[sum((a[i][k]*b[k][j] for k in range(len(b))),ZERO)
             for j in range(len(b[0]))] for i in range(len(a))]


def minus(a,b):
    return [[v-w for v,w in zip(x,y)] for x,y in zip(a,b)]


def pauli_matrix(n, word, sign=1):
    dim=2**n
    out=[[ZERO]*dim for _ in range(dim)]
    for j in range(dim):
        target,phase=j,Exact(sign)
        for q,p in word.items():
            bit=(j>>q)&1
            if p in ('X','Y'):target ^= 1<<q
            if p=='Y':phase *= -IMAG if bit else IMAG
            elif p=='Z':phase *= -1 if bit else 1
        out[target][j]=phase
    return out


def direct_projector_tensor(circuit, generators):
    state=circuit.state();n=2**circuit.n_qubits
    psi=[state.amplitude(i) for i in range(n)]
    p=[[x*y.conjugate() for y in psi] for x in psi]
    tangents=[]
    for sign,word in generators:
        h=pauli_matrix(circuit.n_qubits,word,sign)
        b=[[-IMAG*v for v in row] for row in h]
        tangents.append(minus(mm(b,p),mm(p,b)))
    tensor=[]
    for x in tangents:
        row=[]
        for y in tangents:
            product=mm(mm(mm(p,x),y),p)
            row.append(sum((product[i][i] for i in range(n)),ZERO))
        tensor.append(row)
    return tensor


def request(generators=None,operations=None,**options):
    return dict(schema='nrqc-calculator-v1',n_qubits=2,
                operations=operations if operations is not None else [['h',[0]],['cx',[0,1]]],
                queries=[dict(id='q',kind='geometry',generators=generators if generators is not None else
                    [{'paulis':{'0':'X'}},{'paulis':{'1':'X'}},{'sign':-1,'paulis':{'0':'X'}}])],**options)


class EMKTensorTests(unittest.TestCase):
    def test_primitive_relations_and_all_basis_products(self):
        identity,k,r,rk=EMKBlock(1),EMKBlock(b=1),EMKBlock(c=1),EMKBlock(d=1)
        self.assertEqual(r*r,identity*(-1));self.assertEqual(k*k,identity)
        self.assertEqual(r*k,rk);self.assertEqual(k*r,rk*(-1))
        self.assertEqual((r*k)*r,k)
        for a in (identity,k,r,rk):
            for b in (identity,k,r,rk):
                self.assertEqual([list(row) for row in (a*b).matrix()],mm(a.matrix(),b.matrix()))

    def test_general_exact_multiplication_associativity_and_dagger(self):
        rng=random.Random(20261023)
        for _ in range(25):
            blocks=[EMKBlock(*(Exact(F(rng.randrange(-5,6),rng.randrange(1,6)),
                                     F(rng.randrange(-2,3),3),F(rng.randrange(-2,3),5))
                               for _ in range(4))) for _ in range(3)]
            a,b,c=blocks
            self.assertEqual((a*b)*c,a*(b*c))
            self.assertEqual((a*b).dagger(),b.dagger()*a.dagger())
            self.assertEqual([list(row) for row in (a*b).matrix()],mm(a.matrix(),b.matrix()))

    def test_ordered_pauli_word_phase_and_quarter_turn(self):
        self.assertEqual(word_product({0:'X'},{0:'Y'}),(IMAG,{0:'Z'}))
        self.assertEqual(word_product({0:'Y'},{0:'X'}),(-IMAG,{0:'Z'}))
        self.assertEqual(word_product({0:'X',2:'X'},{0:'Y',2:'Y'}),(-ONE,{0:'Z',2:'Z'}))
        self.assertEqual(IMAG*IMAG,-ONE)
        # A phase EXPONENT product a*b is not root-of-unity multiplication.
        self.assertNotEqual(IMAG**((1*1)%4),IMAG*IMAG)

    def test_cut_metric_cannot_replace_curvature(self):
        generators=[(1,{0:'X'}),(1,{0:'Y'})]
        a=geometry(CompactCircuit(1),generators)
        b=geometry(CompactCircuit(1).add('x',0),generators)
        self.assertEqual(a['metric'],b['metric'])
        self.assertEqual(a['curvature'][0][1],ONE)
        self.assertEqual(b['curvature'][0][1],-ONE)
        self.assertEqual(a['dependencies']['rank'],2)
        self.assertEqual(a['complex_gram_rank'],1)

    def test_bell_real_dependencies_reconstruct_both_halves(self):
        c=CompactCircuit(2).add('h',0).add('cx',0,1)
        g=[(1,{0:'X'}),(1,{1:'X'}),(-1,{0:'X'}),(1,{})]
        a=geometry(c,g,contraction='streaming')
        self.assertEqual(a['dependencies']['rank'],1)
        self.assertEqual(a['dependencies']['basis_indices'],[0])
        self.assertEqual(a['dependencies']['coordinates'],[[ONE,ONE,-ONE,ZERO]])
        self.assertEqual(a['tensor'],direct_projector_tensor(c,g))
        self.assertLess(a['scalar_evaluations'],len(g)+len(g)*(len(g)-1)//2)
        self.assertEqual(a['scalar_evaluations'],3)

    def test_zero_tangents_and_identity(self):
        result=geometry(CompactCircuit(50),[(1,{}),(-1,{})],max_work=1)
        self.assertEqual(result['scalar_evaluations'],0)
        self.assertEqual(result['dependencies']['rank'],0)
        self.assertEqual(result['dependencies']['nullspace'],[[ONE,ZERO],[ZERO,ONE]])
        self.assertEqual(result['tensor'],[[ZERO,ZERO],[ZERO,ZERO]])

    def test_exact_projector_definition_for_phase_and_controlled_circuits(self):
        circuits=[CompactCircuit(1).add('h',0).add('t',0),
                  CompactCircuit(2).add('h',1).add('t',1).add('ch',1,0).add('s',0),
                  CompactCircuit(3).add('h',0).add('cx',0,1).add('t',1).add('cs',1,2).add('h',2)]
        for c in circuits:
            n=c.n_qubits
            generators=[(1,{0:'X'}),(-1,{0:'Y'}),(1,{n-1:'Z'}),(1,{q:'X' for q in range(n)})]
            direct=direct_projector_tensor(c,generators)
            for backend,options in [('observer',{}),('factored',{'contraction':'integer'}),
                                    ('factored',{'contraction':'streaming'})]:
                result=geometry(c,generators,backend=backend,**options)
                self.assertEqual(result['tensor'],direct)
                for vector in result['dependencies']['nullspace']:
                    self.assertEqual(mm(direct,[[v] for v in vector]),[[ZERO] for _ in vector])

    def test_real_factor_with_irrational_entries_and_zero_pivot(self):
        matrix=[[ZERO,ZERO,ZERO],[ZERO,ONE,Exact(b=1)],[ZERO,Exact(b=1),Exact(2)]]
        factor=_factor(matrix,4096)
        self.assertEqual(factor['basis_indices'],[1])
        self.assertEqual(factor['coordinates'],[[ZERO,ONE,Exact(b=1)]])
        self.assertEqual(_reconstruct(matrix,factor,4096),matrix)
        with self.assertRaises(ResourceLimit):
            _factor([[Exact(F(1,1024)),ONE],[ONE,Exact(1024)]],2)

    def test_public_interface_backends_hash_and_simplification(self):
        a=calculate(request(contraction='streaming'))
        b=calculate(request(backend='observer',simplify='exact'))
        self.assertEqual(a['status'],'completed')
        self.assertEqual(a['answers'][0]['geometry']['tensor'],b['answers'][0]['geometry']['tensor'])
        self.assertEqual(a['answers'][0]['geometry']['real_tangent_rank'],1)
        changed=request();changed['queries'][0]['generators'][0]['sign']=-1
        d=calculate(changed)
        self.assertEqual(a['circuit_sha256'],d['circuit_sha256'])
        self.assertNotEqual(a['request_sha256'],d['request_sha256'])

    def test_reject_invalid_generators_and_combined_evaluation_cap(self):
        for gen in ([],[{}],[{'paulis':{'0':'A'}}],[{'paulis':{},'sign':0}],
                    [{'paulis':{},'sign':True}],[{'paulis':{},'extra':1}],
                    [{'paulis':{'2':'X'}}],[{'paulis':{}}]*9):
            with self.subTest(gen=gen),self.assertRaises(ValueError):validate(request(gen))
        d=request([{'paulis':{str(q):'X'}} for q in range(8)],operations=[])
        d['n_qubits']=8
        d['queries']=[dict(copy.deepcopy(d['queries'][0]),id=str(i)) for i in range(8)]
        with self.assertRaises(ValueError):validate(d)

    def test_resource_failure_returns_no_partial_geometry(self):
        d=request(operations=[['h',[0]],['t',[0]],['h',[0]]],limits={'max_work':1})
        result=calculate(d)
        self.assertEqual(result['status'],'incomplete')
        self.assertNotIn('geometry',result['answers'][0])
        self.assertTrue(result['answers'][0]['statistics']['partial_tensor_discarded'])
        with self.assertRaises(ResourceLimit):
            geometry(CompactCircuit(1).add('h',0).add('t',0).add('h',0).add('t',0).add('h',0),
                     [(1,{0:'Z'}),(1,{0:'X'})],max_coefficient_bits=2)

    def test_fresh_worker_and_whole_batch_timeout(self):
        result=run_calculation(request(contraction='streaming'),timeout_seconds=10)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['answers'][0]['geometry']['real_tangent_rank'],1)
        result=run_calculation(request(),timeout_seconds=1e-9)
        self.assertEqual(result['status'],'time_limit')
        self.assertEqual(result['answers'],[])

    def test_independent_qiskit_covariance_and_positive_metric(self):
        try:
            from qiskit.quantum_info import Statevector,Pauli
        except ImportError:
            self.skipTest('optional Qiskit SDK not installed')
        from native_relational_qc.compact_qiskit import to_qiskit
        from native_relational_qc.stress_benchmark import brickwork
        for seed in (117,20261023):
            c=brickwork(4,3,seed)
            g=[(1,{0:'X'}),(-1,{0:'Y',2:'Z'}),(1,{1:'Y'}),(1,{2:'X',3:'Z'})]
            result=geometry(c,g,contraction='streaming')
            state=Statevector.from_instruction(to_qiskit(c)).data
            matrices=[]
            for sign,word in g:
                matrices.append(sign*Pauli(''.join(word.get(q,'I') for q in reversed(range(4)))).to_matrix())
            expected=np.array([[np.vdot(state,a@b@state)-np.vdot(state,a@state)*np.vdot(state,b@state)
                                for b in matrices] for a in matrices])
            actual=np.array([[complex(v) for v in row] for row in result['tensor']])
            np.testing.assert_allclose(actual,expected,rtol=0,atol=2e-13)
            self.assertGreaterEqual(np.linalg.eigvalsh(actual.real).min(),-1e-13)


if __name__=='__main__':unittest.main()
