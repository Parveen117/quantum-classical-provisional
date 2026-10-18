"""Local ideal calculations; never connects to a quantum service."""
import argparse
import json
import sys
from pathlib import Path

from .examples import bell, bernstein_vazirani, ghz, grover_11, order_memory


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'calculate':
        from .calculator import main as calculator_main
        return calculator_main(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__, epilog=
        'Custom exact circuits: python -m native_relational_qc calculate INPUT.json --out RESULT.json')
    parser.add_argument("program", choices=["bell", "ghz", "bv", "grover", "order-memory"])
    parser.add_argument("--compare-qiskit", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
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
