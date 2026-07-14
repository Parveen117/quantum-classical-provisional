#!/usr/bin/env python3
"""Import strictly attributable physical backend evidence.

The gate follows two already-established repository disciplines:

1. ECL condition typing: evidence must declare the condition under which it was
   produced; undeclared conditions do not silently become native evidence.
2. Cryptographic evidence anchoring: hashes establish integrity, while explicit
   provenance, acquisition identity, and negative controls establish evidentiary
   meaning. Demo/runtime artifacts remain demo/runtime artifacts.

No third-party dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

NON_PHYSICAL_ORIGINS = {
    "synthetic", "simulated", "simulation", "demo", "example", "mock", "test",
    "trial", "jupyter", "jupyter-trial", "notebook", "runtime", "undeclared", "unknown",
}
PHYSICAL_ORIGINS = {
    "physical_backend", "hardware", "hardware_backend", "device_run", "experimental",
    "experiment", "real_backend", "quantum_hardware", "laboratory", "remote_hardware",
    "device_measurement",
}
AMBIGUOUS_BACKENDS = {
    "simulated-or-external", "jupyter-trial", "simulator", "simulation", "unknown",
    "undeclared", "external", "local", "trial", "runtime", "backend", "device", "n/a",
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
    values: list[Any] = []
    for path, value in walk(obj):
        key = path.rsplit(".", 1)[-1].split("[")[0].lower()
        if key in names:
            values.append(value)
    return values


def first_text(obj: Any, names: set[str]) -> str | None:
    for value in values_for(obj, names):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def numeric_values(obj: Any, names: set[str]) -> list[float]:
    values: list[float] = []
    for value in values_for(obj, names):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return values


def normalized_text(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "_")


def origin(obj: Any) -> str:
    value = first_text(obj, {
        "evidence_origin", "origin", "source_type", "data_origin", "acquisition_type",
    })
    return normalized_text(value or "undeclared")


def backend(obj: Any) -> str | None:
    return first_text(obj, {
        "backend", "backend_name", "device", "device_name", "hardware_backend",
        "provider_backend", "processor", "qpu", "machine_name",
    })


def provider(obj: Any) -> str | None:
    return first_text(obj, {"provider", "provider_name", "vendor", "service"})


def acquisition_id(obj: Any) -> str | None:
    return first_text(obj, {
        "job_id", "run_id", "acquisition_id", "experiment_id", "task_id",
        "backend_job_id", "provider_job_id",
    })


def timestamp(obj: Any) -> str | None:
    return first_text(obj, {
        "timestamp", "created_at", "executed_at", "acquired_at", "measurement_time",
        "completed_at",
    })


def classify_source(rec: dict[str, Any]) -> tuple[str, str]:
    origin_value = normalized_text(rec.get("origin"))
    backend_value = normalized_text(rec.get("backend"))

    if origin_value in NON_PHYSICAL_ORIGINS:
        return "rejected", f"non-physical or undeclared origin: {origin_value}"
    if origin_value not in PHYSICAL_ORIGINS:
        return "rejected", f"origin not in physical allowlist: {origin_value}"
    if not backend_value:
        return "rejected", "missing concrete backend identity"
    if backend_value in AMBIGUOUS_BACKENDS or any(
        token in backend_value for token in ("simulat", "trial", "jupyter", "unknown", "external")
    ):
        return "rejected", f"ambiguous or non-hardware backend identity: {rec.get('backend')}"
    if not rec.get("acquisition_id"):
        return "rejected", "missing acquisition/job identifier"
    return "physical_backend", "explicit physical origin, concrete backend, and acquisition identity"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import strict physical quantum evidence")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path, default=Path("imported_real_evidence"))
    parser.add_argument("--pattern", action="append", default=["trial-*.json", "trial-*.jsonl"])
    args = parser.parse_args()

    root = args.root.resolve()
    out = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    files = sorted({path for pattern in args.pattern for path in root.glob(pattern) if path.is_file()})
    report: dict[str, Any] = {
        "contract_version": "2.0.0-ecl-crypto-aligned",
        "physical_origin_allowlist": sorted(PHYSICAL_ORIGINS),
        "scanned": [],
        "physical_backend": [],
        "rejected": [],
    }
    accepted_objects: list[tuple[Path, Any, dict[str, Any]]] = []

    for path in files:
        obj = load(path)
        rec = {
            "file": path.name,
            "sha256": sha256(path),
            "origin": origin(obj),
            "backend": backend(obj),
            "provider": provider(obj),
            "acquisition_id": acquisition_id(obj),
            "timestamp": timestamp(obj),
        }
        category, reason = classify_source(rec)
        rec["reason"] = reason
        report["scanned"].append(rec)
        report[category].append(rec)
        if category == "physical_backend":
            accepted_objects.append((path, obj, rec))

    state_candidates: list[dict[str, Any]] = []
    dynamics_candidates: list[dict[str, Any]] = []
    memory_rows: list[dict[str, Any]] = []

    for path, obj, rec in accepted_objects:
        fidelities = numeric_values(obj, {"fidelity", "state_fidelity", "tomography_fidelity"})
        if fidelities:
            state_candidates.append({**rec, "fidelity": max(fidelities)})

        gaps = numeric_values(obj, {"path_gap", "dynamics_gap", "gate_path_gap"})
        declared = values_for(obj, {"declared_path"})
        executed = values_for(obj, {"executed_path"})
        if gaps or (declared and executed):
            dynamics_candidates.append({
                **rec,
                "path_gap": gaps[0] if gaps else None,
                "declared_path": declared[0] if declared else None,
                "executed_path": executed[0] if executed else None,
            })

        metrics = numeric_values(obj, {
            "distribution_gap", "tv_distance", "total_variation", "stability_gap", "drift",
        })
        for metric in metrics:
            memory_rows.append({
                "value": metric,
                "source_file": rec["file"],
                "source_sha256": rec["sha256"],
                "backend": rec["backend"],
                "provider": rec["provider"],
                "acquisition_id": rec["acquisition_id"],
                "timestamp": rec["timestamp"],
            })

    manifests: dict[str, Any] = {}
    if state_candidates:
        best = max(state_candidates, key=lambda item: item["fidelity"])
        manifests["trial-state-witness-real.json"] = {
            "evidence_origin": "physical_backend",
            "physical_closure_eligible": True,
            "backend": best["backend"],
            "provider": best["provider"],
            "acquisition_id": best["acquisition_id"],
            "timestamp": best["timestamp"],
            "method": "imported_backend_state_witness",
            "fidelity": best["fidelity"],
            "threshold": 0.9,
            "source_file": best["file"],
            "source_sha256": best["sha256"],
        }

    if dynamics_candidates:
        item = dynamics_candidates[0]
        manifests["trial-dynamics-path-real.json"] = {
            "evidence_origin": "physical_backend",
            "physical_closure_eligible": True,
            "backend": item["backend"],
            "provider": item["provider"],
            "acquisition_id": item["acquisition_id"],
            "timestamp": item["timestamp"],
            "declared_path": item["declared_path"],
            "executed_path": item["executed_path"],
            "path_gap": item["path_gap"],
            "tolerance": 0.0,
            "source_file": item["file"],
            "source_sha256": item["sha256"],
        }

    # Like a cryptographic chain, memory evidence needs distinct anchored events,
    # not three numbers copied from one convenient report.
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in memory_rows:
        grouped.setdefault(str(row["backend"]), []).append(row)
    eligible_groups = [
        rows for rows in grouped.values()
        if len({row["acquisition_id"] for row in rows}) >= 3
    ]
    if eligible_groups:
        rows = max(eligible_groups, key=len)
        manifests["trial-memory-drift-real.json"] = {
            "evidence_origin": "physical_backend",
            "physical_closure_eligible": True,
            "backend": rows[0]["backend"],
            "provider": rows[0]["provider"],
            "ordered_metric_values": [row["value"] for row in rows],
            "ordered_acquisition_ids": [row["acquisition_id"] for row in rows],
            "timestamps": [row["timestamp"] for row in rows],
            "drift_threshold": 0.05,
            "source_anchors": rows,
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
    report["integrity_rule"] = (
        "A SHA-256 hash establishes artifact integrity, not physical origin. Promotion requires "
        "an allowlisted physical origin, concrete backend identity, and acquisition/job identifier."
    )
    report["negative_control"] = {
        "undeclared_origin": "must reject",
        "simulated_or_external_backend": "must reject",
        "repeated_values_without_distinct_acquisition_ids": "must not generate memory manifest",
    }
    report["reviewer_note"] = (
        "The importer now borrows ECL's condition typing and cryptography's anchor discipline. "
        "A certificate may prove what a file is; it cannot magically prove where the file came from."
    )
    (out / "import_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({
        "physical_backend": len(report["physical_backend"]),
        "rejected": len(report["rejected"]),
        "manifests": sorted(manifests),
        "contract_version": report["contract_version"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
