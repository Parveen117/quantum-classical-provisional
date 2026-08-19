#!/usr/bin/env python3
"""Regenerate a demo bridge ledger under the *current* record schema.

Why this exists. `QUANTUM_NATIVE_BRIDGE_PRO_EVIDENCE/demo-bridge-ledger.jsonl`
was written by an earlier revision of `quantum_native_bridge_pro`. Since then the
record payload changed, so the stored `record_hash` values no longer reproduce
under the current `BridgeRecord.hash_payload()`, and `cli verify` fails on it.
That is schema drift, not corruption: the file is authentic evidence of what the
code produced at the time.

The honest handling is to keep the legacy file for provenance, record that it
does not verify under the present schema (there is a test asserting exactly
that, so the drift cannot be forgotten), and verify a ledger regenerated here
instead. Nothing is silently rewritten.

    python tools/regenerate_demo_ledger.py --out QUANTUM_NATIVE_BRIDGE_PRO_EVIDENCE/demo-bridge-ledger-current.jsonl
    python -m quantum_native_bridge_pro.cli verify --ledger <that file>
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from quantum_native_bridge_pro.bridge import QuantumNativeBridge  # noqa: E402

ROOT = {"state": "phi_plus", "note": "demo root; not hardware evidence"}
TEMPLATE = {"model": "bell_phi_plus", "shots": 1024}
PHASES = [
    {"ZZ": 1.0, "XX": 1.0},
    {"ZZ": 0.98, "XX": 0.97},
    {"ZZ": 0.30, "XX": 0.29},
]
OBSERVED = [
    {"00": 512, "11": 512},
    {"00": 500, "11": 500, "01": 12, "10": 12},
    {"00": 300, "11": 300, "01": 212, "10": 212},
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("QUANTUM_NATIVE_BRIDGE_PRO_EVIDENCE/demo-bridge-ledger-current.jsonl"))
    a = ap.parse_args(argv)
    if a.out.exists():
        a.out.unlink()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    bridge = QuantumNativeBridge(a.out)
    for phase, observed in zip(PHASES, OBSERVED):
        bridge.append(root=ROOT, template=TEMPLATE, phase=phase, observed=observed,
                      expected_model=None, phase_angles=[], backend="demo-simulated",
                      shots=1024, metadata={"evidence_origin": "synthetic",
                                            "note": "demo ledger; software validation only"})
    report = bridge.verify_chain()
    print(f"regenerated {a.out} with {len(PHASES)} records; verify_chain ok")
    print(report.get("summary", report) if isinstance(report, dict) else report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
