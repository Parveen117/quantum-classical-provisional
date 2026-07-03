import json
import subprocess
import sys
from pathlib import Path

import pytest

from quantum_native_bridge_pro import QuantumNativeBridge, VerificationError, measurement_metrics


def test_append_and_verify_chain(tmp_path: Path):
    ledger_path = tmp_path / "qbridge.jsonl"
    bridge = QuantumNativeBridge(ledger_path)
    first = bridge.append(
        root={"circuit": "bell", "qubits": 2},
        template={"gates": ["H0", "CX01"], "measure": "z"},
        phase={"backend": "sim", "calibration": "demo-1"},
        observed={"00": 510, "11": 514},
        phase_angles=[0.1, 0.2, 0.15],
        metadata={"case": "bell-demo"},
    )
    second = bridge.append(
        root={"circuit": "phase-check", "qubits": 1},
        template={"gates": ["RZ"], "measure": "z"},
        phase={"backend": "sim", "calibration": "demo-2"},
        observed={"0": 700, "1": 324},
        phase_angles=[0.0, 0.05],
    )
    result = bridge.verify_chain()
    assert result["valid"] is True
    assert result["records"] == 2
    assert result["head_chain_hash"] == second.chain_hash
    assert first.sequence == 1
    assert second.sequence == 2


def test_tamper_is_detected(tmp_path: Path):
    ledger_path = tmp_path / "qbridge.jsonl"
    bridge = QuantumNativeBridge(ledger_path)
    bridge.append(root="r", template="t", phase="p", observed={"0": 10, "1": 5})
    record = json.loads(ledger_path.read_text(encoding="utf-8").splitlines()[0])
    record["metadata"]["tampered"] = True
    ledger_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(VerificationError):
        bridge.verify_chain()


def test_certificate_export(tmp_path: Path):
    bridge = QuantumNativeBridge(tmp_path / "qbridge.jsonl")
    bridge.append(root="payload", template="gate-path", phase="phase", observed=None)
    cert = bridge.export_certificate()
    assert cert["certificate_type"] == "QUANTUM_NATIVE_BRIDGE_PROOF"
    assert cert["verification"]["valid"] is True
    assert len(cert["certificate_hash"]) == 64


def test_measurement_metrics_recognition_when_observed_missing():
    root = "a" * 64
    template = "b" * 64
    phase = "c" * 64
    metrics = measurement_metrics(root, template, phase, None, [0.0, 0.0])
    assert metrics["classification"] == "RECOGNITION"
    assert metrics["recognized"] is True


def test_cli_roundtrip(tmp_path: Path):
    ledger_path = tmp_path / "cli-qbridge.jsonl"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "quantum_native_bridge_pro.cli",
            "append",
            "--ledger",
            str(ledger_path),
            "--root",
            '{"circuit":"bell"}',
            "--template",
            '{"gates":["H","CX"]}',
            "--phase",
            '{"backend":"sim"}',
            "--observed",
            '{"00":512,"11":512}',
            "--phase-angles",
            "[0.1,0.2]",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    out = subprocess.run(
        [sys.executable, "-m", "quantum_native_bridge_pro.cli", "verify", "--ledger", str(ledger_path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    result = json.loads(out)
    assert result["valid"] is True
    assert result["records"] == 1
