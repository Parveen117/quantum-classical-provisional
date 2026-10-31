"""Bounded causal feedback, exact path replay, and usable CLI records."""
from copy import deepcopy
from fractions import Fraction
import contextlib
import importlib.util
import io
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from native_relational_qc.calculator import calculate
from native_relational_qc.certify import exact_value, flat_field
from native_relational_qc import observer_tracking as tracking
from native_relational_qc.__main__ import main as cli
from benchmarks import moving_observer_tracking_audit as campaign


class TrackingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calibration = [calculate(tracking.calculator_request([k], [0])) for k in range(32)]
        cls.bank = tracking.likelihoods(cls.calibration)
        cls.planner = tracking.Planner(tracking.Model(3))
        cls.policy = cls.planner.adaptive()

    def test_exact_likelihoods_reject_incomplete_or_tampered_calibration(self):
        self.assertEqual(self.bank[0], 1)
        self.assertEqual(self.bank[8], Fraction(1, 2))
        self.assertEqual(self.bank[16], 0)
        with self.assertRaises(ValueError):
            tracking.likelihoods([dict(status='time_limit')]*32)
        bad = deepcopy(self.calibration)
        bad[0]['answers'][0]['probabilities']['0']['exact'] = bad[8]['answers'][0]['probabilities']['0']['exact']
        with self.assertRaises(ArithmeticError):
            tracking.likelihoods(bad)

    def test_bellman_matches_exhaustive_two_round_contingent_plans(self):
        planner = tracking.Planner(tracking.Model(2))
        policy = planner.adaptive()
        scores = []
        # Enumerate all 16 assignments of a second axis to the two possible
        # first records; the first measurement has the common fixed axis 0.
        for a0, a1 in product(range(4), repeat=2):
            utility = 0.0
            for first, action in enumerate((a0, a1)):
                w = planner.prior*(planner.p0[0, 0] if first == 0 else 1-planner.p0[0, 0])
                for second in (0, 1):
                    p = planner.p0[1, action]
                    branch = w*(p if second == 0 else 1-p)
                    utility += float((branch@planner.utility).max())
            scores.append((1-utility)/2)
        self.assertAlmostEqual(policy['planning']['numerical_expected_loss'], min(scores), places=12)
        open_loop, searched = planner.open_loop_search()
        self.assertEqual(policy['planning']['leaf_evaluations'], open_loop['planning']['leaf_evaluations'])
        self.assertEqual(len(searched), 4)

    def test_adaptive_record_paths_equal_full_calculator_circuits_and_co_rotations(self):
        phases = [3, 2, 1, 0]
        result = tracking.exact_evaluate(self.policy, phases, self.bank, keep_branches=True)
        self.assertEqual(result['normalization'], 1)
        self.assertEqual(sum(result['branches'].values(), flat_field()()), 1)
        for bits in map(''.join, product('01', repeat=3)):
            axes = tracking.branch_axes(self.policy, bits)
            request = tracking.calculator_request(phases[:-1], axes, bits)
            actual = exact_value(calculate(request)['answers'][0]['value']['exact'])
            self.assertEqual(actual, result['branches'][bits])
            shifted = tracking.calculator_request([p+3 for p in phases[:-1]], [a+3 for a in axes], bits)
            self.assertEqual(actual, exact_value(calculate(shifted)['answers'][0]['value']['exact']))

    def test_uninformative_records_have_exact_half_error_on_uniform_phase_family(self):
        errors = [tracking.exact_evaluate(self.policy, [start-t for t in range(4)], self.bank,
                                         flip=Fraction(1, 2))['error'] for start in range(0, 32, 2)]
        self.assertEqual(sum(errors, flat_field()())*Fraction(1, 16), Fraction(1, 2))

    def test_numerical_planning_objective_matches_exact_prior_risk(self):
        model = tracking.Model(3)
        errors = [tracking.exact_evaluate(self.policy, [start+t*velocity for t in range(4)], self.bank)['error']
                  for start,velocity in model.hypotheses]
        mean = sum(errors, flat_field()())*Fraction(1, len(errors))
        self.assertAlmostEqual(float(tracking.display(mean)['decimal']),
                               self.policy['planning']['numerical_expected_loss'], delta=2e-11)

    def test_records_are_causal_and_common_frame_shift_only_relabels_coordinates(self):
        for length in range(4):
            bits = '010'[:length]
            ordinary = tracking.read_records(self.policy, bits)
            shifted = tracking.read_records(self.policy, bits, frame_step=3)
            key = 'predicted_phase_step' if length == 3 else 'next_axis_step'
            self.assertEqual(shifted[key], (ordinary[key]+3)%32)
            self.assertEqual(ordinary['probes_used'], length)
            self.assertEqual(ordinary['probes_remaining'], 3-length)
            for a,b in zip(ordinary['measurement_history'], shifted['measurement_history']):
                self.assertEqual(a['bit'], b['bit'])
                self.assertEqual((a['axis_step']+3)%32, b['axis_step'])
        self.assertNotEqual(tracking.read_records(self.policy, '00')['next_axis_step'],
                            tracking.read_records(self.policy, '01')['next_axis_step'])

    def test_policy_integrity_and_resource_boundaries(self):
        for rounds in (0, 7, True, 2.5):
            with self.assertRaises(ValueError):
                tracking.Model(rounds)
        for bits in ('2', '0000', None):
            with self.assertRaises(ValueError):
                tracking.read_records(self.policy, bits)
        tampered = deepcopy(self.policy)
        tampered['tree']['axis'] = 31
        with self.assertRaises(ValueError):
            tracking.validate_policy(tampered)
        forged = tracking.seal({k:v for k,v in tampered.items() if k != 'fingerprint'})
        with self.assertRaises(ValueError):
            tracking.validate_policy(forged)
        for flip in (0.1, Fraction(-1, 10), Fraction(3, 4)):
            with self.assertRaises(ValueError):
                tracking.exact_evaluate(self.policy, [0, 1, 2, 3], self.bank, flip=flip)

    def test_cli_consumes_only_recorded_bits_and_reports_next_axis(self):
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp)/'policy.json'
            policy.write_text(json.dumps(self.policy))
            output = Path(tmp)/'result.json'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli(['observer-track', '--policy', str(policy), '--records', '01', '--out', str(output)]), 0)
            response = json.loads(output.read_text())
            self.assertEqual(response['status'], 'next_measurement')
            self.assertEqual(response['next_axis_step'], tracking.read_records(self.policy, '01')['next_axis_step'])
            self.assertIsNone(response['hardware_job_id'])

    def test_protocol_keeps_stress_families_declared_and_complete(self):
        self.assertEqual(json.loads(campaign.PROTOCOL_PATH.read_text()), campaign.protocol())
        rows = campaign.evaluation_cases()
        self.assertEqual(len(rows), 256)
        self.assertEqual(len({r['id'] for r in rows}), 256)
        for row in rows:
            self.assertEqual(len(row['phases']), 7)
            if row['family'] == 'reversing_drift':
                self.assertEqual(row['phases'][0], row['phases'][-1])
            if row['family'] != 'model_grid':
                self.assertEqual(row['phases'][0]%2, 1)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'), 'optional Qiskit reference')
    def test_independent_reference_checks_branch_bit_order(self):
        for bits in ('001', '110'):
            request = tracking.calculator_request([3, 7, 11], tracking.branch_axes(self.policy, bits), bits)
            result = campaign.reference(request, calculate(request))
            self.assertTrue(result['passed'], result)

    def test_audit_timeout_is_incomplete_and_preserves_frozen_models(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            path = Path(tmp)/'audit'
            with patch.object(campaign, 'run_calculation', return_value=dict(status='time_limit')):
                with self.assertRaises(RuntimeError):
                    campaign.audit(path, 'a'*40)
            self.assertEqual(json.loads((path/'status.json').read_text())['status'], 'incomplete')
            self.assertTrue((path/'frozen_policies.json').exists())
            self.assertFalse((path/'summary.json').exists())
            with self.assertRaises(FileExistsError):
                campaign.audit(path, 'a'*40)


if __name__ == '__main__':
    unittest.main()
