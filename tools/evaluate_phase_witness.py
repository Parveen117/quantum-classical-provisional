#!/usr/bin/env python3
"""Evaluate Bell-state phase-sensitive witnesses.

This tool distinguishes states such as Phi+ and Phi- using declared correlation
witnesses. It does not infer phase from computational-basis probabilities alone.
No third-party dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict

REQUIRED = ("XX", "YY", "ZZ")
IDEAL = {
    "phi_plus": {"XX": 1.0, "YY": -1.0, "ZZ": 1.0},
    "phi_minus": {"XX": -1.0, "YY": 1.0, "ZZ": 1.0},
}


def canonical_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_number(name: str, value: Any) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value) or not -1.0 <= value <= 1.0:
        raise ValueError(f"{name} must be finite and within [-1, 1]")
    return value


def evaluate(payload: Dict[str, Any]) -> Dict[str, Any]:
    target = str(payload.get("target_state", "")).lower()
    if target not in IDEAL:
        raise ValueError("target_state must be phi_plus or phi_minus")
    tolerance = validate_number("tolerance", payload.get("tolerance", 0.15))
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")

    witnesses = payload.get("witnesses")
    if not isinstance(witnesses, dict):
        return {
            "evidence_status": "UNEVALUATED",
            "classification": "RESIDUE",
            "reason": "No phase-sensitive witness dictionary was supplied.",
            "missing_witnesses": list(REQUIRED),
        }

    missing = [name for name in REQUIRED if name not in witnesses]
    if missing:
        return {
            "evidence_status": "PARTIAL",
            "classification": "RESIDUE",
            "reason": "The phase witness set is incomplete.",
            "missing_witnesses": missing,
            "provided_witnesses": sorted(witnesses),
        }

    observed = {name: validate_number(name, witnesses[name]) for name in REQUIRED}
    ideal = IDEAL[target]
    component_errors = {name: abs(observed[name] - ideal[name]) for name in REQUIRED}
    max_error = max(component_errors.values())
    classification = "RECOGNITION" if max_error <= tolerance else "REJECT"
    result: Dict[str, Any] = {
        "certificate_type": "QUANTUM_PHASE_WITNESS_CERTIFICATE",
        "version": "1.0.0",
        "target_state": target,
        "ideal_witnesses": ideal,
        "observed_witnesses": observed,
        "component_errors": component_errors,
        "max_error": max_error,
        "tolerance": tolerance,
        "evidence_status": "EVALUATED",
        "classification": classification,
        "reason": (
            "All declared phase-sensitive correlations agree within tolerance."
            if classification == "RECOGNITION"
            else "At least one phase-sensitive correlation exceeds tolerance."
        ),
        "scientific_scope": "Witness-based phase discrimination; not full state tomography.",
    }
    result["certificate_sha256"] = canonical_hash(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a Bell phase witness")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, default=Path("generated_certificates/quantum_phase_witness_certificate.json"))
    args = parser.parse_args()

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        result = evaluate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 2

    out = args.out
    if not out.is_absolute():
        out = Path.cwd() / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("classification") == "RECOGNITION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
