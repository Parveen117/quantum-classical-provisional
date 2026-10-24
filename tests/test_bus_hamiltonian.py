"""Exact generator/schedule checks and independent continuous Hamiltonians."""
from decimal import Decimal, localcontext
from fractions import Fraction as Q
from itertools import product
import math
import random
import unittest

import numpy as np

from native_relational_qc.cyclotomic64 import ZETA, ZERO
from native_relational_qc.cyclotomic_pow2 import field_of_order, _pi_bounds
from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.weyl_bus import rectangle, normal_form
from phase_seam_foundation.bus_hamiltonian import (
    BusDesign, centered_spectrum, fourier_matrix, generator_matrix,
    centered_kick_matrix, matched_area_sensitivity, sensitivity_matrix,
    implementation_bound, least_area_cz_design, jc_schedule, jc_pulse_bound,
    jc_gate_bound,
)


def dagger(a):return tuple(tuple(a[j][i].conjugate() for j in range(len(a))) for i in range(len(a[0])))


def mm(a,b):
    zero=type(a[0][0])()
    return tuple(tuple(sum((a[i][k]*b[k][j] for k in range(len(b)) if a[i][k] and b[k][j]),zero)
                       for j in range(len(b[0]))) for i in range(len(a)))


def dense(a):return np.array([[complex(x) for x in row] for row in a],dtype=complex)


def exp_i(angle,generator):
    values,vectors=np.linalg.eigh(generator)
    return (vectors*np.exp(1j*angle*values))@vectors.conjugate().T


def continuous_word(d,a,b,data,errors=(0,0,0,0)):
    # Independent complex Fourier construction and numerical diagonalization.
    k=np.arange(d); f=np.exp(-2j*np.pi*np.outer(k,k)/d)/math.sqrt(d)
    q=np.diag(k-(d-1)/2); p=f@q@f.conjugate().T
    s,t=1-2*(data&1),1-2*(data>>1)
    angles=(2*np.pi*a/d,2*np.pi*b/d,-2*np.pi*a/d,-2*np.pi*b/d)
    out=np.eye(d,dtype=complex)
    for angle,error,sign,g in zip(angles,errors,(s,t,s,t),(p,q,p,q)):
        out=exp_i(sign*(angle+error),g)@out
    return out


def exact_schedule_column(design,schedule,data,k):
    d=design.dimension; field=field_of_order(max(8,2*d)); f=fourier_matrix(d)
    vector=[field(int(i==k)) for i in range(d)]
    for event in schedule:
        kind=event["kind"]
        if kind=="data_x": data^=1<<event["data_site"]
        elif kind in ("dispersive","jc_pulse"):
            n=event["area_pi"]*d/2
            assert n.denominator==1
            z=centered_kick_matrix(d,"q",int(n),sign=1-2*((data>>event["data_site"])&1))
            vector=[z[j][j]*vector[j] for j in range(d)]
        elif kind in ("fourier","fourier_inverse"):
            matrix=f if kind=="fourier" else dagger(f)
            vector=[sum((x*y for x,y in zip(row,vector) if x and y),field()) for row in matrix]
        elif kind!="phase_compensation":raise ValueError(kind)
        # jc_pulse here denotes its ideal compensated dispersive target;
        # the actual JC mismatch is tested separately on exact two-level blocks.
    return data,tuple(vector)


class BusHamiltonianTests(unittest.TestCase):
    def test_fourier_unitarity_and_centered_generator_exact(self):
        for d in (2,4,8,16):
            f=fourier_matrix(d); identity=mm(f,dagger(f))
            field=type(f[0][0])
            self.assertEqual(identity,tuple(tuple(field(int(i==j)) for j in range(d)) for i in range(d)))
            q=generator_matrix(d,"q"); p=generator_matrix(d,"p")
            self.assertEqual(p,mm(mm(f,q),dagger(f)))
            self.assertEqual(p,dagger(p))
            self.assertEqual(sum(p[i][i] for i in range(d)),field())

    def test_centered_kicks_from_independent_spectral_sum(self):
        for d in (8,16,64):
            field=field_of_order(2*d); scale=field.ORDER//d
            for steps,sign in ((1,1),(2,-1),(-3,1)):
                actual=centered_kick_matrix(d,"p",steps,sign=sign)
                # Translation covariance reduces this full circulant identity
                # to every element of its first row, computed spectrally.
                for col in range(d):
                    expected=sum((field.root(scale*col*p+steps*sign*(2*p-d+1)) for p in range(d)),field())/d
                    self.assertEqual(actual[0][col],expected)
                self.assertEqual(actual,tuple(tuple(actual[0][(j-i)%d] for j in range(d)) for i in range(d)))

    def test_centered_phase_needs_finer_field_but_closed_loop_matches_v15(self):
        field=field_of_order(128)
        primitive=centered_kick_matrix(64,"p",1)
        self.assertTrue(any(e%2 for e,c in primitive[1][0].terms))
        target=normal_form(rectangle())
        for data,k in product(range(4),range(64)):
            s,t=1-2*(data&1),1-2*(data>>1); phase=field(1); label=k
            for axis,n,sign in (("p",2,s),("q",4,t),("p",-2,s),("q",-4,t)):
                if axis=="p":
                    phase*=field.root(-n*sign*63);label=(label+n*sign)%64
                else:phase*=field.root(n*sign*(2*label-63))
            self.assertEqual(label,k)
            self.assertTrue(all(e%2==0 for e,c in phase.terms))
            old=sum((ZETA**(e//2)*Q(c,phase.den) for e,c in phase.terms),ZERO)
            self.assertEqual(old,ZETA**target[data].phase)

    def test_literal_dispersive_and_fixed_sign_schedules(self):
        for design in (BusDesign(8,1,1),BusDesign(16,1,1,True)):
            d=design.dimension; field=field_of_order(2*d)
            for schedule in (design.schedule(),jc_schedule(design)):
                for data,k in product(range(4),range(d)):
                    out,vector=exact_schedule_column(design,schedule,data,k)
                    self.assertEqual(out,data)
                    sign=(1-2*(data&1))*(1-2*(data>>1))
                    phase=field.root(2*design.a*design.b*(2 if design.echo else 1)*sign)
                    self.assertEqual(vector,tuple(phase if j==k else field() for j in range(d)))

    def test_exact_derivative_against_independent_continuous_hamiltonian(self):
        eps=1e-6
        for design in (BusDesign(8,1,1),BusDesign(16,1,2),BusDesign(8,-1,2)):
            d,a,b=design.dimension,design.a,design.b
            for data,axis in product(range(4),("alpha","beta")):
                direction=(eps,0,-eps,0) if axis=="alpha" else (0,eps,0,-eps)
                plus=continuous_word(d,a,b,data,direction)
                minus=continuous_word(d,a,b,data,tuple(-x for x in direction))
                ideal=continuous_word(d,a,b,data)
                derivative=(plus-minus)/(2*eps)@ideal.conjugate().T
                expected=1j*dense(sensitivity_matrix(design,data,axis))
                self.assertLess(np.linalg.norm(derivative-expected,2),2e-7)

    def test_nontrivial_kicks_have_noncentral_first_order_error(self):
        cases=0
        for d in (2,4,8,16,32,64):
            for a,b in ((0,0),(0,1),(1,0),(1,1),(d//2,-1),(-d//2,d//2)):
                r=matched_area_sensitivity(BusDesign(d,a,b))
                self.assertEqual(r["first_order_bus_independent_alpha"],b%d==0)
                self.assertEqual(r["first_order_bus_independent_beta"],a%d==0)
                for branch in r["branches"]:
                    self.assertEqual(branch["alpha_trace"],0)
                    self.assertEqual(branch["beta_trace"],0)
                cases+=1
        self.assertEqual(cases,36)
        r=matched_area_sensitivity(BusDesign(64,2,4))
        self.assertEqual((r["alpha_operator_norm"],r["beta_operator_norm"]),(60,62))
        with self.assertRaises(ValueError):matched_area_sensitivity(BusDesign(16,1,1,True))

    def test_finite_area_error_bound_against_continuous_operator(self):
        design=BusDesign(8,1,1)
        for errors in ((Q(1,10000),Q(-1,20000),Q(1,30000),Q(1,40000)),(Q(1,3),)*4):
            bound=implementation_bound(design,area_bounds=[abs(e) for e in errors],
                  fourier_bounds=[0]*4,flip_bounds=[],residual_action_bound=0)
            for data in range(4):
                changed=continuous_word(8,1,1,data,tuple(float(e) for e in errors))
                ideal=continuous_word(8,1,1,data)
                self.assertLessEqual(np.linalg.norm(changed-ideal,2),float(bound["unitary_operator_error_bound"])+1e-12)
            self.assertFalse(bound["calibration_accepted"])

    def test_cost_comparison_and_literal_sign_reversal_overhead(self):
        expected={8:(1,1,Q(7,2)),16:(1,2,Q(45,8)),32:(2,2,Q(31,4)),64:(2,4,Q(189,16))}
        for d,(a,b,cost) in expected.items():
            best=least_area_cz_design(d)
            self.assertEqual((best.a,best.b),(a,b))
            self.assertEqual(best.resources()["conditional_time_at_unit_norm_rate_in_pi"],cost)
        self.assertIsNone(least_area_cz_design(4))
        self.assertIsNone(least_area_cz_design(8,echo=True))
        echo=least_area_cz_design(64,echo=True)
        self.assertEqual((echo.a,echo.b),(2,2))
        for design,flips in ((BusDesign(),4),(BusDesign(16,1,1,True),12)):
            self.assertEqual(sum(x["kind"]=="data_x" for x in jc_schedule(design)),flips)

    def test_reused_field_operations_and_pi_enclosure(self):
        rng=random.Random(1601); field=field_of_order(128)
        for _ in range(20):
            a,b,c=[field.root(rng.randrange(128))*Q(rng.randrange(-9,10),7)+field(Q(1,3)) for _ in range(3)]
            self.assertEqual(a*(b+c),a*b+a*c)
            self.assertEqual((a*b).conjugate(),a.conjugate()*b.conjugate())
            self.assertEqual((a/7)*7,a)
        with localcontext() as ctx:
            ctx.prec=65
            ref=Decimal('3.1415926535897932384626433832795028841971693993751058209749445923')
            lo,hi=_pi_bounds(128)
            decimal=lambda q:Decimal(q.numerator)/q.denominator
            self.assertLessEqual(decimal(lo),ref)
            self.assertGreaterEqual(decimal(hi),ref)

    def test_jc_spectral_remainder_against_independent_high_precision_roots(self):
        with localcontext() as ctx:
            ctx.prec=65
            for r,m in product((Q(1,1000),Q(1,50),Q(1,3)),range(1,65)):
                x=Decimal(r.numerator)/r.denominator
                shift=((1+4*x*x*m).sqrt()-1)/2
                remainder=x*x*m-shift
                self.assertGreaterEqual(remainder,0)
                self.assertLessEqual(remainder,x**4*m*m+Decimal('1e-60'))

    def test_jc_norm_bound_including_highest_code_block(self):
        for d,r,steps in product((8,16),(Q(1,1000),Q(1,50)),(1,2)):
            bound=jc_pulse_bound(d,steps,r)
            time=float(bound["detuning_time_pi"])*np.pi
            for m in range(1,d+1):
                coupling=float(r)*math.sqrt(m)
                h=np.array([[0.5,coupling],[coupling,-0.5]])
                actual=exp_i(-time,h)
                ideal=np.diag(np.exp(-1j*time*np.array([.5+float(r*r)*m,-.5-float(r*r)*m])))
                self.assertLessEqual(np.linalg.norm(actual-ideal,2),float(bound["operator_error_bound"])+1e-8)
            self.assertEqual(bound["maximum_excitation_block"],d)
            self.assertTrue(bound["includes_top_code_to_outside_transition"])
        # The highest admitted |e,d-1> couples to |g,d>, which cannot be
        # discarded by truncating the oscillator to exactly d basis states.
        d=8;r=.02;t=np.pi/4/r**2
        actual=exp_i(-t,np.array([[.5,r*math.sqrt(d)],[r*math.sqrt(d),-.5]]))
        self.assertGreater(abs(actual[1,0])**2,1e-8)

    def test_jc_gate_tradeoff_and_required_budget(self):
        design=BusDesign(); budgets=dict(area_bounds=[0]*4,fourier_bounds=[0]*4,
              flip_bounds=[0]*4,compensation_bounds=[0]*4,other_action_bound=0)
        first=jc_gate_bound(design,ratio=Q(1,1000),**budgets)
        second=jc_gate_bound(design,ratio=Q(1,2000),**budgets)
        self.assertLess(second["raw_operator_bound"],first["raw_operator_bound"])
        self.assertEqual(second["total_detuning_time_pi"],4*first["total_detuning_time_pi"])
        self.assertEqual(first["code_escape_probability_bound"],first["raw_operator_bound"]**2)
        self.assertFalse(first["loss_or_dissipative_noise_covered"])
        with self.assertRaises(ValueError):jc_gate_bound(design,ratio=Q(1,1000),**dict(budgets,flip_bounds=[]))

    def test_invalid_domains_and_bounds_fail_without_a_certificate(self):
        for bad in (True,0,3,128):
            with self.assertRaises(ValueError):BusDesign(bad)
        for a in (True,0.5,Q(1,2),5):
            with self.assertRaises(ValueError):BusDesign(8,a,1)
        with self.assertRaises(ValueError):BusDesign(echo=1)
        with self.assertRaises(ValueError):centered_kick_matrix(8,"p",1,sign=True)
        with self.assertRaises(ValueError):generator_matrix(8,"unknown")
        for invalid in (True,.1,-1):
            with self.assertRaises(ValueError):implementation_bound(BusDesign(),area_bounds=[invalid]*4,
                 fourier_bounds=[0]*4,flip_bounds=[],residual_action_bound=0)
        with self.assertRaises(ResourceLimit):jc_pulse_bound(8,1,Q(1,1<<5000))
        with self.assertRaises(ValueError):jc_pulse_bound(8,1,0)
        self.assertEqual(jc_pulse_bound(8,0,Q(1,100))["raw_operator_bound"],0)


if __name__ == "__main__":unittest.main()
