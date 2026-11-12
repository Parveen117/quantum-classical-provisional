import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from native_relational_qc.compact import ResourceLimit
from native_relational_qc.loss_acquisition import (
    ACQUISITION_SCHEMA, CONTROLLER_SCHEMA, OUTCOMES, REJECTS,
    import_loss_events, instrument_reference, loss_plan, observe_loss,
    verify_loss_observation, verify_loss_plan,
)
from native_relational_qc.model_experiment import _rational
from native_relational_qc.self_learning import FIELD, digest
from tests.test_model_experiment import fixture_plan, fixture_prediction, reseal


def policy_for(experiment):
    pairs = [dict(physical_wire=q, zero=f"wire{q}_zero", one=f"wire{q}_one")
             for q in experiment["measure_wires"]]
    return dict(schema="nrqc-click-policy-v1", encoding="dual_rail_one_click_per_measured_wire",
                channels=["herald"] + [pair[bit] for pair in pairs for bit in ("zero", "one")] + ["guard", "extra"],
                readout_pairs=pairs, herald_counts={"herald": 1}, guard_channels=["guard"],
                window_ns=dict(start=0, stop=100), controller_program_sha256=hashlib.sha256(b"synthetic dual-rail controller program").hexdigest(),
                rejection_priority=list(REJECTS))


def scalar_reference(survival=Fraction(1, 2)):
    weights = {key: _rational(Fraction(0)) for key in REJECTS}
    weights.update(no_herald=_rational(Fraction(1, 2)), no_click=_rational(Fraction(1, 2)))
    return dict(schema="nrqc-loss-reference-v1", kind="scalar_survival", model_id="synthetic scalar-loss assumption",
                source_sha256=hashlib.sha256(b"synthetic input-independent scalar-survival model").hexdigest(),
                parameters=dict(survival=_rational(survival), rejection_weights=weights))


def thresholds():
    return dict(minimum_yield=_rational(Fraction(2, 5)), minimum_accepted=100,
                conditional_tolerance=_rational(Fraction(1, 10)), joint_tolerance=_rational(Fraction(1, 20)),
                maximum_unclassified=_rational(Fraction(0)))


def fixture_loss_plan(prediction=None, *, run_id="loss-fixture", wires=None):
    prediction = fixture_prediction() if prediction is None else prediction
    experiment = fixture_plan(prediction, shots=1000, run_id=run_id, wires=wires)
    return loss_plan(experiment, policy_for(experiment), scalar_reference(), thresholds())


def event(plan, count, *, bits=None, herald=1, guard=0, extra=0, flags=(), overrides=None):
    policy = plan["click_policy"]
    values = dict.fromkeys(policy["channels"], 0)
    values.update(herald=herald, guard=guard, extra=extra)
    if bits is not None:
        assert len(bits) == len(policy["readout_pairs"])
        for index, pair in enumerate(policy["readout_pairs"]):
            values[pair["one"] if bits[-1 - index] == "1" else pair["zero"]] = 1
    values.update({} if overrides is None else overrides)
    return dict(clicks=[values[channel] for channel in policy["channels"]], flags=list(flags), count=count)


def controller(plan, events, *, job_id="loss-job"):
    experiment = plan["experiment"]
    return dict(schema=CONTROLLER_SCHEMA, plan_fingerprint=plan["fingerprint"],
                binding_fingerprint=digest(experiment["binding"]), program_sha256=experiment["program_sha256"],
                policy_fingerprint=digest(plan["click_policy"]),
                controller_program_sha256=plan["click_policy"]["controller_program_sha256"],
                job_id=job_id, origin=experiment["binding"]["origin"], provider=experiment["binding"]["provider"],
                backend=experiment["binding"]["backend"], started_at="2026-11-12T01:00:00Z", completed_at="2026-11-12T01:00:01Z",
                attempts=experiment["shots"], window_ns=plan["click_policy"]["window_ns"], events=events)


def raw_bytes(plan, events=None, *, job_id="loss-job"):
    if events is None:
        events = [event(plan, 500, bits="1"), event(plan, 250, herald=0), event(plan, 250)]
    return json.dumps(controller(plan, events, job_id=job_id), sort_keys=True, indent=2).encode() + b"\n"


class LossAcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prediction = fixture_prediction()
        cls.plan = fixture_loss_plan(cls.prediction)

    def test_plan_binds_instrument_policy_and_replays(self):
        self.assertEqual(verify_loss_plan(self.plan)["status"], "verified")
        self.assertEqual(self.plan["reference"]["evidence_class"], "DECLARED_INSTRUMENT_MODEL")
        self.assertEqual(FIELD.from_dict(self.plan["reference"]["accepted_probability"]), FIELD(Fraction(1, 2)))
        self.assertEqual(FIELD.from_dict(self.plan["reference"]["conditional_probability_one"]), FIELD(1))

    def test_every_attempt_and_rejection_is_retained(self):
        raw = raw_bytes(self.plan)
        report = import_loss_events(self.plan, raw)
        self.assertEqual(report["attempts"], 1000)
        self.assertEqual(report["accepted"], 500)
        self.assertEqual(report["rejected_counts"]["no_herald"], 250)
        self.assertEqual(report["rejected_counts"]["no_click"], 250)
        self.assertEqual(report["matched_predicate_counts"]["no_click"], 500)
        self.assertEqual(sum(report["joint_counts"].values()), 1000)
        self.assertTrue(report["qualification_passed"])
        self.assertEqual(report["classification"], "QUALIFIED")
        self.assertEqual(FIELD.from_dict(report["joint_total_variation_error"]), FIELD(0))
        self.assertTrue(verify_loss_observation(report, source_bytes=raw)["source_artifact_hash_verified"])

    def test_zero_accepted_events_keep_the_conditional_result_undefined(self):
        report = import_loss_events(self.plan, raw_bytes(self.plan, [event(self.plan, 1000, herald=0)]))
        self.assertEqual(report["status"], "incomplete")
        self.assertIsNone(report["conditional_probability_one"])
        self.assertIsNone(report["conditional_absolute_error"])
        self.assertFalse(report["qualification_passed"])

    def test_perfect_conditional_result_does_not_hide_low_yield(self):
        t = thresholds()
        t["joint_tolerance"] = _rational(Fraction(1))
        plan = loss_plan(self.plan["experiment"], self.plan["click_policy"], scalar_reference(), t)
        rows = [event(plan, 300, bits="1"), event(plan, 350, herald=0), event(plan, 350)]
        report = import_loss_events(plan, raw_bytes(plan, rows))
        self.assertEqual(FIELD.from_dict(report["conditional_absolute_error"]), FIELD(0))
        self.assertTrue(report["qualification_gates"]["conditional_error"])
        self.assertTrue(report["qualification_gates"]["joint_error"])
        self.assertFalse(report["qualification_gates"]["minimum_yield"])
        self.assertFalse(report["qualification_passed"])

    def test_declared_biased_heralding_uses_its_own_reference(self):
        prediction = fixture_prediction((16, 0))
        self.assertEqual(FIELD.from_dict(prediction["probability_one"]), FIELD(Fraction(1, 2)))
        experiment = fixture_plan(prediction, shots=1000)
        joint = dict.fromkeys(OUTCOMES, FIELD(0))
        joint.update({"accepted:0": FIELD(Fraction(1, 8)), "accepted:1": FIELD(Fraction(3, 8)),
                      "rejected:no_herald": FIELD(Fraction(1, 4)), "rejected:no_click": FIELD(Fraction(1, 4))})
        spec = dict(schema="nrqc-loss-reference-v1", kind="declared_joint", model_id="synthetic biased selection",
                    source_sha256="b" * 64, parameters=dict(joint_distribution={key: p.to_dict() for key, p in joint.items()}))
        plan = loss_plan(experiment, policy_for(experiment), spec, thresholds())
        rows = [event(plan, 125, bits="0"), event(plan, 375, bits="1"), event(plan, 250, herald=0), event(plan, 250)]
        report = import_loss_events(plan, raw_bytes(plan, rows))
        self.assertEqual(report["conditional_probability_one"], _rational(Fraction(3, 4)))
        self.assertEqual(FIELD.from_dict(report["ideal_unitary_probability_one"]), FIELD(Fraction(1, 2)))
        self.assertEqual(FIELD.from_dict(report["conditional_absolute_error"]), FIELD(0))
        self.assertTrue(report["qualification_passed"])

    def test_overlapping_flags_have_one_bucket_and_retained_predicates(self):
        rows = [event(self.plan, 1000, herald=0, guard=1, extra=1, flags=("counter_overflow",))]
        report = import_loss_events(self.plan, raw_bytes(self.plan, rows))
        self.assertEqual(report["rejected_counts"]["unclassified"], 1000)
        self.assertEqual(sum(report["rejected_counts"].values()), 1000)
        for key in ("no_herald", "guard_or_code_violation", "no_click", "unclassified"):
            self.assertEqual(report["matched_predicate_counts"][key], 1000)
        self.assertEqual(report["diagnostic_flag_counts"]["counter_overflow"], 1000)

    def test_guard_multiclick_and_unmonitored_output_are_rejected(self):
        pair = self.plan["click_policy"]["readout_pairs"][0]
        controls = [(event(self.plan, 1000, bits="1", guard=1), "guard_or_code_violation"),
                    (event(self.plan, 1000, bits="1", overrides={pair["zero"]: 1}), "ambiguous_click"),
                    (event(self.plan, 1000, bits="1", extra=1), "unclassified")]
        for row, reason in controls:
            with self.subTest(reason=reason):
                report = import_loss_events(self.plan, raw_bytes(self.plan, [row]))
                self.assertEqual(report["rejected_counts"][reason], 1000)
                self.assertFalse(report["qualification_passed"])

    def test_physical_wire_order_is_preserved_in_multibit_accepted_counts(self):
        plan = fixture_loss_plan(self.prediction, wires=[2, 0, 1])
        rows = [event(plan, 450, bits="100"), event(plan, 50, bits="000"),
                event(plan, 250, herald=0), event(plan, 250)]
        report = import_loss_events(plan, raw_bytes(plan, rows))
        self.assertEqual(report["accepted_counts"], {"100": 450, "000": 50})
        self.assertEqual(report["accepted_marginal_counts"], {"0": 50, "1": 450})
        self.assertEqual(report["conditional_probability_one"], _rational(Fraction(9, 10)))
        self.assertTrue(report["qualification_gates"]["conditional_error"])

    def test_nonclifford_reference_and_residuals_remain_exact(self):
        prediction = fixture_prediction((5, 17))
        plan = fixture_loss_plan(prediction)
        rows = [event(plan, 200, bits="0"), event(plan, 300, bits="1"), event(plan, 250, herald=0), event(plan, 250)]
        report = import_loss_events(plan, raw_bytes(plan, rows))
        error = FIELD(Fraction(3, 5)) - FIELD.from_dict(prediction["probability_one"])
        if error.real_sign() < 0:
            error = -error
        self.assertEqual(FIELD.from_dict(report["conditional_absolute_error"]), error)
        self.assertEqual(verify_loss_observation(report)["status"], "verified")

    def test_wrong_identity_policy_window_and_calibration_are_rejected(self):
        raw = json.loads(raw_bytes(self.plan))
        changes = dict(policy_fingerprint="a" * 64, controller_program_sha256="a" * 64,
                       plan_fingerprint="a" * 64, binding_fingerprint="a" * 64, program_sha256="a" * 64,
                       attempts=999, origin="physical_backend", completed_at="2026-11-13T00:00:00Z",
                       window_ns=dict(start=False, stop=100))
        for key, value in changes.items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                import_loss_events(self.plan, json.dumps(dict(raw, **{key: value})).encode())

    def test_raw_histogram_requires_strict_conserved_integer_counts(self):
        base = json.loads(raw_bytes(self.plan))
        for key, value in (("count", 499), ("count", 500.0), ("count", True),
                           ("flags", ["unknown-controller-flag"]), ("flags", ["timing_invalid", "timing_invalid"]),
                           ("clicks", [1, 0.0, 1, 0, 0])):
            changed = copy.deepcopy(base)
            changed["events"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                import_loss_events(self.plan, json.dumps(changed).encode())
        duplicate = copy.deepcopy(base)
        duplicate["events"] = [event(self.plan, 500, bits="1"), event(self.plan, 500, bits="1")]
        with self.assertRaises(ValueError):
            import_loss_events(self.plan, json.dumps(duplicate).encode())

    def test_implicit_lost_photon_fields_and_duplicate_json_keys_are_rejected(self):
        raw = raw_bytes(self.plan)
        document = json.loads(raw)
        document["events"][0]["lost_photons"] = 0
        with self.assertRaises(ValueError):
            import_loss_events(self.plan, json.dumps(document).encode())
        duplicate = raw.replace(b'"attempts": 1000', b'"attempts": 1000, "attempts": 1000')
        with self.assertRaises(ValueError):
            import_loss_events(self.plan, duplicate)

    def test_invalid_instrument_probabilities_and_zero_reference_acceptance_are_rejected(self):
        for bad in (FIELD(-1), FIELD(2), FIELD.root()):
            joint = dict.fromkeys(OUTCOMES, FIELD(0).to_dict())
            joint["accepted:1"] = bad.to_dict()
            spec = dict(schema="nrqc-loss-reference-v1", kind="declared_joint", model_id="invalid fixture",
                        source_sha256="b" * 64, parameters=dict(joint_distribution=joint))
            with self.assertRaises(ValueError):
                instrument_reference(spec, self.plan["experiment"], self.plan["click_policy"])
        with self.assertRaises(ValueError):
            instrument_reference(scalar_reference(Fraction(0)), self.plan["experiment"], self.plan["click_policy"])

    def test_detector_roles_cannot_overlap_or_reorder(self):
        for change in (dict(herald_counts={self.plan["click_policy"]["readout_pairs"][0]["one"]: 1}),
                       dict(guard_channels=["herald"]), dict(rejection_priority=list(reversed(REJECTS)))):
            policy = dict(self.plan["click_policy"], **change)
            with self.assertRaises(ValueError):
                loss_plan(self.plan["experiment"], policy, scalar_reference(), thresholds())

    def test_reference_budget_normalization_and_zero_acceptance_are_enforced(self):
        def spec(joint):
            return dict(schema="nrqc-loss-reference-v1", kind="declared_joint", model_id="bounded reference control",
                        source_sha256="b" * 64, parameters=dict(joint_distribution={key: p.to_dict() for key, p in joint.items()}))
        joint = dict.fromkeys(OUTCOMES, FIELD(0))
        joint["accepted:1"] = FIELD(Fraction(1, 1 << 5000))
        with self.assertRaises(ResourceLimit):
            instrument_reference(spec(joint), self.plan["experiment"], self.plan["click_policy"])
        joint["accepted:1"] = FIELD(Fraction(1, 2))
        with self.assertRaises(ValueError):
            instrument_reference(spec(joint), self.plan["experiment"], self.plan["click_policy"])
        joint["accepted:1"] = FIELD(0)
        joint["rejected:no_herald"] = FIELD(1)
        with self.assertRaises(ValueError):
            instrument_reference(spec(joint), self.plan["experiment"], self.plan["click_policy"])

    def test_plan_and_report_semantics_are_rechecked_after_checksum_repair(self):
        plan = copy.deepcopy(self.plan)
        plan["reference"]["conditional_probability_one"] = FIELD(0).to_dict()
        with self.assertRaises(ValueError):
            verify_loss_plan(reseal(plan))
        report = import_loss_events(self.plan, raw_bytes(self.plan))
        report["qualification_gates"]["minimum_yield"] = False
        with self.assertRaises(ValueError):
            verify_loss_observation(reseal(report))

    def test_original_artifact_bytes_and_integer_types_are_rechecked(self):
        raw = raw_bytes(self.plan)
        report = import_loss_events(self.plan, raw)
        with self.assertRaises(ValueError):
            verify_loss_observation(report, source_bytes=raw + b"\n")
        altered = json.loads(raw)
        altered["events"][0]["count"] = 500.0
        source = json.dumps(altered).encode()
        acquisition = copy.deepcopy(report["acquisition"])
        acquisition["source_sha256"] = hashlib.sha256(source).hexdigest()
        declared = observe_loss(self.plan, acquisition)
        with self.assertRaises(ValueError):
            verify_loss_observation(declared, source_bytes=source)

    def test_loss_reports_use_the_existing_idempotent_ledger(self):
        from native_relational_qc.experiment_ledger import record_observation, verify_experiment_ledger
        report = import_loss_events(self.plan, raw_bytes(self.plan))
        with tempfile.TemporaryDirectory() as temp:
            ledger = Path(temp) / "loss.jsonl"
            self.assertTrue(record_observation(report, ledger)["appended"])
            self.assertFalse(record_observation(report, ledger)["appended"])
            result = verify_experiment_ledger(ledger)
            self.assertEqual(result["exact_classifications"], {"QUALIFIED": 1})
            self.assertEqual(result["declared_origins"], {"SYNTHETIC_LOSS_OBSERVATION": 1})

    def test_cli_builds_imports_replays_and_records_loss_events(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            files = {key: root / (key + ".json") for key in ("experiment", "policy", "reference", "thresholds", "plan", "raw", "report")}
            for key, document in (("experiment", self.plan["experiment"]), ("policy", self.plan["click_policy"]),
                                   ("reference", self.plan["reference_spec"]), ("thresholds", self.plan["thresholds"])):
                files[key].write_text(json.dumps(document))
            command = [sys.executable, "-m", "native_relational_qc"]
            subprocess.run(command + ["loss-plan", str(files["experiment"]), "--policy", str(files["policy"]),
                                      "--reference", str(files["reference"]), "--thresholds", str(files["thresholds"]),
                                      "--out", str(files["plan"])], check=True, capture_output=True)
            plan = json.loads(files["plan"].read_text())
            files["raw"].write_bytes(raw_bytes(plan))
            subprocess.run(command + ["import-loss-events", str(files["plan"]), str(files["raw"]), "--out", str(files["report"])],
                           check=True, capture_output=True)
            result = subprocess.run(command + ["verify-loss-observation", str(files["report"]), "--source-artifact", str(files["raw"])],
                                    check=True, capture_output=True, text=True)
            self.assertTrue(json.loads(result.stdout)["qualification_passed"])


if __name__ == "__main__":
    unittest.main()
