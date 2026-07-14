from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDER = REPO_ROOT / "tools" / "build_unified_quantum_certificate.py"


class UnifiedCertificateBuilderTests(unittest.TestCase):
    def run_builder(self, root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUILDER), "--root", str(root), *extra],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_recognition_and_source_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "trial-bell-evaluation.json").write_text(
                json.dumps({
                    "distribution_gap": 0.02,
                    "tolerance": 0.08,
                    "classification": "RECOGNITION",
                    "recognized": True,
                }),
                encoding="utf-8",
            )
            result = self.run_builder(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            cert = json.loads((root / "generated_certificates" / "unified_quantum_certificate.json").read_text(encoding="utf-8"))
            self.assertEqual(cert["overall_classification"], "RECOGNITION")
            self.assertEqual(cert["source_count"], 1)
            self.assertEqual(len(cert["sources"][0]["source_sha256"]), 64)
            self.assertTrue(cert["residue_sectors"]["distribution"]["evaluated"])
            self.assertFalse(cert["residue_sectors"]["phase"]["evaluated"])

    def test_reject_dominates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "trial-bell-evaluation.json").write_text(
                json.dumps({"classification": "RECOGNITION"}), encoding="utf-8"
            )
            (root / "trial-backend-comparison-report.json").write_text(
                json.dumps({"status": "FAIL", "backend_gap": 0.9}), encoding="utf-8"
            )
            result = self.run_builder(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            cert = json.loads((root / "generated_certificates" / "unified_quantum_certificate.json").read_text(encoding="utf-8"))
            self.assertEqual(cert["overall_classification"], "REJECT")

    def test_no_inputs_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_builder(Path(tmp))
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
