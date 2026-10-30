from fractions import Fraction
import importlib.util
import random
import unittest

import numpy as np

from native_relational_qc.calculator import calculate, validate, run_calculation
from native_relational_qc.compact import CompactCircuit, ResourceLimit
from native_relational_qc.dyadic import Dyadic, DONE, DZERO
from native_relational_qc.exact import Exact, ONE, ZERO, HALF
from native_relational_qc.factored import _Budget, _StateFactors, probability, expectation
from native_relational_qc.integer_matrix import IntegerMatrix
from native_relational_qc.observer import expectation as expanded_expectation
from native_relational_qc.reused_product import _row_groups, _limb_product
from native_relational_qc.streaming import _plans, _site
from native_relational_qc.stress_benchmark import brickwork


def budget(**changes):
    args = dict(max_bond=256,max_coefficients=1_000_000,max_work=100_000_000,
                max_coefficient_bits=4096,progress=None)
    return _Budget(**{**args,**changes})


class ReusedMatrixTests(unittest.TestCase):
    def compare(self, left, right, m,k,n):
        a,b = IntegerMatrix.from_sparse(left,(m,k)),IntegerMatrix.from_sparse(right,(k,n))
        counter = budget()
        result = a.matmul(b,counter,reuse=True).entries()
        for i in range(m):
            for j in range(n):
                independent = sum((left.get((i,t),DZERO).to_exact()*right.get((t,j),DZERO).to_exact()
                                   for t in range(k)),ZERO)
                self.assertEqual(result.get((i,j),DZERO).to_exact(),independent)
        self.assertEqual(result,a.matmul(b,budget()).entries())
        return counter

    def test_all_field_products_and_complex_signs(self):
        basis = [DONE,Dyadic(b=1),Dyadic(c=1),Dyadic(d=1)]
        for a in basis:
            for b in basis:
                for sign in (1,-1):
                    self.compare({(0,0):a},{(0,0):b if sign==1 else -b},1,1,1)

    def test_rectangular_wide_signed_and_mixed_denominators(self):
        rng = random.Random(20261024)
        for m,k,n in ((1,1,1),(3,7,4),(5,2,3),(2,11,2)):
            for bits in (1,25,53,117,350):
                def entries(r,c):
                    return {(i,j):Dyadic(*(rng.randrange(-(1 << bits),1 << bits) for _ in range(4)),rng.randrange(30))
                            for i in range(r) for j in range(c) if rng.randrange(4)}
                self.compare(entries(m,k),entries(k,n),m,k,n)

    def test_signed_inner_reuse_and_cancellation(self):
        left = {(0,0):Dyadic(3),(0,1):Dyadic(5),(0,2):Dyadic(7),
                (1,0):Dyadic(3),(1,1):Dyadic(5),(1,2):Dyadic(-2)}
        right = {(0,0):Dyadic(1,2,3,4),(1,0):Dyadic(-1,-2,-3,-4),
                 (2,1):DONE,(3,1):Dyadic(9)}
        counter = self.compare(left,right,2,4,2)
        self.assertGreater(counter.stats['reused_inner_labels'],0)
        a=IntegerMatrix.from_sparse({(0,0):DONE,(0,1):DONE},(1,2))
        b=IntegerMatrix.from_sparse({(0,0):DONE,(1,0):-DONE},(2,1))
        counter=budget()
        self.assertEqual(a.matmul(b,counter,reuse=True).entries(),{})
        self.assertEqual(counter.stats['scalar_products'],0)

    def test_zero_and_outer_reuse_keep_output_shape(self):
        left={(0,0):DONE,(1,0):-DONE,(2,0):DONE}
        right={(0,0):Dyadic(c=1),(0,1):Dyadic(c=-1),(0,3):Dyadic(c=1)}
        counter=self.compare(left,right,4,3,5)
        self.assertEqual(counter.stats['reused_matrix_product_slots'],1)
        self.compare({},right,4,3,5)
        self.compare(left,{},4,3,5)

    def test_equal_norm_or_imaginary_phase_is_not_signed_equality(self):
        parts=tuple(np.array([[v] for v in channel],dtype=object)
                    for channel in ((1,0,1,1),(0,0,1,0),(0,1,0,0),(0,0,0,0)))
        indices,signs,mapping=_row_groups(parts)
        self.assertEqual(len(indices),3)  # 1, i, 1+sqrt(2), and a second 1.
        self.assertNotEqual(mapping[0],mapping[1])
        self.assertEqual(mapping[0],mapping[3])

    def test_limb_exactness_at_proved_partial_sum_bound(self):
        for k in (1,3,63,128,317):
            width=(52-(k-1).bit_length())//2
            largest=(1 << width)-1
            a=np.full((2,k),largest,dtype=object)
            a[1,::2]*=-1
            b=np.full((k,2),largest,dtype=object)
            b[::2,1]*=-1
            za=np.zeros(a.shape,dtype=object);zb=np.zeros(b.shape,dtype=object)
            counter=budget()
            result=_limb_product((a,za,za,za),(b,zb,zb,zb),counter)
            self.assertTrue(np.array_equal(result[0],a @ b))
            self.assertLess(counter.stats['peak_integer_partial_sum_bound'],1 << 52)

    def test_work_allocation_and_coefficient_guards(self):
        a=IntegerMatrix.from_sparse({(i,i):DONE for i in range(3)},(3,3))
        with self.assertRaises(ResourceLimit):a.matmul(a,budget(max_work=1),reuse=True)
        with self.assertRaises(ResourceLimit):a.matmul(a,budget(max_coefficients=8),reuse=True)
        big=IntegerMatrix.from_sparse({(0,0):Dyadic(127)},(1,1))
        with self.assertRaises(ResourceLimit):big.matmul(big,budget(max_coefficient_bits=8),reuse=True)


class StreamingTests(unittest.TestCase):
    def test_site_factors_match_original_shared_history_exactly(self):
        rng=random.Random(117)
        for trial in range(12):
            c=CompactCircuit(4)
            links=rng.sample(range(3),3)
            for step in range(12):
                q=rng.randrange(4)
                c.add(rng.choice(('h','t','tdg','sx','sxdg','y','r')),q)
                if step%4 == 3:
                    q=links[step//4];qs=(q,q+1) if rng.randrange(2) else (q+1,q)
                    c.add(rng.choice(('cx','cz','ch','cs','ct','swap')),*qs)
            full=_StateFactors(4,budget());full.run(c.operations)
            for q,plan in enumerate(_plans(4,c.operations)):
                matrices,_=_site(plan,budget())
                self.assertEqual([m.entries() for m in matrices],full.sites[q])
                self.assertEqual(matrices[0].shape,(full.bonds[q],full.bonds[q+1]))

    def test_random_probabilities_and_complex_expectations_match_exact_algorithms(self):
        for seed in (12,117,20261018):
            c=brickwork(5,4,seed)
            for target in ({0:1},{0:0,4:1},{}):
                value=probability(c,target,contraction='streaming').value
                self.assertEqual(value,probability(c,target).value)
                self.assertEqual(value,probability(c,target,contraction='sparse').value)
            target={0:'Y',2:'X',4:'Z'}
            value=expectation(c,target,contraction='streaming').value
            self.assertEqual(value,expanded_expectation(c,target).value)

    def test_all_control_orientations_and_swap(self):
        for gate in ('cx','cz','ch','cs','ct','swap'):
            for qs in ((0,1),(1,0)):
                c=CompactCircuit(2).add('h',0).add('t',0).add('sx',1).add(gate,*qs).add('h',1)
                for target in ({0:'X',1:'Y'},{0:'Y',1:'Z'},{0:'Z'}):
                    self.assertEqual(expectation(c,target,contraction='streaming',product_suffix=False).value,
                                     expanded_expectation(c,target).value)

    def test_zero_identity_phase_and_disconnected_cones(self):
        for c,target,expected in (
                (CompactCircuit(50),{},ONE),
                (CompactCircuit(4),{2:1},ZERO),
                (CompactCircuit(2).add('h',0).add('t',0).add('h',0),{0:0},Exact(Fraction(1,2),Fraction(1,4)))):
            self.assertEqual(probability(c,target,contraction='streaming').value,expected)
        self.assertEqual(expectation(CompactCircuit(2).add('h',0),{0:'Z'},contraction='streaming').value,ZERO)
        c=brickwork(8,2,17)
        for prune in (False,True):
            for suffix in (False,True):
                self.assertEqual(probability(c,{0:1,7:0},contraction='streaming',
                                             causal_pruning=prune,product_suffix=suffix).value,
                                 probability(c,{0:1,7:0}).value)

    def test_frozen_50_qubit_answer(self):
        value=probability(brickwork(50,8,20261018),{24:0,25:0},contraction='streaming')
        self.assertEqual(value.value,Exact(Fraction(35102818810449,140737488355328),
                                          -Fraction(54100655,34359738368)))
        self.assertEqual(value.statistics['peak_live_site_factors'],1)
        self.assertEqual(value.statistics['site_factors_constructed'],value.statistics['active_qubits'])

    def test_lower_live_coefficient_requirement_for_disjoint_bells(self):
        c=CompactCircuit(50)
        for q in range(0,50,2):c.add('h',q).add('cx',q,q+1)
        options=dict(max_coefficients=16,product_suffix=False)
        with self.assertRaises(ResourceLimit):expectation(c,{q:'Z' for q in range(50)},**options)
        result=expectation(c,{q:'Z' for q in range(50)},contraction='streaming',**options)
        self.assertEqual(result.value,ONE)
        self.assertLessEqual(result.statistics['peak_stored_coefficients'],4)

    def test_all_resource_failures_and_invalid_circuits_return_no_value(self):
        c=brickwork(6,4,1)
        for limits in ({'max_bond':1},{'max_work':1},{'max_coefficients':1},{'max_coefficient_bits':2}):
            with self.assertRaises(ResourceLimit) as error:
                probability(c,{2:0,3:0},contraction='streaming',product_suffix=False,**limits)
            self.assertNotIn('value',error.exception.statistics)
        with self.assertRaises(ValueError):probability(CompactCircuit(3).add('cx',0,2),{},contraction='streaming')
        with self.assertRaises(ValueError):probability(CompactCircuit(3).add('ccx',0,1,2),{},contraction='streaming')

    def test_low_bit_cap_uses_canonical_values_before_rejection(self):
        c=CompactCircuit(2)
        for _ in range(20):c.add('h',0).add('h',0)
        value=probability(c,{0:0},contraction='streaming',product_suffix=False,max_coefficient_bits=2)
        self.assertEqual(value.value,ONE)
        self.assertGreater(value.statistics['peak_site_coefficient_bit_bound'],2)

    def test_calculator_selection_hash_distribution_and_budget(self):
        doc=dict(schema='nrqc-calculator-v1',n_qubits=2,operations=[['h',[0]],['cx',[0,1]]],
                 queries=[dict(id='law',kind='distribution',qubits=[0,1])])
        original=calculate(doc)
        streamed=calculate({**doc,'contraction':'streaming','limits':{'max_work':300_000_000}})
        self.assertEqual(streamed['status'],'completed')
        self.assertEqual(streamed['answers'][0]['probabilities'],original['answers'][0]['probabilities'])
        self.assertEqual(original['circuit_sha256'],streamed['circuit_sha256'])
        self.assertNotEqual(original['request_sha256'],streamed['request_sha256'])
        self.assertEqual(calculate({**doc,'contraction':'integer'})['request_sha256'],original['request_sha256'])
        for options in ({'contraction':'auto'},{'contraction':'streaming','backend':'observer'},
                        {'contraction':True},{'limits':{'max_work':1_000_000_001}}):
            with self.assertRaises((ValueError,TypeError)):validate({**doc,**options})
        self.assertEqual(run_calculation({**doc,'contraction':'streaming'})['status'],'completed')

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional Qiskit reference')
    def test_independent_dense_statevector(self):
        from qiskit.quantum_info import Statevector,Pauli
        from native_relational_qc.compact_qiskit import to_qiskit
        for n,seed in ((4,117),(6,20261018),(8,20261019)):
            c=brickwork(n,5,seed)
            reference=Statevector.from_instruction(to_qiskit(c))
            value=probability(c,{0:0,n-1:1},contraction='streaming').value
            self.assertLess(abs(complex(value).real-reference.probabilities([0,n-1])[2]),1e-13)
            target={q:'XYZ'[q%3] for q in range(n)}
            pauli=Pauli(''.join(target[q] for q in reversed(range(n))))
            value=expectation(c,target,contraction='streaming').value
            self.assertLess(abs(complex(value)-reference.expectation_value(pauli)),1e-13)


if __name__=='__main__':unittest.main()
