"""Cluster noise: merge lemma N1, reduction N2, byproduct N3, XOR response, source map, Theorem N bound, controls, grade."""
from fractions import Fraction
import unittest

from native_relational_qc.cyclotomic64 import ONE, ZERO
from phase_seam_foundation.cluster_compile import DISCARDED, NODES, XOR_CHECKPOINT, circuit_probability
from phase_seam_foundation.cluster_noise import (
    BELL_PAIRS, GRADES, NEVER, controls, first_order_error, merge_lemma, noise_grade, noisy_run, reduction_lemma, response_table,
    source_map, stabiliser_reduction,
)


class LemmaTests(unittest.TestCase):
    def test_merge_lemma_n1(self):
        m = merge_lemma()
        self.assertTrue(m["holds"])
        self.assertTrue(m["never_heralded"])
        self.assertEqual(m["rows"]["psi_plus"]["register_paulis"][3], ((0, "X"),))
        self.assertEqual(m["rows"]["psi_minus"]["register_paulis"][4], ((0, "Y"),))
        self.assertEqual(m["rows"]["phi_minus"]["register_paulis"][3], ((0, "Z"), (1, "Z"), (2, "Z")))
        self.assertEqual(m["rows"]["phi_plus"]["register_paulis"][3], ())

    def test_reduction_lemma_n2(self):
        self.assertTrue(reduction_lemma()["holds"])
        self.assertEqual(stabiliser_reduction(6), dict(Z=frozenset({6}), X=frozenset({1, 3, 5, 7}), Y=frozenset({1, 3, 5, 6, 7})))
        with self.assertRaises(ValueError):
            stabiliser_reduction(13)

    def test_clean_run_equals_circuit_and_n3(self):
        r = noisy_run((5, 11), (3, 7, 13, 21, 29))
        self.assertEqual(r["readout_probability"], circuit_probability((5, 11), (3, 7, 13, 21, 29)))
        self.assertEqual(noisy_run((0, 32), XOR_CHECKPOINT, (6,))["readout_probability"], ZERO)   # Z on the hub flips the XOR label
        self.assertEqual(noisy_run((0, 32), XOR_CHECKPOINT, (1,))["readout_probability"], ONE)    # Z on a discarded output is invisible
        with self.assertRaises(ValueError):
            noisy_run((0, 32), XOR_CHECKPOINT, (13,))


class ResponseTests(unittest.TestCase):
    def test_xor_response_is_binary_parity(self):
        t = response_table((32, 0), XOR_CHECKPOINT)
        self.assertTrue(t["clean_equals_circuit"])
        self.assertTrue(t["discarded_invisible"])
        for v in range(NODES):
            for p in "ZXY":
                self.assertIn(t["rows"][v][p]["p_one"], (ZERO, ONE))
            self.assertEqual(t["rows"][v]["X"]["change"], ZERO)                         # X errors never flip the XOR label
            self.assertEqual(t["rows"][v]["Z"]["change"] != ZERO, v % 2 == 0)           # Z flips exactly on the measured wire nodes
            self.assertEqual(t["rows"][v]["Y"]["change"], t["rows"][v]["Z"]["change"])

    def test_source_map(self):
        m = source_map()
        self.assertEqual(m["bell_pairs"], BELL_PAIRS)
        self.assertEqual(sorted(m["exact"]), [1, 3, 5, 7, 9, 11])
        self.assertEqual(m["exact"][7], dict(phi_minus=frozenset({7}), psi_plus=frozenset({10}), psi_minus=frozenset({7, 10}), bell_pairs=1))
        self.assertEqual(m["bounded"][6]["support"], (0, 2, 4, 5, 6, 10))
        self.assertEqual(m["bounded"][10]["support"], (8, 9, 10, 11, 12))
        self.assertEqual(len(m["bounded"][6]["patterns"]), 63)
        self.assertTrue(all(not set(p) & set(DISCARDED) for b in m["bounded"].values() for p in b["patterns"]))

    def test_theorem_n_bound(self):
        e = first_order_error((0, 32), XOR_CHECKPOINT, "1/40", "243/4000")
        w = e["double_fraction"]
        self.assertEqual(w, Fraction(1085773, 13085773))
        self.assertEqual(e["pair_error_probability"], w / 4)
        for k in (1, 3, 5, 7, 9, 11):
            self.assertEqual(e["detail"][f"pair_{k}"], ONE + ONE)                       # Phi- and Psi- flip, Psi+ does not
        self.assertEqual(e["detail"]["star_6_worst"], ONE)
        self.assertEqual(e["first_order"], (ONE + ONE) * 6 * (w / 12) + ONE * 18 * (w / 12))
        self.assertEqual(e["remainder"], 1 - (1 - w / 4) ** 12 - 12 * (w / 4) * (1 - w / 4) ** 11)
        self.assertGreater(e["total_upper_bound"], Fraction(1, 5))
        self.assertLess(e["total_upper_bound"], Fraction(1, 4))
        small = first_order_error((0, 32), XOR_CHECKPOINT, "1/1000", "243/4000")
        self.assertLess(small["total_upper_bound"], Fraction(1, 100))
        with self.assertRaises(ValueError):
            first_order_error((0, 32), XOR_CHECKPOINT, "1/40", "0")


class ControlAndGradeTests(unittest.TestCase):
    def test_controls(self):
        c = controls((0, 32), XOR_CHECKPOINT)
        self.assertTrue(c["discarded_invisible"])
        self.assertTrue(c["uncorrected_branches_differ"])
        self.assertTrue(c["clean_pair_no_pauli"])

    def test_grade_fail_closed(self):
        self.assertEqual(noise_grade({})["grade"], GRADES[0])
        src = dict(evidence_class="LAB_RECORDED", bell_weights=["3/4", "1/12", "1/12", "1/12"])
        self.assertEqual(noise_grade(dict(source_sector=src))["grade"], GRADES[1])
        bad = dict(evidence_class="LAB_RECORDED", bell_weights=["1/12", "3/4", "1/12", "1/12"])
        self.assertEqual(noise_grade(dict(source_sector=bad))["grade"], GRADES[0])
        self.assertEqual(noise_grade(dict(source_sector=dict(src, evidence_class="SIMULATED")))["grade"], GRADES[0])
        ro = dict(evidence_class="LAB_RECORDED", label_error_rate="1/50", predicted_upper_bound="23/100")
        g = noise_grade(dict(source_sector=src, readout=ro))
        self.assertEqual(g["grade"], GRADES[2])
        self.assertEqual(g["never"], NEVER)
        self.assertEqual(noise_grade(dict(source_sector=src, readout=dict(ro, label_error_rate="1/4")))["grade"], GRADES[1])
        self.assertEqual(noise_grade(dict(source_sector=src, readout=dict(ro, evidence_class="SIMULATED")))["grade"], GRADES[1])
        with self.assertRaises(ValueError):
            noise_grade([])


if __name__ == "__main__":
    unittest.main()
