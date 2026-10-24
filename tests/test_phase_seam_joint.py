"""Exact tests with independent dense matrices used ONLY as a reference."""
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import random
import unittest

from phase_seam_foundation.joint import (
    E, ZERO, ONE, IMAG, INV_SQRT2 as H, Element as A, State, local,
    observable, projector, product_reference, interaction, bell_preparation,
    bell_settings, chsh, tsirelson_sos, sign, gns, verify_gns, represent,
    mixture, basis_product, ResourceLimit)


def mm(a,b):
    return tuple(tuple(sum((a[i][k]*b[k][j] for k in range(len(b))),ZERO)
                       for j in range(len(b[0]))) for i in range(len(a)))


def dagger(a):
    return tuple(tuple(a[j][i].conjugate() for j in range(len(a))) for i in range(len(a[0])))


def dense(a):
    # Direct generator matrices, independent of the interpreter product table.
    blocks = (((ONE,ZERO),(ZERO,ONE)),((ONE,ZERO),(ZERO,-ONE)),
              ((ZERO,-ONE),(ONE,ZERO)),((ZERO,ONE),(ONE,ZERO)))
    d = 2**a.sites
    result = [[ZERO]*d for _ in range(d)]
    for k,c in enumerate(a.coefficients):
        for i,j in product(range(d),repeat=2):
            value = c
            for site in range(a.sites):
                value *= blocks[(k//4**site)%4][(i//2**site)%2][(j//2**site)%2]
            result[i][j] += value
    return tuple(tuple(r) for r in result)


def trace(a):
    return sum((a[i][i] for i in range(len(a))),ZERO)


def dense_expect(state,obs):
    # Compute directly from preparation operators; do not use state.density.
    numerator,denominator = ZERO,ZERO
    for w,word in state.factors:
        s = dense(word)
        numerator += w*trace(mm(mm(dagger(s),dense(obs)),s))
        denominator += w*trace(mm(dagger(s),s))
    return numerator/denominator


ANGLES = ((ONE,ZERO),(H,H),(ZERO,ONE),(-H,H),
          (-ONE,ZERO),(-H,-H),(ZERO,-ONE),(H,-H))


class JointAlgebraTests(unittest.TestCase):
    def test_all_basis_products_and_daggers_against_matrices(self):
        for n in (1,2):
            basis = [A.basis(n,i) for i in range(4**n)]
            for x in basis:
                self.assertEqual(dense(x.dagger()),dagger(dense(x)))
                self.assertEqual(x.dagger()*x,A.basis(n))
                for y in basis:
                    self.assertEqual(dense(x*y),mm(dense(x),dense(y)))

    def test_all_4096_basis_associativity_triples(self):
        for a,b,c in product(range(16),repeat=3):
            i,s = basis_product(a,b,2)
            left,t = basis_product(i,c,2)
            j,u = basis_product(b,c,2)
            right,v = basis_product(a,j,2)
            self.assertEqual((left,s*t),(right,u*v))

    def test_emk_relations_and_dagger_mixed_complex_words(self):
        k,r,l = (local(1,0,x) for x in ("K","R","L"))
        identity = A.basis(1)
        self.assertEqual(k*k,identity)
        self.assertEqual(r*r,-identity)
        self.assertEqual(k*r,-r*k)
        self.assertEqual(r*k,l)
        x,y = (identity+k*IMAG+r*F(2,3)), (l*H-r*E(2,1,1,-1))
        self.assertEqual((x*y).dagger(),y.dagger()*x.dagger())
        self.assertEqual(dense(x*y),mm(dense(x),dense(y)))

    def test_tau_positive_norm_identity_and_cyclic_trace(self):
        rng = random.Random(141)
        for _ in range(8):
            words = [A(2,tuple(E(*(F(rng.randint(-2,2),3) for _ in range(4)))
                              for _ in range(16))) for _ in range(2)]
            x,y = words
            self.assertEqual((x.dagger()*x).tau(),
                             sum((c.conjugate()*c for c in x.coefficients),ZERO))
            self.assertEqual((x*y).tau(),(y*x).tau())
            self.assertGreater(sign((x.dagger()*x).tau()),0)

    def test_exact_sign_without_floating_comparison(self):
        for a,b in product(range(-8,9),repeat=2):
            value=E(a,b)
            actual=sign(value)
            self.assertEqual(actual,-sign(-value))
            self.assertEqual(actual == 0, a == b == 0)
            if a*b >= 0:
                self.assertEqual(actual,(a+b>0)-(a+b<0))
            elif a:
                self.assertEqual(actual,((a>0)-(a<0))*((a*a>2*b*b)-(a*a<2*b*b)))
        with self.assertRaises(ValueError): sign(IMAG)

    def test_oriented_reflection_matches_v01_at_supported_grid8_angles(self):
        from phase_seam_foundation import Cell,Config,Operation
        # Matrix acts on the real coordinate pair, while v0.1 stores angle index.
        for r,h in product(range(8),repeat=2):
            cut=observable(1,0,*ANGLES[h])
            x,y=ANGLES[r]
            m=dense(cut)
            result=(m[0][0]*x+m[0][1]*y,m[1][0]*x+m[1][1]*y)
            old=Cell.start((r,0,0,0),config=Config(grid=8)).apply(Operation("cut",(0,h)))
            self.assertEqual(result,ANGLES[old.phases[0]])
            self.assertEqual(cut*cut,A.basis(1))

    def test_cut_pair_generates_rotation_without_conjugating_complex_coefficients(self):
        k,l = local(1,0,"K"),local(1,0,"L")
        self.assertEqual(l*k,local(1,0,"R"))
        self.assertEqual(k*l,-local(1,0,"R"))
        # Complex-linear extension commutes with i; universal conjugation would not.
        self.assertEqual(k*(A.basis(1)*IMAG),(k*IMAG))
        self.assertEqual((k*(A.basis(1)*IMAG)).coefficients[1],IMAG)

    def test_projector_resolution_and_all_supported_axis_pairs(self):
        for u,v in ANGLES+((E(F(3,5)),E(F(4,5))),):
            obs=observable(1,0,u,v)
            p,m=projector(obs,1),projector(obs,-1)
            self.assertEqual(p*p,p)
            self.assertEqual(m*m,m)
            self.assertEqual(p*m,A.basis(1)*0)
            self.assertEqual(p+m,A.basis(1))

    def test_invalid_types_size_and_observables(self):
        for call in (lambda:A.basis(True),lambda:A.basis(3),
                     lambda:A.basis(1,True),lambda:A(1,(0,0,0,0.1)),
                     lambda:observable(2,True,1,0),lambda:observable(2,0,1,1),
                     lambda:observable(1,0,IMAG,0),lambda:projector(local(1,0,"R"),1),
                     lambda:projector(local(1,0,"K"),True),
                     lambda:A.basis(1)+A.basis(2)):
            with self.assertRaises((ValueError,TypeError)): call()

    def test_coefficient_resource_failure_does_not_mutate_input(self):
        x=A.basis(2)*2**2048
        before=x.coefficients
        with self.assertRaises(ResourceLimit): x*x
        self.assertEqual(x.coefficients,before)
        with self.assertRaises(ResourceLimit): A.basis(1)*2**4096


class JointStateTests(unittest.TestCase):
    def test_preparation_and_interaction_derive_singlet_moments(self):
        s=bell_preparation()
        self.assertEqual(s.expect(A.basis(2)),ONE)
        for site in (0,1):
            for x in ("K","R","L"):
                self.assertEqual(s.expect(local(2,site,x)),ZERO)
        for x,y in product(("K","R","L"),repeat=2):
            expected=ZERO if x!=y else (ONE if x=="R" else -ONE)
            self.assertEqual(s.expect(local(2,0,x)*local(2,1,y)),expected)
        ref=product_reference()
        self.assertEqual(ref.expect(local(2,0,"K")),ONE)
        self.assertEqual(ref.expect(local(2,1,"K")),-ONE)
        self.assertEqual(s.unitary(interaction().dagger()).density,ref.density)

    def test_exact_joint_probabilities_and_non_signaling_all_64_contexts(self):
        s=bell_preparation()
        for (u,v),(x,y) in product(ANGLES,repeat=2):
            a,b=observable(2,0,u,v),observable(2,1,x,y)
            d=s.joint(a,b)
            self.assertEqual(sum(d.values(),ZERO),ONE)
            for oa,ob in product((-1,1),repeat=2):
                expected=(ONE-(u*x+v*y)*(oa*ob))/4
                self.assertEqual(d[oa,ob],expected)
                self.assertGreaterEqual(sign(d[oa,ob]),0)
                self.assertEqual(sum((d[oa,k] for k in (-1,1)),ZERO),E(F(1,2)))
                self.assertEqual(sum((d[k,ob] for k in (-1,1)),ZERO),E(F(1,2)))

    def test_joint_values_match_independent_dense_preparation(self):
        rng=random.Random(2056)
        state=State(((F(1,3),A(2,tuple(E(rng.randint(-1,1),0,rng.randint(-1,1),0)
                                        for _ in range(16)))),
                     (F(2,3),product_reference().factors[0][1])))
        for u,v in ANGLES:
            a,b=observable(2,0,u,v),observable(2,1,H,-H)
            self.assertEqual(state.expect(a*b),dense_expect(state,a*b))
            for outcomes,p in state.joint(a,b).items():
                effect=projector(a,outcomes[0])*projector(b,outcomes[1])
                self.assertEqual(p,dense_expect(state,effect))

    def test_chsh_2sqrt2_and_sos_saturation(self):
        s=bell_preparation(); settings=bell_settings()
        self.assertEqual(s.expect(chsh(settings)),E(b=2))
        self.assertGreater(sign(s.expect(chsh(settings))-2),0)
        for d in tsirelson_sos(settings):
            self.assertEqual(s.expect(d.dagger()*d),ZERO)
        rng=random.Random(64)
        for _ in range(12):
            settings=tuple(observable(2,site,*rng.choice(ANGLES)) for site in (0,0,1,1))
            ds=tsirelson_sos(settings)
            self.assertEqual(E(b=2)-s.expect(chsh(settings)),
                             sum((s.expect(d.dagger()*d) for d in ds),ZERO)*H)
            self.assertGreaterEqual(sign(E(b=2)-s.expect(chsh(settings))),0)

    def test_pr_style_table_fails_positive_square_witness(self):
        # The four PR correlations are only a negative control, never a State.
        settings=(local(2,0,"K"),local(2,0,"L"),local(2,1,"K"),local(2,1,"L"))
        moments={0:ONE,1+4:ONE,1+12:ONE,3+4:ONE,3+12:-ONE}
        def pseudo(word):
            return sum((c*moments.get(i,ZERO) for i,c in enumerate(word.coefficients)),ZERO)
        self.assertEqual(pseudo(chsh(settings)),E(4))
        d0,_=tsirelson_sos(settings)
        bad=pseudo(d0.dagger()*d0)
        self.assertEqual(bad,E(2,-2))
        self.assertLess(sign(bad),0)

    def test_sequential_repeatability_zero_outcomes_and_order(self):
        s=bell_preparation(); a,b=local(2,0,"K"),local(2,1,"K")
        for outcome in (-1,1):
            p,after=s.branch(projector(a,outcome))
            self.assertEqual(p,E(F(1,2)))
            self.assertEqual(after.branch(projector(a,outcome))[0],ONE)
            self.assertEqual(after.branch(projector(a,-outcome)),(ZERO,None))
            self.assertEqual(after.expect(b),E(-outcome))
        for oa,ob in product((-1,1),repeat=2):
            pa,sa=s.branch(projector(a,oa))
            pb,sb=s.branch(projector(b,ob))
            pab,ab=sa.branch(projector(b,ob))
            pba,ba=sb.branch(projector(a,oa))
            self.assertEqual(pa*pab,pb*pba)
            if ab is not None: self.assertEqual(ab.density,ba.density)
            else: self.assertIsNone(ba)

    def test_noncommuting_readout_disturbs_instead_of_joint_hidden_assignment(self):
        initial=State(((ONE,projector(local(1,0,"K"),1)),))
        k,l=local(1,0,"K"),local(1,0,"L")
        self.assertEqual(initial.branch(projector(k,1))[0],ONE)
        p,after=initial.branch(projector(l,1))
        self.assertEqual(p,E(F(1,2)))
        self.assertEqual(after.branch(projector(k,1))[0],E(F(1,2)))
        self.assertEqual(initial.expect(k*l),ZERO)

    def test_complete_local_measurement_and_reset_do_not_signal(self):
        s=bell_preparation(); b=local(2,1,"K")
        channels=((projector(b,1),projector(b,-1)),
                  (projector(b,1),local(2,1,"L")*projector(b,-1)))
        for operators in channels:
            out=s.channel(operators)
            for u,v in ANGLES:
                a=observable(2,0,u,v)
                self.assertEqual(out.expect(a),s.expect(a))
            self.assertEqual(out.normalization,s.normalization)
        reset=s.channel(channels[1])
        self.assertEqual(reset.expect(b),ONE)
        with self.assertRaises(ValueError): s.channel((projector(b,1),))

    def test_noise_visibility_threshold_and_product_controls(self):
        bell=bell_preparation(); white=State(((ONE,A.basis(2)),))
        settings=bell_settings()
        for v in (E(F(1,2)),H,E(F(3,4))):
            noisy=mixture(((v,bell),(ONE-v,white)))
            self.assertEqual(noisy.expect(chsh(settings)),E(b=2)*v)
        threshold=mixture(((H,bell),(ONE-H,white)))
        self.assertEqual(threshold.expect(chsh(settings)),E(2))
        self.assertLessEqual(sign(product_reference().expect(chsh(settings))-2),0)
        self.assertEqual(white.expect(chsh(settings)),ZERO)

    def test_unitarity_range_and_rational_partial_interaction(self):
        for c,s in ((1,0),(0,1),(F(3,5),F(4,5)),(H,H)):
            u=interaction(c,s); state=product_reference().unitary(u)
            self.assertEqual(u.dagger()*u,A.basis(2))
            self.assertEqual(state.expect(local(2,0,"K")),E.coerce(c)**2-E.coerce(s)**2)
        for call in (lambda:interaction(1,1),lambda:product_reference().unitary(A.basis(2)*2)):
            with self.assertRaises(ValueError):call()

    def test_invalid_preparations_channels_locality_and_budgets(self):
        identity=A.basis(2); s=bell_preparation()
        for call in (lambda:State(()),lambda:State(((ONE,identity*0),)),
                     lambda:State(((-ONE,identity),)),lambda:State(((IMAG,identity),)),
                     lambda:mixture(((F(1,3),s),(F(1,3),s))),
                     lambda:s.branch(identity*F(1,2)),
                     lambda:s.joint(local(2,1,"K"),local(2,0,"K")),
                     lambda:s.channel((A.basis(1),))):
            with self.assertRaises((ValueError,TypeError)): call()
        large=State(((ONE,identity),)*64)
        before=large.factors
        with self.assertRaises(ResourceLimit):
            large.channel((projector(local(2,0,"K"),1),projector(local(2,0,"K"),-1)))
        self.assertEqual(large.factors,before)
        with self.assertRaises(ResourceLimit): State(((ONE,identity),)*65)


class GNSRecoveryTests(unittest.TestCase):
    def test_complex_preparation_quotient_and_adjoint(self):
        phase=(A.basis(2)+local(2,0,"K")*IMAG)*H
        s=bell_preparation().unitary(phase)
        q=gns(s)
        self.assertEqual(q["rank"],4)
        self.assertTrue(verify_gns(s,q))
        self.assertTrue(any(x.c or x.d for row in q["gram"] for x in row))
        metric=tuple(tuple(q["gram"][i][j] for j in q["basis"]) for i in q["basis"])
        for x in (local(2,0,"R"),local(2,1,"L"),phase):
            m=represent(x,q)
            self.assertEqual(mm(dagger(m),metric),mm(metric,represent(x.dagger(),q)))

    def test_pure_and_mixed_quotient_ranks(self):
        for state,rank in ((bell_preparation(),4),(product_reference(),4),
                           (State(((ONE,A.basis(1)),)),4),
                           (State(((ONE,projector(local(1,0,"K"),1)),)),2),
                           (State(((ONE,A.basis(2)),)),16)):
            quotient=gns(state)
            self.assertEqual(quotient["rank"],rank)
            self.assertTrue(verify_gns(state,quotient))

    def test_null_directions_are_left_ideal_and_born_norm_recovered(self):
        s=bell_preparation(); q=gns(s)
        self.assertEqual(len(q["gram"])-q["rank"],12)
        for i in range(16):
            null=A.basis(2,i)
            for row,b in zip(q["coordinates"],q["basis"]):
                null=null-A.basis(2,b)*row[i]
            self.assertEqual(s.expect(null.dagger()*null),ZERO)
            for g in (local(2,0,"K"),local(2,0,"R"),local(2,1,"L")):
                mapped=g*null
                self.assertEqual(s.expect(mapped.dagger()*mapped),ZERO)
        for a in bell_settings():
            p=projector(a,1)
            self.assertEqual(s.expect(p),s.expect(p.dagger()*p))

    def test_derived_representation_respects_product_and_inner_product(self):
        s=bell_preparation(); q=gns(s)
        for x,y in product(bell_settings(),repeat=2):
            self.assertEqual(mm(represent(x,q),represent(y,q)),represent(x*y,q))
        gram=tuple(tuple(q["gram"][i][j] for j in q["basis"]) for i in q["basis"])
        for x in bell_settings():
            m=represent(x,q)
            self.assertEqual(mm(dagger(m),gram),mm(gram,represent(x.dagger(),q)))

    def test_quotient_verifier_rejects_tamper_and_wrong_state(self):
        s=bell_preparation(); q=gns(s)
        bad=dict(q,rank=True)
        self.assertFalse(verify_gns(s,bad))
        bad=dict(q,basis=(0,0,2,3))
        self.assertFalse(verify_gns(s,bad))
        coords=[list(r) for r in q["coordinates"]]; coords[0][5]+=ONE
        self.assertFalse(verify_gns(s,dict(q,coordinates=tuple(map(tuple,coords)))))
        self.assertFalse(verify_gns(product_reference(),q))


if __name__=="__main__":
    unittest.main()
