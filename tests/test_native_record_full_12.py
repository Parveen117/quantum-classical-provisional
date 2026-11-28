"""Theorem R1 at twelve bits: the committed record-versus-full-register audit and its script."""
import json
import unittest
from pathlib import Path

from native_relational_qc.cyclotomic_pow2 import field_of_order
from native_relational_qc.shor import exact_phase_law

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'native_relational_qc' / 'record_full_12_audit.json'
FULL = {143: ROOT / 'benchmarks' / 'comparisons' / 'full_register_12_n143_20261106.json',
        187: ROOT / 'benchmarks' / 'comparisons' / 'full_register_12_n187_20261106.json'}


class RecordFull12Tests(unittest.TestCase):
    def test_script_binds_full_results_to_the_declared_workload(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('record_full_12_audit', ROOT / 'benchmarks' / 'record_full_12_audit.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with self.assertRaises(ValueError):
            module.full_distribution(dict(status='failed', answers=[]), 141, 2)
        bad = dict(status='completed', answers=[dict(bitstring_qubits_left_to_right=list(range(12)), probabilities={})])
        with self.assertRaises(ValueError):
            module.full_distribution(bad, 141, 2)

    def test_committed_twelve_bit_witness(self):
        if not RECORD.exists():
            self.skipTest('no committed twelve-bit audit')
        record = json.loads(RECORD.read_text())
        self.assertEqual(record['status'], 'witnessed')
        self.assertEqual(record['environment']['python'].split('.')[:2], ['3', '12'])
        self.assertEqual({r['modulus'] for r in record['rows']}, {141, 143, 187})
        for row in record['rows']:
            self.assertEqual(row['bins'], 4096)
            self.assertEqual(row['bins_equal'], 4096)
            self.assertTrue(row['record_equals_full_register'])
            self.assertTrue(row['record_sums_to_one'])
            self.assertTrue(row['record']['exact_fourier_law_agrees'])
            self.assertTrue(row['full']['exact_fourier_law_agrees'])
            self.assertTrue(row['negative_controls']['shifted_relabelling_rejected'])
            self.assertTrue(row['negative_controls']['altered_bin_detected'])
            self.assertEqual(row['record']['wires'], 29)
            self.assertEqual(row['full']['wires'], 40)

    def test_retained_full_register_summaries_agree_with_the_fourier_law(self):
        Z = field_of_order(4096)
        for modulus, path in FULL.items():
            if not path.exists():
                self.skipTest('no retained full-register summary')
            summary = json.loads(path.read_text())
            self.assertEqual(summary['status'], 'completed')
            self.assertLess(summary['wall_seconds'], 300)
            self.assertEqual(summary['distribution_bins'], 4096)
            self.assertTrue(summary['assessment']['exact_fourier_law_agrees'])
            law = exact_phase_law(modulus, 2, 12, field='flat')
            for policy in summary['assessment']['policies'].values():
                self.assertEqual(policy['readings_checked'], 4096)
            total = sum((Z(v) for v in law.values()), Z())
            self.assertEqual(total, Z(1))


if __name__ == '__main__':
    unittest.main()
