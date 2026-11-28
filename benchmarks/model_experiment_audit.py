"""Synthetic acquisition qualification for frozen saved-model readout contracts."""
import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

assert sys.version_info[:2] == (3, 12), sys.version
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.model_runtime_audit import dense_readout
from native_relational_qc.learning_tasks import curvature_splits
from native_relational_qc.model_experiment import experiment_plan, observe, verify_observation
from native_relational_qc.model_runtime import predict
from native_relational_qc.self_learning import digest


def binding_for(prediction):
    return dict(schema="nrqc-acquisition-binding-v1", origin="synthetic",
                provider="nrqc-offline-qualification", backend="synthetic-three-wire-line",
                device_fingerprint=digest(prediction["device"]),
                calibration=dict(calibration_id="synthetic-fixture-20261112",
                                 source_sha256=hashlib.sha256(b"synthetic fixture; no device calibration").hexdigest(),
                                 captured_at="2026-11-12T00:00:00Z", valid_until="2026-11-13T00:00:00Z"))


def acquisition_for(plan, counts, index):
    return dict(schema="nrqc-acquisition-result-v1", plan_fingerprint=plan["fingerprint"],
                binding_fingerprint=digest(plan["binding"]), program_sha256=plan["program_sha256"],
                job_id=f"synthetic-acquisition-{index}", origin="synthetic",
                provider=plan["binding"]["provider"], backend=plan["binding"]["backend"],
                started_at="2026-11-12T01:00:00Z", completed_at="2026-11-12T01:00:01Z",
                shots=plan["shots"], counts=counts,
                source_sha256=hashlib.sha256(json.dumps(counts, sort_keys=True).encode()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--example-dir", type=Path)
    args = parser.parse_args()
    model = json.loads((ROOT / "native_relational_qc/learning/structure_model.json").read_text())
    profile = json.loads((ROOT / "native_relational_qc/calculator_examples/three_wire_line.json").read_text())
    examples, _ = curvature_splits()
    rng = np.random.default_rng(20261112)
    cases, representatives, classes = [], {}, {}
    for index, example in enumerate(examples["test"]):
        prediction = predict(model, example.features, view=example.view, profile=profile)
        plan = experiment_plan(prediction, binding_for(prediction), run_id=example.name, shots=512,
                               tolerance=dict(numerator=1, denominator=8))
        p = min(1.0, max(0.0, dense_readout(prediction)))
        one = int(rng.binomial(plan["shots"], p))
        result = acquisition_for(plan, {"0": plan["shots"] - one, "1": one}, index)
        report = observe(plan, result)
        assert verify_observation(report)["status"] == "verified"
        assert report["evidence_class"] == "SYNTHETIC_OBSERVATION"
        cls = report["classification"]
        classes[cls] = classes.get(cls, 0) + 1
        cases.append(dict(example=example.name, features=list(example.features), counts=result["counts"],
                          classification=cls, absolute_error=report["absolute_error"],
                          plan_fingerprint=plan["fingerprint"], report_fingerprint=report["fingerprint"]))
        if index == 0:
            representatives["sampled"] = report
    # Independently visible exact tolerance endpoints, plus deliberately wrong
    # data against a deterministic readout. These are synthetic negative controls.
    prediction = predict(model, (0, 32), view="first_layer", profile=profile)
    plan = experiment_plan(prediction, binding_for(prediction), run_id="boundary-control", shots=100,
                           tolerance=dict(numerator=1, denominator=10))
    boundaries = []
    for one, cls in ((90, "RECOGNITION"), (80, "BOUNDED_RESIDUE"), (79, "ACTIONABLE_RESIDUE")):
        report = observe(plan, acquisition_for(plan, {"0": 100 - one, "1": one}, one))
        assert report["classification"] == cls
        boundaries.append(dict(count_one=one, classification=cls, absolute_error=report["absolute_error"]))
        if one == 79:
            representatives["deliberate_residue"] = report
    rejected = []
    changes = dict(program_sha256="0" * 64, shots=99, origin="physical_backend",
                   completed_at="2026-11-13T00:00:00Z", counts={"0": 5, "1": 94})
    valid = acquisition_for(plan, {"0": 5, "1": 95}, "valid")
    for key, value in changes.items():
        result = copy.deepcopy(valid)
        result[key] = value
        try:
            observe(plan, result)
        except ValueError as error:
            rejected.append(dict(changed_field=key, reason=str(error)))
        else:
            raise AssertionError(f"negative control admitted: {key}")
    if args.example_dir:
        args.example_dir.mkdir(parents=True, exist_ok=True)
        for name, document in (("synthetic_binding.json", binding_for(prediction)),
                               ("synthetic_plan.json", plan), ("synthetic_result.json", valid)):
            (args.example_dir / name).write_text(json.dumps(document, sort_keys=True, indent=2) + "\n")
    paths = ("native_relational_qc/model_experiment.py", "native_relational_qc/model_runtime.py",
             "native_relational_qc/__main__.py", "native_relational_qc/learning/structure_model.json",
             "benchmarks/model_experiment_audit.py", "benchmarks/model_runtime_audit.py",
             "tests/test_model_experiment.py")
    document = dict(schema="nrqc-model-experiment-audit-v1", python=sys.version.split()[0],
                    evidence_class="SYNTHETIC_ACQUISITION_QUALIFICATION", hardware_submissions=0,
                    sampling=dict(source="independent NumPy state probabilities", seed=20261112,
                                  shots_per_case=512, method="NumPy Generator.binomial"),
                    model_fingerprint=model["fingerprint"], cases=cases, classifications=classes,
                    exact_replay_cases=len(cases), boundary_controls=boundaries, rejected_controls=rejected,
                    representative_reports=representatives,
                    source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths})
    args.out.write_text(json.dumps(document, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(cases=len(cases), classifications=classes, boundary_controls=len(boundaries),
                          rejected_controls=len(rejected), hardware_submissions=0)))


if __name__ == "__main__":
    main()
