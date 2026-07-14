#!/usr/bin/env python3
r"""Offline replication evaluator for the multi-ledger operator-memory benchmark.

The evaluator never submits IBM Quantum jobs. It verifies completed evidence
bundles, checks declared per-run gates and metric bounds, evaluates stability
across independent jobs, and writes a cryptographically hashed replication
certificate.

Jupyter:
    %run r"C:\Users\abc\Desktop\New Folder (2)\New folder\PROVISNAL RELATED\Quantum classical\evaluate_multi_ledger_replication.py"

Usage:
    python evaluate_multi_ledger_replication.py
    python evaluate_multi_ledger_replication.py --self-test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parent
DEFAULT_RUNS_ROOT = ROOT / "multi_ledger_operator_memory_v1" / "runs"
DEFAULT_OUTPUT_ROOT = ROOT / "multi_ledger_operator_memory_v1" / "replication"

PASS_CLASSIFICATION = "MULTI_LEDGER_OPERATOR_MEMORY_DECOMPOSITION"
REQUIRED_PASS_GATES = (
    "hidden_memory",
    "selective_erase",
    "projection_causal",
    "reset_projection",
    "model_comparison",
    "visible_rk_kr_equality",
)

PER_RUN_LIMITS = {
    "minimum_full_ledger_p1": 0.90,
    "maximum_control_ledger_ceiling": 0.05,
    "minimum_full_readout_p1": 0.90,
    "maximum_projection_erased_readout_p1": 0.05,
    "minimum_reset_signature_spread": 0.03,
    "maximum_visible_rk_kr_tvd": 0.03,
    "maximum_full_multi_ledger_mae": 0.08,
}

CROSS_RUN_LIMITS = {
    "maximum_full_readout_range": 0.08,
    "maximum_projection_erased_readout_range": 0.05,
    "maximum_control_ledger_ceiling_range": 0.05,
    "maximum_visible_rk_kr_tvd": 0.03,
    "minimum_reset_signature_spread": 0.03,
    "maximum_full_multi_ledger_mae": 0.08,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def finite_float(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not numeric: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} is not finite: {number!r}")
    return number


def float_list(value: Any, label: str, expected_length: int | None = None) -> list[float]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{label} must be a list")
    result = [finite_float(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if expected_length is not None and len(result) != expected_length:
        raise ValueError(f"{label} must contain {expected_length} values")
    return result


def validate_manifest(run_dir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return False, ["manifest.json is missing"]

    try:
        manifest = load_json(manifest_path)
    except Exception as exc:
        return False, [f"manifest.json is invalid: {exc}"]

    files = manifest.get("files")
    if not isinstance(files, Mapping) or not files:
        return False, ["manifest files map is missing or empty"]

    for name, expected_hash in files.items():
        if not isinstance(name, str) or not isinstance(expected_hash, str):
            errors.append("manifest file entries must be string-to-string")
            continue
        path = run_dir / name
        if not path.exists() or not path.is_file():
            errors.append(f"manifest file missing: {name}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            errors.append(f"hash mismatch for {name}")

    return not errors, errors


def extract_metrics(certificate: Mapping[str, Any]) -> dict[str, Any]:
    metrics = certificate.get("primary_metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("primary_metrics is missing")

    ledgers = float_list(metrics.get("full_ledger_p1"), "full_ledger_p1", 3)
    reset_values = float_list(metrics.get("reset_readout_values"), "reset_readout_values", 3)

    model_mae = metrics.get("model_mae")
    if not isinstance(model_mae, Mapping):
        raise ValueError("model_mae is missing")
    normalized_model_mae = {
        str(name): finite_float(value, f"model_mae.{name}")
        for name, value in model_mae.items()
    }
    if "full_multi_ledger" not in normalized_model_mae:
        raise ValueError("model_mae.full_multi_ledger is missing")

    return {
        "full_ledger_p1": ledgers,
        "minimum_full_ledger_p1": min(ledgers),
        "control_ledger_ceiling": finite_float(
            metrics.get("control_ledger_ceiling"), "control_ledger_ceiling"
        ),
        "full_readout_p1": finite_float(metrics.get("full_readout_p1"), "full_readout_p1"),
        "projection_erased_readout_p1": finite_float(
            metrics.get("projection_erased_readout_p1"),
            "projection_erased_readout_p1",
        ),
        "reset_readout_values": reset_values,
        "reset_signature_spread": finite_float(
            metrics.get("reset_signature_spread"), "reset_signature_spread"
        ),
        "visible_rk_kr_tvd": finite_float(
            metrics.get("visible_rk_kr_tvd"), "visible_rk_kr_tvd"
        ),
        "model_mae": normalized_model_mae,
        "full_multi_ledger_mae": normalized_model_mae["full_multi_ledger"],
    }


def metric_gate_results(metrics: Mapping[str, Any]) -> dict[str, bool]:
    full_mae = finite_float(metrics["full_multi_ledger_mae"], "full_multi_ledger_mae")
    other_model_errors = [
        finite_float(value, f"model_mae.{name}")
        for name, value in metrics["model_mae"].items()
        if name != "full_multi_ledger"
    ]
    model_dominance = bool(other_model_errors) and full_mae < min(other_model_errors)

    return {
        "full_ledgers_above_floor": (
            finite_float(metrics["minimum_full_ledger_p1"], "minimum_full_ledger_p1")
            >= PER_RUN_LIMITS["minimum_full_ledger_p1"]
        ),
        "control_below_ceiling": (
            finite_float(metrics["control_ledger_ceiling"], "control_ledger_ceiling")
            <= PER_RUN_LIMITS["maximum_control_ledger_ceiling"]
        ),
        "full_readout_above_floor": (
            finite_float(metrics["full_readout_p1"], "full_readout_p1")
            >= PER_RUN_LIMITS["minimum_full_readout_p1"]
        ),
        "projection_erased_below_ceiling": (
            finite_float(
                metrics["projection_erased_readout_p1"],
                "projection_erased_readout_p1",
            )
            <= PER_RUN_LIMITS["maximum_projection_erased_readout_p1"]
        ),
        "reset_signature_resolved": (
            finite_float(metrics["reset_signature_spread"], "reset_signature_spread")
            >= PER_RUN_LIMITS["minimum_reset_signature_spread"]
        ),
        "visible_orders_matched": (
            finite_float(metrics["visible_rk_kr_tvd"], "visible_rk_kr_tvd")
            <= PER_RUN_LIMITS["maximum_visible_rk_kr_tvd"]
        ),
        "full_model_error_below_ceiling": (
            full_mae <= PER_RUN_LIMITS["maximum_full_multi_ledger_mae"]
        ),
        "full_model_outperforms_reduced_models": model_dominance,
    }


def inspect_run(run_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "run_directory": str(run_dir),
        "run_name": run_dir.name,
        "valid": False,
        "errors": [],
    }

    certificate_path = run_dir / "certificate.json"
    if not certificate_path.exists():
        result["errors"].append("certificate.json is missing")
        return result

    manifest_valid, manifest_errors = validate_manifest(run_dir)
    result["manifest_valid"] = manifest_valid
    result["errors"].extend(manifest_errors)

    try:
        certificate = load_json(certificate_path)
        metrics = extract_metrics(certificate)
    except Exception as exc:
        result["errors"].append(f"certificate parsing failed: {exc}")
        return result

    pass_gates = certificate.get("pass_gates")
    if not isinstance(pass_gates, Mapping):
        result["errors"].append("pass_gates is missing")
        pass_gates = {}

    declared_gate_results = {
        gate: bool(pass_gates.get(gate, False))
        for gate in REQUIRED_PASS_GATES
    }
    metric_gates = metric_gate_results(metrics)

    backend = str(certificate.get("backend", "")).strip()
    job_id = str(certificate.get("job_id", "")).strip()
    classification = str(certificate.get("classification", "")).strip()
    raw_results_sha256 = str(certificate.get("raw_results_sha256", "")).strip()

    if not backend:
        result["errors"].append("backend is missing")
    if not job_id:
        result["errors"].append("job_id is missing")
    if not raw_results_sha256:
        result["errors"].append("raw_results_sha256 is missing")

    certificate_class_pass = classification == PASS_CLASSIFICATION
    declared_gates_pass = all(declared_gate_results.values())
    metric_gates_pass = all(metric_gates.values())

    result.update(
        {
            "backend": backend,
            "job_id": job_id,
            "classification": classification,
            "certificate_class_pass": certificate_class_pass,
            "declared_pass_gates": declared_gate_results,
            "declared_gates_pass": declared_gates_pass,
            "metric_gates": metric_gates,
            "metric_gates_pass": metric_gates_pass,
            "metrics": metrics,
            "raw_results_sha256": raw_results_sha256,
            "certificate_sha256": sha256_file(certificate_path),
        }
    )

    result["valid"] = (
        manifest_valid
        and not result["errors"]
        and certificate_class_pass
        and declared_gates_pass
        and metric_gates_pass
    )
    return result


def metric_range(values: Iterable[float]) -> float:
    items = list(values)
    return max(items) - min(items) if items else math.inf


def cross_run_stability(passing_runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not passing_runs:
        return {
            "pass": False,
            "reason": "No passing runs are available.",
            "gates": {},
            "statistics": {},
        }

    full_readout_values = [
        finite_float(run["metrics"]["full_readout_p1"], "full_readout_p1")
        for run in passing_runs
    ]
    projection_erased_values = [
        finite_float(
            run["metrics"]["projection_erased_readout_p1"],
            "projection_erased_readout_p1",
        )
        for run in passing_runs
    ]
    control_values = [
        finite_float(run["metrics"]["control_ledger_ceiling"], "control_ledger_ceiling")
        for run in passing_runs
    ]
    visible_values = [
        finite_float(run["metrics"]["visible_rk_kr_tvd"], "visible_rk_kr_tvd")
        for run in passing_runs
    ]
    reset_spreads = [
        finite_float(run["metrics"]["reset_signature_spread"], "reset_signature_spread")
        for run in passing_runs
    ]
    full_model_errors = [
        finite_float(run["metrics"]["full_multi_ledger_mae"], "full_multi_ledger_mae")
        for run in passing_runs
    ]

    statistics = {
        "full_readout_mean": mean(full_readout_values),
        "full_readout_range": metric_range(full_readout_values),
        "projection_erased_readout_mean": mean(projection_erased_values),
        "projection_erased_readout_range": metric_range(projection_erased_values),
        "control_ledger_ceiling_mean": mean(control_values),
        "control_ledger_ceiling_range": metric_range(control_values),
        "maximum_visible_rk_kr_tvd": max(visible_values),
        "minimum_reset_signature_spread": min(reset_spreads),
        "maximum_full_multi_ledger_mae": max(full_model_errors),
    }

    gates = {
        "full_readout_stable": (
            statistics["full_readout_range"]
            <= CROSS_RUN_LIMITS["maximum_full_readout_range"]
        ),
        "projection_erased_stable": (
            statistics["projection_erased_readout_range"]
            <= CROSS_RUN_LIMITS["maximum_projection_erased_readout_range"]
        ),
        "control_ceiling_stable": (
            statistics["control_ledger_ceiling_range"]
            <= CROSS_RUN_LIMITS["maximum_control_ledger_ceiling_range"]
        ),
        "visible_orders_matched": (
            statistics["maximum_visible_rk_kr_tvd"]
            <= CROSS_RUN_LIMITS["maximum_visible_rk_kr_tvd"]
        ),
        "reset_signature_resolved": (
            statistics["minimum_reset_signature_spread"]
            >= CROSS_RUN_LIMITS["minimum_reset_signature_spread"]
        ),
        "full_model_error_controlled": (
            statistics["maximum_full_multi_ledger_mae"]
            <= CROSS_RUN_LIMITS["maximum_full_multi_ledger_mae"]
        ),
    }
    return {
        "pass": all(gates.values()),
        "gates": gates,
        "statistics": statistics,
    }


def classify(
    inspected_runs: Sequence[Mapping[str, Any]],
    duplicate_job_ids: Sequence[str],
    duplicate_result_hashes: Sequence[str],
    stability: Mapping[str, Any],
) -> str:
    total = len(inspected_runs)
    passing = [run for run in inspected_runs if bool(run.get("valid"))]
    passing_backends = {str(run.get("backend")) for run in passing if run.get("backend")}

    if duplicate_job_ids or duplicate_result_hashes:
        return "EVIDENCE_DUPLICATION_DETECTED"
    if total == 0:
        return "NO_HARDWARE_EVIDENCE"
    if not passing:
        return "NO_REPRODUCIBLE_MULTI_LEDGER_MEMORY"
    if len(passing) != total:
        return "MIXED_REPLICATION_RESULT"
    if len(passing) == 1:
        return "SINGLE_HARDWARE_RUN_ONLY"
    if not bool(stability.get("pass")):
        return "REPLICATION_UNSTABLE"
    if len(passing_backends) >= 2:
        return "CROSS_BACKEND_REPLICATION"
    return "SAME_BACKEND_REPLICATION"


def find_duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if not value:
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def evaluate(runs_root: Path) -> dict[str, Any]:
    run_dirs = sorted(
        path for path in runs_root.iterdir()
        if path.is_dir() and (path / "certificate.json").exists()
    ) if runs_root.exists() else []

    inspected = [inspect_run(path) for path in run_dirs]
    duplicate_job_ids = find_duplicates(
        str(run.get("job_id", "")) for run in inspected
    )
    duplicate_result_hashes = find_duplicates(
        str(run.get("raw_results_sha256", "")) for run in inspected
    )
    passing = [run for run in inspected if bool(run.get("valid"))]
    stability = cross_run_stability(passing)
    classification = classify(
        inspected,
        duplicate_job_ids,
        duplicate_result_hashes,
        stability,
    )

    return {
        "schema": "MULTI_LEDGER_OPERATOR_MEMORY_REPLICATION_CERTIFICATE_V1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runs_root": str(runs_root),
        "classification": classification,
        "run_count": len(inspected),
        "passing_run_count": len(passing),
        "backend_count": len(
            {str(run.get("backend")) for run in passing if run.get("backend")}
        ),
        "backends": sorted(
            {str(run.get("backend")) for run in passing if run.get("backend")}
        ),
        "job_ids": [
            str(run.get("job_id")) for run in inspected if run.get("job_id")
        ],
        "duplicate_job_ids": duplicate_job_ids,
        "duplicate_result_hashes": duplicate_result_hashes,
        "per_run_limits": PER_RUN_LIMITS,
        "cross_run_limits": CROSS_RUN_LIMITS,
        "cross_run_stability": stability,
        "runs": inspected,
        "scientific_boundary": (
            "This certificate evaluates replication of a declared quantum "
            "operator-order memory representation. It does not establish a "
            "fabricated device, a material memory mechanism, quantum advantage, "
            "thermodynamic entropy production, or a new physical law."
        ),
    }


def write_outputs(certificate: Mapping[str, Any], output_root: Path) -> Path:
    out = output_root / utc_stamp()
    out.mkdir(parents=True, exist_ok=False)

    cert_path = out / "replication_certificate.json"
    cert_path.write_text(
        json.dumps(certificate, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    stability = certificate["cross_run_stability"]
    lines = [
        "# Multi-Ledger Operator-Memory Replication",
        "",
        f"- Classification: `{certificate['classification']}`",
        f"- Run count: `{certificate['run_count']}`",
        f"- Passing run count: `{certificate['passing_run_count']}`",
        f"- Backend count: `{certificate['backend_count']}`",
        f"- Backends: `{', '.join(certificate['backends']) or 'none'}`",
        f"- Cross-run stability: `{stability.get('pass', False)}`",
        "",
        "## Runs",
        "",
    ]
    for run in certificate["runs"]:
        lines.extend(
            [
                f"- `{run.get('run_name', 'unknown')}`",
                f"  - backend: `{run.get('backend', 'unknown')}`",
                f"  - job: `{run.get('job_id', 'unknown')}`",
                f"  - valid: `{run.get('valid', False)}`",
                f"  - classification: `{run.get('classification', 'unknown')}`",
            ]
        )
        if run.get("errors"):
            lines.append(f"  - errors: `{'; '.join(run['errors'])}`")

    lines.extend(
        [
            "",
            "This is replication evidence for a quantum representation benchmark, "
            "not physical device validation.",
        ]
    )
    summary_path = out / "replication_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    manifest = {
        "schema": "MULTI_LEDGER_OPERATOR_MEMORY_REPLICATION_MANIFEST_V1",
        "files": {
            cert_path.name: sha256_file(cert_path),
            summary_path.name: sha256_file(summary_path),
        },
    }
    manifest_path = out / "replication_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return out


def make_fixture(
    root: Path,
    *,
    name: str,
    backend: str,
    job_id: str,
    valid: bool = True,
    result_marker: str = "",
) -> Path:
    run = root / name
    run.mkdir(parents=True)

    certificate = {
        "schema": "MULTI_LEDGER_OPERATOR_MEMORY_CERTIFICATE_V1",
        "backend": backend,
        "job_id": job_id,
        "classification": (
            PASS_CLASSIFICATION if valid else "NO_REPRODUCIBLE_MULTI_LEDGER_MEMORY"
        ),
        "pass_gates": {
            gate: valid for gate in REQUIRED_PASS_GATES
        },
        "primary_metrics": {
            "full_ledger_p1": [0.98, 0.97, 0.99] if valid else [0.60, 0.61, 0.62],
            "control_ledger_ceiling": 0.01 if valid else 0.10,
            "full_readout_p1": 0.975 if valid else 0.70,
            "projection_erased_readout_p1": 0.002 if valid else 0.20,
            "reset_readout_values": [0.78, 0.73, 0.69],
            "reset_signature_spread": 0.09 if valid else 0.01,
            "visible_rk_kr_tvd": 0.006 if valid else 0.08,
            "model_mae": {
                "full_multi_ledger": 0.03 if valid else 0.20,
                "no_memory": 0.42,
                "single_m1": 0.34,
                "pair_m23": 0.15,
            },
        },
    }

    results_path = run / "results.json"
    results_path.write_text(
        json.dumps({"marker": result_marker or job_id}, sort_keys=True),
        encoding="utf-8",
    )
    certificate["raw_results_sha256"] = sha256_file(results_path)

    cert_path = run / "certificate.json"
    cert_path.write_text(
        json.dumps(certificate, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    summary_path = run / "summary.md"
    summary_path.write_text("# fixture\n", encoding="utf-8")
    manifest = {
        "files": {
            results_path.name: sha256_file(results_path),
            cert_path.name: sha256_file(cert_path),
            summary_path.name: sha256_file(summary_path),
        }
    }
    (run / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return run


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        single = root / "single"
        make_fixture(single, name="run1", backend="backend_a", job_id="job1")
        assert evaluate(single)["classification"] == "SINGLE_HARDWARE_RUN_ONLY"

        same = root / "same"
        make_fixture(same, name="run1", backend="backend_a", job_id="job1")
        make_fixture(same, name="run2", backend="backend_a", job_id="job2")
        assert evaluate(same)["classification"] == "SAME_BACKEND_REPLICATION"

        cross = root / "cross"
        make_fixture(cross, name="run1", backend="backend_a", job_id="job1")
        make_fixture(cross, name="run2", backend="backend_b", job_id="job2")
        assert evaluate(cross)["classification"] == "CROSS_BACKEND_REPLICATION"

        mixed = root / "mixed"
        make_fixture(mixed, name="run1", backend="backend_a", job_id="job1")
        make_fixture(
            mixed,
            name="run2",
            backend="backend_b",
            job_id="job2",
            valid=False,
        )
        assert evaluate(mixed)["classification"] == "MIXED_REPLICATION_RESULT"

        duplicate = root / "duplicate"
        make_fixture(
            duplicate,
            name="run1",
            backend="backend_a",
            job_id="job1",
            result_marker="same",
        )
        make_fixture(
            duplicate,
            name="run2",
            backend="backend_b",
            job_id="job1",
            result_marker="same",
        )
        duplicate_result = evaluate(duplicate)
        assert duplicate_result["classification"] == "EVIDENCE_DUPLICATION_DETECTED"

    print(
        "Self-test passed: single-run, same-backend, cross-backend, mixed, "
        "and duplicate-evidence classifications are enforced."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=DEFAULT_RUNS_ROOT,
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    args = parser.parse_args(argv)

    if args.self_test:
        self_test()
        return 0

    certificate = evaluate(args.runs_root)
    out = write_outputs(certificate, args.output_root)
    print(json.dumps(certificate, indent=2, sort_keys=True))
    print(f"\nReplication evidence written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
