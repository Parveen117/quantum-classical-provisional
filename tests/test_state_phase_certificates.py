import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class StatePhaseCertificateTests(unittest.TestCase):
    def test_computational_basis_is_not_phase_proof(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "trial-bell-evaluation.json").write_text(json.dumps({
                "model_id": "bell_phi_plus_runtime",
                "basis": "computational",
                "expected_distribution": {"00": 0.5, "11": 0.5},
                "observed_distribution": {"00": 0.49, "11": 0.51}
            }), encoding="utf-8")
            result = subprocess.run([
                sys.executable,
                str(Path(__file__).parents[1] / "tools" / "build_state_phase_certificates.py"),
                "--root", str(root)
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            phase = json.loads((root / "generated_certificates" / "quantum_phase_certificate.json").read_text())
            state = json.loads((root / "generated_certificates" / "quantum_state_certificate.json").read_text())
            self.assertEqual(phase["evidence_status"], "UNEVALUATED")
            self.assertEqual(state["evidence_status"], "PARTIAL")

    def test_phase_witness_can_evaluate_sector(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "trial-bell-evaluation.json").write_text(json.dumps({
                "model_id": "bell_phi_plus_runtime",
                "xx_expectation": 0.96,
                "yy_expectation": -0.94,
                "zz_expectation": 0.98
            }), encoding="utf-8")
            subprocess.run([
                sys.executable,
                str(Path(__file__).parents[1] / "tools" / "build_state_phase_certificates.py"),
                "--root", str(root)
            ], check=True, capture_output=True, text=True)
            phase = json.loads((root / "generated_certificates" / "quantum_phase_certificate.json").read_text())
            self.assertEqual(phase["evidence_status"], "EVALUATED")


if __name__ == "__main__":
    unittest.main()
