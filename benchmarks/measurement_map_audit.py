"""Exhaustive readout-map permutations over two synthetic physical histograms."""
import argparse
import hashlib
from itertools import permutations
import json
from pathlib import Path
import sys

import numpy as np

assert sys.version_info[:2] == (3, 12), sys.version
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.model_experiment_audit import acquisition_for, binding_for
from native_relational_qc.circuit import Circuit
from native_relational_qc.model_experiment import experiment_plan, observe, verify_observation
from native_relational_qc.model_runtime import NATIVE_GATES, predict
from native_relational_qc.phase_interop import phase_name
from native_relational_qc.self_learning import packet


def dense_probabilities(prediction):
    request = prediction["calculator_request"]
    circuit = Circuit(request["n_qubits"])
    for name, qubits in request["operations"]:
        phase = phase_name(name)
        if phase is None:
            circuit.add(name, *qubits)
        else:
            turns, controlled = phase
            assert not controlled
            circuit.append(np.diag([1, np.exp(2j * np.pi * float(turns))]), qubits, name)
    return np.abs(circuit.state().amplitudes) ** 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    learning = ROOT / "native_relational_qc/learning"
    selected = json.loads((learning / "structure_model.json").read_text())
    # Explicit arbitrary native phases and a topology that changes the routed
    # final layout. This is a software fixture, not another trained checkpoint.
    routed_model = packet((3, 41, 22, 9, 50), training_digest="a" * 64,
                          view="first_layer", entanglers=((1, 2), (2, 3), (0, 2)))
    line = json.loads((ROOT / "native_relational_qc/calculator_examples/three_wire_line.json").read_text())
    routed = dict(schema="nrqc-device-profile-v1", name="synthetic-directed-four-wire-routing",
                  n_qubits=4, coupling_map=[[0, 1], [1, 2], [2, 3]],
                  native_gates=list(NATIVE_GATES), max_gates=1024)
    predictions = [predict(saved, (5, 17), view="first_layer", profile=profile)
                   for saved, profile in ((selected, line), (routed_model, routed))]
    assert predictions[1]["mapping"]["initial_layout"] != predictions[1]["mapping"]["final_layout"]
    rng = np.random.default_rng(20261114)
    cases, histograms = [], []
    for group, prediction in enumerate(predictions):
        probabilities = dense_probabilities(prediction)
        normalization_error = abs(float(sum(probabilities)) - 1)
        assert normalization_error < 1e-12
        probabilities /= sum(probabilities)
        full_counts = rng.multinomial(512, probabilities)
        readout = prediction["mapping"]["final_layout"]["3"]
        expected_one = sum(int(count) for ket, count in enumerate(full_counts) if (ket >> readout) & 1)
        histograms.append(dict(physical_wires=prediction["device"]["n_qubits"],
                               prediction_fingerprint=prediction["fingerprint"],
                               full_counts=[int(v) for v in full_counts], expected_count_one=expected_one,
                               numpy_normalization_error=normalization_error,
                               initial_layout=prediction["mapping"]["initial_layout"],
                               final_layout=prediction["mapping"]["final_layout"]))
        error = None
        width = prediction["device"]["n_qubits"]
        for measured in range(1, width + 1):
            for wires in permutations(range(width), measured):
                if readout not in wires:
                    continue
                counts = {}
                for ket, count in enumerate(full_counts):
                    if not count:
                        continue
                    key = "".join(str((ket >> q) & 1) for q in reversed(wires))
                    counts[key] = counts.get(key, 0) + int(count)
                plan = experiment_plan(prediction, binding_for(prediction), run_id=f"map-{len(cases)}",
                                       shots=512, tolerance=dict(numerator=1, denominator=8),
                                       measure_wires=list(wires))
                report = observe(plan, acquisition_for(plan, counts, f"map-{len(cases)}"))
                assert report["marginal_counts"] == {"0": 512 - expected_one, "1": expected_one}
                assert verify_observation(report)["status"] == "verified"
                if error is None:
                    error = report["absolute_error"]
                assert error == report["absolute_error"]
                cases.append(dict(histogram=group, measured_wires=list(wires),
                                  readout_classical_bit=plan["readout_classical_bit"], counts=counts,
                                  marginal_counts=report["marginal_counts"], classification=report["classification"],
                                  observation_fingerprint=report["fingerprint"], plan_fingerprint=plan["fingerprint"]))
    assert len(cases) == 60
    paths = ("native_relational_qc/model_experiment.py", "native_relational_qc/model_runtime.py",
             "native_relational_qc/circuit.py", "benchmarks/measurement_map_audit.py")
    document = dict(schema="nrqc-measurement-map-audit-v1", python=sys.version.split()[0],
                    measurement_maps=len(cases), source_histograms=histograms, cases=cases,
                    sampling=dict(seed=20261114, shots_per_source_histogram=512,
                                  reuse="all maps within a group project the same synthetic full-register histogram"),
                    exact_replay_per_map=True,
                    source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
                    evidence_class="SYNTHETIC_MEASUREMENT_MAP_QUALIFICATION", hardware_submissions=0)
    args.out.write_text(json.dumps(document, sort_keys=True, indent=2) + "\n")
    print(json.dumps(dict(measurement_maps=len(cases), source_histograms=len(histograms),
                          nonidentity_routing_checked=True, hardware_submissions=0)))


if __name__ == "__main__":
    main()
