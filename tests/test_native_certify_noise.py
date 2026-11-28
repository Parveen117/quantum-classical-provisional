"""Theorem N (phase seam v0.36) readout response re-derived on the flat backend: nrqc certify noise."""
import json
import unittest
from fractions import Fraction
from pathlib import Path

from native_relational_qc import certify as c

XOR_01 = dict(features=(0, 32), parameters=(32, 0, 0, 32, 0))
GENERIC = dict(features=(5, 11), parameters=(3, 7, 13, 21, 29))
RECORD = Path(__file__).resolve().parents[1] / 'native_relational_qc' / 'certify_records' / 'noise_certificate.json'


class NoiseCertifyTests(unittest.TestCase):
    def test_source_map_patterns(self):
        nmap = c.noise_patterns()
        self.assertEqual(nmap['bell_pairs'], 12)
        self.assertEqual(len(nmap['exact']), 6)
        self.assertEqual(sorted(nmap['bounded']), ['10', '6'])
        self.assertEqual(len(nmap['bounded']['6']['patterns']), 63)
        self.assertEqual(len(nmap['bounded']['10']['patterns']), 31)
        self.assertEqual(len(nmap['patterns']), 99)
        self.assertTrue(all(p == tuple(sorted(set(p))) for p in nmap['patterns']))

    def test_one_assignment_responses_are_path_independent_and_match_the_pattern_engine(self):
        from phase_seam_foundation import cluster_noise as cn
        patterns = [(0,), (8,), (12,), (4, 5), (0, 2, 4, 5, 6, 10), (7,)]
        block = c.cluster_assignment(GENERIC['features'], GENERIC['parameters'], (1, 0, 1, 1, 0, 1), patterns)
        self.assertEqual(len(block['rows']), 8)
        for pattern in patterns:
            row = block['responses'][pattern]
            self.assertTrue(row['path_weights_exact'], pattern)
            self.assertTrue(row['path_independent'], pattern)
            engine = c.embed_tower(cn.noisy_run(GENERIC['features'], GENERIC['parameters'], pattern)['readout_probability'])
            self.assertEqual(row['readout_probability'], engine, pattern)
        clean = c.embed_tower(cn.noisy_run(GENERIC['features'], GENERIC['parameters'])['readout_probability'])
        self.assertEqual(block['responses'][(7,)]['readout_probability'], clean)        # discarded node: invisible
        self.assertNotEqual(block['responses'][(8,)]['readout_probability'], clean)     # a Bell-pair leaf: visible

    def test_xor_first_order_coefficient_is_five_halves(self):
        report = c.certify_noise([dict(label='xor_01', features=list(XOR_01['features']), parameters=list(XOR_01['parameters']))],
                                 [(0, 0, 0, 0, 0, 0)], identity=False)
        case = report['cases'][0]
        self.assertEqual(report['grade'], 'INCOMPLETE')
        self.assertEqual(case['mismatching_patterns'], [])
        self.assertEqual(case['first_order']['coefficient'], '5/2')
        self.assertTrue(case['first_order']['agrees_with_theorem_n'])
        self.assertTrue(case['first_order']['below_declared_14_over_5_w'])
        self.assertTrue(all(case['negative_controls'].values()), case['negative_controls'])
        self.assertEqual(case['discarded_invisible']['discarded'], [1, 3, 7])
        self.assertIn('ROOM_TEMPERATURE_CLASSIFIER', report['never_granted'])
        self.assertIn('WITNESS_QUALIFIED', report['never_granted'])
        self.assertEqual(report['provenance']['source_sha256'].keys() & {'native_relational_qc/certify.py'}, {'native_relational_qc/certify.py'})

    def test_committed_noise_certificate_is_complete_and_certified(self):
        if not RECORD.exists():
            self.skipTest('no committed noise certificate')
        from phase_seam_foundation import cluster_noise as cn
        record = json.loads(RECORD.read_text())
        self.assertEqual(record['grade'], 'CERTIFIED')
        self.assertTrue(record['measurement_identity']['holds'])
        self.assertEqual({case['label'] for case in record['cases']}, {'generic', 'xor_00', 'xor_01', 'xor_10', 'xor_11'})
        for case in record['cases']:
            self.assertEqual(case['assignments_checked'], 64)
            self.assertEqual(case['paths_checked'], 512)
            self.assertEqual(case['patterns_checked'], 99)
            self.assertEqual(case['mismatching_patterns'], [])
            self.assertEqual(case['cluster_witness_mismatching_paths'], [])
            self.assertTrue(case['first_order']['agrees_with_theorem_n'])
            self.assertTrue(all(case['negative_controls'].values()), case['label'])
            # the recorded first-order term is the Theorem N term at the recorded point, recomputed now
            ledger = cn.first_order_error(case['features'], case['parameters'], case['first_order']['x'], case['first_order']['eta'])
            self.assertEqual(c._text(c.embed_tower(ledger['first_order'])), case['first_order']['first_order_term'])
            self.assertEqual(str(ledger['double_fraction']), case['first_order']['double_fraction'])
        xor = next(case for case in record['cases'] if case['label'] == 'xor_01')
        self.assertEqual(xor['first_order']['coefficient'], '5/2')
        self.assertEqual(record['provenance']['python'].split('.')[:2], ['3', '12'])


if __name__ == '__main__':
    unittest.main()
