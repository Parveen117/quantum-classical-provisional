"""Full payload composition: exact Fock references and hidden-postselection controls."""
from collections import defaultdict
from fractions import Fraction as Q
from functools import lru_cache
from itertools import product
from math import factorial, comb
import unittest

from phase_seam_foundation.dual_rail import (
    F,ZERO,ONE,H2,SQRT2,ZETA,COUPLER,embed,_scaled_amplitude,
)
from phase_seam_foundation.optical_refresh import fusion_merge_certificate
from phase_seam_foundation.source_distillation import (
    _r,_round_trajectories,optical_round,purification_schedule,double_pair_channel,
)
from phase_seam_foundation.purification_cascade import (
    QUBIT,VACUUM,_gram,_trace,_initial,_loss,_hadamards,_h_polynomial,
    _merge_coefficient,_merge,_metrics,_check_structure,
    cascade,detector_probability,projection_bias,scan_schedules,physical_plan,
)

NOISY = (Q(3,4),)+(Q(1,12),)*3


def independent_count(n,r,d,h):
    if r == 0:
        return (1-d)**n*(1-h)
    return (n*d*(1-d)**(n-1)*(1-h) if n else Q(0))+(1-d)**n*h


@lru_cache(maxsize=None)
def local_polynomial_from_permanent(n,r):
    total = n[1]+n[2]
    out = (n[0],r,total-r,n[3])
    u = embed(4,(1,2),COUPLER)
    # scaled_amplitude is sqrt(prod out!)*normalised Fock amplitude.
    return _scaled_amplitude(u,n,out,4)*SQRT2**sum(k==2 for k in n)/_gram(out)


def independent_full_first_round(weights,m,d,h):
    """Use v0.34's direct Fock trajectories, retain ALL four payload modes."""
    out = defaultdict(lambda: ZERO)
    phases = {r['click']-1:r['correction_phase_steps'] for r in fusion_merge_certificate()}
    for first,second,mask in product(range(4),range(4),range(16)):
        lost = mask.bit_count()
        weight = weights[first]*weights[second]*m**(4-lost)*(1-m)**lost
        if not weight: continue
        for env,true,payload in _round_trajectories(first,second,mask):
            for ca,cb in product((0,1),repeat=2):
                observed = (int(ca==0),int(ca==1),int(cb==0),int(cb==1))
                factor = weight
                for n,r in zip(true,observed): factor *= independent_count(n,r,d,h)
                if not factor: continue
                vector = {}
                for n,amp in payload:
                    # Convert normalised Fock amplitudes into creation-monomial coefficients.
                    vector[n] = amp*H2**sum(k==2 for k in n)*ZETA**(phases[ca]*n[1]+phases[cb]*n[3])
                for n,nn in product(vector,repeat=2):
                    out[n,nn] += factor*vector[n]*vector[nn].conjugate()
    return {key:_r(c) for key,c in out.items() if c != ZERO}


def assert_positive_blocks(case,state):
    """Exact rational Schur complements; positivity is invariant under Gram scaling."""
    blocks = defaultdict(set)
    for n,m in state:
        blocks[sum(n[:2]),sum(n[2:])].update((n,m))
    for sector,basis in blocks.items():
        basis = sorted(basis)
        matrix = [[state.get((n,m),Q(0)) for m in basis] for n in basis]
        for k in range(len(basis)):
            pivot = matrix[k][k]
            case.assertGreaterEqual(pivot,0,sector)
            if not pivot:
                case.assertTrue(all(matrix[k][j]==0 for j in range(k+1,len(basis))),sector)
            else:
                for i in range(k+1,len(basis)):
                    for j in range(k+1,len(basis)):
                        matrix[i][j] -= matrix[i][k]*matrix[k][j]/pivot


class PolynomialStateTests(unittest.TestCase):
    def test_factorial_trace_is_required(self):
        n = (2,0,2,0)
        state = {(n,n):Q(1,4)}
        self.assertEqual(_trace(state),1)
        self.assertNotEqual(sum(state.values()),1)
        self.assertTrue(_check_structure(state))

    def test_loss_is_trace_preserving_in_every_supported_sector(self):
        for na,nb in product(range(5),repeat=2):
            n = (na,0,0,nb)
            state = {(n,n):Q(1,_gram(n))}
            for eta in (Q(0),Q(2,3),Q(1)):
                lost = _loss(state,eta)
                self.assertEqual(_trace(lost),1)
                self.assertTrue(_check_structure(lost))

    def test_loss_composes_and_retains_source_coherence(self):
        states = ((2,0,2,0),(1,1,1,1),(0,2,0,2))
        amps = (Q(1,2),Q(1),Q(1,2))
        state = {(n,m):amps[i]*amps[j]/3 for i,n in enumerate(states) for j,m in enumerate(states)}
        self.assertEqual(_trace(state),1)
        self.assertEqual(_loss(_loss(state,Q(3,4)),Q(2,3)),_loss(state,Q(1,2)))
        lost = _loss(state,Q(1,2))
        expected = double_pair_channel('1/2')['unnormalised_density']
        actual = tuple(tuple(lost.get((n,m),Q(0)) for m in QUBIT) for n in QUBIT)
        self.assertEqual(actual,expected)
        self.assertEqual(actual[0][3],Q(1,12))

    def test_hadamard_polynomial_against_fock_engine_including_four_photons(self):
        h = ((H2,H2),(H2,-H2))
        for n in product(range(3),repeat=2):
            expected = dict(_h_polynomial(*n))
            for r in range(sum(n)+1):
                out = (sum(n)-r,r)
                actual = _scaled_amplitude(h,n,out,2)*SQRT2**sum(k==2 for k in n)/_gram(out)
                self.assertEqual(actual,H2**sum(n)*expected.get(out,0))

    def test_hadamard_square_and_norm_for_excess_payload(self):
        n = (1,1,1,1)
        state = {(n,n):Q(1)}
        once = _hadamards(state)
        self.assertEqual(_trace(once),1)
        self.assertEqual(_hadamards(once),state)
        self.assertIn(((2,0,2,0),(0,2,0,2)),once)
        assert_positive_blocks(self,once)

    def test_structure_checks_reject_nonhermitian_or_cross_charge_data(self):
        n,m = QUBIT[0],QUBIT[3]
        with self.assertRaises(ValueError): _check_structure({(n,m):Q(1)})
        with self.assertRaises(ValueError): _check_structure({(n,VACUUM):Q(1),(VACUUM,n):Q(1)})
        with self.assertRaises(ValueError): _check_structure({(n,n):1.0})


class InstrumentTests(unittest.TestCase):
    def test_count_distribution_through_four_photons(self):
        for n,d,h in product(range(5),(Q(0),Q(3,4),Q(1)),(Q(0),Q(1,50),Q(1))):
            self.assertEqual(sum(detector_probability(n,r,d,h) for r in range(6)),1)
            for r in (0,1):
                self.assertEqual(detector_probability(n,r,d,h),independent_count(n,r,d,h))

    def test_local_channel_against_permanent_for_all_second_level_inputs(self):
        d,h = Q(4,5),Q(1,50)
        phases = [r['correction_phase_steps'] for r in fusion_merge_certificate()]
        sites = tuple((total-k,k) for total in range(3) for k in range(total+1))
        for a,b,aa,bb in product(sites,repeat=4):
            if sum(a)!=sum(aa) or sum(b)!=sum(bb): continue
            n,m = a+b,aa+bb
            total = n[1]+n[2]
            actual = _merge_coefficient(n,m,d,h)
            if total != m[1]+m[2]:
                self.assertEqual(actual,0)
                continue
            expected = ZERO
            for r in range(total+1):
                c = local_polynomial_from_permanent(n,r)*local_polynomial_from_permanent(m,r).conjugate()
                for click,phase in enumerate(phases):
                    likelihood = independent_count(r,int(click==0),d,h)*independent_count(total-r,int(click==1),d,h)
                    expected += c*factorial(r)*factorial(total-r)*likelihood*ZETA**(phase*(n[3]-m[3]))
            self.assertEqual(F.coerce(actual),expected,(n,m))

    def test_complete_first_round_state_matches_independent_fock_reference(self):
        for p,m,d,h in (((Q(1),Q(0),Q(0),Q(0)),Q(2,3),Q(3,4),Q(1,20)),
                        (NOISY,Q(1),Q(9,10),Q(1,10))):
            reference = independent_full_first_round(p,m,d,h)
            actual = cascade(p,'Z',input_survival=m,detector_efficiency=d,dark_per_mode=h)
            probability = actual['levels'][0]['herald_probability']
            self.assertEqual(_trace(reference),probability)
            self.assertEqual(actual['final_state'],{key:c/probability for key,c in reference.items()})

    def test_one_round_preserves_v034_herald_and_valid_sector(self):
        for basis in 'ZX':
            cfg = dict(input_survival='9/10',detector_efficiency='4/5',dark_per_mode='1/100')
            old,new = optical_round(NOISY,basis,**cfg),cascade(NOISY,basis,**cfg)
            probability = new['levels'][0]['herald_probability']
            self.assertEqual(probability,old['herald_probability'])
            self.assertEqual(new['fidelity'],old['conditional_fidelity'])
            self.assertEqual(new['valid_sector_fidelity'],old['valid_sector_fidelity'])
            self.assertEqual(new['valid_payload_fraction'],old['valid_payload_fraction'])
            matrix = tuple(tuple(new['final_state'].get((n,m),Q(0))*probability for m in QUBIT) for n in QUBIT)
            self.assertEqual(matrix,old['valid_payload_density'])

    def test_excess_input_is_rejected_not_truncated(self):
        n = (3,0,0,0)
        state = {(n,n):Q(1,6)}
        with self.assertRaises(ValueError): _merge(state,state,'Z',Q(1),Q(0))


class CascadeTests(unittest.TestCase):
    def test_all_ideal_schedules_reproduce_existing_recurrence(self):
        for bases in ('','Z','X','ZZ','ZX','XZ','XX'):
            actual = cascade(NOISY,bases)
            old = purification_schedule(NOISY,bases)
            self.assertEqual(actual['fidelity'],old['fidelity'])
            self.assertEqual(actual['expected_raw_pairs'],old['expected_raw_pairs'])
            self.assertEqual(actual['valid_payload_fraction'],1)

    def test_noisy_two_round_result_and_cost_use_actual_heralds(self):
        r = cascade(NOISY,'ZX',input_survival='9/10',detector_efficiency='9/10')
        self.assertEqual(r['fidelity'],Q(15327225,48114809))
        self.assertEqual(r['valid_payload_fraction'],Q(16985700,48114809))
        self.assertEqual(r['valid_sector_fidelity'],Q(841,932))
        p1,p2 = [level['herald_probability'] for level in r['levels']]
        self.assertEqual(r['expected_raw_pairs'],4/(p1*p2))
        self.assertEqual(r['one_tree_probability'],p1*p1*p2)
        self.assertLess(r['fidelity'],Q(1,3))

    def test_hidden_projection_materially_overstates_fidelity(self):
        b = projection_bias(NOISY,input_survival='9/10',detector_efficiency='9/10')
        self.assertEqual(b['actual']['fidelity'],Q(15327225,48114809))
        self.assertEqual(b['extra_sector_projection']['fidelity'],Q(1703025,2888201))
        self.assertGreater(b['extra_sector_projection']['fidelity']-b['actual']['fidelity'],Q(1,4))
        self.assertFalse(b['projection_is_available'])

    def test_two_round_dark_channel_retains_eight_photon_sector(self):
        r = cascade(NOISY,'ZX',input_survival='9/10',detector_efficiency='4/5',dark_per_mode='1/50')
        self.assertEqual(r['trace'],1)
        self.assertEqual(r['max_photons_per_site'],4)
        self.assertGreater(r['photon_sector_weights'].get((4,4),0),0)
        self.assertGreater(r['photon_sector_weights'].get((0,0),0),0)
        self.assertEqual(sum(r['photon_sector_weights'].values()),1)
        self.assertTrue(_check_structure(r['final_state']))
        assert_positive_blocks(self,r['final_state'])

    def test_fixed_waits_compose_at_every_level(self):
        cfg = dict(detector_efficiency='9/10',dark_per_mode='1/100')
        a = cascade(NOISY,'ZX',memory='9/10',left_wait_rounds=1,right_wait_rounds=1,**cfg)
        b = cascade(NOISY,'ZX',input_survival='9/10',**cfg)
        self.assertEqual(a['final_state'],b['final_state'])
        self.assertEqual(a['expected_raw_pairs'],b['expected_raw_pairs'])
        c = cascade(NOISY,'ZX',memory='99/100',left_wait_rounds=4,right_wait_rounds=0,**cfg)
        self.assertNotEqual(c['parameters']['left_survival'],c['parameters']['right_survival'])
        self.assertEqual(c['trace'],1)
        self.assertFalse(c['stochastic_waiting_modelled'])

    def test_no_herald_condition_returns_no_state(self):
        for cfg in (dict(detector_efficiency=0),dict(input_survival=0)):
            r = cascade(NOISY,'ZX',**cfg)
            self.assertEqual(r['status'],'NO_HERALDS')
            self.assertEqual(r['final_state'],{})
            self.assertIsNone(r['fidelity'])
            self.assertIsNone(r['expected_raw_pairs'])
            self.assertEqual(len(r['levels']),1)

    def test_dark_heralds_do_not_create_photons(self):
        r = cascade(NOISY,'ZX',input_survival=0,dark_per_mode='1/100')
        self.assertEqual(r['final_state'],{(VACUUM,VACUUM):Q(1)})
        self.assertEqual(r['fidelity'],0)
        self.assertGreater(r['expected_raw_pairs'],1)
        self.assertEqual(len(r['levels']),2)

    def test_explicit_round_limit_and_input_validation(self):
        for bases in ('ZXZ','Y',['Z']):
            with self.assertRaises(ValueError): cascade(NOISY,bases)
        for cfg in (dict(memory=0.9),dict(detector_efficiency=True),dict(left_wait_rounds=33),
                    dict(right_wait_rounds=-1),dict(dark_per_mode=2)):
            with self.assertRaises((ValueError,TypeError)): cascade(NOISY,**cfg)
        for args in ((5,0,1,0),(1,6,1,0)):
            with self.assertRaises(ValueError): detector_probability(*args)

    def test_scan_includes_untouched_source_and_all_bounded_schedules(self):
        rows = scan_schedules(NOISY,input_survival='9/10',detector_efficiency='9/10')
        self.assertEqual([r['bases'] for r in rows],['','Z','X','ZZ','ZX','XZ','XX'])
        self.assertEqual(rows[0]['fidelity'],Q(3,4))
        self.assertTrue(all(row['fidelity']<rows[0]['fidelity'] for row in rows[1:]))

    def test_plan_records_actual_bounds(self):
        p = physical_plan()
        self.assertEqual(p['maximum_levels'],2)
        self.assertEqual(p['raw_photons_per_unretried_tree'],8)
        self.assertEqual(p['output_total_photons_max'],8)


if __name__ == '__main__':
    unittest.main()
