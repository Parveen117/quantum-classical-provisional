import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from native_relational_qc.model_experiment import (
    acquisition_binding, experiment_plan, observe, verify_observation, verify_plan,
)
from native_relational_qc.model_runtime import predict
from native_relational_qc.self_learning import FIELD, digest

ROOT = Path(__file__).resolve().parents[1]


def fixture_prediction(features=(0, 32)):
    model = json.loads((ROOT / "native_relational_qc/learning/structure_model.json").read_text())
    profile = json.loads((ROOT / "native_relational_qc/calculator_examples/three_wire_line.json").read_text())
    return predict(model, features, view="first_layer", profile=profile)


def fixture_binding(prediction):
    return dict(schema="nrqc-acquisition-binding-v1", origin="synthetic",
                provider="test-fixture", backend="synthetic-three-wire-line",
                device_fingerprint=digest(prediction["device"]),
                calibration=dict(calibration_id="fixture-20261112",
                                 source_sha256=hashlib.sha256(b"synthetic calibration fixture").hexdigest(),
                                 captured_at="2026-11-12T00:00:00Z", valid_until="2026-11-13T00:00:00Z"))


def fixture_plan(prediction, *, shots=100, tolerance=Fraction(1, 10), wires=None, run_id="fixture-run"):
    return experiment_plan(prediction, fixture_binding(prediction), run_id=run_id, shots=shots,
                           tolerance=dict(numerator=tolerance.numerator, denominator=tolerance.denominator),
                           measure_wires=wires)


def fixture_result(plan, counts, *, job_id="fixture-job"):
    return dict(schema="nrqc-acquisition-result-v1", plan_fingerprint=plan["fingerprint"],
                binding_fingerprint=digest(plan["binding"]), program_sha256=plan["program_sha256"],
                job_id=job_id, origin=plan["binding"]["origin"], provider=plan["binding"]["provider"],
                backend=plan["binding"]["backend"], started_at="2026-11-12T01:00:00Z",
                completed_at="2026-11-12T01:00:01Z", shots=plan["shots"], counts=counts,
                source_sha256=hashlib.sha256(json.dumps(counts, sort_keys=True).encode()).hexdigest())


def reseal(record):
    record["fingerprint"] = digest({k: v for k, v in record.items() if k != "fingerprint"})
    return record


class ModelExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prediction = fixture_prediction()
        cls.plan = fixture_plan(cls.prediction)
        # The actual trained model at these features reads one with certainty.
        assert FIELD.from_dict(cls.prediction["probability_one"]) == FIELD(1)

    def test_measurement_contract_replays_and_leaves_inputs_unchanged(self):
        before = copy.deepcopy(self.prediction)
        binding = fixture_binding(self.prediction)
        plan = experiment_plan(self.prediction, binding, run_id="plan", shots=100,
                               tolerance=dict(numerator=2, denominator=20))
        self.assertEqual(plan["tolerance"], dict(numerator=1, denominator=10))
        self.assertIn("measure q[1] -> c[0];", plan["measured_openqasm"])
        self.assertEqual(verify_plan(plan)["status"], "verified")
        self.assertEqual(self.prediction, before)
        binding["calibration"]["calibration_id"] = "changed"
        self.assertNotEqual(plan["binding"], binding)

    def test_exact_acceptance_boundaries(self):
        for ones, expected in ((100, "RECOGNITION"), (90, "RECOGNITION"),
                               (89, "BOUNDED_RESIDUE"), (80, "BOUNDED_RESIDUE"),
                               (79, "ACTIONABLE_RESIDUE")):
            with self.subTest(ones=ones):
                report = observe(self.plan, fixture_result(self.plan, {"0": 100 - ones, "1": ones}))
                self.assertEqual(report["classification"], expected)
                self.assertEqual(FIELD.from_dict(report["absolute_error"]), FIELD(Fraction(100 - ones, 100)))
                self.assertEqual(verify_observation(report)["status"], "verified")

    def test_multibit_histogram_uses_the_frozen_classical_bit(self):
        # Readout q1 -> c2. Leftmost character is therefore the model readout.
        plan = fixture_plan(self.prediction, wires=[2, 0, 1])
        report = observe(plan, fixture_result(plan, {"000": 7, "001": 3, "100": 41, "111": 49}))
        self.assertEqual(report["marginal_counts"], {"0": 10, "1": 90})
        self.assertEqual(report["classification"], "RECOGNITION")
        self.assertEqual(report["bridge_payload"]["observed"], {"0": 10, "1": 90})
        self.assertIn("measure q[1] -> c[2];", plan["measured_openqasm"])

    def test_arbitrary_native_phase_probability_keeps_exact_residue(self):
        prediction = fixture_prediction((5, 17))
        plan = fixture_plan(prediction)
        report = observe(plan, fixture_result(plan, {"0": 40, "1": 60}))
        difference = FIELD(Fraction(3, 5)) - FIELD.from_dict(prediction["probability_one"])
        expected = difference if difference.real_sign() >= 0 else -difference
        self.assertEqual(FIELD.from_dict(report["absolute_error"]), expected)
        self.assertEqual(verify_observation(report)["fingerprint"], report["fingerprint"])

    def test_histogram_rejects_missing_shots_floats_booleans_and_ambiguous_keys(self):
        cases = [{"0": 10, "1": 89}, {"0": -1, "1": 101}, {"0": 0.0, "1": 100},
                 {"0": False, "1": 100}, {"0x0": 100}, {"00": 100}, {"1 ": 100}, {}, {1: 100}]
        for counts in cases:
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                observe(self.plan, fixture_result(self.plan, counts))

    def test_binding_and_job_fields_fail_closed(self):
        result = fixture_result(self.plan, {"1": 100})
        changes = dict(plan_fingerprint="a" * 64, binding_fingerprint="a" * 64,
                       program_sha256="a" * 64, origin="physical_backend", provider="other",
                       backend="other", shots=99, job_id="", source_sha256="bad",
                       started_at="2026-11-11T23:59:59Z", completed_at="2026-11-13T00:00:00Z")
        for key, value in changes.items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                observe(self.plan, dict(result, **{key: value}))

    def test_calibration_times_and_measurement_map_are_validated(self):
        binding = fixture_binding(self.prediction)
        for time in ("2026-11-12T00:00:00", "2026-11-31T00:00:00Z", "yesterday"):
            changed = copy.deepcopy(binding)
            changed["calibration"]["captured_at"] = time
            with self.subTest(time=time), self.assertRaises(ValueError):
                acquisition_binding(changed)
        for wires in ([], [0], [1, 1], [True], [1, 3]):
            with self.subTest(wires=wires), self.assertRaises(ValueError):
                fixture_plan(self.prediction, wires=wires)
        binding["device_fingerprint"] = "a" * 64
        with self.assertRaises(ValueError):
            experiment_plan(self.prediction, binding, run_id="test", shots=100,
                            tolerance=dict(numerator=1, denominator=10))

    def test_repaired_checksum_does_not_bypass_plan_or_report_replay(self):
        plan = copy.deepcopy(self.plan)
        plan["readout_classical_bit"] = 9
        with self.assertRaises(ValueError):
            verify_plan(reseal(plan))
        report = observe(self.plan, fixture_result(self.plan, {"1": 100}))
        report["classification"] = "ACTIONABLE_RESIDUE"
        with self.assertRaises(ValueError):
            verify_observation(reseal(report))

    def test_origins_remain_declared_and_output_does_not_alias_input(self):
        plan = copy.deepcopy(self.plan)
        plan["binding"]["origin"] = "physical_backend"
        plan = experiment_plan(plan["prediction"], plan["binding"], run_id="declared", shots=100,
                               tolerance=plan["tolerance"])
        report = observe(plan, fixture_result(plan, {"1": 100}))
        self.assertEqual(report["evidence_class"], "DECLARED_PHYSICAL_OBSERVATION")
        self.assertEqual(report["source_authentication"], "not_performed")
        self.assertEqual(report["hardware_submissions"], 0)
        before = copy.deepcopy(report)
        plan["binding"]["backend"] = "changed"
        self.assertEqual(report, before)

    def test_normal_cli_plan_observation_and_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            pred, binding, plan, qasm, result, report = [directory / name for name in (
                "prediction.json", "binding.json", "plan.json", "program.qasm", "result.json", "report.json")]
            pred.write_text(json.dumps(self.prediction))
            binding.write_text(json.dumps(fixture_binding(self.prediction)))
            command = [sys.executable, "-m", "native_relational_qc"]
            subprocess.run(command + ["experiment-plan", str(pred), "--binding", str(binding),
                                      "--run-id", "cli", "--shots", "100", "--tolerance", "1/10",
                                      "--out", str(plan), "--qasm-out", str(qasm)], check=True, capture_output=True)
            planned = json.loads(plan.read_text())
            self.assertEqual(qasm.read_text(), planned["measured_openqasm"])
            result.write_text(json.dumps(fixture_result(planned, {"0": 5, "1": 95})))
            subprocess.run(command + ["observe-model", str(plan), str(result), "--out", str(report)],
                           check=True, capture_output=True)
            replay = subprocess.run(command + ["verify-observation", str(report)],
                                    check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(replay.stdout)["classification"], "RECOGNITION")


if __name__ == "__main__":
    unittest.main()
