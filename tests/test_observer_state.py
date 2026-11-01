"""Physical source validity, moving-frame covariance, and causal joint readout."""
from copy import deepcopy
from fractions import Fraction as Q
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

from benchmarks import observer_state_audit as campaign
from native_relational_qc.calculator import calculate, display
from native_relational_qc.certify import flat_field
from native_relational_qc import observer_state as state
from native_relational_qc import observer_tracking as phase
from native_relational_qc.__main__ import main as cli


class ObserverStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = phase.likelihoods([calculate(phase.calculator_request([k],[0])) for k in range(32)])
        cls.planner = state.Planner(state.Model(rounds=2))
        cls.policy = cls.planner.adaptive()

    def test_channel_is_positive_normalized_and_has_correct_pure_limits(self):
        F = flat_field()
        for retention in (Q(0), Q(3,4), Q(7,8), Q(1)):
            mixtures = state.source_mixtures(3,1,8,retention=retention)
            for t, mixture in enumerate(mixtures):
                self.assertEqual(sum(w for _,w in mixture), 1)
                self.assertTrue(all(w > 0 for _,w in mixture))
                z = state.coherence(mixture)
                radius_squared = float(display(z*z.conjugate())['decimal'])
                self.assertTrue(-1e-12 <= radius_squared <= 1+1e-12)
                if retention == 1:
                    self.assertEqual(z, F.root(2*(3+t)))
                if retention == 0 and t:
                    self.assertEqual(z, F.root(22))
        one_step = state.coherence(state.source_mixtures(0,0,8,rounds=1)[1])
        self.assertEqual(one_step, Q(3,4)+F.imag()*Q(1,4))
        self.assertEqual(one_step*one_step.conjugate(), Q(5,8))

    def test_affine_transport_moves_both_state_and_displacement(self):
        F = flat_field(); i = F.imag()
        self.assertEqual(state.transport(F(1),0,F(1),8), -2*i)
        self.assertNotEqual(state.transport(F(1),0,F(1),8), 1-i)
        self.assertTrue(all(campaign.frame_controls().values()))

    def test_acceleration_has_required_coriolis_euler_and_origin_terms(self):
        F = flat_field(); i = F.imag()
        terms = state.frame_acceleration(F(1),F(1),F(),F(),0,1,0)
        self.assertEqual(terms['total'], 1-2*i)
        self.assertEqual(terms['coriolis'], -2*i)
        self.assertEqual(terms['centrifugal'], 1)
        # At zero angular speed, a(t)=t^2/2, lab z=1: q''(0)=-i.
        self.assertEqual(state.frame_acceleration(F(1),F(),F(),F(),0,0,1)['total'], -i)
        # Nonrotating axes, lab point fixed, origin c(t)=t^2: q''=-2.
        self.assertEqual(state.frame_acceleration(F(1),F(),F(),F(2),0,0,0)['total'], -2)
        # Radial relative velocity zero removes only the Coriolis term.
        self.assertEqual(state.frame_acceleration(F(1),F(),F(),F(),0,1,0)['total'], 1)

    def test_common_frame_change_preserves_mixed_readout_and_prediction_loss(self):
        F = flat_field()
        mixture = state.source_mixtures(3,1,-8,rounds=2)[-1]
        z = state.coherence(mixture)
        for shift in (1,3,8,31):
            shifted = tuple(((a+shift)%32,w) for a,w in mixture)
            rotated = state.coherence(shifted)
            self.assertEqual(rotated, F.root(2*shift)*z)
            for axis in state.AXES:
                before = sum((self.bank[(a-axis)%32]*w for a,w in mixture),F())
                after = sum((self.bank[(a-axis-shift)%32]*w for a,w in shifted),F())
                self.assertEqual(before,after)
            e = z-F.root(6)*Q(1,2)
            es = rotated-F.root(6+2*shift)*Q(1,2)
            self.assertEqual(e*e.conjugate(),es*es.conjugate())

    def test_planning_matches_all_two_probe_contingent_choices_and_exact_risk(self):
        p = self.planner
        risks = []
        for a0,a1 in product(range(4),repeat=2):
            utility = 0.
            for b0,axis in enumerate((a0,a1)):
                weights = p.prior*(p.p0[0,0] if b0 == 0 else 1-p.p0[0,0])
                for b1 in (0,1):
                    weights1 = weights*(p.p0[1,axis] if b1 == 0 else 1-p.p0[1,axis])
                    utility += float((weights1@p.utility).max())
            risks.append((1-utility)/2)
        actual = self.policy['planning']['numerical_expected_loss']
        self.assertAlmostEqual(actual,min(risks),places=12)
        exact = [state.exact_evaluate(self.policy,state.source_mixtures(s,v,o,rounds=2),self.bank)['error']
                 for s,v,o in p.model.hypotheses]
        mean = sum(exact,flat_field()())*Q(1,len(exact))
        self.assertAlmostEqual(float(display(mean)['decimal']),actual,delta=2e-11)
        fixed, searched = p.open_loop_search()
        self.assertEqual(len(searched),4)
        self.assertEqual(self.policy['planning']['leaf_evaluations'],fixed['planning']['leaf_evaluations'])

    def test_legacy_angle_control_changes_decoder_without_changing_actions(self):
        old = phase.Planner(phase.Model(2)).adaptive()
        refit = self.planner.redecode(old)
        legacy = state.legacy_policy(old)
        for bits in map(''.join, product('01',repeat=2)):
            self.assertEqual(phase.branch_axes(old,bits),phase.branch_axes(refit,bits))
            self.assertEqual(phase.branch_axes(old,bits),phase.branch_axes(legacy,bits))
            old_out = phase.read_records(old,bits)
            out = state.read_records(legacy,bits)
            self.assertEqual(out['predicted_radius'],'1')
            self.assertEqual(out['predicted_phase_degrees'],old_out['predicted_phase_degrees'])

    def test_random_bits_are_uniform_and_cannot_beat_prior_mean(self):
        F = flat_field(); accumulated, zero = F(), F()
        no_records = state.no_record_policy(2)
        for start in range(0,32,2):
            mixtures = state.source_mixtures(start,1,8,rounds=2)
            result = state.exact_evaluate(self.policy,mixtures,self.bank,flip=Q(1,2),keep_branches=True)
            self.assertTrue(all(w == Q(1,4) for w in result['branches'].values()))
            accumulated += result['error']
            zero += state.exact_evaluate(no_records,mixtures,self.bank,flip=Q(1,2))['error']
        self.assertGreaterEqual(float(display(accumulated-zero)['decimal']),0.)
        response = state.read_records(no_records,'01')
        self.assertEqual(response['predicted_radius'],'0')
        self.assertIsNone(response['predicted_phase_degrees'])

    def test_records_are_causal_and_cli_returns_both_coordinates(self):
        for bits in ('','0','01'):
            out = state.read_records(self.policy,bits)
            shifted = state.read_records(self.policy,bits,frame_step=3)
            self.assertEqual(out['probes_remaining'],2-len(bits))
            key = 'predicted_phase_degrees' if len(bits)==2 else 'next_axis_degrees'
            if out[key] is not None:
                self.assertEqual((out[key]+33.75)%360,shifted[key])
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp)/'policy.json'; policy.write_text(json.dumps(self.policy))
            result = Path(tmp)/'out.json'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cli(['observer-state','--policy',str(policy),'--records','01','--out',str(result)]),0)
            out = json.loads(result.read_text())
            self.assertEqual(out['status'],'complete')
            self.assertIn('predicted_radius',out)
            self.assertIsNone(out['hardware_job_id'])

    def test_invalid_models_mixtures_records_and_tampering_are_rejected(self):
        for rounds in (0,7,True,2.5):
            with self.assertRaises(ValueError): state.Model(rounds=rounds)
        for retention in (0.75, Q(-1,4), Q(17,16), Q(1,17), True):
            with self.assertRaises(ValueError): state.source_mixtures(0,1,8,retention=retention)
        for records in ('2','001',None):
            with self.assertRaises(ValueError): state.read_records(self.policy,records)
        bad = deepcopy(self.policy); bad['tree']['axis']=31
        with self.assertRaises(ValueError): state.validate_policy(bad)
        with self.assertRaises(ValueError): state.validate_policy(phase.seal({k:v for k,v in bad.items() if k!='fingerprint'}))
        for mixture in (((0,Q(1,2)),), ((0,Q(2)),(1,Q(-1))), ((0,1.0),)):
            with self.assertRaises(ValueError): state.exact_evaluate(self.policy,(mixture,)*3,self.bank)
        for flip in (0.1,True,Q(3,4)):
            with self.assertRaises(ValueError): state.exact_evaluate(self.policy,state.source_mixtures(0,1,8,rounds=2),self.bank,flip=flip)

    def test_protocol_retains_all_stresses_and_enforces_no_overwrite(self):
        self.assertEqual(json.loads(campaign.PROTOCOL_PATH.read_text()),campaign.protocol())
        rows = campaign.evaluation_cases()
        self.assertEqual(len(rows),544)
        self.assertEqual(len({r['id'] for r in rows}),544)
        self.assertEqual({r['retention'] for r in rows},{'3/4','7/8'})
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            out = Path(tmp)/'audit'
            # A timeout must retain the frozen proposals, but never a passing report.
            with patch.object(campaign,'run_calculation',return_value=dict(status='time_limit')):
                with self.assertRaises(RuntimeError): campaign.audit(out,'a'*40)
            self.assertEqual(json.loads((out/'status.json').read_text())['status'],'incomplete')
            self.assertTrue((out/'frozen_policies.json').exists())
            self.assertFalse((out/'summary.json').exists())
            with self.assertRaises(FileExistsError): campaign.audit(out,'a'*40)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional Qiskit reference')
    def test_independent_kraus_reference_checks_joint_losses_and_all_paths(self):
        for flip in ('0','1/20','1/2'):
            row = dict(start=3,velocity=-1,offset=8,retention='3/4',flip=flip)
            result = state.exact_evaluate(self.policy,campaign.preparations(row,rounds=2),self.bank,flip=Q(flip),keep_branches=True)
            reference = campaign.reference(self.policy,row,result)
            self.assertTrue(reference['passed'],reference)
            self.assertEqual(reference['branches_checked'],4)


if __name__ == '__main__':
    unittest.main()
