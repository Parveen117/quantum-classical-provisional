"""Exact channel, detector-record and cost checks for encoded optical transfer."""
from fractions import Fraction as Q
from itertools import product
import unittest

from native_relational_qc.compact import CompactCircuit
from native_relational_qc.exact import Exact, ONE as EONE, ZERO as EZERO
from phase_seam_foundation.dual_rail import H2, ONE, ZERO, ZETA
from phase_seam_foundation.loss_refresh import _encode, recovery_plan
from phase_seam_foundation.loss_tolerant_code import code, _rank
from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.photonic_response import unit_jet
from phase_seam_foundation.encoded_bell import (
    basis_bridge_certificate, budget, coarse_instrument_certificate, decode_counts,
    loss_coefficients, mask_success, measurement_handoff, physical_plan, resource_factory_certificate,
    resource_stabiliser_witness, success_probability, transfer_witness, _reference,
)


def observed_counts(zz, xx=0):
    records = coarse_instrument_certificate()['records']
    return next(tuple(r['counts']) for r in records
                if r['possible'] and r['zz'] == zz and (not zz or r['xx'] == xx))


class ComponentTests(unittest.TestCase):
    def test_classifier_heater_interface_is_lifted_to_a_coherent_h(self):
        b = basis_bridge_certificate()
        self.assertEqual(b['measurement_heaters']['after'], 48)
        self.assertEqual(b['coherent_heaters'], dict(lower=16, upper=0, before=32, after=32))
        h = ((H2, H2), (H2, -H2))
        for i, j in product(range(2), repeat=2):
            self.assertEqual(b['unitary'][i][j], b['global_phase']*h[i][j])
        raw, _ = unit_jet(tuple(b['measurement_heaters'][k] for k in ('lower','upper','before','after')))
        self.assertNotEqual(raw[1][0]/h[1][0], raw[0][0]/h[0][0])
        self.assertEqual(b['relative_output_phase_removed'], 16)
        self.assertFalse(b['calibrated_voltage_or_temperature_claim'])

    def test_three_coarse_effects_are_complete_and_even_phase_is_unresolved(self):
        c = coarse_instrument_certificate()
        for i, j in product(range(4), repeat=2):
            self.assertEqual(sum((e[i][j] for e in c['effects'].values()), ZERO), ONE if i == j else ZERO)
        self.assertFalse(c['even_phase_resolved'])
        self.assertEqual(c['effects']['even'], [[ONE if i == j and i in (0,3) else ZERO
                                                for j in range(4)] for i in range(4)])
        self.assertEqual(sum(r['possible'] for r in c['records']), 8)
        self.assertTrue(all(r['xx'] is None for r in c['records'] if r['group']=='even'))

    def test_component_ledger_prices_the_two_encoded_arms(self):
        p = physical_plan()
        self.assertEqual(p['input']['total_photons'], 18)
        self.assertEqual(p['output']['fresh_data_photons']+p['output']['consumed_measured_photons_if_lossless'], 18)
        self.assertEqual((p['transversal_analysers'], p['bell_couplers'], p['detector_mode_channels']), (6,12,24))
        self.assertEqual(p['graph_to_parity']['units'], 8)
        self.assertEqual(p['total_couplers_excluding_factory_and_pauli_routing'], 28)
        self.assertFalse(p['nondestructive_erasure_oracle'])
        self.assertFalse(p['quantum_adaptive_measurement_bases'])
        self.assertTrue(p['fully_encoded_factory_certified_here'])
        self.assertFalse(physical_plan((8,1))['fully_encoded_factory_certified_here'])


class DetectorDecoderTests(unittest.TestCase):
    def test_all_native_bell_support_and_all_64_pair_erasure_masks(self):
        # Independent native compact amplitudes for all FOUR logical Bell
        # states. Infer no logical parities from the decoder under test.
        # Refining the even phase is permitted only in this reference; the
        # corresponding bit is removed before passing optical count records.
        br=(2,2); cc=code(br); n=6
        totals=[EZERO]*64
        for a, b in product((0,1), repeat=2):
            circuit=CompactCircuit(2*n).add('h',0).add('cx',0,n)
            _encode(circuit,br,0); _encode(circuit,br,n)
            for bit, name in ((a,'x_logical'),(b,'z_logical')):
                if bit:
                    x,z=cc[name]
                    for q in range(n):
                        if x>>q&1: circuit.add('x',n+q)
                        if z>>q&1: circuit.add('z',n+q)
            for q in range(n):
                if q>=2: circuit.add('h',q).add('h',n+q)
                circuit.add('cx',q,n+q).add('h',q)
            state=circuit.state()
            support=0
            for bits in range(1<<(2*n)):
                p=state.amplitude(bits).norm2()
                if not p: continue
                support+=1
                self.assertEqual(p,Exact(Q(1,32)))
                records=[observed_counts((bits>>(n+q))&1,(bits>>q)&1) for q in range(n)]
                for lost in range(64):
                    seen=[((1,0,0,0) if q%2 else (0,0,0,0)) if lost>>q&1 else records[q]
                          for q in range(n)]
                    d=decode_counts(br,seen)
                    if d['accepted']:
                        self.assertEqual((d['x_correction'],d['z_correction']),(a,b),(a,b,lost,bits))
                        self.assertEqual(d['pair_lost_mask'],lost)
                        self.assertFalse(d['requires_external_erasure_map'])
                        totals[lost]+=p/Exact(4)
            self.assertEqual(support,32)
        for lost,p in enumerate(totals):
            self.assertEqual(p,Exact(mask_success(br,lost)['success_probability']),lost)
        self.assertEqual(totals[0],Exact(Q(3,4)))

    def test_no_complete_odd_group_or_empty_group_rejects(self):
        self.assertEqual(decode_counts((2,2),[observed_counts(0)]*6)['reason'],'NO_COMPLETE_ODD_GROUP')
        counts=[observed_counts(1)]*6
        for q in (0,2,3): counts[q]=(0,0,0,0)
        self.assertEqual(decode_counts((2,2),counts)['reason'],'GROUP_WITH_NO_COMPLETE_PAIR')

    def test_non_loss_faults_do_not_masquerade_as_passing_records(self):
        counts=[observed_counts(1)]*6
        counts[2]=observed_counts(0)
        self.assertEqual(decode_counts((2,2),counts)['reason'],'INCONSISTENT_GROUP_PARITY')
        counts=[observed_counts(1)]*6; counts[0]=(3,0,0,0)
        self.assertEqual(decode_counts((2,2),counts)['reason'],'EXCESS_PHOTONS')
        counts[0]=(1,0,1,0)
        self.assertEqual(decode_counts((2,2),counts)['reason'],'IMPOSSIBLE_IDEAL_TWO_PHOTON_PATTERN')
        counts=[observed_counts(1)]*6; counts[0]=observed_counts(1,1)
        self.assertEqual(decode_counts((2,2),counts)['reason'],'INCONSISTENT_LOGICAL_PHASE')

    def test_record_validation_and_iterators(self):
        self.assertTrue(decode_counts(iter([2,2]),iter([observed_counts(1)]*6))['accepted'])
        for counts in ([observed_counts(1)]*5, [(True,0,0,0)]*6, [(-1,0,0,0)]*6, [(1,0,0)]*6):
            with self.assertRaises(ValueError): decode_counts((2,2),counts)


class CollaboratorHandoffTests(unittest.TestCase):
    def frame(self, a, b):
        # Both odd groups for b=0; group 1 alone odd for b=1. Their phase
        # parities equal a, as required by the native logical Bell states.
        counts=[observed_counts(0)]*6
        for group in (((0,2,3),(1,4,5)) if not b else ((1,4,5),)):
            for i,q in enumerate(group): counts[q]=observed_counts(1,a if not i else 0)
        return decode_counts((2,2),counts)

    def test_record_frames_expand_to_the_native_physical_paulis(self):
        for a,b in product((0,1),repeat=2):
            d=self.frame(a,b)
            self.assertEqual((d['x_correction'],d['z_correction']),(a,b))
            hand=measurement_handoff((2,2),d,(5,17,22,9,50,14))
            self.assertEqual(hand['physical_x_mask'],b)
            self.assertEqual(hand['physical_z_mask'],(3 if a else 0)^(12 if b else 0))
            self.assertEqual(hand['active_pauli_gates_before_these_measurements'],0)
            self.assertFalse(hand['encoded_logical_classifier_compiled'])

    def test_adapted_projectors_equal_active_correction_for_every_exported_row(self):
        for a,b in product((0,1),repeat=2):
            hand=measurement_handoff((2,2),self.frame(a,b),(5,17,22,9,50,14))
            for row in hand['rows']:
                x,z=row['physical_frame']; angle=row['nominal_angle']
                for s in (0,1):
                    # Construct the nominal bra's ket and apply physical Z,
                    # then X. Compare projectors, eliminating global phases.
                    v=[H2,(-1 if s else 1)*H2*ZETA**angle]
                    if z: v[1]=-v[1]
                    if x: v.reverse()
                    w=[H2,(-1 if s^row['outcome_xor'] else 1)*H2*ZETA**row['adapted_angle']]
                    for i,j in product(range(2),repeat=2):
                        self.assertEqual(v[i]*v[j].conjugate(),w[i]*w[j].conjugate())

    def test_exported_heaters_route_the_adapted_basis_to_the_expected_rails(self):
        hand=measurement_handoff((2,2),self.frame(1,1),(5,17,22,9,50,14))
        for row in hand['rows']:
            h=row['heaters']; u,_=unit_jet(tuple(h[k] for k in ('lower','upper','before','after')))
            for s in (0,1):
                v=(H2,(-1 if s else 1)*H2*ZETA**row['adapted_angle'])
                out=tuple(sum((u[i][j]*v[j] for j in range(2)),ZERO) for i in range(2))
                self.assertEqual(out[1-s],ZERO)
                self.assertEqual(out[s].norm2(),ONE)

    def test_handoff_requires_matching_accepted_frame_and_valid_angles(self):
        d=self.frame(1,1); angles=(5,17,22,9,50,14)
        for bad in (dict(d,accepted=False),dict(d,branching=[3,2]),dict(d,x_correction=True)):
            with self.assertRaises(ValueError): measurement_handoff((2,2),bad,angles)
        for bad in (angles[:-1],(64,)*6,(True,)*6):
            with self.assertRaises(ValueError): measurement_handoff((2,2),d,bad)


class ChannelTests(unittest.TestCase):
    def test_every_recoverable_six_photon_mask_has_identity_conditional_channel(self):
        checked=0
        for lost in range(64):
            w=transfer_witness(pair_lost_mask=lost)
            self.assertEqual(w['success_probability'],Exact(mask_success((2,2),lost)['success_probability']))
            if recovery_plan((2,2),lost)['recoverable']:
                self.assertEqual(w['conditional_entanglement_fidelity'],EONE,lost)
                self.assertEqual(w['success_probability'],Exact(Q(3,4) if not lost else Q(1,2)))
                checked+=1
            else:
                self.assertEqual(w['success_probability'],EZERO)
                self.assertIsNone(w['conditional_entanglement_fidelity'])
        self.assertEqual(checked,13)

    def test_first_odd_group_events_are_disjoint_and_all_are_counted(self):
        w=transfer_witness((3,2))
        self.assertEqual([r['probability'] for r in w['disjoint_first_odd_group_events']],
                         [Exact(Q(1,2)),Exact(Q(1,4)),Exact(Q(1,8))])
        self.assertEqual(w['success_probability'],Exact(Q(7,8)))
        self.assertEqual(w['conditional_entanglement_fidelity'],EONE)
        self.assertFalse(w['even_pair_phases_used'])

    def test_larger_shapes_keep_the_reference_and_expose_supply_assumption(self):
        for br,p in (((4,3),Q(15,16)),((8,1),Q(255,256))):
            w=transfer_witness(br)
            self.assertEqual(w['success_probability'],Exact(p))
            self.assertEqual(w['conditional_entanglement_fidelity'],EONE)
            self.assertFalse(physical_plan(br)['fully_encoded_factory_certified_here'])

    def test_feedback_negative_control_is_not_high_fidelity_postselection(self):
        w=transfer_witness(corrections=False)
        self.assertEqual(w['success_probability'],Exact(Q(3,4)))
        self.assertEqual(w['conditional_entanglement_fidelity'],Exact(Q(1,6)))

    def test_traced_pair_wires_are_never_reused(self):
        r=_reference((2,2),1,1,True)
        dead=set()
        for op in r['circuit'].operations:
            self.assertFalse(dead.intersection(op.qargs))
            if op.kind=='reset': dead.update(op.qargs)
        self.assertEqual(dead,{0,6})

    def test_mask_shape_and_policy_limits(self):
        for mask in (-1,64,True):
            with self.assertRaises((ValueError,TypeError)): transfer_witness(pair_lost_mask=mask)
        with self.assertRaises(ResourceLimit): transfer_witness((9,1))
        with self.assertRaises(ValueError): transfer_witness((3,))
        with self.assertRaises(TypeError): transfer_witness(corrections=1)
        self.assertEqual(transfer_witness(iter([2,2]))['success_probability'],Exact(Q(3,4)))


class FactoryTests(unittest.TestCase):
    def test_port_swap_prepares_encoded_phi_plus_on_every_accepted_pattern(self):
        f=resource_factory_certificate()
        self.assertEqual(len(f['branches']),4)
        for b in f['branches']:
            self.assertTrue(b['target_encoded_phi_plus'])
            self.assertEqual(b['probability'],ONE/8)
        self.assertEqual(f['swap_success_probability'],Q(1,2))
        self.assertEqual(f['input_photons'],f['measured_port_photons']+f['output_photons'])

    def test_resource_has_all_twelve_independent_target_stabilisers(self):
        w=resource_stabiliser_witness()
        self.assertEqual(w['success_probability'],Exact(Q(1,2)))
        self.assertEqual(w['target_expectations'],[EONE]*12)
        cc=code((2,2)); n=6
        gs=list(cc['stabilisers'])+[(x<<n,z<<n) for x,z in cc['stabilisers']]
        gs += [(x|(x<<n),z|(z<<n)) for x,z in (cc['x_logical'],cc['z_logical'])]
        self.assertEqual(_rank(gs),12)
        self.assertFalse(resource_stabiliser_witness(corrections=False)['all_target_stabilisers_plus_one'])

    def test_complete_restart_cost_includes_unsuccessful_port_swaps(self):
        f=resource_factory_certificate()
        self.assertEqual(f['expected_bell_pairs_per_swap_attempt'],2*48)
        self.assertEqual(f['expected_bell_pairs_per_delivered_resource'],2*48/Q(1,2))
        self.assertEqual(f['expected_source_photons_per_delivered_resource'],384)
        self.assertFalse(f['storage_switch_source_noise_included'])
        self.assertFalse(f['preparation_latency_included'])


class LossBudgetTests(unittest.TestCase):
    def b(self,**kw):
        values=dict(memory=1,storage_rounds=0,detector_efficiency=1,resource_ready=1,
                    pre_bell_rounds=0,post_bell_rounds=0)
        values.update(kw); return budget(**values)

    def test_closed_form_matches_independent_weighted_mask_enumeration(self):
        for br in ((1,1),(2,2),(3,2),(4,3),(8,1)):
            c=loss_coefficients(br); n=c['photons']
            for eta in (Q(0),Q(1,2),Q(81,100),Q(99,100),Q(1)):
                enumerated=sum((Q(v,c['denominator'])*eta**(n-k)*(1-eta)**k
                                for k,v in enumerate(c['weighted_numerators'])),Q())
                self.assertEqual(success_probability(br,eta),enumerated,(br,eta))
        self.assertEqual(loss_coefficients([2,2])['weighted_numerators'],[3,12,12,0,0,0,0])

    def test_lossless_law_and_complete_loss(self):
        for b,c in ((1,1),(2,2),(3,2),(4,3),(8,1)):
            self.assertEqual(success_probability((b,c),1),1-Q(1,2)**b)
            self.assertEqual(success_probability((b,c),0),0)
        self.assertEqual(self.b()['herald_probability'],Q(3,4))

    def test_both_photons_and_both_detectors_enter_pair_survival_once(self):
        m=Q(99,100); d=Q(9,10)
        b=self.b(memory=m,storage_rounds=3,pre_bell_rounds=1,post_bell_rounds=2,
                 detector_efficiency=d,resource_ready=Q(4,5))
        eta=m**5*d**2
        self.assertEqual(b['complete_pair_probability'],eta)
        self.assertEqual(b['herald_probability'],Q(4,5)*success_probability((2,2),eta))
        self.assertEqual(b['fresh_payload_survival'],m**18)
        self.assertEqual(b['herald_and_intact_output_probability'],b['herald_probability']*m**18)
        self.assertTrue(b['payload_loss_can_be_unheralded'])
        self.assertFalse(b['physical_conditional_fidelity_claimed'])

    def test_long_composed_wait_keeps_exact_derived_rationals(self):
        b=self.b(memory='99/100',storage_rounds=100)
        eta=Q(99,100)**100
        self.assertEqual(b['herald_probability'],3*eta**4-3*eta**5+Q(3,4)*eta**6)
        self.assertGreater(b['complete_pair_probability'].denominator.bit_length(),256)

    def test_no_supply_no_detection_and_zero_memory_waits(self):
        for kw in ({'resource_ready':0},{'detector_efficiency':0},{'memory':0,'storage_rounds':1}):
            self.assertEqual(self.b(**kw)['herald_probability'],0)
        delayed=self.b(memory=0,post_bell_rounds=1)
        self.assertEqual(delayed['herald_probability'],Q(3,4))
        self.assertEqual(delayed['herald_and_intact_output_probability'],0)

    def test_resource_probabilities_and_waits_fail_closed(self):
        for name in ('memory','resource_ready','detector_efficiency'):
            for value in (True,.9,'2','-1/10'):
                with self.assertRaises((ValueError,TypeError)): self.b(**{name:value})
        for name in ('storage_rounds','pre_bell_rounds','post_bell_rounds'):
            for value in (True,-1,257):
                with self.assertRaises((TypeError,ResourceLimit)): self.b(**{name:value})
        with self.assertRaises(ResourceLimit): self.b(storage_rounds=256,pre_bell_rounds=1)
        with self.assertRaises(TypeError): success_probability((2,2),.99)


if __name__=='__main__':
    unittest.main()
