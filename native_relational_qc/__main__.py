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
    if argv and argv[0] == 'certify':
        from .certify import main as certify_main
        return certify_main(argv[1:])
    if argv and argv[0] == 'check':
        from .check import main as check_main
        return check_main(argv[1:])
    if argv and argv[0] == 'synthesize':
        from .circuit_synthesis import main as synthesis_main
        return synthesis_main(argv[1:])
    if argv and argv[0] == 'learn-structure':
        from .structure_learning import main as structure_main
        return structure_main(argv[1:])
    if argv and argv[0] in ('predict', 'verify-prediction'):
        from .model_runtime import main as model_main
        return model_main(argv[1:], replay=argv[0] == 'verify-prediction')
    if argv and argv[0] == 'observer-track':
        from .observer_tracking import main as tracking_main
        return tracking_main(argv[1:])
    if argv and argv[0] == 'observer-state':
        from .observer_state import main as state_main
        return state_main(argv[1:])
    if argv and argv[0] == 'observer-cycle':
        from .observer_cycle import main as cycle_main
        return cycle_main(argv[1:])
    parser = argparse.ArgumentParser(prog='nrqc', description=__doc__, epilog=
        'Custom exact circuits: nrqc calculate INPUT.json --out RESULT.json; '
        'backend acceptance report: nrqc check INPUT.json (or nrqc check --table); '
        'goal-directed exact circuit construction: nrqc synthesize GOAL.json; '
        'train native phases and search topology: nrqc learn-structure --task curvature; '
        'use a saved model: nrqc predict MODEL.json --features A B --view first_layer; '
        'photonic model arithmetic: nrqc certify; '
        'record-controlled next measurement: nrqc observer-track --records 0101; '
        'joint contrast/phase prediction: nrqc observer-state --records 0101; '
        'exact source return and retained history: nrqc observer-cycle')
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
