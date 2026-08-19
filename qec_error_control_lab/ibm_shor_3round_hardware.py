"""Three-round IBM Shor syndrome acquisition and evidence collector.

The hardware circuit performs three syndrome-extraction rounds per shot.  The
same eight ancillas are measured and reset between rounds.  No conditional
recovery is applied on hardware in this protocol.

Submission uses Qiskit Runtime account discovery only.  Tokens are never
accepted as command-line arguments or written to receipts.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROTOCOL = "bounded-shor-three-round-hardware-syndrome-v1"
BACKEND = "ibm_marrakesh"
SHOTS = 4096
ROUNDS = 3
SEED_TRANSPILER = 20260819
EXPECTED = {
    "no_error": "00000000",
    "x_q0": "00000001",
    "z_q0": "01000000",
    "y_q4": "11001100",
}
ERRORS = {
    "no_error": None,
    "x_q0": (0, "X"),
    "z_q0": (0, "Z"),
    "y_q4": (4, "Y"),
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def protocol_specification() -> dict[str, Any]:
    body = {
        "protocol": PROTOCOL,
        "backend": BACKEND,
        "shots_per_case": SHOTS,
        "rounds_per_shot": ROUNDS,
        "cases": [
            {"label": label, "injected_error": ERRORS[label], "expected_syndrome": EXPECTED[label]}
            for label in EXPECTED
        ],
        "ancilla_policy": "measure all 8 ancillas after each round; reset after rounds 0 and 1",
        "hardware_recovery": False,
        "decision_rule": (
            "Evidence PASS requires the predeclared syndrome to be the unique mode in each "
            "round and the unique mode of the exact-report majority ledger for all four cases."
        ),
        "claim_boundary": (
            "Three repeated non-fault-tolerant extraction rounds on one backend epoch; "
            "no hardware recovery, threshold, or fault-tolerance claim."
        ),
    }
    return {**body, "spec_sha256": sha256_json(body)}


def materialize_case(label: str):
    """Build one untranspiled 17-qubit dynamic circuit."""
    if label not in EXPECTED:
        raise ValueError(f"unknown case {label!r}")
    try:
        from qiskit import ClassicalRegister, QuantumCircuit, QuantumRegister
    except ImportError as exc:
        raise RuntimeError("install requirements-qiskit.txt before hardware submission") from exc
    from qec_circuit_spec import (
        DATA_QUBITS,
        SYNDROME_QUBITS,
        shor_encoding_operations,
        shor_syndrome_operations,
    )

    data = QuantumRegister(DATA_QUBITS, "data")
    ancilla = QuantumRegister(SYNDROME_QUBITS, "syndrome_ancilla")
    round_bits = [ClassicalRegister(SYNDROME_QUBITS, f"syndrome_r{r}") for r in range(ROUNDS)]
    data_bits = ClassicalRegister(DATA_QUBITS, "data_readout")
    circuit = QuantumCircuit(data, ancilla, *round_bits, data_bits, name=f"{PROTOCOL}:{label}")
    circuit.metadata = {
        "protocol": PROTOCOL,
        "case": label,
        "expected_syndrome": EXPECTED[label],
        "rounds": ROUNDS,
        "hardware_recovery": False,
    }

    def qref(index: int):
        return data[index] if index < DATA_QUBITS else ancilla[index - DATA_QUBITS]

    def apply_operations(operations) -> None:
        for operation in operations:
            if operation.gate == "h":
                circuit.h(qref(operation.qubits[0]))
            elif operation.gate == "cx":
                circuit.cx(qref(operation.qubits[0]), qref(operation.qubits[1]))
            else:
                raise ValueError(f"unsupported operation {operation.gate!r}")

    apply_operations(shor_encoding_operations())
    error = ERRORS[label]
    if error is not None:
        qubit, pauli = error
        getattr(circuit, pauli.lower())(data[qubit])

    for round_index in range(ROUNDS):
        apply_operations(shor_syndrome_operations())
        circuit.measure(ancilla, round_bits[round_index])
        if round_index < ROUNDS - 1:
            circuit.reset(ancilla)
            circuit.barrier(data, ancilla)
    circuit.measure(data, data_bits)
    return circuit


def measurement_map_for_register(circuit, register_name: str) -> dict[str, int]:
    """Read physical measured-qubit indices from an ISA circuit."""
    mapping: dict[str, int] = {}
    for instruction in circuit.data:
        if instruction.operation.name not in {"measure", "measure_2"} or not instruction.clbits:
            continue
        clbit_location = circuit.find_bit(instruction.clbits[0])
        for register, index in clbit_location.registers:
            if register.name == register_name:
                mapping[str(index)] = int(circuit.find_bit(instruction.qubits[0]).index)
    if set(mapping) != {str(i) for i in range(8)}:
        raise ValueError(f"could not recover complete 8-stabilizer map for {register_name}")
    return {str(i): mapping[str(i)] for i in range(8)}


def _backend_name(backend) -> str:
    name = getattr(backend, "name", BACKEND)
    return str(name() if callable(name) else name)


def _status_name(job) -> str:
    value = job.status()
    return str(getattr(value, "name", value)).upper()


def submit_job(*, backend_name: str = BACKEND, shots: int = SHOTS, instance: str = "auto") -> dict[str, Any]:
    if shots != SHOTS:
        raise ValueError("v1 predeclares exactly 4096 shots per case")
    try:
        from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
    except ImportError as exc:
        raise RuntimeError("install requirements-qiskit.txt before hardware submission") from exc

    service = QiskitRuntimeService(instance=instance)
    backend = service.backend(backend_name)
    circuits = [materialize_case(label) for label in EXPECTED]
    manager = generate_preset_pass_manager(
        backend=backend, optimization_level=1, seed_transpiler=SEED_TRANSPILER
    )
    isa_circuits = [manager.run(circuit) for circuit in circuits]
    layouts: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    for label, circuit in zip(EXPECTED, isa_circuits):
        layouts[label] = {
            f"syndrome_r{r}": measurement_map_for_register(circuit, f"syndrome_r{r}")
            for r in range(ROUNDS)
        }
        metrics[label] = {
            "depth": int(circuit.depth()),
            "size": int(circuit.size()),
            "count_ops": {str(k): int(v) for k, v in circuit.count_ops().items()},
        }

    sampler = SamplerV2(mode=backend)
    job = sampler.run(isa_circuits, shots=shots)
    job_id = job.job_id()
    receipt = {
        "schema": "ibm-shor-three-round-submission-v1",
        "job_id": job_id,
        "backend": _backend_name(backend),
        "status": _status_name(job),
        "shots_per_case": shots,
        "cases": list(EXPECTED),
        "protocol": PROTOCOL,
        "protocol_spec_sha256": protocol_specification()["spec_sha256"],
        "seed_transpiler": SEED_TRANSPILER,
        "round_ancilla_maps": layouts,
        "transpiled_metrics": metrics,
        "credential_material_recorded": False,
    }
    receipt["receipt_sha256"] = sha256_json(receipt)
    return receipt


def modes(counts: Mapping[str, int]) -> list[str]:
    peak = max(counts.values())
    return sorted(key for key, value in counts.items() if value == peak)


def bit_accuracy(bits: str, expected: str) -> float:
    if len(bits) != len(expected):
        raise ValueError("syndrome width mismatch")
    return sum(a == b for a, b in zip(bits, expected)) / len(expected)


def exact_report_majority(reports: Sequence[str]) -> str | None:
    if len(reports) != 3:
        raise ValueError("exactly three reports are required")
    counts = Counter(reports)
    report, count = counts.most_common(1)[0]
    return report if count >= 2 else None


def analyse_case(
    label: str,
    round_bitstrings: Sequence[Sequence[str]],
    data_bitstrings: Sequence[str] | None = None,
) -> dict[str, Any]:
    if label not in EXPECTED or len(round_bitstrings) != ROUNDS:
        raise ValueError("unknown case or wrong round count")
    shots = len(round_bitstrings[0])
    if shots == 0 or any(len(rounds) != shots for rounds in round_bitstrings):
        raise ValueError("round shot arrays must be non-empty and equal length")
    expected = EXPECTED[label]
    per_round = []
    for index, samples in enumerate(round_bitstrings):
        counts = dict(sorted(Counter(samples).items()))
        modal = modes(counts)
        per_round.append({
            "round": index,
            "counts": counts,
            "modal_syndromes": modal,
            "expected_is_unique_mode": modal == [expected],
            "expected_rate": counts.get(expected, 0) / shots,
            "mean_bit_accuracy": sum(bit_accuracy(bits, expected) for bits in samples) / shots,
        })

    majorities = [exact_report_majority(tuple(round_bitstrings[r][i] for r in range(ROUNDS))) for i in range(shots)]
    majority_counts = Counter(value if value is not None else "<DEFERRED>" for value in majorities)
    nondeferred = {k: v for k, v in majority_counts.items() if k != "<DEFERRED>"}
    majority_modes = modes(nondeferred) if nondeferred else []
    stable = sum(
        round_bitstrings[0][i] == round_bitstrings[1][i] == round_bitstrings[2][i]
        for i in range(shots)
    )

    def mean_hamming(a: Sequence[str], b: Sequence[str]) -> float:
        return sum(sum(x != y for x, y in zip(left, right)) / 8 for left, right in zip(a, b)) / shots

    return {
        "label": label,
        "expected_syndrome": expected,
        "shots": shots,
        "per_round": per_round,
        "majority_ledger": {
            "counts": dict(sorted(majority_counts.items())),
            "modal_syndromes_excluding_deferred": majority_modes,
            "expected_is_unique_mode": majority_modes == [expected],
            "expected_rate": majority_counts.get(expected, 0) / shots,
            "deferred_rate": majority_counts.get("<DEFERRED>", 0) / shots,
        },
        "round_stability": {
            "all_three_identical_rate": stable / shots,
            "mean_normalized_hamming_r0_r1": mean_hamming(round_bitstrings[0], round_bitstrings[1]),
            "mean_normalized_hamming_r1_r2": mean_hamming(round_bitstrings[1], round_bitstrings[2]),
        },
        "data_readout_counts": dict(sorted(Counter(data_bitstrings or []).items())),
    }


def build_certificate(
    *, job_id: str, backend: str, cases: Sequence[Mapping[str, Any]], submission_receipt_sha256: str
) -> dict[str, Any]:
    checks = {
        "four_cases_present": [case["label"] for case in cases] == list(EXPECTED),
        "shots_4096_each": all(case["shots"] == SHOTS for case in cases),
        "expected_unique_mode_every_round": all(
            row["expected_is_unique_mode"] for case in cases for row in case["per_round"]
        ),
        "expected_unique_mode_majority_ledger": all(
            case["majority_ledger"]["expected_is_unique_mode"] for case in cases
        ),
        "no_hardware_recovery": True,
    }
    body = {
        "protocol": PROTOCOL,
        "job_id": job_id,
        "backend": backend,
        "shots_per_case": SHOTS,
        "rounds_per_shot": ROUNDS,
        "hardware_recovery": False,
        "submission_receipt_sha256": submission_receipt_sha256,
        "protocol_spec_sha256": protocol_specification()["spec_sha256"],
        "cases": list(cases),
        "checks": checks,
        "classification": (
            "PASS_BOUNDED_SHOR_3ROUND_HARDWARE_SYNDROME_V1"
            if all(checks.values())
            else "FAIL_BOUNDED_SHOR_3ROUND_HARDWARE_SYNDROME_V1"
        ),
        "claim_boundary": (
            "Three extraction rounds with mid-circuit ancilla measurement/reset, no hardware "
            "recovery. One backend epoch; not fault tolerance or a threshold result."
        ),
    }
    body["certificate_sha256"] = sha256_json(body)
    return body


def _bitstrings(pub_data, register_name: str) -> list[str]:
    register = getattr(pub_data, register_name)
    return list(register.get_bitstrings())


def collect_job(job_id: str, receipt: Mapping[str, Any], *, instance: str = "auto") -> tuple[dict[str, Any] | None, str]:
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
    except ImportError as exc:
        raise RuntimeError("install requirements-qiskit.txt before collection") from exc
    service = QiskitRuntimeService(instance=instance)
    job = service.job(job_id)
    status = _status_name(job)
    if status != "DONE":
        return None, status
    result = job.result()
    if len(result) != len(EXPECTED):
        raise ValueError("result pub count differs from four-case contract")
    cases = []
    for label, pub in zip(EXPECTED, result):
        rounds = [_bitstrings(pub.data, f"syndrome_r{r}") for r in range(ROUNDS)]
        data = _bitstrings(pub.data, "data_readout")
        cases.append(analyse_case(label, rounds, data))
    certificate = build_certificate(
        job_id=job_id,
        backend=str(receipt["backend"]),
        cases=cases,
        submission_receipt_sha256=str(receipt["receipt_sha256"]),
    )
    return certificate, status


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("spec")
    submit = sub.add_parser("submit")
    submit.add_argument("--instance", default="auto")
    collect = sub.add_parser("collect")
    collect.add_argument("job_id")
    collect.add_argument("--instance", default="auto")
    collect.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    evidence = Path(__file__).resolve().parent / "hardware_evidence"

    if args.command == "spec":
        print(json.dumps(protocol_specification(), indent=2, sort_keys=True))
        return 0
    if args.command == "submit":
        receipt = submit_job(instance=args.instance)
        path = evidence / f"ibm_shor_3round_submission_{receipt['job_id']}.json"
        write_json(path, receipt)
        print(f"JOB ID : {receipt['job_id']}")
        print(f"STATUS : {receipt['status']}")
        print(f"RECEIPT: {path}")
        return 0

    receipt_path = args.receipt or evidence / f"ibm_shor_3round_submission_{args.job_id}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    certificate, status = collect_job(args.job_id, receipt, instance=args.instance)
    receipt = {**receipt, "status": status}
    write_json(receipt_path, receipt)
    if certificate is None:
        print(f"STATUS : {status}")
        return 2
    cert_path = evidence / f"{args.job_id}_3round_hardware_certificate.json"
    write_json(cert_path, certificate)
    print(f"STATUS        : {status}")
    print(f"CLASSIFICATION: {certificate['classification']}")
    print(f"SHA256        : {certificate['certificate_sha256']}")
    print(f"SAVED         : {cert_path}")
    return 0 if certificate["classification"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
