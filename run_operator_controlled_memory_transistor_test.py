#!/usr/bin/env python3
"""IBM Quantum benchmark for an operator-controlled transistor with intrinsic memory.

Jupyter:
    %run r"C:\Users\abc\Desktop\New Folder (2)\New folder\PROVISNAL RELATED\Quantum classical\run_operator_controlled_memory_transistor_test.py"

Assumptions:
- IBM Quantum credentials are already saved locally.
- qiskit and qiskit-ibm-runtime are installed.

Optional environment variables:
- IBM_QUANTUM_BACKEND
- IBM_QUANTUM_SHOTS          default 4096
- IBM_QUANTUM_CHANNEL        default ibm_quantum_platform
- IBM_QUANTUM_INSTANCE
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
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
OUT = ROOT / "operator_controlled_memory_transistor_v1" / "runs" / STAMP
SHOTS = int(os.getenv("IBM_QUANTUM_SHOTS", "4096"))
BACKEND_NAME = os.getenv("IBM_QUANTUM_BACKEND", "").strip()
CHANNEL = os.getenv("IBM_QUANTUM_CHANNEL", "ibm_quantum_platform").strip()
INSTANCE = os.getenv("IBM_QUANTUM_INSTANCE", "").strip() or None
SEEDS = (11, 29, 47)

TRAJECTORIES: dict[str, tuple[float, ...]] = {
    "same_final_high": (0.0, 1.20, 0.60),
    "same_final_low": (0.0, 0.20, 0.60),
    "forward_sweep": (0.0, 0.20, 0.60, 1.00),
    "reverse_sweep": (1.00, 0.60, 0.20, 0.00),
}
MODES = (
    "operator_memory",
    "boundary_only",
    "memoryless",
    "memory_erased",
    "history_shuffled",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def select_backend(service: QiskitRuntimeService):
    if BACKEND_NAME:
        return service.backend(BACKEND_NAME)
    candidates = [
        b
        for b in service.backends(simulator=False, operational=True)
        if getattr(b.configuration(), "n_qubits", 0) >= 6
    ]
    if not candidates:
        raise RuntimeError("No operational IBM backend with at least 6 qubits is available.")
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


def bit_probability(counts: dict[str, int], classical_bit: int) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    index = 5 - classical_bit
    return sum(
        n
        for bits, n in counts.items()
        if bits.replace(" ", "")[index] == "1"
    ) / total


def apply_internal_evolution(qc: QuantumCircuit, theta: float, *, write_memory: bool) -> None:
    """Gate-selected nonlinear analogue acting on n, phi, T and memory registers."""
    n, phi, temp, memory, gate, drain = range(6)

    qc.ry(theta, gate)

    # Gate reshapes the evolution operator F -> F_VG.
    qc.crx(0.55 + 0.35 * math.sin(theta), gate, n)
    qc.cry(0.40 + 0.25 * math.cos(theta), gate, phi)
    qc.crz(0.30 + 0.20 * math.sin(2.0 * theta), gate, temp)

    # Coupled nonlinear internal evolution.
    qc.rzz(0.22 + 0.12 * theta, n, phi)
    qc.rzz(0.18 + 0.08 * theta, phi, temp)
    qc.cx(n, temp)
    qc.rz(0.10 + 0.07 * theta, temp)
    qc.cx(n, temp)

    if write_memory:
        qc.crx(0.45 + 0.30 * theta, gate, memory)
        qc.cz(phi, memory)
        qc.rzz(0.20 + 0.10 * theta, temp, memory)

    qc.ry(-theta, gate)


def build_circuit(mode: str, trajectory_name: str) -> QuantumCircuit:
    """Build the six-qubit transistor analogue.

    q0 n: carrier/conduction state
    q1 phi: electrostatic phase
    q2 T: slow thermal/history state
    q3 m: intrinsic memory ledger
    q4 g: gate-control register
    q5 d: drain-current projection ancilla
    """
    qc = QuantumCircuit(6, 6, name=f"{mode}_{trajectory_name}")
    n, phi, temp, memory, gate, drain = range(6)
    trajectory = TRAJECTORIES[trajectory_name]

    qc.h(n)
    qc.ry(0.35, phi)
    qc.ry(0.20, temp)

    if mode == "operator_memory":
        for theta in trajectory:
            apply_internal_evolution(qc, theta, write_memory=True)

    elif mode == "boundary_only":
        apply_internal_evolution(qc, trajectory[-1], write_memory=False)

    elif mode == "memoryless":
        for theta in trajectory:
            apply_internal_evolution(qc, theta, write_memory=False)

    elif mode == "memory_erased":
        for theta in trajectory:
            apply_internal_evolution(qc, theta, write_memory=True)
        # Genuine ledger erasure before output projection.
        qc.reset(memory)

    elif mode == "history_shuffled":
        shuffled = tuple(reversed(trajectory[:-1])) + (trajectory[-1],)
        for theta in shuffled:
            apply_internal_evolution(qc, theta, write_memory=True)

    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Observable drain-current projection Pi(X).
    qc.h(drain)
    qc.cx(n, drain)
    qc.cz(phi, drain)
    qc.crx(0.65, temp, drain)
    qc.crz(0.75, memory, drain)
    qc.h(drain)

    qc.measure(range(6), range(6))
    return qc


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=False)

    service_kwargs: dict[str, Any] = {"channel": CHANNEL}
    if INSTANCE:
        service_kwargs["instance"] = INSTANCE
    service = QiskitRuntimeService(**service_kwargs)
    backend = select_backend(service)

    pubs = []
    metadata: list[dict[str, Any]] = []
    for mode in MODES:
        for trajectory_name in TRAJECTORIES:
            logical = build_circuit(mode, trajectory_name)
            for seed in SEEDS:
                compiled = transpile(
                    logical,
                    backend=backend,
                    optimization_level=3,
                    seed_transpiler=seed,
                )
                pubs.append(compiled)
                metadata.append(
                    {
                        "mode": mode,
                        "trajectory": trajectory_name,
                        "trajectory_values": TRAJECTORIES[trajectory_name],
                        "seed_transpiler": seed,
                        "depth": compiled.depth(),
                        "two_qubit_ops": sum(
                            count
                            for gate_name, count in compiled.count_ops().items()
                            if gate_name in {"cx", "cz", "ecr", "rzz", "crx", "cry", "crz"}
                        ),
                    }
                )

    sampler = Sampler(mode=backend)
    job = sampler.run(pubs, shots=SHOTS)
    result = job.result()

    records: list[dict[str, Any]] = []
    for meta, pub_result in zip(metadata, result):
        counts = counts_from_pub_result(pub_result)
        record = dict(meta)
        record["drain_p1"] = bit_probability(counts, 5)
        record["memory_p1"] = bit_probability(counts, 3)
        record["counts"] = counts
        records.append(record)

    raw_path = OUT / "results.json"
    raw_path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")

    def metric(mode: str, trajectory: str, key: str) -> float:
        vals = [
            float(r[key])
            for r in records
            if r["mode"] == mode and r["trajectory"] == trajectory
        ]
        return mean(vals)

    def same_final_gap(mode: str, key: str) -> float:
        return abs(
            metric(mode, "same_final_high", key)
            - metric(mode, "same_final_low", key)
        )

    def hysteresis_gap(mode: str, key: str) -> float:
        return abs(
            metric(mode, "forward_sweep", key)
            - metric(mode, "reverse_sweep", key)
        )

    summaries: dict[str, Any] = {}
    for mode in MODES:
        summaries[mode] = {
            "same_final_drain_gap": same_final_gap(mode, "drain_p1"),
            "same_final_memory_gap": same_final_gap(mode, "memory_p1"),
            "forward_reverse_drain_gap": hysteresis_gap(mode, "drain_p1"),
            "forward_reverse_memory_gap": hysteresis_gap(mode, "memory_p1"),
            "mean_drain_p1": mean(
                float(r["drain_p1"]) for r in records if r["mode"] == mode
            ),
            "mean_memory_p1": mean(
                float(r["memory_p1"]) for r in records if r["mode"] == mode
            ),
        }

    operator_gap = summaries["operator_memory"]["same_final_drain_gap"]
    operator_hysteresis = summaries["operator_memory"]["forward_reverse_drain_gap"]
    control_same_final = max(
        summaries[m]["same_final_drain_gap"]
        for m in ("boundary_only", "memoryless", "memory_erased", "history_shuffled")
    )
    control_hysteresis = max(
        summaries[m]["forward_reverse_drain_gap"]
        for m in ("boundary_only", "memoryless", "memory_erased", "history_shuffled")
    )

    same_final_margin = operator_gap - control_same_final
    hysteresis_margin = operator_hysteresis - control_hysteresis
    passes = same_final_margin > 0.02 and hysteresis_margin > 0.02

    certificate = {
        "schema": "OPERATOR_CONTROLLED_MEMORY_TRANSISTOR_CERTIFICATE_V1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "backend": backend.name,
        "job_id": job.job_id(),
        "shots_per_circuit": SHOTS,
        "transpiler_seeds": SEEDS,
        "trajectories": TRAJECTORIES,
        "classification": (
            "OPERATOR_CONTROLLED_MEMORY_EFFECT_CANDIDATE"
            if passes
            else "NO_REPRODUCIBLE_OPERATOR_MEMORY_ADVANTAGE"
        ),
        "primary_metrics": {
            "operator_same_final_drain_gap": operator_gap,
            "largest_control_same_final_drain_gap": control_same_final,
            "same_final_margin": same_final_margin,
            "operator_forward_reverse_drain_gap": operator_hysteresis,
            "largest_control_forward_reverse_drain_gap": control_hysteresis,
            "hysteresis_margin": hysteresis_margin,
            "pass_threshold_each_margin": 0.02,
        },
        "summary": summaries,
        "scientific_boundary": (
            "This is a quantum analogue of gate-controlled internal evolution, hidden memory, "
            "and drain projection. It does not establish a fabricated transistor, material "
            "performance, commercial device advantage, or a new physical law without independent "
            "replication and real electrical measurements."
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
    manifest_path = OUT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

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
