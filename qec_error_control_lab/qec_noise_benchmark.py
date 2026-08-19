"""Bounded encoded-vs-unencoded phenomenological noise comparison.

This is an analytic storage-channel benchmark, not a circuit-level threshold
simulation.  It keeps data errors and whole-report syndrome reliability
separate so gate and measurement assumptions remain visible.
"""

from __future__ import annotations

from qec_repetition import sha256_payload


PROTOCOL = "qec-shor-phenomenological-noise-v1"
DATA_ERROR_GRID = (0.0001, 0.0003, 0.001, 0.003, 0.01, 0.02, 0.03, 0.04, 0.05, 0.1)
SYNDROME_BIT_ERROR_GRID = (0.0, 0.001, 0.005, 0.01)


def _probability(value: float, name: str) -> float:
    value = float(value)
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must lie in [0, 1]")
    return value


def unencoded_process_success(data_error_probability: float) -> float:
    p = _probability(data_error_probability, "data_error_probability")
    return 1.0 - p


def shor_weight_zero_or_one_success(data_error_probability: float) -> float:
    """Probability that nine independent data locations contain at most one error."""

    p = _probability(data_error_probability, "data_error_probability")
    return (1.0 - p) ** 9 + 9.0 * p * (1.0 - p) ** 8


def exact_eight_bit_report_probability(bit_error_probability: float) -> float:
    r = _probability(bit_error_probability, "bit_error_probability")
    return (1.0 - r) ** 8


def three_round_exact_majority_probability(bit_error_probability: float) -> float:
    """Conservative probability that at least two whole syndrome reports are exact."""

    exact = exact_eight_bit_report_probability(bit_error_probability)
    return exact**3 + 3.0 * exact**2 * (1.0 - exact)


def shor_conservative_success(
    data_error_probability: float, syndrome_bit_error_probability: float
) -> float:
    return shor_weight_zero_or_one_success(
        data_error_probability
    ) * three_round_exact_majority_probability(syndrome_bit_error_probability)


def build_noise_benchmark_certificate() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for syndrome_rate in SYNDROME_BIT_ERROR_GRID:
        for data_rate in DATA_ERROR_GRID:
            unencoded = unencoded_process_success(data_rate)
            ideal_shor = shor_weight_zero_or_one_success(data_rate)
            conservative_shor = shor_conservative_success(data_rate, syndrome_rate)
            rows.append(
                {
                    "data_error_probability": data_rate,
                    "syndrome_bit_error_probability": syndrome_rate,
                    "unencoded_process_success": unencoded,
                    "ideal_shor_weight_le_one_success": ideal_shor,
                    "conservative_shor_success": conservative_shor,
                    "conservative_advantage": conservative_shor - unencoded,
                }
            )

    def row(data_rate: float, syndrome_rate: float) -> dict[str, object]:
        return next(
            item
            for item in rows
            if item["data_error_probability"] == data_rate
            and item["syndrome_bit_error_probability"] == syndrome_rate
        )

    gates = {
        "ideal_code_beats_unencoded_at_one_percent": row(0.01, 0.0)[
            "conservative_advantage"
        ]
        > 0,
        "overhead_negative_control_at_four_percent": row(0.04, 0.0)[
            "conservative_advantage"
        ]
        < 0,
        "syndrome_noise_never_improves_bound": all(
            item["conservative_shor_success"] <= item["ideal_shor_weight_le_one_success"]
            for item in rows
        ),
        "all_reported_values_are_probabilities": all(
            0.0 <= item[key] <= 1.0
            for item in rows
            for key in (
                "unencoded_process_success",
                "ideal_shor_weight_le_one_success",
                "conservative_shor_success",
            )
        ),
    }
    body: dict[str, object] = {
        "protocol": PROTOCOL,
        "model": {
            "data": "independent non-identity Pauli event with total probability p per data qubit",
            "recovery": "ideal correction for weight zero or one",
            "syndrome": (
                "three independent reports; a round is counted correct only if all eight bits "
                "are correct; at least two exact reports required"
            ),
        },
        "claim_boundary": (
            "Phenomenological storage-channel comparison only. Encoding, extraction, recovery "
            "gate noise, connectivity, leakage, crosstalk, correlated errors, and hardware "
            "calibration are excluded; this is not a threshold theorem."
        ),
        "rows": rows,
        "gates": gates,
        "classification": (
            "PASS_BOUNDED_PHENOMENOLOGICAL_NOISE_V1" if all(gates.values()) else "FAIL"
        ),
    }
    return {**body, "certificate_sha256": sha256_payload(body)}
