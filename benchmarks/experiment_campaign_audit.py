"""Synthetic repeated-run campaign coverage and failure/outlier controls."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

assert sys.version_info[:2] == (3, 12), sys.version
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.model_experiment_audit import acquisition_for, binding_for
from benchmarks.model_runtime_audit import dense_readout
from native_relational_qc.experiment_campaign import campaign_plan, campaign_report, verify_campaign_report
from native_relational_qc.model_experiment import experiment_plan, observe
from native_relational_qc.model_runtime import predict


def summary(report):
    return {k: report[k] for k in ("fingerprint", "status", "qualification_passed", "planned_runs",
                                  "observed_runs", "failed_runs", "missing_plans", "groups", "run_results")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    model = json.loads((ROOT / "native_relational_qc/learning/structure_model.json").read_text())
    profile = json.loads((ROOT / "native_relational_qc/calculator_examples/three_wire_line.json").read_text())
    predictions = [predict(model, features, view="first_layer", profile=profile)
                   for features in ((0, 32), (0, 0), (5, 17))]
    plans = [experiment_plan(prediction, binding_for(prediction), run_id=f"context-{group}-repeat-{repeat}",
                             shots=512, tolerance=dict(numerator=1, denominator=8))
             for group, prediction in enumerate(predictions) for repeat in range(3)]
    # This plan is frozen before any of the following synthetic results exist.
    campaign = campaign_plan(plans, name="three fixed inputs, three independent synthetic repetitions",
                             minimum_repetitions=3)
    rng = np.random.default_rng(20261113)
    reports = []
    for index, plan in enumerate(plans):
        probability = min(1.0, max(0.0, dense_readout(plan["prediction"])))
        one = int(rng.binomial(plan["shots"], probability))
        reports.append(observe(plan, acquisition_for(plan, {"0": 512 - one, "1": one}, index)))
    healthy = campaign_report(campaign, reports)
    assert healthy["qualification_passed"]
    assert verify_campaign_report(healthy)["status"] == "verified"
    partial = campaign_report(campaign, reports[:-1])
    assert partial["status"] == "incomplete" and not partial["qualification_passed"]
    failure = dict(plan_fingerprint=plans[-1]["fingerprint"], kind="timeout",
                   detail="synthetic missing-acquisition control", job_id="synthetic-timeout", source_sha256=None)
    failed = campaign_report(campaign, reports[:-1], failures=[failure])
    assert failed["status"] == "complete" and not failed["qualification_passed"]
    # For the first deterministic-one group, two perfect runs mask one badly
    # biased run in a pooled mean. The per-run policy must still fail the group.
    outlier = observe(plans[0], acquisition_for(plans[0], {"0": 160, "1": 352}, "outlier"))
    bad = campaign_report(campaign, [outlier] + reports[1:])
    assert not bad["qualification_passed"]
    group = next(item for item in bad["groups"].values() if item["exact_classifications"].get("ACTIONABLE_RESIDUE"))
    assert group["pooled_probability_one"] == dict(numerator=43, denominator=48)
    paths = ("native_relational_qc/experiment_campaign.py", "native_relational_qc/experiment_ledger.py",
             "native_relational_qc/model_experiment.py", "native_relational_qc/__main__.py",
             "tests/test_experiment_campaign.py", "benchmarks/experiment_campaign_audit.py")
    document = dict(schema="nrqc-experiment-campaign-audit-v1", python=sys.version.split()[0],
                    campaign=campaign, healthy=summary(healthy), missing=summary(partial),
                    failed=summary(failed), outlier=summary(bad),
                    observation_fingerprints=[report["fingerprint"] for report in reports],
                    synthetic_counts=[report["marginal_counts"] for report in reports],
                    sampling=dict(seed=20261113, shots_per_run=512, contexts=3, repetitions=3,
                                  source="independent NumPy state probabilities"),
                    source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
                    evidence_class="SYNTHETIC_CAMPAIGN_QUALIFICATION", hardware_submissions=0)
    args.out.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n")
    print(json.dumps(dict(planned=healthy["planned_runs"], healthy=healthy["qualification_passed"],
                          missing_status=partial["status"], failure_qualified=failed["qualification_passed"],
                          outlier_qualified=bad["qualification_passed"])))


if __name__ == "__main__":
    main()
