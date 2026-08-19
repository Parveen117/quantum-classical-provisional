from __future__ import annotations

import math
from pathlib import Path
import unittest

from qec_repetition import (
    IncompleteSyndrome,
    apply_x,
    build_campaign_certificate,
    encode_logical,
    fidelity,
    majority_syndrome,
    recover,
    run_trial,
    syndrome_for_error_qubits,
)


class RepetitionCodeTests(unittest.TestCase):
    def test_encoding_preserves_normalized_logical_amplitudes(self) -> None:
        state = encode_logical(3, 4j)
        self.assertEqual(state[0], 0.6)
        self.assertEqual(state[7], 0.8j)
        self.assertAlmostEqual(sum(abs(value) ** 2 for value in state), 1.0)

    def test_x_is_self_inverse_on_every_data_qubit(self) -> None:
        target = encode_logical(math.sqrt(0.2), 1j * math.sqrt(0.8))
        for qubit in range(3):
            self.assertEqual(apply_x(apply_x(target, qubit), qubit), target)

    def test_declared_syndrome_table(self) -> None:
        self.assertEqual(syndrome_for_error_qubits(()), (0, 0))
        self.assertEqual(syndrome_for_error_qubits((0,)), (1, 0))
        self.assertEqual(syndrome_for_error_qubits((1,)), (1, 1))
        self.assertEqual(syndrome_for_error_qubits((2,)), (0, 1))

    def test_every_single_x_error_is_recovered_for_nontrivial_state(self) -> None:
        alpha, beta = math.sqrt(0.3), complex(0.2, math.sqrt(0.66))
        for qubit in range(3):
            result = run_trial(alpha, beta, (qubit,))
            self.assertEqual(result.classification, "PASS_SINGLE_X_RECOVERY")
            self.assertEqual(result.correction_qubit, qubit)
            self.assertEqual(result.fidelity, 1.0)

    def test_recovery_uses_syndrome_not_injection_label(self) -> None:
        target = encode_logical(1, 0)
        damaged = apply_x(target, 2)
        recovered, correction = recover(damaged, (0, 1))
        self.assertEqual(correction, 2)
        self.assertEqual(fidelity(target, recovered), 1.0)

    def test_one_faulty_report_is_tolerated(self) -> None:
        self.assertEqual(majority_syndrome(((1, 0), (1, 0), (0, 0))), (1, 0))

    def test_no_exact_majority_fails_closed(self) -> None:
        with self.assertRaises(IncompleteSyndrome):
            majority_syndrome(((1, 0), (0, 0), (1, 1)))
        result = run_trial(
            1,
            0,
            (0,),
            syndrome_reports=((1, 0), (0, 0), (1, 1)),
        )
        self.assertEqual(result.classification, "INCOMPLETE_SYNDROME")

    def test_double_errors_are_not_promoted(self) -> None:
        for errors in ((0, 1), (0, 2), (1, 2)):
            result = run_trial(1, 0, errors)
            self.assertEqual(
                result.classification,
                "NEGATIVE_CONTROL_OUTSIDE_DISTANCE3_CAPABILITY",
            )
            self.assertEqual(result.fidelity, 0.0)

    def test_duplicate_or_invalid_errors_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_trial(1, 0, (0, 0))
        with self.assertRaises(ValueError):
            run_trial(1, 0, (3,))

    def test_campaign_certificate_is_deterministic_and_complete(self) -> None:
        first = build_campaign_certificate()
        second = build_campaign_certificate()
        self.assertEqual(first, second)
        self.assertEqual(first["classification"], "PASS_BOUNDED_QEC_ERROR_CONTROL_V1")
        self.assertTrue(all(first["gates"].values()))
        self.assertEqual(first["counts"]["positive_trials"], 16)
        self.assertEqual(first["counts"]["single_report_fault_trials"], 18)
        self.assertEqual(len(first["certificate_sha256"]), 64)
        expected = Path(__file__).with_name("EXPECTED_CAMPAIGN.sha256").read_text(
            encoding="utf-8"
        ).strip()
        self.assertEqual(first["certificate_sha256"], expected)


if __name__ == "__main__":
    unittest.main()
