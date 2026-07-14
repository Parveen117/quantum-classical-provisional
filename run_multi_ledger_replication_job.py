#!/usr/bin/env python3
r"""Submit one independent multi-ledger replication job and evaluate the campaign.

The runner selects one operational IBM backend that has not already been used
by a completed local evidence bundle. It invokes the existing declared
multi-ledger benchmark unchanged, then runs the offline replication evaluator.

Jupyter:
    %run r"C:\Users\abc\Desktop\New Folder (2)\New folder\PROVISNAL RELATED\Quantum classical\run_multi_ledger_replication_job.py"

Usage:
    python run_multi_ledger_replication_job.py
    python run_multi_ledger_replication_job.py --backend ibm_backend_name
    python run_multi_ledger_replication_job.py --allow-used-backend
    python run_multi_ledger_replication_job.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parent
RUNS_ROOT = ROOT / "multi_ledger_operator_memory_v1" / "runs"
BENCHMARK = ROOT / "run_multi_ledger_operator_memory_test.py"
EVALUATOR = ROOT / "evaluate_multi_ledger_replication.py"

CHANNEL = os.getenv("IBM_QUANTUM_CHANNEL", "ibm_quantum_platform").strip()
INSTANCE = os.getenv("IBM_QUANTUM_INSTANCE", "").strip() or None


def load_used_backends(runs_root: Path = RUNS_ROOT) -> set[str]:
    used: set[str] = set()
    if not runs_root.exists():
        return used
    for certificate_path in sorted(runs_root.glob("*/certificate.json")):
        try:
            certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        backend = str(certificate.get("backend", "")).strip()
        job_id = str(certificate.get("job_id", "")).strip()
        if backend and job_id:
            used.add(backend)
    return used


def backend_qubits(backend: Any) -> int:
    value = getattr(backend, "num_qubits", None)
    if isinstance(value, int):
        return value
    try:
        configuration = backend.configuration()
    except Exception:
        return 0
    return int(getattr(configuration, "n_qubits", 0) or 0)


def backend_pending_jobs(backend: Any) -> int:
    try:
        status = backend.status()
    except Exception:
        return 10**9
    return int(getattr(status, "pending_jobs", 10**9) or 0)


def backend_name(backend: Any) -> str:
    name = getattr(backend, "name", "")
    if callable(name):
        name = name()
    return str(name).strip()


def select_backend(
    backends: Iterable[Any],
    *,
    used_backends: set[str],
    requested_backend: str = "",
    allow_used_backend: bool = False,
) -> Any:
    candidates = []
    for backend in backends:
        name = backend_name(backend)
        if not name:
            continue
        if requested_backend and name != requested_backend:
            continue
        if backend_qubits(backend) < 7:
            continue
        if not allow_used_backend and name in used_backends:
            continue
        candidates.append(backend)

    if requested_backend and not candidates:
        if requested_backend in used_backends and not allow_used_backend:
            raise RuntimeError(
                f"{requested_backend} already has local evidence. "
                "Choose another backend or pass --allow-used-backend."
            )
        raise RuntimeError(
            f"Requested backend {requested_backend!r} is unavailable, "
            "non-operational, or has fewer than 7 qubits."
        )

    if not candidates:
        if used_backends and not allow_used_backend:
            raise RuntimeError(
                "No unused operational backend with at least 7 qubits is "
                "currently available. Retry later or pass --allow-used-backend "
                "for same-backend replication."
            )
        raise RuntimeError(
            "No operational backend with at least 7 qubits is currently available."
        )

    return min(candidates, key=backend_pending_jobs)


def service_backends(service: Any) -> list[Any]:
    return list(service.backends(simulator=False, operational=True))


def run_checked(command: Sequence[str], *, env: dict[str, str] | None = None) -> None:
    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        env=env,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with return code {completed.returncode}: "
            + " ".join(command)
        )


def submit_replication(
    *,
    requested_backend: str = "",
    allow_used_backend: bool = False,
) -> str:
    if not BENCHMARK.exists():
        raise FileNotFoundError(f"Benchmark runner is missing: {BENCHMARK}")
    if not EVALUATOR.exists():
        raise FileNotFoundError(f"Replication evaluator is missing: {EVALUATOR}")

    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency. Install with: pip install qiskit-ibm-runtime"
        ) from exc

    used = load_used_backends()
    service_kwargs: dict[str, Any] = {"channel": CHANNEL}
    if INSTANCE:
        service_kwargs["instance"] = INSTANCE
    service = QiskitRuntimeService(**service_kwargs)

    selected = select_backend(
        service_backends(service),
        used_backends=used,
        requested_backend=requested_backend,
        allow_used_backend=allow_used_backend,
    )
    selected_name = backend_name(selected)

    print("Previously used backends:", sorted(used) or ["none"])
    print("Selected replication backend:", selected_name)
    print("Submitting exactly one independent benchmark job.")

    child_env = os.environ.copy()
    child_env["IBM_QUANTUM_BACKEND"] = selected_name

    run_checked([sys.executable, str(BENCHMARK)], env=child_env)
    run_checked([sys.executable, str(EVALUATOR)], env=child_env)
    return selected_name


class _FakeStatus:
    def __init__(self, pending_jobs: int):
        self.pending_jobs = pending_jobs


class _FakeBackend:
    def __init__(self, name: str, qubits: int, pending_jobs: int):
        self.name = name
        self.num_qubits = qubits
        self._pending_jobs = pending_jobs

    def status(self) -> _FakeStatus:
        return _FakeStatus(self._pending_jobs)


def self_test() -> None:
    backends = [
        _FakeBackend("used_backend", 127, 0),
        _FakeBackend("small_backend", 5, 0),
        _FakeBackend("fresh_busy", 127, 12),
        _FakeBackend("fresh_quiet", 127, 2),
    ]
    selected = select_backend(
        backends,
        used_backends={"used_backend"},
    )
    assert backend_name(selected) == "fresh_quiet"

    requested = select_backend(
        backends,
        used_backends={"used_backend"},
        requested_backend="fresh_busy",
    )
    assert backend_name(requested) == "fresh_busy"

    try:
        select_backend(
            backends,
            used_backends={"used_backend"},
            requested_backend="used_backend",
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Used backend was not rejected.")

    allowed = select_backend(
        backends,
        used_backends={"used_backend"},
        requested_backend="used_backend",
        allow_used_backend=True,
    )
    assert backend_name(allowed) == "used_backend"

    print(
        "Self-test passed: used backends are excluded, small backends are "
        "rejected, and the least-busy eligible backend is selected."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", default="")
    parser.add_argument("--allow-used-backend", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        self_test()
        return 0

    submit_replication(
        requested_backend=args.backend.strip(),
        allow_used_backend=args.allow_used_backend,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
