"""SP1 application checked against convex preparations and an independent channel."""
import contextlib
from fractions import Fraction as Q
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from native_relational_qc.__main__ import main as cli
from native_relational_qc.calculator import calculate
from native_relational_qc.certify import exact_value, flat_field
from native_relational_qc.compact import ResourceLimit
from native_relational_qc import observer_cycle as cycle
from native_relational_qc import observer_state as state
from native_relational_qc import observer_tracking as tracking


def decode(record):
    return exact_value(record['real']['exact']) + flat_field().imag() * exact_value(record['imag']['exact'])


class ObserverCycleTests(unittest.TestCase):
    def test_block_powers_match_existing_convex_source_and_calculator_readout(self):
        F = flat_field()
        bank = tracking.likelihoods([calculate(tracking.calculator_request([k], [0])) for k in range(32)])
        for start, velocity, offset, retention in (
            (0, 8, 8, Q(3, 4)), (3, -1, -8, Q(7, 8)),
            (31, 5, 1, Q(1, 3)), (5, 0, 8, Q(0)), (1, 9, 6, Q(1)),
        ):
            mixtures = state.source_mixtures(start, velocity, offset, retention=retention)
            A, c = state.source_affine(start, velocity, offset, retention=retention)
            for t in range(6):
                self.assertEqual(A * state.coherence(mixtures[t]) + c, state.coherence(mixtures[t + 1]))
            for steps, repetitions in ((1, 6), (2, 3), (3, 2), (6, 1)):
                out = cycle.audit_cycles(start=start, velocity=velocity, offset=offset,
                                         retention=retention, steps_per_cycle=steps,
                                         cycles=repetitions, axis=5)
                self.assertEqual(decode(out['state']['final']), state.coherence(mixtures[6]))
                probability = sum((bank[(a - 5) % 32] * w for a, w in mixtures[6]), F())
                self.assertEqual(exact_value(out['observer']['final_probability_zero']['exact']), probability)

    def test_closed_rotation_is_not_state_reset_and_raw_b_is_not_obstruction(self):
        F = flat_field(); i = F.imag()
        out = cycle.audit_cycles(cycles=1)
        self.assertEqual(decode(out['cycle']['H']), Q(81, 256))
        self.assertEqual(decode(out['cycle']['b']), (-21 + 28 * i) / 256)
        self.assertEqual(decode(out['state']['final']), (15 + 7 * i) / 64)
        self.assertEqual(decode(out['reset']['fixed_point']), (-3 + 4 * i) / 25)
        self.assertTrue(out['cycle']['rotation_closes'])
        self.assertFalse(out['cycle']['channel_is_identity'])
        self.assertFalse(out['state']['returns_to_initial'])
        self.assertTrue(out['reset']['obstruction_zero'])
        # Omitting affine transport would instead predict 4*c = i.
        self.assertNotEqual(decode(out['cycle']['b']), i)

    def test_equal_detector_reading_can_hide_state_and_future_probe_reveals_it(self):
        out = cycle.audit_cycles(retention=Q(1), steps_per_cycle=1, cycles=1, axis=4, frame_step=8)
        self.assertFalse(out['state']['returns_to_initial'])
        self.assertTrue(out['observer']['repeats_at_requested_cycles'])
        self.assertFalse(out['observer']['two_axis_readout_returns'])
        self.assertEqual(out['observer']['future_bank_rank'], 2)
        self.assertEqual(out['observer']['distinguishing_future_cycles'], 1)
        # A co-rotating coordinate looks stationary only with its calibration retained.
        self.assertTrue(out['frame']['relative_state_returns'])
        self.assertTrue(out['frame']['laboratory_reconstruction_verified'])
        self.assertTrue(out['frame']['analyzer_transported_probability_verified'])

    def test_real_cycle_multiplier_can_leave_hidden_difference_hidden_forever(self):
        out = cycle.audit_cycles(start=8, velocity=16, retention=Q(1),
                                 steps_per_cycle=1, cycles=1, axis=0)
        self.assertFalse(out['state']['returns_to_initial'])
        self.assertTrue(out['observer']['repeats_at_requested_cycles'])
        self.assertEqual(out['observer']['future_bank_rank'], 1)
        self.assertIsNone(out['observer']['distinguishing_future_cycles'])
        self.assertFalse(out['observer']['two_axis_readout_returns'])

    def test_moving_frame_transports_the_complete_driven_update(self):
        F = flat_field(); q = F.root(6)
        A, c = state.source_affine(3, 5, 8)
        for t in range(1, 6):
            q = F.root(-6) * A * q + F.root(-6 * t) * c
        out = cycle.audit_cycles(start=3, velocity=5, offset=8, steps_per_cycle=1,
                                 cycles=5, frame_step=3)
        self.assertEqual(decode(out['frame']['relative_final']), q)
        wrong = F.root(6)
        for _ in range(5):
            wrong = F.root(-6) * A * wrong + c
        self.assertNotEqual(q, wrong)

    def test_identity_source_retains_protocol_count_and_zero_exponent_is_identity(self):
        out = cycle.audit_cycles(retention=Q(1), cycles=1_000_000)
        self.assertTrue(out['cycle']['channel_is_identity'])
        self.assertTrue(out['state']['returns_to_initial'])
        self.assertFalse(out['history']['retained_counter_returns'])
        self.assertEqual(out['history']['modeled_channel_applications'], 4_000_000)
        self.assertLess(out['work']['affine_compositions'], 50)
        self.assertIsNone(out['history']['physical_duration'])
        self.assertFalse(out['reset']['state_event_counter_from_nonzero_obstruction'])
        zero = cycle.audit_cycles(cycles=0, frame_step=7)
        self.assertTrue(zero['state']['returns_to_initial'])
        self.assertTrue(zero['history']['retained_counter_returns'])
        self.assertEqual(zero['frame']['final_angle'], 0)

    def test_limits_invalid_inputs_and_cli_do_not_emit_partial_success(self):
        for change in (dict(cycles=-1), dict(cycles=True), dict(cycles=1_000_001),
                       dict(steps_per_cycle=0), dict(steps_per_cycle=33),
                       dict(retention=0.75), dict(retention=Q(1, 17)),
                       dict(retention=True), dict(max_coeff_bits=127),
                       dict(start=True), dict(axis=0.5), dict(frame_step=True)):
            with self.assertRaises(ValueError): cycle.audit_cycles(**change)
        with self.assertRaises(ResourceLimit):
            cycle.audit_cycles(cycles=1000, max_coeff_bits=128)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'report.json'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli(['observer-cycle', '--out', str(path)]), 0)
            self.assertEqual(json.loads(path.read_text())['status'], 'complete')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli(['observer-cycle', '--cycles', '1000', '--max-coeff-bits', '128', '--out', str(path)]), 2)
            limited = json.loads(path.read_text())
            self.assertEqual(limited['status'], 'resource_limit')
            self.assertNotIn('state', limited)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                cli(['observer-cycle', '--retention', '1/0'])
            self.assertEqual(error.exception.code, 2)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'), 'optional independent Qiskit channel')
    def test_independent_kraus_evolution_matches_exact_source_and_fixed_point(self):
        from qiskit.quantum_info import DensityMatrix, Kraus
        for start, velocity, offset, retention in ((3, -1, 8, Q(3, 4)), (0, 8, 8, Q(1)),
                                                    (4, 2, -8, Q(0)), (7, 5, 3, Q(1, 3))):
            phase = lambda a: np.exp(2j * np.pi * a / 32)
            psi = np.array([1, phase(start)]) / np.sqrt(2)
            drive = np.array([1, phase(start + offset)]) / np.sqrt(2)
            channel = Kraus([np.sqrt(float(retention)) * np.diag([1, phase(velocity)])] +
                            [np.sqrt(float(1 - retention)) * np.outer(drive, np.eye(2)[j]) for j in range(2)])
            self.assertTrue(channel.is_cptp())
            rho = DensityMatrix(psi)
            for _ in range(12):
                rho = rho.evolve(channel)
            out = cycle.audit_cycles(start=start, velocity=velocity, offset=offset,
                                     retention=retention, cycles=3, steps_per_cycle=4)
            self.assertAlmostEqual(complex(decode(out['state']['final'])), 2 * rho.data[1, 0], delta=2e-12)
            fixed = complex(decode(out['reset']['fixed_point']))
            stationary = DensityMatrix(np.array([[1, fixed.conjugate()], [fixed, 1]]) / 2)
            for _ in range(4):
                stationary = stationary.evolve(channel)
            self.assertAlmostEqual(fixed, 2 * stationary.data[1, 0], delta=2e-12)


if __name__ == '__main__':
    unittest.main()
