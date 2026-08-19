from __future__ import annotations

import math
from pathlib import Path
import unittest

from qec_shor import (
    IncompleteSyndrome,
    SHOR_STABILIZERS,
    apply_errors,
    build_shor_campaign_certificate,
    encode_shor,
    extract_shor_syndrome,
    fidelity,
    majority_shor_syndrome,
    run_shor_trial,
)


class ShorCodeTests(unittest.TestCase):
    def test_logical_codewords_are_normalized_and_orthogonal(self) -> None:
        logical_zero = encode_shor(1, 0)
        logical_one = encode_shor(0, 1)
        self.assertAlmostEqual(sum(abs(value) ** 2 for value in logical_zero), 1.0)
        self.assertAlmostEqual(sum(abs(value) ** 2 for value in logical_one), 1.0)
        self.assertEqual(fidelity(logical_zero, logical_one), 0.0)

    def test_clean_codeword_has_zero_syndrome(self) -> None:
        state = encode_shor(math.sqrt(0.3), 1j * math.sqrt(0.7))
        self.assertEqual(len(SHOR_STABILIZERS), 8)
        self.assertEqual(extract_shor_syndrome(state), (0,) * 8)

    def test_bit_syndrome_localizes_each_qubit_in_each_block(self) -> None:
        state = encode_shor(1, 0)
        expected_pairs = ((1, 0), (1, 1), (0, 1))
        for qubit in range(9):
            syndrome = extract_shor_syndrome(apply_errors(state, ((qubit, "X"),)))
            block = qubit // 3
            self.assertEqual(syndrome[2 * block : 2 * block + 2], expected_pairs[qubit % 3])
            self.assertEqual(syndrome[6:], (0, 0))

    def test_phase_syndrome_localizes_each_ghz_block(self) -> None:
        state = encode_shor(1, 0)
        expected = ((1, 0), (1, 1), (0, 1))
        for qubit in range(9):
            syndrome = extract_shor_syndrome(apply_errors(state, ((qubit, "Z"),)))
            self.assertEqual(syndrome[:6], (0,) * 6)
            self.assertEqual(syndrome[6:], expected[qubit // 3])

    def test_every_single_pauli_error_is_recovered(self) -> None:
        alpha = math.sqrt(0.31)
        beta = complex(0.2, math.sqrt(0.65))
        for qubit in range(9):
            for pauli in ("X", "Y", "Z"):
                result = run_shor_trial(alpha, beta, ((qubit, pauli),))
                self.assertEqual(result.classification, "PASS_SINGLE_PAULI_RECOVERY")
                self.assertEqual(result.fidelity, 1.0)

    def test_y_error_activates_bit_and_phase_sectors(self) -> None:
        result = run_shor_trial(1, 0, ((4, "Y"),))
        self.assertEqual(result.extracted_syndrome[2:4], (1, 1))
        self.assertEqual(result.extracted_syndrome[6:], (1, 1))
        self.assertEqual(result.fidelity, 1.0)

    def test_one_faulty_eight_bit_report_is_tolerated(self) -> None:
        syndrome = (1, 0, 0, 0, 0, 0, 1, 0)
        faulty = list(syndrome)
        faulty[7] ^= 1
        self.assertEqual(majority_shor_syndrome((syndrome, syndrome, faulty)), syndrome)

    def test_no_exact_report_majority_fails_closed(self) -> None:
        first = (1, 0, 0, 0, 0, 0, 1, 0)
        second = (0, 0, 0, 0, 0, 0, 1, 0)
        third = (1, 0, 0, 0, 0, 0, 0, 0)
        with self.assertRaises(IncompleteSyndrome):
            majority_shor_syndrome((first, second, third))
        result = run_shor_trial(1, 0, ((0, "Y"),), syndrome_reports=(first, second, third))
        self.assertEqual(result.classification, "INCOMPLETE_SYNDROME")

    def test_multi_error_cases_are_never_promoted(self) -> None:
        cases = (
            ((0, "X"), (1, "X")),
            ((0, "Z"), (3, "Z")),
            ((2, "Y"), (7, "Y")),
        )
        for errors in cases:
            result = run_shor_trial(math.sqrt(0.3), math.sqrt(0.7), errors)
            self.assertFalse(result.classification.startswith("PASS"))

    def test_duplicate_qubit_and_invalid_pauli_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_shor_trial(1, 0, ((0, "X"), (0, "Z")))
        with self.assertRaises(ValueError):
            run_shor_trial(1, 0, ((0, "A"),))

    def test_campaign_is_deterministic_and_matches_pin(self) -> None:
        first = build_shor_campaign_certificate()
        second = build_shor_campaign_certificate()
        self.assertEqual(first, second)
        self.assertEqual(first["classification"], "PASS_BOUNDED_SHOR_QEC_V1")
        self.assertTrue(all(first["gates"].values()))
        self.assertEqual(first["counts"]["positive_trials"], 112)
        self.assertEqual(first["counts"]["single_report_fault_trials"], 648)
        expected = Path(__file__).with_name("EXPECTED_SHOR_CAMPAIGN.sha256")
        if expected.exists():
            self.assertEqual(
                first["certificate_sha256"],
                expected.read_text(encoding="utf-8").strip(),
            )


if __name__ == "__main__":
    unittest.main()
