"""Chain memory: exact lossy-memory walk, Theorem M1 bound, tree law, fibre table, joint design point, memory grade."""
from fractions import Fraction
import unittest

from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.chain_memory import (
    design_point, fibre_delay_table, memory_grade, memory_walk, theorem_M1_bound, tree_survival,
)


class MemoryWalkTests(unittest.TestCase):
    def test_lossless_memory_recovers_the_v022_walk(self):
        self.assertEqual(memory_walk(4, 1)["p_reach_target"], Fraction(6, 7))
        self.assertEqual(memory_walk(8, 1)["p_reach_target"], Fraction(7, 9))
        self.assertEqual(memory_walk(32, 1)["p_reach_target"], Fraction(2207, 2889))

    def test_smallest_case_closed_form(self):
        # from 3 to 4 with memory m: first attempt survives with m^3, succeeds with 1/2; failure drops to 2, etc.
        m = Fraction(9, 10)
        w = memory_walk(4, m)
        self.assertLess(w["p_reach_target"], Fraction(6, 7))
        self.assertGreater(w["p_reach_target"], m ** 3 / 2)                   # at least the immediate success
        self.assertEqual(memory_walk(4, 0)["p_reach_target"], 0)               # no memory: nothing survives

    def test_monotone_in_memory_and_in_target(self):
        for n in (8, 16):
            p = [memory_walk(n, m)["p_reach_target"] for m in (Fraction(9, 10), Fraction(99, 100), 1)]
            self.assertTrue(p[0] < p[1] < p[2])
        p = [memory_walk(n, Fraction(99, 100))["p_reach_target"] for n in (4, 8, 16, 32)]
        self.assertTrue(p[0] > p[1] > p[2] > p[3])
        with self.assertRaises(ResourceLimit):
            memory_walk(300, Fraction(99, 100))


class TheoremM1Tests(unittest.TestCase):
    def test_bound_dominates_the_exact_walk(self):
        for m in (Fraction(9, 10), Fraction(99, 100), Fraction(999, 1000)):
            for n in (4, 5, 8, 16, 32, 64):
                self.assertLessEqual(memory_walk(n, m)["p_reach_target"], theorem_M1_bound(n, m)["bound"])

    def test_exponent_is_quadratic(self):
        self.assertEqual(theorem_M1_bound(5, Fraction(1, 2))["exponent"], 3)          # J = 1
        self.assertEqual(theorem_M1_bound(7, Fraction(1, 2))["exponent"], 8)          # J = 2: 3 + 5
        self.assertEqual(theorem_M1_bound(9, Fraction(1, 2))["exponent"], 15)         # J = 3: 3 + 5 + 7
        self.assertEqual(theorem_M1_bound(2056, Fraction(1, 2))["exponent"], 3 * 1027 + 1027 * 1026)
        self.assertEqual(theorem_M1_bound(3, Fraction(1, 2))["bound"], 1)             # nothing to do

    def test_tree_is_exponential_not_quadratic(self):
        t = tree_survival(16, Fraction(99, 100))
        self.assertEqual((t["depth"], t["exponent"]), (4, 64))
        self.assertEqual(t["survival"], Fraction(99, 100) ** 64)
        big = tree_survival(2056, Fraction(999, 1000))
        self.assertEqual(big["exponent"], 2056 * 12)                                # ceil(log2 2056) = 12
        self.assertLess(big["survival_approx"], 1e-10)
        # at m = 99/100 and N = 64 the tree beats the chain by orders of magnitude
        self.assertGreater(tree_survival(64, Fraction(99, 100))["survival_approx"], float(memory_walk(64, Fraction(99, 100))["p_reach_target"]) * 1e6)
        with self.assertRaises(ValueError):
            tree_survival(0, Fraction(1, 2))


class DesignTests(unittest.TestCase):
    def test_fibre_table_is_declared_and_monotone(self):
        rows = fibre_delay_table()
        self.assertEqual(rows[0]["fibre_length_m"], "20")
        self.assertEqual(rows[2]["loss_db"], "4")
        self.assertTrue(rows[0]["memory_approx"] > rows[1]["memory_approx"] > rows[2]["memory_approx"])

    def test_design_point_feasibility(self):
        small = design_point(64, "1/2")
        self.assertTrue(small["feasible"])
        self.assertEqual(small["best"]["x"], Fraction(1, 40))                 # g2 cap 1/10 at herald efficiency 1/2 excludes x >= 1/20
        self.assertTrue(all(r["within_budget"] for r in small["rows"]))
        big_thr = design_point(2056, "1/2", eta_site="1/2", dark_per_mode="1/1000000")
        self.assertFalse(big_thr["feasible"])                                  # threshold readout: no x works
        big_nr = design_point(2056, "1/2", readout="number_resolving", eta_site="1/2", dark_per_mode="1/1000000")
        self.assertTrue(big_nr["feasible"])
        self.assertEqual(big_nr["best"]["x"], Fraction(1, 40))
        strict = design_point(64, "1/2", max_g2="1/100")
        self.assertEqual(strict["best"]["x"], Fraction(1, 400))               # only the smallest x keeps g2 <= 1/100


DELAY = dict(evidence_class="LAB_RECORDED", transmission_per_attempt="9/10")
CHAIN = dict(evidence_class="LAB_RECORDED", sites=3, survival="7/10", rule="exactly one click per site",
             witness_after_storage="9/10", source_visibility="9/10")


class GradeTests(unittest.TestCase):
    def test_grade_climbs_and_negative_controls(self):
        self.assertEqual(memory_grade({})["grade"], "MEMORY_DECLARED")
        self.assertEqual(memory_grade(dict(delay=DELAY))["grade"], "DELAY_LOSS_RECORDED")
        self.assertEqual(memory_grade(dict(delay=DELAY, stored_chain=CHAIN))["grade"], "MEMORY_QUALIFIED")   # 0.7 >= 0.729 * 0.9
        low = memory_grade(dict(delay=DELAY, stored_chain=dict(CHAIN, survival="1/2")))
        self.assertEqual(low["grade"], "STORED_CHAIN_RECORDED")
        self.assertEqual(memory_grade(dict(delay=DELAY, stored_chain=dict(CHAIN, sites=2)))["grade"], "DELAY_LOSS_RECORDED")
        self.assertEqual(memory_grade(dict(delay=DELAY, stored_chain=dict(CHAIN, rule="any click")))["grade"], "DELAY_LOSS_RECORDED")
        self.assertEqual(memory_grade(dict(delay=DELAY, stored_chain=dict(CHAIN, witness_after_storage="4/5")))["grade"], "STORED_CHAIN_RECORDED")
        self.assertEqual(memory_grade(dict(delay=dict(DELAY, evidence_class="MODELLED"), stored_chain=CHAIN))["grade"], "MEMORY_DECLARED")
        with self.assertRaises(ValueError):
            memory_grade(0)


if __name__ == "__main__":
    unittest.main()
