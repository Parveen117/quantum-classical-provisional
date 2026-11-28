"""Source-byte binding for an explicitly synthetic controller-counts artifact."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

assert sys.version_info[:2] == (3, 12), sys.version
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from native_relational_qc.model_experiment import import_observation, verify_observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    examples = ROOT / "native_relational_qc/experiments"
    plan = json.loads((examples / "synthetic_plan.json").read_text())
    raw = (examples / "synthetic_controller_counts.json").read_bytes()
    report = import_observation(plan, raw)
    verified = verify_observation(report, source_bytes=raw)
    assert verified["source_artifact_hash_verified"]
    controls = []
    for name, changed in (("extra-newline", raw + b"\n"),
                          ("duplicate-shots-key", raw.replace(b'"shots": 100', b'"shots": 100, "shots": 100'))):
        try:
            verify_observation(report, source_bytes=changed)
        except ValueError as error:
            controls.append(dict(control=name, reason=str(error)))
        else:
            raise AssertionError("changed source artifact was accepted")
    paths = ("native_relational_qc/model_experiment.py", "native_relational_qc/__main__.py",
             "native_relational_qc/experiments/synthetic_controller_counts.json",
             "tests/test_controller_intake.py", "benchmarks/controller_intake_audit.py")
    document = dict(schema="nrqc-controller-intake-audit-v1", python=sys.version.split()[0],
                    observation=report, verification=verified, rejected_controls=controls,
                    source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
                    evidence_class="SYNTHETIC_CONTROLLER_INTAKE", hardware_submissions=0)
    args.out.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n")
    print(json.dumps(dict(source_artifact_hash_verified=True, rejected_controls=len(controls), hardware_submissions=0)))


if __name__ == "__main__":
    main()
