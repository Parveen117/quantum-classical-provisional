"""Exercise installed acquisition commands from outside the source checkout."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import native_relational_qc
from native_relational_qc.self_learning import digest

assert sys.version_info[:2] == (3, 12), sys.version
PACKAGE = Path(native_relational_qc.__file__).resolve().parent
assert "site-packages" in PACKAGE.parts, "install the wheel before running this check"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nrqc", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    assert not (work / "native_relational_qc").exists(), "choose a directory outside the checkout"
    calls = []
    def run(*arguments, code=0):
        result = subprocess.run([str(args.nrqc), *map(str, arguments)], cwd=work,
                                capture_output=True, text=True)
        if result.returncode != code:
            raise AssertionError(dict(command=list(map(str, arguments)), code=result.returncode,
                                      stdout=result.stdout, stderr=result.stderr))
        calls.append(dict(command=arguments[0], returncode=result.returncode))
        return json.loads(result.stdout)
    prediction_path = work / "prediction.json"
    run("predict", PACKAGE / "learning/structure_model.json", "--features", 0, 32,
        "--view", "first_layer", "--device", PACKAGE / "calculator_examples/three_wire_line.json",
        "--out", prediction_path)
    plans = []
    for index in range(3):
        plan = run("experiment-plan", prediction_path, "--binding", PACKAGE / "experiments/synthetic_binding.json",
                   "--run-id", f"installed-run-{index}", "--shots", 100, "--tolerance", "1/10",
                   "--out", work / f"plan-{index}.json", "--qasm-out", work / f"measured-{index}.qasm")
        plans.append(plan)
    request_path, campaign_path = work / "campaign-request.json", work / "campaign.json"
    request_path.write_text(json.dumps(dict(name="installed wheel campaign", minimum_repetitions=3, plans=plans)))
    run("campaign-plan", request_path, "--out", campaign_path)
    ledger_path = work / "observations.jsonl"
    if ledger_path.exists():
        raise ValueError("installed smoke requires a fresh work directory")
    for index, plan in enumerate(plans):
        controller = json.loads((PACKAGE / "experiments/synthetic_controller_counts.json").read_text())
        controller.update(plan_fingerprint=plan["fingerprint"], binding_fingerprint=digest(plan["binding"]),
                          program_sha256=plan["program_sha256"], job_id=f"installed-job-{index}",
                          counts={"0": 5 - index, "1": 95 + index})
        raw_path, report_path = work / f"raw-{index}.json", work / f"observation-{index}.json"
        raw_path.write_text(json.dumps(controller, sort_keys=True, indent=2) + "\n")
        run("import-model-counts", work / f"plan-{index}.json", raw_path, "--out", report_path)
        verified = run("verify-observation", report_path, "--source-artifact", raw_path)
        assert verified["source_artifact_hash_verified"]
        run("record-observation", report_path, "--ledger", ledger_path)
    before = ledger_path.read_bytes()
    retry = run("record-observation", work / "observation-0.json", "--ledger", ledger_path)
    assert not retry["appended"] and before == ledger_path.read_bytes()
    ledger = run("verify-experiment-ledger", "--ledger", ledger_path)
    report_path = work / "campaign-report.json"
    campaign = run("campaign-report", campaign_path, "--ledger", ledger_path,
                   "--require-qualified", "--out", report_path)
    assert campaign["qualification_passed"] and ledger["observations_replayed"] == 3
    run("verify-campaign-report", report_path)
    raw_path = work / "raw-0.json"
    raw_path.write_bytes(raw_path.read_bytes() + b"\n")
    changed_source = run("verify-observation", work / "observation-0.json", "--source-artifact", raw_path, code=2)
    assert changed_source["status"] == "invalid_request"
    controller = json.loads(raw_path.read_text())
    controller["counts"] = {"0": 4, "1": 95}
    raw_path.write_text(json.dumps(controller))
    incomplete = run("import-model-counts", work / "plan-0.json", raw_path, code=2)
    assert incomplete["status"] == "invalid_request"
    source_files = ("model_runtime.py", "model_experiment.py", "experiment_ledger.py", "experiment_campaign.py", "__main__.py")
    document = dict(schema="nrqc-installed-acquisition-smoke-v1", python=sys.version.split()[0],
                    wheel_sha256=hashlib.sha256(args.wheel.read_bytes()).hexdigest(),
                    imported_from_installed_package=True, commands=calls,
                    observations=ledger["observations_replayed"], campaign_qualified=campaign["qualification_passed"],
                    idempotent_retry_byte_identical=True, changed_source_rejected=True,
                    incomplete_raw_counts_rejected=True,
                    installed_source_sha256={name: hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest()
                                             for name in source_files},
                    evidence_class="INSTALLED_SOFTWARE_SYNTHETIC_QUALIFICATION", hardware_submissions=0)
    args.out.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n")
    print(json.dumps(dict(commands=len(calls), observations=3, campaign_qualified=True,
                          imported_from_installed_package=True)))


if __name__ == "__main__":
    main()
