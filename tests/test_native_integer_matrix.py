from fractions import Fraction
import random
import unittest

from native_relational_qc.compact import CompactCircuit, ResourceLimit
from native_relational_qc.dyadic import Dyadic, DONE
from native_relational_qc.exact import Exact, ZERO, ONE
from native_relational_qc.factored import _Budget, _StateFactors, expectation, probability
from native_relational_qc.integer_matrix import IntegerMatrix
from native_relational_qc.observer import expectation as expanded_expectation
from native_relational_qc.stress_benchmark import brickwork


def budget(**options):
    args = dict(max_bond=256,max_coefficients=1000000,max_work=100000000,
                max_coefficient_bits=4096,progress=None)
    args.update(options)
    return _Budget(**args)


class IntegerMatrixTests(unittest.TestCase):
    def assert_product(self, left, right, shape):
        m,k,n = shape
        a = IntegerMatrix.from_sparse(left,(m,k))
        b = IntegerMatrix.from_sparse(right,(k,n))
        actual = a.matmul(b,budget()).entries()
        for i in range(m):
            for j in range(n):
                reference = ZERO
                for t in range(k):
                    reference += left.get((i,t),Dyadic()).to_exact()*right.get((t,j),Dyadic()).to_exact()
                self.assertEqual(actual.get((i,j),Dyadic()).to_exact(),reference)

    def test_all_basis_products_and_signs(self):
        basis = [Dyadic(1),Dyadic(b=1),Dyadic(c=1),Dyadic(d=1)]
        for a in basis:
            for b in basis:
                for sign in (1,-1):
                    self.assert_product({(0,0):a},{(0,0):b if sign==1 else -b},(1,1,1))

    def test_rectangular_products_with_mixed_denominators(self):
        rng = random.Random(232610)
        for m,k,n in [(1,7,3),(3,5,2),(4,1,5),(2,9,2)]:
            for _ in range(8):
                def entries(rows,cols):
                    return {(i,j):Dyadic(*(rng.randrange(-100,101) for _ in range(4)),rng.randrange(15))
                            for i in range(rows) for j in range(cols) if rng.randrange(3)}
                self.assert_product(entries(m,k),entries(k,n),(m,k,n))

    def test_large_negative_coefficients_and_carry_bound(self):
        # Large exact integers exercise signed packing and cancellation; a
        # fixed-width integer or floating-point implementation cannot pass.
        big = (1 << 350)+117
        left = {(i,j):Dyadic(big,-big,big-1,-big-3,j%7)
                for i in range(2) for j in range(13)}
        right = {(i,j):Dyadic(-big,big-5,-big+1,big+3,i%5)
                 for i in range(13) for j in range(3)}
        self.assert_product(left,right,(2,13,3))

    def test_exact_cancellation_and_zero_products(self):
        v = Dyadic(7,-11,13,17,8)
        self.assert_product({(0,0):v,(0,1):-v},{(0,0):v,(1,0):v},(1,2,1))
        self.assert_product({}, {(1,2):v}, (2,3,4))
        self.assert_product({(1,2):v}, {}, (2,3,4))

    def test_adjoint_and_scale_preserve_phase(self):
        entries = {(0,0):Dyadic(2,3,-5,7,4),(1,0):Dyadic(1,-2,4,6,7)}
        matrix = IntegerMatrix.from_sparse(entries,(2,1))
        scalar = Dyadic(-3,2,1,-5,3)
        adjoint = matrix.adjoint().entries()
        scaled = matrix.scale(scalar).entries()
        for (i,j),v in entries.items():
            self.assertEqual(adjoint[j,i].to_exact(),v.to_exact().conjugate())
            self.assertEqual(scaled[i,j].to_exact(),v.to_exact()*scalar.to_exact())
        self.assertEqual(matrix.add(matrix.scale(Dyadic(-1))).entries(),{})

    def test_preallocation_work_and_coefficient_limits(self):
        matrix = IntegerMatrix.from_sparse({(0,0):DONE},(3,3))
        for limits in ({'max_work':26},{'max_coefficients':8}):
            with self.assertRaises(ResourceLimit) as failure:
                matrix.matmul(matrix,budget(**limits))
            self.assertNotIn('value',failure.exception.statistics)
        with self.assertRaises(ResourceLimit):
            IntegerMatrix.from_sparse({(0,0):Dyadic(127)},(1,1)).matmul(
                IntegerMatrix.from_sparse({(0,0):Dyadic(127)},(1,1)),budget(max_coefficient_bits=8))

    def test_shape_mismatch_is_rejected(self):
        a= IntegerMatrix.from_sparse({},(2,3))
        b= IntegerMatrix.from_sparse({},(2,2))
        with self.assertRaises(ValueError):a.matmul(b,budget())
        with self.assertRaises(ValueError):a.add(b)


class IntegerContractionTests(unittest.TestCase):
    def test_integer_sparse_and_expanded_observers_agree_exactly(self):
        for seed in (117,20261018,20261019):
            circuit = brickwork(5,4,seed)
            for query in ({0:'Y',2:'X',4:'Z'},{q:'Z' for q in range(5)}):
                integer = expectation(circuit,query,contraction='integer').value
                self.assertEqual(integer,expectation(circuit,query,contraction='sparse').value)
                self.assertEqual(integer,expanded_expectation(circuit,query).value)

    def test_all_supported_controls_both_directions_and_swap(self):
        for gate in ('cx','cz','ch','cs','ct','swap'):
            for qs in ((0,1),(1,0)):
                circuit = (CompactCircuit(2).add('h',0).add('t',0).add('sx',1)
                           .add(gate,*qs).add('tdg',1).add('h',0))
                for query in ({0:'X',1:'Y'},{0:'Y',1:'Z'},{0:'I',1:'X'}):
                    self.assertEqual(expectation(circuit,query,product_suffix=False).value,
                                     expanded_expectation(circuit,query).value)

    def test_frozen_50_qubit_answer_and_native_backend_diagnostics(self):
        result = probability(brickwork(50,8,20261018),{24:0,25:0})
        self.assertEqual(result.value,Exact(Fraction(35102818810449,140737488355328),
                                            -Fraction(54100655,34359738368)))
        self.assertEqual(result.statistics['contraction'],'integer')
        self.assertGreater(result.statistics['integer_matrix_products'],0)
        self.assertFalse(result.to_dict()['statevector_constructed'])

    def test_cached_site_budget_matches_full_storage_scan(self):
        meter=budget()
        state=_StateFactors(4,meter)
        operations=[('h',(0,)),('ct',(0,1)),('sx',(1,)),('cx',(1,2)),
                    ('t',(3,)),('h',(2,)),('cz',(2,3)),('sxdg',(0,))]
        peak_count,peak_bits=4,1
        for operation in operations:
            state.run([operation])
            entries=[v for site in state.sites for matrix in site for v in matrix.values()]
            peak_count=max(peak_count,len(entries))
            peak_bits=max(peak_bits,max(v.max_bits for v in entries))
            self.assertEqual(meter.stats['peak_stored_coefficients'],peak_count)
            self.assertEqual(meter.stats['max_coefficient_bits'],peak_bits)
        with self.assertRaises(ResourceLimit):_StateFactors(5,budget(max_coefficients=4))

    def test_invalid_contraction_and_budget_fail_without_answer(self):
        with self.assertRaises(ValueError):expectation(CompactCircuit(1),{},contraction='float')
        circuit = brickwork(8,4,117)
        with self.assertRaises(ResourceLimit) as failure:
            probability(circuit,{3:0,4:0},max_work=100)
        self.assertNotIn('value',failure.exception.statistics)


if __name__=='__main__':unittest.main()
