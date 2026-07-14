#!/usr/bin/env python3
"""Single-command IBM Quantum test runner for the UGD seam-ledger star/delta benchmark.

Usage:
    python run_ugd_seam_ledger_test.py

Environment variables:
    IBM_QUANTUM_BACKEND   Optional backend name. Defaults to least-busy operational backend.
    IBM_QUANTUM_SHOTS     Optional shots per circuit. Defaults to 4096.
    IBM_QUANTUM_CHANNEL   Optional channel. Defaults to ibm_quantum_platform.
    IBM_QUANTUM_INSTANCE  Optional CRN/instance.

The script assumes IBM Quantum credentials are already saved locally.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from qiskit import QuantumCircuit, transpile
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
except ImportError as exc:
    raise SystemExit(
        "Missing dependencies. Install with: pip install qiskit qiskit-ibm-runtime"
    ) from exc


ROOT = Path(__file__).resolve().parent
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = ROOT / "ugd_seam_ledger_star_delta_v1" / "runs" / STAMP
SHOTS = int(os.getenv("IBM_QUANTUM_SHOTS", "4096"))
BACKEND_NAME = os.getenv("IBM_QUANTUM_BACKEND", "").strip()
CHANNEL = os.getenv("IBM_QUANTUM_CHANNEL", "ibm_quantum_platform").strip()
INSTANCE = os.getenv("IBM_QUANTUM_INSTANCE", "").strip() or None
PERTURBATIONS = (0.0, 0.15, 0.30, 0.45)
SEEDS = (11, 29, 47)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_circuit(topology: str, mode: str, epsilon: float) -> QuantumCircuit:
    """Create matched six-system-qubit plus one ledger-ancilla circuits."""
    qc = QuantumCircuit(7, 7, name=f"{topology}_{mode}_eps_{epsilon:.2f}")
    system = list(range(6))
    ledger = 6

    for q in system:
        qc.h(q)

    if topology == "star":
        edges = [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5)]
    elif topology == "delta":
        edges = [(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)]
    else:
        raise ValueError(f"Unknown topology: {topology}")

    for a, b in edges:
        qc.rzz(0.35, a, b)

    if epsilon:
        qc.rz(epsilon, 2)
        qc.rzz(epsilon, 1, 2)

    qc.h(ledger)
    if mode == "seam":
        qc.cx(ledger, 2)
        qc.cz(ledger, 2)
    elif mode == "commuting":
        qc.cz(ledger, 2)
        qc.cz(ledger, 2)
    elif mode == "order_erased":
        qc.cx(ledger, 2)
        qc.cz(ledger, 2)
        qc.cx(ledger, 2)
        qc.cz(ledger, 2)
    elif mode == "ordinary":
        qc.id(ledger)
    else:
        raise ValueError(f"Unknown mode: {mode}")
    qc.h(ledger)

    for q in system:
        qc.h(q)
    qc.measure(range(7), range(7))
    return qc


def select_backend(service: QiskitRuntimeService):
    if BACKEND_NAME:
        return service.backend(BACKEND_NAME)
    candidates = [
        b for b in service.backends(simulator=False, operational=True)
        if getattr(b.configuration(), "n_qubits", 0) >= 7
    ]
    if not candidates:
        raise RuntimeError("No operational IBM backend with at least 7 qubits is available.")
    return min(candidates, key=lambda b: b.status().pending_jobs)


def counts_from_pub_result(pub_result: Any) -> dict[str, int]:
    data = pub_result.data
    for name in ("c", "meas"):
        register = getattr(data, name, None)
        if register is not None and hasattr(register, "get_counts"):
            return dict(register.get_counts())
    for value in vars(data).values():
        if hasattr(value, "get_counts"):
            return dict(value.get_counts())
    raise RuntimeError("Could not locate measurement counts in Sampler result.")


def ancilla_p1(counts: dict[str, int]) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return sum(n for bits, n in counts.items() if bits.replace(" ", "")[0] == "1") / total


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=False)
    service_kwargs: dict[str, Any] = {"channel": CHANNEL}
    if INSTANCE:
        service_kwargs["instance"] = INSTANCE
    service = QiskitRuntimeService(**service_kwargs)
    backend = select_backend(service)

    records: list[dict[str, Any]] = []
    pubs = []
    metadata = []
    for topology in ("star", "delta"):
        for mode in ("ordinary", "seam", "commuting", "order_erased"):
            for epsilon in PERTURBATIONS:
                logical = build_circuit(topology, mode, epsilon)
                for seed in SEEDS:
                    compiled = transpile(
                        logical,
                        backend=backend,
                        optimization_level=3,
                        seed_transpiler=seed,
                    )
                    pubs.append(compiled)
                    metadata.append({
                        "topology": topology,
                        "mode": mode,
                        "epsilon": epsilon,
                        "seed_transpiler": seed,
                        "depth": compiled.depth(),
                        "two_qubit_ops": sum(
                            count for gate, count in compiled.count_ops().items()
                            if gate in {"cx", "cz", "ecr", "rzz"}
                        ),
                    })

    sampler = Sampler(mode=backend)
    job = sampler.run(pubs, shots=SHOTS)
    result = job.result()

    for meta, pub_result in zip(metadata, result):
        counts = counts_from_pub_result(pub_result)
        record = dict(meta)
        record["ancilla_p1"] = ancilla_p1(counts)
        record["counts"] = counts
        records.append(record)

    raw_path = OUT / "results.json"
    raw_path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")

    def mean_p1(topology: str, mode: str, epsilon: float) -> float:
        vals = [
            r["ancilla_p1"] for r in records
            if r["topology"] == topology and r["mode"] == mode and r["epsilon"] == epsilon
        ]
        return sum(vals) / len(vals)

    summary: dict[str, Any] = {}
    passes = []
    for topology in ("star", "delta"):
        baseline = mean_p1(topology, "seam", 0.0)
        high = mean_p1(topology, "seam", max(PERTURBATIONS))
        ordinary_high = mean_p1(topology, "ordinary", max(PERTURBATIONS))
        commuting_high = mean_p1(topology, "commuting", max(PERTURBATIONS))
        erased_high = mean_p1(topology, "order_erased", max(PERTURBATIONS))
        seam_response = abs(high - baseline)
        control_ceiling = max(
            abs(ordinary_high - mean_p1(topology, "ordinary", 0.0)),
            abs(commuting_high - mean_p1(topology, "commuting", 0.0)),
            abs(erased_high - mean_p1(topology, "order_erased", 0.0)),
        )
        topology_pass = seam_response > control_ceiling + 0.05
        passes.append(topology_pass)
        summary[topology] = {
            "seam_baseline_p1": baseline,
            "seam_high_perturbation_p1": high,
            "seam_response": seam_response,
            "largest_control_response": control_ceiling,
            "pass": topology_pass,
        }

    certificate = {
        "schema": "UGD_SEAM_LEDGER_STAR_DELTA_CERTIFICATE_V1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "backend": backend.name,
        "job_id": job.job_id(),
        "shots_per_circuit": SHOTS,
        "perturbations": PERTURBATIONS,
        "transpiler_seeds": SEEDS,
        "classification": (
            "SEAM_LEDGER_DEVICE_EFFECT_CANDIDATE"
            if all(passes)
            else "NO_REPRODUCIBLE_SEAM_LEDGER_ADVANTAGE"
        ),
        "summary": summary,
        "scientific_boundary": (
            "This benchmark tests whether an RK/KR-inspired ledger changes perturbation "
            "recognition in matched star/delta circuits. It does not establish a new "
            "physical law or device advantage without independent replication."
        ),
        "raw_results_sha256": sha256_file(raw_path),
    }
    cert_path = OUT / "certificate.json"
    cert_path.write_text(json.dumps(certificate, indent=2, sort_keys=True), encoding="utf-8")

    manifest = {
        "backend": backend.name,
        "job_id": job.job_id(),
        "files": {
            raw_path.name: sha256_file(raw_path),
            cert_path.name: sha256_file(cert_path),
        },
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    print(json.dumps(certificate, indent=2, sort_keys=True))
    print(f"\nEvidence written to: {OUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
