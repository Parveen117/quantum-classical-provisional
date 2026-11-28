import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from native_relational_qc.compact import ResourceLimit
from native_relational_qc.model_runtime import (
    NATIVE_GATES, device_profile, predict, verify_prediction,
)
from native_relational_qc.self_learning import Evaluator, FIELD, digest, packet


def line_profile(n, *, bidirectional=True):
    edges = [[q, q + 1] for q in range(n - 1)]
    if bidirectional:
        edges += [[b, a] for a, b in edges]
    return dict(schema="nrqc-device-profile-v1", name=f"test-{n}-wire-line", n_qubits=n,
                coupling_map=edges, native_gates=list(NATIVE_GATES), max_gates=1024)


def model(*, selected=False):
    kwargs = dict(entanglers=((0, 3), (1, 3))) if selected else {}
    return packet((32, 0, 0, 32, 0), training_digest="a" * 64, view="first_layer", **kwargs)


class ModelRuntimeTests(unittest.TestCase):
    def test_selected_checkpoint_maps_to_three_wires_and_replays(self):
        source = model(selected=True)
        before = copy.deepcopy(source)
        result = predict(source, (5, 17), view="first_layer", profile=line_profile(3))
        self.assertEqual(source, before)
        self.assertEqual(result["verification"]["basis_inputs_checked"], 8)
        self.assertEqual(result["mapping"]["omitted_logical_wires_initial_zero"], [2])
        self.assertEqual(result["calculator_request"]["n_qubits"], 3)
        self.assertEqual(result["mapping"]["final_layout"]["3"], 1)
        self.assertEqual(sum(g == "cx" for g, _ in result["calculator_request"]["operations"]), 2)
        self.assertEqual(verify_prediction(result)["status"], "verified")
        source["phase_steps"][0] = 0
        self.assertEqual(result["model"], before)

    def test_legacy_model_routes_through_a_directed_chain(self):
        source = model()
        result = predict(source, (5, 17), view="first_layer",
                         profile=line_profile(4, bidirectional=False))
        admitted = {tuple(e) for e in result["device"]["coupling_map"]}
        for name, qs in result["calculator_request"]["operations"]:
            if name == "cx":
                self.assertIn(tuple(qs), admitted)
        self.assertGreater(result["resources"]["native_gates"], result["resources"]["source_gates"])
        self.assertEqual(result["verification"]["basis_inputs_checked"], 16)
        expected = Evaluator().probability((5, 17), tuple(source["phase_steps"]))
        self.assertEqual(FIELD.from_dict(result["probability_one"]), expected)

    def test_routing_retains_a_nonidentity_final_logical_layout(self):
        edges = ((1, 2), (2, 3), (0, 2))
        source = packet((3, 41, 22, 9, 50), training_digest="a" * 64,
                        view="first_layer", entanglers=edges)
        result = predict(source, (5, 17), view="first_layer",
                         profile=line_profile(4, bidirectional=False))
        self.assertNotEqual(result["mapping"]["initial_layout"], result["mapping"]["final_layout"])
        expected = Evaluator(entanglers=edges).probability((5, 17), (3, 41, 22, 9, 50))
        self.assertEqual(FIELD.from_dict(result["probability_one"]), expected)

    def test_general_nonclifford_parameters_survive_mapping_and_qasm(self):
        source = packet((3, 41, 22, 9, 50), training_digest="a" * 64, view="first_layer")
        result = predict(source, (5, 17), view="first_layer", profile=line_profile(4))
        self.assertEqual(result["verification"]["basis_inputs_checked"], 16)
        self.assertTrue(result["verification"]["qasm_exact_active_unitary_roundtrip"])
        self.assertIn("pi/64", result["openqasm"])
        expected = Evaluator().probability((5, 17), (3, 41, 22, 9, 50))
        self.assertEqual(FIELD.from_dict(result["probability_one"]), expected)

    def test_complete_fit_wrapper_uses_its_saved_model(self):
        source = model(selected=True)
        wrapper = dict(schema="nrqc-structure-learning-v1", status="completed", model=source)
        result = predict(wrapper, (0, 32), view="first_layer", profile=line_profile(3))
        self.assertEqual(result["model"], source)
        wrapper["status"] = "incomplete"
        with self.assertRaises(ValueError):
            predict(wrapper, (0, 32), view="first_layer")

    def test_bad_view_width_gates_and_connectivity_are_rejected(self):
        source = model(selected=True)
        with self.assertRaises(ValueError):
            predict(source, (5, 17), view="xor_bits")
        for profile in [line_profile(2), dict(line_profile(3), coupling_map=[]),
                        dict(line_profile(3), native_gates=[g for g in NATIVE_GATES if g != "p64"])]:
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                predict(source, (5, 17), view="first_layer", profile=profile)
        for features in ((True, 0), (64, 0)):
            with self.assertRaises(ValueError):
                predict(source, features, view="first_layer")

    def test_gate_and_whole_verification_budgets_return_no_prediction(self):
        with self.assertRaises(ResourceLimit):
            predict(model(), (5, 17), view="first_layer", max_work=1)
        with self.assertRaises(ResourceLimit):
            predict(model(), (5, 17), view="first_layer",
                    profile=dict(line_profile(4), max_gates=1))

    def test_replay_rejects_both_fingerprint_and_semantic_tampering(self):
        record = predict(model(selected=True), (5, 17), view="first_layer", profile=line_profile(3))
        for key in ("predicted", "openqasm", "mapping"):
            corrupted = copy.deepcopy(record)
            if key == "predicted":
                corrupted[key] = 1 - record[key]
            elif key == "openqasm":
                corrupted[key] += "// changed\n"
            else:
                corrupted[key]["final_layout"]["3"] = 0
            with self.assertRaises(ValueError):
                verify_prediction(corrupted)
            corrupted["fingerprint"] = digest({k: v for k, v in corrupted.items() if k != "fingerprint"})
            with self.assertRaises(ValueError):
                verify_prediction(corrupted)

    def test_profile_contract_is_strict(self):
        for override in (dict(n_qubits=True), dict(coupling_map=[[0, 0]]),
                         dict(coupling_map=[[0, 1], [0, 1]]), dict(native_gates=["magic"]),
                         dict(max_gates=0)):
            with self.subTest(override=override), self.assertRaises(ValueError):
                device_profile(dict(line_profile(3), **override))

    def test_cli_prediction_then_exact_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target, output = [Path(folder) / name for name in ("model.json", "device.json", "run.json")]
            source.write_text(json.dumps(model(selected=True)))
            target.write_text(json.dumps(line_profile(3)))
            run = subprocess.run([sys.executable, "-m", "native_relational_qc", "predict", str(source),
                                  "--features", "5", "17", "--view", "first_layer", "--device", str(target),
                                  "--out", str(output)], text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(json.loads(run.stdout), json.loads(output.read_text()))
            replay = subprocess.run([sys.executable, "-m", "native_relational_qc", "verify-prediction", str(output)],
                                     text=True, capture_output=True)
            self.assertEqual(replay.returncode, 0, replay.stdout + replay.stderr)
            self.assertEqual(json.loads(replay.stdout)["status"], "verified")


if __name__ == "__main__":
    unittest.main()
