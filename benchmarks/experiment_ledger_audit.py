"""Retain synthetic acquisition ledger, idempotency and semantic-replay evidence."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

assert sys.version_info[:2] == (3, 12), sys.version
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.model_experiment_audit import acquisition_for
from native_relational_qc.experiment_ledger import record_observation, verify_experiment_ledger
from native_relational_qc.model_experiment import experiment_plan, observe
from quantum_native_bridge_pro import QuantumNativeBridge
from quantum_native_bridge_pro.bridge import canonical_json, sha256_hex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads((ROOT / "native_relational_qc/experiments/synthetic_plan.json").read_text())
    result = json.loads((ROOT / "native_relational_qc/experiments/synthetic_result.json").read_text())
    report = observe(plan, result)
    if args.ledger.exists():
        raise ValueError("audit requires a fresh ledger output path")
    first = record_observation(report, args.ledger)
    digest_before = hashlib.sha256(args.ledger.read_bytes()).hexdigest()
    repeat = record_observation(report, args.ledger)
    assert repeat["appended"] is False
    assert hashlib.sha256(args.ledger.read_bytes()).hexdigest() == digest_before
    second_plan = experiment_plan(plan["prediction"], plan["binding"], run_id="synthetic-negative-run",
                                  shots=plan["shots"], tolerance=plan["tolerance"])
    negative = observe(second_plan, acquisition_for(second_plan, {"0": 21, "1": 79}, "negative"))
    second = record_observation(negative, args.ledger)
    verified = verify_experiment_ledger(args.ledger)
    assert verified["observations_replayed"] == 2
    assert verified["exact_classifications"] == {"RECOGNITION": 1, "ACTIONABLE_RESIDUE": 1}
    rejected = []
    conflict = observe(plan, acquisition_for(plan, {"0": 21, "1": 79}, "different-job"))
    try:
        record_observation(conflict, args.ledger)
    except ValueError as error:
        rejected.append(dict(control="same-plan-different-result", reason=str(error)))
    else:
        raise AssertionError("conflicting plan result was recorded")
    with tempfile.TemporaryDirectory() as temp:
        bad_path = Path(temp) / "repaired-chain.jsonl"
        record = json.loads(args.ledger.read_text().splitlines()[0])
        record["recognition"]["distribution_gap"] = 0.99
        payload = {k: v for k, v in record.items() if k not in ("record_hash", "chain_hash")}
        record["record_hash"] = sha256_hex(canonical_json(payload))
        record["chain_hash"] = sha256_hex(canonical_json(dict(previous_hash=record["previous_hash"],
                                                            record_hash=record["record_hash"], sequence=1)))
        bad_path.write_text(json.dumps(record) + "\n")
        assert QuantumNativeBridge(bad_path).verify_chain()["valid"]
        try:
            verify_experiment_ledger(bad_path)
        except ValueError as error:
            rejected.append(dict(control="changed-metrics-with-repaired-chain", reason=str(error)))
        else:
            raise AssertionError("repaired chain bypassed semantic replay")
    paths = ("native_relational_qc/experiment_ledger.py", "native_relational_qc/model_experiment.py",
             "native_relational_qc/__main__.py", "quantum_native_bridge_pro/bridge.py",
             "quantum_native_bridge_pro/expected_models.py", "pyproject.toml",
             "tests/test_experiment_ledger.py", "benchmarks/experiment_ledger_audit.py")
    document = dict(schema="nrqc-experiment-ledger-audit-v1", python=sys.version.split()[0],
                    first_write=first, idempotent_retry=repeat, second_write=second,
                    verification=verified, rejected_controls=rejected,
                    ledger_sha256=hashlib.sha256(args.ledger.read_bytes()).hexdigest(),
                    source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
                    evidence_class="SYNTHETIC_ACQUISITION_LEDGER", hardware_submissions=0)
    args.out.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n")
    print(json.dumps(dict(replayed=verified["observations_replayed"],
                          duplicate_appended=repeat["appended"], rejected_controls=len(rejected))))


if __name__ == "__main__":
    main()
