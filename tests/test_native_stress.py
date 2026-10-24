import unittest

from native_relational_qc.compact import CompactCircuit, ResourceLimit
from native_relational_qc.observer import probability, expectation
from native_relational_qc.stress_benchmark import brickwork, describe, _memory


class StressDiagnosticsTests(unittest.TestCase):
    def test_process_memory_uses_proc_self(self):
        # In a nested PID namespace os.getpid() need not address /proc/self.
        self.assertGreater(_memory(), 0)
        self.assertGreater(_memory(field='VmHWM'), 0)

    def test_progress_does_not_change_answer(self):
        c = brickwork(4, 2, 20261018)
        events = []
        measured = probability(c, {1: 0, 2: 0}, progress=events.append)
        self.assertEqual(measured, probability(c, {1: 0, 2: 0}))
        self.assertEqual(events[-1]['event'], 'completed')
        self.assertEqual(events[-1]['peak_terms'], measured.peak_terms)

    def test_limit_exposes_partial_work_without_an_answer(self):
        c = CompactCircuit(1).add('h', 0).add('t', 0).add('h', 0)
        events = []
        with self.assertRaises(ResourceLimit) as failure:
            expectation(c, {0: 'Z'}, max_terms=1, progress=events.append)
        self.assertEqual(failure.exception.statistics['peak_terms'], 2)
        self.assertEqual(events[-1]['event'], 'resource_limit')
        self.assertNotIn('value', failure.exception.statistics)

    def test_seed_and_lightcone(self):
        c = brickwork(40, 4, 20261018)
        first = describe(c, 'local00')
        self.assertEqual(first, describe(brickwork(40, 4, 20261018), 'local00'))
        self.assertNotEqual(first['circuit_sha256'], describe(brickwork(40, 4, 20261019), 'local00')['circuit_sha256'])
        self.assertEqual(first['n_cz'], 78)
        self.assertEqual(first['n_t_or_tdg'], 200)
        self.assertEqual(first['structural_lightcone_qubits'], 8)
        self.assertEqual(describe(c, 'parity')['structural_lightcone_qubits'], 40)


if __name__ == '__main__':
    unittest.main()
