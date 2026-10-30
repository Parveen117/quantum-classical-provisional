import importlib.util
from fractions import Fraction
import random
import unittest

from native_relational_qc.compact import CompactCircuit, ResourceLimit
from native_relational_qc.dyadic import Dyadic
from native_relational_qc.exact import Exact,ONE,HALF,ZERO
from native_relational_qc.factored import probability,expectation,_suffix,_Budget
from native_relational_qc.observer import probability as expanded_probability
from native_relational_qc.stress_benchmark import brickwork


class DyadicTests(unittest.TestCase):
    def test_arithmetic_matches_general_field(self):
        rng=random.Random(117)
        for _ in range(100):
            a,b=[Exact(*(Fraction(rng.randint(-12,12),2**rng.randrange(6)) for _ in range(4))) for j in range(2)]
            da,db=Dyadic.from_exact(a),Dyadic.from_exact(b)
            self.assertEqual((da+db).to_exact(),a+b)
            self.assertEqual((da-db).to_exact(),a-b)
            self.assertEqual((da*db).to_exact(),a*b)
            self.assertEqual(da.conjugate().to_exact(),a.conjugate())

    def test_canonical_and_rejected_inputs(self):
        self.assertEqual(Dyadic(4,-8,0,12,2),Dyadic(1,-2,0,3))
        self.assertEqual(Dyadic(0,0,0,0,20),Dyadic())
        with self.assertRaises(ValueError):Dyadic.from_exact(Exact(Fraction(1,3)))
        with self.assertRaises(TypeError):Dyadic(0.5)


class FactoredTests(unittest.TestCase):
    def test_bell_and_order_sensitive_interference(self):
        c=CompactCircuit(2).add('h',0).add('cx',0,1)
        self.assertEqual(probability(c,{0:0,1:0}).value,HALF)
        self.assertEqual(expectation(c,{0:'Y',1:'Y'}).value,-ONE)
        c=CompactCircuit(1).add('h',0).add('t',0).add('h',0)
        self.assertEqual(probability(c,{0:0}).value,Exact(Fraction(1,2),Fraction(1,4)))
        wrong=CompactCircuit(1).add('t',0).add('h',0).add('h',0)
        self.assertEqual(probability(wrong,{0:0}).value,ONE)

    def test_suffix_factorization_of_actual_failed_50_qubit_case(self):
        c=brickwork(50,4,20261018)
        budget=_Budget(256,1000000,10000000,4096,None)
        remaining,factors=_suffix(list(c.operations),[{(0,1):ONE} for _ in range(50)],budget)
        self.assertEqual(len(c.operations)-len(remaining),174)
        self.assertEqual(budget.stats['prefix_expanded_terms'],2**50)
        self.assertEqual(sum(map(len,factors)),100)

    def test_complete_exact_matches_expanded(self):
        for seed in (12,31,52):
            c=brickwork(5,3,seed)
            for query in ({0:0,2:1},{1:1},{}):
                self.assertEqual(probability(c,query).value,expanded_probability(c,query).value)

    def test_ablation_and_causal_pruning_preserve_value(self):
        c=brickwork(6,3,19)
        v=probability(c,{2:0,3:0}).value
        self.assertEqual(v,probability(c,{2:0,3:0},causal_pruning=False).value)
        self.assertEqual(v,probability(c,{2:0,3:0},product_suffix=False).value)
        self.assertEqual(v,probability(c,{2:0,3:0},product_suffix=False,causal_pruning=False).value)

    def test_identity_and_impossible_readout(self):
        c=CompactCircuit(50)
        self.assertEqual(probability(c,{}).value,ONE)
        self.assertEqual(probability(c,{12:1}).value,ZERO)
        self.assertEqual(expectation(c,{}).value,ONE)

    def test_resource_limits_fail_with_statistics(self):
        c=brickwork(6,4,1)
        for options in ({'max_bond':1,'product_suffix':False},{'max_work':1},
                        {'max_coefficients':1},{'max_coefficient_bits':2,'product_suffix':False}):
            with self.assertRaises(ResourceLimit) as error:probability(c,{0:0,1:0},**options)
            self.assertIn('event',error.exception.statistics)
            self.assertNotIn('value',error.exception.statistics)

    def test_unsupported_and_invalid_inputs_fail(self):
        with self.assertRaises(ValueError):expectation(CompactCircuit(3).add('cz',0,2),{0:'Z'})
        with self.assertRaises(ValueError):probability(CompactCircuit(3).add('ccx',0,1,2),{})
        with self.assertRaises(ValueError):probability(CompactCircuit(2),{0:2})
        with self.assertRaises(ValueError):expectation(CompactCircuit(2),{0:'A'})


@unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional Qiskit SDK not installed')
class FactoredReferenceTests(unittest.TestCase):
    def test_control_orientation_and_complex_readouts(self):
        from qiskit.quantum_info import Statevector,Pauli
        from native_relational_qc.compact_qiskit import to_qiskit
        rng=random.Random(20261018)
        for n in (2,3,4,5):
            for trial in range(4):
                c=CompactCircuit(n)
                for step in range(10):
                    q=rng.randrange(n)
                    c.add(rng.choice(('h','t','tdg','sx','sxdg','r','y')),q)
                    if step%3==0:
                        q=rng.randrange(n-1);qs=(q,q+1) if step%2 else (q+1,q)
                        c.add(rng.choice(('cx','cz','ch','cs','ct')),*qs)
                state=Statevector.from_instruction(to_qiskit(c))
                query={q:rng.choice('XYZ') for q in range(n)}
                label=''.join(query[q] for q in reversed(range(n)))
                value=expectation(c,query).value
                self.assertAlmostEqual(complex(value).real,float(state.expectation_value(Pauli(label)).real),places=12)
                value=probability(c,{0:1,n-1:0}).value
                self.assertAlmostEqual(complex(value).real,float(state.probabilities([0,n-1])[1]),places=12)

    def test_adjacent_swap(self):
        from qiskit.quantum_info import Statevector,Pauli
        from native_relational_qc.compact_qiskit import to_qiskit
        c=CompactCircuit(3).add('h',0).add('t',0).add('cx',0,1).add('swap',1,2).add('sx',1)
        reference=Statevector.from_instruction(to_qiskit(c))
        self.assertAlmostEqual(complex(expectation(c,{0:'X',2:'X'},product_suffix=False).value).real,
                               float(reference.expectation_value(Pauli('XIX')).real),places=12)


if __name__=='__main__':unittest.main()
