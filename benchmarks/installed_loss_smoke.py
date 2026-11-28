"""Installed-wheel loss intake, ledger and campaign workflow without a checkout import."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import native_relational_qc

assert sys.version_info[:2] == (3, 12), sys.version
PACKAGE = Path(native_relational_qc.__file__).resolve().parent
assert "site-packages" in PACKAGE.parts, "install the wheel before running this qualification"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nrqc", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    if (work / "loss.jsonl").exists() or (work / "native_relational_qc").exists():
        raise ValueError("choose a fresh directory outside the source checkout")
    calls = []
    def run(*arguments, code=0):
        result = subprocess.run([str(args.nrqc), *map(str, arguments)], cwd=work,
                                capture_output=True, text=True)
        if result.returncode != code:
            raise AssertionError(dict(command=list(map(str, arguments)), code=result.returncode,
                                      stdout=result.stdout, stderr=result.stderr))
        calls.append(dict(command=arguments[0], returncode=result.returncode))
        return json.loads(result.stdout)
    examples = PACKAGE / "experiments"
    plan = run("loss-plan", examples / "loss_experiment.json", "--policy", examples / "loss_policy.json",
               "--reference", examples / "loss_reference.json", "--thresholds", examples / "loss_thresholds.json",
               "--out", work / "single-loss-plan.json")
    assert plan["fingerprint"] == json.loads((examples / "loss_plan.json").read_text())["fingerprint"]
    campaign = work / "campaign.json"
    run("loss-campaign-plan", examples / "loss_campaign_request.json", "--out", campaign)
    ledger = work / "loss.jsonl"
    reports = []
    for index in range(3):
        raw = work / f"raw-{index}.json"
        raw.write_bytes((examples / f"loss_run_{index}_controller_events.json").read_bytes())
        report = work / f"report-{index}.json"
        output = run("import-loss-events", examples / f"loss_run_{index}_plan.json", raw, "--out", report)
        assert output["qualification_passed"] and output["accepted"] == 500
        checked = run("verify-loss-observation", report, "--source-artifact", raw)
        assert checked["source_artifact_hash_verified"]
        run("record-observation", report, "--ledger", ledger)
        reports.append(report)
    previous = ledger.read_bytes()
    assert not run("record-observation", reports[0], "--ledger", ledger)["appended"]
    assert ledger.read_bytes() == previous
    verified = run("verify-experiment-ledger", "--ledger", ledger)
    assert verified["observations_replayed"] == 3
    result_path = work / "campaign-report.json"
    result = run("loss-campaign-report", campaign, "--ledger", ledger, "--require-qualified", "--out", result_path)
    assert result["qualification_passed"]
    assert run("verify-loss-campaign-report", result_path)["qualification_passed"]
    low_raw = work / "low-yield.json"
    document = json.loads((work / "raw-2.json").read_text())
    document["job_id"] = "installed-low-yield"
    for entry, count in zip(document["events"], (300, 350, 350)):
        entry["count"] = count
    low_raw.write_text(json.dumps(document))
    low_report = work / "low-report.json"
    low = run("import-loss-events", examples / "loss_run_2_plan.json", low_raw, "--out", low_report)
    assert not low["qualification_gates"]["minimum_yield"] and low["qualification_gates"]["conditional_error"]
    rejected = run("loss-campaign-report", campaign, reports[0], reports[1], low_report, "--require-qualified", code=3)
    assert not rejected["qualification_passed"]
    assert next(iter(rejected["groups"].values()))["pooled_accepted_yield"] == dict(numerator=13, denominator=30)
    conflict = run("record-observation", low_report, "--ledger", ledger, code=2)
    assert conflict["status"] == "invalid_request" and ledger.read_bytes() == previous
    zero_raw, zero_report = work / "zero-events.json", work / "zero-report.json"
    document["job_id"] = "installed-zero-accepted"
    document["events"] = [document["events"][1]]
    document["events"][0]["count"] = 1000
    zero_raw.write_text(json.dumps(document))
    zero = run("import-loss-events", examples / "loss_run_2_plan.json", zero_raw, "--out", zero_report)
    assert zero["conditional_probability_one"] is None and zero["status"] == "incomplete"
    run("verify-loss-observation", zero_report, "--source-artifact", zero_raw)
    zero_campaign = run("loss-campaign-report", campaign, reports[0], reports[1], zero_report, "--require-qualified", code=3)
    assert zero_campaign["conditional_incomplete_plans"] and not zero_campaign["qualification_passed"]
    raw = work / "raw-0.json"
    raw.write_bytes(raw.read_bytes() + b"\n")
    run("verify-loss-observation", reports[0], "--source-artifact", raw, code=2)
    document = json.loads(low_raw.read_text())
    document["events"][0]["count"] -= 1
    low_raw.write_text(json.dumps(document))
    run("import-loss-events", examples / "loss_run_2_plan.json", low_raw, code=2)
    source = ("loss_acquisition.py", "loss_campaign.py", "model_experiment.py", "experiment_campaign.py",
              "experiment_ledger.py", "__main__.py")
    qualification = dict(schema="nrqc-installed-loss-smoke-v1", python=sys.version.split()[0],
                         wheel_sha256=hashlib.sha256(args.wheel.read_bytes()).hexdigest(), commands=calls,
                         imported_from_installed_package=True, qiskit_available=importlib.util.find_spec("qiskit") is not None,
                         qualified_campaign=True, ledger_observations=3, idempotent_retry_byte_identical=True,
                         low_yield_blocked=True, zero_conditional_preserved=True, changed_source_rejected=True,
                         conflicting_result_rejected=True, missing_attempt_rejected=True,
                         installed_source_sha256={name: hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() for name in source},
                         evidence_class="INSTALLED_SOFTWARE_SYNTHETIC_LOSS_QUALIFICATION", hardware_submissions=0)
    args.out.write_text(json.dumps(qualification, sort_keys=True, indent=2) + "\n")
    print(json.dumps(dict(commands=len(calls), qualified_campaign=True, low_yield_blocked=True, zero_conditional_preserved=True)))


if __name__ == "__main__":
    main()
