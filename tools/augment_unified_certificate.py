#!/usr/bin/env python3
"""Augment a unified quantum certificate with sector-specific certificates.

The tool preserves the original source certificate, adds state/dynamics/phase
statuses, and refuses full recognition while any required sector is PARTIAL or
UNEVALUATED. No third-party dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

SECTOR_FILES = {
    "state": "quantum_state_certificate.json",
    "dynamics": "quantum_dynamics_certificate.json",
    "phase": "quantum_phase_certificate.json",
    "phase_witness": "quantum_phase_witness_certificate.json",
}
REQUIRED = ("state", "distribution", "dynamics", "bridge", "phase", "frame", "memory", "constitutive", "provenance")


def digest(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return obj


def normalize_status(obj: Dict[str, Any]) -> str:
    return str(obj.get("evidence_status") or obj.get("classification") or "UNDETERMINED").upper()


def main() -> int:
    parser = argparse.ArgumentParser(description="Augment unified quantum certificate")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--unified", type=Path, default=Path("generated_certificates/unified_quantum_certificate.json"))
    parser.add_argument("--out", type=Path, default=Path("generated_certificates/unified_quantum_certificate_v2.json"))
    args = parser.parse_args()

    root = args.root.resolve()
    unified_path = args.unified if args.unified.is_absolute() else root / args.unified
    out_path = args.out if args.out.is_absolute() else root / args.out

    try:
        unified = load(unified_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2

    cert_dir = root / "generated_certificates"
    integrations: Dict[str, Any] = {}
    for key, filename in SECTOR_FILES.items():
        path = cert_dir / filename
        if path.exists():
            obj = load(path)
            integrations[key] = {
                "filename": filename,
                "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "status": normalize_status(obj),
                "classification": str(obj.get("classification", "UNDETERMINED")).upper(),
                "reason": obj.get("reason"),
            }

    sectors = dict(unified.get("residue_sectors", {}))
    for sector in ("state", "dynamics", "phase"):
        integration = integrations.get(sector)
        if integration:
            status = integration["status"]
            sectors[sector] = {
                "evaluated": status == "EVALUATED",
                "evidence_status": status,
                "sources": [integration["filename"]],
                "reason": integration.get("reason"),
            }

    witness = integrations.get("phase_witness")
    if witness and witness.get("status") == "EVALUATED":
        sectors["phase"] = {
            "evaluated": True,
            "evidence_status": "EVALUATED",
            "sources": [witness["filename"]],
            "reason": witness.get("reason"),
        }

    unresolved = []
    for sector in REQUIRED:
        entry = sectors.get(sector, {})
        status = str(entry.get("evidence_status", "EVALUATED" if entry.get("evaluated") else "UNEVALUATED")).upper()
        if not entry.get("evaluated") or status in {"PARTIAL", "UNEVALUATED", "UNDETERMINED"}:
            unresolved.append({"sector": sector, "status": status})

    inherited = str(unified.get("overall_classification", "UNDETERMINED")).upper()
    if inherited == "REJECT" or any(item.get("classification") == "REJECT" for item in integrations.values()):
        overall = "REJECT"
    elif unresolved:
        overall = "RESIDUE"
    else:
        overall = "RECOGNITION"

    output = dict(unified)
    output.update({
        "certificate_type": "UNIFIED_QUANTUM_RECOGNITION_CERTIFICATE",
        "version": "2.0.0",
        "sector_certificate_integrations": integrations,
        "residue_sectors": sectors,
        "unresolved_required_sectors": unresolved,
        "overall_classification": overall,
        "closure_rule": "RECOGNITION requires every required sector to be evaluated and no integrated certificate to reject.",
    })
    output.pop("certificate_sha256", None)
    output["certificate_sha256"] = digest(output)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({
        "output": str(out_path),
        "overall_classification": overall,
        "unresolved_required_sectors": unresolved,
        "certificate_sha256": output["certificate_sha256"],
    }, indent=2))
    return 0 if overall != "REJECT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
