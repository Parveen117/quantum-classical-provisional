from fractions import Fraction
import importlib.util
import random
import unittest

from native_relational_qc.compact import CompactCircuit, ResourceLimit
from native_relational_qc.exact import Exact, ONE, ZERO, HALF, INV_SQRT2
from native_relational_qc.observer import probability, expectation


class ObserverTests(unittest.TestCase):
    def test_exact_interference(self):
        c=CompactCircuit(1).add('h',0).add('t',0).add('h',0)
        r=probability(c,{0:0})
        self.assertEqual(r.value,Exact(Fraction(1,2),Fraction(1,4)))
        self.assertEqual(r.peak_terms,3)
        self.assertEqual(expectation(c,{0:'Z'}).value,INV_SQRT2)

    def test_source_boundary_is_not_applied_early(self):
        c=CompactCircuit(1).add('h',0)
        self.assertEqual(expectation(c,{0:'X'}).value,ONE)
        self.assertEqual(expectation(c,{0:'Z'}).value,ZERO)

    def test_bell_joint_and_y_observers(self):
        c=CompactCircuit(2).add('h',0).add('cx',0,1)
        self.assertEqual(probability(c,{0:0,1:0}).value,HALF)
        self.assertEqual(probability(c,{0:1,1:0}).value,ZERO)
        self.assertEqual(expectation(c,{0:'X',1:'X'}).value,ONE)
        self.assertEqual(expectation(c,{0:'Y',1:'Y'}).value,-ONE)

    def test_exact_cancellation(self):
        c=CompactCircuit(1).add('h',0).add('t',0).add('tdg',0).add('h',0)
        self.assertEqual(probability(c,{0:0}).value,ONE)
        self.assertEqual(probability(c,{}).value,ONE)

    def test_joint_observer_invariant_when_terms_are_permuted(self):
        # H0 sends Z0 to X0; CZ then swaps X0 and X0 Z1 in this projector.
        c=CompactCircuit(2).add('cz',0,1).add('h',0)
        r=probability(c,{0:0,1:0})
        self.assertEqual(r.value,HALF)
        self.assertEqual(r.gates_proved_invariant,1)

    def test_128_qubit_full_support_entangled_family(self):
        c=CompactCircuit(128)
        for q in range(128):c.add('h',q).add('t',q)
        for q in range(127):c.add('cz',q,q+1)
        c.add('h',0)
        r=probability(c,{0:0,1:0})
        self.assertEqual(r.value,Exact(Fraction(1,4),Fraction(1,8)))
        self.assertLessEqual(r.peak_terms,6)
        self.assertFalse(r.to_dict()['statevector_constructed'])

    def test_fail_closed_budgets(self):
        c=CompactCircuit(1).add('h',0).add('t',0).add('h',0)
        with self.assertRaises(ResourceLimit):expectation(c,{0:'Z'},max_terms=1)
        with self.assertRaises(ResourceLimit):probability(c,{0:0},max_work=1)
        with self.assertRaises(ResourceLimit):probability(CompactCircuit(8),{q:0 for q in range(8)},max_terms=8)
        with self.assertRaises(ResourceLimit):probability(CompactCircuit(5),{q:0 for q in range(5)},max_coefficient_bits=4)


@unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional Qiskit SDK not installed')
class ObserverReferenceTests(unittest.TestCase):
    def test_seeded_nonclifford_pauli_queries(self):
        from qiskit.quantum_info import Statevector, Pauli
        from native_relational_qc.compact_qiskit import to_qiskit
        rng=random.Random(731)
        for n in range(1,6):
            for trial in range(6):
                c=CompactCircuit(n)
                for step in range(15):
                    if n>1 and step%3==0:
                        c.add(rng.choice(('cx','cz','ch','ct')), *rng.sample(range(n),2))
                    else:c.add(rng.choice(('h','t','sx','y','r','k','tdg')),rng.randrange(n))
                reference=Statevector.from_instruction(to_qiskit(c))
                query={q:rng.choice('XYZ') for q in range(n)}
                label=''.join(query[q] for q in reversed(range(n)))
                answer=expectation(c,query).value
                self.assertAlmostEqual(complex(answer).real,float(reference.expectation_value(Pauli(label)).real),places=12)
                answer=probability(c,{0:1}).value
                self.assertAlmostEqual(complex(answer).real,float(reference.probabilities([0])[1]),places=12)

    def test_toffoli_and_swap_queries(self):
        from qiskit.quantum_info import Statevector, Pauli
        from native_relational_qc.compact_qiskit import to_qiskit
        c=CompactCircuit(3).add('h',0).add('h',1).add('t',0).add('ccx',0,1,2).add('swap',0,2)
        reference=Statevector.from_instruction(to_qiskit(c))
        for query,label in (({0:'X',1:'Z',2:'Y'},'YZX'),({0:'Z',2:'Z'},'ZIZ')):
            self.assertAlmostEqual(complex(expectation(c,query).value).real,
                                   float(reference.expectation_value(Pauli(label)).real),places=12)


if __name__=='__main__':unittest.main()
