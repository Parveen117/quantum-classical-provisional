"""Exact dual-rail route: boson engine, single-site Euler, HOM, type-I fusion, visibility law."""
from fractions import Fraction
import unittest

from native_relational_qc.cyclotomic64 import Cyclotomic64 as F, ONE, ZERO, ZETA
from native_relational_qc.exact import INV_SQRT2
from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.dual_rail import (
    COUPLER, MEASURED, bell_pairs_state, compose, corrected_witness, distinguishable_fusion, embed, encode,
    evolve, fock_amplitude, fusion_outcomes, ghz_merge, hom_from_engine, identity, phase,
    room_temperature_plan, single_site_euler, total_probability, unit_matrix, visibility_law,
)

H2 = F(INV_SQRT2)


class BosonEngineTests(unittest.TestCase):
    def test_single_photon_amplitudes_are_matrix_entries(self):
        u = embed(3, (0, 2), COUPLER)
        self.assertEqual(fock_amplitude(u, (1, 0, 0), (1, 0, 0)), H2)
        self.assertEqual(fock_amplitude(u, (1, 0, 0), (0, 0, 1)), F.coerce(0) + COUPLER[1][0])
        self.assertEqual(fock_amplitude(u, (0, 1, 0), (0, 1, 0)), ONE)

    def test_unitarity_preserves_total_probability(self):
        u = compose(embed(4, (0, 1), COUPLER), phase(4, 1, 7), embed(4, (1, 2), COUPLER), embed(4, (2, 3), COUPLER))
        for state in ({(1, 0, 1, 0): ONE}, {(1, 1, 0, 0): H2, (0, 0, 1, 1): H2}):
            self.assertEqual(total_probability(evolve(u, state)), ONE)
        # three photons can bunch three into one mode: that probability is exact but its amplitude is not in the field
        with self.assertRaises(ResourceLimit):
            evolve(u, {(2, 0, 0, 1): ONE})
        overflow = [ZERO]
        kept = evolve(u, {(2, 0, 0, 1): ONE}, overflow=overflow)
        self.assertNotEqual(overflow[0], ZERO)
        self.assertEqual(total_probability(kept) + overflow[0], ONE)

    def test_bunching_normalisation(self):
        # two photons on a balanced coupler: |2,0> and |0,2> each 1/2, |1,1> zero
        out = evolve(COUPLER, {(1, 1): ONE})
        self.assertNotIn((1, 1), out)
        self.assertEqual(out[(2, 0)].norm2(), F.coerce(Fraction(1, 2)))
        self.assertEqual(out[(0, 2)].norm2(), F.coerce(Fraction(1, 2)))

    def test_guards(self):
        with self.assertRaises(ResourceLimit):
            fock_amplitude(identity(2), (3, 0), (3, 0))
        with self.assertRaises(ResourceLimit):
            fock_amplitude(identity(3), (2, 2, 1), (2, 2, 1))
        with self.assertRaises(ValueError):
            embed(2, (0, 0), COUPLER)
        with self.assertRaises(ValueError):
            evolve(identity(2), {(1, 0): ONE, (1, 1): ONE})
        self.assertEqual(fock_amplitude(identity(2), (1, 0), (1, 1)), ZERO)

    def test_encode(self):
        self.assertEqual(encode((0, 1, 1), 6), (1, 0, 0, 1, 0, 1))
        with self.assertRaises(ValueError):
            encode((2,), 2)


class SingleSiteTests(unittest.TestCase):
    def test_euler_identity_on_the_grid(self):
        for theta in range(0, 65, 4):
            for b in (-64, -16, 0, 7, 48, 64):
                for a in (-16, 0, 25, 48):
                    self.assertTrue(single_site_euler(theta, b, a), (theta, b, a))
        with self.assertRaises(ValueError):
            single_site_euler(16, 65, 0)

    def test_hom_from_engine_matches_closed_form(self):
        for theta in range(0, 65, 2):
            h = hom_from_engine(theta)
            c = (ZETA ** theta + ZETA ** (-theta)) / 2
            self.assertEqual(h["coincidence"], c * c)
            self.assertEqual(h["coincidence"] + h["bunched"], ONE)
        self.assertEqual(hom_from_engine(16)["coincidence"], ZERO)


class FusionTests(unittest.TestCase):
    def test_bell_pairs_are_normalised_four_photon_states(self):
        s = bell_pairs_state()
        self.assertEqual(len(s), 4)
        self.assertEqual(total_probability(s), ONE)
        self.assertTrue(all(sum(k) == 4 for k in s))

    def test_success_and_failure_split_one_half(self):
        r = fusion_outcomes()
        self.assertEqual(r["success_probability"], F.coerce(Fraction(1, 2)))
        self.assertEqual(r["failure_probability"], F.coerce(Fraction(1, 2)))
        self.assertTrue(all(o[MEASURED[0]] + o[MEASURED[1]] in (0, 2) for o in r["failure"]))

    def test_each_click_heralds_ghz_with_known_phase(self):
        g = ghz_merge()
        self.assertEqual(sorted(g["clicks"]), list(MEASURED))
        for click, c in g["clicks"].items():
            self.assertEqual(c["probability"], F.coerce(Fraction(1, 4)))
            self.assertTrue(c["support_is_ghz"])
            self.assertTrue(c["equal_weights"])
            self.assertIn(c["heralded_phase_steps"], (16, 48))
            self.assertEqual(c["corrected_xxx"], ONE)
        self.assertEqual(corrected_witness(g), ONE)

    def test_distinguishable_photons_keep_success_but_lose_coherence(self):
        d = distinguishable_fusion()
        self.assertEqual(d["success_probability"], F.coerce(Fraction(1, 2)))
        self.assertEqual(d["corrected_xxx"], ZERO)

    def test_witness_equals_visibility(self):
        for v in ("1", "9/10", "0"):
            r = visibility_law(v)
            self.assertEqual(r["success_probability"], F.coerce(Fraction(1, 2)))
            self.assertTrue(r["witness_equals_visibility"])
        with self.assertRaises(ValueError):
            visibility_law("1.5")


class PlanTests(unittest.TestCase):
    def test_plan_counts_and_route(self):
        p = room_temperature_plan(2056)
        self.assertEqual((p["modes"], p["photons_per_shot"], p["heaters_single_site"]), (4112, 2056, 8224))
        self.assertEqual(p["wavelength_nm"], 810)
        self.assertEqual(p["detector"]["thermal_class_if_recorded"], "ROOM_TEMPERATURE")
        self.assertEqual(p["status"], "DECLARED_DESIGN")
        self.assertEqual(len(p["claim_boundary"]), 4)
        with self.assertRaises(ValueError):
            room_temperature_plan(0)

    def test_unit_matrix_embeds(self):
        u = unit_matrix(16, m=4, pair=(1, 2))
        self.assertEqual(u[0][0], ONE)
        self.assertEqual(u[3][3], ONE)
        self.assertEqual(u[0][1], ZERO)


if __name__ == "__main__":
    unittest.main()
