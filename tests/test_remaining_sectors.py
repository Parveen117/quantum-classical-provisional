import json
import tempfile
import unittest
from pathlib import Path

from tools.evaluate_remaining_sectors import state_certificate, dynamics_certificate, memory_certificate


class RemainingSectorTests(unittest.TestCase):
    def test_state_fidelity_recognition_requires_declared_physical_origin(self):
        """The provenance guard withholds physical closure for undeclared origin:
        the quantitative rule passes but the classification is downgraded."""
        cert = state_certificate({"fidelity": 0.97, "threshold": 0.9})
        self.assertEqual(cert["evidence_status"], "EVALUATED")
        self.assertEqual(cert["computational_classification"], "RECOGNITION")
        self.assertEqual(cert["classification"], "RESIDUE")
        self.assertFalse(cert["physical_closure_eligible"])

    def test_state_fidelity_recognition_with_hardware_origin(self):
        cert = state_certificate({"fidelity": 0.97, "threshold": 0.9, "evidence_origin": "hardware"})
        self.assertEqual(cert["evidence_status"], "EVALUATED")
        self.assertEqual(cert["classification"], "RECOGNITION")
        self.assertTrue(cert["physical_closure_eligible"])

    def test_dynamics_rejects_large_path_gap(self):
        cert = dynamics_certificate({"path_gap": 0.2, "tolerance": 0.05})
        self.assertEqual(cert["classification"], "REJECT")

    def test_memory_detects_residue(self):
        cert = memory_certificate({"ordered_metric_values": [0.01, 0.08, 0.02], "drift_threshold": 0.03})
        self.assertEqual(cert["evidence_status"], "EVALUATED")
        self.assertEqual(cert["classification"], "RESIDUE")

    def test_missing_memory_is_unevaluated(self):
        cert = memory_certificate(None)
        self.assertEqual(cert["evidence_status"], "UNEVALUATED")


if __name__ == "__main__":
    unittest.main()
