"""Finite algebra and analytic-program checks; no hardware or random shots."""
import json
import unittest

import numpy as np
from numpy.testing import assert_allclose

from native_relational_qc import Circuit, RelationalState, I, K, R, RK, controlled, emk, gate
from native_relational_qc.examples import bell, ghz, bernstein_vazirani, grover_11, order_memory


class AlgebraTests(unittest.TestCase):
    def test_native_relations(self):
        assert_allclose(R @ R, -I, atol=1e-14)
        assert_allclose(K @ K, I, atol=1e-14)
        assert_allclose(R @ K, -K @ R, atol=1e-14)
        assert_allclose(RK, gate("x"), atol=1e-14)
        assert_allclose((K + RK) / np.sqrt(2), gate("h"), atol=1e-14)

    def test_all_named_gates_are_unitary(self):
        for name in ("id", "r", "k", "rk", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx", "swap"):
            u = gate(name)
            assert_allclose(u.conj().T @ u, np.eye(len(u)), atol=1e-14)
        for name in ("rx", "ry", "rz", "rzz", "p"):
            u = gate(name, 0.731)
            assert_allclose(u.conj().T @ u, np.eye(len(u)), atol=1e-14)

    def test_nonunitary_emk_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonunitary"):
            emk(a=np.cosh(0.3), b=np.sinh(0.3))
        assert_allclose(emk(b=1), K)

    def test_gate_validation(self):
        for matrix in (np.zeros((2, 2)), [[1, 0, 0]], [[np.nan, 0], [0, 1]], np.eye(3)):
            with self.assertRaises(ValueError):
                Circuit(2).append(matrix, [0])
        with self.assertRaises(ValueError):
            gate("rz", np.inf)
        with self.assertRaises(ValueError):
            Circuit(2).add("cx", 0, 1, theta=0.2)

    def test_operator_phase_survives_control(self):
        plus = Circuit(2).add("h", 0).control(I, 0, 1).add("h", 0)
        minus = Circuit(2).add("h", 0).control(-I, 0, 1).add("h", 0)
        self.assertAlmostEqual(plus.probabilities()["00"], 1)
        self.assertAlmostEqual(minus.probabilities()["01"], 1)
        self.assertAlmostEqual(order_memory().probabilities()["01"], 1)
        self.assertAlmostEqual(order_memory(erase=True).probabilities()["00"], 1)


class StateTests(unittest.TestCase):
    def test_common_complex_scale_invariant(self):
        state = RelationalState([1, 2j, -3, 1 + 1j])
        scaled = RelationalState((3 - 2j) * state.amplitudes)
        self.assertAlmostEqual(state.overlap(scaled), 1)
        assert_allclose(state.chart()[1], scaled.chart()[1], atol=1e-14)

    def test_large_and_small_scales(self):
        for scale in (1e-300, 1e300):
            state = RelationalState(np.array([1, 1j]) * scale)
            assert_allclose(list(state.probabilities().values()), [0.5, 0.5])

    def test_second_chart_covers_zero_first_amplitude(self):
        state = RelationalState([0, 1j])
        self.assertEqual(state.chart()[0], 1)
        assert_allclose(state.chart()[1], [0, 1])
        with self.assertRaises(ValueError):
            state.chart(0)

    def test_invalid_states_and_dimensions(self):
        for values in ([0, 0], [1, 0, 0], [1, np.inf], [[1, 0]], [1]):
            with self.assertRaises(ValueError):
                RelationalState(values)
        for n in (0, -1, 1.5, True, 21):
            with self.assertRaises(ValueError):
                RelationalState.zero(n)

    def test_tensor_register_order(self):
        low = RelationalState([0, 1])
        high = RelationalState([1, 0])
        self.assertAlmostEqual(low.tensor(high).probabilities()["01"], 1)

    def test_joint_state_keeps_entanglement(self):
        values = bell().state().amplitudes.reshape(2, 2)
        singular = np.linalg.svd(values, compute_uv=False)
        assert_allclose(singular, [1 / np.sqrt(2)] * 2)

    def test_unitary_preserves_relational_overlap(self):
        left = RelationalState([1, 1j, 0.5, -2])
        right = RelationalState([-1, 2, 0.2j, 1])
        circuit = Circuit(2).add("ry", 1, theta=0.42).add("cx", 1, 0).add("rzz", 0, 1, theta=-0.9)
        self.assertAlmostEqual(left.overlap(right), circuit.state(left).overlap(circuit.state(right)))

    def test_state_access_does_not_mutate_original(self):
        state = RelationalState([1, 0])
        copy = state.amplitudes
        copy[0] = 0
        self.assertEqual(state.probabilities()["0"], 1)


class CircuitTests(unittest.TestCase):
    def test_bell_observers(self):
        for basis, expected in (("ZZ", [0.5, 0, 0, 0.5]), ("XX", [0.5, 0, 0, 0.5]),
                                ("YY", [0, 0.5, 0.5, 0]), ("ZX", [0.25] * 4)):
            assert_allclose(list(bell(basis).probabilities().values()), expected, atol=1e-14)

    def test_analytic_algorithm_answers(self):
        probabilities = ghz(5).probabilities()
        self.assertAlmostEqual(probabilities["00000"], 0.5)
        self.assertAlmostEqual(probabilities["11111"], 0.5)
        for secret in ("0", "1", "1011", "00101"):
            self.assertAlmostEqual(bernstein_vazirani(secret).probabilities()[secret], 1)
        self.assertAlmostEqual(grover_11().probabilities()["11"], 1)

    def test_control_and_target_order(self):
        for control, target, initial_index, answer in ((0, 2, 1, "101"), (2, 0, 4, "101"),
                                                        (1, 2, 2, "110")):
            initial = np.eye(8)[initial_index]
            out = Circuit(3).add("cx", control, target).probabilities(RelationalState(initial))
            self.assertAlmostEqual(out[answer], 1)

    def test_partial_nontrivial_classical_map(self):
        circuit = Circuit(3, 4).add("x", 0).measure(0, 2).measure(2, 0)
        self.assertAlmostEqual(circuit.probabilities()["0100"], 1)
        partial = Circuit(2, 1).add("h", 0).add("cx", 0, 1).measure(1, 0)
        assert_allclose(list(partial.probabilities().values()), [0.5, 0.5])

    def test_invalid_operation_and_measurement(self):
        for qargs in ((0, 0), (-1, 1), (0, 2)):
            with self.assertRaises(ValueError):
                Circuit(2).add("cx", *qargs)
        with self.assertRaises(ValueError):
            Circuit(2).append(I, [0, 1])
        with self.assertRaises(ValueError):
            Circuit(2).measure_all().add("x", 0)
        with self.assertRaises(ValueError):
            Circuit(2, 2).measure(0, 0).measure(1, 0)
        with self.assertRaises(ValueError):
            Circuit(2).state(RelationalState.zero(1))

    def test_global_phase_is_preserved(self):
        assert_allclose(Circuit(1).phase(np.pi / 3).state().amplitudes,
                        [np.exp(1j * np.pi / 3), 0], atol=1e-14)

    def test_json_roundtrip_and_digest_binding(self):
        circuit = bell("YY").phase(0.31)
        restored = Circuit.from_dict(json.loads(json.dumps(circuit.to_dict())))
        self.assertEqual(circuit.digest(), restored.digest())
        assert_allclose(circuit.state().amplitudes, restored.state().amplitudes)
        changed = circuit.to_dict()
        changed["operations"][0]["qargs"] = [1]
        self.assertNotEqual(circuit.digest(), Circuit.from_dict(changed).digest())
        changed["bit_order"] = "reversed"
        with self.assertRaises(ValueError):
            Circuit.from_dict(changed)

    def test_no_matrix_aliasing(self):
        original = np.array(K)
        circuit = Circuit(1).append(original, [0])
        digest = circuit.digest()
        original[:] = 0
        circuit.operations[0].matrix[:] = 0
        self.assertEqual(digest, circuit.digest())

    def test_control_on_zero(self):
        out = Circuit(2).append(controlled(gate("x"), 0), [0, 1])
        self.assertAlmostEqual(out.probabilities()["10"], 1)

    def test_existing_evidence_model_bridge(self):
        from native_relational_qc.bridge import expected_model
        model = expected_model(bell(), tolerance=0.08)
        self.assertAlmostEqual(model.distribution["00"], 0.5)
        self.assertEqual(model.metadata["evidence_class"], "MODEL_PREDICTION")
        self.assertIsNone(model.metadata["hardware_job_id"])
        for tolerance in (-1, float("nan"), 2):
            with self.assertRaises(ValueError):
                expected_model(bell(), tolerance=tolerance)


if __name__ == "__main__":
    unittest.main()
