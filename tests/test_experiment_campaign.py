from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from native_relational_qc.experiment_campaign import (
    campaign_plan, campaign_report, verify_campaign, verify_campaign_report,
)
from native_relational_qc.model_experiment import observe
from native_relational_qc.self_learning import FIELD
from tests.test_model_experiment import fixture_plan, fixture_prediction, fixture_result, reseal


class ExperimentCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prediction = fixture_prediction()
        cls.plans = [fixture_plan(cls.prediction, run_id=f"repetition-{n}") for n in range(3)]
        cls.campaign = campaign_plan(cls.plans, name="three fixed repetitions", minimum_repetitions=3)
        cls.reports = [observe(plan, fixture_result(plan, {"0": 0, "1": 100}, job_id=f"job-{n}"))
                       for n, plan in enumerate(cls.plans)]

    def test_frozen_campaign_and_complete_healthy_report_replay(self):
        self.assertEqual(verify_campaign(self.campaign)["status"], "verified")
        report = campaign_report(self.campaign, self.reports)
        self.assertTrue(report["qualification_passed"])
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["observed_runs"], 3)
        self.assertEqual(verify_campaign_report(report)["status"], "verified")

    def test_missing_run_retains_incomplete_qualification(self):
        report = campaign_report(self.campaign, self.reports[:2])
        self.assertEqual(report["status"], "incomplete")
        self.assertFalse(report["qualification_passed"])
        self.assertEqual(report["missing_plans"], [self.plans[2]["fingerprint"]])
        self.assertEqual(report["run_results"][2]["status"], "missing")

    def test_declared_failure_completes_accounting_without_qualification(self):
        failure = dict(plan_fingerprint=self.plans[2]["fingerprint"], kind="timeout",
                       detail="synthetic controller timeout fixture", job_id="failed-job", source_sha256=None)
        report = campaign_report(self.campaign, self.reports[:2], failures=[failure])
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["failed_runs"], 1)
        self.assertFalse(report["qualification_passed"])
        self.assertFalse(report["missing_plans"])

    def test_pooled_average_cannot_hide_an_actionable_outlier(self):
        outlier = observe(self.plans[2], fixture_result(self.plans[2], {"0": 21, "1": 79}, job_id="outlier"))
        report = campaign_report(self.campaign, self.reports[:2] + [outlier])
        group = next(iter(report["groups"].values()))
        self.assertEqual(group["pooled_marginal_counts"], {"0": 21, "1": 279})
        self.assertEqual(group["pooled_probability_one"], dict(numerator=93, denominator=100))
        self.assertEqual(FIELD.from_dict(group["mean_run_absolute_error"]), FIELD(Fraction(7, 100)))
        self.assertEqual(FIELD.from_dict(group["maximum_run_absolute_error"]), FIELD(Fraction(21, 100)))
        self.assertFalse(group["qualified"])
        self.assertFalse(report["qualification_passed"])

    def test_unknown_duplicate_or_reused_jobs_are_rejected(self):
        other_plan = fixture_plan(self.prediction, run_id="unplanned")
        unknown = observe(other_plan, fixture_result(other_plan, {"1": 100}, job_id="unknown"))
        reused = observe(self.plans[1], fixture_result(self.plans[1], {"1": 100}, job_id="job-0"))
        for reports in ([unknown], [self.reports[0], self.reports[0]], [self.reports[0], reused]):
            with self.subTest(reports=len(reports)), self.assertRaises(ValueError):
                campaign_report(self.campaign, reports)

    def test_success_and_failure_cannot_occupy_the_same_slot(self):
        failure = dict(plan_fingerprint=self.plans[0]["fingerprint"], kind="cancelled",
                       detail="fixture", job_id=None, source_sha256=None)
        with self.assertRaises(ValueError):
            campaign_report(self.campaign, self.reports, failures=[failure])
        failure["plan_fingerprint"] = self.plans[2]["fingerprint"]
        failure["job_id"] = "job-0"
        with self.assertRaises(ValueError):
            campaign_report(self.campaign, self.reports[:2], failures=[failure])

    def test_grouping_and_repetition_requirement_are_frozen(self):
        with self.assertRaises(ValueError):
            campaign_plan(self.plans[:2], name="too few", minimum_repetitions=3)
        with self.assertRaises(ValueError):
            campaign_plan([self.plans[0], self.plans[0]], name="duplicate", minimum_repetitions=1)
        other_prediction = fixture_prediction((5, 17))
        other = fixture_plan(other_prediction, run_id="different-input")
        with self.assertRaises(ValueError):
            campaign_plan(self.plans + [other], name="incomparable singleton", minimum_repetitions=3)
        mixed = campaign_plan([self.plans[0], other], name="two contexts", minimum_repetitions=1)
        self.assertEqual(len(mixed["planned_groups"]), 2)

    def test_repaired_summary_hash_cannot_hide_missing_runs(self):
        report = campaign_report(self.campaign, self.reports[:2])
        report["qualification_passed"] = True
        report["status"] = "complete"
        with self.assertRaises(ValueError):
            verify_campaign_report(reseal(report))

    def test_cli_handles_full_campaign_and_incomplete_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request, campaign, report, observation = [root / name for name in (
                "request.json", "campaign.json", "report.json", "observation.json")]
            request.write_text(json.dumps(dict(name="cli-campaign", minimum_repetitions=3, plans=self.plans)))
            observation.write_text(json.dumps(self.reports[0]))
            command = [sys.executable, "-m", "native_relational_qc"]
            subprocess.run(command + ["campaign-plan", str(request), "--out", str(campaign)],
                           check=True, capture_output=True)
            subprocess.run(command + ["campaign-report", str(campaign), str(observation), "--out", str(report)],
                           check=True, capture_output=True)
            result = subprocess.run(command + ["verify-campaign-report", str(report)],
                                    check=True, capture_output=True, text=True)
            self.assertFalse(json.loads(result.stdout)["qualification_passed"])
            gated = subprocess.run(command + ["campaign-report", str(campaign), str(observation),
                                              "--require-qualified"], capture_output=True, text=True)
            self.assertEqual(gated.returncode, 3)
            self.assertEqual(json.loads(gated.stdout)["status"], "incomplete")

    def test_campaign_cli_can_read_a_dedicated_verified_ledger(self):
        from native_relational_qc.experiment_ledger import record_observation
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            campaign, ledger = root / "campaign.json", root / "campaign.jsonl"
            campaign.write_text(json.dumps(self.campaign))
            for report in self.reports:
                record_observation(report, ledger)
            result = subprocess.run([sys.executable, "-m", "native_relational_qc", "campaign-report",
                                     str(campaign), "--ledger", str(ledger), "--require-qualified"],
                                    capture_output=True, check=True, text=True)
            self.assertTrue(json.loads(result.stdout)["qualification_passed"])


if __name__ == "__main__":
    unittest.main()
