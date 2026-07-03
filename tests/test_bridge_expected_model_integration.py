import json
import subprocess
import sys
from pathlib import Path

from quantum_native_bridge_pro import QuantumNativeBridge
from quantum_native_bridge_pro.expected_models import bell_model


def test_bridge_uses_expected_model_for_combined_classification(tmp_path: Path):
    ledger_path = tmp_path / "bridge-expected.jsonl"
    bridge = QuantumNativeBridge(ledger_path)
    record = bridge.append(
        root={"circuit": "bell_state", "qubits": 2},
        template={"expected_model": "bell_phi_plus", "gates": ["H q0", "CX q0 q1"], "tolerance": 0.08},
        phase={"backend": "test", "session": "expected-model"},
        observed={"00": 506, "01": 11, "10": 9, "11": 498},
        phase_angles=[0.1, 0.2, 0.15],
        expected_model=bell_model(tolerance=0.08),
    )
    assert record.recognition["expected_model_classification"] == "RECOGNITION"
    assert record.recognition["combined_runtime_classification"] == "RECOGNITION"
    assert record.recognition["classification"] == "RECOGNITION"
    verification = bridge.verify_chain()
    assert verification["recognized"] == 1
    assert verification["actionable_residue"] == 0
    assert verification["expected_model_counts"]["RECOGNITION"] == 1


def test_low_phase_coherence_downgrades_expected_recognition(tmp_path: Path):
    ledger_path = tmp_path / "bridge-low-phase.jsonl"
    bridge = QuantumNativeBridge(ledger_path)
    record = bridge.append(
        root={"circuit": "bell_state", "qubits": 2},
        template={"expected_model": "bell_phi_plus"},
        phase={"backend": "test", "session": "low-phase"},
        observed={"00": 506, "01": 11, "10": 9, "11": 498},
        phase_angles=[0.0, 3.14],
        expected_model=bell_model(tolerance=0.08),
    )
    assert record.recognition["expected_model_classification"] == "RECOGNITION"
    assert record.recognition["combined_runtime_classification"] == "ACTIONABLE_RESIDUE"


def test_cli_expected_model_append_roundtrip(tmp_path: Path):
    ledger_path = tmp_path / "cli-expected.jsonl"
    model_path = tmp_path / "bell-model.json"
    model_path.write_text(json.dumps(bell_model(tolerance=0.08).to_dict()), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "quantum_native_bridge_pro.cli",
            "append",
            "--ledger",
            str(ledger_path),
            "--root",
            '{"circuit":"bell_state","qubits":2}',
            "--template",
            '{"expected_model":"bell_phi_plus"}',
            "--phase",
            '{"backend":"cli-test"}',
            "--observed",
            '{"00":506,"01":11,"10":9,"11":498}',
            "--expected-model",
            str(model_path),
            "--phase-angles",
            "[0.1,0.2,0.15]",
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
    assert result["recognized"] == 1
    assert result["actionable_residue"] == 0
