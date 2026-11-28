"""Reproduce the bounded circuit-maker application using Python 3.12."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

assert sys.version_info[:2] == (3, 12), sys.version
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from native_relational_qc.circuit import Circuit
from native_relational_qc.circuit_synthesis import synthesize
from native_relational_qc.modular_rewrite import verify_rewrite
from native_relational_qc.phase_backend import PowerPhaseCircuit


def ghz_goal(n, sign=1):
    return dict(schema="nrqc-circuit-goal-v1", n_qubits=n,
                allowed_gates=["h", "x", "z", "cx"],
                coupling_map=[[q, q + 1] for q in range(n - 1)],
                stabilizers=[dict(paulis={str(q): "X" for q in range(n)}, eigenvalue=sign)] +
                [dict(paulis={str(q): "Z", str(q + 1): "Z"}, eigenvalue=1)
                 for q in range(n - 1)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    cases = []
    for name, n, sign in (("bell_plus", 2, 1), ("bell_minus", 2, -1),
                          ("ghz_three", 3, 1), ("ghz_four", 4, 1)):
        goal = ghz_goal(n, sign)
        result = synthesize(goal)
        assert result["status"] == "verified", result
        circuit = Circuit(n)
        for gate, qs in result["calculator_request"]["operations"]:
            circuit.add(gate, *qs)
        target = np.zeros(2 ** n, dtype=complex)
        target[0], target[-1] = 1 / np.sqrt(2), sign / np.sqrt(2)
        actual = circuit.state().amplitudes
        # Only an overall phase can vary for this state-preparation goal.
        phase = actual[0] / target[0]
        error = float(np.max(np.abs(actual - phase * target)))
        assert error < 1e-12 and abs(abs(phase) - 1) < 1e-12
        for item in result["rewrite_examples"]:
            circuits = []
            for key in ("source", "result"):
                c = PowerPhaseCircuit(n, 8)
                for gate, qs in item[key]:
                    c.add(gate, *qs)
                circuits.append(c)
            assert verify_rewrite(*circuits, item["certificate"])["status"] == "verified"
        cases.append(dict(name=name, numpy_max_amplitude_error=error, result=result))
    negative = copy.deepcopy(ghz_goal(2))
    negative["allowed_gates"] = ["x", "z", "cx"]
    rejected = synthesize(negative)
    assert rejected["status"] == "search_exhausted" and rejected["calculator_request"] is None
    report = dict(schema="nrqc-panini-synthesis-audit-v1", python=sys.version.split()[0],
                  evidence_class="LOCAL_IDEAL_CALCULATION", cases=cases,
                  no_superposition_gate_control=rejected,
                  source_sha256={name: hashlib.sha256(
                      (Path(__file__).resolve().parents[1] / name).read_bytes()).hexdigest()
                      for name in ("native_relational_qc/circuit_synthesis.py",
                                   "native_relational_qc/modular_rewrite.py",
                                   "native_relational_qc/phase_backend.py",
                                   "benchmarks/panini_synthesis_audit.py")})
    rendered = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(json.dumps(dict(cases=[dict(name=c["name"], gates=len(c["result"]["calculator_request"]["operations"]),
                                    resources=c["result"]["resources"],
                                    numpy_max_amplitude_error=c["numpy_max_amplitude_error"])
                               for c in cases], negative_control=rejected["status"]), indent=2))


if __name__ == "__main__":
    main()
