"""Ledger violations: V1 double occupancy (engine, all angles), dark readout law, V2 witness law, budget, dual-rail verdict."""
from fractions import Fraction
import unittest

from native_relational_qc.cyclotomic64 import ONE, ZERO
from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.ledger_violations import (
    allowed_wrong_fraction, dark_readout_site, double_occupancy, double_occupancy_table, dual_rail_sweep_verdict,
    error_budget, multi_pair_site, witness_law,
)


class TheoremV1Tests(unittest.TestCase):
    def test_double_occupancy_is_unit_and_never_below_half_same_rail(self):
        half = Fraction(1, 2)
        for t in range(65):
            d = double_occupancy(t)
            self.assertEqual(d["total"], ONE)
            self.assertGreaterEqual(d["same_rail"].real_bounds(12)[0], half - Fraction(1, 1 << 10))
        self.assertEqual(double_occupancy(16)["same_rail"].real_bounds(10)[0], half)    # balanced point: HOM bunching
        self.assertEqual(double_occupancy(0)["split"], ZERO)                            # identity: both stay
        self.assertEqual(double_occupancy(8)["same_rail"].real_bounds(10)[0], Fraction(3, 4))
        self.assertTrue(all(r["unit_total"] for r in double_occupancy_table()))

    def test_multi_pair_site_weights(self):
        m = multi_pair_site(16, Fraction(1, 40), Fraction(1, 2))
        self.assertEqual(m["wrong_threshold_bounds"][0], Fraction(1, 40) * Fraction(1, 4) * Fraction(1, 2))
        self.assertEqual(m["right_one_survivor"], Fraction(1, 40) * 2 * Fraction(1, 2) * Fraction(1, 2))
        self.assertEqual(m["wrong_number_resolving"], 0)
        self.assertEqual(multi_pair_site(16, 0)["wrong_threshold_bounds"], (0, 0))      # no multi-pair, no error
        with self.assertRaises(ValueError):
            multi_pair_site(16, Fraction(3, 2))


class DarkAndWitnessTests(unittest.TestCase):
    def test_dark_readout_law(self):
        d = dark_readout_site(Fraction(1, 2), Fraction(1, 100))
        self.assertEqual(d["accept_right"], Fraction(1, 2) * Fraction(99, 100))
        self.assertEqual(d["accept_wrong"], Fraction(1, 2) * 2 * Fraction(1, 100) * Fraction(99, 100))
        self.assertEqual(d["accept_right"] + d["accept_wrong"] + d["rejected"], 1)
        self.assertEqual(dark_readout_site(1, Fraction(1, 100))["accept_wrong"], 0)       # a photon always present
        self.assertEqual(dark_readout_site(Fraction(1, 2), 0)["accept_wrong"], 0)          # no dark clicks

    def test_theorem_V2_witness_law(self):
        w = witness_law(Fraction(1, 2), Fraction(1, 100), 8)
        self.assertEqual(w["witness"], Fraction(50, 51) ** 8)
        self.assertEqual(witness_law(Fraction(1, 2), 0, 2056)["witness"], 1)
        self.assertEqual(witness_law(Fraction(1, 2), Fraction(1, 2), 1)["witness"], Fraction(1, 2))
        with self.assertRaises(ResourceLimit):
            witness_law(Fraction(1, 2), 0, 5000)

    def test_allowed_wrong_fraction_brackets_the_root(self):
        a = allowed_wrong_fraction(Fraction(1, 2), 2056)
        lo, hi = a["max_wrong_fraction_bounds"]
        self.assertTrue(lo < hi)
        self.assertTrue((1 - hi) ** 2056 <= Fraction(1, 2) <= (1 - lo) ** 2056)
        self.assertLess(hi, Fraction(4, 10000))
        self.assertGreater(lo, Fraction(3, 10000))
        self.assertLess(allowed_wrong_fraction(1, 5)["max_wrong_fraction_bounds"][1], Fraction(1, 1 << 30))   # witness 1 allows nothing


class BudgetTests(unittest.TestCase):
    def test_budget_threshold_versus_number_resolving(self):
        th = error_budget(2056)
        nr = error_budget(2056, readout="number_resolving")
        self.assertLess(th["witness_bounds"][1], Fraction(1, 5))
        self.assertGreater(nr["witness_bounds"][0], Fraction(1, 2))
        self.assertEqual(th["dominant"], "multi-pair")
        self.assertEqual(nr["dominant"], "dark counts")
        small = error_budget(3)
        self.assertGreater(small["witness_bounds"][0], Fraction(99, 100))
        with self.assertRaises(ValueError):
            error_budget(3, readout="analogue")

    def test_budget_monotone_in_sites_and_in_dark_rate(self):
        self.assertGreater(error_budget(8)["witness_bounds"][0], error_budget(64)["witness_bounds"][0])
        self.assertGreater(error_budget(64, dark_per_mode="1/1000000")["witness_bounds"][0], error_budget(64, dark_per_mode="1/1000")["witness_bounds"][0])


LEDGER = dict(readout_rule="exactly one click per site",
              dark_count_bound=dict(evidence_class="LAB_RECORDED", value="1/100000"),
              heralded_g2=dict(evidence_class="LAB_RECORDED", value="1/20"),
              source_visibility=dict(evidence_class="LAB_RECORDED", value="9/10"))


class VerdictTests(unittest.TestCase):
    def test_missing_ledger_fails_closed_without_touching_thermal(self):
        v = dual_rail_sweep_verdict({})
        self.assertEqual((v["logic_class"], v["ledger_recorded"]), ("UNDETERMINED", False))
        self.assertEqual(v["claims_allowed"], [])
        self.assertEqual(v["thermal_class"], "UNDETERMINED")

    def test_ledger_block_is_checked_field_by_field(self):
        ok = dual_rail_sweep_verdict(dict(ledger=LEDGER))
        self.assertTrue(ok["ledger_recorded"])
        bad_rule = dual_rail_sweep_verdict(dict(ledger=dict(LEDGER, readout_rule="any click")))
        self.assertFalse(bad_rule["ledger_recorded"])
        self.assertTrue(any("readout_rule" in r for r in bad_rule["reasons"]))
        g2 = dual_rail_sweep_verdict(dict(ledger=dict(LEDGER, heralded_g2=dict(evidence_class="LAB_RECORDED", value="1/2"))))
        self.assertFalse(g2["ledger_recorded"])
        synthetic = dual_rail_sweep_verdict(dict(ledger=dict(LEDGER, source_visibility=dict(evidence_class="SYNTHETIC", value="9/10"))))
        self.assertFalse(synthetic["ledger_recorded"])
        with self.assertRaises(ValueError):
            dual_rail_sweep_verdict([])


if __name__ == "__main__":
    unittest.main()
