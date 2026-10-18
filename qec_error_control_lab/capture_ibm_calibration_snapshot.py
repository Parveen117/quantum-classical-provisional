"""Capture the historical calibration snapshot bound to an IBM Runtime job."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from ibm_shor_3round_hardware import canonical_json, measurement_map_for_register


JOB_ID = "da2raps3jnrc73ae9n80"
BACKEND = "ibm_marrakesh"


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def parse_ancilla_map(text: str) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for item in text.split(","):
        key, value = item.split(":", 1)
        mapping[str(int(key.strip()))] = int(value.strip())
    if set(mapping) != {str(i) for i in range(8)}:
        raise ValueError("ancilla map must contain stabilizers 0..7 exactly once")
    if len(set(mapping.values())) != 8 or min(mapping.values()) < 0:
        raise ValueError("ancilla physical qubits must be eight distinct non-negative indices")
    return {str(i): mapping[str(i)] for i in range(8)}


def _find_circuits(value: Any, *, depth: int = 0, seen: set[int] | None = None) -> list[Any]:
    if depth > 8:
        return []
    seen = seen or set()
    identity = id(value)
    if identity in seen:
        return []
    seen.add(identity)
    if hasattr(value, "data") and hasattr(value, "find_bit") and hasattr(value, "num_qubits"):
        return [value]
    if isinstance(value, Mapping):
        output = []
        for child in value.values():
            output.extend(_find_circuits(child, depth=depth + 1, seen=seen))
        return output
    if isinstance(value, (list, tuple)):
        output = []
        for child in value:
            output.extend(_find_circuits(child, depth=depth + 1, seen=seen))
        return output
    for name in ("circuit", "pubs"):
        if hasattr(value, name):
            return _find_circuits(getattr(value, name), depth=depth + 1, seen=seen)
    return []


def ancilla_map_from_job(job, register_name: str = "syndrome") -> dict[str, int]:
    inputs = getattr(job, "inputs", None)
    inputs = inputs() if callable(inputs) else inputs
    circuits = _find_circuits(inputs)
    if not circuits:
        raise ValueError("submitted ISA circuits were not recoverable from job.inputs")
    maps = [measurement_map_for_register(circuit, register_name) for circuit in circuits]
    first = maps[0]
    if any(mapping != first for mapping in maps[1:]):
        raise ValueError("the four submitted circuits do not share one ancilla map")
    return first


def job_creation_time(job) -> datetime:
    value = getattr(job, "creation_date", None)
    value = value() if callable(value) else value
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError("job creation timestamp is unavailable")
    return value


def build_snapshot(
    *,
    job_id: str,
    backend_name: str,
    requested_time: datetime,
    properties,
    ancilla_map: Mapping[str, int],
) -> dict[str, Any]:
    qubits: dict[str, Any] = {}
    for physical in sorted(set(ancilla_map.values())):
        t1 = float(properties.t1(physical)) * 1e6
        t2 = float(properties.t2(physical)) * 1e6
        readout = float(properties.readout_error(physical))
        if t1 <= 0 or t2 <= 0 or not (0 <= readout <= 1):
            raise ValueError(f"invalid calibration values for physical qubit {physical}")
        qubits[str(physical)] = {
            "T1_us": t1,
            "T2_us": t2,
            "readout_error": readout,
        }
    update = getattr(properties, "last_update_date", None)
    update = update.isoformat() if hasattr(update, "isoformat") else str(update)
    body = {
        "schema": "rnke-thermo-decoherence-calibration-snapshot-v1",
        "job_id": job_id,
        "backend": backend_name,
        "snapshot_time": update,
        "properties_requested_at": requested_time.isoformat(),
        "historical_lookup_policy": "closest backend properties older than the job creation time",
        "qubits": qubits,
        "ancilla_map": {str(i): int(ancilla_map[str(i)]) for i in range(8)},
        "claim_boundary": "Calibration metadata for one backend epoch; not a device-wide lifetime claim.",
    }
    body["certificate_sha256"] = sha256_json(body)
    return body


def capture(job_id: str, *, instance: str = "auto", explicit_map: str | None = None) -> dict[str, Any]:
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
    except ImportError as exc:
        raise RuntimeError("install requirements-qiskit.txt before calibration capture") from exc
    service = QiskitRuntimeService(instance=instance)
    job = service.job(job_id)
    backend = job.backend()
    backend_name = getattr(backend, "name", BACKEND)
    backend_name = str(backend_name() if callable(backend_name) else backend_name)
    requested_time = job_creation_time(job)
    try:
        properties = backend.properties(datetime=requested_time)
    except NotImplementedError as exc:
        raise RuntimeError(
            "historical backend.properties(datetime=...) is unavailable for this account channel; "
            "do not substitute current calibration for the job epoch"
        ) from exc
    if properties is None:
        raise RuntimeError("historical backend properties are unavailable for the job epoch")
    mapping = parse_ancilla_map(explicit_map) if explicit_map else ancilla_map_from_job(job)
    return build_snapshot(
        job_id=job_id,
        backend_name=backend_name,
        requested_time=requested_time,
        properties=properties,
        ancilla_map=mapping,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", default=JOB_ID)
    parser.add_argument("--instance", default="auto")
    parser.add_argument("--ancilla-map", help="fallback format 0:q0,1:q1,...,7:q7")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "hardware_evidence" / f"{JOB_ID}_calibration_snapshot.json",
    )
    args = parser.parse_args()
    snapshot = capture(args.job_id, instance=args.instance, explicit_map=args.ancilla_map)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"JOB ID  : {snapshot['job_id']}")
    print(f"BACKEND : {snapshot['backend']}")
    print(f"SNAPSHOT: {snapshot['snapshot_time']}")
    print(f"SHA256  : {snapshot['certificate_sha256']}")
    print(f"SAVED   : {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
