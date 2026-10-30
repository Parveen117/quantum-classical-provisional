"""Constitutive identities, independent finite responses and failed domains."""
import cmath
from fractions import Fraction as Q
import math
import unittest

from phase_seam_foundation.constitutive_response import (
    CubicEnergy, response_record, phase_control_response, coupled_optical_response,
    patch_bound, phase_observer_bounds, harmonic_phase_noise,
)
from phase_seam_foundation.photonic_io import fingerprint
from phase_seam_foundation.photonic_observer import observer_packet, assess_uncertainty
from phase_seam_foundation.photonic_response import optical_response, compose_response

PHASE = ((1,0),(0,1),(0,0),(0,0),(Q(1,2),Q(1,2)))
DRIVE = ((1,0),(0,1))


def model(mu=1):
    return CubicEnergy((2,1,5),(0,mu,0,0),(10,-10))


def packet(*,dx=1,dy=1,dt=1):
    return observer_packet((16,0,48,48),target="exchange_angle",measurements="reference",
                           state_scales=[dx]*5,reading_scales=[dy]*24,target_scales=[dt])


def probabilities(phases):
    """Independent continuous complex two-port word for finite-error tests."""
    def mul(a,b): return [[sum(x*y for x,y in zip(row,col)) for col in zip(*b)] for row in a]
    def diag(a,b): return [[a,0],[0,b]]
    h=1/math.sqrt(2); d=[[h,1j*h],[1j*h,h]]
    l,u,b,a,r=phases
    word=diag(1,cmath.exp(1j*a))
    for factor in (d,diag(cmath.exp(1j*u),cmath.exp(1j*l)),d,diag(1,cmath.exp(1j*b))):
        word=mul(word,factor)
    states=((1,0),(0,1),(h,h),(h,1j*h)); out=[]
    for source in states:
        for detector in states:
            amplitude=sum(complex(detector[i]).conjugate()*word[i][j]*source[j] for i in range(2) for j in range(2))
            out.append(abs(amplitude)**2)
    for s in range(2):
        for t in range(2):
            for alpha in (0,math.pi/2): out.append(abs((word[t][s]+cmath.exp(1j*(r-alpha)))/2)**2)
    return out


class ConstitutiveTests(unittest.TestCase):
    def test_energy_force_and_hessian_are_integrable_exactly(self):
        m=CubicEnergy((4,1,6),(Q(1,3),Q(1,4),Q(-1,5),Q(1,7)),(20,-20))
        q=(Q(1,10),Q(-1,20)); eps=Q(1,100); h=m.at(q)[0]
        for j in range(2):
            plus=list(q); minus=list(q); plus[j]+=eps; minus[j]-=eps
            force=m.force(q)[j]
            # Exact centered cubic derivative has a known diagonal cubic term.
            cubic=m.third[0 if j==0 else 3]
            self.assertEqual((m.energy(plus)-m.energy(minus))/(2*eps)-cubic*eps**2/6,force)
            for i in range(2):
                self.assertEqual((m.force(plus)[i]-m.force(minus)[i])/(2*eps),h[i][j])

    def test_six_responses_and_thermal_em_closure(self):
        r=response_record(model(),(Q(1,100),Q(-1,200)))
        t,e=r["thermal"],r["em"]
        self.assertEqual(t["Cp"]/t["Cv"],t["Ks"]/t["Kt"])
        self.assertEqual(e["epsilon_B"]*e["mu_E"],e["epsilon_H"]*e["mu_D"])
        self.assertEqual(r["responses"]["lambdaS"],-t["Ks"])
        self.assertEqual(r["responses"]["zT"],-t["Kt"])
        self.assertEqual(r["responses"]["lambdaS"]*r["responses"]["zS"],
                         r["responses"]["lambdaT"]*r["responses"]["zT"])

    def test_same_point_different_layers_and_curvature(self):
        records=[response_record(model(mu)) for mu in (0,1,5,-5)]
        self.assertTrue(all(r["responses"]==records[0]["responses"] for r in records))
        self.assertEqual([r["selected_response_curvature"] for r in records],[0,Q(5,324),Q(125,324),Q(125,324)])
        self.assertEqual([r["response_first"]["lambdaV"][1] for r in records],[0,-1,-5,5])

    def test_first_response_layer_matches_neighbouring_response(self):
        m=CubicEnergy((4,1,6),(Q(1,3),Q(1,4),Q(-1,5),Q(1,7)),(20,-20))
        q=(Q(1,100),Q(-1,200)); eps=Q(1,10**6); r=response_record(m,q)
        for j in range(2):
            plus=list(q); minus=list(q); plus[j]+=eps; minus[j]-=eps
            rp,rm=response_record(m,plus),response_record(m,minus)
            for name in r["responses"]:
                slope=(rp["responses"][name]-rm["responses"][name])/(2*eps)
                self.assertLess(abs(slope-r["response_first"][name][j]),Q(1,10**10))

    def test_clamped_and_released_control_responses_differ(self):
        free=phase_control_response(model(),(0,0),PHASE,DRIVE)
        held=phase_control_response(model(),(0,0),PHASE,DRIVE,held_coordinate=1)
        self.assertEqual(free[0],(Q(5,9),Q(-1,9)))
        self.assertEqual(held[0],(Q(1,2),0))
        self.assertEqual(held[1],(0,0))
        self.assertEqual(free[4],(Q(2,9),Q(1,18)))
        joint=coupled_optical_response(model(),(0,0),(16,0,48,48),PHASE,DRIVE)
        self.assertEqual(joint["measurement_per_control"],compose_response(optical_response((16,0,48,48))["jacobian"],free))

    def test_patch_proves_inverse_remainder_for_actual_force_record(self):
        m=model(); bound=patch_bound(m,(0,0),patch_radius=Q(1,20),force_radius=Q(1,100))
        chi=m.at((0,0))[1]; f0=m.force((0,0))
        for q in ((Q(1,1000),Q(-1,2000)),(Q(-1,2000),Q(1,1000))):
            df=tuple(a-b for a,b in zip(m.force(q),f0))
            self.assertLess(sum(v*v for v in df),bound["force_radius"]**2)
            tangent=tuple(sum(a*b for a,b in zip(row,df)) for row in chi)
            error=sum((a-b)**2 for a,b in zip(q,tangent))
            self.assertLessEqual(error,bound["inverse_linearization_remainder"]**2)

    def test_optical_and_composed_bounds_cover_finite_response(self):
        m=model(); p=packet(); b=phase_observer_bounds(m,(0,0),PHASE,p,patch_radius=Q(1,20),force_radius=Q(1,100))
        optical=optical_response((16,0,48,48)); j=optical["jacobian"]
        base=[math.pi/2,0,3*math.pi/2,3*math.pi/2,0]; y0=probabilities(base)
        self.assertLess(max(abs(x-float(complex(y).real)) for x,y in zip(y0,optical["probabilities"])),1e-14)
        for q in ((Q(1,1000),Q(-1,2000)),(Q(-1,2000),Q(1,1000))):
            dq=tuple(sum(a*x for a,x in zip(row,q)) for row in PHASE)
            df=tuple(a-c for a,c in zip(m.force(q),m.force((0,0))))
            control=phase_control_response(m,(0,0),PHASE,DRIVE)
            linear=tuple(sum(a*x for a,x in zip(row,df)) for row in control)
            actual=probabilities([a+float(x) for a,x in zip(base,dq)])
            for delta,key in ((dq,"optical"),(linear,"composed")):
                predicted=[y+sum(float(complex(a).real)*float(x) for a,x in zip(row,delta)) for y,row in zip(y0,j)]
                error=math.sqrt(sum((a-c)**2 for a,c in zip(actual,predicted)))
                upper=b["observer_bounds"]["nonlinear_remainder_bound"] if key=="optical" else b["composed_force_to_reading_remainder"]
                self.assertLessEqual(error,float(upper))

    def test_quadratic_material_still_has_optical_remainder(self):
        b=phase_observer_bounds(model(0),(0,0),PHASE,packet(),patch_radius=Q(1,20),force_radius=Q(1,100))
        self.assertEqual(b["patch"]["inverse_linearization_remainder"],0)
        self.assertGreater(b["observer_bounds"]["nonlinear_remainder_bound"],0)

    def test_normalization_and_existing_observer_integration(self):
        kwargs=dict(patch_radius=Q(1,20),force_radius=Q(1,100))
        base=phase_observer_bounds(model(),(0,0),PHASE,packet(),**kwargs)
        scaled=phase_observer_bounds(model(),(0,0),PHASE,packet(dx=2,dy=3,dt=7),**kwargs)
        self.assertEqual(2*scaled["observer_bounds"]["state_norm_bound"],base["observer_bounds"]["state_norm_bound"])
        self.assertEqual(3*scaled["observer_bounds"]["nonlinear_remainder_bound"],base["observer_bounds"]["nonlinear_remainder_bound"])
        r=assess_uncertainty(packet(),bounds=base["observer_bounds"])
        self.assertEqual(r["status"],"INCOMPLETE_UNCERTAINTY_BOUNDS")
        self.assertFalse(base["calibration_accepted"])

    def test_harmonic_noise_retains_cross_covariance_and_reference(self):
        m=CubicEnergy((1,0,1)); common=((1,0),(1,0),(0,0),(0,0),(1,0))
        same=harmonic_phase_noise(m,common,thermal_scale=Q(1,10))
        self.assertEqual(same["phase_covariance"][0][0],Q(1,10))
        self.assertEqual(same["phase_covariance"][0][1],Q(1,10))
        self.assertEqual(same["exchange_angle_variance"],0)
        independent=harmonic_phase_noise(m,PHASE,thermal_scale=Q(1,10))
        self.assertEqual(independent["exchange_angle_variance"],Q(1,5))
        with self.assertRaises(ValueError): harmonic_phase_noise(model(),PHASE,thermal_scale=1)

    def test_unstable_outside_patch_and_invalid_inputs_fail(self):
        for h in ((0,0,1),(1,2,1)):
            with self.assertRaises(ValueError): CubicEnergy(h).at((0,0))
        for R,B in ((1,Q(1,100)),(Q(1,20),1),(0,0),(Q(1,20),-1)):
            with self.assertRaises(ValueError): patch_bound(model(),(0,0),patch_radius=R,force_radius=B)
        for h in ((True,0,1),(1.0,0,1),(1,0)):
            with self.assertRaises((ValueError,TypeError)): CubicEnergy(h)
        with self.assertRaises(ValueError): response_record(CubicEnergy((1,0,1)))
        with self.assertRaises(ValueError): phase_control_response(model(),(0,0),PHASE,DRIVE,held_coordinate=True)

    def test_resigned_wrong_optical_normalization_is_rejected(self):
        p=packet(); p["scales"]["reading"]=["2"]*24
        p["packet_sha256"]=fingerprint({k:v for k,v in p.items() if k!="packet_sha256"})
        with self.assertRaisesRegex(ValueError,"optical and normalization"):
            phase_observer_bounds(model(),(0,0),PHASE,p,patch_radius=Q(1,20),force_radius=Q(1,100))


if __name__ == "__main__": unittest.main()
