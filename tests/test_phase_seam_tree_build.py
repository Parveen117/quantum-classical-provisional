"""Tree-site build: star growth cost, attachment law, storage survival PGF, site cost, net benefit, grade."""
from fractions import Fraction
import unittest

from phase_seam_foundation.tree_build import (
    BELL_PAIRS_PER_GHZ3, attachments, build_grade, net_benefit, site_build, star, storage_survival,
)


class StarTests(unittest.TestCase):
    def test_star_costs(self):
        self.assertEqual(star(2)["expected_bell_pairs"], 1)
        self.assertEqual(star(3)["expected_bell_pairs"], BELL_PAIRS_PER_GHZ3)
        s4 = star(4)
        self.assertEqual((s4["p_reach"], s4["expected_attempts"], s4["expected_bell_pairs"]), (Fraction(6, 7), 2, 12))
        self.assertEqual(star(8)["expected_bell_pairs"], Fraction(292, 9))
        with self.assertRaises(ValueError):
            star(1)


class AttachmentTests(unittest.TestCase):
    def test_negative_binomial_law(self):
        a0 = attachments(4, 0)
        self.assertEqual(a0["p_build"], Fraction(1, 16))                       # no spare leaf: every fusion must succeed
        a4 = attachments(4, 4)
        self.assertEqual(a4["p_build"], Fraction(163, 256))
        self.assertGreater(attachments(4, 8)["p_build"], Fraction(9, 10))
        self.assertEqual(attachments(1, 0)["p_build"], Fraction(1, 2))
        self.assertEqual(attachments(4, 0)["expected_blocks_consumed"], 4)
        self.assertGreater(a4["expected_blocks_consumed"], 4)
        # monotone in spare and tends to 1
        p = [attachments(4, r)["p_build"] for r in (0, 2, 4, 8, 16)]
        self.assertTrue(all(x < y for x, y in zip(p, p[1:])) and p[-1] > Fraction(99, 100))

    def test_storage_survival_controls(self):
        self.assertEqual(storage_survival(4, 4, 4, 9, 1)["survival_given_success_lower_bound"], 1)        # lossless memory
        s = storage_survival(4, 4, 4, 9, Fraction(99, 100))
        self.assertTrue(0 < s["survival_given_success_lower_bound"] < 1)
        self.assertEqual(s["p_build"], Fraction(163, 256))
        worse = storage_survival(4, 4, 4, 9, Fraction(9, 10))["survival_given_success_lower_bound"]
        self.assertLess(worse, s["survival_given_success_lower_bound"])
        # with no spare leaves every attachment succeeds first time: survival is the deterministic product
        d = storage_survival(2, 0, 4, 3, Fraction(1, 2))
        self.assertEqual(d["survival_given_success_lower_bound"], Fraction(1, 2) ** 3 * Fraction(1, 2) ** 7)


class SiteTests(unittest.TestCase):
    def test_site_build_numbers(self):
        s = site_build([4, 3], 4, Fraction(99, 100))
        self.assertEqual(s["photons_in_site"], 16)
        self.assertEqual(s["p_attach_all"], Fraction(163, 256))
        self.assertGreater(s["expected_bell_pairs_per_site_lower_bound"], 100)
        self.assertLess(s["expected_bell_pairs_per_site_lower_bound"], 200)
        self.assertEqual(site_build([4, 3], 4, 1)["build_storage_survival_lower_bound"], 1)

    def test_net_benefit_one_shot_fails_and_multiplexed_pays(self):
        nb = net_benefit(16, [4, 3], 4, Fraction(99, 100))
        self.assertFalse(nb["one_shot"]["pays"])                                   # a second cliff
        self.assertTrue(nb["site_multiplexed"]["pays"])
        self.assertGreater(nb["site_multiplexed"]["bell_pairs_per_delivered_site"], 400)
        self.assertLess(nb["site_multiplexed"]["bell_pairs_per_delivered_site"], 700)
        slow = net_benefit(16, [4, 3], 4, Fraction(9, 10))
        self.assertGreater(slow["site_multiplexed"]["bell_pairs_per_delivered_site"], 10 ** 5)   # m = 0.9: infeasible
        self.assertTrue(slow["site_multiplexed"]["pays"])                           # the walk still gains, at that price


BLOCK = dict(evidence_class="LAB_RECORDED", size=4, ghz_witness="9/10", rule="exactly one click per site")
ATT = dict(evidence_class="LAB_RECORDED", heralded=True, stabiliser_witness="9/10", success_rate="12/25",
           storage_survival="2/5", declared_survival="2/5")


class GradeTests(unittest.TestCase):
    def test_grade_climbs_and_negative_controls(self):
        self.assertEqual(build_grade({})["grade"], "BUILD_DECLARED")
        self.assertEqual(build_grade(dict(block=BLOCK))["grade"], "BLOCK_RECORDED")
        self.assertEqual(build_grade(dict(block=BLOCK, attachment=ATT))["grade"], "BUILD_QUALIFIED")
        self.assertEqual(build_grade(dict(block=BLOCK, attachment=dict(ATT, success_rate="1/4")))["grade"], "ATTACHMENT_RECORDED")
        self.assertEqual(build_grade(dict(block=BLOCK, attachment=dict(ATT, storage_survival="1/4")))["grade"], "ATTACHMENT_RECORDED")
        self.assertEqual(build_grade(dict(block=BLOCK, attachment=dict(ATT, heralded=False)))["grade"], "BLOCK_RECORDED")
        self.assertEqual(build_grade(dict(block=dict(BLOCK, rule="any click"), attachment=ATT))["grade"], "BUILD_DECLARED")
        with self.assertRaises(ValueError):
            build_grade("x")


if __name__ == "__main__":
    unittest.main()
