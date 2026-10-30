"""Ledger certification through the calculator: the v0.29 cluster witness on the flat backend."""
import json
import unittest
from fractions import Fraction
from pathlib import Path

from native_relational_qc import certify as c

GENERIC = dict(features=(5, 11), parameters=(3, 7, 13, 21, 29))
RECORD = Path(__file__).resolve().parents[1] / 'native_relational_qc' / 'certify_records' / 'cluster_certificate.json'


class CertifyTests(unittest.TestCase):
    def test_phase_steps_realise_every_angle_through_named_gates(self):
        F = c.flat_field()
        for k in range(64):
            ops = [['h', [0]]]
            c.phase_steps(ops, 0, k)
            amplitude = c.probabilities(1, ops + [['h', [0]]], [{'0': 0}])[0]
            # P(0) after H diag(1, zeta^k) H = |1 + zeta^k|^2 / 4
            expected = (F(1) + F.root(k)) * (F(1) + F.root(k)).conjugate() * Fraction(1, 4)
            self.assertEqual(amplitude, expected, k)

    def test_tower_embedding_is_a_ring_map_into_the_flat_field(self):
        from native_relational_qc.cyclotomic64 import Cyclotomic64 as C, ZETA, ONE
        from native_relational_qc.exact import INV_SQRT2
        F = c.flat_field()
        a, b = ZETA ** 5 * C.coerce(INV_SQRT2) + ONE, ZETA ** 19 - ZETA ** 2 * C.coerce(Fraction(3, 7))
        self.assertEqual(c.embed_tower(ZETA), F.root(1))
        self.assertEqual(c.embed_tower(a * b), c.embed_tower(a) * c.embed_tower(b))
        self.assertEqual(c.embed_tower(a + b), c.embed_tower(a) + c.embed_tower(b))
        self.assertEqual(c.embed_tower(a.conjugate()), c.embed_tower(a).conjugate())

    def test_lower_order_values_lift_exactly(self):
        value = c.probabilities(1, [['h', [0]], ['t', [0]], ['h', [0]]], [{'0': 0}])[0]   # Q(zeta_8) circuit
        F = c.flat_field()
        self.assertEqual(value, (F(1) + F.root(8)) * (F(1) + F.root(8)).conjugate() * Fraction(1, 4))

    def test_byproduct_identity_through_the_calculator(self):
        record = c.measurement_identity()
        self.assertTrue(record['holds'], record)
        self.assertGreaterEqual(record['checks'], 400)

    def test_assignment_partition_covers_every_path_once(self):
        spec = c._spec(**GENERIC)
        self.assertEqual(len(spec['signed']), 6)
        seen = []
        for k in range(64):
            assignment = tuple((k >> i) & 1 for i in range(6))
            paths = c.paths_for_assignment(spec, assignment)
            self.assertEqual(len(paths), 8)
            for path in paths:
                x_par, _ = c.path_byproducts(spec, path)
                self.assertEqual(tuple(x_par[n] for n in spec['signed']), assignment)
            seen += paths
        self.assertEqual(len(set(seen)), 512)

    def test_one_assignment_matches_circuit_and_pattern_engine(self):
        witness = c.cluster_witness(GENERIC['features'], GENERIC['parameters'], [(1, 0, 1, 1, 0, 1)])
        self.assertEqual(witness['paths_checked'], 8)
        self.assertEqual(witness['mismatching_paths'], [])
        self.assertTrue(witness['every_path_weight_exact'])
        self.assertTrue(witness['every_distribution_normalised'])
        self.assertTrue(witness['pattern_engine']['agrees_with_calculator'])
        self.assertEqual(witness['circuit_probability']['decimal'], '0.6370361636225')

    def test_control_without_corrections_depends_on_the_path(self):
        control = c.control_without_corrections(**GENERIC)
        self.assertTrue(control['corrections_do_work'])
        self.assertEqual(control['paths_with_weight'], 512)
        self.assertGreater(control['distinct_readout_values'], 1)

    def test_partial_run_is_incomplete_not_certified(self):
        report = c.certify_cluster([dict(label='generic', features=list(GENERIC['features']), parameters=list(GENERIC['parameters']))],
                                   [(0, 0, 0, 0, 0, 0)], identity=False)
        self.assertEqual(report['grade'], 'INCOMPLETE')
        self.assertIn('TRAINED_ON_CHIP', report['never_granted'])

    def test_committed_certificate_is_complete_and_certified(self):
        if not RECORD.exists():
            self.skipTest('no committed certificate')
        record = json.loads(RECORD.read_text())
        self.assertEqual(record['grade'], 'CERTIFIED')
        self.assertEqual({case['label'] for case in record['cases']}, {'generic', 'xor_00', 'xor_01', 'xor_10', 'xor_11'})
        for case in record['cases']:
            self.assertTrue(case['control_without_corrections']['corrections_do_work'])
            self.assertEqual(case['assignments_checked'], 64)
            self.assertEqual(case['paths_checked'], 512)
            self.assertEqual(case['mismatching_paths'], [])
            self.assertTrue(case['pattern_engine']['agrees_with_calculator'])
        self.assertTrue(record['measurement_identity']['holds'])


if __name__ == '__main__':
    unittest.main()
