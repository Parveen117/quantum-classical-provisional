"""Backend acceptance report: static validation across every explicit backend."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from native_relational_qc.check import BACKENDS, CAPABILITIES, capability_table, check, main

EXAMPLES = Path(__file__).resolve().parents[1] / 'native_relational_qc' / 'calculator_examples'


def request(operations, n_qubits=2, backend='factored', **extra):
    doc = dict(schema='nrqc-calculator-v1', n_qubits=n_qubits, operations=operations,
               queries=[dict(id='p', kind='probability', outcomes={'0': 0})], backend=backend)
    doc.update(extra)
    return doc


class CheckTests(unittest.TestCase):
    def test_bell_is_accepted_everywhere(self):
        report = check(request([['h', [0]], ['cx', [0, 1]]]))
        self.assertEqual(report['requested_status'], 'accepted')
        self.assertEqual(report['accepted_backends'], list(BACKENDS))
        self.assertEqual(set(report['capabilities']), set(BACKENDS))

    def test_nonadjacent_gate_rejected_by_factored_only_for_that_reason(self):
        report = check(request([['h', [0]], ['cx', [0, 2]]], n_qubits=3))
        self.assertEqual(report['requested_status'], 'rejected')
        self.assertIn('adjacent', report['requested_reason'])
        self.assertNotIn('factored', report['accepted_backends'])
        self.assertIn('observer', report['accepted_backends'])
        self.assertIn('stabilizer', report['accepted_backends'])

    def test_ccx_splits_compact_and_clifford_backends(self):
        report = check(request([['ccx', [0, 1, 2]]], n_qubits=3, backend='observer'))
        self.assertEqual(report['requested_status'], 'accepted')
        accepted = set(report['accepted_backends'])
        self.assertTrue({'observer', 'cyclotomic', 'cyclotomic_pow2', 'observer32'} <= accepted)
        self.assertFalse({'stabilizer', 'clifford_t', 'clifford_frame', 'jya_frame', 'factored'} & accepted)
        reasons = {r['backend']: r.get('reason') for r in report['backends']}
        self.assertIn('stabilizer backend does not support gate ccx', reasons['stabilizer'])

    def test_phase_gate_orders_nest(self):
        report = check(request([['h', [0]], ['p32', [0]]], n_qubits=1, backend='cyclotomic32'))
        self.assertEqual(report['accepted_backends'], ['cyclotomic32', 'cyclotomic64', 'cyclotomic_pow2', 'observer32'])
        report = check(request([['h', [0]], ['p4096', [0]]], n_qubits=1, backend='cyclotomic_pow2'))
        self.assertEqual(report['accepted_backends'], ['cyclotomic_pow2'])
        report = check(request([['h', [0]], ['p3', [0]]], n_qubits=1, backend='cyclotomic_pow2'))
        self.assertEqual(report['requested_status'], 'rejected')
        self.assertIn('power of two', report['requested_reason'])

    def test_width_separates_compact_from_large_register(self):
        ops = [['h', [0]], ['cx', [0, 1]]]
        report = check(request(ops, n_qubits=300, backend='stabilizer'))
        self.assertEqual(sorted(report['accepted_backends']), ['clifford_frame', 'clifford_t', 'jya_frame', 'stabilizer'])
        self.assertEqual(check(request(ops, n_qubits=3000, backend='stabilizer'))['accepted_backends'], [])

    def test_contraction_is_dropped_only_when_probing_other_backends(self):
        report = check(request([['h', [0]]], n_qubits=1, contraction='streaming'))
        rows = {r['backend']: r for r in report['backends']}
        self.assertEqual(rows['factored']['status'], 'accepted')
        self.assertNotIn('options_dropped_for_probe', rows['factored'])
        self.assertEqual(rows['observer']['options_dropped_for_probe'], ['contraction'])
        self.assertEqual(rows['observer']['status'], 'accepted')

    def test_geometry_and_simplify_are_rejected_by_phase_backends(self):
        doc = request([['h', [0]], ['cx', [0, 1]]], simplify='exact')
        report = check(doc)
        rows = {r['backend']: r for r in report['backends']}
        self.assertEqual(rows['factored']['status'], 'accepted')
        self.assertEqual(rows['cyclotomic_pow2']['status'], 'rejected')
        self.assertIn('circuit reduction', rows['cyclotomic_pow2']['reason'])

    def test_requested_backend_errors_are_invalid_requests(self):
        with self.assertRaises(ValueError):
            check(request([['h', [0]]], backend='aer'))
        with self.assertRaises(ValueError):
            check(dict(schema='other'))

    def test_shipped_examples_are_accepted_by_their_declared_backend(self):
        for path in sorted(EXAMPLES.glob('*.json')):
            if path.name.endswith('.result.json'):
                continue
            doc = json.loads(path.read_text())
            with self.subTest(example=path.name):
                report = check(doc)
                self.assertEqual(report['requested_status'], 'accepted', report['requested_reason'])
                self.assertEqual(report['requested_backend'], doc.get('backend', 'factored'))

    def test_capability_table_covers_every_backend(self):
        table = capability_table()
        for backend in BACKENDS:
            self.assertIn(f'`{backend}`', table)
            self.assertEqual(set(CAPABILITIES[backend]), {'width', 'gates', 'queries', 'options', 'limits', 'representation', 'notes'})
        self.assertEqual(len(table.splitlines()), len(BACKENDS) + 2)

    def test_cli_exit_codes(self):
        bell = EXAMPLES / 'bell.json'
        run = lambda *args, stdin=None: subprocess.run([sys.executable, '-m', 'native_relational_qc', 'check', *args],
                                                       input=stdin, text=True, capture_output=True)
        done = run(str(bell))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)['requested_status'], 'accepted')
        rejected = run('-', stdin=json.dumps(request([['ccx', [0, 1, 2]]], n_qubits=3, backend='stabilizer')))
        self.assertEqual(rejected.returncode, 1)
        self.assertEqual(json.loads(rejected.stdout)['requested_status'], 'rejected')
        invalid = run('-', stdin='{"schema": "x"}')
        self.assertEqual(invalid.returncode, 2)
        table = run('--table')
        self.assertEqual(table.returncode, 0)
        self.assertTrue(table.stdout.startswith('| Backend |'))
        self.assertEqual(main(['--table', '--out', str(Path(self.tmp_path()))]), 0)

    def tmp_path(self):
        import tempfile
        handle = tempfile.NamedTemporaryFile(suffix='.md', delete=False)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name


if __name__ == '__main__':
    unittest.main()
