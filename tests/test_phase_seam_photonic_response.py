"""Ideal response identities, observer blindness, and existing-engine checks."""
from fractions import Fraction
import unittest

from native_relational_qc.cyclotomic64 import ONE, ZERO
from native_relational_qc.phase_backend import Phase64Circuit, prepare
from phase_seam_foundation.photonic_io import _two_path, calibration_template
from phase_seam_foundation.photonic_response import (
    optical_response, unit_jet, exact_rank, compose_response, response_plan,
)
from phase_seam_foundation.sector_control import pulse_coefficients


def steps(theta):
    return ((32-theta)%64, 0, 48, 48)


class PhotonicResponseTests(unittest.TestCase):
    def test_unit_word_matches_native_exchange_all_64_angles(self):
        for theta in range(64):
            u, _ = unit_jet(steps(theta))
            a, b = pulse_coefficients(theta)
            self.assertEqual(u, ((a,b),(b,a)), theta)

    def test_reference_probabilities_match_existing_phase64_engine(self):
        theta, reference = 8, 3
        expected = optical_response(steps(theta), reference_steps=reference)
        for s in range(2):
            for r in range(2):
                for alpha in (0,16):
                    c = Phase64Circuit(8)
                    if s: c.add('x',0)
                    def word(ports, *operations): _two_path(c, ports, operations)
                    word((s,2), ('h',0))
                    word((0,1), ('phase',48), ('phase',16), ('h',0), ('phase',16),
                         ('phase',32-theta), ('phase',16), ('h',0), ('phase',16), ('phase',48))
                    word((0,2), ('phase',reference))
                    word((r,2), ('phase',-alpha), ('h',0))
                    state = prepare(c)
                    self.assertTrue(all(k < 3 for k in state.amplitudes))
                    label = f'reference:{s}->{r}:analyzer_{alpha}'
                    probability = state.probability({0:r, 1:0})
                    self.assertEqual(probability, expected['probabilities'][expected['labels'].index(label)])

    def test_analytic_derivatives_equal_exact_parameter_shift(self):
        point, ref = (7,11,19,33), 5
        base = optical_response(point, reference_steps=ref)
        for col in range(5):
            shifted = []
            for sign in (1,-1):
                params = list((*point,ref)); params[col] = (params[col]+sign*16)%64
                shifted.append(optical_response(tuple(params[:4]), reference_steps=params[4]))
            for row, plus, minus in zip(base['jacobian'], shifted[0]['probabilities'], shifted[1]['probabilities']):
                self.assertEqual(row[col], (plus-minus)/2)

    def test_all_64_angles_have_declared_local_rank(self):
        for theta in range(64):
            singular = theta in (0,32)
            for kind, generic in (('basis',1),('local',3),('reference',4)):
                matrix = optical_response(steps(theta), measurements=kind)['jacobian']
                self.assertEqual(exact_rank(matrix), generic-int(singular), (theta,kind))

    def test_global_phase_including_reference_is_unobservable(self):
        point, ref, shift = (7,11,19,33), 5, 9
        before = optical_response(point, reference_steps=ref)
        after = optical_response((point[0]+shift,point[1]+shift,*point[2:]), reference_steps=ref+shift)
        self.assertEqual(before['probabilities'], after['probabilities'])
        self.assertTrue(all(row[0]+row[1]+row[4] == ZERO for row in before['jacobian']))
        self.assertTrue(any(row[0]+row[1] != ZERO for row in before['jacobian']))

    def test_basis_reads_miss_trims_and_common_phase(self):
        rows = optical_response(steps(16), measurements='basis')['jacobian']
        self.assertTrue(all(row[2] == row[3] == row[4] == ZERO for row in rows))
        self.assertTrue(all(row[0]+row[1] == ZERO for row in rows))

    def test_coupled_response_retains_blindness_and_reference_crosstalk(self):
        # Algebraic fixture: first control heats both arms, second shifts input.
        # Full column rank of B alone does not establish optical observability.
        b = ((1,0),(1,0),(0,1),(0,0),(0,0))
        basis = optical_response(steps(16), measurements='basis')['jacobian']
        full = optical_response(steps(16))['jacobian']
        self.assertEqual(exact_rank(b), 2)
        self.assertEqual(exact_rank(compose_response(basis,b)), 0)
        self.assertEqual(exact_rank(compose_response(full,b)), 2)
        # Heating the reference equally makes that common response disappear.
        drifting = (*b[:4],(1,0))
        self.assertEqual(exact_rank(compose_response(full,drifting)), 1)

    def test_exact_rank_accepts_dependence_and_rejects_invalid_inputs(self):
        self.assertEqual(exact_rank(((1,2),(2,4))),1)
        self.assertEqual(exact_rank(((0,0),(0,0))),0)
        self.assertEqual(exact_rank(((1,Fraction(1,3)),(0,1))),2)
        for rows in ((), ((1,),(1,2)), ((True,),), ((0.1,),), ((complex(1,2),),), ((1,)*33,)):
            with self.assertRaises((TypeError,ValueError)): exact_rank(rows)
        with self.assertRaises(ValueError): compose_response(((1,2),),((1,),(1,)))

    def test_phase_input_validation_and_unmeasured_plan_binding(self):
        unit_jet((1,0,0,0))  # cached numeric tuple must not admit an equal bool tuple
        for point in ([0,0,0,0], (0,0,0), (65,0,0,0), (True,0,0,0), (0.1,0,0,0)):
            with self.assertRaises((TypeError,ValueError)): unit_jet(point)
        with self.assertRaises(ValueError): optical_response(steps(16),measurements='temperature')
        plan, physical = response_plan(), calibration_template(physical_layout=True)
        for key in ('io_sha256','layout_spec_sha256','layout_gds_sha256'):
            self.assertEqual(plan[key],physical[key])
        self.assertEqual(len(plan['power_control_order']),28)
        self.assertEqual(len(plan['all_recorded_actuators']),31)
        self.assertEqual(plan['status'],'UNMEASURED_PLAN')
        self.assertEqual(plan['acquisitions'],[])
        self.assertFalse(plan['hardware_submitted'])
        for unit in plan['units']:
            self.assertNotIn(unit['reference_path'],unit['paths'])
            self.assertEqual(len(unit['phase_per_power_rad_per_w']),5)
            self.assertTrue(all(len(row)==28 and all(x is None for x in row)
                                for row in unit['phase_per_power_rad_per_w']))
        plan['power_control_order'].clear()
        self.assertEqual(len(response_plan()['power_control_order']),28)


if __name__ == '__main__': unittest.main()
