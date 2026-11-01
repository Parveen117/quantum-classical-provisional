"""Covariance, sequential backaction, and record-dependent source/axis controls."""
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from native_relational_qc.calculator import calculate
from native_relational_qc.certify import flat_field
from native_relational_qc import moving_observer as moving


class MovingObserverTests(unittest.TestCase):
    def test_oriented_cut_pair_is_transport_on_declared_phase_carrier(self):
        # Cut axis alpha=pi*h/16, phase phi=2*pi*r/16. This is algebra
        # on known scalar phases, not a deterministic antiunitary quantum gate.
        F = flat_field()
        def cut(z, axis):
            return F.root(4*axis)*z.conjugate()
        for phase in range(16):
            z = F.root(4*phase)
            for first in range(16):
                self.assertEqual(cut(cut(z, first), first), z)
                for second in (0, 3, 7, 15):
                    self.assertEqual(cut(cut(z, first), second), F.root(4*(second-first))*z)

    def test_exact_campaign_distinguishes_covariance_from_physical_feedback(self):
        results = {name: calculate(request) for name, request in moving.cases().items()}
        checks = moving.check_results(results)
        self.assertTrue(all(checks.values()), checks)
        for name, expected in (('none', Fraction(1, 2)), ('observer', Fraction(3, 4)),
                               ('source', Fraction(1, 4)), ('both', Fraction(1, 2))):
            self.assertEqual(moving.law(results['feedback_'+name], 'second')['1'], expected)
        self.assertEqual(moving.law(results['record_disabled'], 'second')['1'], 1)

    def test_deferred_records_match_explicit_sequential_projective_measurements(self):
        # Independent NumPy projectors: actually condition after the first read,
        # then evolve and measure at that branch's axis. No deferred CNOT circuit.
        basis = lambda angle, bit: np.array([1, (-1)**bit*np.exp(1j*angle)])/np.sqrt(2)
        for phi, first_axis, drift, second_axis, source, observer in (
            (4, 0, 4, 0, 0, 4), (3, 1, 2, 5, 7, -2), (6, 4, 1, 3, -3, 5)):
            kwargs = dict(signal_steps=phi, first_axis=first_axis, drift_steps=drift,
                          second_axis=second_axis, source_feedback=source, observer_feedback=observer)
            result = calculate(moving.feedback_request(**kwargs))
            actual = moving.law(result, 'records')
            self.assertEqual(actual, moving.analytic_joint(**kwargs))
            for first in (0, 1):
                ket = basis(first_axis*np.pi/8, first)
                weight = abs(np.vdot(ket, basis(phi*np.pi/8, 0)))**2
                evolved = np.diag([1, np.exp(1j*(drift+source*first)*np.pi/8)])@ket
                for second in (0, 1):
                    probability = weight*abs(np.vdot(basis((second_axis+observer*first)*np.pi/8, second), evolved))**2
                    self.assertAlmostEqual(probability, float(moving.display(actual[str(first)+str(second)])['decimal']), delta=2e-10)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'), 'optional Qiskit reference')
    def test_qiskit_uses_same_record_order_and_frame_convention(self):
        for request in (moving.feedback_request(observer_feedback=4),
                        moving.frame_request((2, 5, 1, 7, 4), representation='moving')):
            check = moving.qiskit_check(request, calculate(request))
            self.assertTrue(check['passed'], check)

    def test_incomplete_run_keeps_requests_and_does_not_certify(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'audit'
            with patch.object(moving, 'run_calculation', return_value=dict(status='time_limit')):
                with self.assertRaises(RuntimeError):
                    moving.audit(path)
            self.assertEqual(json.loads((path/'status.json').read_text())['status'], 'incomplete')
            self.assertFalse((path/'summary.json').exists())
            self.assertEqual(len(list((path/'inputs').glob('*.json'))), 47)
            with self.assertRaises(FileExistsError):
                moving.audit(path)


if __name__ == '__main__':
    unittest.main()
