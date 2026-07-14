#!/usr/bin/env python3
"""Validate a physical quantum acquisition record without third-party packages."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

PLACEHOLDERS = {
    "actual_backend_name",
    "provider_name",
    "unique_job_or_run_id",
    "iso-8601 timestamp",
    "sha256",
    "backend calibration reference",
}
AMBIGUOUS = {
    "simulator", "simulation", "simulated-or-external", "jupyter-trial",
    "unknown", "undeclared", "external", "local", "trial",
}
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def canonical_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["record must be a JSON object"]

    required = [
        "evidence_origin", "backend", "provider", "acquisition_id",
        "acquired_at", "shots", "circuit_hash", "raw_result_hash",
    ]
    for key in required:
        if key not in data:
            errors.append(f"missing required field: {key}")

    if data.get("evidence_origin") != "physical_backend":
        errors.append("evidence_origin must equal physical_backend")

    for key in ("backend", "provider", "acquisition_id", "acquired_at", "circuit_hash", "raw_result_hash"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} must be a non-empty string")
            continue
        normalized = value.strip().lower()
        if normalized in PLACEHOLDERS:
            errors.append(f"{key} contains a placeholder value")
        if key == "backend" and normalized in AMBIGUOUS:
            errors.append("backend identity is ambiguous or non-physical")

    shots = data.get("shots")
    if not isinstance(shots, int) or isinstance(shots, bool) or shots < 1:
        errors.append("shots must be a positive integer")

    for key in ("circuit_hash", "raw_result_hash"):
        value = data.get(key)
        if isinstance(value, str) and not HEX64.fullmatch(value):
            errors.append(f"{key} must be a 64-character hexadecimal SHA-256 digest")

    acquired_at = data.get("acquired_at")
    if isinstance(acquired_at, str) and acquired_at.strip().lower() not in PLACEHOLDERS:
        try:
            datetime.fromisoformat(acquired_at.replace("Z", "+00:00"))
        except ValueError:
            errors.append("acquired_at must be a valid ISO-8601 timestamp")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate physical acquisition evidence")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    errors = validate(data)
    result = {
        "certificate_type": "PHYSICAL_ACQUISITION_VALIDATION_CERTIFICATE",
        "version": "1.0.0",
        "valid": not errors,
        "classification": "RECOGNITION" if not errors else "REJECT",
        "errors": errors,
        "source_file": args.input.name,
        "source_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
    }
    result["certificate_sha256"] = canonical_hash(result)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
