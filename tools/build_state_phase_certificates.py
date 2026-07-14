#!/usr/bin/env python3
"""Build cautious quantum state, dynamics, and phase certificates.

The builder consumes existing Bell/runtime evidence without inventing missing
physics. Computational-basis probabilities can support distribution closure,
but they cannot by themselves distinguish Bell phase. Missing tomography,
non-commuting-basis witnesses, or gate-path evidence therefore remains marked
PARTIAL or UNEVALUATED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def canonical_hash(obj: Dict[str, Any]) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def walk(obj: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key, value
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def first_value(obj: Any, names: set[str]) -> Optional[Any]:
    lowered = {name.lower() for name in names}
    for key, value in walk(obj):
        if key.lower() in lowered:
            return value
    return None


def find_first(root: Path, names: list[str]) -> Optional[Path]:
    for name in names:
        path = root / name
        if path.exists():
            return path
    return None


def source_record(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    return {"path": path.name, "sha256": file_hash(path)}


def state_certificate(root: Path, bell_path: Optional[Path], calibration_path: Optional[Path]) -> Dict[str, Any]:
    bell = load_json(bell_path) if bell_path else {}
    model_id = first_value(bell, {"model_id", "state_id", "bell_model_id"}) or "bell_phi_plus_declared"
    basis = first_value(bell, {"basis", "measurement_basis"}) or "computational"
    expected = first_value(bell, {"expected_distribution", "expected_probabilities", "target_distribution"})
    observed = first_value(bell, {"observed_distribution", "observed_probabilities", "distribution"})
    has_density = first_value(bell, {"density_matrix", "rho", "reconstructed_density_matrix"}) is not None
    has_tomography = bool(first_value(bell, {"tomography", "state_tomography", "fidelity"}) is not None)
    status = "EVALUATED" if has_density and has_tomography else "PARTIAL"
    reason = (
        "Density-matrix or tomography evidence is present."
        if status == "EVALUATED"
        else "Distribution evidence identifies a declared Bell model but does not uniquely reconstruct the quantum state."
    )
    cert: Dict[str, Any] = {
        "certificate_type": "QUANTUM_STATE_CERTIFICATE",
        "version": "1.0",
        "state_model": {
            "model_id": model_id,
            "declared_state": "(|00> + |11>)/sqrt(2)",
            "measurement_basis": basis,
            "expected_distribution": expected,
            "observed_distribution": observed,
        },
        "evidence_status": status,
        "density_matrix_available": has_density,
        "tomography_or_fidelity_available": has_tomography,
        "reason": reason,
        "sources": [record for record in [source_record(bell_path), source_record(calibration_path)] if record],
        "limitations": [
            "Computational-basis outcome agreement is distribution evidence, not unique state reconstruction.",
            "Full state closure requires density-matrix reconstruction, tomography, or an equivalent informationally complete witness.",
        ],
    }
    cert["certificate_sha256"] = canonical_hash(cert)
    return cert


def dynamics_certificate(root: Path, bundle_path: Optional[Path], ledger_path: Optional[Path]) -> Dict[str, Any]:
    bundle = load_json(bundle_path) if bundle_path else {}
    gate_path = first_value(bundle, {"gate_path", "circuit", "operations", "instruction_path"})
    backend = first_value(bundle, {"backend", "backend_id", "backend_name"})
    channel = first_value(bundle, {"channel", "noise_model", "evolution_model"})
    has_ledger = ledger_path is not None
    status = "EVALUATED" if gate_path is not None and has_ledger else "PARTIAL"
    cert: Dict[str, Any] = {
        "certificate_type": "QUANTUM_DYNAMICS_CERTIFICATE",
        "version": "1.0",
        "evidence_status": status,
        "declared_dynamics": {
            "gate_path_or_circuit": gate_path,
            "backend": backend,
            "channel_or_noise_model": channel,
            "ledger_present": has_ledger,
        },
        "reason": (
            "An explicit gate path and execution ledger are available."
            if status == "EVALUATED"
            else "Runtime provenance exists, but an explicit prepared-to-measured evolution path is incomplete."
        ),
        "sources": [record for record in [source_record(bundle_path), source_record(ledger_path)] if record],
        "requirements_for_closure": [
            "declared input state",
            "ordered gate or channel path",
            "backend and calibration epoch",
            "executed-path or transpilation evidence",
            "comparison rule between declared and executed dynamics",
        ],
    }
    cert["certificate_sha256"] = canonical_hash(cert)
    return cert


def phase_certificate(root: Path, bell_path: Optional[Path]) -> Dict[str, Any]:
    bell = load_json(bell_path) if bell_path else {}
    xx = first_value(bell, {"xx", "xx_expectation", "x_x_correlation"})
    yy = first_value(bell, {"yy", "yy_expectation", "y_y_correlation"})
    zz = first_value(bell, {"zz", "zz_expectation", "z_z_correlation"})
    phase = first_value(bell, {"relative_phase", "phase_estimate", "phase_witness"})
    witnesses = {"XX": xx, "YY": yy, "ZZ": zz, "relative_phase": phase}
    available = [key for key, value in witnesses.items() if value is not None]
    status = "EVALUATED" if phase is not None or len([v for v in (xx, yy, zz) if v is not None]) >= 2 else "UNEVALUATED"
    cert: Dict[str, Any] = {
        "certificate_type": "QUANTUM_PHASE_CERTIFICATE",
        "version": "1.0",
        "evidence_status": status,
        "phase_witnesses": witnesses,
        "available_witnesses": available,
        "reason": (
            "Non-commuting-basis or explicit relative-phase evidence is available."
            if status == "EVALUATED"
            else "Computational-basis Bell probabilities cannot distinguish Phi+ from Phi-; no sufficient phase witness was found."
        ),
        "sources": [record for record in [source_record(bell_path)] if record],
        "required_measurements": [
            "X-basis correlations such as <X tensor X>",
            "Y-basis correlations or an equivalent phase-sensitive witness",
            "registered uncertainty and acceptance thresholds",
        ],
    }
    cert["certificate_sha256"] = canonical_hash(cert)
    return cert


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--out-dir", type=Path, default=Path("generated_certificates"))
    args = parser.parse_args()
    root = args.root.resolve()
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    bell = find_first(root, ["trial-bell-evaluation.json", "QUANTUM_NATIVE_BRIDGE_PRO_EVIDENCE/advanced-runtime-validation-report.json"])
    calibration = find_first(root, ["trial-calibration-report.json"])
    bundle = find_first(root, ["trial-integrated-quantum-evidence-bundle.json", "trial-quantum-evidence-bundle.json"])
    ledger = find_first(root, ["trial-expected-integrated-ledger.jsonl", "trial-quantum-ledger.jsonl"])

    certs = {
        "quantum_state_certificate.json": state_certificate(root, bell, calibration),
        "quantum_dynamics_certificate.json": dynamics_certificate(root, bundle, ledger),
        "quantum_phase_certificate.json": phase_certificate(root, bell),
    }
    for name, cert in certs.items():
        (out_dir / name).write_text(json.dumps(cert, indent=2, sort_keys=True), encoding="utf-8")
        print(name, cert["evidence_status"], cert["certificate_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
