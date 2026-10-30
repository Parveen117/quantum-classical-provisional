"""Independent environment, Fock, channel, false-herald and retry checks."""
from fractions import Fraction as Q
from itertools import product
from math import comb
import unittest

from phase_seam_foundation.dual_rail import (
    ZERO, ONE, H2, COUPLER, ZETA, compose, embed, encode, evolve, fock_amplitude,
)
from phase_seam_foundation.optical_refresh import fusion_merge_certificate
from phase_seam_foundation.source_distillation import (
    DOUBLE_PAIR, _r, _round_trajectories, bell_density, count_probability,
    dilation_certificate, double_pair_channel, fused_double_pair_channel,
    loss_environment_vectors, optical_round, physical_plan,
    purification_schedule, purification_step, source_sector,
)

NOISY = (Q(3, 4),)+(Q(1, 12),)*3


class SourceChannelTests(unittest.TestCase):
    def test_shared_environment_keeps_cross_terms(self):
        rows = {r['environment']: tuple(_r(v) for v in r['vector']) for r in loss_environment_vectors()}
        self.assertEqual(rows[(1, 0, 1, 0)], (2, 0, 0, 1))
        self.assertEqual(rows[(0, 1, 0, 1)], (1, 0, 0, 2))
        self.assertEqual(sum(sum(a*a for a in v) for v in rows.values()), 12)
        self.assertEqual(sum(v[0]*v[3] for v in rows.values()), 4)

    def test_independent_permanent_dilation(self):
        c = dilation_certificate()
        self.assertTrue(c['matches_environment_channel'])
        self.assertEqual(c['probability'], Q(1, 4))
        self.assertEqual(c['density'][0][3], Q(1, 12))

    def test_full_dilation_is_normalised(self):
        u = compose(*(embed(8, (i, i+4), COUPLER) for i in range(4)))
        state = evolve(u, {occ+(0,)*4: ONE for occ in DOUBLE_PAIR})
        self.assertEqual(sum((a.norm2() for a in state.values()), ZERO), 3*ONE)

    def test_state_and_eigenvalues(self):
        expected = ((Q(5,12),0,0,Q(1,3)), (0,Q(1,12),0,0),
                    (0,0,Q(1,12),0), (Q(1,3),0,0,Q(5,12)))
        for eta in ('1/2', '243/4000', '9/10'):
            c = double_pair_channel(eta)
            self.assertEqual(c['conditional_density'], expected)
            self.assertEqual(c['conditional_bell_weights'], NOISY)
            self.assertEqual(bell_density(NOISY), expected)
            self.assertEqual(c['conditional_bell_fidelity'], Q(3,4))
            self.assertFalse(c['postselection_is_source_certification'])

    def test_zero_events_are_not_normalised(self):
        for eta in (0, 1):
            c = double_pair_channel(eta)
            self.assertEqual(c['event_probability'], 0)
            self.assertIsNone(c['conditional_density'])
            self.assertIsNone(fused_double_pair_channel(eta)['conditional_xxx'])

    def test_fusion_corrects_each_detector_branch(self):
        c = fused_double_pair_channel('1/2')
        self.assertEqual(c['fusion_success'], Q(1,2))
        self.assertEqual(c['joint_event_probability'], Q(1,8))
        self.assertEqual(c['conditional_xxx'], Q(2,3))
        self.assertEqual(c['conditional_ghz_fidelity'], Q(3,4))
        for row in c['clicks']:
            self.assertEqual(row['probability'], Q(1,4))
            self.assertEqual(row['conditional_xxx'], Q(2,3))

    def test_dephasing_is_an_extra_channel(self):
        # Dephasing the source terms before loss destroys cross terms; that
        # operation was absent from the declared v0.33 pure input state.
        rho = double_pair_channel('1/2')['conditional_density']
        diagonal_fidelity = (rho[0][0]+rho[3][3])/2
        self.assertEqual(diagonal_fidelity, Q(5,12))
        self.assertNotEqual(diagonal_fidelity, Q(3,4))

    def test_double_origin_is_not_infidelity(self):
        s = source_sector('1/40', '1/2')
        self.assertEqual(s['double_fraction'], Q(1,40))
        self.assertEqual(s['conditional_fidelity'], Q(159,160))
        self.assertEqual(s['conditional_xx'], Q(119,120))
        self.assertEqual(source_sector('1/40', '9/10')['double_fraction'], Q(1,976))
        self.assertFalse(s['source_ready'])
        self.assertIsNone(source_sector(1, 1)['conditional_fidelity'])

    def test_source_input_validation(self):
        for x in (True, 0.5, -1, 2, 'invalid'):
            with self.assertRaises((ValueError, TypeError)):
                double_pair_channel(x)


class PurificationTests(unittest.TestCase):
    def test_four_detector_kraus_matrices_from_global_fock_unitary(self):
        u = compose(embed(8, (1,2), COUPLER), embed(8, (5,6), COUPLER))
        for ra, rb in product(fusion_merge_certificate(), repeat=2):
            for bits in product((0,1), repeat=4):
                for a, b in product((0,1), repeat=2):
                    occ = [0]*8
                    occ[ra['click']] = 1; occ[4+rb['click']] = 1
                    occ[0 if a == 0 else 3] = 1; occ[4 if b == 0 else 7] = 1
                    actual = fock_amplitude(u, encode(bits,8), tuple(occ))
                    expected = ra['raw_kraus'][a][2*bits[0]+bits[1]]*rb['raw_kraus'][b][2*bits[2]+bits[3]]
                    self.assertEqual(actual, expected)

    def test_density_contraction_matches_recurrence(self):
        inputs = [NOISY, (1,0,0,0), (0,1,0,0), (0,0,1,0), (0,0,0,1),
                  (Q(1,4),)*4, (Q(3,5),Q(1,5),Q(1,10),Q(1,10))]
        for p, basis in product(inputs, 'ZX'):
            theoretical = purification_step(p, basis)
            actual = optical_round(p, basis)
            prob = actual['herald_probability']
            normalised = tuple(tuple(v/prob for v in row) for row in actual['valid_payload_density'])
            self.assertEqual(prob, theoretical['success_probability'])
            self.assertEqual(normalised, bell_density(theoretical['output_weights']))
            self.assertEqual(actual['false_payload_probability'], 0)

    def test_named_result_and_retry_cost(self):
        z = purification_step(NOISY)
        self.assertEqual(z['success_probability'], Q(13,36))
        self.assertEqual(z['output_fidelity'], Q(41,52))
        self.assertEqual(z['expected_input_pairs'], Q(72,13))
        zx = purification_schedule(NOISY, 'ZX')
        self.assertEqual(zx['fidelity'], Q(841,932))
        self.assertEqual(zx['expected_raw_pairs'], Q(7488,233))
        four = purification_schedule(NOISY)
        self.assertEqual(four['fidelity'], Q(62828777761,63748336772))
        self.assertGreater(four['expected_raw_pairs'], 300)
        self.assertFalse(four['noisy_rounds_composed'])

    def test_both_error_bases_matter(self):
        one = purification_schedule(NOISY, 'Z')
        same = purification_schedule(NOISY, 'ZZ')
        alternate = purification_schedule(NOISY, 'ZX')
        self.assertLess(same['fidelity'], one['fidelity'])
        self.assertGreater(alternate['fidelity'], one['fidelity'])

    def test_no_round_and_mixed_fixed_point(self):
        self.assertEqual(purification_schedule(NOISY, '')['expected_raw_pairs'], 1)
        mixed = purification_step((Q(1,4),)*4)
        self.assertEqual(mixed['output_weights'], (Q(1,4),)*4)
        self.assertEqual(mixed['success_probability'], Q(1,4))

    def test_plan_has_physical_detector_and_retry_scope(self):
        p = physical_plan()
        self.assertEqual(p['detector_modes'], [1,2,5,6])
        self.assertEqual(p['output_rails'], [[0,3],[4,7]])
        self.assertEqual(p['local_fusion_couplers'], 2)
        self.assertEqual(p['x_basis_extra_hadamards'], 6)
        self.assertEqual(p['coherent_h_heaters'], dict(lower=16,upper=0,before=32,after=32))
        self.assertTrue(p['coherent_h_verified'])

    def test_invalid_probability_and_schedule_inputs(self):
        for p in ((1,0,0), (1,1,0,0), (True,0,0,0), (0.75,0.25,0,0), (2,-1,0,0)):
            with self.assertRaises((ValueError, TypeError)):
                purification_step(p)
        for b in ('Y', 'Z'*7, ['Z']):
            with self.assertRaises((ValueError, TypeError)):
                purification_schedule(NOISY, b)


class NoisyRoundTests(unittest.TestCase):
    def test_detector_distribution_normalised(self):
        for n, d, h in product(range(3), (Q(0),Q(2,3),Q(1)), (Q(0),Q(1,100),Q(1))):
            self.assertEqual(sum(count_probability(n,r,d,h) for r in range(4)), 1)

    def test_loss_trajectories_normalised_before_readout(self):
        for first, second, mask in product(range(4), range(4), range(16)):
            norm = sum((_r(amp.norm2()) for env, true, payload in _round_trajectories(first,second,mask)
                        for occ, amp in payload), Q(0))
            self.assertEqual(norm, 1)

    def test_all_heralds_include_invalid_payloads(self):
        # Independent count argument for two perfect Phi+ pairs: initial
        # detector occupancies (1,1), (0,0), (2,2) have weights 1/2,1/4,1/4.
        for m, d in ((Q(1),Q(9,10)), (Q(9,10),Q(1)), (Q(1,2),Q(2,3)), (Q(0),Q(1))):
            c = optical_round((1,0,0,0), input_survival=m, detector_efficiency=d)
            expected_herald = (m*d)**2*(Q(1,2)+(1-m*d)**2)
            expected_valid = m**4*d**2/2
            self.assertEqual(c['herald_probability'], expected_herald)
            self.assertEqual(c['valid_payload_probability'], expected_valid)
            self.assertEqual(c['fidelity_weight'], expected_valid)

    def test_detector_loss_is_not_just_a_rate(self):
        c = optical_round((1,0,0,0), detector_efficiency='9/10')
        self.assertEqual(c['conditional_fidelity'], Q(50,51))
        self.assertEqual(c['valid_sector_fidelity'], 1)
        self.assertEqual(c['false_payload_probability'], Q(81,10000))
        self.assertFalse(c['payload_validity_is_observed'])

    def test_memory_loss_is_not_observed_by_herald(self):
        c = optical_round((1,0,0,0), input_survival='9/10')
        self.assertEqual(c['conditional_fidelity'], Q(27,34))
        self.assertEqual(c['false_payload_probability'], Q(1701,20000))

    def test_dark_only_vacuum_control(self):
        h = Q(1,1000)
        c = optical_round((1,0,0,0), input_survival=0, dark_per_mode=h)
        self.assertEqual(c['herald_probability'], (2*h*(1-h))**2)
        self.assertEqual(c['conditional_fidelity'], 0)
        self.assertIsNone(c['valid_sector_fidelity'])

    def test_dark_counts_reject_good_patterns_and_accept_empty_detectors(self):
        h = Q(1,100)
        c = optical_round((1,0,0,0), dark_per_mode=h)
        self.assertEqual(c['valid_payload_probability'], (1-h)**4/2)
        self.assertEqual(c['false_payload_probability'], h**2*(1-h)**2)

    def test_random_dark_herald_loses_phase_information(self):
        c = optical_round((1,0,0,0), detector_efficiency=0, dark_per_mode='1/100')
        self.assertEqual(c['valid_payload_fraction'], Q(1,2))
        self.assertEqual(c['valid_sector_fidelity'], Q(1,2))
        self.assertEqual(c['conditional_fidelity'], Q(1,4))

    def test_complete_detector_failure_without_darks(self):
        c = optical_round(NOISY, detector_efficiency=0)
        self.assertEqual(c['herald_probability'], 0)
        self.assertIsNone(c['conditional_fidelity'])

    def test_noisy_conditional_density_is_positive(self):
        # These Bell-diagonal/X-family outputs have two 2x2 Hermitian blocks.
        for basis in 'ZX':
            c = optical_round(NOISY,basis,input_survival='9/10',detector_efficiency='4/5',dark_per_mode='1/100')
            rho = c['valid_payload_density']
            self.assertLessEqual(c['valid_payload_probability'], c['herald_probability'])
            self.assertLessEqual(c['fidelity_weight'], c['valid_payload_probability'])
            for a,b in ((0,3),(1,2)):
                self.assertGreaterEqual(rho[a][a],0)
                self.assertEqual(rho[a][b],rho[b][a])
                self.assertGreaterEqual(rho[a][a]*rho[b][b]-rho[a][b]**2,0)

    def test_noise_input_validation(self):
        for value in (True, 0.9, -1, 2):
            with self.assertRaises((ValueError, TypeError)):
                optical_round(NOISY, detector_efficiency=value)
        with self.assertRaises(ValueError):
            count_probability(3,1,1,0)


if __name__ == '__main__':
    unittest.main()
