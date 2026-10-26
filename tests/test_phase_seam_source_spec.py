"""810 nm heralded source: exact pair statistics, g2 law, Klyshko, purity law, fail-closed source grade."""
from fractions import Fraction
import unittest

from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.source_spec import (
    SINGLE_PHOTON_G2_BOUND, all_herald_probability, energy_conservation, heralded_statistics, hom_visibility_bound,
    klyshko, mean_pairs, operating_table, pair_distribution, source_grade, source_spec, spectral_purity,
)


class PairStatisticsTests(unittest.TestCase):
    def test_energy_conservation_is_exact_and_degenerate(self):
        e = energy_conservation()
        self.assertTrue(e["exact"] and e["degenerate"])
        self.assertFalse(energy_conservation(405, 800, 820)["exact"])      # 1/800 + 1/820 != 1/405
        self.assertTrue(energy_conservation(405, 780, Fraction(405 * 780, 780 - 405))["exact"])  # non-degenerate partner

    def test_pair_distribution_is_thermal_and_normalised(self):
        p = pair_distribution(Fraction(1, 3), 8)
        self.assertEqual(p[0], Fraction(2, 3))
        self.assertEqual(p[2], Fraction(2, 3) * Fraction(1, 9))
        self.assertEqual(sum(p), 1 - Fraction(1, 3) ** 9)                   # tail is exactly x^(n_max+1)
        self.assertEqual(mean_pairs(Fraction(1, 3)), Fraction(1, 2))
        with self.assertRaises(ResourceLimit):
            pair_distribution(Fraction(1, 3), 65)
        with self.assertRaises(ValueError):
            pair_distribution(1, 4)

    def test_lossless_herald_gives_g2_equal_2x_and_multipair_equal_x(self):
        for xv in (Fraction(1, 100), Fraction(1, 40), Fraction(1, 5), Fraction(1, 4)):
            h = heralded_statistics(xv)
            self.assertEqual(h["g2_heralded"], 2 * xv)
            self.assertEqual(h["p_multipair_given_click"], xv)
            self.assertEqual(h["p_click"], xv)
        self.assertTrue(heralded_statistics(Fraction(1, 40))["single_photon_regime"])
        self.assertFalse(heralded_statistics(Fraction(1, 4))["single_photon_regime"])   # g2 = 1/2 exactly, not below

    def test_lossy_herald_raises_g2_monotonically(self):
        x = Fraction(1, 40)
        g = [heralded_statistics(x, eta)["g2_heralded"] for eta in (1, Fraction(1, 2), Fraction(1, 10))]
        self.assertEqual(g[0], Fraction(1, 20))
        self.assertTrue(g[0] < g[1] < g[2])
        with self.assertRaises(ValueError):
            heralded_statistics(x, 0)

    def test_klyshko_tends_to_signal_efficiency_and_overestimates_at_finite_x(self):
        k = klyshko(Fraction(1, 40), Fraction(1, 2), Fraction(3, 10))
        self.assertGreater(k["klyshko_signal"], Fraction(1, 2))
        self.assertEqual(k["klyshko_overestimates_by"], k["klyshko_signal"] - Fraction(1, 2))
        small = klyshko(Fraction(1, 10 ** 6), Fraction(1, 2), Fraction(3, 10))
        self.assertLess(abs(small["klyshko_signal"] - Fraction(1, 2)), Fraction(1, 10 ** 5))
        self.assertLess(abs(small["klyshko_idler"] - Fraction(3, 10)), Fraction(1, 10 ** 5))
        # coincidences never exceed either singles
        self.assertLessEqual(k["coincidence"], min(k["singles_signal"], k["singles_idler"]))

    def test_purity_law(self):
        self.assertEqual(spectral_purity(1, 1)["purity"], 1)
        self.assertEqual(spectral_purity(2, 3)["purity"], Fraction(12, 13))
        self.assertEqual(spectral_purity(3, 2)["purity"], Fraction(12, 13))     # symmetric
        self.assertEqual(spectral_purity(1, 10)["purity"], Fraction(20, 101))   # unfiltered: strongly correlated
        with self.assertRaises(ValueError):
            spectral_purity(0, 1)

    def test_visibility_bound_and_all_herald_law(self):
        b = hom_visibility_bound(Fraction(12, 13), Fraction(1, 40))
        self.assertEqual(b["upper_bound"], Fraction(12, 13))
        self.assertEqual(all_herald_probability(3, Fraction(1, 79))["p_all"], Fraction(1, 79) ** 3)
        self.assertFalse(all_herald_probability(1, Fraction(1, 2))["needs_multiplexing"])
        self.assertIsNone(all_herald_probability(8192, Fraction(1, 2))["p_all"])
        with self.assertRaises(ValueError):
            hom_visibility_bound(Fraction(3, 2), Fraction(1, 40))

    def test_operating_table_marks_regime(self):
        rows = operating_table()
        self.assertEqual([r["single_photon_regime"] for r in rows], [True, True, True, True, False])


PAIRS = dict(evidence_class="LAB_RECORDED", coincidence_rate_hz=1000, klyshko_signal="1/2")
G2 = dict(evidence_class="LAB_RECORDED", value="1/20")
HOM = dict(evidence_class="LAB_RECORDED", visibility="9/10")
TEMPS = dict(pump_c=25, crystal_oven_c=45, detector_c=22)


class GradeTests(unittest.TestCase):
    def test_spec_is_declared_only(self):
        s = source_spec()
        self.assertEqual(s["status"], "SPEC_DECLARED")
        self.assertFalse(s["built"])
        self.assertIsNone(s["measured_parameters"])
        self.assertTrue(s["pairs"]["energy_conservation_exact"])
        self.assertEqual(source_grade(s)["grade"], "SPEC_DECLARED")

    def test_grade_climbs_with_complete_recorded_blocks(self):
        rec = {}
        self.assertEqual(source_grade(rec)["grade"], "SPEC_DECLARED")
        rec["pairs"] = PAIRS
        self.assertEqual(source_grade(rec)["grade"], "PAIRS_RECORDED")
        rec["heralded_g2"] = G2
        self.assertEqual(source_grade(rec)["grade"], "HERALDED_SINGLE_PHOTON")
        rec["hom"] = HOM
        self.assertEqual(source_grade(rec)["grade"], "INDISTINGUISHABLE")
        rec["subsystem_temperatures_c"] = TEMPS
        r = source_grade(rec)
        self.assertEqual((r["grade"], r["reasons"], r["visibility"]), ("SOURCE_QUALIFIED", [], Fraction(9, 10)))

    def test_negative_controls(self):
        base = dict(pairs=PAIRS, heralded_g2=G2, hom=HOM, subsystem_temperatures_c=TEMPS)
        self.assertEqual(source_grade(dict(base, heralded_g2=dict(G2, value="1/2")))["grade"], "PAIRS_RECORDED")
        self.assertEqual(source_grade(dict(base, heralded_g2=dict(G2, evidence_class="SYNTHETIC")))["grade"], "PAIRS_RECORDED")
        self.assertEqual(source_grade(dict(base, hom=dict(HOM, visibility="2/5")))["grade"], "HERALDED_SINGLE_PHOTON")
        self.assertEqual(source_grade(dict(base, subsystem_temperatures_c=dict(TEMPS, detector_c=-40)))["grade"], "INDISTINGUISHABLE")
        self.assertEqual(source_grade(dict(base, subsystem_temperatures_c={}))["grade"], "INDISTINGUISHABLE")
        self.assertEqual(source_grade(dict(base, pairs=dict(PAIRS, evidence_class="SIMULATED")))["grade"], "SPEC_DECLARED")
        self.assertEqual(SINGLE_PHOTON_G2_BOUND, Fraction(1, 2))
        with self.assertRaises(ValueError):
            source_grade(None)


if __name__ == "__main__":
    unittest.main()
