"""Cluster build: adaptation lemma, adaptive witness along chosen paths, tree from v0.30 merges, cost, ledger, grade."""
from fractions import Fraction
import unittest

from phase_seam_foundation.cluster_build import (
    adaptation_lemma, adaptive_run, build_cost, build_plan, cluster_build_grade, feedforward_layers, ledger_table,
    online_ledger, star_plan, tree_from_stars,
)
from phase_seam_foundation.cluster_compile import XOR_CHECKPOINT


class AdaptationTests(unittest.TestCase):
    def test_lemma_a_every_native_angle(self):
        for k in range(64):
            self.assertTrue(adaptation_lemma(k)["holds"], k)

    def test_feedforward_layers(self):
        f = feedforward_layers()
        self.assertEqual(f["stages"], 6)
        self.assertEqual(f["parallel_first_layer"], (0, 2, 4, 8))
        self.assertEqual(f["layer"][12], 5)
        self.assertEqual(f["writers"][6], (0, 2, 4, 5))

    def test_adaptive_xor_checkpoint_all_paths_exercised(self):
        for feats, label in (((0, 0), 0), ((0, 32), 1), ((32, 0), 1), ((32, 32), 0)):
            for path in (None, (1,) * 9, (1, 0, 1, 1, 0, 1, 1, 0, 1)):
                r = adaptive_run(feats, XOR_CHECKPOINT, path)
                self.assertTrue(r["witness"] and r["exact_equality"], (feats, path))
                self.assertEqual(r["rail_switches"], 0)
                if path:
                    self.assertGreater(r["outcomes_relabelled"] + r["angles_flipped"], 0)

    def test_adaptive_generic_angles(self):
        r = adaptive_run((5, 17), (3, 41, 22, 9, 50), (1, 1, 0, 1, 0, 1, 1, 1, 0))
        self.assertTrue(r["witness"] and r["exact_equality"])
        self.assertGreater(r["angles_flipped"], 0)
        with self.assertRaises(ValueError):
            adaptive_run((5, 17), (3, 41, 22, 9, 50), (1, 1))


class TreeTests(unittest.TestCase):
    def test_tree_from_seven_merges(self):
        t = tree_from_stars()
        self.assertTrue(t["tree_graph_exact"] and t["full_final_basis"])
        self.assertEqual((t["photons_before"], t["merges"], t["photons_after"]), (20, 7, 13))
        self.assertEqual(t["probability_per_click_sequence"], Fraction(1, 2 ** 14))
        self.assertEqual(t["success_probability"], Fraction(1, 128))
        self.assertEqual(t["phase_corrections_per_merge"], (16, 48))

    def test_star_plan(self):
        p = star_plan()
        self.assertEqual(p["stars"][6]["size"], 5)
        self.assertEqual(p["stars"][10]["size"], 3)
        self.assertEqual(sum(1 for s in p["stars"].values() if s["size"] == 2), 6)


class CostTests(unittest.TestCase):
    def test_policies(self):
        c = build_cost()
        f = c["full_restart"]
        self.assertEqual(f["bell_pairs_per_candidate"], Fraction(138, 5))
        self.assertEqual(f["expected_bell_pairs_per_delivered_cluster"], Fraction(17664, 5))
        self.assertEqual(f["expected_merge_rounds_per_delivered_cluster"], 254)
        self.assertGreater(c["spare_leaves"]["spare=4"]["p_build"], Fraction(1, 2))


class LedgerTests(unittest.TestCase):
    def test_online_ledger(self):
        l = online_ledger("99/100", "9/10")
        self.assertEqual((l["stages"], l["nodes_required"]), (6, 13))
        self.assertEqual(l["acceptance"], l["storage_survival"] * Fraction(9, 10) ** 13)
        self.assertEqual(online_ledger(1, 1)["acceptance"], 1)
        self.assertEqual(online_ledger("99/100", 1, latency_rounds=0)["acceptance"], 1)
        self.assertLess(online_ledger("99/100", 1, require_discarded_clicks=False)["nodes_required"], 13)
        self.assertEqual(len(ledger_table()), 9)
        with self.assertRaises(ValueError):
            online_ledger("3/2", 1)


class GradeTests(unittest.TestCase):
    def test_fail_closed(self):
        self.assertEqual(cluster_build_grade({})["grade"], "BUILD_DECLARED")
        stars = dict(evidence_class="LAB_RECORDED", ghz5_witness="7/10", ghz3_witness="9/10")
        self.assertEqual(cluster_build_grade(dict(stars=stars))["grade"], "STARS_RECORDED")
        tree = dict(evidence_class="LAB_RECORDED", photons=13, stabiliser_witnesses=12, merge_phases_applied=True)
        self.assertEqual(cluster_build_grade(dict(stars=stars, tree=tree))["grade"], "TREE_RECORDED")
        self.assertEqual(cluster_build_grade(dict(stars=stars, tree=dict(tree, merge_phases_applied=False)))["grade"], "STARS_RECORDED")
        run = dict(evidence_class="LAB_RECORDED", latency_us="1/10", stages=6, rejected_runs=12, rail_switches=0)
        self.assertEqual(cluster_build_grade(dict(stars=stars, tree=tree, adaptive_run=run))["grade"], "ADAPTIVE_RUN_RECORDED")
        self.assertEqual(cluster_build_grade(dict(stars=stars, tree=tree, adaptive_run=dict(run, rail_switches=1)))["grade"], "TREE_RECORDED")
        self.assertEqual(cluster_build_grade(dict(stars=stars, tree=tree, adaptive_run=dict(run, stages=5)))["grade"], "TREE_RECORDED")

    def test_plan(self):
        p = build_plan()
        self.assertTrue(p["adaptation"]["lemma_a_all_angles"] and p["tree"]["exact"])
        self.assertEqual(p["adaptation"]["stages"], 6)


if __name__ == "__main__":
    unittest.main()
