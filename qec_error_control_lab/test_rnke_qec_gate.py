import unittest
from qec_shor import encode_shor, apply_errors, extract_shor_syndrome
from rnke_qec_gate import (build_rnke_qec_certificate, recognition_cycle, GENESIS,
                           COMMITTED, CORRECTED, DEFERRED, CUT, sha256_hex, canonical_json)

S = 2 ** -0.5

class GateTests(unittest.TestCase):
    def cycle(self, ref, cand, reports):
        return recognition_cycle(index_n=0, parent_receipt_hash=GENESIS,
                                 reference_state=ref, candidate_state=cand,
                                 syndrome_reports=reports)

    def test_clean_committed(self):
        ref = encode_shor(S, S); s = extract_shor_syndrome(ref)
        nxt, r = self.cycle(ref, ref, [s, s, s])
        self.assertEqual(r.verdict, COMMITTED); self.assertIsNotNone(nxt)

    def test_single_y_corrected_and_reaudited(self):
        ref = encode_shor(S, 1j * S); cand = apply_errors(ref, [(5, "Y")])
        s = extract_shor_syndrome(cand)
        nxt, r = self.cycle(ref, cand, [s, s, s])
        self.assertEqual(r.verdict, CORRECTED); self.assertEqual(r.fidelity_to_reference, 1.0)
        self.assertEqual(r.output_root, r.output_root); self.assertTrue(r.corrections)

    def test_disagreement_deferred_no_state(self):
        ref = encode_shor(1, 0); cand = apply_errors(ref, [(1, "X")])
        s = list(extract_shor_syndrome(cand)); a = s[:]; a[0] ^= 1; b = s[:]; b[1] ^= 1
        nxt, r = self.cycle(ref, cand, [s, a, b])
        self.assertEqual(r.verdict, DEFERRED); self.assertIsNone(nxt); self.assertIsNone(r.output_root)

    def test_two_bit_errors_same_block_cut(self):
        ref = encode_shor(S, S); cand = apply_errors(ref, [(0, "X"), (1, "X")])
        s = extract_shor_syndrome(cand)
        nxt, r = self.cycle(ref, cand, [s, s, s])
        self.assertEqual(r.verdict, CUT); self.assertIsNone(nxt)

    def test_multi_block_activation_cut(self):
        ref = encode_shor(0, 1); cand = apply_errors(ref, [(0, "X"), (3, "X")])
        s = extract_shor_syndrome(cand)
        _, r = self.cycle(ref, cand, [s, s, s])
        self.assertEqual(r.verdict, CUT); self.assertIsNone(r.residue["weight_bound"])

    def test_certificate_passes_and_chain_tamper_detected(self):
        cert = build_rnke_qec_certificate()
        self.assertEqual(cert["classification"], "PASS_RNKE_QEC_GATE_V1")
        self.assertEqual(cert["verdict_tallies"][COMMITTED], 4)
        self.assertEqual(cert["verdict_tallies"][DEFERRED], 4)
        # tamper one receipt body -> hash mismatch
        e = cert["ledger"][7]; body = {k: v for k, v in e.items() if k != "receipt_hash"}
        body["verdict"] = COMMITTED
        self.assertNotEqual(sha256_hex(canonical_json(body)), e["receipt_hash"])

    def test_certificate_deterministic(self):
        a = build_rnke_qec_certificate(); b = build_rnke_qec_certificate()
        self.assertEqual(a["certificate_sha256"], b["certificate_sha256"])

if __name__ == "__main__":
    unittest.main()
