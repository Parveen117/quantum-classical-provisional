"""Local ideal calculations; never connects to a quantum service."""
import argparse
import json
from pathlib import Path

from .examples import bell, bernstein_vazirani, ghz, grover_11, order_memory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("program", choices=["bell", "ghz", "bv", "grover", "order-memory"])
    parser.add_argument("--compare-qiskit", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    circuit = {"bell": bell, "ghz": ghz, "bv": bernstein_vazirani,
               "grover": grover_11, "order-memory": order_memory}[args.program]()
    result = {
        "evidence_class": "LOCAL_IDEAL_CALCULATION",
        "program": args.program, "circuit_sha256": circuit.digest(),
        "probabilities": circuit.probabilities(), "hardware_job_id": None,
    }
    if args.compare_qiskit:
        from .qiskit_adapter import compare_qiskit, to_qiskit
        result["comparison"] = compare_qiskit(to_qiskit(circuit))
    text = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if args.compare_qiskit and not result["comparison"]["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
