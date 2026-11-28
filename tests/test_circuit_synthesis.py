import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from native_relational_qc.calculator import calculate
from native_relational_qc.circuit import Circuit
from native_relational_qc.circuit_synthesis import synthesize
from native_relational_qc.cyclotomic_pow2 import field_of_order
from native_relational_qc.learning_tasks import xor_examples
from native_relational_qc.modular_rewrite import verify_rewrite
from native_relational_qc.phase_backend import PowerPhaseCircuit
from native_relational_qc.self_learning import Evaluator, FIELD as LEARNING_FIELD


FIELD = field_of_order(8)
BELL = dict(schema="nrqc-circuit-goal-v1", n_qubits=2,
            stabilizers=[dict(paulis={"0": "X", "1": "X"}, eigenvalue=1),
                         dict(paulis={"0": "Z", "1": "Z"}, eigenvalue=1)],
            coupling_map=[[0, 1]])


class CircuitSynthesisTests(unittest.TestCase):
    def test_bell_is_built_from_the_goal_and_checked_by_the_calculator(self):
        original = copy.deepcopy(BELL)
        result = synthesize(BELL)
        self.assertEqual(BELL, original)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["calculator_request"]["operations"],
                         [["h", [0]], ["cx", [0, 1]]])
        self.assertEqual([FIELD.from_dict(a["value"]["exact"])
                          for a in result["verification"]["answers"]], [FIELD(1)] * 2)
        pruned = synthesize(dict(BELL, allowed_gates=["x", "z", "cx"]))
        self.assertGreater(pruned["resources"]["rewrite_pruned"], 0)
        for item in pruned["rewrite_examples"]:
            def circuit(operations):
                c = PowerPhaseCircuit(2, 8)
                for name, qs in operations:
                    c.add(name, *qs)
                return c
            self.assertEqual(verify_rewrite(circuit(item["source"]), circuit(item["result"]),
                                            item["certificate"])["status"], "verified")

    def test_relative_phase_is_part_of_the_goal(self):
        minus = copy.deepcopy(BELL)
        minus["stabilizers"][0]["eigenvalue"] = -1
        result = synthesize(minus)
        self.assertEqual(result["status"], "verified")
        report = calculate(dict(result["calculator_request"],
                                queries=[dict(id="phase", kind="expectation",
                                              paulis={"0": "X", "1": "X"}),
                                         dict(id="law", kind="distribution", qubits=[1, 0])]))
        self.assertEqual(FIELD.from_dict(report["answers"][0]["value"]["exact"]), FIELD(-1))
        # Both Bell signs have the same Z-basis probabilities.
        law = report["answers"][1]["probabilities"]
        self.assertEqual(FIELD.from_dict(law["00"]["exact"]), FIELD(1) / 2)
        self.assertEqual(FIELD.from_dict(law["11"]["exact"]), FIELD(1) / 2)

    def test_three_qubit_ghz_obeys_directed_connectivity(self):
        goal = dict(schema=BELL["schema"], n_qubits=3, allowed_gates=["h", "cx"],
                    coupling_map=[[0, 1], [1, 2]],
                    stabilizers=[dict(paulis={"0": "X", "1": "X", "2": "X"}, eigenvalue=1),
                                 dict(paulis={"0": "Z", "1": "Z"}, eigenvalue=1),
                                 dict(paulis={"1": "Z", "2": "Z"}, eigenvalue=1)])
        result = synthesize(goal)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["calculator_request"]["operations"],
                         [["h", [0]], ["cx", [0, 1]], ["cx", [1, 2]]])

    def test_initial_state_can_satisfy_the_goal_with_zero_gates(self):
        goal = dict(schema=BELL["schema"], n_qubits=1,
                    stabilizers=[dict(paulis={"0": "Z"}, eigenvalue=1)],
                    limits=dict(max_gates=0))
        result = synthesize(goal)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["calculator_request"]["operations"], [])

    def test_impossible_gate_alphabet_exhausts_without_a_candidate_circuit(self):
        result = synthesize(dict(BELL, allowed_gates=["x", "z", "cx"]))
        self.assertEqual(result["status"], "search_exhausted")
        self.assertIsNone(result["calculator_request"])
        self.assertIsNone(synthesize(dict(BELL, coupling_map=[]))["calculator_request"])

    def test_declared_resource_limits_do_not_return_partial_circuits(self):
        for limits, expected in [(dict(max_gates=1), "depth_limit"),
                                 (dict(max_candidates=1), "incomplete"),
                                 (dict(max_work=1), "incomplete"),
                                 (dict(max_seconds=1e-12), "incomplete")]:
            with self.subTest(limits=limits):
                result = synthesize(dict(BELL, limits=limits))
                self.assertEqual(result["status"], expected)
                self.assertIsNone(result["calculator_request"])
                if limits == dict(max_work=1):
                    self.assertEqual(result["resources"]["exact_work"], 2)

    def test_rejects_noncommuting_dependent_identity_and_malformed_targets(self):
        invalid = [
            [dict(paulis={"0": "X"}, eigenvalue=1), dict(paulis={"0": "Z"}, eigenvalue=1)],
            [BELL["stabilizers"][0]] * 2,
            [dict(paulis={"0": "I"}, eigenvalue=1), BELL["stabilizers"][1]],
            [dict(paulis={"0": "X", "1": "X"}, eigenvalue=True), BELL["stabilizers"][1]],
        ]
        for stabilizers in invalid:
            with self.subTest(stabilizers=stabilizers), self.assertRaises(ValueError):
                synthesize(dict(BELL, stabilizers=stabilizers))
        for options in [dict(allowed_gates=["magic"]), dict(coupling_map=[[0, 0]]),
                        dict(coupling_map=[[0, 1], [0, 1]]), dict(n_qubits=5),
                        dict(limits={"max_gates": True}), dict(limits={"max_seconds": float("nan")})]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                synthesize(dict(BELL, **options))

    def test_calculator_reverification_is_required_for_success(self):
        with patch("native_relational_qc.circuit_synthesis.calculate",
                   return_value=dict(status="incomplete", answers=[], statistics={})):
            result = synthesize(BELL)
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["calculator_request"])

    def test_y_stabilizer_and_negative_eigenvalues_are_supported(self):
        target = dict(schema=BELL["schema"], n_qubits=2,
                      stabilizers=[dict(paulis={"0": "Y", "1": "Y"}, eigenvalue=-1),
                                   dict(paulis={"0": "Z", "1": "Z"}, eigenvalue=1)])
        result = synthesize(target)
        self.assertEqual(result["status"], "verified")

    def test_real_gate_alphabet_exhausts_for_a_single_y_eigenstate(self):
        goal = dict(schema=BELL["schema"], n_qubits=1,
                    stabilizers=[dict(paulis={"0": "Y"}, eigenvalue=1)])
        result = synthesize(goal)
        self.assertEqual(result["status"], "search_exhausted")
        self.assertIsNone(result["calculator_request"])

    def test_four_qubit_ghz_matches_the_independent_numpy_circuit(self):
        goal = dict(schema=BELL["schema"], n_qubits=4, allowed_gates=["h", "cx"],
                    coupling_map=[[0, 1], [1, 2], [2, 3]],
                    stabilizers=[dict(paulis={str(q): "X" for q in range(4)}, eigenvalue=1)] +
                    [dict(paulis={str(q): "Z", str(q + 1): "Z"}, eigenvalue=1)
                     for q in range(3)])
        result = synthesize(goal)
        self.assertEqual(result["status"], "verified")
        circuit = Circuit(4)
        for name, wires in result["calculator_request"]["operations"]:
            circuit.add(name, *wires)
        target = np.zeros(16, dtype=complex)
        target[0] = target[-1] = 1 / np.sqrt(2)
        np.testing.assert_allclose(circuit.state().amplitudes, target, atol=1e-14, rtol=0)

    def test_existing_self_learning_predictions_remain_exact(self):
        evaluator = Evaluator()
        for row in xor_examples():
            self.assertEqual(evaluator.probability(row.features, (0,) * 5),
                             LEARNING_FIELD(row.target))

    def test_cli_uses_the_normal_entry_point_and_exports_a_calculator_request(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "goal.json"
            output = Path(folder) / "result.json"
            source.write_text(json.dumps(BELL), encoding="utf-8")
            process = subprocess.run([sys.executable, "-m", "native_relational_qc", "synthesize",
                                      str(source), "--out", str(output)],
                                     text=True, capture_output=True, check=True)
            result = json.loads(process.stdout)
            self.assertEqual(result, json.loads(output.read_text()))
            self.assertEqual(calculate(result["calculator_request"])["status"], "completed")
            source.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
            process = subprocess.run([sys.executable, "-m", "native_relational_qc", "synthesize",
                                      str(source)], text=True, capture_output=True)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(json.loads(process.stdout)["status"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
