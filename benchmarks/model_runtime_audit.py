"""Saved-model deployment qualification with exact device/QASM verification."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

assert sys.version_info[:2] == (3, 12), sys.version
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from native_relational_qc.circuit import Circuit
from native_relational_qc.learning_tasks import curvature_splits, xor_examples
from native_relational_qc.model_runtime import NATIVE_GATES, predict, verify_prediction
from native_relational_qc.phase_interop import phase_name
from native_relational_qc.self_learning import FIELD, digest, load_packet


def model(name):
    result = json.loads((ROOT / "native_relational_qc/learning" / name).read_text())
    load_packet(result)
    return result


def dense_readout(record):
    request = record["calculator_request"]
    program = Circuit(request["n_qubits"])
    for name, qs in request["operations"]:
        phase = phase_name(name)
        if phase is None:
            program.add(name, *qs)
        else:
            turns, controlled = phase
            assert not controlled
            matrix = np.diag([1, np.exp(2j * np.pi * float(turns))])
            program.append(matrix, qs, name)
    readout = record["mapping"]["final_layout"]["3"]
    return sum(abs(v) ** 2 for k, v in enumerate(program.state().amplitudes) if (k >> readout) & 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    line3 = json.loads((ROOT / "native_relational_qc/calculator_examples/three_wire_line.json").read_text())
    directed = dict(schema="nrqc-device-profile-v1", name="declared-software-four-wire-directed-line",
                    n_qubits=4, coupling_map=[[0, 1], [1, 2], [2, 3]],
                    native_gates=list(NATIVE_GATES), max_gates=1024)
    splits, _ = curvature_splits()
    blind, _ = curvature_splits(view="point_only")
    jobs = [("curvature_selected", model("structure_model.json"), splits["test"], line3),
            ("xor_legacy", model("xor_bits_model.json"), xor_examples(), None),
            ("point_only_legacy", model("point_only_model.json"), blind["test"], None),
            ("curvature_routed_legacy", model("first_layer_model.json"), splits["validation"], directed)]
    cache = {}
    rows, representatives, summaries = [], {}, {}
    max_error = 0.0
    total_basis_checks = 0
    for name, saved, examples, profile in jobs:
        correct = native_gates = 0
        for example in examples:
            key = digest(dict(model=saved, features=list(example.features), view=example.view, device=profile))
            reused = key in cache
            if not reused:
                result = predict(saved, example.features, view=example.view, profile=profile)
                assert verify_prediction(result)["status"] == "verified"
                probability = FIELD.from_dict(result["probability_one"])
                error = abs(complex(probability).real - dense_readout(result))
                assert error < 1e-12
                max_error = max(max_error, error)
                total_basis_checks += result["verification"]["basis_inputs_checked"]
                cache[key] = result
            result = cache[key]
            correct += result["predicted"] == example.target
            native_gates += result["resources"]["native_gates"]
            representatives.setdefault(name, result)
            rows.append(dict(task=name, example_id=example.name, features=list(example.features),
                             target=example.target, predicted=result["predicted"],
                             probability_one=result["probability_one"], fingerprint=result["fingerprint"],
                             reused_identical_program=reused, native_gates=result["resources"]["native_gates"]))
        summaries[name] = dict(examples=len(examples), correct=correct, native_gates=native_gates,
                               physical_wires=representatives[name]["calculator_request"]["n_qubits"])
        print(name, summaries[name], flush=True)
    assert summaries["curvature_selected"]["correct"] == 64
    assert summaries["xor_legacy"]["correct"] == 4
    assert summaries["point_only_legacy"]["correct"] == 32
    assert summaries["curvature_routed_legacy"]["correct"] == 4
    paths = ("native_relational_qc/model_runtime.py", "native_relational_qc/openqasm.py",
             "native_relational_qc/self_learning.py", "native_relational_qc/learning/structure_model.json",
             "native_relational_qc/calculator_examples/three_wire_line.json", "benchmarks/model_runtime_audit.py")
    report = dict(schema="nrqc-model-runtime-audit-v1", python=sys.version.split()[0],
                  summaries=summaries, cases=rows, representative_records=representatives,
                  unique_programs=len(cache), checked_basis_inputs=total_basis_checks,
                  exact_replay_per_program=True, maximum_numpy_probability_error=max_error,
                  source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
                  evidence_class="LOCAL_IDEAL_CALCULATION", hardware_jobs=0)
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(unique_programs=len(cache), checked_basis_inputs=total_basis_checks,
                          maximum_numpy_probability_error=max_error), indent=2))


if __name__ == "__main__":
    main()
