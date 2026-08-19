"""The legacy demo ledger predates a change to the record payload.

It is kept for provenance and must NOT be silently rewritten. This test records
the drift so it cannot be forgotten, and checks that a ledger regenerated under
the current schema does verify.
"""
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEGACY = ROOT / "QUANTUM_NATIVE_BRIDGE_PRO_EVIDENCE" / "demo-bridge-ledger.jsonl"
CURRENT = ROOT / "QUANTUM_NATIVE_BRIDGE_PRO_EVIDENCE" / "demo-bridge-ledger-current.jsonl"

sys.path.insert(0, str(ROOT))
from quantum_native_bridge_pro.bridge import QuantumNativeBridge, VerificationError  # noqa: E402


def test_legacy_ledger_does_not_verify_under_current_schema():
    if not LEGACY.exists():
        pytest.skip("legacy ledger absent")
    with pytest.raises(VerificationError):
        QuantumNativeBridge(LEGACY).verify_chain()


def test_regenerated_ledger_verifies():
    subprocess.run([sys.executable, str(ROOT / "tools" / "regenerate_demo_ledger.py"),
                    "--out", str(CURRENT)], check=True, cwd=ROOT)
    report = QuantumNativeBridge(CURRENT).verify_chain()
    assert report["valid"] is True and report["records"] == 3
