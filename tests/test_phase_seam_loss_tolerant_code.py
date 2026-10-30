"""Tree code: stabiliser checks, exact recovery polynomials, controls, crossover, encoded walk, grade."""
from fractions import Fraction
import unittest

from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.loss_tolerant_code import (
    check_code, code, code_grade, crossover, effective_memory, encoded_walk, evaluate, loss_polynomials, recoverable, tree,
)

P22, P33 = loss_polynomials([2, 2]), loss_polynomials([3, 3])


class CodeTests(unittest.TestCase):
    def test_tree_shapes(self):
        parent, level = tree([2, 3])
        self.assertEqual(len(parent), 8)
        self.assertEqual(level.count(0), 2)
        self.assertEqual(level.count(1), 6)
        with self.assertRaises(ResourceLimit):
            tree([5, 4])
        with self.assertRaises(ValueError):
            tree([0])

    def test_stabilisers_commute_and_encode_one_qubit(self):
        for br in ([1], [2], [3], [2, 2], [2, 3], [3, 2], [3, 3]):
            c = check_code(code(br))
            self.assertTrue(c["commute"] and c["one_logical_qubit"], br)

    def test_recovery_examples(self):
        c = code([2, 2])
        self.assertTrue(recoverable(c["z_logical"], c["stabilisers"], 1 << 0))        # lose one level-1 photon
        self.assertTrue(recoverable(c["x_logical"], c["stabilisers"], 1 << 0))
        self.assertFalse(recoverable(c["z_logical"], c["stabilisers"], (1 << 1) | (1 << 2) | (1 << 3)))
        self.assertTrue(recoverable(c["z_logical"], c["stabilisers"], 0))


class PolynomialTests(unittest.TestCase):
    def test_bare_and_repetition_controls(self):
        bare = loss_polynomials([1])
        self.assertEqual(evaluate(bare, Fraction(1, 10))["p_both"], Fraction(9, 10))
        rep = loss_polynomials([3])
        e = evaluate(rep, Fraction(1, 10))
        self.assertEqual(e["p_z"], 1 - Fraction(1, 10) ** 3)                    # Z protected by repetition
        self.assertEqual(e["p_x"], Fraction(9, 10) ** 3)                        # X needs every photon
        self.assertFalse(e["beats_bare_both"])

    def test_tree_counts_and_values(self):
        self.assertEqual(P22["counts"]["both"], [1, 6, 6, 0, 0, 0, 0])
        self.assertEqual(P33["counts"]["both"][:4], [1, 12, 66, 156])
        e = evaluate(P33, Fraction(1, 10))
        self.assertGreater(e["p_both"], Fraction(95, 100))
        self.assertTrue(e["beats_bare_both"])
        self.assertEqual(evaluate(P33, 0)["p_both"], 1)
        self.assertEqual(evaluate(P33, 1)["p_both"], 0)
        with self.assertRaises(ValueError):
            evaluate(P33, 2)

    def test_crossover_brackets(self):
        c = crossover([3, 3])
        lo, hi = c["crossover_bounds"]
        self.assertTrue(Fraction(19, 100) < lo < hi < Fraction(20, 100))
        self.assertTrue(evaluate(P33, lo)["beats_bare_both"])
        self.assertFalse(evaluate(P33, hi)["beats_bare_both"])
        self.assertFalse(crossover([2])["beats_bare_at_small_loss"])            # repetition never beats bare on both


class WalkTests(unittest.TestCase):
    def test_effective_memory_and_encoded_walk(self):
        e = effective_memory([3, 3], Fraction(9, 10))
        self.assertEqual(e["m_eff"], evaluate(P33, Fraction(1, 10))["p_both"])
        w = encoded_walk(16, [3, 3], Fraction(9, 10))
        self.assertLessEqual(w["m_eff_floored"], w["m_eff"])
        self.assertGreater(w["p_reach_encoded_lower_bound"], 100 * w["p_reach_bare"])
        self.assertEqual(w["photons_in_register"], 192)


SITE = dict(evidence_class="LAB_RECORDED", branching=[2, 2], stabiliser_witnesses=5)
REC = dict(evidence_class="LAB_RECORDED", epsilon="1/10", p_x="99/100", p_z="9/10", removed_photon=True)


class GradeTests(unittest.TestCase):
    def test_grade_climbs_and_negative_controls(self):
        self.assertEqual(code_grade({})["grade"], "CODE_DECLARED")
        self.assertEqual(code_grade(dict(encoded_site=SITE))["grade"], "ENCODED_SITE_RECORDED")
        self.assertEqual(code_grade(dict(encoded_site=SITE, recovery=REC))["grade"], "CODE_QUALIFIED")
        low = code_grade(dict(encoded_site=SITE, recovery=dict(REC, p_z="1/2")))
        self.assertEqual(low["grade"], "LOSS_RECOVERY_RECORDED")
        self.assertEqual(code_grade(dict(encoded_site=SITE, recovery=dict(REC, removed_photon=False)))["grade"], "ENCODED_SITE_RECORDED")
        self.assertEqual(code_grade(dict(encoded_site=dict(SITE, evidence_class="SIMULATED"), recovery=REC))["grade"], "CODE_DECLARED")
        with self.assertRaises(ValueError):
            code_grade(3)


if __name__ == "__main__":
    unittest.main()
