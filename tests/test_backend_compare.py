import json
import subprocess
import sys
from pathlib import Path

from quantum_native_bridge_pro.backend_compare import BackendObservation, compare_backends, load_observations
from quantum_native_bridge_pro.expected_models import bell_model


def test_backend_consensus_recognition():
    report = compare_backends(
        bell_model(tolerance=0.08),
        [
            BackendObservation("sim-a", {"00": 506, "01": 11, "10": 9, "11": 498}),
            BackendObservation("sim-b", {"00": 511, "01": 8, "10": 10, "11": 495}),
        ],
    )
    assert report.classification == "BACKEND_CONSENSUS_RECOGNITION"
    assert report.recognized_backends == 2
    assert report.actionable_backends == 0
    assert report.max_backend_gap < 0.08


def test_backend_actionable_divergence_when_one_backend_bad():
    report = compare_backends(
        bell_model(tolerance=0.08),
        [
            BackendObservation("good", {"00": 506, "01": 11, "10": 9, "11": 498}),
            BackendObservation("bad", {"00": 250, "01": 250, "10": 250, "11": 274}),
        ],
    )
    assert report.classification == "BACKEND_ACTIONABLE_DIVERGENCE"
    assert report.actionable_backends == 1


def test_load_observations(tmp_path: Path):
    path = tmp_path / "observations.json"
    path.write_text(json.dumps({"observations": [{"backend_id": "a", "observed_counts": {"00": 1, "11": 1}}]}), encoding="utf-8")
    observations = load_observations(path)
    assert observations[0].backend_id == "a"
    assert observations[0].observed_counts["00"] == 1


def test_backend_compare_cli(tmp_path: Path):
    model_path = tmp_path / "model.json"
    obs_path = tmp_path / "obs.json"
    out_path = tmp_path / "report.json"
    model_path.write_text(json.dumps(bell_model(tolerance=0.08).to_dict()), encoding="utf-8")
    obs_path.write_text(
        json.dumps(
            {
                "observations": [
                    {"backend_id": "sim-a", "observed_counts": {"00": 506, "01": 11, "10": 9, "11": 498}},
                    {"backend_id": "sim-b", "observed_counts": {"00": 511, "01": 8, "10": 10, "11": 495}},
                ]
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, "-m", "quantum_native_bridge_pro.backend_compare", "--model", str(model_path), "--observations", str(obs_path), "--out", str(out_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["classification"] == "BACKEND_CONSENSUS_RECOGNITION"
