#!/usr/bin/env python3
"""Import explicitly physical backend evidence into state, dynamics, and memory manifests.

The importer scans JSON/JSONL artifacts, records source hashes, and separates three
classes:

1. physical_backend: eligible for physical-closure manifests;
2. provenance_only: useful runtime provenance, but not physical evidence;
3. rejected: synthetic, simulated, undeclared, ambiguous, or missing identity.

No third-party dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

SYNTHETIC_TOKENS = {
    "synthetic", "simulated", "simulation", "demo", "example", "mock", "test",
    "jupyter-trial", "simulated-or-external", "undeclared", "unknown",
}
PHYSICAL_ORIGINS = {
    "physical_backend", "hardware", "hardware_backend", "device_run",
    "experimental", "experiment", "real_backend", "quantum_hardware",
}
AMBIGUOUS_BACKENDS = {
    "simulated-or-external", "jupyter-trial", "simulator", "simulation",
    "unknown", "undeclared", "external", "local", "trial",
}


def walk(obj: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield path, value
            yield from walk(value, path)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            path = f"{prefix}[{index}]"
            yield path, value
            yield from walk(value, path)


def load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def values_for(obj: Any, names: set[str]) -> list[Any]:
    out: list[Any] = []
    for path, value in walk(obj):
        key = path.rsplit(".", 1)[-1].split("[")[0].lower()
        if key in names:
            out.append(value)
    return out


def first_text(obj: Any, names: set[str]) -> str | None:
    for value in values_for(obj, names):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def numeric_values(obj: Any, names: set[str]) -> list[float]:
    vals: list[float] = []
    for value in values_for(obj, names):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            vals.append(float(value))
    return vals


def origin(obj: Any) -> str:
    value = first_text(obj, {"evidence_origin", "origin", "source_type", "data_origin"})
    return (value or "undeclared").strip().lower()


def backend(obj: Any) -> str | None:
    value = first_text(
        obj,
        {"backend", "backend_name", "device", "device_name", "hardware_backend", "provider_backend"},
    )
    return value.strip() if value else None


def normalized(value: str | None) -> str:
    return (value or "").strip().lower()


def classify_source(rec: dict[str, Any]) -> tuple[str, str]:
    origin_value = normalized(rec.get("origin"))
    backend_value = normalized(rec.get("backend"))

    if any(token in origin_value for token in SYNTHETIC_TOKENS):
        return "rejected", "synthetic, simulated, trial, or undeclared origin"
    if not backend_value:
        return "rejected", "missing backend identity"
    if backend_value in AMBIGUOUS_BACKENDS or any(token in backend_value for token in SYNTHETIC_TOKENS):
        return "rejected", "ambiguous or non-physical backend identity"
    if origin_value not in PHYSICAL_ORIGINS:
        return "provenance_only", "backend-linked provenance without explicit physical evidence origin"
    return "physical_backend", "explicit physical backend evidence"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path, default=Path("imported_real_evidence"))
    parser.add_argument("--pattern", action="append", default=["trial-*.json", "trial-*.jsonl"])
    args = parser.parse_args()

    root = args.root.resolve()
    out = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    files = sorted({p for pattern in args.pattern for p in root.glob(pattern) if p.is_file()})
    report: dict[str, Any] = {
        "scanned": [],
        "physical_backend": [],
        "provenance_only": [],
        "rejected": [],
    }
    state_candidates: list[dict[str, Any]] = []
    dynamics_candidates: list[dict[str, Any]] = []
    memory_rows: list[dict[str, Any]] = []

    for path in files:
        obj = load(path)
        rec = {
            "file": path.name,
            "sha256": sha256(path),
            "origin": origin(obj),
            "backend": backend(obj),
        }
        category, reason = classify_source(rec)
        rec["reason"] = reason
        report["scanned"].append(rec)
        report[category].append(rec)

        if category != "physical_backend":
            continue

        fidelities = numeric_values(obj, {"fidelity", "state_fidelity", "tomography_fidelity"})
        if fidelities:
            state_candidates.append({**rec, "fidelity": max(fidelities)})

        gaps = numeric_values(obj, {"path_gap", "dynamics_gap", "gate_path_gap"})
        declared = values_for(obj, {"declared_path"})
        executed = values_for(obj, {"executed_path"})
        if gaps or (declared and executed):
            dynamics_candidates.append(
                {
                    **rec,
                    "path_gap": gaps[0] if gaps else None,
                    "declared_path": declared[0] if declared else None,
                    "executed_path": executed[0] if executed else None,
                }
            )

        metrics = numeric_values(
            obj,
            {"distribution_gap", "tv_distance", "total_variation", "stability_gap", "drift"},
        )
        for metric in metrics:
            memory_rows.append({"value": metric, "source_file": rec["file"], "source_sha256": rec["sha256"]})

    manifests: dict[str, Any] = {}
    if state_candidates:
        best = max(state_candidates, key=lambda item: item["fidelity"])
        manifests["trial-state-witness-real.json"] = {
            "evidence_origin": "physical_backend",
            "backend": best["backend"],
            "method": "imported_backend_state_witness",
            "fidelity": best["fidelity"],
            "threshold": 0.9,
            "source_file": best["file"],
            "source_sha256": best["sha256"],
        }

    if dynamics_candidates:
        candidate = dynamics_candidates[0]
        manifests["trial-dynamics-path-real.json"] = {
            "evidence_origin": "physical_backend",
            "backend": candidate["backend"],
            "declared_path": candidate["declared_path"],
            "executed_path": candidate["executed_path"],
            "path_gap": candidate["path_gap"],
            "tolerance": 0.0,
            "source_file": candidate["file"],
            "source_sha256": candidate["sha256"],
        }

    if len(memory_rows) >= 3:
        manifests["trial-memory-drift-real.json"] = {
            "evidence_origin": "physical_backend",
            "ordered_metric_values": [row["value"] for row in memory_rows],
            "drift_threshold": 0.05,
            "source_rows": memory_rows,
        }

    for old_name in (
        "trial-state-witness-real.json",
        "trial-dynamics-path-real.json",
        "trial-memory-drift-real.json",
    ):
        old_path = out / old_name
        if old_path.exists() and old_name not in manifests:
            old_path.unlink()

    for name, data in manifests.items():
        (out / name).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    report["manifests"] = sorted(manifests)
    report["reviewer_note"] = (
        "Only explicitly physical origins with non-ambiguous backend identities can generate physical-closure manifests. "
        "Provenance is retained, but provenance is not promoted into experiment by optimism."
    )
    (out / "import_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(
        json.dumps(
            {
                "physical_backend": len(report["physical_backend"]),
                "provenance_only": len(report["provenance_only"]),
                "rejected": len(report["rejected"]),
                "manifests": sorted(manifests),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
