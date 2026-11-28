"""Lossless contract equivalence and non-dyadic declared survival controls."""
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
from benchmarks.model_experiment_audit import acquisition_for, binding_for
from native_relational_qc.loss_acquisition import import_loss_events, loss_plan, verify_loss_observation
from native_relational_qc.model_experiment import _rational, experiment_plan, import_observation
from native_relational_qc.model_runtime import predict
from native_relational_qc.self_learning import FIELD


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads((ROOT / "native_relational_qc/experiments/loss_experiment.json").read_text())["prediction"]
    balanced = predict(source["model"], (16, 0), view="first_layer", profile=source["device"])
    cases = []
    for name, prediction, ones in (("deterministic-input", source, 950), ("balanced-input", balanced, 490)):
        experiment = experiment_plan(prediction, binding_for(prediction), run_id="lossless-" + name,
                                     shots=1000, tolerance=_rational(Fraction(1, 10)))
        legacy = acquisition_for(experiment, {"0": 1000 - ones, "1": ones}, name)
        del legacy["source_sha256"]
        legacy["schema"] = "nrqc-controller-counts-v1"
        old = import_observation(experiment, encode(legacy))
        spec = reference()
        spec["parameters"]["survival"] = _rational(Fraction(1))
        plan = loss_plan(experiment, policy(experiment), spec, thresholds())
        raw = encode(controller(plan, [row(plan, 1000 - ones, bit=0), row(plan, ones, bit=1)], "lossless-" + name))
        new = import_loss_events(plan, raw)
        assert new["accepted"] == 1000 and not any(new["rejected_counts"].values())
        assert old["observed_probability_one"] == new["conditional_probability_one"]
        assert old["absolute_error"] == new["conditional_absolute_error"] == new["joint_total_variation_error"]
        assert old["classification"] == "RECOGNITION" and new["qualification_passed"]
        assert verify_loss_observation(new, source_bytes=raw)["status"] == "verified"
        cases.append(dict(name=name, counts=legacy["counts"], old_report_fingerprint=old["fingerprint"],
                          loss_report_fingerprint=new["fingerprint"], conditional_probability_one=new["conditional_probability_one"],
                          identical_absolute_errors=new["conditional_absolute_error"], qualification_passed=True))
    experiment = experiment_plan(source, binding_for(source), run_id="rational-third-survival", shots=1200,
                                 tolerance=_rational(Fraction(1, 10)))
    spec, limits = reference(), thresholds()
    spec["parameters"]["survival"] = _rational(Fraction(1, 3))
    limits["minimum_yield"] = _rational(Fraction(1, 4))
    plan = loss_plan(experiment, policy(experiment), spec, limits)
    raw = encode(controller(plan, [row(plan, 400, bit=1), row(plan, 400, herald=0), row(plan, 400)], "third-survival"))
    report = import_loss_events(plan, raw)
    assert report["accepted_yield"] == _rational(Fraction(1, 3))
    assert FIELD.from_dict(report["joint_total_variation_error"]) == FIELD(0)
    assert report["qualification_passed"]
    verify_loss_observation(report, source_bytes=raw)
    paths = ("native_relational_qc/loss_acquisition.py", "native_relational_qc/model_experiment.py",
             "benchmarks/loss_compatibility_audit.py")
    result = dict(schema="nrqc-loss-compatibility-audit-v1", python=sys.version.split()[0], lossless_cases=cases,
                  rational_survival=dict(value=_rational(Fraction(1, 3)), report=report),
                  source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
                  scope="two finite lossless contract comparisons and one declared non-dyadic survival model; no physical equivalence assertion",
                  evidence_class="SYNTHETIC_LOSS_COMPATIBILITY_QUALIFICATION", hardware_submissions=0)
    args.out.write_bytes(encode(result))
    print(json.dumps(dict(lossless_comparisons=2, rational_survival="1/3", exact_replays=3)))


if __name__ == "__main__":
    main()
