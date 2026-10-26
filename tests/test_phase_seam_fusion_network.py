"""Fusion network: multiplexing law, Theorem N1 drift, exact Markov hitting probabilities (N2 limit), grade."""
from fractions import Fraction
import unittest

from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.fusion_network import (
    BOOSTED_SUCCESS, FUSION_SUCCESS, best_multiplexing, chain_fidelity_bound, chain_walk, extinction_cubic,
    growth_drift, multiplex, network_grade, network_plan, resource_estimate,
)


class MultiplexTests(unittest.TestCase):
    def test_law_and_lossless_limit(self):
        m = multiplex(Fraction(1, 2), 4, 1)
        self.assertEqual(m["p_at_least_one"], Fraction(15, 16))
        self.assertEqual(m["delivered"], Fraction(15, 16))
        self.assertEqual(multiplex(Fraction(1, 2), 1, Fraction(1, 2))["delivered"], Fraction(1, 2))   # depth 0: no switch
        m = multiplex(Fraction(1, 2), 4, Fraction(1, 2))
        self.assertEqual(m["delivered"], Fraction(15, 16) * Fraction(1, 4))
        with self.assertRaises(ValueError):
            multiplex(Fraction(1, 2), 3)
        with self.assertRaises(ResourceLimit):
            multiplex(Fraction(1, 2), 1 << 17)

    def test_switch_loss_sets_an_optimum(self):
        b = best_multiplexing(Fraction(1, 79), Fraction(9, 10))
        self.assertEqual(b["best_branches"], 256)              # still climbing at depth 8 for these inputs
        lossy = best_multiplexing(Fraction(1, 79), Fraction(1, 2))
        self.assertEqual(lossy["best_branches"], 1)             # 3 dB per stage: multiplexing never pays
        mid = best_multiplexing(Fraction(1, 4), Fraction(4, 5))
        self.assertLess(mid["best_branches"], 256)
        self.assertGreater(mid["best_branches"], 1)


class GrowthTests(unittest.TestCase):
    def test_theorem_N1(self):
        bell = growth_drift(FUSION_SUCCESS, 2)
        self.assertEqual(bell["drift"], 0)
        self.assertFalse(bell["grows"])
        self.assertEqual(bell["minimum_resource_sites_for_growth"], 3)
        ghz3 = growth_drift(FUSION_SUCCESS, 3)
        self.assertEqual(ghz3["drift"], Fraction(1, 2))
        self.assertTrue(ghz3["grows"])
        self.assertEqual(growth_drift(BOOSTED_SUCCESS, 2)["drift"], Fraction(1, 2))   # boosted Bell pairs also grow
        with self.assertRaises(ValueError):
            growth_drift(FUSION_SUCCESS, 1)

    def test_exact_hitting_probabilities(self):
        self.assertEqual(chain_walk(4)["p_reach_target"], Fraction(6, 7))
        self.assertEqual(chain_walk(4)["expected_attempts"], 2)
        self.assertEqual(chain_walk(5)["p_reach_target"], Fraction(5, 6))
        self.assertEqual(chain_walk(8)["p_reach_target"], Fraction(7, 9))
        self.assertEqual(chain_walk(16)["p_reach_target"], Fraction(94, 123))
        self.assertEqual(chain_walk(32)["p_reach_target"], Fraction(2207, 2889))

    def test_bell_pair_walk_is_fair_and_dies(self):
        w = chain_walk(8, FUSION_SUCCESS, 2, 2)
        self.assertEqual(w["p_reach_target"], Fraction(2, 8))          # gambler's ruin: start/target
        self.assertEqual(w["expected_attempts"], 2 * (8 - 2))           # start (target - start)
        self.assertEqual(chain_walk(8, FUSION_SUCCESS, 2, 4)["p_reach_target"], Fraction(1, 2))

    def test_theorem_N2_limit(self):
        # exact finite values bracket 3 - sqrt 5 = 0.7639320225...
        p32 = chain_walk(32)["p_reach_target"]
        p64 = chain_walk(64)["p_reach_target"]
        self.assertTrue(Fraction(7639320, 10 ** 7) < p64 < p32 < Fraction(7639322, 10 ** 7))
        # q = (sqrt5 - 1)/2 solves the cubic: residual of a rational approximation is tiny and changes sign around it
        self.assertGreater(extinction_cubic(Fraction(6180339887, 10 ** 10)), 0)
        self.assertLess(extinction_cubic(Fraction(6180339888, 10 ** 10)), 0)
        self.assertEqual(extinction_cubic(1), 0)                         # the trivial root

    def test_resources_and_fidelity(self):
        r = resource_estimate(8)
        self.assertEqual(r["expected_bell_pairs"], Fraction(274, 9))
        f = chain_fidelity_bound(Fraction(3, 5), 6)
        self.assertEqual(f["all_heralds_genuine"], Fraction(5, 7) ** 6)
        self.assertEqual(chain_fidelity_bound(1, 100)["all_heralds_genuine"], 1)
        with self.assertRaises(ResourceLimit):
            chain_walk(300)


FUSION = dict(evidence_class="LAB_RECORDED", xxx_witness="9/10")
GROWTH = dict(evidence_class="LAB_RECORDED", sites=4)
MUX = dict(evidence_class="LAB_RECORDED", delivered="1/20", bare="1/79")
TEMPS = dict(switches_c=24, delay_c=24, detectors_c=22)


class GradeTests(unittest.TestCase):
    def test_plan_is_declared(self):
        p = network_plan(2056)
        self.assertEqual(p["status"], "NETWORK_DECLARED")
        self.assertEqual(p["theorem_N1"]["bell_pair_drift"], "0")
        self.assertEqual(p["chain_walk"]["target"], 256)
        self.assertEqual(network_grade(p)["grade"], "NETWORK_DECLARED")
        with self.assertRaises(ValueError):
            network_plan(2)

    def test_grade_climbs_and_negative_controls(self):
        rec = {}
        self.assertEqual(network_grade(rec)["grade"], "NETWORK_DECLARED")
        rec["fusion"] = FUSION
        self.assertEqual(network_grade(rec)["grade"], "FUSION_RECORDED")
        rec["growth"] = GROWTH
        self.assertEqual(network_grade(rec)["grade"], "GROWTH_RECORDED")
        rec["multiplexing"] = MUX
        self.assertEqual(network_grade(rec)["grade"], "MULTIPLEXED_RECORDED")
        rec["subsystem_temperatures_c"] = TEMPS
        self.assertEqual(network_grade(rec), dict(grade="NETWORK_QUALIFIED", reasons=[]))
        base = dict(rec)
        self.assertEqual(network_grade(dict(base, fusion=dict(FUSION, xxx_witness="2/5")))["grade"], "NETWORK_DECLARED")
        self.assertEqual(network_grade(dict(base, fusion=dict(FUSION, evidence_class="SYNTHETIC")))["grade"], "NETWORK_DECLARED")
        self.assertEqual(network_grade(dict(base, growth=dict(GROWTH, sites=3)))["grade"], "FUSION_RECORDED")
        self.assertEqual(network_grade(dict(base, multiplexing=dict(MUX, delivered="1/100")))["grade"], "GROWTH_RECORDED")
        self.assertEqual(network_grade(dict(base, subsystem_temperatures_c=dict(TEMPS, detectors_c=-40)))["grade"], "MULTIPLEXED_RECORDED")
        with self.assertRaises(ValueError):
            network_grade("x")


if __name__ == "__main__":
    unittest.main()
