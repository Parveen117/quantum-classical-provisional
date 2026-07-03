import json
from pathlib import Path

from quantum_native_bridge_pro.backend_adapter import (
    RecordedBackendAdapter,
    QuantumJobInput,
    bridge_payload_from_job,
    build_job_from_json,
)
from quantum_native_bridge_pro import QuantumNativeBridge


def test_recorded_backend_adapter_roundtrip(tmp_path: Path):
    job_path = tmp_path / "job.json"
    result_path = tmp_path / "result.json"
    ledger_path = tmp_path / "bridge.jsonl"

    job_path.write_text(json.dumps({
        "job_id": "job-1",
        "root": {"circuit": "bell", "qubits": 2},
        "template": {"gates": ["H", "CX"]},
        "phase": {"session": "s1"},
        "shots": 100,
        "backend": "recorded",
    }), encoding="utf-8")
    result_path.write_text(json.dumps({
        "job_id": "job-1",
        "observed_counts": {"00": 48, "11": 52},
        "backend": "recorded",
        "shots": 100,
        "completed_at_ns": 123,
    }), encoding="utf-8")

    job = build_job_from_json(job_path)
    output = RecordedBackendAdapter(result_path).load_output("job-1")
    payload = bridge_payload_from_job(job, output)
    record = QuantumNativeBridge(ledger_path).append(**payload)

    assert record.sequence == 1
    assert record.backend == "recorded"
    assert QuantumNativeBridge(ledger_path).verify_chain()["valid"] is True
    assert payload["phase"]["job_id"] == "job-1"
