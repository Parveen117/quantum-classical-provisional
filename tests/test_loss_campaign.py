import copy
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from native_relational_qc.loss_acquisition import import_loss_events
from native_relational_qc.loss_campaign import loss_campaign_plan, loss_campaign_report, verify_loss_campaign_report
from native_relational_qc.self_learning import FIELD
from tests.test_loss_acquisition import event, fixture_loss_plan, raw_bytes
from tests.test_model_experiment import fixture_prediction, reseal


class LossCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prediction = fixture_prediction()
        cls.plans = [fixture_loss_plan(cls.prediction, run_id=f"loss-repetition-{index}") for index in range(3)]
        cls.campaign = loss_campaign_plan(cls.plans, name="three fixed retained-event runs", minimum_repetitions=3)
        cls.reports = [import_loss_events(plan, raw_bytes(plan, job_id=f"loss-job-{index}")) for index, plan in enumerate(cls.plans)]

    def test_complete_healthy_campaign_preserves_counts_and_replays(self):
        report = loss_campaign_report(self.campaign, self.reports)
        self.assertTrue(report["qualification_passed"])
        self.assertEqual(report["status"], "complete")
        group = next(iter(report["groups"].values()))
        self.assertEqual(group["attempts_observed"], 3000)
        self.assertEqual(group["accepted_observed"], 1500)
        self.assertEqual(sum(group["rejected_counts"].values()), 1500)
        self.assertEqual(verify_loss_campaign_report(report)["status"], "verified")

    def test_low_yield_run_cannot_hide_behind_a_good_pooled_yield(self):
        plan = self.plans[2]
        low = import_loss_events(plan, raw_bytes(plan, [event(plan, 300, bits="1"), event(plan, 350, herald=0), event(plan, 350)], job_id="low-yield"))
        report = loss_campaign_report(self.campaign, self.reports[:2] + [low])
        group = next(iter(report["groups"].values()))
        self.assertEqual(group["pooled_accepted_yield"], dict(numerator=13, denominator=30))
        self.assertEqual(group["minimum_observed_yield"], dict(numerator=3, denominator=10))
        self.assertFalse(report["qualification_passed"])
        self.assertEqual(group["qualified_runs"], 2)

    def test_conditional_outlier_cannot_be_hidden_by_an_accepted_average(self):
        plan = self.plans[2]
        wrong = import_loss_events(plan, raw_bytes(plan, [event(plan, 125, bits="0"), event(plan, 375, bits="1"),
                                                       event(plan, 250, herald=0), event(plan, 250)], job_id="conditional-outlier"))
        report = loss_campaign_report(self.campaign, self.reports[:2] + [wrong])
        group = next(iter(report["groups"].values()))
        self.assertEqual(group["pooled_conditional_probability_one"], dict(numerator=11, denominator=12))
        self.assertEqual(FIELD.from_dict(group["maximum_conditional_error"]), FIELD(Fraction(1, 4)))
        self.assertEqual(FIELD.from_dict(group["mean_conditional_error"]), FIELD(Fraction(1, 12)))
        self.assertFalse(report["qualification_passed"])

    def test_zero_accepted_run_has_no_invented_error_in_the_mean(self):
        plan = self.plans[2]
        zero = import_loss_events(plan, raw_bytes(plan, [event(plan, 1000, herald=0)], job_id="zero-accepted"))
        report = loss_campaign_report(self.campaign, self.reports[:2] + [zero])
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["conditional_incomplete_plans"], [plan["fingerprint"]])
        group = next(iter(report["groups"].values()))
        self.assertEqual(group["conditional_results_available"], 2)
        self.assertEqual(group["conditional_incomplete_runs"], 1)
        self.assertFalse(report["qualification_passed"])

    def test_missing_and_failed_acquisitions_preserve_planned_workload(self):
        partial = loss_campaign_report(self.campaign, self.reports[:2])
        self.assertEqual(partial["status"], "incomplete")
        self.assertEqual(partial["missing_plans"], [self.plans[2]["fingerprint"]])
        failure = dict(plan_fingerprint=self.plans[2]["fingerprint"], kind="timeout", detail="synthetic detector timeout", job_id="timeout-job", source_sha256=None)
        failed = loss_campaign_report(self.campaign, self.reports[:2], failures=[failure])
        self.assertEqual(failed["status"], "complete")
        self.assertEqual(failed["failed_runs"], 1)
        self.assertFalse(failed["qualification_passed"])
        group = next(iter(failed["groups"].values()))
        self.assertEqual(group["planned_attempts"], 3000)
        self.assertEqual(group["attempts_observed"], 2000)

    def test_duplicate_unknown_and_reused_jobs_are_rejected(self):
        other_plan = fixture_loss_plan(self.prediction, run_id="unplanned")
        other = import_loss_events(other_plan, raw_bytes(other_plan, job_id="unplanned-job"))
        reused = import_loss_events(self.plans[1], raw_bytes(self.plans[1], job_id="loss-job-0"))
        for reports in ([other], [self.reports[0], self.reports[0]], [self.reports[0], reused]):
            with self.assertRaises(ValueError):
                loss_campaign_report(self.campaign, reports)

    def test_failed_job_and_successful_job_cannot_reuse_identity(self):
        failure = dict(plan_fingerprint=self.plans[2]["fingerprint"], kind="cancelled", detail="fixture", job_id="loss-job-0", source_sha256=None)
        with self.assertRaises(ValueError):
            loss_campaign_report(self.campaign, self.reports[:2], failures=[failure])
        failure["job_id"] = None
        with self.assertRaises(ValueError):
            loss_campaign_report(self.campaign, self.reports, failures=[failure])

    def test_repetitions_and_instrument_context_are_fixed_before_data(self):
        with self.assertRaises(ValueError):
            loss_campaign_plan(self.plans[:2], name="too few", minimum_repetitions=3)
        balanced = fixture_loss_plan(fixture_prediction((16, 0)), run_id="different-input")
        with self.assertRaises(ValueError):
            loss_campaign_plan(self.plans + [balanced], name="singleton input", minimum_repetitions=3)
        campaign = loss_campaign_plan([self.plans[0], balanced], name="separate contexts", minimum_repetitions=1)
        self.assertEqual(len(campaign["planned_groups"]), 2)

    def test_repaired_summary_hash_does_not_hide_a_missing_run(self):
        report = loss_campaign_report(self.campaign, self.reports[:2])
        report["status"] = "complete"
        report["qualification_passed"] = True
        with self.assertRaises(ValueError):
            verify_loss_campaign_report(reseal(report))

    def test_cli_uses_a_verified_loss_ledger_and_requires_qualification(self):
        from native_relational_qc.experiment_ledger import record_observation
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            request, campaign, report, ledger = (root / name for name in ("request.json", "campaign.json", "report.json", "ledger.jsonl"))
            request.write_text(json.dumps(dict(name="CLI loss campaign", minimum_repetitions=3, plans=self.plans)))
            command = [sys.executable, "-m", "native_relational_qc"]
            subprocess.run(command + ["loss-campaign-plan", str(request), "--out", str(campaign)], check=True, capture_output=True)
            record_observation(self.reports[0], ledger)
            partial = subprocess.run(command + ["loss-campaign-report", str(campaign), "--ledger", str(ledger),
                                                "--require-qualified"], capture_output=True, text=True)
            self.assertEqual(partial.returncode, 3)
            for observation in self.reports[1:]:
                record_observation(observation, ledger)
            subprocess.run(command + ["loss-campaign-report", str(campaign), "--ledger", str(ledger),
                                      "--require-qualified", "--out", str(report)], check=True, capture_output=True)
            verified = subprocess.run(command + ["verify-loss-campaign-report", str(report)], check=True, capture_output=True, text=True)
            self.assertTrue(json.loads(verified.stdout)["qualification_passed"])


if __name__ == "__main__":
    unittest.main()
