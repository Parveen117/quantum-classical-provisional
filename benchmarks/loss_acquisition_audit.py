"""Finite synthetic qualification of retained click-event acquisition."""
import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

assert sys.version_info[:2] == (3, 12), sys.version
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.model_experiment_audit import binding_for
from benchmarks.model_runtime_audit import dense_readout
from native_relational_qc.loss_acquisition import (
    CONTROLLER_SCHEMA, OUTCOMES, REJECTS, import_loss_events, loss_plan, verify_loss_observation,
)
from native_relational_qc.model_experiment import _rational, experiment_plan
from native_relational_qc.model_runtime import predict
from native_relational_qc.self_learning import FIELD, digest


def policy(experiment):
    pairs = [dict(physical_wire=q, zero=f"d{q}_zero", one=f"d{q}_one") for q in experiment["measure_wires"]]
    return dict(schema="nrqc-click-policy-v1", encoding="dual_rail_one_click_per_measured_wire",
                channels=["herald"] + [pair[key] for pair in pairs for key in ("zero", "one")] + ["guard", "extra"],
                readout_pairs=pairs, herald_counts={"herald": 1}, guard_channels=["guard"],
                window_ns=dict(start=0, stop=100), controller_program_sha256=hashlib.sha256(b"synthetic controller with explicit detector outputs").hexdigest(),
                rejection_priority=list(REJECTS))


def reference():
    weights = {key: _rational(Fraction(0)) for key in REJECTS}
    weights.update(no_herald=_rational(Fraction(1, 2)), no_click=_rational(Fraction(1, 2)))
    return dict(schema="nrqc-loss-reference-v1", kind="scalar_survival", model_id="synthetic input-independent loss model",
                source_sha256=hashlib.sha256(b"declared scalar instrument: acceptance 1/2").hexdigest(),
                parameters=dict(survival=_rational(Fraction(1, 2)), rejection_weights=weights))


def thresholds():
    return dict(minimum_yield=_rational(Fraction(2, 5)), minimum_accepted=100,
                conditional_tolerance=_rational(Fraction(1, 10)), joint_tolerance=_rational(Fraction(1, 20)),
                maximum_unclassified=_rational(Fraction(0)))


def row(plan, count, *, bit=None, herald=1, guard=0, extra=0, flags=()):
    values = dict.fromkeys(plan["click_policy"]["channels"], 0)
    values.update(herald=herald, guard=guard, extra=extra)
    if bit is not None:
        pair = plan["click_policy"]["readout_pairs"][0]
        values[pair["one"] if bit else pair["zero"]] = 1
    return dict(clicks=[values[key] for key in plan["click_policy"]["channels"]], flags=list(flags), count=count)


def controller(plan, events, job_id):
    experiment = plan["experiment"]
    return dict(schema=CONTROLLER_SCHEMA, plan_fingerprint=plan["fingerprint"],
                binding_fingerprint=digest(experiment["binding"]), program_sha256=experiment["program_sha256"],
                policy_fingerprint=digest(plan["click_policy"]), controller_program_sha256=plan["click_policy"]["controller_program_sha256"],
                job_id=job_id, origin=experiment["binding"]["origin"], provider=experiment["binding"]["provider"], backend=experiment["binding"]["backend"],
                started_at="2026-11-12T01:00:00Z", completed_at="2026-11-12T01:00:01Z", attempts=experiment["shots"],
                window_ns=plan["click_policy"]["window_ns"], events=events)


def encode(document):
    return json.dumps(document, sort_keys=True, indent=2).encode() + b"\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--example-dir", type=Path)
    args = parser.parse_args()
    source = json.loads((ROOT / "native_relational_qc/experiments/synthetic_plan.json").read_text())
    certain = source["prediction"]
    balanced = predict(certain["model"], (16, 0), view="first_layer", profile=certain["device"])
    assert abs(dense_readout(balanced) - 0.5) < 1e-12
    def make(name, prediction=certain, spec=None, limits=None):
        experiment = experiment_plan(prediction, binding_for(prediction), run_id=name, shots=1000,
                                     tolerance=_rational(Fraction(1, 10)))
        return loss_plan(experiment, policy(experiment), reference() if spec is None else spec,
                         thresholds() if limits is None else limits)
    cases, representatives = [], {}
    def check(name, plan, events, expected):
        raw = encode(controller(plan, events, name))
        report = import_loss_events(plan, raw)
        assert report["classification"] == expected
        assert verify_loss_observation(report, source_bytes=raw)["status"] == "verified"
        cases.append(dict(name=name, plan=plan, controller=json.loads(raw), report_fingerprint=report["fingerprint"],
                          classification=report["classification"], accepted=report["accepted"], accepted_yield=report["accepted_yield"],
                          conditional_probability_one=report["conditional_probability_one"],
                          conditional_absolute_error=report["conditional_absolute_error"],
                          joint_total_variation_error=report["joint_total_variation_error"], qualification_gates=report["qualification_gates"]))
        return report, raw
    good = make("healthy-synthetic-loss")
    healthy, raw = check("healthy", good, [row(good, 500, bit=1), row(good, 250, herald=0), row(good, 250)], "QUALIFIED")
    representatives["healthy"] = healthy
    zero = make("zero-accepted-control")
    check("zero-accepted", zero, [row(zero, 1000, herald=0)], "INCOMPLETE")
    loose = thresholds()
    loose["joint_tolerance"] = _rational(Fraction(1))
    low = make("low-yield-control", limits=loose)
    low_report, _ = check("low-yield", low, [row(low, 300, bit=1), row(low, 350, herald=0), row(low, 350)], "RESIDUE")
    assert low_report["qualification_gates"]["conditional_error"] and not low_report["qualification_gates"]["minimum_yield"]
    wrong = make("wrong-conditional-control")
    check("wrong-conditional", wrong, [row(wrong, 100, bit=0), row(wrong, 400, bit=1), row(wrong, 250, herald=0), row(wrong, 250)], "RESIDUE")
    unknown = make("overlapping-flags-control")
    check("overlapping-flags", unknown, [row(unknown, 1000, herald=0, guard=1, extra=1, flags=("counter_overflow",))], "INCOMPLETE")
    joint = dict.fromkeys(OUTCOMES, FIELD(0))
    joint.update({"accepted:0": FIELD(Fraction(1, 8)), "accepted:1": FIELD(Fraction(3, 8)),
                  "rejected:no_herald": FIELD(Fraction(1, 4)), "rejected:no_click": FIELD(Fraction(1, 4))})
    spec = dict(schema="nrqc-loss-reference-v1", kind="declared_joint", model_id="synthetic outcome-dependent heralding",
                source_sha256=hashlib.sha256(b"acceptance efficiencies: zero 1/4, one 3/4; input probability 1/2").hexdigest(),
                parameters=dict(joint_distribution={key: p.to_dict() for key, p in joint.items()}))
    biased = make("explicit-biased-reference", balanced, spec)
    biased_report, _ = check("biased-reference", biased, [row(biased, 125, bit=0), row(biased, 375, bit=1), row(biased, 250, herald=0), row(biased, 250)], "QUALIFIED")
    assert biased_report["conditional_probability_one"] == _rational(Fraction(3, 4))
    representatives["biased_reference"] = biased_report
    naive = make("incorrect-scalar-reference", balanced)
    check("incorrect-scalar-reference", naive, [row(naive, 125, bit=0), row(naive, 375, bit=1), row(naive, 250, herald=0), row(naive, 250)], "RESIDUE")
    rejected = []
    changed = json.loads(raw)
    changed["events"][0]["count"] -= 1
    for name, source_bytes in (("missing-attempt", encode(changed)), ("byte-change", raw + b"\n")):
        try:
            if name == "byte-change":
                verify_loss_observation(healthy, source_bytes=source_bytes)
            else:
                import_loss_events(good, source_bytes)
        except ValueError as error:
            rejected.append(dict(control=name, reason=str(error)))
        else:
            raise AssertionError("invalid source artifact was accepted")
    if args.example_dir:
        args.example_dir.mkdir(parents=True, exist_ok=True)
        for name, document in (("loss_experiment.json", good["experiment"]), ("loss_policy.json", good["click_policy"]),
                               ("loss_reference.json", good["reference_spec"]), ("loss_thresholds.json", good["thresholds"]),
                               ("loss_plan.json", good)):
            (args.example_dir / name).write_bytes(encode(document))
        (args.example_dir / "loss_controller_events.json").write_bytes(raw)
    paths = ("native_relational_qc/loss_acquisition.py", "native_relational_qc/model_experiment.py",
             "native_relational_qc/experiment_ledger.py", "native_relational_qc/__main__.py",
             "tests/test_loss_acquisition.py", "benchmarks/loss_acquisition_audit.py")
    result = dict(schema="nrqc-loss-acquisition-audit-v1", python=sys.version.split()[0], cases=cases,
                  representative_reports=representatives, rejected_controls=rejected,
                  independent_numpy_balanced_probability=dense_readout(balanced),
                  source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
                  evidence_class="SYNTHETIC_LOSS_ACQUISITION_QUALIFICATION", hardware_submissions=0)
    args.out.write_bytes(encode(result))
    print(json.dumps(dict(cases=len(cases), exact_source_replays=len(cases), rejected_controls=len(rejected), hardware_submissions=0)))


if __name__ == "__main__":
    main()
