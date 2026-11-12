"""Fixed-context loss campaigns with retained missing, failed and weak runs."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

assert sys.version_info[:2] == (3, 12), sys.version
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.loss_acquisition_audit import controller, encode, policy, reference, row, thresholds
from benchmarks.model_experiment_audit import binding_for
from native_relational_qc.loss_acquisition import import_loss_events, loss_plan
from native_relational_qc.loss_campaign import loss_campaign_plan, loss_campaign_report, verify_loss_campaign_report
from native_relational_qc.model_experiment import _rational, experiment_plan
from native_relational_qc.model_runtime import predict


def summary(report):
    return {key: report[key] for key in ("fingerprint", "status", "qualification_passed", "planned_runs",
                                        "observed_runs", "failed_runs", "missing_plans", "conditional_incomplete_plans",
                                        "groups", "run_results")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--example-dir", type=Path)
    args = parser.parse_args()
    certain = json.loads((ROOT / "native_relational_qc/experiments/loss_experiment.json").read_text())["prediction"]
    balanced = predict(certain["model"], (16, 0), view="first_layer", profile=certain["device"])
    plans = []
    for group, prediction in enumerate((certain, balanced)):
        for repetition in range(3):
            experiment = experiment_plan(prediction, binding_for(prediction), run_id=f"loss-context-{group}-repeat-{repetition}",
                                         shots=1000, tolerance=_rational(Fraction(1, 10)))
            plans.append(loss_plan(experiment, policy(experiment), reference(), thresholds()))
    campaign = loss_campaign_plan(plans, name="two fixed inputs, three retained-event repetitions", minimum_repetitions=3)
    reports, artifacts = [], []
    for index, plan in enumerate(plans):
        ones = 500 if index < 3 else 250
        rows = ([row(plan, 500 - ones, bit=0)] if ones < 500 else [])
        rows += [row(plan, ones, bit=1), row(plan, 250, herald=0), row(plan, 250)]
        raw = encode(controller(plan, rows, f"loss-campaign-job-{index}"))
        reports.append(import_loss_events(plan, raw))
        artifacts.append(raw)
    healthy = loss_campaign_report(campaign, reports)
    assert healthy["qualification_passed"]
    assert verify_loss_campaign_report(healthy)["qualification_passed"]
    missing = loss_campaign_report(campaign, reports[:-1])
    assert missing["status"] == "incomplete" and not missing["qualification_passed"]
    failure = dict(plan_fingerprint=plans[-1]["fingerprint"], kind="timeout", detail="synthetic controller timeout",
                   job_id="synthetic-timeout", source_sha256=None)
    failed = loss_campaign_report(campaign, reports[:-1], failures=[failure])
    assert failed["status"] == "complete" and not failed["qualification_passed"]
    plan = plans[2]
    low = import_loss_events(plan, encode(controller(plan, [row(plan, 300, bit=1), row(plan, 350, herald=0), row(plan, 350)], "low-yield")))
    low_report = loss_campaign_report(campaign, reports[:2] + [low] + reports[3:])
    assert not low_report["qualification_passed"]
    group = next(item for item in low_report["groups"].values() if item["qualified_runs"] == 2)
    assert group["pooled_accepted_yield"] == _rational(Fraction(13, 30))
    assert group["minimum_observed_yield"] == _rational(Fraction(3, 10))
    wrong = import_loss_events(plan, encode(controller(plan, [row(plan, 125, bit=0), row(plan, 375, bit=1),
                                                            row(plan, 250, herald=0), row(plan, 250)], "conditional-outlier")))
    wrong_report = loss_campaign_report(campaign, reports[:2] + [wrong] + reports[3:])
    assert not wrong_report["qualification_passed"]
    zero = import_loss_events(plan, encode(controller(plan, [row(plan, 1000, herald=0)], "zero-accepted")))
    zero_report = loss_campaign_report(campaign, reports[:2] + [zero] + reports[3:])
    assert zero_report["status"] == "complete" and not zero_report["qualification_passed"]
    assert zero_report["conditional_incomplete_plans"] == [plan["fingerprint"]]
    if args.example_dir:
        args.example_dir.mkdir(parents=True, exist_ok=True)
        request = dict(name="synthetic repeated-loss example", minimum_repetitions=3, plans=plans[:3])
        (args.example_dir / "loss_campaign_request.json").write_bytes(encode(request))
        for index in range(3):
            (args.example_dir / f"loss_run_{index}_plan.json").write_bytes(encode(plans[index]))
            (args.example_dir / f"loss_run_{index}_controller_events.json").write_bytes(artifacts[index])
    paths = ("native_relational_qc/loss_campaign.py", "native_relational_qc/loss_acquisition.py",
             "native_relational_qc/experiment_campaign.py", "native_relational_qc/experiment_ledger.py",
             "native_relational_qc/__main__.py", "tests/test_loss_campaign.py", "benchmarks/loss_campaign_audit.py")
    record = dict(schema="nrqc-loss-campaign-audit-v1", python=sys.version.split()[0], campaign=campaign,
                  healthy=summary(healthy), missing=summary(missing), failed=summary(failed),
                  low_yield=summary(low_report), conditional_outlier=summary(wrong_report), zero_accepted=summary(zero_report),
                  observation_fingerprints=[report["fingerprint"] for report in reports],
                  healthy_campaign_exact_replay=True, contexts=2, repetitions=3,
                  source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
                  evidence_class="SYNTHETIC_LOSS_CAMPAIGN_QUALIFICATION", hardware_submissions=0)
    args.out.write_bytes(encode(record))
    print(json.dumps(dict(planned=6, contexts=2, healthy_qualified=True, negative_controls=5, hardware_submissions=0)))


if __name__ == "__main__":
    main()
