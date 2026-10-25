from fractions import Fraction as Q
from itertools import product
import random
import unittest

from native_relational_qc.compact import ResourceLimit
from native_relational_qc.enclosure_learner import (EnclosureReader,InconsistentEnclosure,Interval,JetEnclosure,certification_threshold,certify_sign,
    check_enclosure,choose_design,count_roots,cubic_form_numerator,curvature_enclosure,curvature_from_entries,curvature_numerator,design_inverse,
    design_spreads,fit_jet_enclosure,first_layer_width_factor,integrability_defects,learn_jet_enclosure,numerator_determinant,numerator_ranges,
    reading_corner_range,smallest_positive_root,sturm_sequence,tolerance_bracket,width_factors)
from native_relational_qc.hessian_metric import (christoffel,energy_from_jet,gaussian_curvature_brioschi,gaussian_curvature_riemann,
    jacobian,transport_chart)
from native_relational_qc.jet_readings import Jet,PolynomialEnergy,Reader,default_candidates,fit_jet,ghost_energy,learn_jet,poly_diff,poly_eval,poly_substitute
from native_relational_qc.layer_queries import (canonical,classical_complexity,classical_lower_bound,classical_reader,count_functions,evaluate,increment,
    nonadaptive_points,quadratic_oracle,read_quadratic_layer,same_function,shift_blind_pair,shifted_row_circuit,table)
from native_relational_qc.phase_backend import PowerPhaseCircuit,prepare


def random_energy(rng,degree):
    return PolynomialEnergy({(i,j):Q(rng.randint(-6,6),rng.randint(1,4)) for i in range(degree+1) for j in range(degree+1-i)}
                            |{(2,0):Q(3),(0,2):Q(4),(1,1):Q(1,2)})


def gradient(energy,point):return tuple(poly_eval(poly_diff(energy.coefficients,l),point) for l in range(2))


class HessianMetricTests(unittest.TestCase):
    def test_selected_curvature_equals_gaussian_curvature_two_ways(self):
        rng=random.Random(21);cases=0
        for _ in range(40):
            energy=random_energy(rng,rng.choice((3,4,5,6)));point=(Q(rng.randint(-2,2),5),Q(rng.randint(-2,2),7))
            try:kappa=energy.curvature(point)
            except ValueError:continue
            self.assertEqual(kappa,gaussian_curvature_riemann(energy,point))
            self.assertEqual(kappa,gaussian_curvature_brioschi(energy,point));cases+=1
        self.assertGreaterEqual(cases,25)
        for u,v in ((3,-5),(1,1),(-7,7)):
            self.assertEqual(gaussian_curvature_riemann(PolynomialEnergy.cubic(u,v),(0,0)),Q(u*v,324))

    def test_christoffel_symbols_are_the_selected_connection(self):
        rng=random.Random(4)
        for _ in range(10):
            energy=random_energy(rng,4);point=(Q(1,3),Q(-1,5))
            try:G=christoffel(energy,point)
            except ValueError:continue
            jet=energy.hessian_jet(point,1);H=jet.hessian();Hs,Hv=jet.first_layer()
            det=H[0]*H[2]-H[1]**2;inv=((H[2]/det,-H[1]/det),(-H[1]/det,H[0]/det))
            for i,layer in enumerate((Hs,Hv)):
                L=((layer[0],layer[1]),(layer[1],layer[2]))
                A=tuple(tuple(sum(inv[k][l]*L[l][j] for l in range(2))/2 for j in range(2)) for k in range(2))
                for k in range(2):
                    for j in range(2):self.assertEqual(G[k][i][j],A[k][j])

    def test_nonlinear_chart_transport_matches_recomposition_and_needs_the_gradient(self):
        rng=random.Random(9)
        chart=({(1,0):Q(1),(0,2):Q(1,2)},{(0,1):Q(1)})            # phi(s',v') = (s'+v'^2/2, v'), phi(0)=0
        energy=PolynomialEnergy.cubic(3,-5);jet=energy.hessian_jet((0,0),2)
        moved,grad=transport_chart(jet,(10,-10),chart,(0,0))
        recomposed=PolynomialEnergy(poly_substitute(energy.coefficients,chart[0],chart[1]))
        self.assertEqual(moved,recomposed.hessian_jet((0,0),2));self.assertEqual(grad,(Q(10),Q(-10)))
        self.assertEqual(moved.curvature(),Q(-22,841));self.assertNotEqual(moved.curvature(),jet.curvature())
        other,_=transport_chart(jet,(0,0),chart,(0,0))                # same Hessian field, different gradient
        self.assertNotEqual(other,moved);self.assertEqual(other.curvature(),Q(-7,81))
        for _ in range(6):                                            # general base, quadratic chart
            energy=random_energy(rng,4);base=(Q(1,3),Q(-1,2));new_base=(Q(1,2),Q(1,2))
            chart=({(1,0):Q(1),(2,0):Q(1,4),(1,1):Q(1,3),(0,0):Q(1,3)-Q(1,2)-Q(1,16)-Q(1,12)},{(0,1):Q(1),(0,2):Q(-1,5),(0,0):Q(-1,2)-Q(1,2)+Q(1,20)})
            jet=energy.hessian_jet(base,2);moved,grad=transport_chart(jet,gradient(energy,base),chart,new_base)
            recomposed=PolynomialEnergy(poly_substitute(energy.coefficients,chart[0],chart[1]))
            self.assertEqual(moved,recomposed.hessian_jet(new_base,2));self.assertEqual(grad,gradient(recomposed,new_base))

    def test_affine_chart_transport_agrees_with_jet_transport_and_ignores_the_gradient(self):
        energy=PolynomialEnergy.cubic(2,7);jet=energy.hessian_jet((0,0),2);A=((2,1),(-1,3))
        chart=({(1,0):Q(2),(0,1):Q(1)},{(1,0):Q(-1),(0,1):Q(3)})
        one,_=transport_chart(jet,(10,-10),chart,(0,0));two,_=transport_chart(jet,(0,99),chart,(0,0))
        self.assertEqual(one,jet.transport(A));self.assertEqual(two,one)
        self.assertEqual(jacobian(chart,(0,0)),((Q(2),Q(1)),(Q(-1),Q(3))))

    def test_non_integrable_jets_and_bad_charts_are_refused(self):
        with self.assertRaises(ValueError):energy_from_jet(Jet((0,0),{(0,0):(2,1,5),(1,0):(1,0,0),(0,1):(0,1,0)}),(0,0))
        jet=PolynomialEnergy.cubic(1,1).hessian_jet((0,0),1)
        with self.assertRaises(ValueError):transport_chart(jet,(10,-10),({(1,0):Q(1),(0,0):Q(1)},{(0,1):Q(1)}),(0,0))   # does not map base to base
        with self.assertRaises(ValueError):transport_chart(jet,(10,-10),({(2,0):Q(1)},{(0,1):Q(1)}),(0,0))              # singular Jacobian
        with self.assertRaises(ValueError):gaussian_curvature_brioschi(PolynomialEnergy({(2,0):Q(-1),(0,2):Q(1)}),(0,0))

    def test_sign_of_kappa_can_change_under_a_nonlinear_chart(self):
        energy=PolynomialEnergy.cubic(1,1);jet=energy.hessian_jet((0,0),1)
        self.assertEqual(jet.curvature(),Q(1,324))
        chart=({(1,0):Q(1)},{(0,1):Q(1),(0,2):Q(-1,4)})               # phi(s',v') = (s', v' - v'^2/4)
        moved,_=transport_chart(jet,(10,-10),chart,(0,0))
        self.assertEqual(moved.hessian(),(Q(2),Q(1),Q(10)))             # H' = H + (d_v U) Hess(phi_v) = H + (-10)(-1/2) e22
        self.assertEqual(moved.curvature(),Q(-1,1444))
        recomposed=PolynomialEnergy(poly_substitute(energy.coefficients,chart[0],chart[1]))
        self.assertEqual(recomposed.curvature((0,0)),Q(-1,1444))


    def test_any_sign_at_a_critical_base_and_the_order_of_phi_needed(self):
        zero=PolynomialEnergy({k:v for k,v in PolynomialEnergy.cubic(3,-5).coefficients.items() if sum(k)>=2})
        self.assertEqual(transport_chart(zero.hessian_jet((0,0),1),(0,0),({(1,0):Q(1),(0,2):Q(2)},{(0,1):Q(1)}),(0,0))[0].curvature(),Q(29,324))
        moved,_=transport_chart(PolynomialEnergy.cubic(3,-5).hessian_jet((0,0),1),(10,-10),({(1,0):Q(1),(1,1):Q(-1,5)},{(0,1):Q(1)}),(0,0))
        self.assertEqual((moved.hessian(),moved.curvature()),((Q(2),Q(-1),Q(5)),Q(421,8100)))
        flat=PolynomialEnergy({(2,0):Q(1),(1,1):Q(1),(0,2):Q(5,2)})
        self.assertEqual(transport_chart(flat.hessian_jet((0,0),1),(0,0),({(1,0):Q(1),(0,2):Q(1)},{(0,1):Q(1)}),(0,0))[0].curvature(),Q(8,81))
        for c in (Q(1,2),Q(-1,5),Q(2),Q(1,10)):
            k=transport_chart(PolynomialEnergy.cubic(3,-5).hessian_jet((0,0),1),(10,-10),({(1,0):Q(1),(0,2):c},{(0,1):Q(1)}),(0,0))[0].curvature()
            self.assertEqual(k,(-208*c*c-42*c-15)/(4*(9+40*c)**2))
        self.assertLess(42*42-4*208*15,0)
        # T' = T + S(Q) with H' = H at a critical base, for a random quadratic chart.
        rng=random.Random(31)
        for _ in range(5):
            critical=PolynomialEnergy({k:v for k,v in random_energy(rng,4).coefficients.items() if sum(k)>=2});jet=critical.hessian_jet((0,0),1);H=jet.hessian()
            q=[[Q(rng.randint(-3,3),4) for _ in range(3)] for _ in range(2)]
            chart=({(1,0):Q(1),(2,0):q[0][0],(1,1):q[0][1],(0,2):q[0][2]},{(0,1):Q(1),(2,0):q[1][0],(1,1):q[1][1],(0,2):q[1][2]})
            moved,_=transport_chart(jet,(0,0),chart,(0,0));Hs,Hv=jet.first_layer();T=(Hs[0],Hs[1],Hs[2],Hv[2])
            Qm=[((2*q[k][0],q[k][1]),(q[k][1],2*q[k][2])) for k in range(2)];Hm=((H[0],H[1]),(H[1],H[2]))
            def S(a,b,c):return sum(Hm[k][c]*Qm[k][a][b]+Hm[k][b]*Qm[k][a][c]+Hm[k][a]*Qm[k][b][c] for k in range(2))
            Ms,Mv=moved.first_layer()
            self.assertEqual(moved.hessian(),H);self.assertEqual((Ms[0],Ms[1],Ms[2],Mv[2]),(T[0]+S(0,0,0),T[1]+S(0,0,1),T[2]+S(0,1,1),T[3]+S(1,1,1)))
        for d in (0,1,2):   # only the order-(d+2) term of phi, times the gradient, reaches the order-d jet
            base_jet=PolynomialEnergy.cubic(3,-5).hessian_jet((0,0),d)
            plain,_=transport_chart(base_jet,(10,-10),({(1,0):Q(1)},{(0,1):Q(1)}),(0,0))
            bumped,_=transport_chart(base_jet,(10,-10),({(1,0):Q(1),(0,d+2):Q(1,7)},{(0,1):Q(1)}),(0,0))
            for k in plain.coefficients:
                diff=tuple(x-y for x,y in zip(bumped.coefficients[k],plain.coefficients[k]))
                self.assertEqual(diff,(0,0,Q(10*(d+2)*(d+1),7)) if k==(0,d) else (0,0,0))
            same,_=transport_chart(base_jet,(0,0),({(1,0):Q(1),(0,d+2):Q(1,7)},{(0,1):Q(1)}),(0,0))
            self.assertEqual(same,transport_chart(base_jet,(0,0),({(1,0):Q(1)},{(0,1):Q(1)}),(0,0))[0])


    def test_chart_with_zero_hessian_at_the_base_still_moves_kappa_through_its_third_derivatives(self):
        # J6(d'): phi = (s' + t v'^3, v') has J(0) = I and Hess(phi^k)(0) = 0, so H'(0) = H exactly; the first layer still
        # changes by (gradient) x (third derivatives of phi), and kappa' = (-15 + 180 t)/324 for cubic(3,-5) with gradient (10,-10).
        energy=PolynomialEnergy.cubic(3,-5);jet=energy.hessian_jet((0,0),1)
        for t,expected in ((Q(1,7),Q(25,756)),(Q(1,12),Q(0)),(Q(-1,3),Q(-25,108))):
            out,_=transport_chart(jet,(10,-10),({(1,0):Q(1),(0,3):t},{(0,1):Q(1)}),(0,0))
            self.assertEqual(out.hessian(),jet.hessian());self.assertEqual(out.first_layer()[1],(Q(0),Q(0),Q(-5)+Q(60)*t))
            self.assertEqual(out.curvature(),expected);self.assertEqual(expected,(-15+180*t)/324)
        self.assertLess(jet.curvature(),0);self.assertGreater(Q(25,756),0)                  # the sign flips at t = 1/7
        unchanged,_=transport_chart(jet,(0,0),({(1,0):Q(1),(0,3):Q(1,7)},{(0,1):Q(1)}),(0,0))
        self.assertEqual(unchanged.coefficients,jet.coefficients)                               # zero gradient: no effect at order one

    def test_some_nonlinear_charts_leave_the_order_one_jet_unchanged_at_a_critical_base(self):
        # J6(d) remark: S has rank 4 on the six quadratic chart coefficients, so a two-parameter family of genuinely
        # nonlinear quadratic charts leaves the order-one jet and kappa unchanged when the gradient vanishes.
        energy=PolynomialEnergy.cubic(3,-5);jet=energy.hessian_jet((0,0),1)
        charts=(({(1,0):Q(1),(2,0):Q(-1),(1,1):Q(-5)},{(0,1):Q(1),(2,0):Q(2),(1,1):Q(1)}),
                ({(1,0):Q(1),(2,0):Q(1),(1,1):Q(9,2),(0,2):Q(-5,2)},{(0,1):Q(1),(2,0):Q(-2),(0,2):Q(1,2)}))
        for chart in charts:
            out,gradient=transport_chart(jet,(0,0),chart,(0,0))
            self.assertEqual(out.coefficients,jet.coefficients);self.assertEqual(out.curvature(),Q(-5,108));self.assertEqual(gradient,(Q(0),Q(0)))
            moved,_=transport_chart(jet,(10,-10),chart,(0,0))                                  # with a gradient the same chart does act
            self.assertNotEqual(moved.coefficients,jet.coefficients)


class EnclosureLearnerTests(unittest.TestCase):
    def test_interval_arithmetic_and_closed_form(self):
        a=Interval(Q(-1),Q(2));b=Interval(Q(1,2),Q(3))
        self.assertEqual((a*b),Interval(Q(-3),Q(6)));self.assertEqual(a.square(),Interval(Q(0),Q(4)));self.assertEqual(b.reciprocal(),Interval(Q(1,3),Q(2)))
        with self.assertRaises(ZeroDivisionError):a.reciprocal()
        with self.assertRaises(ValueError):Interval(Q(1),Q(0))
        rng=random.Random(2);n=0
        for _ in range(20):
            energy=random_energy(rng,rng.choice((3,4,5)));point=(Q(rng.randint(-2,2),5),Q(rng.randint(-2,2),7))
            try:kappa=energy.curvature(point)
            except ValueError:continue
            jet=energy.hessian_jet(point,1);self.assertEqual(curvature_from_entries(jet.hessian(),*jet.first_layer()),kappa);n+=1
        self.assertGreaterEqual(n,12)

    def test_enclosure_contains_every_admissible_interpolant_and_is_tight(self):
        energy=PolynomialEnergy.cubic(3,-5);base=(0,0);design=[(Q(-3,4),Q(-3,4)),(Q(3,4),Q(3,4)),(Q(-3,4),Q(3,4))]
        w=Q(1,10);enclosure=fit_jet_enclosure(base,[(p,EnclosureReader(energy,w).read(p)) for p in design],1)
        rng=random.Random(5)
        for _ in range(100):
            readings=[(p,tuple(x+Q(rng.randint(-10,10),100) for x in energy.hessian(p))) for p in design]
            self.assertTrue(enclosure.contains(fit_jet(base,readings,1)))
        factors=width_factors(base,design,1)
        for key,triple in enclosure.coefficients.items():
            for c in triple:self.assertEqual(c.width,2*w*factors[key])
        # Tightness: the extreme of each coefficient is attained by choosing each reading at a bound.
        mono_rows=[(key,row) for key,row in zip(*__import__('native_relational_qc.enclosure_learner',fromlist=['design_inverse']).design_inverse(base,design,1))]
        for key,row in mono_rows:
            top=[(p,tuple(x+(w if coefficient>=0 else -w) for x in energy.hessian(p))) for coefficient,p in zip(row,design)]
            self.assertEqual(fit_jet(base,top,1).coefficients[key][0],enclosure.coefficients[key][0].hi)

    def test_zero_width_reproduces_exact_and_wide_readings_withhold_the_sign(self):
        energy=PolynomialEnergy.cubic(3,-5)
        exact=learn_jet_enclosure(EnclosureReader(energy,0),(0,0))
        self.assertEqual(exact['status'],'sign_certified');self.assertEqual(exact['curvature'],Interval.point(Q(-5,108)))
        narrow=learn_jet_enclosure(EnclosureReader(energy,Q(1,100)),(0,0))
        self.assertEqual(narrow['status'],'sign_certified');self.assertTrue(Q(-5,108) in narrow['curvature']);self.assertEqual(narrow['sign'],-1)
        wide=learn_jet_enclosure(EnclosureReader(energy,Q(3,5)),(0,0))             # the exact threshold of cubic(3,-5) on this design is 15/29
        self.assertEqual(wide['status'],'sign_not_certified');self.assertTrue(Q(-5,108) in wide['curvature'])
        huge=learn_jet_enclosure(EnclosureReader(energy,Q(3)),(0,0))
        self.assertEqual(huge['status'],'positivity_not_certified')

    def test_width_factor_scales_inversely_with_design_radius_and_swaps_lower_it(self):
        base=(0,0)
        for r in (Q(1,4),Q(1,2),Q(3,4),Q(3,2)):
            design=[(-r,-r),(r,r),(-r,r)]
            self.assertEqual(first_layer_width_factor(base,design),Q(2)/r)
        candidates=default_candidates(base,radius=6,step=Q(1,4))
        design,value,converged=choose_design(base,candidates,1)
        self.assertLessEqual(value,first_layer_width_factor(base,[(Q(-3,4),Q(-3,4)),(Q(3,4),Q(3,4)),(Q(-3,4),Q(3,4))]));self.assertTrue(converged)
        with self.assertRaises(ValueError):width_factors(base,[(0,0),(1,0),(2,0)],1)

    def test_curvature_enclosure_is_valid_for_integrable_points_of_the_box(self):
        rng=random.Random(8);energy=PolynomialEnergy.cubic(2,-6);jet=energy.hessian_jet((0,0),1)
        for _ in range(30):
            w=Q(rng.randint(1,20),100)
            box={k:tuple(Interval.around(x,w) for x in v) for k,v in jet.coefficients.items()}
            enclosure=JetEnclosure((0,0),box);kappa=curvature_enclosure(enclosure)
            self.assertTrue(jet.curvature() in kappa)
            for _ in range(20):   # any integrable point of the box has its curvature inside the enclosure
                h=tuple(x+Q(rng.randint(-100,100),100)*w for x in jet.hessian())
                T=tuple(x+Q(rng.randint(-100,100),100)*w for x in (*jet.first_layer()[0],jet.first_layer()[1][2]))
                self.assertTrue(curvature_from_entries(h,T[:3],T[1:]) in kappa)
            loose=curvature_enclosure(enclosure,corners=False)
            self.assertLessEqual(loose.lo,kappa.lo);self.assertGreaterEqual(loose.hi,kappa.hi)
        # Perturbed energies whose readings stay admissible have their exact curvature inside the enclosure.
        design=[(Q(-3,4),Q(-3,4)),(Q(3,4),Q(3,4)),(Q(-3,4),Q(3,4))];w=Q(1,20)
        enclosure=fit_jet_enclosure((0,0),[(p,EnclosureReader(energy,w).read(p)) for p in design],1);kappa=curvature_enclosure(enclosure)
        admissible=rejected=0
        for _ in range(200):
            perturbed=PolynomialEnergy(dict(energy.coefficients)|{(i,j):energy.coefficients.get((i,j),Q(0))+Q(rng.randint(-9,9),1000) for i in range(4) for j in range(4-i) if i+j>=2})
            if all(abs(a-b)<=w for p in design for a,b in zip(perturbed.hessian(p),energy.hessian(p))):
                admissible+=1;self.assertTrue(perturbed.curvature((0,0)) in kappa)
            else:rejected+=1
        self.assertGreater(admissible,10);self.assertGreater(rejected,10)                     # the sampler reaches and crosses the reading box
        # Energies of the family whose readings sit exactly at reading-box corners (the boundary) are inside too.
        corners=0
        for pick in product((0,1),repeat=9):
            readings=[(p,tuple((enclosure.readings[q][e].lo,enclosure.readings[q][e].hi)[pick[3*q+e]] for e in range(3))) for q,p in enumerate(design)]
            try:boundary=energy_from_jet(fit_jet((0,0),readings,1),(0,0))
            except ValueError:continue                                                          # not integrable: not an energy of the family
            corners+=1;self.assertTrue(boundary.curvature((0,0)) in kappa)
        self.assertGreater(corners,0)

    def test_falsification_with_intervals_and_reader_budget(self):
        quartic=PolynomialEnergy({(2,0):Q(1),(1,1):Q(1),(0,2):Q(5,2),(4,0):Q(1)})
        result=learn_jet_enclosure(EnclosureReader(quartic,Q(1,1000)),(0,0),order=1)
        self.assertEqual(result['status'],'order_falsified');self.assertTrue(result['falsifications'])
        self.assertIsNone(result['sign']);self.assertIsNone(result['curvature']);self.assertIn('higher order',result['remedy'])
        consistent=learn_jet_enclosure(EnclosureReader(quartic,Q(1,1000)),(0,0),order=2)   # Hessian is quadratic in s: order 2 fits; kappa(0)=0 exactly
        self.assertEqual(consistent['status'],'sign_not_certified');self.assertTrue(0 in consistent['curvature']);self.assertEqual(quartic.curvature((0,0)),0)
        negative=JetEnclosure((0,0),{(0,0):(Interval(1,2),Interval.point(0),Interval(-3,-2)),(1,0):(Interval.point(0),)*3,(0,1):(Interval.point(0),)*3})
        with self.assertRaisesRegex(ValueError,'positivity'):curvature_enclosure(negative)
        reader=EnclosureReader(quartic,Q(1,10),max_readings=2);reader.read((0,0));reader.read((1,0))
        with self.assertRaises(ResourceLimit):reader.read((2,0))
        with self.assertRaises(TypeError):learn_jet_enclosure(Reader(quartic),(0,0))

    def test_tolerance_bracket_on_the_test_grid(self):
        cases=[PolynomialEnergy.cubic(u,v) for u,v in product([s*m for m in (1,3,5,7) for s in (-1,1)],repeat=2)]
        design=[(Q(-3,4),Q(-3,4)),(Q(3,4),Q(3,4)),(Q(-3,4),Q(3,4))]
        ok,fail=tolerance_bracket(cases,(0,0),design,steps=12)
        self.assertLess(ok,fail);self.assertGreater(ok,Q(1,20));self.assertLess(fail,Q(1,10))


    def test_cubic_form_route_tightens_asymmetric_enclosures_and_stays_valid(self):
        rng=random.Random(77);base=(0,0);tightened=0
        for _ in range(60):
            u,v=rng.choice([s*m for m in (1,3,5,7) for s in (-1,1)]),rng.choice([s*m for m in (1,3,5,7) for s in (-1,1)]);energy=PolynomialEnergy.cubic(u,v)
            points=[(Q(rng.randint(-6,6),8),Q(rng.randint(-6,6),8)) for _ in range(3)];widths=tuple(Q(rng.randint(1,8),200) for _ in range(3))
            try:enclosure=fit_jet_enclosure(base,[(p,EnclosureReader(energy,lambda q,w=widths:w).read(p)) for p in points],1)
            except ValueError:continue
            try:both=curvature_enclosure(enclosure);nine=curvature_enclosure(enclosure,intersect=False)
            except ValueError:continue
            self.assertTrue(nine.lo<=both.lo and both.hi<=nine.hi);self.assertTrue(energy.curvature(base) in both)
            if both.lo>nine.lo or both.hi<nine.hi:tightened+=1
        self.assertGreater(tightened,10)
        jet=PolynomialEnergy.cubic(3,-5).hessian_jet((0,0),1);Hs,Hv=jet.first_layer();h=jet.hessian();det=h[0]*h[2]-h[1]**2
        self.assertEqual(cubic_form_numerator(h,(Hs[0],Hs[1],Hs[2],Hv[2]))/(4*det*det),jet.curvature())

    def test_integrability_defect_falsifies_the_order_instead_of_positivity(self):
        skew=PolynomialEnergy({(2,0):Q(1),(1,1):Q(1),(0,2):Q(5,2),(3,1):Q(1,10)})
        design=[(Q(-3,4),Q(-3,4)),(Q(3,4),Q(3,4)),(Q(-3,4),Q(3,4))]
        enclosure=fit_jet_enclosure((0,0),[(p,EnclosureReader(skew,Q(1,100)).read(p)) for p in design],1)
        self.assertEqual([d['derivative'] for d in integrability_defects(enclosure)],['U_ssv'])
        with self.assertRaises(InconsistentEnclosure):curvature_enclosure(enclosure)
        result=learn_jet_enclosure(EnclosureReader(skew,Q(1,100)),(0,0),checks=0)
        self.assertEqual(result['status'],'order_falsified');self.assertTrue(any('integrability' in f for f in result['falsifications']))

    def test_certificate_is_conditional_on_the_declared_family(self):
        energy=PolynomialEnergy.cubic(3,-5);reader=EnclosureReader(energy,Q(1,100));learned=learn_jet_enclosure(reader,(0,0))
        ghost=ghost_energy(energy,list(reader.record),scale=5,directions=((1,0),(0,1),(2,1),(1,2),(3,1),(1,3)))
        for point in reader.record:self.assertEqual(ghost.hessian(point),energy.hessian(point))
        twin=learn_jet_enclosure(EnclosureReader(ghost,Q(1,100)),(0,0))
        self.assertEqual((twin['status'],twin['curvature']),(learned['status'],learned['curvature']))
        self.assertGreater(ghost.curvature((0,0)),0);self.assertLess(energy.curvature((0,0)),0)
        self.assertFalse(ghost.curvature((0,0)) in twin['curvature']);self.assertIn('conditional',twin['hypothesis'])


    def test_numerator_determinant_form_and_the_three_numerator_ranges(self):
        # E3(a): N = det[[a,b,c],[p],[r]] equals the commutator form; for a three-point design N = det(Hmat)/det D.
        rng=random.Random(11);base=(0,0)
        for _ in range(100):
            h,hs,hv=([Q(rng.randint(-9,9),rng.randint(1,5)) for _ in range(3)] for _ in range(3))
            self.assertEqual(numerator_determinant(h,hs,hv),curvature_numerator(h,hs,hv))
        design=[(Q(-3,4),Q(-3,4)),(Q(3,4),Q(3,4)),(Q(-3,4),Q(3,4))]
        mono,inverse=design_inverse(base,design,1);detD=Q(9,4)
        for _ in range(20):
            Hm=[[Q(rng.randint(-9,9),rng.randint(1,4)) for _ in range(3)] for _ in range(3)]
            jet=fit_jet(base,list(zip(design,[tuple(r) for r in Hm])),1)
            det=Hm[0][0]*(Hm[1][1]*Hm[2][2]-Hm[1][2]*Hm[2][1])-Hm[0][1]*(Hm[1][0]*Hm[2][2]-Hm[1][2]*Hm[2][0])+Hm[0][2]*(Hm[1][0]*Hm[2][1]-Hm[1][1]*Hm[2][0])
            self.assertEqual(numerator_determinant(jet.hessian(),*jet.first_layer()),det/detD)
        # The three ranges at w = 1/16 for cubic(1,1): natural >= coefficient corners >= reading corners (exact).
        energy=PolynomialEnergy.cubic(1,1);w=Q(1,16)
        enclosure=fit_jet_enclosure(base,[(p,EnclosureReader(energy,w).read(p)) for p in design],1)
        ranges=numerator_ranges(enclosure)
        self.assertEqual(ranges['coefficient_corners'],Interval(Q(-371,192),Q(-3,16)));self.assertEqual(ranges['reading_corners'],Interval(Q(-3763,2304),Q(-11,24)))
        self.assertLessEqual(ranges['natural'].lo,ranges['coefficient_corners'].lo);self.assertGreaterEqual(ranges['natural'].hi,ranges['coefficient_corners'].hi)
        self.assertLess(ranges['coefficient_corners'].lo,ranges['reading_corners'].lo)      # the coefficient-box corner is not admissible
        attained=set()
        for pick in product((0,1),repeat=9):
            readings=[(p,tuple((enclosure.readings[q][e].lo,enclosure.readings[q][e].hi)[pick[3*q+e]] for e in range(3))) for q,p in enumerate(design)]
            jet=fit_jet(base,readings,1);value=numerator_determinant(jet.hessian(),*jet.first_layer())
            self.assertTrue(value in ranges['reading_corners']);attained.add(value)
        self.assertIn(ranges['reading_corners'].lo,attained);self.assertIn(ranges['reading_corners'].hi,attained)
        # The admissible interpolant with N = -371/192 does not exist: the unique preimage of the corner leaves the box.
        corner=(Q(33,16),Q(13,12),Q(1,12))                                                     # (a, p1, r1) at their upper bounds
        D=[[Q(1),p[0],p[1]] for p in design];h11=[sum(D[q][k]*corner[k] for k in range(3)) for q in range(3)]
        self.assertEqual(h11,[Q(19,16),Q(47,16),Q(21,16)]);self.assertFalse(h11[1] in enclosure.readings[1][0])
        self.assertEqual(curvature_enclosure(enclosure,intersect=False),ranges["reading_corners"]*Interval(Q(-1,4)/Q(135,16)**2,Q(-1,4)/Q(153,16)**2))
        without=JetEnclosure(base,enclosure.coefficients);self.assertIsNone(reading_corner_range(without))
        self.assertEqual(curvature_enclosure(without,intersect=False),curvature_enclosure(enclosure,intersect=False,readings=False))

    def test_closed_form_equals_kappa_where_its_E_and_G_terms_do_not_vanish(self):
        # cubic(u,v) has U_ssv = U_svv = 0, so the E- and G-terms of the J5 closed form vanish on it; random energies exercise them.
        rng=random.Random(99);n=exercised=0
        while n<40:
            energy=random_energy(rng,rng.choice((3,4,5)));point=(Q(rng.randint(-2,2),5),Q(rng.randint(-2,2),7))
            try:kappa=energy.curvature(point)
            except ValueError:continue
            jet=energy.hessian_jet(point,1);E,F,G=jet.hessian();Hs,Hv=jet.first_layer();T=(Hs[0],Hs[1],Hs[2],Hv[2]);det=E*G-F*F
            self.assertEqual(cubic_form_numerator((E,F,G),T)/(4*det*det),kappa)
            if G*(T[1]*T[1]-T[0]*T[2])!=0 and E*(T[2]*T[2]-T[1]*T[3])!=0:exercised+=1
            n+=1
        self.assertGreaterEqual(exercised,30)
        energy=random_energy(random.Random(5),4);point=(Q(1,5),Q(-1,7));jet=energy.hessian_jet(point,1)
        box={k:tuple(Interval.point(x) for x in v) for k,v in jet.coefficients.items()}
        self.assertEqual(curvature_enclosure(JetEnclosure(point,box)),Interval.point(jet.curvature()))
        # A cubic energy with all four third derivatives nonzero is still in the declared family: its enclosure certificate is valid.
        mixed=PolynomialEnergy({(2,0):Q(1),(1,1):Q(1,2),(0,2):Q(5,2),(3,0):Q(1,2),(2,1):Q(-1,3),(1,2):Q(2,5),(0,3):Q(-1,6)});base=(0,0)
        result=learn_jet_enclosure(EnclosureReader(mixed,Q(1,200)),base)
        self.assertEqual(result['status'],'sign_certified');self.assertTrue(mixed.curvature(base) in result['curvature']);self.assertEqual(result['sign'],1 if mixed.curvature(base)>0 else -1)

    def test_swap_descent_lowers_the_factor_below_the_greedy_start_to_a_local_minimum(self):
        from itertools import combinations
        base=(0,0);cands=[(Q(-5,4),Q(-2)),(Q(-3,4),Q(0)),(Q(0),Q(1,4)),(Q(1,4),Q(1)),(Q(3,2),Q(1,2)),(Q(7,4),Q(7,4)),(Q(2),Q(-3,4))]
        greedy,g,converged0=choose_design(base,cands,1,sweeps=0);swapped,s,converged=choose_design(base,cands,1,sweeps=4)
        self.assertEqual(g,first_layer_width_factor(base,greedy));self.assertEqual(s,first_layer_width_factor(base,swapped))
        self.assertEqual((g,s),(Q(224,135),Q(100,63)));self.assertLess(s,g);self.assertFalse(converged0);self.assertTrue(converged)
        def factor(t):
            try:return first_layer_width_factor(base,list(t))
            except ValueError:return None
        best=min(f for t in combinations(cands,3) for f in [factor(t)] if f is not None)
        self.assertEqual(best,Q(168,107));self.assertGreater(s,best)                             # a local minimum over swaps, not the global one
        with self.assertRaises(ValueError):choose_design(base,[(Q(0),Q(0)),(Q(1),Q(0)),(Q(2),Q(0))],1)   # collinear candidates refused

    def test_sturm_root_counting_and_the_smallest_positive_root(self):
        p=[Q(-6),Q(11),Q(-6),Q(1)]                                                              # (w-1)(w-2)(w-3)
        seq=sturm_sequence(p);self.assertEqual(count_roots(seq,Q(0),Q(4)),3);self.assertEqual(count_roots(seq,Q(0),Q(2)),2);self.assertEqual(count_roots(seq,Q(5,2),Q(4)),1)
        self.assertEqual(smallest_positive_root(p)[0],Q(1));self.assertEqual(smallest_positive_root([Q(9,4),Q(-117,4)])[0],Q(1,13))
        root,bracket=smallest_positive_root([Q(-2),Q(0),Q(1)]);self.assertIsNone(root);self.assertLess(bracket[0]**2,2);self.assertGreaterEqual(bracket[1]**2,2)
        self.assertEqual(smallest_positive_root([Q(1),Q(0),Q(1)]),(None,None));self.assertEqual(smallest_positive_root([Q(1),Q(1)]),(None,None))
        with self.assertRaises(ValueError):smallest_positive_root([Q(0),Q(1)])

    def test_certification_threshold_on_the_grid_is_exactly_one_thirteenth_and_intrinsic(self):
        # E4: sup = 1/13; the first corner to vanish is case (u,v) = (-1,1) and its interpolant is the Hessian jet of a cubic with kappa = 0.
        base=(0,0);design=[(Q(-3,4),Q(-3,4)),(Q(3,4),Q(3,4)),(Q(-3,4),Q(3,4))]
        values=[s*m for m in (1,3,5,7) for s in (-1,1)];pairs=list(product(values,repeat=2));cases=[PolynomialEnergy.cubic(u,v) for u,v in pairs]
        result=certification_threshold(cases,base,design)
        self.assertEqual((result['sup'],result['exact'],result['bracket'],result['gate_root']),(Q(1,13),True,None,Q(1)))
        witness=result['witness'];self.assertEqual(pairs[witness['case']],(-1,1));self.assertTrue(witness['integrable']);self.assertEqual(witness['kappa'],Q(0))
        self.assertEqual(witness['readings'],[(Q(147,52),Q(12,13),Q(225,52)),(Q(69,52),Q(12,13),Q(303,52)),(Q(139,52),Q(14,13),Q(295,52))])
        self.assertEqual(witness['jet'].hessian(),(Q(27,13),Q(12,13),Q(66,13)))
        self.assertEqual(witness['jet'].first_layer(),((Q(-35,39),Q(-4,39),Q(4,39)),(Q(-4,39),Q(4,39),Q(35,39))))
        self.assertEqual(energy_from_jet(witness['jet'],(0,0)).hessian_jet(base,1).coefficients,witness['jet'].coefficients)   # a genuine energy of the family
        for q,p in enumerate(design):                                                           # the witness readings are admissible at w = 1/13
            for e in range(3):self.assertLessEqual(abs(witness['readings'][q][e]-cases[witness['case']].hessian(p)[e]),Q(1,13))
        below=Q(1,13)-Q(1,1<<40)
        for (u,v),energy in zip(pairs,cases):
            sign,_=certify_sign(fit_jet_enclosure(base,[(p,EnclosureReader(energy,below).read(p)) for p in design],1))
            self.assertEqual(sign,1 if u*v>0 else -1)
        at=fit_jet_enclosure(base,[(p,EnclosureReader(cases[witness['case']],Q(1,13)).read(p)) for p in design],1)
        self.assertIsNone(certify_sign(at)[0]);self.assertTrue(Q(0) in certify_sign(at)[1])
        # Negative control: beyond the supremum the same reading pattern gives the wrong sign (true kappa is -1/324).
        beyond=Q(1,13)+Q(1,1<<20);energy=cases[witness['case']]
        readings=[(p,tuple(energy.hessian(p)[e]+beyond*witness['pattern'][3*q+e] for e in range(3))) for q,p in enumerate(design)]
        wrong=fit_jet(base,readings,1).curvature();self.assertGreater(wrong,0);self.assertLess(energy.curvature(base),0)

    def test_design_criterion_identities_lower_bound_and_the_determinant_is_not_monotone(self):
        # E2: for three points, rowsum_(1,0) = 2 Dv/|det D|, rowsum_(0,1) = 2 Ds/|det D|, rowsum_(0,0) = 1 iff the base is in the triangle.
        rng=random.Random(13);base=(0,0);inside=outside=0
        for _ in range(200):
            points=[(Q(rng.randint(-8,8),4),Q(rng.randint(-8,8),4)) for _ in range(3)]
            try:factors=width_factors(base,points,1)
            except ValueError:continue
            D=[[Q(1),p[0],p[1]] for p in points];det=D[0][0]*(D[1][1]*D[2][2]-D[1][2]*D[2][1])-D[0][1]*(D[1][0]*D[2][2]-D[1][2]*D[2][0])+D[0][2]*(D[1][0]*D[2][1]-D[1][1]*D[2][0])
            Ds,Dv=design_spreads(points)
            self.assertEqual(factors[(1,0)],2*Dv/abs(det));self.assertEqual(factors[(0,1)],2*Ds/abs(det));self.assertGreaterEqual(factors[(0,0)],1)
            self.assertGreaterEqual(factors[(1,0)],2/Ds);self.assertGreaterEqual(factors[(0,1)],2/Dv)
            lam=[Q(x) for x in design_inverse(base,points,1)[1][0]]
            if all(x>=0 for x in lam):inside+=1;self.assertEqual(factors[(0,0)],1)
            else:outside+=1;self.assertGreater(factors[(0,0)],1)
        self.assertGreater(inside,10);self.assertGreater(outside,10)
        # Lower bound 1/R on the default candidates (half-side 3/4): every three-point design has first-layer row sums >= 4/3.
        candidates=default_candidates(base);checked=0
        for _ in range(300):
            points=rng.sample(candidates,3)
            try:factors=width_factors(base,points,1)
            except ValueError:continue
            checked+=1;self.assertGreaterEqual(factors[(1,0)],Q(4,3));self.assertGreaterEqual(factors[(0,1)],Q(4,3))
        self.assertGreater(checked,250);self.assertEqual(width_factors(base,[(Q(-3,4),Q(-3,4)),(Q(3,4),Q(3,4)),(Q(-3,4),Q(3,4))],1),{(0,0):Q(1),(1,0):Q(4,3),(0,1):Q(4,3)})
        # Larger |det D| does not mean a smaller width: inside the candidate grid and in general.
        A3=[(Q(-3,4),Q(0)),(Q(3,4),Q(0)),(Q(0),Q(1,4))];B3=[(Q(-3,4),Q(-3,4)),(Q(-1,4),Q(-3,4)),(Q(0),Q(3,4))]
        self.assertEqual((width_factors(base,A3,1)[(1,0)],width_factors(base,B3,1)[(1,0)]),(Q(4,3),Q(4)))
        A=[(0,0),(2,0),(0,2)];B=[(0,0),(5,4),(4,5)]
        self.assertEqual(width_factors(base,A,1),{(0,0):Q(1),(1,0):Q(1),(0,1):Q(1)});self.assertEqual(width_factors(base,B,1),{(0,0):Q(1),(1,0):Q(10,9),(0,1):Q(10,9)})
        # A higher order on the same candidates ties (order 2) or loses (order 3) on the first layer, and widens H.
        greedy2=[(Q(-3,4),Q(-3,4)),(Q(3,4),Q(3,4)),(Q(-3,4),Q(3,4)),(Q(-3,4),Q(-1,2)),(Q(3,4),Q(-3,4)),(Q(0),Q(-3,4))]
        self.assertEqual(width_factors(base,greedy2,2),{(0,0):Q(51,10),(1,0):Q(4,3),(0,1):Q(4,3),(2,0):Q(32,9),(1,1):Q(16,9),(0,2):Q(32,5)})
        self.assertEqual([choose_design(base,candidates,order)[1] for order in (1,2,3)],[Q(8,3),Q(8,3),Q(28,3)])


class WitnessPinTests(unittest.TestCase):
    def test_recorded_witness_pins_the_current_sources(self):
        # A stale qualification2.json (regenerated before the last source edit) must fail loudly.
        import hashlib,json
        from pathlib import Path
        root=Path(__file__).resolve().parents[1];record=json.loads((root/'native_relational_qc'/'jet_readings'/'qualification2.json').read_text())
        for path,pinned in record['source_blob_sha1'].items():
            data=(root/path).read_bytes();blob=hashlib.sha1(b'blob %d\0'%len(data)+data).hexdigest()
            self.assertEqual(blob,pinned,f'{path} changed after the witness was written; rerun benchmarks/jet_readings2_audit.py')
        stable=dict(record);stable.pop('seconds')
        for row in stable['quadratic_layer']:row.pop('seconds')
        digest=hashlib.sha256(json.dumps(stable,sort_keys=True).encode()).hexdigest()
        self.assertEqual((root/'native_relational_qc'/'jet_readings'/'EXPECTED2.sha256').read_text().split()[0],digest)


class LayerQueryTests(unittest.TestCase):
    def test_function_classes_and_canonical_representatives(self):
        for bits,n in ((2,1),(3,1),(2,2)):
            count,formula=count_functions(bits,n);self.assertEqual(count,formula)
        for bits in (2,3):
            M=1<<bits
            for a,b in product(range(M),repeat=2):
                Ac,bc=canonical(((a,),),(b,),bits)
                self.assertTrue(same_function(((a,),),(b,),Ac,bc,bits));self.assertLess(Ac[0][0],M//2)
            self.assertTrue(same_function(((1,),),(0,),((1+M//2,),),(M//2,),bits))
            self.assertFalse(same_function(((1,),),(0,),((1,),),(1,),bits))
        self.assertEqual([classical_lower_bound(3,n) for n in (1,2,3,4,5)],[2,4,7,11,15])
        self.assertEqual([classical_lower_bound(2,n) for n in (1,2,3,4)],[2,4,6,9])

    def test_increment_is_a_modular_plus_one_and_oracle_phases_match_the_table(self):
        for bits in (1,2,3):
            M=1<<bits
            for x in range(M):
                c=PowerPhaseCircuit(bits,8)
                for j in range(bits):
                    if x>>j&1:c.add('x',j)
                increment(c,range(bits));state=prepare(c,max_work=100000,max_branches=8)
                self.assertEqual(list(state.amplitudes),[(x+1)%M])
                increment(c,range(bits),inverse=True);state=prepare(c,max_work=100000,max_branches=8)
                self.assertEqual(list(state.amplitudes),[x])
        A=((3,1),(1,6));b=(5,2);bits=3;M=8
        for x in product(range(M),repeat=2):
            c=PowerPhaseCircuit(6,8)
            for i in range(2):
                for j in range(bits):
                    if x[i]>>j&1:c.add('x',i*bits+j)
            quadratic_oracle(c,A,b,bits);state=prepare(c,max_work=100000,max_branches=8)
            ket,amplitude=next(iter(state.amplitudes.items()))
            self.assertEqual(amplitude,c.field.root(evaluate(A,b,bits,x)))

    def test_two_n_plus_one_queries_recover_the_class_exactly(self):
        for bits in (2,3):
            M=1<<bits
            for a,b in product(range(M),repeat=2):
                r=read_quadratic_layer(((a,),),(b,),bits)
                self.assertTrue(r['same_function'] and r['canonical_match']);self.assertEqual(r['oracle_uses'],3)
        rng=random.Random(13)
        for _ in range(6):
            a11,a12,a22,b1,b2=(rng.randrange(8) for _ in range(5))
            r=read_quadratic_layer(((a11,a12),(a12,a22)),(b1,b2),3)
            self.assertTrue(r['same_function'] and r['canonical_match']);self.assertEqual(r['oracle_uses'],5);self.assertEqual(r['classical_lower_bound'],4)
        r=read_quadratic_layer(((5,3,1),(3,2,7),(1,7,4)),(6,0,3),3)
        self.assertTrue(r['same_function']);self.assertEqual((r['oracle_uses'],r['classical_lower_bound']),(7,7))

    def test_exact_classical_complexity_is_n_n_plus_3_over_2_and_the_counting_bound_is_not_attained(self):
        # Q3(v): the nonadaptive points P0 decode every class with n(n+3)/2 readings, and at (M,n) = (4,2) no four-point set separates the classes.
        for bits,n in ((2,1),(3,1),(2,2)):
            M=1<<bits;entries=n*(n+1)//2
            for upper in product(range(M),repeat=entries):
                A=[[0]*n for _ in range(n)];k=0
                for i in range(n):
                    for j in range(i,n):A[i][j]=A[j][i]=upper[k];k+=1
                for b in product(range(M),repeat=n):
                    r=classical_reader(tuple(map(tuple,A)),b,bits)
                    self.assertTrue(r['same_function'] and r['canonical_match']);self.assertEqual(r['readings'],classical_complexity(bits,n))
        self.assertEqual([classical_complexity(b,n) for b,n in ((2,1),(3,1),(2,2),(3,2),(2,3),(3,3),(3,4),(1,3))],[2,2,5,5,9,9,14,3])
        self.assertEqual(len(nonadaptive_points(3)),9)
        bits,n=2,2;M=4;points=list(product(range(M),repeat=n));tables={}
        for upper in product(range(M),repeat=3):
            A=((upper[0],upper[1]),(upper[1],upper[2]))
            for b in product(range(M),repeat=n):tables[tuple(evaluate(A,b,bits,p) for p in points)]=1
        classes=list(tables);self.assertEqual(len(classes),128)
        from itertools import combinations
        failing=0
        for sub in combinations(range(len(points)),4):
            keys={tuple(tab[i] for i in sub) for tab in classes}
            failing+=len(keys)<len(classes)
        self.assertEqual(failing,1820)                                                            # every four-point set fails; the counting bound 4 is not attained
        P0=[points.index(p) for p in nonadaptive_points(2)]
        self.assertEqual(len({tuple(tab[i] for i in P0) for tab in classes}),128)
        self.assertEqual([evaluate(((0,0),(0,0)),(0,1),2,p) for p in ((1,0),(0,1),(1,1),(2,0))],[evaluate(((0,0),(0,1)),(0,0),2,p) for p in ((1,0),(0,1),(1,1),(2,0))])
        self.assertFalse(same_function(((0,0),(0,0)),(0,1),((0,0),(0,1)),(0,0),2))                # x_2 and x_2^2 agree on e1, e2, e1+e2, 2e1 and differ as functions
        # Comparison: quantum 2n+1 against the exact classical complexity: worse at n = 1, tie at n = 2, fewer from n = 3 for every M >= 4.
        self.assertEqual([(2*n+1<classical_complexity(3,n)) for n in (1,2,3,4)],[False,False,True,True])
        self.assertEqual([(2*n+1<classical_lower_bound(3,n)) for n in (1,2,3,4)],[False,False,False,True])

    def test_fewer_than_n_shifts_cannot_read_the_quadratic_part(self):
        # Q3(vi): with k <= n-1 shifts, N = (M/4) v v^T is nonzero mod M/2 yet reads like A = 0; its shifted pass is the same point mass.
        N,v=shift_blind_pair([(1,0)],2,2);self.assertEqual((N,v),(((0,0),(0,1)),(0,1)))
        self.assertFalse(same_function(N,(0,0),((0,0),(0,0)),(0,0),2))
        zero=prepare(shifted_row_circuit(((0,0),(0,0)),(0,0),2,0));blind=prepare(shifted_row_circuit(N,(0,0),2,0))
        self.assertEqual(zero.norms,blind.norms)                                                   # identical reading from the single shift e_1
        N3,v3=shift_blind_pair([(0,0,0),(0,0,1)],3,3);self.assertEqual(v3,(1,0,0));self.assertEqual(N3[0][0],2)
        self.assertTrue(all(sum(2*N3[i][k]*s[k] for k in range(3))%8==0 for s in ((0,0,0),(0,0,1)) for i in range(3)))
        self.assertFalse(same_function(N3,(0,0,0),((0,0,0),(0,0,0),(0,0,0)),(0,0,0),3))
        with self.assertRaises(ValueError):shift_blind_pair([(1,0),(0,1)],2,2)   # the unit shifts span F_2^2
        with self.assertRaises(ValueError):shift_blind_pair([(1,0)],1,2)
        # Exactly n shifts: a blind pair exists iff the shift matrix is singular mod 2 (exhaustive at (4,2)), and the
        # readings (2 A s)_s separate all symmetric A mod M/2 iff det S is odd.
        M=4;zero=((0,0),(0,0));sym=[((a,c),(c,d)) for a in range(2) for c in range(2) for d in range(2)]
        singular=invertible=0
        for S in product(product(range(M),repeat=2),repeat=2):
            readings=lambda A:tuple(tuple(sum(2*A[i][k]*s[k] for k in range(2))%M for i in range(2)) for s in S)
            if (S[0][0]*S[1][1]-S[0][1]*S[1][0])%2:
                invertible+=1
                with self.assertRaises(ValueError):shift_blind_pair(list(S),2,2)
                self.assertEqual(len({readings(A) for A in sym}),len(sym))
            else:
                singular+=1;N,v=shift_blind_pair(list(S),2,2)
                self.assertTrue(any(N[i][j]%(M//2) for i in range(2) for j in range(2)))
                self.assertEqual(readings(N),readings(zero));self.assertFalse(same_function(N,(0,0),zero,(0,0),2))
                self.assertLess(len({readings(A) for A in sym}),len(sym))
        self.assertEqual((singular,invertible),(160,96))
        self.assertEqual(shift_blind_pair([(1,0),(1,2)],3,2),(((0,0),(0,2)),(0,1)))   # even determinant at M = 8: 2 x_2^2 is blind

    def test_oracle_uses_are_counted_on_the_circuits_not_asserted(self):
        from unittest import mock
        import native_relational_qc.layer_queries as LQ
        A=((5,3),(3,2));b=(6,1);bits=3;real=LQ.quadratic_oracle;hidden=[]
        def counting(circuit,A_,b_,bits_,*,inverse=False,hidden=True):
            if tuple(map(tuple,A_))==A and tuple(b_)==b:hidden_calls.append(inverse)
            return real(circuit,A_,b_,bits_,inverse=inverse,hidden=hidden)
        hidden_calls=hidden
        with mock.patch.object(LQ,'quadratic_oracle',counting):r=LQ.read_quadratic_layer(A,b,bits)
        self.assertEqual(len(hidden_calls),r['oracle_uses']);self.assertEqual(len(hidden_calls),2*len(b)+1)
        self.assertTrue(r['same_function'] and r['canonical_match'])
        self.assertEqual(shifted_row_circuit(A,b,bits,0).oracle_uses,2)
        from native_relational_qc.layer_queries import remainder_circuit
        self.assertEqual(remainder_circuit(A,b,bits,canonical(A,b,bits)[0]).oracle_uses,1)       # the known representative is not a query

    def test_shifted_pass_is_a_point_mass_at_twice_the_row(self):
        A=((5,3),(3,2));b=(6,1);bits=3
        state=prepare(shifted_row_circuit(A,b,bits,0),max_work=10_000_000,max_branches=4096)
        support={ket for ket,p in state.norms.items() if p}
        self.assertEqual(support,{(2*A[0][0]%8)|((2*A[0][1]%8)<<3)})
        with self.assertRaises(ValueError):shifted_row_circuit(((1,2),(3,4)),(0,0),2,0)     # not symmetric
        with self.assertRaises(ValueError):shifted_row_circuit(((1,),),(0,),4,0)             # increment limited to 3 bits


if __name__=='__main__':unittest.main()
