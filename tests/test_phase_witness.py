import json
import tempfile
import unittest
from pathlib import Path

from tools.evaluate_phase_witness import evaluate


class PhaseWitnessTests(unittest.TestCase):
    def test_phi_plus_recognized(self):
        result = evaluate({
            "target_state": "phi_plus",
            "witnesses": {"XX": 0.96, "YY": -0.94, "ZZ": 0.98},
            "tolerance": 0.10,
        })
        self.assertEqual(result["classification"], "RECOGNITION")
        self.assertEqual(result["evidence_status"], "EVALUATED")

    def test_wrong_phase_rejected(self):
        result = evaluate({
            "target_state": "phi_plus",
            "witnesses": {"XX": -0.96, "YY": 0.94, "ZZ": 0.98},
            "tolerance": 0.10,
        })
        self.assertEqual(result["classification"], "REJECT")

    def test_missing_witness_partial(self):
        result = evaluate({
            "target_state": "phi_plus",
            "witnesses": {"ZZ": 0.98},
            "tolerance": 0.10,
        })
        self.assertEqual(result["evidence_status"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
