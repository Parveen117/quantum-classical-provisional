"""Cluster compilation of the pinned parity classifier: lemmas, exact end-to-end witness, controls, resources, codebook, grade."""
from fractions import Fraction
import unittest

from native_relational_qc.cyclotomic64 import ZERO
from phase_seam_foundation.cluster_compile import (
    EDGES, NODES, ORDER, XOR_CHECKPOINT, H2, circuit_probability, cluster_resources, compile_grade, compile_plan,
    gadget_lemma, heater_codebook, heater_setting, is_tree, neighbours, pattern, pattern_run, propagation_lemma,
    ry_lemma, witness, xor_witnesses,
)


class LemmaTests(unittest.TestCase):
    def test_gadget_identity_every_native_angle(self):
        for k in range(64):
            g = gadget_lemma(k)
            self.assertTrue(g["holds"], k)
            self.assertEqual(g["measurement_angle"], (-k) % 64)

    def test_pauli_propagation(self):
        self.assertTrue(propagation_lemma()["holds"])

    def test_ry_rewrite_every_native_angle(self):
        for k in range(64):
            r = ry_lemma(k)
            self.assertTrue(r["prep_holds"] and r["additive_holds"], k)


class PatternTests(unittest.TestCase):
    def test_tree_shape(self):
        self.assertTrue(is_tree())
        self.assertEqual((NODES, len(EDGES)), (13, 12))
        self.assertEqual(len(neighbours(6)), 4)
        self.assertEqual(len(neighbours(10)), 3)
        self.assertEqual(sum(1 for n in range(NODES) if len(neighbours(n)) == 1), 5)

    def test_angles_follow_the_rewrite(self):
        spec = pattern((5, 17), (3, 41, 22, 9, 50))
        self.assertEqual(spec["j_steps"][0], (5 + 3) % 64)
        self.assertEqual(spec["j_steps"][2], (17 + 41) % 64)
        self.assertEqual(spec["measurement_angles"][0], (-8) % 64)
        self.assertEqual(spec["measurement_angles"][12], (-50) % 64)
        self.assertEqual(spec["corrections"][5], dict(x=6, z=(7, 1, 3)))
        with self.assertRaises(ValueError):
            pattern((64, 0), (0, 0, 0, 0, 0))


class WitnessTests(unittest.TestCase):
    def test_xor_checkpoint_exact_on_all_inputs(self):
        rows = xor_witnesses()
        self.assertEqual(len(rows), 4)
        for r in rows:
            self.assertTrue(r["exact_equality"])
            self.assertEqual(r["predicted"], r["label"])
            self.assertEqual(r["p_one"], ZERO if r["label"] == 0 else H2 * H2 + H2 * H2)
            self.assertTrue(r["x_only_control_diverges"])

    def test_non_clifford_angles_exact(self):
        w = witness((5, 17), (3, 41, 22, 9, 50))
        self.assertTrue(w["exact_equality"])
        self.assertTrue(w["every_branch_weight_half"])
        self.assertEqual(w["branches_checked"], len(ORDER))
        self.assertTrue(w["control_no_corrections"]["outcome_dependent"])
        self.assertTrue(w["control_x_only"]["branches_diverge"])
        lo, hi = w["pattern_probability"].real_bounds(30)
        self.assertLess(lo, Fraction(142, 1000))
        self.assertGreater(hi, Fraction(141, 1000))

    def test_pattern_run_rules(self):
        with self.assertRaises(ValueError):
            pattern_run((0, 32), XOR_CHECKPOINT, rule="magic")
        self.assertEqual(circuit_probability((0, 32), XOR_CHECKPOINT), H2 * H2 + H2 * H2)


class ResourceTests(unittest.TestCase):
    def test_tree_cluster_costs(self):
        r0 = cluster_resources(0)
        self.assertEqual((r0["photons"], r0["edges"], r0["fusions"]), (13, 12, 7))
        self.assertEqual(r0["p_build_all"], Fraction(1, 128))
        self.assertEqual(r0["expected_bell_pairs_conditional_on_success"], Fraction(138, 5))
        r4 = cluster_resources(4)
        self.assertGreater(r4["p_build_all"], Fraction(1, 2))
        self.assertGreater(r4["expected_bell_pairs_conditional_on_success"], 200)
        with self.assertRaises(ValueError):
            cluster_resources(17)


class CodebookTests(unittest.TestCase):
    def test_every_angle_has_an_exact_heater_setting(self):
        for k in range(64):
            h = heater_setting(k)
            self.assertEqual(h["heaters"]["before"], (32 - k) % 64)
            self.assertEqual((h["heaters"]["lower"], h["heaters"]["upper"]), (16, 0))

    def test_training_touches_five_trims(self):
        book = heater_codebook((0, 32), XOR_CHECKPOINT)
        self.assertEqual((book["trained_heaters"], book["fixed_heaters"], book["detectors"]), (5, 5, 26))
        self.assertEqual([r["node"] for r in book["rows"] if r["trained"]], [0, 2, 4, 8, 12])


class GradeTests(unittest.TestCase):
    def test_fail_closed(self):
        self.assertEqual(compile_grade({})["grade"], "COMPILED")
        cluster = dict(evidence_class="LAB_RECORDED", photons=13, stabiliser_witnesses=12)
        self.assertEqual(compile_grade(dict(cluster=cluster))["grade"], "CLUSTER_RECORDED")
        self.assertEqual(compile_grade(dict(cluster=dict(cluster, stabiliser_witnesses=11)))["grade"], "COMPILED")
        self.assertEqual(compile_grade(dict(cluster=dict(cluster, evidence_class="SIMULATED")))["grade"], "COMPILED")
        rows = [dict(features=[0, 32], shots=1000, ones=990), dict(features=[0, 0], shots=1000, ones=12)]
        readout = dict(evidence_class="LAB_RECORDED", feedforward=True, parameters=list(XOR_CHECKPOINT), rows=rows)
        self.assertEqual(compile_grade(dict(cluster=cluster, readout=readout))["grade"], "PATTERN_RECORDED")
        bad = compile_grade(dict(cluster=cluster, readout=dict(readout, rows=[dict(features=[0, 32], shots=1000, ones=600)])))
        self.assertEqual(bad["grade"], "CLUSTER_RECORDED")
        self.assertEqual(compile_grade(dict(cluster=cluster, readout=dict(readout, feedforward=False)))["grade"], "CLUSTER_RECORDED")
        self.assertEqual(compile_grade(dict(cluster=cluster, readout=readout, trained_on_chip=True))["grade"], "REJECTED")
        self.assertEqual(compile_grade(dict(quantum_advantage=True))["grade"], "REJECTED")
        with self.assertRaises(ValueError):
            compile_grade(dict(cluster=cluster, readout=dict(readout, tolerance="1")))

    def test_plan_declares_what_is_never_claimed(self):
        plan = compile_plan()
        self.assertEqual(plan["status"], "COMPILED_NO_DEVICE")
        self.assertIn("QUANTUM_ADVANTAGE", plan["claims"]["never"])
        self.assertEqual(plan["one_shot_build"], "1/128")


if __name__ == "__main__":
    unittest.main()
