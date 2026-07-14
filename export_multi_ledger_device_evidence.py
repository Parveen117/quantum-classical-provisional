#!/usr/bin/env python3
r"""Freeze replicated multi-ledger quantum evidence and copy it into a device repository.

This tool never submits IBM jobs and never edits source evidence files. It validates
an existing CROSS_BACKEND_REPLICATION certificate, copies every manifest-declared
run and replication file into an immutable export bundle, hashes the bundle, and
optionally copies it into the device repository with post-copy verification.

Jupyter:
    %run r"C:\Users\abc\Desktop\New Folder (2)\New folder\PROVISNAL RELATED\Quantum classical\export_multi_ledger_device_evidence.py" --device-repo r"C:\Users\abc\Desktop\New Folder (2)\New folder\PROVISNAL RELATED\Devices"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parent
DEFAULT_RUNS_ROOT = ROOT / "multi_ledger_operator_memory_v1" / "runs"
DEFAULT_REPLICATION_ROOT = ROOT / "multi_ledger_operator_memory_v1" / "replication"
DEFAULT_EXPORT_ROOT = ROOT / "device_evidence_exports" / "multi_ledger_operator_memory"
EXPECTED_REPLICATION_CLASS = "CROSS_BACKEND_REPLICATION"
EXPECTED_RUN_CLASS = "MULTI_LEDGER_OPERATOR_MEMORY_DECOMPOSITION"
DEVICE_STATUS = "REPLICATED_DEVICE_RELEVANT_QUANTUM_WITNESS"
PHYSICAL_STATUS = "PHYSICAL_DEVICE_NOT_VALIDATED"
REQUIRED_PASS_GATES = (
    "hidden_memory",
    "selective_erase",
    "projection_causal",
    "reset_projection",
    "model_comparison",
    "visible_rk_kr_equality",
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def latest_manifest_directory(root: Path, manifest_name: str) -> Path:
    candidates = sorted(
        path for path in root.iterdir()
        if path.is_dir() and (path / manifest_name).is_file()
    ) if root.exists() else []
    if not candidates:
        raise FileNotFoundError(f"No {manifest_name} found under {root}")
    return candidates[-1]


def manifest_files(directory: Path, manifest_name: str) -> dict[str, str]:
    manifest_path = directory / manifest_name
    manifest = load_json(manifest_path)
    files = manifest.get("files")
    if not isinstance(files, Mapping) or not files:
        raise ValueError(f"{manifest_path} has no files map")

    normalized: dict[str, str] = {}
    for name, expected_hash in files.items():
        if not isinstance(name, str) or not isinstance(expected_hash, str):
            raise ValueError(f"Invalid manifest entry in {manifest_path}")
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe manifest path: {name}")
        path = directory / relative
        if not path.is_file():
            raise FileNotFoundError(f"Manifest file is missing: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise ValueError(f"Hash mismatch for {path}")
        normalized[name] = expected_hash
    return normalized


def verify_git_frozen(repo_root: Path, paths: Sequence[Path]) -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("The quantum repository is not available as a Git checkout") from exc

    relative_paths = [str(path.resolve().relative_to(repo_root.resolve())) for path in paths]
    for relative in relative_paths:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=repo_root,
            text=True,
            capture_output=True,
        )
        if tracked.returncode != 0:
            raise RuntimeError(
                f"Evidence is not committed: {relative}. Commit and push the evidence before export."
            )

    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", *relative_paths],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    if dirty:
        raise RuntimeError(
            "Evidence files differ from the committed source. Commit them before export:\n" + dirty
        )
    return commit


def validate_replication(replication_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    files = manifest_files(replication_dir, "replication_manifest.json")
    certificate = load_json(replication_dir / "replication_certificate.json")

    if certificate.get("classification") != EXPECTED_REPLICATION_CLASS:
        raise ValueError(
            f"Replication classification must be {EXPECTED_REPLICATION_CLASS}, "
            f"got {certificate.get('classification')}"
        )
    if int(certificate.get("passing_run_count", 0)) < 2:
        raise ValueError("At least two passing hardware runs are required")
    if int(certificate.get("backend_count", 0)) < 2:
        raise ValueError("At least two distinct backends are required")
    stability = certificate.get("cross_run_stability")
    if not isinstance(stability, Mapping) or not bool(stability.get("pass")):
        raise ValueError("Cross-run stability did not pass")
    if certificate.get("duplicate_job_ids") or certificate.get("duplicate_result_hashes"):
        raise ValueError("Duplicate evidence is present in the replication certificate")
    runs = certificate.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("Replication certificate contains no runs")
    return certificate, files


def validate_run(run_dir: Path, expected: Mapping[str, Any]) -> dict[str, str]:
    files = manifest_files(run_dir, "manifest.json")
    certificate = load_json(run_dir / "certificate.json")

    for field in ("backend", "job_id", "classification"):
        expected_value = str(expected.get(field, ""))
        actual_value = str(certificate.get(field, ""))
        if expected_value != actual_value:
            raise ValueError(
                f"Run {run_dir.name} {field} mismatch: {actual_value!r} != {expected_value!r}"
            )
    if certificate.get("classification") != EXPECTED_RUN_CLASS:
        raise ValueError(f"Run {run_dir.name} is not a passing multi-ledger benchmark")
    gates = certificate.get("pass_gates")
    if not isinstance(gates, Mapping) or not all(bool(gates.get(gate)) for gate in REQUIRED_PASS_GATES):
        raise ValueError(f"Run {run_dir.name} does not pass all declared gates")
    if not bool(expected.get("valid")):
        raise ValueError(f"Replication evaluator did not mark {run_dir.name} valid")

    results_path = run_dir / "results.json"
    declared_raw_hash = str(certificate.get("raw_results_sha256", ""))
    if not declared_raw_hash or sha256_file(results_path) != declared_raw_hash:
        raise ValueError(f"Raw-results hash mismatch in {run_dir.name}")
    return files


def copy_declared_files(
    source_dir: Path,
    destination_dir: Path,
    declared_files: Mapping[str, str],
    manifest_name: str,
) -> list[Path]:
    copied: list[Path] = []
    destination_dir.mkdir(parents=True, exist_ok=False)
    for name in sorted(declared_files):
        source = source_dir / name
        destination = destination_dir / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    shutil.copy2(source_dir / manifest_name, destination_dir / manifest_name)
    copied.append(destination_dir / manifest_name)
    return copied


def write_summary(certificate: Mapping[str, Any], path: Path) -> None:
    backends = ", ".join(str(item) for item in certificate.get("backends", []))
    jobs = ", ".join(str(item) for item in certificate.get("job_ids", []))
    lines = [
        "# Replicated Device-Relevant Quantum Witness",
        "",
        f"- Evidence status: `{DEVICE_STATUS}`",
        f"- Replication classification: `{EXPECTED_REPLICATION_CLASS}`",
        f"- Passing runs: `{certificate.get('passing_run_count')}`",
        f"- Backends: `{backends}`",
        f"- IBM jobs: `{jobs}`",
        f"- Physical device status: `{PHYSICAL_STATUS}`",
        "",
        "## Supported architecture concepts",
        "",
        "- three separately resolved operator-order memory ledgers;",
        "- selective erasure of individual memory channels;",
        "- causal memory-to-readout projection;",
        "- distinguishable reset signatures;",
        "- stable full-model reconstruction across independent IBM backends;",
        "- matched visible RK/KR outputs with hidden operator-order memory.",
        "",
        "## Scientific boundary",
        "",
        "This bundle is cross-backend replication evidence for a quantum representation "
        "of decomposable operator-order memory. It is not physical transistor, material, "
        "breadboard, thermodynamic, quantum-advantage, or new-law validation.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_transfer_bundle(bundle: Path) -> dict[str, Any]:
    manifest_path = bundle / "transfer_manifest.json"
    manifest = load_json(manifest_path)
    files = manifest.get("files")
    if not isinstance(files, Mapping) or not files:
        raise ValueError("Transfer manifest contains no files")
    for name, expected_hash in files.items():
        path = bundle / str(name)
        if not path.is_file():
            raise FileNotFoundError(f"Transferred file is missing: {path}")
        if sha256_file(path) != str(expected_hash):
            raise ValueError(f"Transferred file hash mismatch: {path}")
    return manifest


def create_export(
    runs_root: Path,
    replication_dir: Path,
    export_root: Path,
    *,
    require_git_frozen: bool = True,
) -> Path:
    replication_certificate, replication_files = validate_replication(replication_dir)
    runs = replication_certificate["runs"]

    run_records: list[tuple[Mapping[str, Any], Path, dict[str, str]]] = []
    source_files: list[Path] = []
    for run in runs:
        if not isinstance(run, Mapping):
            raise ValueError("Invalid run record in replication certificate")
        run_name = str(run.get("run_name", ""))
        if not run_name or Path(run_name).name != run_name:
            raise ValueError(f"Unsafe run name: {run_name!r}")
        run_dir = runs_root / run_name
        files = validate_run(run_dir, run)
        run_records.append((run, run_dir, files))
        source_files.extend(run_dir / name for name in files)
        source_files.append(run_dir / "manifest.json")

    source_files.extend(replication_dir / name for name in replication_files)
    source_files.append(replication_dir / "replication_manifest.json")
    source_commit = (
        verify_git_frozen(ROOT, source_files)
        if require_git_frozen
        else "SELF_TEST_UNCOMMITTED_FIXTURE"
    )

    stamp = utc_stamp()
    destination = export_root / stamp
    destination.mkdir(parents=True, exist_ok=False)

    payload_files: list[Path] = []
    for run, run_dir, files in run_records:
        run_destination = destination / "runs" / str(run["run_name"])
        payload_files.extend(
            copy_declared_files(run_dir, run_destination, files, "manifest.json")
        )

    replication_destination = destination / "replication" / replication_dir.name
    payload_files.extend(
        copy_declared_files(
            replication_dir,
            replication_destination,
            replication_files,
            "replication_manifest.json",
        )
    )

    summary_path = destination / "DEVICE_RELEVANT_QUANTUM_WITNESS.md"
    write_summary(replication_certificate, summary_path)
    payload_files.append(summary_path)

    transfer_certificate = {
        "schema": "MULTI_LEDGER_DEVICE_EVIDENCE_TRANSFER_CERTIFICATE_V1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_repository": "Parveen117/quantum-classical-provisional",
        "source_commit": source_commit,
        "source_replication_directory": replication_dir.name,
        "replication_classification": EXPECTED_REPLICATION_CLASS,
        "device_evidence_status": DEVICE_STATUS,
        "physical_device_status": PHYSICAL_STATUS,
        "run_count": replication_certificate.get("run_count"),
        "passing_run_count": replication_certificate.get("passing_run_count"),
        "backend_count": replication_certificate.get("backend_count"),
        "backends": replication_certificate.get("backends"),
        "job_ids": replication_certificate.get("job_ids"),
        "cross_run_stability": replication_certificate.get("cross_run_stability"),
        "scientific_boundary": (
            "Cross-backend replication of a declared quantum operator-order memory "
            "representation; not physical device or material validation."
        ),
    }
    transfer_certificate_path = destination / "transfer_certificate.json"
    transfer_certificate_path.write_text(
        json.dumps(transfer_certificate, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    payload_files.append(transfer_certificate_path)

    transfer_manifest = {
        "schema": "MULTI_LEDGER_DEVICE_EVIDENCE_TRANSFER_MANIFEST_V1",
        "files": {
            str(path.relative_to(destination)).replace(os.sep, "/"): sha256_file(path)
            for path in sorted(payload_files)
        },
    }
    (destination / "transfer_manifest.json").write_text(
        json.dumps(transfer_manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    verify_transfer_bundle(destination)
    return destination


def copy_to_device(export_dir: Path, device_repo: Path) -> Path:
    if not device_repo.is_dir():
        raise FileNotFoundError(f"Device repository does not exist: {device_repo}")
    certificate = load_json(export_dir / "transfer_certificate.json")
    created = str(certificate.get("created_at_utc", ""))
    try:
        date_part = datetime.fromisoformat(created).date().isoformat()
    except ValueError:
        date_part = datetime.now(timezone.utc).date().isoformat()
    destination = (
        device_repo
        / "quantum_hardware_evidence"
        / date_part
        / f"multi_ledger_cross_backend_{export_dir.name}"
    )
    if destination.exists():
        raise FileExistsError(f"Device evidence destination already exists: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".partial")
    if temporary.exists():
        shutil.rmtree(temporary)
    shutil.copytree(export_dir, temporary)
    verify_transfer_bundle(temporary)
    os.replace(temporary, destination)

    receipt = {
        "schema": "MULTI_LEDGER_DEVICE_EVIDENCE_COPY_RECEIPT_V1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "COPIED_AND_HASH_VERIFIED",
        "source_export": str(export_dir),
        "destination": str(destination),
        "transfer_manifest_sha256": sha256_file(destination / "transfer_manifest.json"),
    }
    (destination / "device_copy_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return destination


def make_fixture(root: Path) -> tuple[Path, Path]:
    runs_root = root / "runs"
    replication_root = root / "replication"
    run_records = []
    for index, backend in enumerate(("backend_a", "backend_b"), start=1):
        run_name = f"run{index}"
        run_dir = runs_root / run_name
        run_dir.mkdir(parents=True)
        results_path = run_dir / "results.json"
        results_path.write_text(json.dumps({"run": index}), encoding="utf-8")
        certificate = {
            "backend": backend,
            "job_id": f"job{index}",
            "classification": EXPECTED_RUN_CLASS,
            "raw_results_sha256": sha256_file(results_path),
            "pass_gates": {gate: True for gate in REQUIRED_PASS_GATES},
        }
        cert_path = run_dir / "certificate.json"
        cert_path.write_text(json.dumps(certificate), encoding="utf-8")
        summary_path = run_dir / "summary.md"
        summary_path.write_text("fixture\n", encoding="utf-8")
        manifest = {
            "files": {
                "results.json": sha256_file(results_path),
                "certificate.json": sha256_file(cert_path),
                "summary.md": sha256_file(summary_path),
            }
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        run_records.append({
            "run_name": run_name,
            "backend": backend,
            "job_id": f"job{index}",
            "classification": EXPECTED_RUN_CLASS,
            "valid": True,
        })

    replication_dir = replication_root / "rep1"
    replication_dir.mkdir(parents=True)
    rep_certificate = {
        "classification": EXPECTED_REPLICATION_CLASS,
        "run_count": 2,
        "passing_run_count": 2,
        "backend_count": 2,
        "backends": ["backend_a", "backend_b"],
        "job_ids": ["job1", "job2"],
        "duplicate_job_ids": [],
        "duplicate_result_hashes": [],
        "cross_run_stability": {"pass": True, "gates": {}, "statistics": {}},
        "runs": run_records,
    }
    rep_cert_path = replication_dir / "replication_certificate.json"
    rep_cert_path.write_text(json.dumps(rep_certificate), encoding="utf-8")
    rep_summary_path = replication_dir / "replication_summary.md"
    rep_summary_path.write_text("fixture\n", encoding="utf-8")
    rep_manifest = {
        "files": {
            "replication_certificate.json": sha256_file(rep_cert_path),
            "replication_summary.md": sha256_file(rep_summary_path),
        }
    }
    (replication_dir / "replication_manifest.json").write_text(
        json.dumps(rep_manifest), encoding="utf-8"
    )
    return runs_root, replication_dir


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        runs_root, replication_dir = make_fixture(root)
        export_dir = create_export(
            runs_root,
            replication_dir,
            root / "exports",
            require_git_frozen=False,
        )
        manifest = verify_transfer_bundle(export_dir)
        assert len(manifest["files"]) >= 12
        device_repo = root / "device"
        device_repo.mkdir()
        copied = copy_to_device(export_dir, device_repo)
        assert (copied / "device_copy_receipt.json").is_file()
        assert verify_transfer_bundle(copied)["schema"].endswith("_V1")
    print(
        "Self-test passed: replicated evidence is validated, frozen, copied, "
        "and hash-verified without modifying source files."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--replication-root", type=Path, default=DEFAULT_REPLICATION_ROOT)
    parser.add_argument("--replication-dir", type=Path)
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--device-repo", type=Path)
    args = parser.parse_args(argv)

    if args.self_test:
        self_test()
        return 0

    replication_dir = args.replication_dir or latest_manifest_directory(
        args.replication_root, "replication_manifest.json"
    )
    export_dir = create_export(
        args.runs_root,
        replication_dir,
        args.export_root,
        require_git_frozen=True,
    )
    result: dict[str, Any] = {
        "classification": EXPECTED_REPLICATION_CLASS,
        "device_evidence_status": DEVICE_STATUS,
        "export_directory": str(export_dir),
        "source_commit": load_json(export_dir / "transfer_certificate.json")["source_commit"],
    }
    if args.device_repo:
        device_destination = copy_to_device(export_dir, args.device_repo)
        result["device_destination"] = str(device_destination)
        result["copy_status"] = "COPIED_AND_HASH_VERIFIED"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
