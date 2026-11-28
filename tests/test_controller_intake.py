import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from native_relational_qc.model_experiment import import_observation, observe, verify_observation
from tests.test_model_experiment import fixture_plan, fixture_prediction, fixture_result


def controller_bytes(plan):
    acquired = fixture_result(plan, {"0": 5, "1": 95})
    del acquired["source_sha256"]
    acquired["schema"] = "nrqc-controller-counts-v1"
    return json.dumps(acquired, sort_keys=True, indent=2).encode("utf-8") + b"\n"


class ControllerIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = fixture_plan(fixture_prediction())
        cls.raw = controller_bytes(cls.plan)

    def test_actual_artifact_bytes_are_bound_and_rechecked(self):
        report = import_observation(self.plan, self.raw)
        self.assertEqual(report["acquisition"]["source_sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertFalse(verify_observation(report)["source_artifact_hash_verified"])
        self.assertTrue(verify_observation(report, source_bytes=self.raw)["source_artifact_hash_verified"])
        self.assertEqual(report["evidence_class"], "SYNTHETIC_OBSERVATION")
        self.assertEqual(report["source_authentication"], "not_performed")

    def test_byte_change_is_detected_even_if_the_json_values_are_identical(self):
        report = import_observation(self.plan, self.raw)
        with self.assertRaisesRegex(ValueError, "artifact bytes"):
            verify_observation(report, source_bytes=self.raw + b"\n")

    def test_changed_acquisition_binding_is_rejected(self):
        raw = json.loads(self.raw)
        for key, value in (("backend", "different-device"), ("shots", 99), ("program_sha256", "0" * 64)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                import_observation(self.plan, json.dumps(dict(raw, **{key: value})).encode())

    def test_controller_schema_is_explicit_and_has_no_self_hash(self):
        raw = json.loads(self.raw)
        for changed in (dict(raw, schema="vendor-unknown"), dict(raw, source_sha256="0" * 64)):
            with self.assertRaises(ValueError):
                import_observation(self.plan, json.dumps(changed).encode())
        with self.assertRaises(ValueError):
            import_observation(self.plan, self.raw.decode())

    def test_duplicate_json_keys_and_coerced_numeric_counts_are_rejected(self):
        duplicate = self.raw.replace(b'"shots": 100', b'"shots": 100, "shots": 100')
        with self.assertRaises(ValueError):
            import_observation(self.plan, duplicate)
        raw = json.loads(self.raw)
        for counts in ({"0": 5.0, "1": 95}, {"0": True, "1": 99}, {"0": "5", "1": 95}):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                import_observation(self.plan, json.dumps(dict(raw, counts=counts)).encode())

    def test_artifact_recheck_revalidates_integer_types_despite_python_numeric_equality(self):
        controller = json.loads(self.raw)
        controller["counts"] = {"0": 5.0, "1": 95.0}
        raw = json.dumps(controller).encode()
        result = fixture_result(self.plan, {"0": 5, "1": 95})
        result["source_sha256"] = hashlib.sha256(raw).hexdigest()
        declared = observe(self.plan, result)
        with self.assertRaises(ValueError):
            verify_observation(declared, source_bytes=raw)

    def test_cli_import_and_replay_check_the_original_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plan, raw, report = root / "plan.json", root / "raw.json", root / "report.json"
            plan.write_text(json.dumps(self.plan))
            raw.write_bytes(self.raw)
            command = [sys.executable, "-m", "native_relational_qc"]
            subprocess.run(command + ["import-model-counts", str(plan), str(raw), "--out", str(report)],
                           check=True, capture_output=True)
            good = subprocess.run(command + ["verify-observation", str(report), "--source-artifact", str(raw)],
                                  check=True, capture_output=True, text=True)
            self.assertTrue(json.loads(good.stdout)["source_artifact_hash_verified"])
            raw.write_bytes(self.raw + b"\n")
            bad = subprocess.run(command + ["verify-observation", str(report), "--source-artifact", str(raw)],
                                 capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(json.loads(bad.stdout)["status"], "invalid_request")


if __name__ == "__main__":
    unittest.main()
