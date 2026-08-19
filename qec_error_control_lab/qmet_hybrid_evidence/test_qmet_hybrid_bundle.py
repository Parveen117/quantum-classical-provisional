import copy
import json
from pathlib import Path
import tempfile
import unittest

from qmet_hybrid_bundle import (
    build_bundle,
    load_json,
    validate_sources,
    verify_bundle,
    verify_local_qec_anchors,
)


HERE = Path(__file__).resolve().parent


class QmetHybridBundleTests(unittest.TestCase):
    def setUp(self):
        self.sources = load_json(HERE / "qmet_evidence_sources.json")
        self.attestation = load_json(HERE / "qseam_nv_attestation.json")

    def make_local_root(self, *, tamper_gate=False):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        components = {item["component_id"]: item for item in self.sources["components"]}
        hardware = components["ibm_shor_hardware_syndrome"]
        gate = components["rnke_shor_recognition_gate"]
        theorem = components["rnke_hardware_theorem_binding"]
        for item in (hardware, gate, theorem):
            (root / item["path"]).parent.mkdir(parents=True, exist_ok=True)
        (root / hardware["path"]).write_text(
            json.dumps({
                "certificate_sha256": hardware["certificate_sha256"],
                "classification": hardware["observed_outcome"],
            }), encoding="utf-8"
        )
        gate_value = "f" * 64 if tamper_gate else gate["certificate_sha256"]
        (root / gate["path"]).write_text(gate_value + "\n", encoding="utf-8")
        (root / theorem["path"]).write_text(theorem["certificate_sha256"] + "\n", encoding="utf-8")
        return temporary, root

    def pass_bundle(self):
        temporary, root = self.make_local_root()
        self.addCleanup(temporary.cleanup)
        components = validate_sources(self.sources)
        checks = verify_local_qec_anchors(root, components)
        return build_bundle(self.sources, self.attestation, checks)

    def test_bounded_bundle_passes(self):
        bundle = self.pass_bundle()
        self.assertEqual(bundle["classification"], "PASS_BOUNDED_QMET_HYBRID_EVIDENCE_BUNDLE_V1")
        self.assertEqual(bundle["review_readiness"], "READY_FOR_QMET_BOUNDED_POC_REVIEW")
        self.assertTrue(verify_bundle(bundle))

    def test_deterministic(self):
        self.assertEqual(self.pass_bundle(), self.pass_bundle())

    def test_pinned_certificate_hash(self):
        expected = (HERE / "EXPECTED_QMET_HYBRID_BUNDLE.sha256").read_text(encoding="utf-8").split()[0]
        self.assertEqual(self.pass_bundle()["certificate_sha256"], expected)

    def test_component_order_is_predeclared(self):
        changed = copy.deepcopy(self.sources)
        changed["components"][0], changed["components"][1] = changed["components"][1], changed["components"][0]
        with self.assertRaises(ValueError):
            validate_sources(changed)

    def test_unsafe_composition_policy_rejected(self):
        changed = copy.deepcopy(self.sources)
        changed["composition_policy"] = "PROMOTE_ALL_TO_HARDWARE"
        with self.assertRaises(ValueError):
            validate_sources(changed)

    def test_qseam_anchor_tamper_makes_bundle_incomplete(self):
        changed = copy.deepcopy(self.attestation)
        changed["campaign_sha256"] = "f" * 64
        temporary, root = self.make_local_root()
        self.addCleanup(temporary.cleanup)
        checks = verify_local_qec_anchors(root, validate_sources(self.sources))
        bundle = build_bundle(self.sources, changed, checks)
        self.assertEqual(bundle["classification"], "INCOMPLETE_QMET_HYBRID_EVIDENCE_BUNDLE_V1")

    def test_local_pin_tamper_makes_bundle_incomplete(self):
        temporary, root = self.make_local_root(tamper_gate=True)
        self.addCleanup(temporary.cleanup)
        checks = verify_local_qec_anchors(root, validate_sources(self.sources))
        bundle = build_bundle(self.sources, self.attestation, checks)
        self.assertFalse(bundle["checks"]["local_qec_anchor_replay_complete"])
        self.assertEqual(bundle["classification"], "INCOMPLETE_QMET_HYBRID_EVIDENCE_BUNDLE_V1")

    def test_receipt_tamper_detected(self):
        bundle = self.pass_bundle()
        bundle["component_receipts"][1]["observed_outcome"] = "PROMOTED"
        self.assertFalse(verify_bundle(bundle))

    def test_certificate_tamper_detected(self):
        bundle = self.pass_bundle()
        bundle["review_readiness"] = "PHYSICAL_SENSOR_VALIDATED"
        self.assertFalse(verify_bundle(bundle))

    def test_truth_table_never_promotes_physical_claims(self):
        truth = self.pass_bundle()["aggregate_truth_table"]
        self.assertFalse(truth["physical_sensor_validated"])
        self.assertFalse(truth["metrological_traceability_established"])
        self.assertFalse(truth["fault_tolerance_established"])
        self.assertFalse(truth["threshold_established"])
        self.assertFalse(truth["riemann_hypothesis_claimed"])


if __name__ == "__main__":
    unittest.main()
