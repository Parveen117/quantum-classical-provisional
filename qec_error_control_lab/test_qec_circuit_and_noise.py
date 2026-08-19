from __future__ import annotations

import math
from pathlib import Path
import unittest

from qec_circuit_spec import (
    QiskitUnavailable,
    build_circuit_specification,
    credential_free_ibm_plan,
    cross_check_encoding_spec,
    materialize_qiskit_experiment,
    qiskit_available,
    shor_encoding_operations,
    shor_syndrome_operations,
)
from qec_noise_benchmark import (
    build_noise_benchmark_certificate,
    shor_conservative_success,
    shor_weight_zero_or_one_success,
    three_round_exact_majority_probability,
    unencoded_process_success,
)
from qec_repetition import named_logical_states


class CircuitSpecificationTests(unittest.TestCase):
    def test_encoding_spec_matches_exact_shor_codewords(self) -> None:
        self.assertTrue(cross_check_encoding_spec(named_logical_states().values()))

    def test_expected_encoder_gate_counts(self) -> None:
        operations = shor_encoding_operations()
        self.assertEqual(sum(item.gate == "h" for item in operations), 3)
        self.assertEqual(sum(item.gate == "cx" for item in operations), 8)

    def test_expected_syndrome_network_gate_counts(self) -> None:
        operations = shor_syndrome_operations()
        self.assertEqual(sum(item.gate == "h" for item in operations), 4)
        self.assertEqual(sum(item.gate == "cx" for item in operations), 24)

    def test_circuit_specification_matches_pin(self) -> None:
        specification = build_circuit_specification()
        expected_path = Path(__file__).with_name("EXPECTED_CIRCUIT_SPEC.sha256")
        if expected_path.exists():
            self.assertEqual(
                specification["spec_sha256"],
                expected_path.read_text(encoding="utf-8").strip(),
            )

    def test_qiskit_adapter_is_explicitly_optional(self) -> None:
        if qiskit_available():
            circuit = materialize_qiskit_experiment(1, 0, injected_error=(4, "Y"))
            self.assertEqual(circuit.num_qubits, 17)
            self.assertEqual(circuit.num_clbits, 17)
        else:
            with self.assertRaises(QiskitUnavailable):
                materialize_qiskit_experiment()

    def test_ibm_plan_never_submits_or_contains_token(self) -> None:
        plan = credential_free_ibm_plan()
        self.assertFalse(plan["submission_performed"])
        self.assertNotIn("token", {key.lower() for key in plan})


class NoiseBenchmarkTests(unittest.TestCase):
    def test_zero_noise_is_exact(self) -> None:
        self.assertEqual(unencoded_process_success(0), 1.0)
        self.assertEqual(shor_weight_zero_or_one_success(0), 1.0)
        self.assertEqual(three_round_exact_majority_probability(0), 1.0)

    def test_single_error_scaling_improves_at_one_percent(self) -> None:
        self.assertGreater(shor_weight_zero_or_one_success(0.01), unencoded_process_success(0.01))

    def test_overhead_negative_control_at_four_percent(self) -> None:
        self.assertLess(shor_weight_zero_or_one_success(0.04), unencoded_process_success(0.04))

    def test_report_noise_reduces_conservative_success(self) -> None:
        self.assertLess(shor_conservative_success(0.01, 0.01), shor_conservative_success(0.01, 0))

    def test_invalid_probability_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            shor_weight_zero_or_one_success(-0.1)
        with self.assertRaises(ValueError):
            three_round_exact_majority_probability(1.1)

    def test_noise_certificate_is_deterministic_and_pinned(self) -> None:
        first = build_noise_benchmark_certificate()
        second = build_noise_benchmark_certificate()
        self.assertEqual(first, second)
        self.assertEqual(
            first["classification"], "PASS_BOUNDED_PHENOMENOLOGICAL_NOISE_V1"
        )
        self.assertTrue(all(first["gates"].values()))
        expected_path = Path(__file__).with_name("EXPECTED_NOISE_BENCHMARK.sha256")
        if expected_path.exists():
            self.assertEqual(
                first["certificate_sha256"],
                expected_path.read_text(encoding="utf-8").strip(),
            )


if __name__ == "__main__":
    unittest.main()
