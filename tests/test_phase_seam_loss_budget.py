"""Loss budget: exact stage product, survival law, Theorem L1 false-herald law (engine-checked), fail-closed grade."""
from fractions import Fraction
import unittest

from native_relational_qc.cyclotomic64 import ONE
from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.loss_budget import (
    DECLARED_STAGES, budget, false_herald_law, fusion_chain_fidelity, loss_grade, loss_plan, lossy_fusion_from_engine,
    site_survival,
)


class BudgetTests(unittest.TestCase):
    def test_declared_budget_is_exact_product(self):
        b = budget()
        self.assertEqual(b["eta"], Fraction(243, 4000))
        self.assertEqual(len(b["stages"]), 6)
        self.assertEqual(budget((("a", Fraction(1, 2)), ("b", Fraction(1, 2))))["eta"], Fraction(1, 4))
        with self.assertRaises(ValueError):
            budget((("a", Fraction(3, 2)),))
        with self.assertRaises(TypeError):
            budget((("a", 0.5),))

    def test_survival_law(self):
        s = site_survival(Fraction(243, 4000), 3)
        self.assertEqual(s["all_survive"], Fraction(243, 4000) ** 3)
        self.assertEqual(site_survival(1, 50)["all_survive"], 1)
        with self.assertRaises(ResourceLimit):
            site_survival(Fraction(1, 2), 5000)


class FalseHeraldTests(unittest.TestCase):
    def test_closed_form_values(self):
        f = false_herald_law(Fraction(3, 5))
        self.assertEqual((f["p_one_click"], f["p_genuine"], f["genuine_fraction"], f["false_herald_fraction"]),
                         (Fraction(21, 50), Fraction(3, 10), Fraction(5, 7), Fraction(2, 7)))
        self.assertEqual(false_herald_law(1)["false_herald_fraction"], 0)
        self.assertEqual(false_herald_law(1)["p_one_click"], Fraction(1, 2))
        with self.assertRaises(ValueError):
            false_herald_law(0)

    def test_engine_confirms_law_at_eta_one_half(self):
        r = lossy_fusion_from_engine(8)
        self.assertTrue(r["matches_closed_form"])
        self.assertEqual(r["total"], ONE)
        self.assertEqual(r["genuine_fraction"].real_bounds(8)[0], Fraction(2, 3))
        self.assertEqual(r["probabilities"][(1, 1)].real_bounds(8)[0], Fraction(1, 8))   # the false heralds

    def test_engine_confirms_law_at_irrational_eta(self):
        r = lossy_fusion_from_engine(4)   # eta = cos^2(pi/8) = (2 + sqrt 2)/4, not rational
        self.assertTrue(r["matches_closed_form"])
        self.assertEqual(r["total"], ONE)

    def test_chain_fidelity(self):
        c = fusion_chain_fidelity(Fraction(3, 5), 2)
        self.assertEqual(c["all_genuine"], Fraction(25, 49))
        self.assertEqual(fusion_chain_fidelity(1, 10)["all_genuine"], 1)
        self.assertEqual(fusion_chain_fidelity(Fraction(1, 2), 0)["all_genuine"], 1)


STAGES = {n: dict(evidence_class="LAB_RECORDED", transmission=str(t)) for n, t in DECLARED_STAGES}
E2E = dict(evidence_class="LAB_RECORDED", efficiency="243/4000")


class GradeTests(unittest.TestCase):
    def test_plan_is_declared(self):
        p = loss_plan(4)
        self.assertEqual(p["status"], "BUDGET_DECLARED")
        self.assertEqual(p["eta_per_site"], "243/4000")
        self.assertEqual(p["all_heralds_genuine"], "25/49")
        self.assertEqual(loss_grade(p)["grade"], "BUDGET_DECLARED")

    def test_grade_climbs(self):
        self.assertEqual(loss_grade({})["grade"], "BUDGET_DECLARED")
        self.assertEqual(loss_grade(dict(stages=STAGES))["grade"], "STAGES_RECORDED")
        r = loss_grade(dict(stages=STAGES, end_to_end=E2E))
        self.assertEqual((r["grade"], r["reasons"]), ("BUDGET_CONSISTENT", []))

    def test_negative_controls(self):
        missing = dict(STAGES); missing.pop("fibre to chip facet")
        self.assertEqual(loss_grade(dict(stages=missing, end_to_end=E2E))["grade"], "BUDGET_DECLARED")
        synthetic = dict(STAGES, **{"fibre to chip facet": dict(evidence_class="SYNTHETIC", transmission="1/2")})
        self.assertEqual(loss_grade(dict(stages=synthetic, end_to_end=E2E))["grade"], "BUDGET_DECLARED")
        too_good = dict(stages=STAGES, end_to_end=dict(E2E, efficiency="1/10"))      # exceeds stage product
        self.assertEqual(loss_grade(too_good)["grade"], "END_TO_END_RECORDED")
        too_bad = dict(stages=STAGES, end_to_end=dict(E2E, efficiency="1/100"))
        self.assertEqual(loss_grade(too_bad)["grade"], "END_TO_END_RECORDED")
        self.assertEqual(loss_grade(dict(stages=STAGES, end_to_end=dict(E2E, evidence_class="MODELLED")))["grade"], "STAGES_RECORDED")
        with self.assertRaises(ValueError):
            loss_grade([])


if __name__ == "__main__":
    unittest.main()
