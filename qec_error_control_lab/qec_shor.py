"""Exact 9-qubit Shor-code laboratory for arbitrary single-Pauli recovery.

The implementation is dependency-free and intentionally explicit.  Syndrome
bits are extracted from stabilizer expectation values of the damaged
statevector; injected error labels are retained only for campaign bookkeeping
and claim-boundary enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

from qec_repetition import (
    FIDELITY_TOLERANCE,
    IncompleteSyndrome,
    named_logical_states,
    normalize_logical_state,
    sha256_payload,
)


PROTOCOL = "qec-shor-nine-qubit-pauli-v1"
QUBIT_COUNT = 9
STATE_DIMENSION = 1 << QUBIT_COUNT
PAULIS = frozenset(("X", "Y", "Z"))


# Six bit-flip checks within the three GHZ blocks, followed by two phase checks
# across neighboring blocks.
SHOR_STABILIZERS: tuple[tuple[tuple[int, str], ...], ...] = (
    ((0, "Z"), (1, "Z")),
    ((1, "Z"), (2, "Z")),
    ((3, "Z"), (4, "Z")),
    ((4, "Z"), (5, "Z")),
    ((6, "Z"), (7, "Z")),
    ((7, "Z"), (8, "Z")),
    tuple((qubit, "X") for qubit in range(0, 6)),
    tuple((qubit, "X") for qubit in range(3, 9)),
)


PAIR_TO_OFFSET: dict[tuple[int, int], int | None] = {
    (0, 0): None,
    (1, 0): 0,
    (1, 1): 1,
    (0, 1): 2,
}

PAIR_TO_BLOCK: dict[tuple[int, int], int | None] = {
    (0, 0): None,
    (1, 0): 0,
    (1, 1): 1,
    (0, 1): 2,
}


def _validate_qubit(qubit: int) -> None:
    if not isinstance(qubit, int) or qubit < 0 or qubit >= QUBIT_COUNT:
        raise ValueError(f"qubit must be an integer from 0 through 8; got {qubit!r}")


def _validate_pauli(pauli: str) -> str:
    normalized = str(pauli).upper()
    if normalized not in PAULIS:
        raise ValueError(f"Pauli must be X, Y, or Z; got {pauli!r}")
    return normalized


def _basis_index(block_bits: Sequence[int]) -> int:
    index = 0
    for bit in block_bits:
        index = (index << 1) | bit
    return index


def encode_shor(alpha: complex, beta: complex) -> tuple[complex, ...]:
    """Encode alpha|0> + beta|1> into the 9-qubit Shor code."""

    alpha, beta = normalize_logical_state(alpha, beta)
    state = [0j] * STATE_DIMENSION
    scale = math.sqrt(8)
    for block_mask in range(8):
        bits: list[int] = []
        populated_blocks = 0
        for block in range(3):
            occupied = (block_mask >> (2 - block)) & 1
            populated_blocks += occupied
            bits.extend((occupied, occupied, occupied))
        logical_one_sign = -1 if populated_blocks % 2 else 1
        state[_basis_index(bits)] = (alpha + logical_one_sign * beta) / scale
    return tuple(state)


def apply_pauli(state: Sequence[complex], qubit: int, pauli: str) -> tuple[complex, ...]:
    _validate_qubit(qubit)
    pauli = _validate_pauli(pauli)
    if len(state) != STATE_DIMENSION:
        raise ValueError("9-qubit statevector must contain exactly 512 amplitudes")
    mask = 1 << (QUBIT_COUNT - 1 - qubit)
    output = [0j] * STATE_DIMENSION
    for index, amplitude in enumerate(state):
        bit = 1 if index & mask else 0
        if pauli == "Z":
            output[index] = amplitude if bit == 0 else -amplitude
        elif pauli == "X":
            output[index ^ mask] = amplitude
        else:  # Y|0> = i|1>, Y|1> = -i|0>
            output[index ^ mask] = (1j if bit == 0 else -1j) * amplitude
    return tuple(output)


def normalize_errors(errors: Iterable[tuple[int, str]]) -> tuple[tuple[int, str], ...]:
    normalized: list[tuple[int, str]] = []
    occupied: set[int] = set()
    for qubit, pauli in errors:
        _validate_qubit(qubit)
        if qubit in occupied:
            raise ValueError("an injected error list must not repeat a qubit")
        occupied.add(qubit)
        normalized.append((qubit, _validate_pauli(pauli)))
    return tuple(normalized)


def apply_errors(
    state: Sequence[complex], errors: Iterable[tuple[int, str]]
) -> tuple[complex, ...]:
    output = tuple(state)
    for qubit, pauli in normalize_errors(errors):
        output = apply_pauli(output, qubit, pauli)
    return output


def inner_product(left: Sequence[complex], right: Sequence[complex]) -> complex:
    if len(left) != len(right):
        raise ValueError("statevectors must have equal dimensions")
    return sum(a.conjugate() * b for a, b in zip(left, right))


def fidelity(left: Sequence[complex], right: Sequence[complex]) -> float:
    value = float(abs(inner_product(left, right)) ** 2)
    if abs(value - 1.0) <= FIDELITY_TOLERANCE:
        return 1.0
    if abs(value) <= FIDELITY_TOLERANCE:
        return 0.0
    return value


def apply_pauli_string(
    state: Sequence[complex], operators: Sequence[tuple[int, str]]
) -> tuple[complex, ...]:
    output = tuple(state)
    for qubit, pauli in operators:
        output = apply_pauli(output, qubit, pauli)
    return output


def stabilizer_bit(
    state: Sequence[complex], stabilizer: Sequence[tuple[int, str]]
) -> int:
    expectation = inner_product(state, apply_pauli_string(state, stabilizer))
    if abs(expectation.imag) > 1e-10:
        raise IncompleteSyndrome("stabilizer expectation is not real")
    if abs(expectation.real - 1.0) <= 1e-10:
        return 0
    if abs(expectation.real + 1.0) <= 1e-10:
        return 1
    raise IncompleteSyndrome(
        f"stabilizer expectation is not a resolved +/-1 eigenvalue: {expectation.real!r}"
    )


def extract_shor_syndrome(state: Sequence[complex]) -> tuple[int, ...]:
    """Extract six intra-block and two inter-block stabilizer syndrome bits."""

    return tuple(stabilizer_bit(state, stabilizer) for stabilizer in SHOR_STABILIZERS)


def validate_shor_syndrome(syndrome: Sequence[int]) -> tuple[int, ...]:
    if len(syndrome) != 8 or any(bit not in (0, 1) for bit in syndrome):
        raise ValueError("Shor syndrome must contain exactly eight binary values")
    return tuple(int(bit) for bit in syndrome)


def majority_shor_syndrome(reports: Sequence[Sequence[int]]) -> tuple[int, ...]:
    if len(reports) < 3 or len(reports) % 2 == 0:
        raise ValueError("syndrome voting requires an odd number of at least 3 reports")
    normalized = [validate_shor_syndrome(report) for report in reports]
    counts = {candidate: normalized.count(candidate) for candidate in set(normalized)}
    candidate, count = max(counts.items(), key=lambda item: (item[1], item[0]))
    if count <= len(normalized) // 2:
        raise IncompleteSyndrome("no exact eight-bit syndrome has a strict majority")
    return candidate


def corrections_for_syndrome(syndrome: Sequence[int]) -> tuple[tuple[int, str], ...]:
    syndrome = validate_shor_syndrome(syndrome)
    corrections: list[tuple[int, str]] = []
    active_bit_blocks: list[tuple[int, int]] = []
    for block in range(3):
        pair = syndrome[2 * block], syndrome[2 * block + 1]
        offset = PAIR_TO_OFFSET[pair]
        if offset is not None:
            active_bit_blocks.append((block, offset))
    if len(active_bit_blocks) > 1:
        raise IncompleteSyndrome("syndrome activates bit-flip recovery in multiple blocks")
    if active_bit_blocks:
        block, offset = active_bit_blocks[0]
        corrections.append((3 * block + offset, "X"))

    phase_block = PAIR_TO_BLOCK[(syndrome[6], syndrome[7])]
    if phase_block is not None:
        # A Z on any one member of a GHZ block has the same action on the code
        # subspace; choose the first qubit as the canonical representative.
        corrections.append((3 * phase_block, "Z"))
    return tuple(corrections)


def recover_shor(
    state: Sequence[complex], syndrome: Sequence[int]
) -> tuple[tuple[complex, ...], tuple[tuple[int, str], ...]]:
    corrections = corrections_for_syndrome(syndrome)
    output = tuple(state)
    for qubit, pauli in corrections:
        output = apply_pauli(output, qubit, pauli)
    return output, corrections


@dataclass(frozen=True)
class ShorTrialResult:
    protocol: str
    injected_errors: tuple[tuple[int, str], ...]
    extracted_syndrome: tuple[int, ...] | None
    used_syndrome: tuple[int, ...] | None
    corrections: tuple[tuple[int, str], ...]
    fidelity: float
    classification: str

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol": self.protocol,
            "injected_errors": [
                {"qubit": qubit, "pauli": pauli}
                for qubit, pauli in self.injected_errors
            ],
            "extracted_syndrome": (
                None if self.extracted_syndrome is None else list(self.extracted_syndrome)
            ),
            "used_syndrome": None if self.used_syndrome is None else list(self.used_syndrome),
            "corrections": [
                {"qubit": qubit, "pauli": pauli} for qubit, pauli in self.corrections
            ],
            "fidelity": self.fidelity,
            "classification": self.classification,
        }


def run_shor_trial(
    alpha: complex,
    beta: complex,
    errors: Iterable[tuple[int, str]],
    *,
    syndrome_reports: Sequence[Sequence[int]] | None = None,
) -> ShorTrialResult:
    normalized_errors = normalize_errors(errors)
    target = encode_shor(alpha, beta)
    damaged = apply_errors(target, normalized_errors)
    try:
        extracted = extract_shor_syndrome(damaged)
        used = (
            extracted
            if syndrome_reports is None
            else majority_shor_syndrome(syndrome_reports)
        )
        recovered, corrections = recover_shor(damaged, used)
    except IncompleteSyndrome:
        return ShorTrialResult(
            protocol=PROTOCOL,
            injected_errors=normalized_errors,
            extracted_syndrome=None,
            used_syndrome=None,
            corrections=(),
            fidelity=fidelity(target, damaged),
            classification=(
                "NEGATIVE_CONTROL_OUTSIDE_DISTANCE3_CAPABILITY"
                if len(normalized_errors) > 1
                else "INCOMPLETE_SYNDROME"
            ),
        )

    recovered_fidelity = fidelity(target, recovered)
    if len(normalized_errors) > 1:
        classification = "NEGATIVE_CONTROL_OUTSIDE_DISTANCE3_CAPABILITY"
    elif not normalized_errors and recovered_fidelity >= 1.0 - FIDELITY_TOLERANCE:
        classification = "PASS_NO_ERROR"
    elif len(normalized_errors) == 1 and recovered_fidelity >= 1.0 - FIDELITY_TOLERANCE:
        classification = "PASS_SINGLE_PAULI_RECOVERY"
    else:
        classification = "FAIL_RECOVERY"
    return ShorTrialResult(
        protocol=PROTOCOL,
        injected_errors=normalized_errors,
        extracted_syndrome=extracted,
        used_syndrome=used,
        corrections=corrections,
        fidelity=recovered_fidelity,
        classification=classification,
    )


def build_shor_campaign_certificate() -> dict[str, object]:
    positive_results: list[dict[str, object]] = []
    for state_name, (alpha, beta) in named_logical_states().items():
        no_error = run_shor_trial(alpha, beta, ())
        positive_results.append({"state": state_name, **no_error.to_dict()})
        for qubit in range(QUBIT_COUNT):
            for pauli in ("X", "Y", "Z"):
                result = run_shor_trial(alpha, beta, ((qubit, pauli),))
                positive_results.append({"state": state_name, **result.to_dict()})

    alpha, beta = named_logical_states()["generic"]
    repeated_results: list[dict[str, object]] = []
    for qubit in range(QUBIT_COUNT):
        for pauli in ("X", "Y", "Z"):
            target = encode_shor(alpha, beta)
            damaged = apply_errors(target, ((qubit, pauli),))
            true_syndrome = extract_shor_syndrome(damaged)
            for faulty_round in range(3):
                for faulty_bit in range(8):
                    reports = [list(true_syndrome) for _ in range(3)]
                    reports[faulty_round][faulty_bit] ^= 1
                    result = run_shor_trial(
                        alpha,
                        beta,
                        ((qubit, pauli),),
                        syndrome_reports=reports,
                    )
                    repeated_results.append(
                        {
                            "faulty_round": faulty_round,
                            "faulty_syndrome_bit": faulty_bit,
                            **result.to_dict(),
                        }
                    )

    true_syndrome = extract_shor_syndrome(apply_errors(encode_shor(alpha, beta), ((0, "Y"),)))
    report_b = list(true_syndrome)
    report_c = list(true_syndrome)
    report_b[0] ^= 1
    report_c[6] ^= 1
    incomplete = run_shor_trial(
        alpha,
        beta,
        ((0, "Y"),),
        syndrome_reports=(true_syndrome, report_b, report_c),
    )

    negative_patterns = (
        ((0, "X"), (1, "X")),
        ((0, "Z"), (3, "Z")),
        ((0, "X"), (4, "Z")),
        ((2, "Y"), (7, "Y")),
        ((0, "X"), (3, "X")),
        ((1, "Z"), (8, "X")),
    )
    negative_results = [
        run_shor_trial(alpha, beta, errors).to_dict() for errors in negative_patterns
    ]

    gates = {
        "all_single_pauli_errors_recovered": all(
            item["classification"]
            == ("PASS_NO_ERROR" if not item["injected_errors"] else "PASS_SINGLE_PAULI_RECOVERY")
            and item["fidelity"] == 1.0
            for item in positive_results
        ),
        "single_syndrome_report_fault_tolerated": all(
            item["classification"] == "PASS_SINGLE_PAULI_RECOVERY"
            and item["fidelity"] == 1.0
            for item in repeated_results
        ),
        "no_exact_majority_fails_closed": incomplete.classification == "INCOMPLETE_SYNDROME",
        "multi_error_controls_not_promoted": all(
            not str(item["classification"]).startswith("PASS") for item in negative_results
        ),
    }

    body: dict[str, object] = {
        "protocol": PROTOCOL,
        "code": {"name": "Shor code", "n": 9, "k": 1, "distance": 3},
        "declared_capability": "correct one arbitrary X, Y, or Z error on nine data qubits",
        "syndrome_source": "eight stabilizer expectations computed from the damaged statevector",
        "claim_boundary": (
            "Exact simulator-level Shor-code evidence only; no noisy-gate model, hardware "
            "validation, transversal universal gate set, threshold theorem, or scalable "
            "fault-tolerant quantum computer claim."
        ),
        "stabilizer_count": len(SHOR_STABILIZERS),
        "counts": {
            "positive_trials": len(positive_results),
            "single_report_fault_trials": len(repeated_results),
            "incomplete_syndrome_trials": 1,
            "multi_error_negative_controls": len(negative_results),
        },
        "gates": gates,
        "classification": "PASS_BOUNDED_SHOR_QEC_V1" if all(gates.values()) else "FAIL",
        "positive_results": positive_results,
        "single_report_fault_results": repeated_results,
        "incomplete_syndrome_result": incomplete.to_dict(),
        "negative_control_results": negative_results,
    }
    return {**body, "certificate_sha256": sha256_payload(body)}
