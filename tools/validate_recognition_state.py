#!/usr/bin/env python3
"""Deterministic quantum-classical recognition validator.

Uses the existing ECL native-ledger design principles: explicit lawful ledger,
open residue, control classification, and a hash-stable certificate. The first
implementation validates probability distributions using total variation
distance and leaves the remaining residue sectors explicit rather than silently
claiming they were measured.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, Mapping

EPS = 1e-9


def canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Top-level JSON value must be an object")
    return data


def validate_distribution(name: str, distribution: Any, outcomes: list[str]) -> Dict[str, float]:
    if not isinstance(distribution, dict):
        raise ValueError(f"{name} must be an object mapping outcomes to probabilities")
    if set(distribution) != set(outcomes):
        missing = sorted(set(outcomes) - set(distribution))
        extra = sorted(set(distribution) - set(outcomes))
        raise ValueError(f"{name} outcome mismatch; missing={missing}, extra={extra}")
    clean: Dict[str, float] = {}
    for outcome in outcomes:
        value = distribution[outcome]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name}[{outcome!r}] must be numeric")
        value = float(value)
        if not math.isfinite(value) or value < 0.0 or value > 1.0:
            raise ValueError(f"{name}[{outcome!r}] must be finite and within [0, 1]")
        clean[outcome] = value
    total = sum(clean.values())
    if abs(total - 1.0) > EPS:
        raise ValueError(f"{name} must sum to 1; got {total:.12g}")
    return clean


def total_variation(expected: Mapping[str, float], observed: Mapping[str, float]) -> float:
    return 0.5 * sum(abs(observed[key] - expected[key]) for key in expected)


def classify(gap: float, tolerance: float) -> str:
    if gap <= tolerance:
        return "RECOGNITION"
    if gap <= min(1.0, 2.0 * tolerance):
        return "RESIDUE"
    return "REJECT"


def build_certificate(state: Dict[str, Any], source_path: Path) -> Dict[str, Any]:
    required = [
        "state_id", "visible_state", "protocol", "ledger",
        "expected_distribution", "observed_distribution", "metric", "tolerance",
    ]
    missing = [key for key in required if key not in state]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    visible = state["visible_state"]
    if not isinstance(visible, dict) or not isinstance(visible.get("outcomes"), list):
        raise ValueError("visible_state.outcomes must be a list")
    outcomes = visible["outcomes"]
    if not outcomes or any(not isinstance(item, str) or not item for item in outcomes):
        raise ValueError("visible_state.outcomes must contain non-empty strings")
    if len(set(outcomes)) != len(outcomes):
        raise ValueError("visible_state.outcomes must be unique")

    expected = validate_distribution("expected_distribution", state["expected_distribution"], outcomes)
    observed = validate_distribution("observed_distribution", state["observed_distribution"], outcomes)

    metric = state["metric"]
    if metric != "total_variation":
        raise ValueError(f"Unsupported metric: {metric!r}")
    tolerance = state["tolerance"]
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        raise ValueError("tolerance must be numeric")
    tolerance = float(tolerance)
    if not math.isfinite(tolerance) or tolerance < 0.0 or tolerance > 1.0:
        raise ValueError("tolerance must be finite and within [0, 1]")

    gap = total_variation(expected, observed)
    classification = classify(gap, tolerance)
    recognized = classification == "RECOGNITION"

    certificate: Dict[str, Any] = {
        "certificate_type": "QUANTUM_CLASSICAL_RECOGNITION_CERTIFICATE",
        "certificate_version": "1.0.0",
        "state_id": state["state_id"],
        "source_file": str(source_path.as_posix()),
        "model_id": visible.get("model_id"),
        "basis": visible.get("basis"),
        "metric": metric,
        "distribution_gap": gap,
        "tolerance": tolerance,
        "classification": classification,
        "recognized": recognized,
        "residue": {
            "state": 0.0,
            "distribution": gap,
            "dynamics": 0.0,
            "bridge": 0.0,
            "phase": 0.0,
            "frame": 0.0,
            "memory": 0.0
        },
        "scope_note": (
            "Only distribution residue is evaluated in validator v1.0. "
            "Zero values in other sectors mean not evaluated, not physically absent."
        ),
        "protocol": state["protocol"],
        "ledger": state["ledger"],
        "memory": state.get("memory", {}),
        "expected_classification": state.get("expected_classification")
    }
    hash_payload = dict(certificate)
    certificate["certificate_hash"] = canonical_hash(hash_payload)
    return certificate


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a quantum-classical recognition state")
    parser.add_argument("input", type=Path, help="Input state JSON")
    parser.add_argument("--out", type=Path, help="Optional certificate output path")
    parser.add_argument(
        "--require-expected-classification",
        action="store_true",
        help="Fail when the computed classification differs from expected_classification"
    )
    args = parser.parse_args()

    try:
        state = load_json(args.input)
        certificate = build_certificate(state, args.input)
        expected = certificate.get("expected_classification")
        if args.require_expected_classification and expected is not None and expected != certificate["classification"]:
            raise ValueError(
                f"Classification mismatch: expected {expected}, computed {certificate['classification']}"
            )
    except ValueError as exc:
        print(json.dumps({"status": "INVALID_INPUT", "error": str(exc)}, indent=2), file=sys.stderr)
        return 2

    rendered = json.dumps(certificate, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if certificate["recognized"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
