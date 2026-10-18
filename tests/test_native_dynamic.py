from fractions import Fraction
import importlib.util
import random
import unittest

from native_relational_qc.compact import ResourceLimit, CompactCircuit
from native_relational_qc.dynamic import DynamicCircuit, probability, expectation
from native_relational_qc.dynamic_examples import teleport, bitflip_recovery, shor_recovery, bell_fidelity
from native_relational_qc.exact import Exact, ZERO, ONE, HALF, INV_SQRT2


class DynamicTests(unittest.TestCase):
    def test_initial_classical_memory_and_empty_query(self):
        c = DynamicCircuit(2, 2)
        self.assertEqual(probability(c).value, ONE)
        self.assertEqual(probability(c, classical={1: 0}).value, ONE)
        self.assertEqual(probability(c, classical={0: 1}).value, ZERO)

    def test_measurement_retains_quantum_classical_correlation(self):
        c = DynamicCircuit(2, 1).add('h', 0).add('cx', 0, 1).measure(0, 0)
        self.assertEqual(probability(c, {1: 1}, {0: 1}).value, HALF)
        self.assertEqual(probability(c, {1: 0}, {0: 1}).value, ZERO)
        self.assertEqual(expectation(c, {0: 'X', 1: 'X'}).value, ZERO)
        self.assertEqual(expectation(c, {1: 'Z'}, classical={0: 1}).value, -HALF)

    def test_measurement_overwrites_old_memory(self):
        c = DynamicCircuit(1, 1).add('h', 0).measure(0, 0).add('x', 0).measure(0, 0)
        self.assertEqual(probability(c, {0: 1}, {0: 1}).value, HALF)
        self.assertEqual(probability(c, {0: 0}, {0: 1}).value, ZERO)
        c.reset(0).measure(0, 0)
        self.assertEqual(probability(c, classical={0: 0}).value, ONE)

    def test_reset_preserves_remote_mixed_state_and_old_record(self):
        c = DynamicCircuit(2, 1).add('h', 0).add('cx', 0, 1).measure(0, 0).reset(0)
        self.assertEqual(probability(c, {0: 0}).value, ONE)
        self.assertEqual(probability(c, {1: 1}, {0: 1}).value, HALF)
        self.assertEqual(expectation(c, {0: 'X', 1: 'X'}).value, ZERO)

    def test_repeated_measurement_and_later_basis_change(self):
        c = DynamicCircuit(1, 2).add('h', 0).measure(0, 0).measure(0, 1).add('h', 0)
        self.assertEqual(probability(c, classical={0: 1, 1: 0}).value, ZERO)
        self.assertEqual(expectation(c, {0: 'X'}, classical={0: 0}).value, HALF)

    def test_feedforward_uses_current_memory_and_zero_condition(self):
        c = DynamicCircuit(1, 1).add('h', 0).measure(0, 0).add('x', 0, condition={0: 1})
        self.assertEqual(probability(c, {0: 0}).value, ONE)
        c.add('x', 0, condition={0: 0})
        self.assertEqual(probability(c, {0: 1}, {0: 0}).value, HALF)

    def test_teleportation_preserves_nonclifford_state_all_branches(self):
        c = teleport()
        for axis, value in [('X', INV_SQRT2), ('Y', INV_SQRT2), ('Z', ZERO)]:
            self.assertEqual(expectation(c, {2: axis}).value, value)
            for a in (0, 1):
                for b in (0, 1):
                    event = {0: a, 1: b}
                    self.assertEqual(probability(c, classical=event).value, Exact(Fraction(1, 4)))
                    self.assertEqual(expectation(c, {2: axis}, classical=event).value, value/Exact(4))
        self.assertEqual(probability(c, {0: 0, 1: 0}).value, ONE)

    def test_teleportation_negative_control(self):
        for axis in 'XYZ':
            self.assertEqual(expectation(teleport(corrections=False), {2: axis}).value, ZERO)

    def test_rational_channels_and_y_signs(self):
        c = DynamicCircuit(1).add('h', 0).pauli_channel(0, {'I': Fraction(3, 4), 'Y': Fraction(1, 4)})
        self.assertEqual(expectation(c, {0: 'X'}).value, HALF)
        c.pauli_channel(0, {'I': HALF.a, 'Z': HALF.a})
        self.assertEqual(expectation(c, {0: 'X'}).value, ZERO)
        self.assertEqual(probability(c).value, ONE)

    def test_bitflip_recovery_exact_noise_and_multiple_rounds(self):
        p = Fraction(1, 10)
        logical_error = 3*p*p - 2*p*p*p
        for rounds in (1, 2, 3):
            value, _ = bell_fidelity(bitflip_recovery(rounds=rounds), 0, 4)
            self.assertEqual(value, Exact((1+(1-2*logical_error)**rounds)/2))
        value, _ = bell_fidelity(bitflip_recovery(corrections=False), 0, 4)
        self.assertEqual(value, Exact(Fraction(9, 10)))

    def test_shor_y_error_and_negative_control(self):
        value, _ = bell_fidelity(shor_recovery((4, 'y')), 0, 10)
        self.assertEqual(value, ONE)
        value, _ = bell_fidelity(shor_recovery((0, 'z'), corrections=False), 0, 10)
        self.assertEqual(value, ZERO)

    def test_long_reused_memory_program_stays_compact(self):
        c = DynamicCircuit(128, 1)
        for _ in range(40):
            c.add('h', 127).measure(127, 0).add('x', 127, condition={0: 1}).reset(127)
        result = probability(c, {127: 0})
        self.assertEqual(result.value, ONE)
        self.assertLessEqual(result.peak_terms, 2)
        self.assertEqual(result.measurements, 40)
        self.assertEqual(result.to_dict()['trajectories_enumerated'], 0)

    def test_budgets_fail_without_modifying_program(self):
        c = teleport()
        before = c.operations
        with self.assertRaises(ResourceLimit): expectation(c, {2: 'Y'}, max_terms=1)
        with self.assertRaises(ResourceLimit): probability(c, max_work=1)
        with self.assertRaises(ResourceLimit): probability(DynamicCircuit(5), {q: 0 for q in range(5)}, max_coefficient_bits=4)
        with self.assertRaises(ResourceLimit): probability(DynamicCircuit(30), {q: 0 for q in range(30)}, max_terms=8)
        wide = DynamicCircuit(1, 30).add('x', 0, condition={q: 0 for q in range(30)})
        with self.assertRaises(ResourceLimit): expectation(wide, {0: 'Z'}, max_terms=8)
        self.assertEqual(c.operations, before)
        self.assertEqual(expectation(c, {2: 'X'}).value, INV_SQRT2)

    def test_reject_invalid_inputs(self):
        for weights in ({'I': .5, 'X': .5}, {'I': 2, 'X': -1}, {'I': Fraction(1, 2)}, {'A': 1}, {'I': True}):
            with self.assertRaises(ValueError): DynamicCircuit(1).pauli_channel(0, weights)
        with self.assertRaises(ValueError): DynamicCircuit(1).measure(0, 0)
        with self.assertRaises(ValueError): DynamicCircuit(1, 1).add('x', 0, condition={0: 2})
        with self.assertRaises(ValueError): DynamicCircuit(1).reset(1)
        with self.assertRaises(ValueError): probability(DynamicCircuit(1), {0: True})
        with self.assertRaises(TypeError): probability(CompactCircuit(1))
        with self.assertRaises(ValueError): expectation(DynamicCircuit(1), {0: 'A'})


@unittest.skipUnless(importlib.util.find_spec('qiskit'), 'optional Qiskit not installed')
class DynamicReferenceTests(unittest.TestCase):
    def test_seeded_dynamic_circuits_against_forward_density_branches(self):
        from native_relational_qc import dynamic_reference as reference
        rng = random.Random(92641)
        for n in range(1, 5):
            for trial in range(8):
                c = DynamicCircuit(n, 3)
                for step in range(18):
                    q = rng.randrange(n)
                    kind = step % 6
                    if kind == 0: c.measure(q, rng.randrange(3))
                    elif kind == 1: c.reset(q)
                    elif kind == 2: c.pauli_channel(q, {'I': Fraction(2, 3), rng.choice('XYZ'): Fraction(1, 3)})
                    elif n > 1 and kind == 3: c.add(rng.choice(('cx', 'ct', 'ch')), *rng.sample(range(n), 2))
                    else:
                        condition = {b: rng.randrange(2) for b in rng.sample(range(3), 2)} if kind == 4 else None
                        c.add(rng.choice(('h', 't', 'sx', 'r', 'y')), q, condition=condition)
                states = reference.branches(c)
                for output in range(8):
                    quantum = {0: output & 1}
                    classical = {0: (output >> 1) & 1, 2: (output >> 2) & 1}
                    actual = complex(probability(c, quantum, classical).value).real
                    expected = reference.probability(c, quantum, classical, evaluated=states)
                    self.assertAlmostEqual(actual, expected, places=12, msg=(n, trial, output))
                paulis = {q: rng.choice('XYZ') for q in range(n)}
                for event in (None, {1: 1}):
                    actual = complex(expectation(c, paulis, classical=event).value).real
                    expected = reference.expectation(c, paulis, event, evaluated=states)
                    self.assertAlmostEqual(actual, expected, places=12)
                self.assertEqual(probability(c).value, ONE)

    def test_noise_recovery_against_forward_density_reference(self):
        from native_relational_qc import dynamic_reference as reference
        c = bitflip_recovery(rounds=3)
        states = reference.branches(c)
        for axis in 'XYZ':
            query = {0: axis, 4: axis}
            self.assertAlmostEqual(complex(expectation(c, query).value).real,
                reference.expectation(c, query, evaluated=states), places=12)

    def test_qiskit_roundtrip_nested_conditions_and_reordered_wires(self):
        from native_relational_qc.dynamic_qiskit import to_qiskit, from_qiskit
        c = teleport().add('cx', 2, 0, condition={0: 0, 1: 1})
        restored = from_qiskit(to_qiskit(c))
        self.assertEqual(restored.operations, c.operations)
        from qiskit import QuantumCircuit
        qc = QuantumCircuit(3, 3)
        qc.h(2)
        qc.measure(2, 1)
        with qc.if_test((qc.cregs[0], 2)):
            qc.x(0)
            with qc.if_test((qc.clbits[2], 0)):
                qc.cx(0, 1)
        imported = from_qiskit(qc)
        self.assertEqual(probability(imported, {0: 1, 1: 1}, {1: 1}).value, HALF)

    def test_qiskit_import_rejects_unsupported_control_flow(self):
        from qiskit import QuantumCircuit
        from native_relational_qc.dynamic_qiskit import from_qiskit
        qc = QuantumCircuit(1, 1)
        with qc.if_test((qc.clbits[0], 1)) as otherwise: qc.x(0)
        with otherwise: qc.h(0)
        with self.assertRaises(ValueError): from_qiskit(qc)
        qc = QuantumCircuit(1, 1)
        with qc.if_test((qc.clbits[0], 1)): qc.reset(0)
        with self.assertRaises(ValueError): from_qiskit(qc)
        qc = QuantumCircuit(1)
        qc.rx(.123, 0)
        with self.assertRaises(ValueError): from_qiskit(qc)

    @unittest.skipUnless(importlib.util.find_spec('qiskit_aer'), 'optional Aer not installed')
    def test_rational_noise_export_against_aer_density(self):
        from qiskit_aer import AerSimulator
        from qiskit.quantum_info import Pauli
        from native_relational_qc.dynamic_qiskit import to_qiskit, from_qiskit
        c = DynamicCircuit(1).add('h', 0).add('t', 0)
        c.pauli_channel(0, {'I': Fraction(3, 4), 'Y': Fraction(1, 4)})
        qc = to_qiskit(c)
        # Import must not infer exact rational probabilities from Aer floats.
        with self.assertRaises(ValueError): from_qiskit(qc)
        for axis in 'XYZ': qc.save_expectation_value(Pauli(axis), [0], label=axis)
        result = AerSimulator(method='density_matrix', max_parallel_threads=1).run(qc, shots=1).result()
        self.assertTrue(result.success)
        for axis in 'XYZ':
            self.assertAlmostEqual(result.data(0)[axis], complex(expectation(c, {0: axis}).value).real, places=12)


if __name__ == '__main__':
    unittest.main()
