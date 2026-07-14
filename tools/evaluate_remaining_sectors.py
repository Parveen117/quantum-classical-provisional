#!/usr/bin/env python3
"""Evaluate state, dynamics, and memory evidence for the quantum projection.

No third-party dependencies. The tool consumes optional JSON evidence files and
emits three certificates. Missing evidence is UNEVALUATED, incomplete evidence is
PARTIAL, and only explicit quantitative witnesses can become EVALUATED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List


def digest(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def load(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_cert(out: Path, cert: Dict[str, Any]) -> None:
    cert["certificate_sha256"] = digest(cert)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cert, indent=2, sort_keys=True), encoding="utf-8")
    print(out.name, cert["evidence_status"], cert["certificate_sha256"])


def state_certificate(data: Any) -> Dict[str, Any]:
    cert = {
        "certificate_type": "QUANTUM_STATE_WITNESS_CERTIFICATE",
        "version": "1.0.0",
        "evidence_status": "UNEVALUATED",
        "reason": "No explicit state witness file was supplied.",
        "scientific_scope": "State witness evaluation; not full tomography unless tomography data are supplied.",
    }
    if not isinstance(data, dict):
        return cert
    method = str(data.get("method", "")).lower()
    fidelity = data.get("fidelity")
    threshold = data.get("threshold", 0.9)
    witnesses = data.get("witnesses")
    if isinstance(fidelity, (int, float)) and math.isfinite(float(fidelity)):
        cert.update({"method": method or "declared_fidelity", "fidelity": float(fidelity), "threshold": float(threshold)})
        cert["evidence_status"] = "EVALUATED"
        cert["classification"] = "RECOGNITION" if float(fidelity) >= float(threshold) else "REJECT"
        cert["reason"] = "A quantitative state-fidelity witness was supplied and evaluated against its declared threshold."
    elif isinstance(witnesses, dict) and witnesses:
        cert.update({"method": method or "state_witness_set", "witnesses": witnesses})
        cert["evidence_status"] = "PARTIAL"
        cert["classification"] = "RESIDUE"
        cert["reason"] = "State witnesses exist, but no complete fidelity or tomography decision rule was supplied."
    else:
        cert["evidence_status"] = "PARTIAL"
        cert["classification"] = "RESIDUE"
        cert["reason"] = "A state declaration exists, but no quantitative state witness was found."
    return cert


def dynamics_certificate(data: Any) -> Dict[str, Any]:
    cert = {
        "certificate_type": "QUANTUM_DYNAMICS_PATH_CERTIFICATE",
        "version": "1.0.0",
        "evidence_status": "UNEVALUATED",
        "reason": "No explicit dynamics-path file was supplied.",
    }
    if not isinstance(data, dict):
        return cert
    declared = data.get("declared_path")
    executed = data.get("executed_path")
    tolerance = float(data.get("tolerance", 0.0))
    path_gap = data.get("path_gap")
    if isinstance(path_gap, (int, float)) and math.isfinite(float(path_gap)):
        cert.update({"path_gap": float(path_gap), "tolerance": tolerance, "declared_path": declared, "executed_path": executed})
        cert["evidence_status"] = "EVALUATED"
        cert["classification"] = "RECOGNITION" if float(path_gap) <= tolerance else "REJECT"
        cert["reason"] = "Prepared-to-measured dynamics were compared using an explicit path-gap rule."
    elif declared and executed:
        cert.update({"declared_path": declared, "executed_path": executed})
        cert["evidence_status"] = "PARTIAL"
        cert["classification"] = "RESIDUE"
        cert["reason"] = "Declared and executed paths exist, but no quantitative path metric was supplied."
    else:
        cert["evidence_status"] = "PARTIAL"
        cert["classification"] = "RESIDUE"
        cert["reason"] = "Runtime provenance exists without a complete declared-to-executed path comparison."
    return cert


def memory_certificate(data: Any) -> Dict[str, Any]:
    cert = {
        "certificate_type": "QUANTUM_MEMORY_DRIFT_CERTIFICATE",
        "version": "1.0.0",
        "evidence_status": "UNEVALUATED",
        "reason": "No repeated-run memory evidence was supplied.",
    }
    if not isinstance(data, dict):
        return cert
    values = data.get("ordered_metric_values")
    threshold = float(data.get("drift_threshold", 0.05))
    if isinstance(values, list) and len(values) >= 3 and all(isinstance(x, (int, float)) for x in values):
        vals = [float(x) for x in values]
        drift = max(vals) - min(vals)
        cert.update({"run_count": len(vals), "ordered_metric_values": vals, "observed_drift": drift, "drift_threshold": threshold})
        cert["evidence_status"] = "EVALUATED"
        cert["classification"] = "RECOGNITION" if drift <= threshold else "RESIDUE"
        cert["reason"] = "Repeated ordered runs were evaluated for history-dependent drift."
    elif isinstance(values, list) and values:
        cert["evidence_status"] = "PARTIAL"
        cert["classification"] = "RESIDUE"
        cert["reason"] = "Repeated-run data exist, but at least three ordered quantitative runs are required."
    return cert


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--state", type=Path)
    p.add_argument("--dynamics", type=Path)
    p.add_argument("--memory", type=Path)
    p.add_argument("--out-dir", type=Path, default=Path("generated_certificates"))
    a = p.parse_args()
    root = a.root.resolve()
    out = a.out_dir if a.out_dir.is_absolute() else root / a.out_dir
    state_path = a.state if a.state and a.state.is_absolute() else (root / a.state if a.state else root / "trial-state-witness.json")
    dyn_path = a.dynamics if a.dynamics and a.dynamics.is_absolute() else (root / a.dynamics if a.dynamics else root / "trial-dynamics-path.json")
    mem_path = a.memory if a.memory and a.memory.is_absolute() else (root / a.memory if a.memory else root / "trial-memory-drift.json")
    write_cert(out / "quantum_state_witness_certificate.json", state_certificate(load(state_path)))
    write_cert(out / "quantum_dynamics_path_certificate.json", dynamics_certificate(load(dyn_path)))
    write_cert(out / "quantum_memory_certificate.json", memory_certificate(load(mem_path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
