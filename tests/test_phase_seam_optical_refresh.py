"""Cross-check optical lowering, coherent transfer and unconditional costs.

The boson instrument, compact-state graph amplitudes and dynamic-reference
channel are separate checks. All probabilities include rejected events;
fidelity is explicitly conditional on the Bell herald and stated resources.
"""
from fractions import Fraction as Q
from itertools import product
import unittest

from native_relational_qc.compact import CompactState
from native_relational_qc.exact import Exact, ONE as EONE
from phase_seam_foundation.dual_rail import (
    F, ZERO, ONE, fock_amplitude, ghz_merge, _patterns,
)
from phase_seam_foundation.loss_refresh import memory_lifetime, recovery_plan
from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.optical_refresh import (
    bell_analyser_certificate, decoder_plan, encoded_bell_factory_certificate,
    fusion_merge_certificate, optical_budget, optical_reference, optical_witness,
    physical_plan, _graph_state,
)


class MeasurementDecoderTests(unittest.TestCase):
    def test_fixed_policy_needs_four_photons_and_only_single_photon_controls(self):
        d = decoder_plan()
        self.assertEqual(d['required_photons'], [0, 1, 2, 3])
        self.assertEqual(d['measurements'], 3)
        self.assertEqual(d['discarded_photons'], [4, 5])
        self.assertEqual(d['online_two_qubit_unitaries'], 0)
        self.assertEqual({o['kind'] for o in d['operations']}, {'measure_z', 'z_parity', 'h'})
        self.assertEqual(d['policy'], 'FIXED_NO_ERASURE_ORACLE')

    def test_every_correctable_erasure_preserves_an_external_reference(self):
        passed = []
        for lost in range(64):
            if recovery_plan([2, 2], lost)['recoverable']:
                d = decoder_plan(known_lost_mask=lost)
                self.assertEqual(d['required_mask'] & lost, 0)
                w = optical_witness(lost_masks=(lost,))
                self.assertEqual(w['herald_probability'], Exact(Q(1, 2)), lost)
                self.assertEqual(w['conditional_entanglement_fidelity'], EONE, lost)
                self.assertEqual(w['joint_bell_projector'], Exact(Q(1, 2)))
                self.assertFalse(w['decoder_outcomes_postselected'])
                self.assertTrue(w['known_erasure_map_required'])
                passed.append(lost)
        self.assertEqual(len(passed), 13)

    def test_fixed_no_oracle_policy_accepts_exactly_four_erasure_patterns(self):
        required = decoder_plan()['required_mask']
        accepted = [lost for lost in range(64) if not lost & required]
        self.assertEqual(accepted, [0, 16, 32, 48])
        for lost in accepted:
            w = optical_witness(lost_masks=(lost,), known_erasures=False)
            self.assertEqual(w['conditional_entanglement_fidelity'], EONE)
            self.assertFalse(w['known_erasure_map_required'])
        for lost in (1, 2, 4, 8):
            with self.assertRaises(ValueError):
                optical_reference(lost_masks=(lost,), known_erasures=False)

    def test_two_transfers_keep_coherence_but_not_unit_success(self):
        w = optical_witness(lost_masks=(1, 16))
        self.assertEqual(w['conditional_entanglement_fidelity'], EONE)
        self.assertEqual(w['herald_probability'], Exact(Q(1, 4)))
        self.assertEqual(w['rejected_probability'], Exact(Q(3, 4)))

    def test_no_feedback_control_destroys_entanglement(self):
        w = optical_witness(lost_masks=(1,), corrections=False)
        self.assertEqual(w['herald_probability'], Exact(Q(1, 2)))
        self.assertEqual(w['conditional_entanglement_fidelity'], Exact(Q(1, 4)))

    def test_other_depth_two_shapes_have_the_same_optical_transfer(self):
        for br, lost in (([3, 2], 1), ([4, 3], 7)):
            w = optical_witness(br, (lost,))
            self.assertEqual(w['herald_probability'], Exact(Q(1, 2)))
            self.assertEqual(w['conditional_entanglement_fidelity'], EONE)
            self.assertFalse(physical_plan(br)['supplied_resource']['factory_certified_here'])

    def test_decoder_never_operates_on_a_lost_photon(self):
        p = optical_reference(lost_masks=(1,))
        dead = set()
        for op in p['circuit'].operations:
            self.assertFalse(dead.intersection(op.qargs))
            if op.kind == 'reset':
                dead.update(op.qargs)
        self.assertEqual(dead, {0})
        # The only online two-qubit unitary in this *verification adapter*
        # represents the certified optical Bell instrument, not a device CNOT.
        online = p['circuit'].operations[p['online_start']:p['fresh_output_boundary']]
        self.assertEqual(sum(op.kind == 'gate' and len(op.qargs) == 2 for op in online), 1)

    def test_generators_are_materialised_once_and_bad_inputs_rejected(self):
        w = optical_witness(iter([2, 2]), iter([0]))
        self.assertEqual((w['branching'], w['lost_masks'], w['transfers']), ([2, 2], [0], 1))
        self.assertEqual(physical_plan(iter([2, 2]))['branching'], [2, 2])
        for mask in (-1, 64, True, 3):
            with self.assertRaises((ValueError, TypeError)):
                decoder_plan(known_lost_mask=mask)
        for group in (-1, 2, True):
            with self.assertRaises((ValueError, TypeError)):
                decoder_plan(fixed_group=group)
        for masks in ((), (0,)*4):
            with self.assertRaises(ResourceLimit):
                optical_reference(lost_masks=masks)
        with self.assertRaises(TypeError):
            optical_reference(known_erasures=1)
        with self.assertRaises(ValueError):
            decoder_plan([3])


class PassiveInstrumentTests(unittest.TestCase):
    def test_all_ten_detector_patterns_form_a_complete_instrument(self):
        b = bell_analyser_certificate()
        self.assertEqual(len(b['outcomes']), 10)
        total = [[ZERO]*2 for _ in range(2)]
        accepted = [[ZERO]*2 for _ in range(2)]
        for outcome in b['outcomes']:
            k = outcome['kraus']
            for i, j in product(range(2), repeat=2):
                gram = sum((k[r][i].conjugate()*k[r][j] for r in range(2)), ZERO)
                total[i][j] += gram
                if outcome['accepted']:
                    accepted[i][j] += gram
        self.assertEqual(total, [[ONE, ZERO], [ZERO, ONE]])
        self.assertEqual(accepted, [[ONE/2, ZERO], [ZERO, ONE/2]])

    def test_four_heralds_are_corrected_identity_each_with_one_eighth_probability(self):
        b = bell_analyser_certificate()
        good = [r for r in b['outcomes'] if r['accepted']]
        self.assertEqual(len(good), 4)
        self.assertEqual({r['bell_label'] for r in good}, {'psi_plus', 'psi_minus'})
        for r in good:
            k = r['kraus']
            x_then_z = ((k[1][0], k[1][1]),
                        tuple((-1 if r['z_correction'] else 1)*v for v in k[0]))
            s = x_then_z[0][0]
            self.assertEqual(x_then_z, ((s, ZERO), (ZERO, s)))
            self.assertEqual(s.norm2(), ONE/8)
        self.assertEqual(b['success_probability'], Q(1, 2))

    def test_missing_bell_input_cannot_fake_two_photon_success_in_pure_loss_model(self):
        b = bell_analyser_certificate()
        for photons in (0, 1):
            for inp in _patterns(4, photons):
                for r in b['outcomes']:
                    if r['accepted']:
                        self.assertEqual(fock_amplitude(b['mode_unitary'], inp, r['outcome']), ZERO)

    def test_single_photon_mode_matrix_is_unitary(self):
        u = bell_analyser_certificate()['mode_unitary']
        for i, j in product(range(4), repeat=2):
            self.assertEqual(sum((u[k][i].conjugate()*u[k][j] for k in range(4)), ZERO),
                             ONE if i == j else ZERO)

    def test_local_fusion_kraus_maps_equal_even_parity_merge(self):
        merges = fusion_merge_certificate()
        self.assertEqual({m['click'] for m in merges}, {1, 2})
        for m in merges:
            a = m['scalar']
            self.assertEqual(a.norm2(), ONE/2)
            self.assertEqual(m['corrected_kraus'], ((a, ZERO, ZERO, ZERO), (ZERO, ZERO, ZERO, a)))
            self.assertIn(m['correction_phase_steps'], (16, 48))


class ResourceFactoryTests(unittest.TestCase):
    def test_all_four_factory_branches_produce_target_graph_with_probabilities(self):
        f = encoded_bell_factory_certificate()
        self.assertEqual(len(f['branches']), 4)
        for b in f['branches']:
            self.assertTrue(b['target_graph_matches'])
            self.assertEqual(b['first_click_probability'], ONE/4)
            self.assertEqual(b['probability'], ONE/16)
        self.assertEqual(sum((b['probability'] for b in f['branches']), ZERO), ONE/4)
        self.assertEqual(f['photons_supplied'], f['photons_detected']+f['photons_delivered'])
        self.assertEqual(f['success_probability'] + f['rejected_at_first_attachment_probability']
                         + f['rejected_at_second_attachment_probability'], 1)
        self.assertTrue(f['fresh_port_is_unmeasured'])

    def test_factory_graph_equals_the_independently_encoded_bell_state(self):
        # Separate native compact representation and a directly written code
        # encoder; do not obtain the target amplitudes from the factory merge.
        state = CompactState(7).apply('h', 0).apply('cx', 0, 1).apply('cx', 1, 2)
        for centre, leaves in ((1, (3, 4)), (2, (5, 6))):
            state.apply('h', centre)
            for leaf in leaves:
                state.apply('cx', centre, leaf).apply('h', leaf)
        graph = _graph_state(tuple(range(7)), ((0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)))
        for bits, expected in graph.items():
            self.assertEqual(F(state.amplitude(bits)), expected, bits)

    def test_source_star_and_full_restart_cost_include_failed_candidates(self):
        source = ghz_merge()
        self.assertEqual(source['success_probability'], ONE/2)
        self.assertTrue(all(b['support_is_ghz'] and b['equal_weights'] and b['corrected_xxx'] == ONE
                            for b in source['clicks'].values()))
        f = encoded_bell_factory_certificate()
        pairs_per_star = Q(2)/Q(1, 2)
        pairs_per_attempt = 3*pairs_per_star  # all three stars prepared first
        self.assertEqual(f['expected_bell_pairs_per_factory_attempt'], pairs_per_attempt)
        self.assertEqual(f['expected_bell_pairs_per_delivered_resource'], pairs_per_attempt/Q(1, 4))
        self.assertEqual(f['expected_source_photons_per_delivered_resource'], 96)
        # Second attachment is attempted only if the first succeeded.
        self.assertEqual(f['expected_attachment_rounds_per_attempt'], 1+Q(1, 2))
        self.assertEqual(f['expected_attachment_rounds_per_delivered_resource'], (1+Q(1, 2))/Q(1, 4))
        self.assertFalse(f['star_preparation_time_included'])
        self.assertFalse(f['storage_loss_included'])


class OpticalBudgetTests(unittest.TestCase):
    def budget(self, **kw):
        values = dict(memory=1, storage_rounds=0, decoder_efficiency=1, bell_efficiency=1,
                      resource_ready=1, pre_bell_rounds=0, post_bell_rounds=0)
        values.update(kw)
        return optical_budget(**values)

    def test_lossless_instrument_succeeds_only_half_the_time(self):
        b = self.budget()
        self.assertEqual(b['herald_probability'], Q(1, 2))
        self.assertEqual(b['herald_and_intact_output_probability'], Q(1, 2))
        self.assertEqual(b['total_required_detections'], 5)

    def test_fixed_policy_survival_equals_explicit_loss_distribution(self):
        s = Q(3, 4)**3
        required = decoder_plan()['required_mask']
        by_masks = sum((s**(6-mask.bit_count())*(1-s)**mask.bit_count()
                        for mask in range(64) if not mask & required), Q())
        b = self.budget(memory=Q(3, 4), storage_rounds=3)
        self.assertEqual(by_masks, s**4)
        self.assertEqual(b['input_usable_probability'], by_masks)
        self.assertEqual(b['herald_probability'], by_masks/2)

    def test_known_erasure_oracle_is_a_distinct_stronger_assumption(self):
        fixed = self.budget(memory=Q(99, 100), storage_rounds=10)
        oracle = self.budget(memory=Q(99, 100), storage_rounds=10, known_erasures=True)
        self.assertGreater(oracle['input_usable_probability'], fixed['input_usable_probability'])
        self.assertEqual(oracle['input_usable_probability'], memory_lifetime([2, 2], '99/100', 10)['p_no_refresh'])
        self.assertEqual(oracle['policy'], 'KNOWN_ERASURE_ORACLE')

    def test_supply_and_each_required_detection_are_charged(self):
        b = self.budget(resource_ready=Q(4, 5), decoder_efficiency=Q(9, 10), bell_efficiency=Q(7, 8))
        self.assertEqual(b['herald_probability'], Q(1, 2)*Q(4, 5)*Q(9, 10)**3*Q(7, 8)**2)
        for kw in ({'resource_ready': 0}, {'decoder_efficiency': 0}, {'bell_efficiency': 0}):
            self.assertEqual(self.budget(**kw)['herald_probability'], 0)

    def test_payload_loss_is_not_certified_by_consumed_photon_herald(self):
        m = Q(99, 100)
        b = self.budget(memory=m, storage_rounds=3, pre_bell_rounds=1, post_bell_rounds=1)
        self.assertEqual(b['herald_probability'], m**12*m**2/2)
        self.assertEqual(b['fresh_payload_survival'], m**12)
        self.assertEqual(b['herald_and_intact_output_probability'], m**26/2)
        self.assertTrue(b['payload_loss_can_be_unheralded'])
        self.assertTrue(b['conditional_fidelity_with_payload_loss_not_claimed'])
        self.assertFalse(b['resource_factory_time_included'])

    def test_zero_memory_only_counts_actual_waits(self):
        self.assertEqual(self.budget(memory=0)['herald_probability'], Q(1, 2))
        self.assertEqual(self.budget(memory=0, storage_rounds=1)['herald_probability'], 0)
        delayed = self.budget(memory=0, post_bell_rounds=1)
        self.assertEqual(delayed['herald_probability'], Q(1, 2))
        self.assertEqual(delayed['herald_and_intact_output_probability'], 0)

    def test_nonphysical_probabilities_types_and_rounds_are_rejected(self):
        for field in ('memory', 'decoder_efficiency', 'bell_efficiency', 'resource_ready'):
            for bad in (True, .9, '2', '-1/10'):
                with self.assertRaises((ValueError, TypeError)):
                    self.budget(**{field: bad})
        for field in ('storage_rounds', 'pre_bell_rounds', 'post_bell_rounds'):
            for bad in (True, -1, 257):
                with self.assertRaises((TypeError, ResourceLimit)):
                    self.budget(**{field: bad})
        with self.assertRaises(ResourceLimit):
            self.budget(storage_rounds=256, pre_bell_rounds=1)
        with self.assertRaises(TypeError):
            self.budget(known_erasures=1)

    def test_physical_netlist_conserves_present_photons_and_lists_herald_corrections(self):
        for lost in (None, 1, 48):
            p = physical_plan(known_lost_mask=lost)
            photons = p['photons']
            self.assertEqual(photons['input_total'], photons['detected_on_success']+photons['discarded_old']+photons['fresh_output'])
            self.assertEqual(photons['maximum_input'], 13)
            self.assertEqual(photons['prior_losses'], 0 if lost is None else lost.bit_count())
            self.assertEqual(p['detector_mode_channels'], 10)
            self.assertEqual(p['online_deterministic_two_photon_gates'], 0)
            bell = p['online_operations'][1]
            self.assertEqual(len(bell['accepted_patterns_and_corrections']), 4)
            self.assertTrue(bell['number_resolved_detection'])
            self.assertFalse(p['physical_temperatures_measured'])


if __name__ == '__main__':
    unittest.main()
