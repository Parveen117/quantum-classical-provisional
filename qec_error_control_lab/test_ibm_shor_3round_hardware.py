from datetime import datetime, timezone
import unittest

from ibm_shor_3round_hardware import (
    EXPECTED,
    SHOTS,
    analyse_case,
    build_certificate,
    exact_report_majority,
    protocol_specification,
)
from capture_ibm_calibration_snapshot import build_snapshot, parse_ancilla_map


class FakeProperties:
    last_update_date = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)

    def t1(self, qubit):
        return (100 + qubit) * 1e-6

    def t2(self, qubit):
        return (150 + qubit) * 1e-6

    def readout_error(self, qubit):
        return 0.01 + qubit / 10000


class ThreeRoundHardwareTests(unittest.TestCase):
    def test_spec_is_exactly_three_rounds_without_recovery(self):
        spec = protocol_specification()
        self.assertEqual(spec["rounds_per_shot"], 3)
        self.assertEqual(spec["shots_per_case"], 4096)
        self.assertFalse(spec["hardware_recovery"])
        self.assertEqual([case["label"] for case in spec["cases"]], list(EXPECTED))

    def test_exact_report_majority(self):
        self.assertEqual(exact_report_majority(("a", "b", "a")), "a")
        self.assertIsNone(exact_report_majority(("a", "b", "c")))

    def test_case_analysis_tracks_deferred_and_stability(self):
        expected = EXPECTED["x_q0"]
        rounds = [
            [expected, expected, "00000000"],
            [expected, "00000000", "00000001"],
            [expected, "11111111", "00000010"],
        ]
        result = analyse_case("x_q0", rounds)
        self.assertEqual(result["shots"], 3)
        self.assertEqual(result["majority_ledger"]["counts"][expected], 1)
        self.assertAlmostEqual(result["majority_ledger"]["deferred_rate"], 2 / 3)
        self.assertAlmostEqual(result["round_stability"]["all_three_identical_rate"], 1 / 3)

    def test_passing_certificate_is_deterministic(self):
        cases = []
        for label, expected in EXPECTED.items():
            rounds = [[expected] * SHOTS for _ in range(3)]
            cases.append(analyse_case(label, rounds, ["0" * 9] * SHOTS))
        first = build_certificate(
            job_id="test-job", backend="ibm_marrakesh", cases=cases,
            submission_receipt_sha256="a" * 64
        )
        second = build_certificate(
            job_id="test-job", backend="ibm_marrakesh", cases=cases,
            submission_receipt_sha256="a" * 64
        )
        self.assertEqual(first, second)
        self.assertEqual(first["classification"], "PASS_BOUNDED_SHOR_3ROUND_HARDWARE_SYNDROME_V1")
        self.assertFalse(first["hardware_recovery"])

    def test_wrong_round_mode_fails(self):
        cases = []
        for label, expected in EXPECTED.items():
            rounds = [[expected] * SHOTS for _ in range(3)]
            if label == "no_error":
                rounds[2] = ["11111111"] * SHOTS
            cases.append(analyse_case(label, rounds))
        certificate = build_certificate(
            job_id="test-job", backend="ibm_marrakesh", cases=cases,
            submission_receipt_sha256="a" * 64
        )
        self.assertTrue(certificate["classification"].startswith("FAIL_"))

    def test_parse_ancilla_map(self):
        mapping = parse_ancilla_map("0:10,1:11,2:12,3:13,4:14,5:15,6:16,7:17")
        self.assertEqual(mapping["0"], 10)
        self.assertEqual(mapping["7"], 17)
        with self.assertRaises(ValueError):
            parse_ancilla_map("0:10,1:11")

    def test_calibration_snapshot_schema(self):
        mapping = {str(i): i + 20 for i in range(8)}
        snapshot = build_snapshot(
            job_id="da2raps3jnrc73ae9n80",
            backend_name="ibm_marrakesh",
            requested_time=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc),
            properties=FakeProperties(),
            ancilla_map=mapping,
        )
        self.assertEqual(snapshot["ancilla_map"], mapping)
        self.assertEqual(set(snapshot["qubits"]), {str(i) for i in range(20, 28)})
        for row in snapshot["qubits"].values():
            self.assertGreater(row["T1_us"], 0)
            self.assertGreater(row["T2_us"], 0)
            self.assertGreaterEqual(row["readout_error"], 0)
            self.assertLessEqual(row["readout_error"], 1)


if __name__ == "__main__":
    unittest.main()
