"""Cluster faults: storage during growth (S1), switches, double-pair one-survivor (P1), herald counting, ledger on 13 nodes, grade."""
from fractions import Fraction
import unittest

from native_relational_qc.cyclotomic64 import ONE, ZERO
from phase_seam_foundation.cluster_faults import (
    MERGE_PHOTON_ROUNDS, acceptance_with_switches, allowed_x, assembly_storage, cluster_fault_ledger, double_pair_survivors,
    fault_grade, fault_plan, fused_one_survivor_witness, ledger_table, multi_pair_fused_fraction, number_resolving_herald,
    star_growth_with_storage, switch_buffer,
)
from phase_seam_foundation.tree_build import star


class StorageTests(unittest.TestCase):
    def test_lossless_reproduces_star_walk(self):
        for n in (4, 5, 8):
            self.assertEqual(star_growth_with_storage(n, 1)["p_reach_and_survive"], star(n)["p_reach"])
        self.assertEqual(star_growth_with_storage(3, "9/10")["p_reach_and_survive"], 1)

    def test_storage_monotone_and_exact(self):
        a, b = star_growth_with_storage(5, "999/1000"), star_growth_with_storage(5, "99/100")
        self.assertGreater(a["p_reach_and_survive"], b["p_reach_and_survive"])
        self.assertLess(b["survival_factor"], 1)
        self.assertGreater(b["survival_factor"], Fraction(9, 10))
        with self.assertRaises(ValueError):
            star_growth_with_storage(2, "9/10")

    def test_assembly(self):
        a = assembly_storage("99/100")
        self.assertEqual(a["merge_photon_rounds"], MERGE_PHOTON_ROUNDS)
        self.assertEqual(a["merge_success_path_survival"], Fraction(99, 100) ** 119)
        self.assertEqual(a["candidate_success_with_storage"], Fraction(99, 100) ** 119 / 128)
        self.assertEqual(a["bell_pairs"], 6)


class SwitchTests(unittest.TestCase):
    def test_grid_and_composition(self):
        self.assertEqual(switch_buffer(0, 0)["acceptance_multiplier"], ONE)
        s = switch_buffer(1, 2)
        lo, hi = s["bounds"]
        self.assertLess(lo, Fraction(55, 100)); self.assertGreater(hi, Fraction(53, 100))      # (cos^2(pi/32) cos^2(2pi/32))^13
        a = acceptance_with_switches("99/100", "9/10", 1, 2)
        self.assertLess(a["acceptance_bounds"][1], a["base_acceptance"])
        with self.assertRaises(ValueError):
            switch_buffer(17, 0)


class DoublePairTests(unittest.TestCase):
    def test_loss_trace_retains_coherence(self):
        d = double_pair_survivors("1/2")
        self.assertEqual(d["density"][0][0], Fraction(5, 12))
        self.assertEqual(d["density"][0][3], Fraction(1, 3))
        self.assertEqual(d["coherence"], Fraction(2, 3))
        self.assertEqual(d["zz_correlation"], Fraction(2, 3))
        self.assertEqual(d["p_one_survivor_each"], Fraction(1, 4))
        self.assertTrue(d["closed_form_check"])

    def test_fused_one_survivor_is_wrong(self):
        w = fused_one_survivor_witness("243/4000")
        self.assertEqual(w["fusion_success"], Fraction(1, 2))
        self.assertEqual(w["conditional_xxx"], Fraction(2, 3))
        self.assertEqual(w["conditional_ghz_fidelity"], Fraction(3, 4))

    def test_wrong_fraction_law(self):
        m = multi_pair_fused_fraction("1/40", "243/4000")
        x, e = Fraction(1, 40), Fraction(243, 4000)
        self.assertEqual(m["double_fraction"], 4 * x * (1 - e) ** 2 / ((1 - x) + 4 * x * (1 - e) ** 2))
        self.assertGreater(m["double_fraction"], Fraction(8, 100))
        self.assertEqual(number_resolving_herald("1/40", 1)["double_pair_fraction_given_one_click"], 0)
        self.assertEqual(number_resolving_herald("1/40", "9/10")["double_pair_fraction_given_one_click"], Fraction(1, 196))

    def test_allowed_x(self):
        a = allowed_x("9/10", 13, "243/4000", "9/10")
        lo, hi = a["x_bounds"]
        self.assertLess(hi, Fraction(1, 400)); self.assertGreater(lo, Fraction(1, 500))
        self.assertGreater(a["with_number_resolving_herald"]["x_bounds"][0], Fraction(1, 100))


class LedgerTests(unittest.TestCase):
    def test_design_point_fails_and_recovers(self):
        bad = cluster_fault_ledger()
        self.assertLess(bad["toy_score_before_visibility"], Fraction(1, 3))
        self.assertEqual(bad["dominant"], "multi-pair")
        good = cluster_fault_ledger(x="1/200", herald_efficiency="9/10")
        self.assertGreater(good["toy_score_before_visibility"], Fraction(89, 100))
        self.assertEqual(good["dominant"], "dark counts")
        self.assertEqual(good["toy_visibility_factor"], Fraction(9, 10) ** 7)
        self.assertEqual(len(ledger_table()), 6)


class GradeTests(unittest.TestCase):
    def test_perfect_record_still_requires_a_circuit_channel(self):
        record = dict(source=dict(evidence_class='LAB_RECORDED', heralded_g2=0,
                                  herald_readout='number_resolving', herald_efficiency=1),
                      nodes=dict(evidence_class='LAB_RECORDED', dark_count_bound=0,
                                 site_efficiency=1, hom_visibility=1))
        verdict = fault_grade(record)
        self.assertEqual(verdict['grade'], 'NODE_FAULTS_RECORDED')
        self.assertFalse(verdict['witness_qualified'])
        self.assertEqual(double_pair_survivors(1)['p_one_survivor_each'], 0)
        self.assertIsNone(double_pair_survivors(1)['density'])

    def test_fail_closed(self):
        self.assertEqual(fault_grade({})["grade"], "FAULTS_DECLARED")
        src = dict(evidence_class="LAB_RECORDED", heralded_g2="1/100", herald_readout="number_resolving", herald_efficiency="9/10")
        self.assertEqual(fault_grade(dict(source=src))["grade"], "SOURCE_RECORDED")
        self.assertEqual(fault_grade(dict(source=dict(src, heralded_g2="3/5")))["grade"], "FAULTS_DECLARED")
        self.assertEqual(fault_grade(dict(source=dict(src, herald_efficiency=None)))["grade"], "FAULTS_DECLARED")
        nodes = dict(evidence_class="LAB_RECORDED", dark_count_bound="1/1000000", site_efficiency="243/4000", hom_visibility="99/100")
        self.assertEqual(fault_grade(dict(source=src, nodes=nodes))["grade"], "NODE_FAULTS_RECORDED")          # circuit-level source map is not supplied
        tight = dict(src, heralded_g2="1/500")                                                                   # g2 alone does not identify double-pair weight
        self.assertEqual(fault_grade(dict(source=tight, nodes=nodes))["grade"], "NODE_FAULTS_RECORDED")
        self.assertEqual(fault_grade(dict(source=tight, nodes=dict(nodes, hom_visibility="9/10")))["grade"], "NODE_FAULTS_RECORDED")
        self.assertEqual(fault_grade(dict(source=dict(tight, herald_readout="threshold"), nodes=dict(nodes, dark_count_bound="1/100000")))["grade"], "NODE_FAULTS_RECORDED")

    def test_plan(self):
        p = fault_plan()
        self.assertEqual(p["corrected_p1"]["conditional_xxx"], Fraction(2, 3))
        self.assertFalse(cluster_fault_ledger()["is_physical_witness_bound"])


if __name__ == "__main__":
    unittest.main()
