"""Age composition, coherent erasure recovery, refresh costs and bad evidence.

The group decoder is checked against the existing GF(2) logical-support
algorithm. Its channel is checked by an external Bell reference, with all
measurement outcomes averaged, including controls that lose coherence.
"""
from fractions import Fraction as F
from itertools import product
from math import comb
import unittest

from native_relational_qc.exact import ONE, Exact
from phase_seam_foundation.loss_tolerant_code import (
    code, code_grade, encoded_walk, evaluate, loss_polynomials, recoverable,
)
from phase_seam_foundation.loss_refresh import (
    MAX_ROUNDS, memory_lifetime, recovery_plan, refresh_budget,
    refresh_circuit, refresh_witness,
)
from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.tree_build import build_grade


class LifetimeTests(unittest.TestCase):
    def test_bare_photon_composes_without_a_reset(self):
        for t in (0, 1, 2, 50, 100):
            w = memory_lifetime([1], F(99, 100), t)
            self.assertEqual(w['p_no_refresh'], F(99, 100)**t)
            self.assertEqual(w['p_no_refresh'], w['p_ideal_refresh_every_round'])

    def test_zero_loss_total_loss_and_zero_time(self):
        for br in ([2, 2], [3, 3]):
            self.assertEqual(memory_lifetime(br, 1, 50)['p_no_refresh'], 1)
            self.assertEqual(memory_lifetime(br, 0, 1)['p_no_refresh'], 0)
            self.assertEqual(memory_lifetime(br, 0, 0)['p_no_refresh'], 1)

    def test_two_round_distribution_by_explicit_loss_history(self):
        # 64 x 64 independent first/second-round potential loss masks. A loss
        # on an already absent photon has no further effect: union the masks.
        c = code([2, 2]); n = c['photons']; m = F(3, 4)
        weights = [m**(n-mask.bit_count())*(1-m)**mask.bit_count() for mask in range(1 << n)]
        good = [recoverable(c['x_logical'], c['stabilisers'], mask)
                and recoverable(c['z_logical'], c['stabilisers'], mask)
                for mask in range(1 << n)]
        total = sum((weights[a]*weights[b] for a, b in product(range(1 << n), repeat=2)
                     if good[a | b]), F())
        self.assertEqual(memory_lifetime([2, 2], m, 2)['p_no_refresh'], total)

    def test_long_memory_counterexample_is_exact_not_rounded(self):
        w = memory_lifetime([4, 3], '99/100', 50)
        self.assertTrue(F(4042, 10000) < w['p_no_refresh'] < F(4043, 10000))
        self.assertTrue(F(9998, 10000) < w['p_ideal_refresh_every_round'] < 1)
        self.assertGreater(w['effective_photon_loss'].denominator.bit_length(), 256)

    def test_declared_limits_and_input_types(self):
        for m in (True, .99, '2', '-1/10'):
            with self.assertRaises((TypeError, ValueError)):
                memory_lifetime([2, 2], m, 1)
        for t in (True, -1, MAX_ROUNDS+1):
            with self.assertRaises((TypeError, ResourceLimit)):
                memory_lifetime([2, 2], 1, t)
        with self.assertRaises(ResourceLimit):
            memory_lifetime([10**9, 10**9], 1, 1)


class CoherentRecoveryTests(unittest.TestCase):
    def test_group_rule_matches_gf2_for_every_small_tree_loss_pattern(self):
        for br in ([2, 2], [3, 2], [3, 3]):
            c = code(br)
            for lost in range(1 << c['photons']):
                expected = (recoverable(c['x_logical'], c['stabilisers'], lost)
                            and recoverable(c['z_logical'], c['stabilisers'], lost))
                self.assertEqual(recovery_plan(br, lost)['recoverable'], expected, (br, lost))

    def test_every_correctable_six_photon_pattern_transfers_entanglement(self):
        passed = 0
        for lost in range(64):
            if recovery_plan([2, 2], lost)['recoverable']:
                w = refresh_witness(lost_masks=(lost,))
                self.assertEqual(w['entanglement_fidelity'], ONE, lost)
                self.assertEqual(w['correlations'], {'X': ONE, 'Y': -ONE, 'Z': ONE})
                self.assertFalse(w['outcomes_postselected'])
                passed += 1
        self.assertEqual(passed, 13)  # no loss, six single losses, six double losses

    def test_two_fresh_blocks_preserve_an_external_reference(self):
        for schedule in ((1, 16), (8, 2), (5, 48)):
            w = refresh_witness(lost_masks=schedule)
            self.assertEqual(w['entanglement_fidelity'], ONE)
            self.assertEqual(w['transfers'], 2)
            self.assertEqual(w['simulator_wires'], 20)
            self.assertEqual(w['peak_live_data_and_helper_wires'], 13)

    def test_feedback_is_necessary_negative_control(self):
        w = refresh_witness(lost_masks=(1,), corrections=False)
        self.assertEqual(w['entanglement_fidelity'], Exact(F(1, 4)))
        # No teleportation here: the decoder's own missing parity correction
        # dephases an otherwise perfectly encoded Bell reference.
        decoder_only = refresh_witness(lost_masks=(), corrections=False)
        self.assertEqual(decoder_only['entanglement_fidelity'], Exact(F(1, 2)))

    def test_larger_supported_depth_two_codes_have_coherent_decoders(self):
        for branching, lost in (([3, 2], 1), ([3, 3], 3), ([4, 3], 7)):
            w = refresh_witness(branching, (lost,))
            self.assertEqual(w['entanglement_fidelity'], ONE)

    def test_decoder_never_reuses_a_lost_wire(self):
        for lost in (1, 2, 4, 8, 16, 32, 5):
            p = refresh_circuit(lost_masks=(lost,))
            dead = set()
            for op in p['circuit'].operations:
                self.assertFalse(dead.intersection(op.qargs))
                if op.kind == 'reset' and op.qargs[0] < 6 and (lost >> op.qargs[0]) & 1:
                    dead.add(op.qargs[0])
            self.assertEqual(len(dead), lost.bit_count())

    def test_uncorrectable_patterns_and_invalid_schedules_fail_closed(self):
        for lost in (3, 13, 63):
            self.assertFalse(recovery_plan([2, 2], lost)['recoverable'])
            with self.assertRaises(ValueError):
                refresh_circuit(lost_masks=(lost,))
        for lost in (-1, 64, True):
            with self.assertRaises((ValueError, TypeError)):
                recovery_plan([2, 2], lost)
        with self.assertRaises(ResourceLimit):
            refresh_circuit(lost_masks=(0,)*5)
        with self.assertRaises(ValueError):
            refresh_circuit(branching=[3], lost_masks=())

    def test_correct_guarantee_for_three_losses_in_twelve_photons(self):
        p = loss_polynomials([3, 3])
        self.assertEqual(p['counts']['both'][:3], [comb(12, j) for j in range(3)])
        self.assertEqual(p['counts']['both'][3], 156)
        self.assertLess(156, comb(12, 3))


class RefreshBudgetTests(unittest.TestCase):
    def budget(self, intervals=(1,), **kw):
        args = dict(latency_rounds=0, transfer_success=1, resource_ready=1, bell_pairs_per_attempt=10)
        args.update(kw)
        return refresh_budget([2, 2], '99/100', intervals, **args)

    def test_no_latency_perfect_refresh_recovers_reference_product(self):
        b = self.budget((1,)*50)
        w = memory_lifetime([2, 2], '99/100', 50)
        self.assertEqual(b['p_complete'], w['p_ideal_refresh_every_round'])
        self.assertEqual(b['p_no_refresh_same_elapsed_time'], w['p_no_refresh'])

    def test_one_cycle_counts_storage_latency_supply_and_transfer(self):
        b = self.budget((3,), latency_rounds=2, transfer_success=F(3, 4), resource_ready=F(4, 5))
        self.assertEqual(b['elapsed_rounds'], 5)
        self.assertEqual(b['p_complete'], memory_lifetime([2, 2], '99/100', 5)['p_no_refresh']*F(3, 5))
        self.assertEqual(b['expected_bell_pairs_per_input_trial'], 10)

    def test_early_abort_charges_only_reached_refresh_attempts(self):
        b = self.budget((1, 1), transfer_success=F(1, 2))
        first = b['cycles'][0]['p_cycle']
        self.assertEqual(b['expected_refresh_attempts'], 1+first)
        self.assertEqual(b['expected_bell_pairs_per_input_trial'], 10*(1+first))
        self.assertEqual(b['bell_pairs_on_all_success_path'], 20)

    def test_bad_supply_or_transfer_can_remove_the_gain(self):
        b = self.budget((1,)*10, transfer_success=F(1, 2))
        self.assertFalse(b['improves_survival'])
        for kw in ({'resource_ready': 0}, {'transfer_success': 0}):
            b = self.budget((1, 1), **kw)
            self.assertEqual(b['p_complete'], 0)
            self.assertEqual(b['expected_refresh_attempts'], 1)

    def test_budget_limits_and_resource_accounting_are_explicit(self):
        for kw in ({'latency_rounds': True}, {'transfer_success': '2'}, {'resource_ready': '-1'},
                   {'bell_pairs_per_attempt': -1}, {'bell_pairs_per_attempt': True}):
            with self.assertRaises((ValueError, TypeError)):
                self.budget(**kw)
        for intervals in ((), (0,), (257,)):
            with self.assertRaises(ResourceLimit):
                self.budget(intervals)
        b = self.budget()
        self.assertFalse(b['physical_refresh_implemented'])
        self.assertFalse(b['initial_encoding_cost_included'])

    def test_legacy_walk_no_longer_presents_a_device_bound(self):
        w = encoded_walk(4, [2, 2], '99/100')
        self.assertFalse(w['physical_lower_bound'])
        self.assertTrue(w['ideal_refresh_every_round'])


class EvidenceValidationTests(unittest.TestCase):
    def test_impossible_recovery_probabilities_and_tolerances_rejected(self):
        s = dict(evidence_class='LAB_RECORDED', branching=[2, 2], stabiliser_witnesses=5)
        r = dict(evidence_class='LAB_RECORDED', epsilon='1/10', p_x='1', p_z='1', removed_photon=True)
        for field, value in (('p_x', '2'), ('p_z', '-1'), ('p_x', True), ('p_z', .9),
                             ('tolerance', '1'), ('tolerance', '-1/10'), ('epsilon', '0'), ('epsilon', '1')):
            with self.assertRaises((ValueError, TypeError), msg=(field, value)):
                code_grade(dict(encoded_site=s, recovery=dict(r, **{field: value})))
        for count in (-1, 0, True, '5'):
            self.assertEqual(code_grade(dict(encoded_site=dict(s, stabiliser_witnesses=count), recovery=r))['grade'],
                             'CODE_DECLARED')

    def test_build_grade_rejects_bad_witnesses_survival_and_tolerance(self):
        block = dict(evidence_class='LAB_RECORDED', size=4, ghz_witness='9/10', rule='exactly one click per site')
        att = dict(evidence_class='LAB_RECORDED', heralded=True, stabiliser_witness='9/10',
                   success_rate='1/2', storage_survival='2/5', declared_survival='2/5')
        for field, value in (('stabiliser_witness', '2'), ('storage_survival', '2'),
                             ('declared_survival', '-1'), ('tolerance', '1')):
            with self.assertRaises(ValueError):
                build_grade(dict(block=block, attachment=dict(att, **{field: value})))
        self.assertEqual(build_grade(dict(block=dict(block, ghz_witness='0'), attachment=att))['grade'], 'BUILD_DECLARED')
        self.assertEqual(build_grade(dict(block=block, attachment=dict(att, declared_survival='0')))['grade'], 'ATTACHMENT_RECORDED')


if __name__ == '__main__':
    unittest.main()
