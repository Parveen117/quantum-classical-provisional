"""Native ledger treatment of loss: Theorem L2 (engine), Kraus completeness, native grid, rate law, dark counts, grade."""
from fractions import Fraction
import unittest

from native_relational_qc.cyclotomic64 import ONE, ZERO
from phase_seam_foundation.loss_ledger import (
    charge_ledger, dark_count_table, kraus_completeness, ledger_grade, native_transmission_grid, nearest_grid_point,
    rate_not_fidelity,
)

LEDGER_8 = charge_ledger(8)          # eta_d = 1/2, computed once
LEDGER_4 = charge_ledger(4)          # eta_d = cos^2(pi/8), irrational


class TheoremL2Tests(unittest.TestCase):
    def test_L2a_charge_identity_on_every_outcome(self):
        for r in (LEDGER_8, LEDGER_4):
            self.assertTrue(r["charge_identity"])
            self.assertEqual(r["total"], ONE)

    def test_L2b_false_heralds_are_exactly_the_empty_middle_site(self):
        for r in (LEDGER_8, LEDGER_4):
            self.assertTrue(r["false_heralds_have_empty_middle_site"])
            self.assertTrue(r["genuine_heralds_fill_every_site"])
        self.assertEqual(LEDGER_8["rejected_false_heralds"].real_bounds(8)[0], Fraction(1, 8))
        self.assertEqual(LEDGER_8["accepted_probability"].real_bounds(8)[0], Fraction(1, 4))
        self.assertEqual(LEDGER_8["missed_genuine"].real_bounds(8)[0], Fraction(1, 4))

    def test_L2c_witness_after_readout_is_one_at_any_efficiency(self):
        for r in (LEDGER_8, LEDGER_4):
            self.assertTrue(r["witness_is_one"])
            self.assertEqual({w["heralded_phase_steps"] for w in r["witness_after_readout"].values()}, {48, 16})

    def test_negative_control_the_lossless_case_has_no_rejected_class(self):
        r = charge_ledger(0)
        self.assertEqual(r["rejected_false_heralds"], ZERO)
        self.assertEqual(r["missed_genuine"], ZERO)
        self.assertTrue(r["witness_is_one"])


class ChannelAndGridTests(unittest.TestCase):
    def test_kraus_completeness_is_exact_on_the_native_grid(self):
        for k in (0, 4, 8, 12, 16):
            self.assertTrue(kraus_completeness(k)["complete"])

    def test_native_grid_is_monotone_and_bracketed(self):
        rows = native_transmission_grid()
        self.assertEqual(rows[0]["eta"], ONE)
        self.assertEqual(rows[16]["eta"], ZERO)
        self.assertEqual(len(rows), 17)
        self.assertEqual(rows[8]["eta"].real_bounds(8)[0], Fraction(1, 2))
        for a, b in zip(rows, rows[1:]):
            self.assertGreaterEqual(a["lower"], b["upper"] - Fraction(1, 1 << 14))

    def test_nearest_grid_point_and_residual(self):
        n = nearest_grid_point("3/5")
        self.assertEqual(n["k"], 7)
        lo, hi = n["residual_bounds"]
        self.assertTrue(lo <= hi and abs(hi) < Fraction(1, 100))
        self.assertEqual(nearest_grid_point(Fraction(1, 2))["k"], 8)
        with self.assertRaises(ValueError):
            nearest_grid_point("3/2")


class RateAndDarkTests(unittest.TestCase):
    def test_loss_is_rate_not_fidelity(self):
        r = rate_not_fidelity("3/5", 6)
        self.assertEqual(r["accepted_fraction_of_heralds"], Fraction(5, 7) ** 6)
        self.assertEqual((r["witness_after_readout"], r["fidelity_cost_from_loss"]), (1, 0))

    def test_dark_count_heralds_are_rejected_or_correct(self):
        d = dark_count_table(8)
        self.assertEqual(d["threshold_wrong_by_dark"], ZERO)                 # the two C photons never share a mode
        self.assertEqual(d["correct_by_dark"].real_bounds(8)[0], Fraction(1, 4))
        self.assertEqual(d["rejected_by_dark"].real_bounds(8)[0], Fraction(5, 16))
        for row in d["rows"]:
            self.assertEqual(row["wrong_fraction_threshold"], ZERO)


PS = dict(evidence_class="LAB_RECORDED", rule="exactly one click per site", accepted_fraction="1/4")
DC = dict(evidence_class="LAB_RECORDED", per_window="1/1000", declared_bound="1/100")
W = dict(evidence_class="LAB_RECORDED", xxx_after_readout="9/10", source_visibility="9/10")


class GradeTests(unittest.TestCase):
    def test_grade_climbs_and_negative_controls(self):
        self.assertEqual(ledger_grade({})["grade"], "LEDGER_DECLARED")
        self.assertEqual(ledger_grade(dict(postselection=PS))["grade"], "POSTSELECTION_RECORDED")
        self.assertEqual(ledger_grade(dict(postselection=PS, dark_counts=DC))["grade"], "DARK_COUNTS_BOUNDED")
        self.assertEqual(ledger_grade(dict(postselection=PS, dark_counts=DC, witness=W)), dict(grade="LEDGER_QUALIFIED", reasons=[]))
        base = dict(postselection=PS, dark_counts=DC, witness=W)
        self.assertEqual(ledger_grade(dict(base, postselection=dict(PS, rule="any click")))["grade"], "LEDGER_DECLARED")
        self.assertEqual(ledger_grade(dict(base, dark_counts=dict(DC, per_window="1/10")))["grade"], "POSTSELECTION_RECORDED")
        self.assertEqual(ledger_grade(dict(base, witness=dict(W, xxx_after_readout="4/5")))["grade"], "DARK_COUNTS_BOUNDED")
        self.assertEqual(ledger_grade(dict(base, witness=dict(W, evidence_class="SYNTHETIC")))["grade"], "DARK_COUNTS_BOUNDED")
        with self.assertRaises(ValueError):
            ledger_grade(None)


if __name__ == "__main__":
    unittest.main()
