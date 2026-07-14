#!/usr/bin/env python3
"""Build one reviewer-facing certificate from existing quantum evidence files.

The builder intentionally reuses existing Bell, calibration, backend, stability,
ledger, and bundle artifacts. It records source hashes, extracts declared metrics,
and refuses to label missing sectors as zero.

No third-party dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

DEFAULT_PATTERNS = [
    "trial-bell-evaluation.json",
    "trial-bell-stability-report.json",
    "trial-calibration-report.json",
    "trial-backend-comparison-report.json",
    "trial-expected-integrated-ledger.jsonl",
    "trial-integrated-quantum-evidence-bundle.json",
    "trial-quantum-certificate.json",
    "trial-quantum-evidence-bundle.json",
    "trial-quantum-ledger.jsonl",
]

NUMERIC_KEYS = {
    "distribution_gap", "calibration_gap", "stability_gap", "backend_gap",
    "total_variation", "tv_distance", "residue", "gap", "tolerance",
    "threshold", "drift", "fidelity", "confidence", "score",
}
STATUS_KEYS = {
    "classification", "recognized", "status", "decision", "action",
    "native_advantage", "passed", "valid",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_hash(obj: Any) -> str:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(data)


def read_artifact(path: Path) -> Tuple[Any, str]:
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    if path.suffix.lower() == ".jsonl":
        rows = []
        for number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: invalid JSONL at line {number}: {exc}") from exc
        return rows, digest
    try:
        return json.loads(raw.decode("utf-8")), digest
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc


def walk(obj: Any, prefix: str = "") -> Iterable[Tuple[str, Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            yield child, value
            yield from walk(value, child)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            child = f"{prefix}[{index}]"
            yield child, value
            yield from walk(value, child)


def extract_signals(obj: Any) -> Dict[str, Any]:
    numeric: Dict[str, float] = {}
    statuses: Dict[str, Any] = {}
    for path, value in walk(obj):
        key = path.rsplit(".", 1)[-1].split("[")[0].lower()
        if key in NUMERIC_KEYS and isinstance(value, (int, float)) and not isinstance(value, bool):
            value_f = float(value)
            if math.isfinite(value_f):
                numeric[path] = value_f
        elif key in STATUS_KEYS and isinstance(value, (str, bool, int, float)):
            statuses[path] = value
    return {"numeric": numeric, "statuses": statuses}


def infer_sector(name: str) -> str:
    lower = name.lower()
    if "bell" in lower or "distribution" in lower:
        return "distribution"
    if "calibration" in lower:
        return "frame"
    if "backend" in lower or "bridge" in lower:
        return "bridge"
    if "stability" in lower or "drift" in lower:
        return "memory"
    if "ledger" in lower:
        return "constitutive"
    if "certificate" in lower or "bundle" in lower:
        return "provenance"
    return "unclassified"


def find_inputs(root: Path, explicit: List[str]) -> List[Path]:
    names = explicit or DEFAULT_PATTERNS
    found: List[Path] = []
    for name in names:
        candidate = (root / name).resolve()
        if candidate.exists() and candidate.is_file():
            found.append(candidate)
    return found


def classify_overall(records: List[Dict[str, Any]]) -> str:
    text = " ".join(
        str(value).upper()
        for record in records
        for value in record["signals"]["statuses"].values()
    )
    if any(token in text for token in ("REJECT", "FAIL", "INVALID")):
        return "REJECT"
    if any(token in text for token in ("RESIDUE", "MONITOR", "REVIEW", "CORRECT")):
        return "RESIDUE"
    if records and any(token in text for token in ("RECOGNITION", "PASS", "VALID", "TRUE")):
        return "RECOGNITION"
    return "UNDETERMINED"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build unified quantum recognition certificate")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--input", action="append", default=[], help="Evidence filename relative to root; repeatable")
    parser.add_argument("--out", type=Path, default=Path("generated_certificates/unified_quantum_certificate.json"))
    parser.add_argument("--require-all-defaults", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    inputs = find_inputs(root, args.input)
    expected_names = args.input or DEFAULT_PATTERNS
    missing = [name for name in expected_names if not (root / name).exists()]

    if args.require_all_defaults and missing:
        print(json.dumps({"error": "missing evidence files", "missing": missing}, indent=2))
        return 2
    if not inputs:
        print(json.dumps({"error": "no evidence files found", "searched": expected_names}, indent=2))
        return 2

    records: List[Dict[str, Any]] = []
    for path in sorted(inputs, key=lambda p: p.name.lower()):
        obj, source_hash = read_artifact(path)
        records.append({
            "filename": path.name,
            "relative_path": str(path.relative_to(root)),
            "sector": infer_sector(path.name),
            "source_sha256": source_hash,
            "record_count": len(obj) if isinstance(obj, list) else 1,
            "signals": extract_signals(obj),
        })

    sectors = {
        sector: {
            "evaluated": any(r["sector"] == sector for r in records),
            "sources": [r["filename"] for r in records if r["sector"] == sector],
        }
        for sector in ["state", "distribution", "dynamics", "bridge", "phase", "frame", "memory", "constitutive", "provenance"]
    }

    certificate: Dict[str, Any] = {
        "certificate_type": "UNIFIED_QUANTUM_RECOGNITION_CERTIFICATE",
        "version": "1.0.0",
        "scientific_scope": "Computational evidence aggregation; not a universal physical proof.",
        "repository_projection": "quantum-classical",
        "source_count": len(records),
        "missing_optional_sources": missing,
        "sources": records,
        "residue_sectors": sectors,
        "overall_classification": classify_overall(records),
        "decision_rule": {
            "REJECT": "Any source explicitly reports reject, fail, or invalid.",
            "RESIDUE": "No rejection, but at least one source requests monitoring, review, or correction.",
            "RECOGNITION": "At least one affirmative result and no rejection/residue status.",
            "UNDETERMINED": "Evidence lacks an explicit reusable decision field.",
        },
        "limitations": [
            "The builder preserves source claims; it does not independently verify experimental hardware.",
            "Missing sectors are marked unevaluated, never silently set to zero.",
            "Overall classification is subordinate to source-specific metrics and tolerances.",
        ],
    }
    certificate["certificate_sha256"] = canonical_hash(certificate)

    out = args.out if args.out.is_absolute() else root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(certificate, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({
        "output": str(out),
        "certificate_sha256": certificate["certificate_sha256"],
        "source_count": len(records),
        "overall_classification": certificate["overall_classification"],
        "missing_optional_sources": missing,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
