"""Circuit semantics, true reset, exact negative controls and honest failure states."""
from collections import Counter
import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

from native_relational_qc.calculator import calculate, run_calculation, validate
from native_relational_qc.certify import exact_value
from native_relational_qc import delta_ogmt as d


def solve(history, mode="M3", variant="nominal"):
    request, encoding = d.build_request(history, mode, variant)
    result = calculate(request)
    if result["status"] != "completed":
        raise AssertionError(result)
    return request, encoding, result


class DeltaOGMTTests(unittest.TestCase):
    def test_observer_reconstruction_matches_all_sixteen_explicit_rotations(self):
        from fractions import Fraction
        from native_relational_qc.delta_ogmt_observer import probability_at_angle, rotated_request
        from native_relational_qc.phase_interop import phase_operations
        ops = [["h", [0]]]
        ops += [[name, list(qs)] for name, qs in phase_operations(Fraction(3, 16), (0,))]
        ops += [["h", [0]]]
        request = dict(schema="nrqc-calculator-v1", backend="cyclotomic_pow2", n_qubits=1,
                       operations=ops, queries=[dict(id=p, kind="expectation", paulis={"0": p}) for p in ("Y", "Z")])
        moments = {a["id"]: exact_value(a["value"]["exact"]) for a in calculate(request)["answers"]}
        request["queries"] = [dict(id="p", kind="probability", outcomes={"0": 1})]
        for steps in range(16):
            with self.subTest(steps=steps):
                actual = exact_value(calculate(rotated_request(request, steps, wire=0))["answers"][0]["value"]["exact"])
                self.assertEqual(actual, probability_at_angle(moments["Y"], moments["Z"], steps))

    def test_same_pulse_multiset_and_endpoints_are_enforced_in_campaign(self):
        a, b = d.HISTORIES.values()
        self.assertNotEqual(a, b)
        self.assertEqual(Counter(a), Counter(b))
        self.assertEqual((a[0], a[-1]), (b[0], b[-1]))
        for mode in d.MODES:
            left, _ = d.build_request(a, mode)
            right, _ = d.build_request(b, mode)
            validate(left)
            validate(right)
            counts = lambda request: Counter((name, tuple(qs)) for name, qs in request["operations"])
            self.assertEqual(counts(left), counts(right))
            self.assertEqual(d.digest(left), d.digest(d.build_request(a, mode)[0]))

    def test_edge_intervention_removes_only_the_designated_coupling(self):
        full, meta = d.build_request("ABAB")
        cut, altered = d.build_request("ABAB", "E_CA")
        self.assertEqual(altered["coupling_edges"], [e for e in meta["coupling_edges"] if e[0] != "CA"])
        self.assertEqual(meta["active_memory_wires"], altered["active_memory_wires"])
        counts = lambda request: Counter((name, tuple(qs)) for name, qs in request["operations"])
        self.assertEqual(counts(full) - counts(cut), Counter({("cp8", (2, 0)): 6}))
        self.assertFalse(counts(cut) - counts(full))

    def test_negative_controls_have_exact_zero_separation(self):
        cases = [("M0", "nominal")] + [("M3", variant) for variant in d.NEGATIVE]
        for mode, variant in cases:
            with self.subTest(mode=mode, variant=variant):
                left = solve("ABAB", mode, variant)[2]
                right = solve("AABB", mode, variant)[2]
                summary = d.pair_summary(left, right)
                self.assertEqual(exact_value(summary["drain_gap"]["exact"]), 0)
                if variant in ("equal_inputs", "commuting_updates"):
                    for key in ("core_distribution_TV", "memory_distribution_TV"):
                        self.assertEqual(exact_value(summary[key]["exact"]), 0)

    def test_swap_to_fresh_environment_is_reset_not_postselection(self):
        # Bell pair: tracing/resetting q1 must preserve q0's mixed marginal.
        request = dict(schema="nrqc-calculator-v1", backend="cyclotomic_pow2", n_qubits=3,
                       operations=[["h", [0]], ["cx", [0, 1]], ["swap", [1, 2]]],
                       queries=[dict(id="state", kind="distribution", qubits=[0, 1])])
        probabilities = calculate(request)["answers"][0]["probabilities"]
        from fractions import Fraction
        self.assertEqual({k: exact_value(v["exact"]) for k, v in probabilities.items()},
                         {"00": Fraction(1, 2), "01": 0, "10": Fraction(1, 2), "11": 0})
        for variant, wires in d.RESETS.items():
            request, metadata = d.build_request("ABAB", variant=variant)
            self.assertEqual(request["n_qubits"], 7 + len(wires))
            self.assertEqual(len(metadata["reset_operation_indices"]), len(wires))
            for query in request["queries"]:
                self.assertFalse(set(query["qubits"]) & set(metadata["reset_environment_wires"]))

    def test_invalid_requests_are_rejected(self):
        for history in ("", "AAA", "ABCDE", "AAAX", True, None):
            with self.subTest(history=history), self.assertRaises(ValueError):
                d.build_request(history)
        for kwargs in (dict(mode="unknown"), dict(variant="unknown"), dict(mode="M1", variant="reset_C1")):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                d.build_request("ABAB", **kwargs)

    def test_incomplete_results_cannot_be_summarized_or_verified(self):
        request, _ = d.build_request("ABAB")
        failed = run_calculation(request, timeout_seconds=1e-9)
        self.assertEqual(failed["status"], "time_limit")
        with self.assertRaises(ValueError):
            d.pair_summary(failed, failed)
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            path = Path(directory) / "audit"
            report = d.audit(path, timeout_seconds=1e-9)
            self.assertEqual(report["status"], "incomplete")
            self.assertFalse(report["verification_passed"])
            self.assertEqual(report["completed_cases"], 0)
            self.assertFalse(report["pairs"])
            self.assertEqual(len(list((path / "inputs").glob("*.json"))), 24)
            with self.assertRaises(FileExistsError):
                d.audit(path)

    @unittest.skipUnless(importlib.util.find_spec("qiskit"), "optional Qiskit reference")
    def test_independent_numeric_evolution_and_true_resets(self):
        for variant in ("nominal", *d.RESETS):
            with self.subTest(variant=variant):
                request, encoding, result = solve("ABAB", variant=variant)
                check = d.compare_qiskit(request, encoding, result)
                self.assertTrue(check["passed"], check)
                if variant in d.RESETS:
                    self.assertEqual(check["reference"], "DensityMatrix with reset")


if __name__ == "__main__":
    unittest.main()
