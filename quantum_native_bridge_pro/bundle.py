#!/usr/bin/env python3
"""Certificate bundle builder for Quantum Native Bridge Pro.

This combines ledger verification, expected-model evaluation, calibration evidence,
and stability reports into a single reproducible evidence bundle.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from .bridge import QuantumNativeBridge, canonical_json, sha256_hex


def read_json(path: str | Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def optional_json(path: str | Path | None) -> Dict[str, Any] | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    return read_json(p)


def build_bundle(
    ledger_path: str | Path,
    expected_evaluation_path: str | Path | None = None,
    calibration_report_path: str | Path | None = None,
    stability_report_path: str | Path | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    bridge = QuantumNativeBridge(ledger_path)
    ledger_verification = bridge.verify_chain()
    certificate = bridge.export_certificate()
    bundle = {
        "bundle_type": "QUANTUM_NATIVE_BRIDGE_EVIDENCE_BUNDLE",
        "issued_at_ns": time.time_ns(),
        "ledger_path": str(ledger_path),
        "ledger_verification": ledger_verification,
        "bridge_certificate": certificate,
        "expected_evaluation": optional_json(expected_evaluation_path),
        "calibration_report": optional_json(calibration_report_path),
        "stability_report": optional_json(stability_report_path),
        "metadata": dict(metadata or {}),
    }
    bundle["bundle_hash"] = sha256_hex(canonical_json(bundle))
    return bundle


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build Quantum Native Bridge evidence bundle")
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--expected")
    parser.add_argument("--calibration")
    parser.add_argument("--stability")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    bundle = build_bundle(args.ledger, args.expected, args.calibration, args.stability)
    Path(args.out).write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
