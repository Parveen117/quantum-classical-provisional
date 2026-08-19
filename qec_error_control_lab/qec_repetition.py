"""Exact, dependency-free distance-3 bit-flip error-control laboratory.

The module deliberately implements a bounded experiment rather than claiming
fault-tolerant quantum computation.  It encodes one logical qubit into three
data qubits, extracts the two Z-parity syndromes, applies the corresponding
single-X recovery, and can vote over repeated syndrome reports.
"""

from __future__ import annotations

from dataclasses import dataclass
import cmath
import hashlib
import json
import math
from typing import Iterable, Sequence


PROTOCOL = "qec-repetition-bit-flip-v1"
FIDELITY_TOLERANCE = 1e-12


class IncompleteSyndrome(ValueError):
    """Raised when repeated syndrome reports do not close to one majority."""


def _validate_qubit(qubit: int) -> None:
    if qubit not in (0, 1, 2):
        raise ValueError(f"data qubit must be 0, 1, or 2; got {qubit!r}")


def normalize_logical_state(alpha: complex, beta: complex) -> tuple[complex, complex]:
    norm = abs(alpha) ** 2 + abs(beta) ** 2
    if not math.isfinite(norm) or norm <= 0.0:
        raise ValueError("logical amplitudes must have a finite non-zero norm")
    scale = math.sqrt(norm)
    return alpha / scale, beta / scale


def encode_logical(alpha: complex, beta: complex) -> tuple[complex, ...]:
    """Return alpha|000> + beta|111> in q0-q1-q2 big-endian order."""

    alpha, beta = normalize_logical_state(alpha, beta)
    state = [0j] * 8
    state[0] = alpha
    state[7] = beta
    return tuple(state)


def apply_x(state: Sequence[complex], qubit: int) -> tuple[complex, ...]:
    _validate_qubit(qubit)
    if len(state) != 8:
        raise ValueError("three-qubit statevector must contain exactly 8 amplitudes")
    mask = 1 << (2 - qubit)
    output = [0j] * 8
    for index, amplitude in enumerate(state):
        output[index ^ mask] = amplitude
    return tuple(output)


def apply_x_errors(state: Sequence[complex], error_qubits: Iterable[int]) -> tuple[complex, ...]:
    output = tuple(state)
    seen: set[int] = set()
    for qubit in error_qubits:
        _validate_qubit(qubit)
        if qubit in seen:
            raise ValueError("an injected error list must not repeat a qubit")
        seen.add(qubit)
        output = apply_x(output, qubit)
    return output


def syndrome_for_error_qubits(error_qubits: Iterable[int]) -> tuple[int, int]:
    """Return eigenvalue bits for Z0Z1 and Z1Z2 (0 means +1, 1 means -1)."""

    error = [0, 0, 0]
    for qubit in error_qubits:
        _validate_qubit(qubit)
        if error[qubit]:
            raise ValueError("an injected error list must not repeat a qubit")
        error[qubit] = 1
    return error[0] ^ error[1], error[1] ^ error[2]


SYNDROME_TO_CORRECTION: dict[tuple[int, int], int | None] = {
    (0, 0): None,
    (1, 0): 0,
    (1, 1): 1,
    (0, 1): 2,
}


def validate_syndrome(syndrome: Sequence[int]) -> tuple[int, int]:
    if len(syndrome) != 2 or any(bit not in (0, 1) for bit in syndrome):
        raise ValueError("syndrome must contain exactly two binary values")
    return int(syndrome[0]), int(syndrome[1])


def majority_syndrome(reports: Sequence[Sequence[int]]) -> tuple[int, int]:
    """Require one exact syndrome tuple to occupy a strict majority of reports."""

    if len(reports) < 3 or len(reports) % 2 == 0:
        raise ValueError("repeated syndrome voting requires an odd number of at least 3 reports")
    normalized = [validate_syndrome(report) for report in reports]
    counts = {candidate: normalized.count(candidate) for candidate in set(normalized)}
    candidate, count = max(counts.items(), key=lambda item: (item[1], item[0]))
    if count <= len(normalized) // 2:
        raise IncompleteSyndrome("no exact syndrome report has a strict majority")
    return candidate


def recover(state: Sequence[complex], syndrome: Sequence[int]) -> tuple[tuple[complex, ...], int | None]:
    normalized = validate_syndrome(syndrome)
    correction = SYNDROME_TO_CORRECTION[normalized]
    if correction is None:
        return tuple(state), None
    return apply_x(state, correction), correction


def fidelity(left: Sequence[complex], right: Sequence[complex]) -> float:
    if len(left) != len(right):
        raise ValueError("statevectors must have equal dimensions")
    overlap = sum(a.conjugate() * b for a, b in zip(left, right))
    value = float(abs(overlap) ** 2)
    if abs(value - 1.0) <= FIDELITY_TOLERANCE:
        return 1.0
    if abs(value) <= FIDELITY_TOLERANCE:
        return 0.0
    return value


@dataclass(frozen=True)
class TrialResult:
    protocol: str
    error_qubits: tuple[int, ...]
    ideal_syndrome: tuple[int, int]
    used_syndrome: tuple[int, int] | None
    correction_qubit: int | None
    fidelity: float
    classification: str

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol": self.protocol,
            "error_qubits": list(self.error_qubits),
            "ideal_syndrome": list(self.ideal_syndrome),
            "used_syndrome": None if self.used_syndrome is None else list(self.used_syndrome),
            "correction_qubit": self.correction_qubit,
            "fidelity": self.fidelity,
            "classification": self.classification,
        }


def run_trial(
    alpha: complex,
    beta: complex,
    error_qubits: Iterable[int],
    *,
    syndrome_reports: Sequence[Sequence[int]] | None = None,
) -> TrialResult:
    errors = tuple(error_qubits)
    target = encode_logical(alpha, beta)
    damaged = apply_x_errors(target, errors)
    ideal_syndrome = syndrome_for_error_qubits(errors)
    try:
        used_syndrome = (
            ideal_syndrome if syndrome_reports is None else majority_syndrome(syndrome_reports)
        )
    except IncompleteSyndrome:
        return TrialResult(
            protocol=PROTOCOL,
            error_qubits=errors,
            ideal_syndrome=ideal_syndrome,
            used_syndrome=None,
            correction_qubit=None,
            fidelity=fidelity(target, damaged),
            classification="INCOMPLETE_SYNDROME",
        )

    recovered, correction = recover(damaged, used_syndrome)
    recovered_fidelity = fidelity(target, recovered)
    if recovered_fidelity >= 1.0 - FIDELITY_TOLERANCE and not errors:
        classification = "PASS_NO_ERROR"
    elif recovered_fidelity >= 1.0 - FIDELITY_TOLERANCE and len(errors) == 1:
        classification = "PASS_SINGLE_X_RECOVERY"
    elif len(errors) > 1:
        classification = "NEGATIVE_CONTROL_OUTSIDE_DISTANCE3_CAPABILITY"
    else:
        classification = "FAIL_RECOVERY"
    return TrialResult(
        protocol=PROTOCOL,
        error_qubits=errors,
        ideal_syndrome=ideal_syndrome,
        used_syndrome=used_syndrome,
        correction_qubit=correction,
        fidelity=recovered_fidelity,
        classification=classification,
    )


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_payload(payload: object) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def named_logical_states() -> dict[str, tuple[complex, complex]]:
    root_half = 1 / math.sqrt(2)
    return {
        "zero": (1 + 0j, 0j),
        "one": (0j, 1 + 0j),
        "plus": (root_half + 0j, root_half + 0j),
        "generic": (math.sqrt(0.3) + 0j, cmath.exp(0.37j) * math.sqrt(0.7)),
    }


def build_campaign_certificate() -> dict[str, object]:
    """Run deterministic positive, readout-fault, and negative-control campaigns."""

    positive_results: list[dict[str, object]] = []
    for state_name, (alpha, beta) in named_logical_states().items():
        for errors in ((), (0,), (1,), (2,)):
            result = run_trial(alpha, beta, errors)
            positive_results.append({"state": state_name, **result.to_dict()})

    repeated_results: list[dict[str, object]] = []
    alpha, beta = named_logical_states()["generic"]
    for error_qubit in (0, 1, 2):
        true_syndrome = syndrome_for_error_qubits((error_qubit,))
        for faulty_round in range(3):
            for faulty_bit in range(2):
                reports = [list(true_syndrome) for _ in range(3)]
                reports[faulty_round][faulty_bit] ^= 1
                result = run_trial(alpha, beta, (error_qubit,), syndrome_reports=reports)
                repeated_results.append(
                    {
                        "faulty_round": faulty_round,
                        "faulty_syndrome_bit": faulty_bit,
                        "reports": reports,
                        **result.to_dict(),
                    }
                )

    incomplete = run_trial(
        alpha,
        beta,
        (0,),
        syndrome_reports=((1, 0), (0, 0), (1, 1)),
    )

    negative_results = [
        run_trial(1, 0, errors).to_dict()
        for errors in ((0, 1), (0, 2), (1, 2), (0, 1, 2))
    ]

    gates = {
        "all_no_or_single_x_errors_recovered": all(
            item["classification"]
            == ("PASS_NO_ERROR" if not item["error_qubits"] else "PASS_SINGLE_X_RECOVERY")
            and item["fidelity"] == 1.0
            for item in positive_results
        ),
        "single_syndrome_report_fault_tolerated": all(
            item["classification"] == "PASS_SINGLE_X_RECOVERY" and item["fidelity"] == 1.0
            for item in repeated_results
        ),
        "no_majority_fails_closed": incomplete.classification == "INCOMPLETE_SYNDROME",
        "multi_error_negative_controls_not_promoted": all(
            item["classification"] == "NEGATIVE_CONTROL_OUTSIDE_DISTANCE3_CAPABILITY"
            for item in negative_results
        ),
    }

    body: dict[str, object] = {
        "protocol": PROTOCOL,
        "code": {"name": "three-qubit repetition code", "n": 3, "k": 1, "distance": 3},
        "declared_capability": "correct one X error on the three data qubits",
        "claim_boundary": (
            "Exact simulator-level error-control evidence only; no hardware validation, "
            "threshold theorem, arbitrary Pauli correction, or fault-tolerant quantum computer claim."
        ),
        "syndrome_table": {
            "00": None,
            "10": 0,
            "11": 1,
            "01": 2,
        },
        "counts": {
            "positive_trials": len(positive_results),
            "single_report_fault_trials": len(repeated_results),
            "incomplete_syndrome_trials": 1,
            "multi_error_negative_controls": len(negative_results),
        },
        "gates": gates,
        "classification": "PASS_BOUNDED_QEC_ERROR_CONTROL_V1" if all(gates.values()) else "FAIL",
        "positive_results": positive_results,
        "single_report_fault_results": repeated_results,
        "incomplete_syndrome_result": incomplete.to_dict(),
        "negative_control_results": negative_results,
    }
    return {**body, "certificate_sha256": sha256_payload(body)}
