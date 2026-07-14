#!/usr/bin/env python3
r"""IBM Quantum benchmark for decomposable operator-order memory.

The benchmark uses three independent RK/KR interferometers. Each interferometer
writes an operator-order phase into a separate ledger qubit while its visible
target state is identical up to global phase. The ledgers are projected into a
single readout through predeclared, distinguishable weights. Selective reset
controls test whether each ledger causally contributes to the projection.

Jupyter:
    %run r"C:\Users\abc\Desktop\New Folder (2)\New folder\PROVISNAL RELATED\Quantum classical\run_multi_ledger_operator_memory_test.py"

Optional environment variables:
    IBM_QUANTUM_BACKEND
    IBM_QUANTUM_SHOTS          default 4096
    IBM_QUANTUM_CHANNEL        default ibm_quantum_platform
    IBM_QUANTUM_INSTANCE
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Sequence

try:
    from qiskit import QuantumCircuit, transpile
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
except ImportError as exc:
    raise SystemExit(
        "Missing dependencies. Install with: pip install qiskit qiskit-ibm-runtime"
    ) from exc

ROOT = Path(__file__).resolve().parent
STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = ROOT / "multi_ledger_operator_memory_v1" / "runs" / STAMP
SHOTS = int(os.getenv("IBM_QUANTUM_SHOTS", "4096"))
BACKEND_NAME = os.getenv("IBM_QUANTUM_BACKEND", "").strip()
CHANNEL = os.getenv("IBM_QUANTUM_CHANNEL", "ibm_quantum_platform").strip()
INSTANCE = os.getenv("IBM_QUANTUM_INSTANCE", "").strip() or None
SEEDS = (11, 29, 47)

TARGETS = (0, 1, 2)
LEDGERS = (3, 4, 5)
READOUT = 6

# These are declared readout weights, not physical constants. They sum to pi,
# so an ideal three-ledger write produces P(readout=1)=1 while each selective
# reset produces a distinct lower probability.
PROJECTION_WEIGHTS = (3.0 * math.pi / 10.0, math.pi / 3.0, 11.0 * math.pi / 30.0)

MODES = (
    "full_memory",
    "erase_m1",
    "erase_m2",
    "erase_m3",
    "erase_all",
    "projection_erased",
    "single_m1",
    "single_m2",
    "single_m3",
    "commuting_control",
    "order_erased_control",
)

PROJECTION_ACTIVE_MODES = tuple(mode for mode in MODES if mode != "projection_erased")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_backend(service: QiskitRuntimeService):
    if BACKEND_NAME:
        return service.backend(BACKEND_NAME)
    candidates = [
        backend
        for backend in service.backends(simulator=False, operational=True)
        if getattr(backend.configuration(), "n_qubits", 0) >= 7
    ]
    if not candidates:
        raise RuntimeError("No operational IBM backend with at least 7 qubits is available.")
    return min(candidates, key=lambda backend: backend.status().pending_jobs)


def counts_from_pub_result(pub_result: Any) -> dict[str, int]:
    data = pub_result.data
    for name in ("c", "meas"):
        register = getattr(data, name, None)
        if register is not None and hasattr(register, "get_counts"):
            return dict(register.get_counts())
    for value in vars(data).values():
        if hasattr(value, "get_counts"):
            return dict(value.get_counts())
    raise RuntimeError("Could not locate measurement counts in Sampler result.")


def normalized_bits(bits: str) -> str:
    compact = bits.replace(" ", "")
    if len(compact) != 7:
        raise ValueError(f"Expected a 7-bit result, received {bits!r}")
    return compact


def classical_bit_value(bits: str, classical_bit: int) -> int:
    return int(normalized_bits(bits)[6 - classical_bit])


def bit_probability(counts: dict[str, int], classical_bit: int) -> float:
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    return sum(
        count
        for bits, count in counts.items()
        if classical_bit_value(bits, classical_bit) == 1
    ) / total


def ledger_distribution(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    distribution = {f"{value:03b}": 0.0 for value in range(8)}
    if total <= 0:
        return distribution
    for bits, count in counts.items():
        pattern = "".join(str(classical_bit_value(bits, ledger)) for ledger in LEDGERS)
        distribution[pattern] += count / total
    return distribution


def visible_distribution(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    distribution = {f"{value:03b}": 0.0 for value in range(8)}
    if total <= 0:
        return distribution
    for bits, count in counts.items():
        pattern = "".join(str(classical_bit_value(bits, target)) for target in TARGETS)
        distribution[pattern] += count / total
    return distribution


def total_variation_distance(left: dict[str, float], right: dict[str, float]) -> float:
    keys = set(left) | set(right)
    return 0.5 * sum(abs(left.get(key, 0.0) - right.get(key, 0.0)) for key in keys)


def apply_branch_x(qc: QuantumCircuit, control: int, target: int, branch: int) -> None:
    if branch == 0:
        qc.x(control)
    qc.cx(control, target)
    if branch == 0:
        qc.x(control)


def apply_branch_z(qc: QuantumCircuit, control: int, target: int, branch: int) -> None:
    if branch == 0:
        qc.x(control)
    qc.cz(control, target)
    if branch == 0:
        qc.x(control)


def write_order_ledger(qc: QuantumCircuit, ledger: int, target: int, kind: str) -> None:
    """Interfere two operator histories and store their relative phase in ledger."""
    if kind == "disabled":
        return

    qc.h(ledger)

    if kind == "anticommuting":
        # Branch 0: R then K. Branch 1: K then R, with R=X and K=Z.
        # Because RK=-KR, the visible target agrees up to global phase and the
        # relative sign is converted into ledger |1> by the final Hadamard.
        apply_branch_x(qc, ledger, target, 0)
        apply_branch_z(qc, ledger, target, 1)
        apply_branch_z(qc, ledger, target, 0)
        apply_branch_x(qc, ledger, target, 1)
    elif kind == "commuting":
        # Both histories consist of two X operations, so no order phase exists.
        apply_branch_x(qc, ledger, target, 0)
        apply_branch_x(qc, ledger, target, 1)
        apply_branch_x(qc, ledger, target, 0)
        apply_branch_x(qc, ledger, target, 1)
    elif kind == "order_erased":
        # Both branches receive the same R-then-K history.
        apply_branch_x(qc, ledger, target, 0)
        apply_branch_x(qc, ledger, target, 1)
        apply_branch_z(qc, ledger, target, 0)
        apply_branch_z(qc, ledger, target, 1)
    else:
        raise ValueError(f"Unknown ledger kind: {kind}")

    qc.h(ledger)


def initialise_targets(qc: QuantumCircuit) -> None:
    qc.h(TARGETS[0])
    qc.ry(0.43, TARGETS[1])
    qc.h(TARGETS[2])
    qc.rz(0.27, TARGETS[2])


def mode_ledger_kinds(mode: str) -> tuple[str, str, str]:
    if mode in {
        "full_memory",
        "erase_m1",
        "erase_m2",
        "erase_m3",
        "erase_all",
        "projection_erased",
    }:
        return ("anticommuting", "anticommuting", "anticommuting")
    if mode == "single_m1":
        return ("anticommuting", "disabled", "disabled")
    if mode == "single_m2":
        return ("disabled", "anticommuting", "disabled")
    if mode == "single_m3":
        return ("disabled", "disabled", "anticommuting")
    if mode == "commuting_control":
        return ("commuting", "commuting", "commuting")
    if mode == "order_erased_control":
        return ("order_erased", "order_erased", "order_erased")
    raise ValueError(f"Unknown mode: {mode}")


def build_memory_circuit(mode: str) -> QuantumCircuit:
    qc = QuantumCircuit(7, 7, name=mode)
    initialise_targets(qc)

    for target, ledger, kind in zip(TARGETS, LEDGERS, mode_ledger_kinds(mode)):
        write_order_ledger(qc, ledger, target, kind)

    if mode == "erase_m1":
        qc.reset(LEDGERS[0])
    elif mode == "erase_m2":
        qc.reset(LEDGERS[1])
    elif mode == "erase_m3":
        qc.reset(LEDGERS[2])
    elif mode == "erase_all":
        for ledger in LEDGERS:
            qc.reset(ledger)

    if mode != "projection_erased":
        for ledger, weight in zip(LEDGERS, PROJECTION_WEIGHTS):
            qc.cry(weight, ledger, READOUT)

    qc.measure(range(7), range(7))
    return qc


def build_visible_order_circuit(order: str) -> QuantumCircuit:
    qc = QuantumCircuit(7, 7, name=f"visible_{order}")
    initialise_targets(qc)
    for target in TARGETS:
        if order == "rk":
            qc.x(target)
            qc.z(target)
        elif order == "kr":
            qc.z(target)
            qc.x(target)
        else:
            raise ValueError(f"Unknown visible order: {order}")
    qc.measure(range(7), range(7))
    return qc


def projection_probability(pattern: str, active_indices: Iterable[int]) -> float:
    active = set(active_indices)
    angle = sum(
        PROJECTION_WEIGHTS[index]
        for index, bit in enumerate(pattern)
        if index in active and bit == "1"
    )
    return math.sin(angle / 2.0) ** 2


def predict_from_distribution(
    distribution: dict[str, float], active_indices: Sequence[int]
) -> float:
    return sum(
        probability * projection_probability(pattern, active_indices)
        for pattern, probability in distribution.items()
    )


def mean_absolute_error(observed: Sequence[float], predicted: Sequence[float]) -> float:
    if len(observed) != len(predicted):
        raise ValueError("Observed and predicted lengths differ.")
    if not observed:
        return 0.0
    return mean(abs(left - right) for left, right in zip(observed, predicted))


def ideal_reset_readout_probabilities() -> dict[str, float]:
    full = math.sin(sum(PROJECTION_WEIGHTS) / 2.0) ** 2
    return {
        "full_memory": full,
        "erase_m1": math.sin(sum(PROJECTION_WEIGHTS[1:]) / 2.0) ** 2,
        "erase_m2": math.sin((PROJECTION_WEIGHTS[0] + PROJECTION_WEIGHTS[2]) / 2.0) ** 2,
        "erase_m3": math.sin(sum(PROJECTION_WEIGHTS[:2]) / 2.0) ** 2,
        "erase_all": 0.0,
    }


def self_test() -> None:
    if not math.isclose(sum(PROJECTION_WEIGHTS), math.pi, rel_tol=0.0, abs_tol=1e-12):
        raise AssertionError("Projection weights must sum to pi.")
    ideals = ideal_reset_readout_probabilities()
    if ideals["full_memory"] < 0.999:
        raise AssertionError("Full-memory ideal readout should be one.")
    reset_values = [ideals["erase_m1"], ideals["erase_m2"], ideals["erase_m3"]]
    if min(abs(left - right) for i, left in enumerate(reset_values) for right in reset_values[i + 1 :]) < 0.03:
        raise AssertionError("Selective reset signatures are not distinguishable.")
    for mode in MODES:
        circuit = build_memory_circuit(mode)
        if circuit.num_qubits != 7 or circuit.num_clbits != 7:
            raise AssertionError(f"Unexpected circuit width for {mode}.")
    for order in ("rk", "kr"):
        circuit = build_visible_order_circuit(order)
        if circuit.num_qubits != 7:
            raise AssertionError(f"Unexpected visible circuit width for {order}.")
    print("Self-test passed: three ledgers, selective resets, matched visible orders, and projection signatures are defined.")
    print(json.dumps(ideals, indent=2, sort_keys=True))


def run_hardware() -> int:
    OUT.mkdir(parents=True, exist_ok=False)

    service_kwargs: dict[str, Any] = {"channel": CHANNEL}
    if INSTANCE:
        service_kwargs["instance"] = INSTANCE
    service = QiskitRuntimeService(**service_kwargs)
    backend = select_backend(service)

    pubs = []
    metadata: list[dict[str, Any]] = []

    for mode in MODES:
        logical = build_memory_circuit(mode)
        for seed in SEEDS:
            compiled = transpile(
                logical,
                backend=backend,
                optimization_level=3,
                seed_transpiler=seed,
            )
            pubs.append(compiled)
            metadata.append(
                {
                    "experiment_family": "memory_decomposition",
                    "mode": mode,
                    "seed_transpiler": seed,
                    "depth": compiled.depth(),
                    "two_qubit_ops": sum(
                        count
                        for gate_name, count in compiled.count_ops().items()
                        if gate_name in {"cx", "cz", "ecr", "rzz", "crx", "cry", "crz"}
                    ),
                }
            )

    for order in ("rk", "kr"):
        logical = build_visible_order_circuit(order)
        for seed in SEEDS:
            compiled = transpile(
                logical,
                backend=backend,
                optimization_level=3,
                seed_transpiler=seed,
            )
            pubs.append(compiled)
            metadata.append(
                {
                    "experiment_family": "visible_order_equality",
                    "order": order,
                    "seed_transpiler": seed,
                    "depth": compiled.depth(),
                    "two_qubit_ops": sum(
                        count
                        for gate_name, count in compiled.count_ops().items()
                        if gate_name in {"cx", "cz", "ecr", "rzz", "crx", "cry", "crz"}
                    ),
                }
            )

    sampler = Sampler(mode=backend)
    job = sampler.run(pubs, shots=SHOTS)
    result = job.result()

    records: list[dict[str, Any]] = []
    for meta, pub_result in zip(metadata, result):
        counts = counts_from_pub_result(pub_result)
        record = dict(meta)
        record["counts"] = counts
        if meta["experiment_family"] == "memory_decomposition":
            record["ledger_p1"] = [bit_probability(counts, ledger) for ledger in LEDGERS]
            record["readout_p1"] = bit_probability(counts, READOUT)
            record["ledger_distribution"] = ledger_distribution(counts)
        else:
            record["visible_distribution"] = visible_distribution(counts)
        records.append(record)

    raw_path = OUT / "results.json"
    raw_path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")

    memory_records = [record for record in records if record["experiment_family"] == "memory_decomposition"]
    visible_records = [record for record in records if record["experiment_family"] == "visible_order_equality"]

    def records_for_mode(mode: str) -> list[dict[str, Any]]:
        return [record for record in memory_records if record["mode"] == mode]

    def mode_ledger_means(mode: str) -> list[float]:
        group = records_for_mode(mode)
        return [mean(float(record["ledger_p1"][index]) for record in group) for index in range(3)]

    def mode_readout_mean(mode: str) -> float:
        return mean(float(record["readout_p1"]) for record in records_for_mode(mode))

    def mode_distribution(mode: str) -> dict[str, float]:
        group = records_for_mode(mode)
        patterns = {f"{value:03b}" for value in range(8)}
        return {
            pattern: mean(float(record["ledger_distribution"][pattern]) for record in group)
            for pattern in patterns
        }

    summaries: dict[str, Any] = {}
    for mode in MODES:
        summaries[mode] = {
            "ledger_p1": mode_ledger_means(mode),
            "readout_p1": mode_readout_mean(mode),
            "ledger_distribution": mode_distribution(mode),
        }

    visible_by_order: dict[str, dict[str, float]] = {}
    for order in ("rk", "kr"):
        group = [record for record in visible_records if record["order"] == order]
        visible_by_order[order] = {
            pattern: mean(float(record["visible_distribution"][pattern]) for record in group)
            for pattern in {f"{value:03b}" for value in range(8)}
        }
    visible_tvd = total_variation_distance(visible_by_order["rk"], visible_by_order["kr"])

    full_ledgers = summaries["full_memory"]["ledger_p1"]
    control_ceiling = max(
        max(summaries["commuting_control"]["ledger_p1"]),
        max(summaries["order_erased_control"]["ledger_p1"]),
    )
    hidden_memory_pass = min(full_ledgers) > 0.70 and control_ceiling < 0.30

    selective_details: dict[str, Any] = {}
    selective_checks: list[bool] = []
    for index, mode in enumerate(("erase_m1", "erase_m2", "erase_m3")):
        ledger_means = summaries[mode]["ledger_p1"]
        erased_low = ledger_means[index] < 0.30
        untouched_high = min(
            value for other_index, value in enumerate(ledger_means) if other_index != index
        ) > 0.60
        selective_checks.extend((erased_low, untouched_high))
        selective_details[mode] = {
            "ledger_p1": ledger_means,
            "erased_channel_low": erased_low,
            "untouched_channels_high": untouched_high,
            "readout_p1": summaries[mode]["readout_p1"],
        }
    erase_all_low = max(summaries["erase_all"]["ledger_p1"]) < 0.30
    selective_checks.append(erase_all_low)
    selective_erase_pass = all(selective_checks)

    projection_erased = summaries["projection_erased"]
    projection_causal_pass = (
        min(projection_erased["ledger_p1"]) > 0.60
        and projection_erased["readout_p1"] < 0.30
        and summaries["full_memory"]["readout_p1"] > 0.65
    )

    reset_readouts = [summaries[mode]["readout_p1"] for mode in ("erase_m1", "erase_m2", "erase_m3")]
    reset_signature_spread = max(reset_readouts) - min(reset_readouts)
    reset_projection_pass = (
        all(summaries["full_memory"]["readout_p1"] - value > 0.05 for value in reset_readouts)
        and reset_signature_spread > 0.025
    )

    model_rows = []
    for mode in PROJECTION_ACTIVE_MODES:
        distribution = summaries[mode]["ledger_distribution"]
        observed = summaries[mode]["readout_p1"]
        model_rows.append(
            {
                "mode": mode,
                "observed": observed,
                "no_memory": 0.0,
                "single_m1": predict_from_distribution(distribution, (0,)),
                "single_m2": predict_from_distribution(distribution, (1,)),
                "single_m3": predict_from_distribution(distribution, (2,)),
                "pair_m12": predict_from_distribution(distribution, (0, 1)),
                "pair_m13": predict_from_distribution(distribution, (0, 2)),
                "pair_m23": predict_from_distribution(distribution, (1, 2)),
                "full_multi_ledger": predict_from_distribution(distribution, (0, 1, 2)),
            }
        )

    observed_values = [row["observed"] for row in model_rows]
    model_errors = {
        key: mean_absolute_error(observed_values, [row[key] for row in model_rows])
        for key in (
            "no_memory",
            "single_m1",
            "single_m2",
            "single_m3",
            "pair_m12",
            "pair_m13",
            "pair_m23",
            "full_multi_ledger",
        )
    }
    best_single_error = min(model_errors[key] for key in ("single_m1", "single_m2", "single_m3"))
    best_pair_error = min(model_errors[key] for key in ("pair_m12", "pair_m13", "pair_m23"))
    full_model_error = model_errors["full_multi_ledger"]
    model_comparison_pass = (
        full_model_error + 0.02 < best_single_error
        and full_model_error <= best_pair_error + 0.02
        and full_model_error < model_errors["no_memory"]
        and full_model_error < 0.20
    )

    visible_equality_pass = visible_tvd < 0.08
    full_pass = all(
        (
            hidden_memory_pass,
            selective_erase_pass,
            projection_causal_pass,
            reset_projection_pass,
            model_comparison_pass,
            visible_equality_pass,
        )
    )

    if full_pass:
        classification = "MULTI_LEDGER_OPERATOR_MEMORY_DECOMPOSITION"
    elif hidden_memory_pass and selective_erase_pass and visible_equality_pass:
        classification = "HIDDEN_MULTI_LEDGER_MEMORY_WITHOUT_RELIABLE_PROJECTION"
    else:
        classification = "NO_REPRODUCIBLE_MULTI_LEDGER_MEMORY"

    certificate = {
        "schema": "MULTI_LEDGER_OPERATOR_MEMORY_CERTIFICATE_V1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "backend": backend.name,
        "job_id": job.job_id(),
        "shots_per_circuit": SHOTS,
        "transpiler_seeds": SEEDS,
        "operator_definition": {"R": "X", "K": "Z", "relation": "RK=-KR"},
        "projection_weights_radians": PROJECTION_WEIGHTS,
        "classification": classification,
        "pass_gates": {
            "hidden_memory": hidden_memory_pass,
            "selective_erase": selective_erase_pass,
            "projection_causal": projection_causal_pass,
            "reset_projection": reset_projection_pass,
            "model_comparison": model_comparison_pass,
            "visible_rk_kr_equality": visible_equality_pass,
        },
        "primary_metrics": {
            "full_ledger_p1": full_ledgers,
            "control_ledger_ceiling": control_ceiling,
            "full_readout_p1": summaries["full_memory"]["readout_p1"],
            "projection_erased_readout_p1": projection_erased["readout_p1"],
            "reset_readout_values": reset_readouts,
            "reset_signature_spread": reset_signature_spread,
            "visible_rk_kr_tvd": visible_tvd,
            "model_mae": model_errors,
        },
        "selective_erase_details": selective_details,
        "summary": summaries,
        "model_rows": model_rows,
        "visible_distributions": visible_by_order,
        "scientific_boundary": (
            "This benchmark tests a quantum representation of decomposable operator-order memory, "
            "selective ledger erasure, and declared memory-to-readout projection. It does not establish "
            "a fabricated transistor, a material memory effect, quantum advantage, or a new physical law."
        ),
        "raw_results_sha256": sha256_file(raw_path),
    }

    cert_path = OUT / "certificate.json"
    cert_path.write_text(json.dumps(certificate, indent=2, sort_keys=True), encoding="utf-8")

    summary_lines = [
        "# Multi-Ledger Operator-Memory Benchmark v1",
        "",
        f"- Classification: `{classification}`",
        f"- Backend: `{backend.name}`",
        f"- Job ID: `{job.job_id()}`",
        f"- Hidden-memory pass: `{hidden_memory_pass}`",
        f"- Selective-erase pass: `{selective_erase_pass}`",
        f"- Projection-causal pass: `{projection_causal_pass}`",
        f"- Reset-projection pass: `{reset_projection_pass}`",
        f"- Model-comparison pass: `{model_comparison_pass}`",
        f"- Visible RK/KR equality pass: `{visible_equality_pass}`",
        "",
        "The benchmark is a quantum representation test, not physical device validation.",
    ]
    summary_path = OUT / "summary.md"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    manifest = {
        "schema": "MULTI_LEDGER_OPERATOR_MEMORY_MANIFEST_V1",
        "backend": backend.name,
        "job_id": job.job_id(),
        "files": {
            raw_path.name: sha256_file(raw_path),
            cert_path.name: sha256_file(cert_path),
            summary_path.name: sha256_file(summary_path),
        },
    }
    manifest_path = OUT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps(certificate, indent=2, sort_keys=True))
    print(f"\nEvidence written to: {OUT}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    return run_hardware()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
