from fractions import Fraction as Q
from itertools import product
import random
import unittest

from native_relational_qc.compact import ResourceLimit
from native_relational_qc.jet_readings import (EXISTING_FIRST_LAYER_MODEL,Jet,PolynomialEnergy,Reader,check_jet,
    classify_first_layer,default_candidates,fit_jet,first_layer_steps,ghost_energy,learn_jet,linear_phase_circuit,
    next_point,parity_classifier,quadratic_phase_distribution,read_linear_layer)


def random_energy(rng,degree):
    return PolynomialEnergy({(i,j):Q(rng.randint(-6,6),rng.randint(1,4)) for i in range(degree+1) for j in range(degree+1-i)}
                            |{(2,0):Q(3),(0,2):Q(4),(1,1):Q(1,2)})


class JetReadingsTests(unittest.TestCase):
    def test_cubic_family_reproduces_the_existing_identity_kappa_uv_over_324(self):
        for u,v in product(range(-7,8),repeat=2):
            if u and v:
                self.assertEqual(PolynomialEnergy.cubic(u,v).curvature((0,0)),Q(u*v,324),(u,v))

    def test_fit_reproduces_the_exact_jet_of_any_polynomial_within_its_degree(self):
        rng=random.Random(5)
        for degree in (2,3,4,5):
            energy=random_energy(rng,degree);order=degree-2;base=(Q(1,3),Q(-1,2))
            exact=energy.hessian_jet(base,order);reader=Reader(energy)
            result=learn_jet(reader,base,max_order=order+1)
            self.assertEqual(result['status'],f'consistent_at_order_{order}')
            self.assertEqual(result['jet'],exact)
            need=(order+1)*(order+2)//2
            self.assertLessEqual(reader.readings,need+3*(order+1))
            # Taylor coefficients turn into derivatives by alpha!.
            self.assertEqual(result['jet'].derivative((2,0)) if order>=2 else None,
                             tuple(2*c for c in exact.coefficients[(2,0)]) if order>=2 else None)

    def test_quadratic_energy_is_consistent_at_order_zero_and_cubic_at_order_one(self):
        quadratic=PolynomialEnergy({(2,0):Q(1),(1,1):Q(1),(0,2):Q(5,2),(1,0):Q(10)})
        self.assertEqual(learn_jet(Reader(quadratic),(0,0))['status'],'consistent_at_order_0')
        self.assertEqual(learn_jet(Reader(PolynomialEnergy.cubic(3,-5)),(0,0))['status'],'consistent_at_order_1')

    def test_unisolvence_is_checked_and_collinear_designs_fail(self):
        energy=PolynomialEnergy.cubic(1,1);line=[(Q(k),Q(0)) for k in range(3)]
        with self.assertRaises(ValueError):fit_jet((0,0),[(p,energy.hessian(p)) for p in line],1)
        with self.assertRaises(ValueError):fit_jet((0,0),[((0,0),energy.hessian((0,0)))]*3,1)
        with self.assertRaises(ValueError):fit_jet((0,0),[((0,0),energy.hessian((0,0)))],1)
        point,gain=next_point((0,0),line,line,1)
        self.assertIsNone(point);self.assertEqual(gain,0)
        point,gain=next_point((0,0),line,default_candidates((0,0)),1)
        self.assertIsNotNone(point);self.assertGreater(gain,0)

    def test_truncated_jet_is_falsified_by_a_check_reading_beyond_its_order(self):
        energy=PolynomialEnergy.cubic(2,-2);base=(0,0)
        jet=energy.hessian_jet(base,0)
        self.assertEqual(check_jet(jet,[((0,0),energy.hessian((0,0)))]),[])
        self.assertEqual(len(check_jet(jet,[((Q(1,2),0),energy.hessian((Q(1,2),0)))])),1)

    def test_curvature_is_invariant_under_linear_chart_change_and_first_layer_is_not(self):
        rng=random.Random(11)
        for _ in range(12):
            energy=random_energy(rng,rng.choice((3,4)));base=(Q(rng.randint(-2,2),3),Q(rng.randint(-2,2),5))
            try:kappa=energy.curvature(base)
            except ValueError:continue
            A=((Q(rng.randint(-3,3)),Q(rng.randint(-3,3))),(Q(rng.randint(-3,3)),Q(rng.randint(-3,3))))
            if not A[0][0]*A[1][1]-A[0][1]*A[1][0]:continue
            jet=energy.hessian_jet(base,2);moved=jet.transport(A)
            self.assertEqual(moved.curvature(),kappa)
            # The transported jet is the jet of the recomposed energy at A^-1 base.
            self.assertEqual(energy.compose_linear(A).hessian_jet(moved.base,2),moved)
        shear=((1,1),(0,1));jet=PolynomialEnergy.cubic(3,-5).hessian_jet((0,0),1)
        self.assertNotEqual(jet.transport(shear).first_layer(),jet.first_layer())
        self.assertEqual(jet.transport(shear).curvature(),jet.curvature())

    def test_nonlinear_chart_changes_are_not_offered(self):
        jet=PolynomialEnergy.cubic(1,1).hessian_jet((0,0),1)
        with self.assertRaises(ValueError):jet.transport(((1,2),(2,4)))
        with self.assertRaises(TypeError):jet.transport(((1.0,0),(0,1)))

    def test_ghost_energy_keeps_every_reading_and_changes_the_field_elsewhere(self):
        energy=PolynomialEnergy.cubic(3,-5);reader=Reader(energy);learned=learn_jet(reader,(0,0))
        ghost=ghost_energy(energy,list(reader.record),scale=Q(1,1000))
        for point,reading in reader.record.items():self.assertEqual(ghost.hessian(point),reading)
        twin=learn_jet(Reader(ghost),(0,0))
        self.assertEqual(twin['status'],learned['status']);self.assertEqual(twin['jet'],learned['jet'])
        elsewhere=(Q(1,41),Q(-1,43))
        self.assertNotEqual(ghost.hessian_jet(elsewhere,1),energy.hessian_jet(elsewhere,1))
        self.assertNotEqual(ghost.curvature(elsewhere),energy.curvature(elsewhere))
        self.assertFalse(learned['certificate'])

    def test_reader_counts_and_fails_closed(self):
        reader=Reader(PolynomialEnergy.cubic(1,1),max_readings=4)
        for k in range(4):reader.read((k,0))
        reader.read((0,0))   # repeat is served from the record
        self.assertEqual((reader.readings,reader.requests),(4,5))
        with self.assertRaises(ResourceLimit):reader.read((9,9))
        with self.assertRaises(TypeError):Reader(object())
        with self.assertRaises(TypeError):PolynomialEnergy({(1,0):0.5})
        with self.assertRaises(ValueError):Jet((0,0),{(1,0):(1,0,0)})

    def test_existing_frozen_model_scores_one_on_jets_read_from_readings_in_its_own_chart(self):
        correct=0;cases=0
        for u,v in product([s*m for m in (1,3,5,7) for s in (-1,1)],repeat=2):
            energy=PolynomialEnergy.cubic(u,v);result=learn_jet(Reader(energy),(0,0))
            self.assertEqual(first_layer_steps(result['jet']),(16+2*u,16+2*v))
            predicted,_=classify_first_layer(result['jet']);cases+=1;correct+=predicted==int(Q(u*v,324)<0)
        self.assertEqual((cases,correct),(64,64))
        self.assertEqual(EXISTING_FIRST_LAYER_MODEL['phase_steps'],(32,0,0,32,0))

    def test_existing_model_loses_accuracy_in_a_sheared_chart_while_the_invariant_does_not(self):
        shear=((1,1),(0,1));correct=invariant=cases=0
        for u,v in product([s*m for m in (1,3,5,7) for s in (-1,1)],repeat=2):
            jet=PolynomialEnergy.cubic(u,v).hessian_jet((0,0),1).transport(shear);label=int(Q(u*v,324)<0)
            try:predicted,_=classify_first_layer(jet)
            except ValueError:continue
            cases+=1;correct+=predicted==label;invariant+=int(jet.curvature()<0)==label
        self.assertEqual(cases,58);self.assertEqual(correct,38);self.assertEqual(invariant,58)

    def test_parity_classifier_matches_real_rotation_arithmetic(self):
        # RY(a) RY(b) ... with CNOT parity: compare against an independent real-amplitude evaluation.
        from math import cos,sin,pi
        import itertools
        def ry(theta):c,s=cos(theta/2),sin(theta/2);return ((c,-s),(s,c))
        for features,params in (((20,12),(32,0,0,32,0)),((0,32),(8,16,24,40,56)),((33,7),(1,2,3,4,5))):
            amps={0:1.0}
            def apply(amps,q,m):
                out={}
                for ket,a in amps.items():
                    bit=(ket>>q)&1;base=ket&~(1<<q)
                    for r in (0,1):
                        if m[r][bit]:out[base|(r<<q)]=out.get(base|(r<<q),0)+m[r][bit]*a
                return out
            for q,step in enumerate(features):amps=apply(amps,q,ry(step*pi/32))
            for q,step in enumerate(params[:4]):amps=apply(amps,q,ry(step*pi/32))
            for a,b in ((0,2),(1,2),(2,3)):amps={(k^(1<<b) if k>>a&1 else k):v for k,v in amps.items()}
            amps=apply(amps,3,ry(params[4]*pi/32))
            expected=sum(v*v for k,v in amps.items() if k>>3&1)
            exact=parity_classifier(features,params);low,high=exact.real_bounds(30)
            self.assertLessEqual(float(low),expected+1e-9);self.assertGreaterEqual(float(high),expected-1e-9)

    def test_one_query_reads_every_linear_layer_exactly(self):
        for bits,n in ((3,1),(3,2),(2,3)):
            M=1<<bits
            for layer in product(range(M),repeat=n):
                distribution,stats=read_linear_layer(layer,bits)
                self.assertEqual({k:v for k,v in distribution.items() if v},{layer:distribution[layer]})
                self.assertEqual(distribution[layer],distribution[layer].__class__(1))
                self.assertEqual(stats['peak_branches'],M**n)
        circuit=linear_phase_circuit((5,2),3)
        self.assertEqual(sum(1 for name,_ in circuit.operations if name=='h'),12)   # 6 preparation + 6 QFT Hadamards

    def test_quadratic_layer_is_not_read_by_the_single_query_circuit(self):
        for bits in (2,3):
            M=1<<bits
            for a in range(1,M):
                for b in range(M):
                    distribution=quadratic_phase_distribution(a,b,bits);F=next(iter(distribution.values())).__class__
                    if a==M//2:   # a x**2 = a x mod M because x**2-x is even: a linear layer in disguise
                        self.assertEqual({k:v for k,v in distribution.items() if v},{(a+b)%M:F(1)},(a,b,bits));continue
                    self.assertTrue(all((F(1)-p).real_sign()>0 for p in distribution.values()),(a,b,bits))
            for b in range(M):   # a=0 is a linear layer again and is read exactly
                distribution=quadratic_phase_distribution(0,b,bits)
                self.assertEqual({k:v for k,v in distribution.items() if v},{b:distribution[b]})

    def test_layer_entries_outside_the_register_are_rejected(self):
        with self.assertRaises(ValueError):linear_phase_circuit((4,),2)
        with self.assertRaises(ValueError):linear_phase_circuit((),3)
        with self.assertRaises(ValueError):quadratic_phase_distribution(8,0,3)


if __name__=='__main__':unittest.main()
