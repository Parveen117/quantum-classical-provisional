#!/usr/bin/env python3
"""Backend adapter layer for Quantum Native Bridge Pro.

This module gives the bridge a clean interface for simulators, hardware backends,
or recorded experiment outputs. It keeps the core bridge independent from any
vendor SDK while still allowing real quantum job metadata to be attached.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class QuantumJobInput:
    job_id: str
    root: Dict[str, Any]
    template: Dict[str, Any]
    phase: Dict[str, Any]
    shots: int = 1024
    backend: str = "external"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuantumJobOutput:
    job_id: str
    observed_counts: Dict[str, int]
    backend: str
    shots: int
    completed_at_ns: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RecordedBackendAdapter:
    """Adapter for recorded simulator or hardware result files."""

    def __init__(self, results_path: str | Path) -> None:
        self.results_path = Path(results_path)

    def load_output(self, job_id: str) -> QuantumJobOutput:
        data = json.loads(self.results_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            matches = [item for item in data if str(item.get("job_id")) == str(job_id)]
            if not matches:
                raise KeyError(f"job_id not found: {job_id}")
            data = matches[0]
        if str(data.get("job_id")) != str(job_id):
            raise KeyError(f"job_id mismatch: expected {job_id}, found {data.get('job_id')}")
        return QuantumJobOutput(
            job_id=str(data["job_id"]),
            observed_counts={str(k): int(v) for k, v in dict(data["observed_counts"]).items()},
            backend=str(data.get("backend", "recorded")),
            shots=int(data.get("shots", sum(int(v) for v in dict(data["observed_counts"]).values()))),
            completed_at_ns=int(data.get("completed_at_ns", time.time_ns())),
            metadata=dict(data.get("metadata", {})),
        )


def bridge_payload_from_job(job: QuantumJobInput, output: QuantumJobOutput) -> Dict[str, Any]:
    """Return normalized inputs for QuantumNativeBridge.append."""
    return {
        "root": job.root,
        "template": job.template,
        "phase": {
            **job.phase,
            "job_id": job.job_id,
            "backend": output.backend,
            "shots": output.shots,
            "completed_at_ns": output.completed_at_ns,
        },
        "observed": output.observed_counts,
        "backend": output.backend,
        "shots": output.shots,
        "metadata": {
            **job.metadata,
            **output.metadata,
            "adapter": "RecordedBackendAdapter",
        },
    }


def build_job_from_json(path: str | Path) -> QuantumJobInput:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return QuantumJobInput(
        job_id=str(data["job_id"]),
        root=dict(data["root"]),
        template=dict(data["template"]),
        phase=dict(data["phase"]),
        shots=int(data.get("shots", 1024)),
        backend=str(data.get("backend", "external")),
        metadata=dict(data.get("metadata", {})),
    )


def main() -> int:
    import argparse
    from .bridge import QuantumNativeBridge

    parser = argparse.ArgumentParser(description="Recorded backend adapter for Quantum Native Bridge Pro")
    parser.add_argument("--job", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--ledger", required=True)
    args = parser.parse_args()

    job = build_job_from_json(args.job)
    output = RecordedBackendAdapter(args.result).load_output(job.job_id)
    payload = bridge_payload_from_job(job, output)
    bridge = QuantumNativeBridge(args.ledger)
    record = bridge.append(**payload)
    print(json.dumps(record.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
