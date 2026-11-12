import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from quantum_native_bridge_pro import QuantumNativeBridge, VerificationError
from quantum_native_bridge_pro.bridge import canonical_json, sha256_hex
from native_relational_qc.experiment_ledger import record_observation, verify_experiment_ledger
from native_relational_qc.model_experiment import observe
from tests.test_model_experiment import fixture_plan, fixture_prediction, fixture_result, reseal


def repair_bridge_hashes(record):
    record["record_hash"] = sha256_hex(canonical_json({k: v for k, v in record.items()
                                                     if k not in ("record_hash", "chain_hash")}))
    record["chain_hash"] = sha256_hex(canonical_json(dict(previous_hash=record["previous_hash"],
                                                        record_hash=record["record_hash"],
                                                        sequence=record["sequence"])))
    return record


class ExperimentLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prediction = fixture_prediction()
        cls.plan = fixture_plan(cls.prediction)
        cls.report = observe(cls.plan, fixture_result(cls.plan, {"0": 5, "1": 95}))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger = Path(self.temp.name) / "observations.jsonl"

    def test_record_replay_and_retry_are_idempotent(self):
        first = record_observation(self.report, self.ledger)
        before = self.ledger.read_bytes()
        retry = record_observation(self.report, self.ledger)
        self.assertTrue(first["appended"])
        self.assertFalse(retry["appended"])
        self.assertEqual(first["chain_hash"], retry["chain_hash"])
        self.assertEqual(before, self.ledger.read_bytes())
        verification = verify_experiment_ledger(self.ledger)
        self.assertEqual(verification["observations_replayed"], 1)
        self.assertEqual(verification["exact_classifications"], {"RECOGNITION": 1})

    def test_same_job_or_plan_cannot_be_relabelled_into_another_run(self):
        record_observation(self.report, self.ledger)
        before = self.ledger.read_bytes()
        new_plan = fixture_plan(self.prediction, run_id="other-plan")
        same_job = observe(new_plan, fixture_result(new_plan, {"0": 5, "1": 95}))
        changed_job = observe(self.plan, fixture_result(self.plan, {"0": 5, "1": 95}, job_id="other-job"))
        for report in (same_job, changed_job):
            with self.assertRaises(ValueError):
                record_observation(report, self.ledger)
        self.assertEqual(before, self.ledger.read_bytes())

    def test_independent_plans_and_jobs_append_in_order(self):
        record_observation(self.report, self.ledger)
        plan = fixture_plan(self.prediction, run_id="second-run")
        report = observe(plan, fixture_result(plan, {"0": 21, "1": 79}, job_id="second-job"))
        receipt = record_observation(report, self.ledger)
        self.assertEqual(receipt["sequence"], 2)
        verification = verify_experiment_ledger(self.ledger)
        self.assertEqual(verification["exact_classifications"], {"RECOGNITION": 1, "ACTIONABLE_RESIDUE": 1})

    def test_repaired_chain_cannot_hide_different_bridge_metrics(self):
        record_observation(self.report, self.ledger)
        record = json.loads(self.ledger.read_text())
        record["recognition"]["distribution_gap"] = 0.99
        self.ledger.write_text(json.dumps(repair_bridge_hashes(record)) + "\n")
        self.assertTrue(QuantumNativeBridge(self.ledger).verify_chain()["valid"])
        with self.assertRaisesRegex(ValueError, "replayed observation"):
            verify_experiment_ledger(self.ledger)

    def test_repaired_report_and_chain_cannot_hide_false_exact_classification(self):
        record_observation(self.report, self.ledger)
        record = json.loads(self.ledger.read_text())
        report = record["metadata"]["nrqc_observation"]
        report["classification"] = "ACTIONABLE_RESIDUE"
        reseal(report)
        self.ledger.write_text(json.dumps(repair_bridge_hashes(record)) + "\n")
        with self.assertRaisesRegex(ValueError, "deterministic exact replay"):
            verify_experiment_ledger(self.ledger)

    def test_broken_chain_rejects_append_without_changing_ledger(self):
        record_observation(self.report, self.ledger)
        record = json.loads(self.ledger.read_text())
        record["record_hash"] = "0" * 64
        self.ledger.write_text(json.dumps(record) + "\n")
        before = self.ledger.read_bytes()
        with self.assertRaises(VerificationError):
            record_observation(self.report, self.ledger)
        self.assertEqual(before, self.ledger.read_bytes())
        self.assertFalse(self.ledger.with_name(self.ledger.name + ".nrqc-lock").exists())

    def test_existing_writer_lock_is_retained(self):
        lock = self.ledger.with_name(self.ledger.name + ".nrqc-lock")
        lock.write_text("another writer")
        with self.assertRaisesRegex(ValueError, "busy"):
            record_observation(self.report, self.ledger)
        self.assertEqual(lock.read_text(), "another writer")
        self.assertFalse(self.ledger.exists())

    def test_mixed_legacy_ledger_preserves_and_counts_legacy_records(self):
        bridge = QuantumNativeBridge(self.ledger)
        bridge.append(root="legacy", template="template", phase="context", observed={"0": 1})
        record_observation(self.report, self.ledger)
        result = verify_experiment_ledger(self.ledger)
        self.assertEqual(result["legacy_records"], 1)
        self.assertEqual(result["observations_replayed"], 1)
        self.assertEqual(result["chain"]["records"], 2)

    def test_read_only_verification_does_not_create_a_missing_ledger(self):
        with self.assertRaises(ValueError):
            verify_experiment_ledger(self.ledger)
        self.assertFalse(self.ledger.exists())

    def test_parallel_writers_either_append_or_retry_without_losing_runs(self):
        plan = fixture_plan(self.prediction, run_id="parallel-run")
        other = observe(plan, fixture_result(plan, {"0": 5, "1": 95}, job_id="parallel-job"))
        def write(report):
            try:
                return record_observation(report, self.ledger)
            except ValueError as error:
                if "busy" not in str(error):
                    raise
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts = list(pool.map(write, (self.report, other)))
        self.assertTrue(any(receipt is not None for receipt in receipts))
        for report in (self.report, other):
            record_observation(report, self.ledger)
        self.assertEqual(verify_experiment_ledger(self.ledger)["observations_replayed"], 2)

    def test_duplicate_json_keys_in_ledger_are_rejected(self):
        record_observation(self.report, self.ledger)
        text = self.ledger.read_text()
        self.ledger.write_text(text.replace('"sequence":1', '"sequence":1,"sequence":1'))
        with self.assertRaises(ValueError):
            verify_experiment_ledger(self.ledger)

    def test_nrqc_metadata_cannot_drop_the_embedded_observation(self):
        record_observation(self.report, self.ledger)
        record = json.loads(self.ledger.read_text())
        del record["metadata"]["nrqc_observation"]
        self.ledger.write_text(json.dumps(repair_bridge_hashes(record)) + "\n")
        with self.assertRaisesRegex(ValueError, "missing its replayable observation"):
            verify_experiment_ledger(self.ledger)

    def test_cli_records_and_verifies_ledger(self):
        report = Path(self.temp.name) / "report.json"
        report.write_text(json.dumps(self.report))
        command = [sys.executable, "-m", "native_relational_qc"]
        output = subprocess.run(command + ["record-observation", str(report), "--ledger", str(self.ledger)],
                                check=True, capture_output=True, text=True)
        self.assertTrue(json.loads(output.stdout)["appended"])
        output = subprocess.run(command + ["verify-experiment-ledger", "--ledger", str(self.ledger)],
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(output.stdout)["observations_replayed"], 1)


if __name__ == "__main__":
    unittest.main()
