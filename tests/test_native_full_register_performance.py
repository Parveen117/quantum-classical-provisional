"""Exact fast paths must retain full-state semantics and resource failures."""
from fractions import Fraction
import random
import unittest

from native_relational_qc.compact import ResourceLimit
from native_relational_qc.cyclotomic_pow2 import field_of_order
from native_relational_qc.phase_backend import Budget,PhaseCircuit,PowerPhaseCircuit,execute


class RootRotationTests(unittest.TestCase):
    def test_signed_rotations_match_integer_reference_in_every_storage_width(self):
        for order in (8,64,4096):
            field=field_of_order(order)
            for magnitude in (0,1,42,127,128,32767,32768,2**31,2**80):
                coefficients=[0]*field.N
                for i,c in ((0,magnitude),(field.N//2,-magnitude),(field.N-1,3*magnitude)):
                    coefficients[i]=c
                value=field._build(coefficients,7)
                original=(value.data,value.item,value.den)
                for exponent in (-2*order-3,-1,0,1,field.N,order-1,3*order+5):
                    expected=[0]*field.N
                    for i,c in enumerate(coefficients):
                        j=(i+exponent)%order
                        expected[j%field.N]+=c if j<field.N else -c
                    rotated=value.times_root(exponent)
                    self.assertEqual(rotated,field._build(expected,7))
                    self.assertEqual(rotated.max_bits,value.max_bits)
                    self.assertEqual((value.data,value.item,value.den),original)

    def test_phase_rotation_enforces_bounds_on_an_external_state(self):
        field=field_of_order(4096)
        circuit=PowerPhaseCircuit(1,4096).add('p4096',0)
        with self.assertRaises(ResourceLimit):
            execute(circuit,{1:field(Fraction(1,2**16))},Budget(max_coefficient_bits=16))
        with self.assertRaises(ResourceLimit):
            execute(circuit,{0:field(1),1:field(1)},Budget(max_branches=1))
        for exponent in (True,1.5):
            with self.assertRaises(TypeError):field(1).times_root(exponent)

    def test_external_field_order_keeps_the_original_embedding_rules(self):
        small,large=field_of_order(64),field_of_order(4096)
        c=PowerPhaseCircuit(1,64).add('p64',0)
        value=large.root(17)/3
        self.assertEqual(execute(c,{1:value},Budget()),{1:value*large.root(64)})
        with self.assertRaises(ValueError):execute(c,{1:field_of_order(8)(1)},Budget())
        h=PowerPhaseCircuit(1,64).add('h',0)
        expected=small(1).times_inv_sqrt2()
        self.assertEqual(execute(h,{0:field_of_order(8)(1)},Budget()),{0:expected,1:expected})


class HadamardProductTests(unittest.TestCase):
    def test_product_crossing_packed_limit_stays_canonical(self):
        field=field_of_order(8)
        value=field._build([2**61+1,1,2**61+2,0],3)
        expected=field._build([1,2**62+3,1,1],6)
        self.assertEqual(value.times_inv_sqrt2(),expected)
        self.assertEqual(expected.item,0)

    def test_all_widths_and_denominators_match_integer_convolution(self):
        rng=random.Random(14112)
        for order in (8,16,128,4096):
            field=field_of_order(order);n=field.N
            for magnitude in (0,1,63,127,32767,2**31,2**61,2**80):
                coefficients=[rng.randrange(-3,4)*magnitude for _ in range(n)]
                for denominator in (3,16):
                    value=field._build(coefficients,denominator)
                    expected=[0]*n
                    for i,c in enumerate(coefficients):
                        for e,sign in ((order//8,1),(3*order//8,-1)):
                            j=(i+e)%order
                            expected[j%n]+=sign*c*(1 if j<n else -1)
                    actual=value.times_inv_sqrt2()
                    self.assertEqual(actual,field._build(expected,2*denominator))
                    self.assertEqual(actual.times_inv_sqrt2()*2,value)


class SparsePairProductTests(unittest.TestCase):
    def test_sparse_products_and_overflow_fallback_match_python_integers(self):
        rng=random.Random(312141)
        for order,support in ((256,8),(256,32),(4096,7),(4096,8),(4096,89),(4096,128),(4096,129)):
            field=field_of_order(order)
            for scale in (1,2**26,2**32,2**80):
                left={i:rng.choice((-3,-1,1,2))*scale for i in rng.sample(range(field.N),support)}
                right={i:rng.choice((-2,-1,1,3))*scale for i in rng.sample(range(field.N),support)}
                expected=[0]*field.N
                for i,a in left.items():
                    for j,b in right.items():
                        k=i+j
                        expected[k%field.N]+=a*b*(1 if k<field.N else -1)
                self.assertEqual(field._from_sparse(left,17)*field._from_sparse(right,19),
                                 field._build(expected,17*19))


class ExecutionBudgetTests(unittest.TestCase):
    def test_fast_paths_match_generic_execution_at_every_work_cutoff(self):
        field=field_of_order(16)
        fast=PowerPhaseCircuit(3,16)
        generic=PhaseCircuit(3)
        generic.field=field
        generic.phase_gates=fast.phase_gates
        for name,sites in (('h',(0,)),('p16',(0,)),('ch',(0,1)),('h',(2,)),
                           ('cp16dg',(2,1)),('h',(0,)),('h',(1,)),('h',(2,))):
            fast.add(name,*sites);generic.add(name,*sites)

        def run(circuit,**limits):
            budget=Budget(**limits)
            try:result=execute(circuit,{0:field(1)},budget)
            except ResourceLimit as error:result=str(error)
            return result,budget.stats

        expected=run(generic)
        self.assertEqual(run(fast),expected)
        for cutoff in range(1,expected[1]['work_used']+1):
            self.assertEqual(run(fast,max_work=cutoff),run(generic,max_work=cutoff))
        for cap in range(1,9):
            self.assertEqual(run(fast,max_branches=cap),run(generic,max_branches=cap))
        for bits in range(2,8):
            self.assertEqual(run(fast,max_coefficient_bits=bits),
                             run(generic,max_coefficient_bits=bits))


if __name__=='__main__':unittest.main()
