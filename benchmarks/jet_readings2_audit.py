"""Exact witnesses for the second jet-readings packet: Hessian-metric curvature, enclosure learner, quadratic layer.

Every check compares exact rationals or exact flat-field elements. Checks and
negative controls are counted separately. Regression evidence only: the
statements are proved in JET_READINGS_2.md, not here.
"""
from fractions import Fraction as Q
import hashlib
from itertools import product
import json
from pathlib import Path
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_relational_qc.jet_readings import PolynomialEnergy,Reader,ghost_energy,learn_jet,poly_diff,poly_eval,poly_substitute
from native_relational_qc.hessian_metric import gaussian_curvature_brioschi,gaussian_curvature_riemann,transport_chart
from native_relational_qc.enclosure_learner import (EnclosureReader,Interval,JetEnclosure,certification_threshold,certify_sign,choose_design,
    cubic_form_numerator,curvature_enclosure,curvature_from_entries,curvature_numerator,design_inverse,design_spreads,first_layer_width_factor,fit_jet_enclosure,
    learn_jet_enclosure,numerator_determinant,numerator_ranges,tolerance_bracket,width_factors)
from native_relational_qc.jet_readings import default_candidates,fit_jet
from native_relational_qc.layer_queries import (canonical,classical_complexity,classical_lower_bound,classical_reader,count_functions,evaluate,
    nonadaptive_points,read_quadratic_layer,same_function,shift_blind_pair)

PINNED=('native_relational_qc/hessian_metric.py','native_relational_qc/enclosure_learner.py','native_relational_qc/layer_queries.py',
        'native_relational_qc/jet_readings.py','native_relational_qc/phase_backend.py','native_relational_qc/cyclotomic_pow2.py',
        'native_relational_qc/shor.py','tests/test_native_jet_readings2.py')
TEST_VALUES=[s*m for m in (1,3,5,7) for s in (-1,1)]


def blob_sha1(path):
    data=(ROOT/path).read_bytes()
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


class Tally:
    def __init__(self):self.checks=0;self.controls=0;self.sections={}
    def check(self,condition,section,note=''):
        if not condition:raise AssertionError(f'{section}: {note}')
        self.checks+=1;self.sections.setdefault(section,dict(checks=0,negative_controls=0))['checks']+=1
    def control(self,condition,section,note=''):
        if not condition:raise AssertionError(f'{section} (negative control): {note}')
        self.controls+=1;self.sections.setdefault(section,dict(checks=0,negative_controls=0))['negative_controls']+=1


def random_energy(rng,degree):
    return PolynomialEnergy({(i,j):Q(rng.randint(-6,6),rng.randint(1,4)) for i in range(degree+1) for j in range(degree+1-i)}
                            |{(2,0):Q(3),(0,2):Q(4),(1,1):Q(1,2)})


def gradient(energy,point):return tuple(poly_eval(poly_diff(energy.coefficients,l),point) for l in range(2))


def main():
    start=time.perf_counter();t=Tally();report=dict(schema='nrqc-jet-readings-v2-audit',evidence_class='LOCAL_IDEAL_CALCULATION',
        hardware_jobs=0,source_blob_sha1={p:blob_sha1(p) for p in PINNED})

    # 1. kappa equals the Gaussian curvature of the Hessian metric (two independent formulas).
    rng=random.Random(101);cases=0
    while cases<120:
        energy=random_energy(rng,rng.choice((3,4,5,6,7)));point=(Q(rng.randint(-3,3),5),Q(rng.randint(-3,3),7))
        try:kappa=energy.curvature(point)
        except ValueError:continue
        t.check(kappa==gaussian_curvature_riemann(energy,point),'hessian_metric_curvature')
        t.check(kappa==gaussian_curvature_brioschi(energy,point),'hessian_metric_curvature');cases+=1
    for u,v in product(TEST_VALUES,repeat=2):
        energy=PolynomialEnergy.cubic(u,v)
        t.check(gaussian_curvature_riemann(energy,(0,0))==Q(u*v,324),'hessian_metric_curvature')
        t.check(gaussian_curvature_brioschi(energy,(0,0))==Q(u*v,324),'hessian_metric_curvature')
        t.check(energy.curvature((0,0))==Q(u*v,324),'hessian_metric_curvature')
    report['hessian_metric']=dict(random_cases=cases,grid_cases=64)

    # 2. Nonlinear chart changes: transport with gradient equals recomposition; kappa not invariant; gradient needed.
    rng=random.Random(202);transport=0;changed=0;sign_changes=0;gradient_needed=0;defined=0
    while transport<40:
        energy=random_energy(rng,rng.choice((3,4,5)));base=(Q(rng.randint(-2,2),3),Q(rng.randint(-2,2),5));new_base=(Q(rng.randint(-2,2),4),Q(rng.randint(-2,2),4))
        c=(Q(rng.randint(-4,4),4),Q(rng.randint(-4,4),4),Q(rng.randint(-4,4),4))
        if not any(c):continue
        chart=({(1,0):Q(1),(2,0):c[0],(1,1):c[1],(0,0):Q(0)},{(0,1):Q(1),(0,2):c[2],(0,0):Q(0)})
        image=tuple(poly_eval(p,new_base) for p in chart)
        chart=({**chart[0],(0,0):base[0]-image[0]},{**chart[1],(0,0):base[1]-image[1]})
        try:kappa=energy.curvature(base)
        except ValueError:continue
        jet=energy.hessian_jet(base,2)
        try:moved,grad=transport_chart(jet,gradient(energy,base),chart,new_base)
        except ValueError:continue
        recomposed=PolynomialEnergy(poly_substitute(energy.coefficients,chart[0],chart[1]))
        t.check(moved==recomposed.hessian_jet(new_base,2),'nonlinear_chart');t.check(grad==gradient(recomposed,new_base),'nonlinear_chart')
        other,_=transport_chart(jet,(gradient(energy,base)[0]+1,gradient(energy,base)[1]),chart,new_base)
        if other!=moved:gradient_needed+=1
        try:
            k2=moved.curvature();defined+=1
            if k2!=kappa:changed+=1
            if (k2>0)!=(kappa>0):sign_changes+=1
        except ValueError:pass
        transport+=1
    t.control(changed>0,'nonlinear_chart','kappa must change under some nonlinear chart');t.control(gradient_needed>0,'nonlinear_chart','gradient must matter')
    scout=transport_chart(PolynomialEnergy.cubic(3,-5).hessian_jet((0,0),1),(10,-10),({(1,0):Q(1),(0,2):Q(1,2)},{(0,1):Q(1)}),(0,0))[0].curvature()
    t.check(scout==Q(-22,841),'nonlinear_chart',scout)
    # J6(d): explicit instances, the one-parameter formula, the shift T' = T + S(Q) with H' = H at a critical base, and the order of phi needed.
    zero=PolynomialEnergy({k:v for k,v in PolynomialEnergy.cubic(3,-5).coefficients.items() if sum(k)>=2})
    t.check(transport_chart(zero.hessian_jet((0,0),1),(0,0),({(1,0):Q(1),(0,2):Q(2)},{(0,1):Q(1)}),(0,0))[0].curvature()==Q(29,324),'nonlinear_chart','+29/324')
    moved=transport_chart(PolynomialEnergy.cubic(3,-5).hessian_jet((0,0),1),(10,-10),({(1,0):Q(1),(1,1):Q(-1,5)},{(0,1):Q(1)}),(0,0))[0]
    t.check(moved.hessian()==(Q(2),Q(-1),Q(5)) and moved.curvature()==Q(421,8100),'nonlinear_chart','+421/8100')
    flat=PolynomialEnergy({(2,0):Q(1),(1,1):Q(1),(0,2):Q(5,2)})
    t.check(flat.curvature((0,0))==0 and transport_chart(flat.hessian_jet((0,0),1),(0,0),({(1,0):Q(1),(0,2):Q(1)},{(0,1):Q(1)}),(0,0))[0].curvature()==Q(8,81),'nonlinear_chart','8/81')
    for c in (Q(1,2),Q(-1,5),Q(2),Q(1,10),Q(-1,10),Q(3)):   # admissible: 9+40c>0
        k=transport_chart(PolynomialEnergy.cubic(3,-5).hessian_jet((0,0),1),(10,-10),({(1,0):Q(1),(0,2):c},{(0,1):Q(1)}),(0,0))[0].curvature()
        t.check(k==(-208*c*c-42*c-15)/(4*(9+40*c)**2),'nonlinear_chart',('kappa(c)',c))
        t.check(transport_chart(zero.hessian_jet((0,0),1),(0,0),({(1,0):Q(1),(0,2):c},{(0,1):Q(1)}),(0,0))[0].curvature()==(32*c*c-42*c-15)/324,'nonlinear_chart',('kappa0(c)',c))
    t.check(42*42-4*208*15<0,'nonlinear_chart','that family never flips the sign (integer arithmetic on the proved formula)')
    rng=random.Random(606);shifts=0
    while shifts<20:
        energy=random_energy(rng,rng.choice((3,4,5)));base=(Q(rng.randint(-2,2),3),Q(rng.randint(-2,2),5))
        critical=PolynomialEnergy({k:v for k,v in energy.coefficients.items() if sum(k)>=2})  # gradient zero at the origin
        try:jet=critical.hessian_jet((0,0),1);H=jet.hessian();jet.curvature()
        except ValueError:continue
        q=[[Q(rng.randint(-3,3),4) for _ in range(3)] for _ in range(2)]        # phi^k = delta_k + q20 s^2 + q11 s v + q02 v^2
        chart=({(1,0):Q(1),(2,0):q[0][0],(1,1):q[0][1],(0,2):q[0][2]},{(0,1):Q(1),(2,0):q[1][0],(1,1):q[1][1],(0,2):q[1][2]})
        moved,_=transport_chart(jet,(0,0),chart,(0,0));Hs,Hv=jet.first_layer();T=(Hs[0],Hs[1],Hs[2],Hv[2])
        Qm=[((2*q[k][0],q[k][1]),(q[k][1],2*q[k][2])) for k in range(2)];Hm=((H[0],H[1]),(H[1],H[2]))
        def S(a,b,c):return sum(Hm[k][c]*Qm[k][a][b]+Hm[k][b]*Qm[k][a][c]+Hm[k][a]*Qm[k][b][c] for k in range(2))
        expected=(T[0]+S(0,0,0),T[1]+S(0,0,1),T[2]+S(0,1,1),T[3]+S(1,1,1))
        Ms,Mv=moved.first_layer();got=(Ms[0],Ms[1],Ms[2],Mv[2])
        t.check(moved.hessian()==H and got==expected,'nonlinear_chart','T+S(Q)');shifts+=1
    for d in (0,1,2):
        base_jet=PolynomialEnergy.cubic(3,-5).hessian_jet((0,0),d)
        plain,_=transport_chart(base_jet,(10,-10),({(1,0):Q(1)},{(0,1):Q(1)}),(0,0))
        bumped,_=transport_chart(base_jet,(10,-10),({(1,0):Q(1),(0,d+2):Q(1,7)},{(0,1):Q(1)}),(0,0))
        diff={k:tuple(x-y for x,y in zip(bumped.coefficients[k],plain.coefficients[k])) for k in plain.coefficients}
        t.check(diff[(0,d)]==(0,0,Q(10*(d+2)*(d+1),7)) and all(not any(v) for k,v in diff.items() if k!=(0,d)),'nonlinear_chart',('order d+2 of phi',d))
    # J6(d'): phi = (s' + t v'^3, v') has J = I and Hess(phi^k) = 0 at the base, so H' = H exactly; the gradient times the third
    # derivatives of phi still moves the first layer, kappa' = (-15 + 180 t)/324, and the sign flips at t = 1/7.
    jet35=PolynomialEnergy.cubic(3,-5).hessian_jet((0,0),1)
    for tt in (Q(1,7),Q(1,12),Q(-1,3),Q(1,100),Q(-1,2)):
        out=transport_chart(jet35,(10,-10),({(1,0):Q(1),(0,3):tt},{(0,1):Q(1)}),(0,0))[0]
        t.check(out.hessian()==jet35.hessian() and out.first_layer()[1]==(Q(0),Q(0),Q(-5)+60*tt) and out.curvature()==(-15+180*tt)/324,'nonlinear_chart',('third derivative',tt))
    t.check(transport_chart(jet35,(10,-10),({(1,0):Q(1),(0,3):Q(1,7)},{(0,1):Q(1)}),(0,0))[0].curvature()==Q(25,756)>0>jet35.curvature(),'nonlinear_chart','sign flip with zero chart Hessian')
    t.control(transport_chart(jet35,(0,0),({(1,0):Q(1),(0,3):Q(1,7)},{(0,1):Q(1)}),(0,0))[0].coefficients==jet35.coefficients,'nonlinear_chart','zero gradient: third derivatives of phi do nothing at order one')
    # Nullspace of S: two genuinely nonlinear quadratic charts that leave the order-one jet (hence kappa) unchanged at a critical base.
    for chart in (({(1,0):Q(1),(2,0):Q(-1),(1,1):Q(-5)},{(0,1):Q(1),(2,0):Q(2),(1,1):Q(1)}),({(1,0):Q(1),(2,0):Q(1),(1,1):Q(9,2),(0,2):Q(-5,2)},{(0,1):Q(1),(2,0):Q(-2),(0,2):Q(1,2)})):
        t.check(transport_chart(jet35,(0,0),chart,(0,0))[0].coefficients==jet35.coefficients,'nonlinear_chart','nullspace chart leaves the jet')
        t.control(transport_chart(jet35,(10,-10),chart,(0,0))[0].coefficients!=jet35.coefficients,'nonlinear_chart','the same chart acts once the gradient is nonzero')
    report['nonlinear_chart']=dict(transports=transport,kappa_defined_after=defined,kappa_changed=changed,sign_changed=sign_changes,gradient_changed_result=gradient_needed,
                                   scout_example=dict(energy='cubic(3,-5)',chart="(s'+v'^2/2, v')",kappa_before='-5/108',kappa_after=str(scout)),
                                   zero_hessian_chart=dict(chart="(s'+t v'^3, v')",gradient='(10,-10)',kappa_after='(-15+180t)/324',sign_flip_at='t=1/7',kappa_at_1_over_7='25/756'),
                                   nullspace_charts=2)

    # 3. Enclosure learner: tightness, validity, certification, tolerance.
    rng=random.Random(303);design=[(Q(-3,4),Q(-3,4)),(Q(3,4),Q(3,4)),(Q(-3,4),Q(3,4))];base=(0,0);per_case={};rescued=rescued_learner=rejected_perturbations=0
    factors=width_factors(base,design,1);t.check(factors[(1,0)]+factors[(0,1)]==Q(8,3),'enclosure_learner')
    for u,v in product(TEST_VALUES,repeat=2):
        energy=PolynomialEnergy.cubic(u,v);jet=energy.hessian_jet(base,1)
        for w in (Q(1,100),Q(1,20)):
            enclosure=fit_jet_enclosure(base,[(p,EnclosureReader(energy,w).read(p)) for p in design],1)
            t.check(enclosure.contains(jet),'enclosure_learner',(u,v,w))
            for key,triple in enclosure.coefficients.items():
                for c in triple:t.check(c.width==2*w*factors[key],'enclosure_learner',(u,v,w,key))
            kappa=curvature_enclosure(enclosure);t.check(jet.curvature() in kappa,'enclosure_learner',(u,v,w))
            for _ in range(5):
                readings=[(p,tuple(x+Q(rng.randint(-100,100),100)*w for x in energy.hessian(p))) for p in design]
                t.check(enclosure.contains(fit_jet(base,readings,1)),'enclosure_learner')     # E1: any admissible interpolant
            admissible=0
            while admissible<3:                                                                  # E3: any admissible energy (sampler reaches the box boundary)
                perturbed=PolynomialEnergy(dict(energy.coefficients)|{(i,j):energy.coefficients.get((i,j),Q(0))+Q(rng.randint(-3,3),1000)*w*120 for i in range(4) for j in range(4-i) if i+j>=2})
                if all(abs(x-y)<=w for p in design for x,y in zip(perturbed.hessian(p),energy.hessian(p))):
                    admissible+=1;t.check(perturbed.curvature(base) in kappa,'enclosure_learner',(u,v,w))
                else:rejected_perturbations+=1
        certified=learn_jet_enclosure(EnclosureReader(energy,Q(1,100)),base)
        t.check(certified['status']=='sign_certified' and certified['sign']==(1 if u*v>0 else -1),'enclosure_learner',(u,v))
        thr=certification_threshold([energy],base,design);sup=thr['sup']                  # E4 per case: exact rational supremum
        t.check(thr['exact'] and Q(1,13)<=sup<thr['gate_root']==1,'enclosure_learner',(u,v,'threshold'))
        just_below=fit_jet_enclosure(base,[(p,EnclosureReader(energy,sup-Q(1,1<<40)).read(p)) for p in design],1)
        t.check(certify_sign(just_below)[0]==(1 if u*v>0 else -1),'enclosure_learner',(u,v,'certified just below the threshold'))
        at=fit_jet_enclosure(base,[(p,EnclosureReader(energy,sup).read(p)) for p in design],1)
        t.control(Q(0) in curvature_enclosure(at,intersect=False),'enclosure_learner',(u,v,'route (i) withholds the sign at the threshold'))
        still=certify_sign(at)[0]
        if still is not None:rescued+=1;t.check(still==(1 if u*v>0 else -1),'enclosure_learner',(u,v,'route (ii) beyond the route (i) threshold is still right'))
        withheld=learn_jet_enclosure(EnclosureReader(energy,sup+Q(1,50)),base)
        t.control(withheld['status'] in ('sign_not_certified','sign_certified') and Q(u*v,324) in withheld['curvature'],'enclosure_learner',(u,v))
        if withheld['status']=='sign_certified':rescued_learner+=1;t.check(withheld['sign']==(1 if u*v>0 else -1),'enclosure_learner',(u,v))
        per_case[f'{u},{v}']=dict(threshold=str(sup),witness_integrable=bool(thr['witness']['integrable']),witness_kappa=str(thr['witness']['kappa']))
    t.check(rejected_perturbations>0,'enclosure_learner','the perturbation sampler crosses the reading box')
    # Cubic energies with all four third derivatives nonzero (the E- and G-terms of the closed form active) are in the declared family too.
    mixed_cases=0
    while mixed_cases<24:
        mixed=PolynomialEnergy({(2,0):Q(2),(1,1):Q(1),(0,2):Q(5)}|{(i,j):Q(rng.randint(-9,9),rng.randint(1,3)) for i in range(4) for j in range(4-i) if i+j==3})
        jet=mixed.hessian_jet(base,1);Hs,Hv=jet.first_layer();T=(Hs[0],Hs[1],Hs[2],Hv[2])
        if T[1]==0 or T[2]==0 or jet.curvature()==0:continue
        mixed_cases+=1;w=Q(1,100)
        enclosure=fit_jet_enclosure(base,[(p,EnclosureReader(mixed,w).read(p)) for p in design],1);kappa=curvature_enclosure(enclosure)
        t.check(enclosure.contains(jet) and jet.curvature() in kappa,'enclosure_learner',('mixed cubic',mixed_cases))
        t.check(cubic_form_numerator(jet.hessian(),T)/(4*(jet.hessian()[0]*jet.hessian()[2]-jet.hessian()[1]**2)**2)==jet.curvature(),'enclosure_learner',('closed form, E and G terms active',mixed_cases))
        for pick in rng.sample(list(product((0,1),repeat=9)),16):                               # family members at reading-box corners
            readings=[(p,tuple((enclosure.readings[q][e].lo,enclosure.readings[q][e].hi)[pick[3*q+e]] for e in range(3))) for q,p in enumerate(design)]
            corner_jet=fit_jet(base,readings,1);S_,V_=corner_jet.first_layer()
            if S_[1]==V_[0] and S_[2]==V_[1]:t.check(corner_jet.curvature() in kappa,'enclosure_learner',('integrable corner',mixed_cases))
        certified=learn_jet_enclosure(EnclosureReader(mixed,w),base)
        if certified['status']=='sign_certified':t.check(certified['sign']==(1 if jet.curvature()>0 else -1),'enclosure_learner',('mixed cubic certificate',mixed_cases))
    cases=[PolynomialEnergy.cubic(u,v) for u,v in product(TEST_VALUES,repeat=2)]
    ok,fail=tolerance_bracket(cases,base,design,steps=20)
    t.check(ok<fail,'enclosure_learner')
    scaled=[(Q(-3,2),Q(-3,2)),(Q(3,2),Q(3,2)),(Q(-3,2),Q(3,2))]
    t.check(first_layer_width_factor(base,scaled)==Q(4,3),'enclosure_learner')
    ok2,fail2=tolerance_bracket(cases,base,scaled,steps=20);t.check(ok2>ok,'enclosure_learner','larger design radius tolerates wider readings for an affine Hessian field')
    # E4 on the whole grid: sup = 1/13 exactly; the witness is the Hessian jet of a cubic with kappa = 0, so no sound certifier can do better.
    whole=certification_threshold(cases,base,design);witness=whole['witness']
    t.check(whole['sup']==Q(1,13) and whole['exact'] and whole['gate_root']==1 and ok<Q(1,13)<fail,'enclosure_learner','sup 1/13')
    t.check(list(product(TEST_VALUES,repeat=2))[witness['case']]==(-1,1) and witness['integrable'] and witness['kappa']==0,'enclosure_learner','witness (-1,1), integrable, kappa 0')
    t.check(witness['jet'].hessian()==(Q(27,13),Q(12,13),Q(66,13)) and witness['jet'].first_layer()==((Q(-35,39),Q(-4,39),Q(4,39)),(Q(-4,39),Q(4,39),Q(35,39))),'enclosure_learner','witness jet')
    t.check(all(abs(witness['readings'][q][e]-cases[witness['case']].hessian(p)[e])<=Q(1,13) for q,p in enumerate(design) for e in range(3)),'enclosure_learner','witness admissible')
    beyond=[(p,tuple(cases[witness['case']].hessian(p)[e]+(Q(1,13)+Q(1,1<<20))*witness['pattern'][3*q+e] for e in range(3))) for q,p in enumerate(design)]
    t.control(fit_jet(base,beyond,1).curvature()>0>cases[witness['case']].curvature(base),'enclosure_learner','beyond the supremum the pattern gives the wrong sign')
    whole2=certification_threshold(cases,base,scaled)
    t.check(whole2['sup']==Q(1,7) and whole2['exact'] and whole2['witness']['integrable'] and ok2<Q(1,7)<fail2,'enclosure_learner','scaled sup 1/7')
    t.check(min(Q(r['threshold']) for r in per_case.values())==Q(1,13),'enclosure_learner','grid sup is the minimum per-case sup')
    quartic=PolynomialEnergy({(2,0):Q(1),(1,1):Q(1),(0,2):Q(5,2),(4,0):Q(1)})
    t.control(learn_jet_enclosure(EnclosureReader(quartic,Q(1,1000)),base,order=1)['status']=='order_falsified','enclosure_learner')
    t.control(learn_jet_enclosure(EnclosureReader(PolynomialEnergy.cubic(1,1),Q(3)),base)['status']=='positivity_not_certified','enclosure_learner')
    # Scope control: an energy outside the declared family with identical readings gets the same certificate and a different kappa.
    energy=PolynomialEnergy.cubic(3,-5);reader=EnclosureReader(energy,Q(1,100));learned=learn_jet_enclosure(reader,base)
    ghost=ghost_energy(energy,list(reader.record),scale=5,directions=((1,0),(0,1),(2,1),(1,2),(3,1),(1,3)))
    for point in reader.record:t.check(ghost.hessian(point)==energy.hessian(point),'enclosure_scope')
    twin=learn_jet_enclosure(EnclosureReader(ghost,Q(1,100)),base)
    t.control(twin['status']==learned['status']=='sign_certified' and twin['curvature']==learned['curvature'],'enclosure_scope','same certificate')
    t.control(ghost.curvature(base) not in twin['curvature'] and (ghost.curvature(base)>0)!=(energy.curvature(base)>0),'enclosure_scope','different true kappa, outside the enclosure')
    # Integrability falsification: a quartic whose first-layer intervals cannot be one Hessian jet.
    skew=PolynomialEnergy({(2,0):Q(1),(1,1):Q(1),(0,2):Q(5,2),(3,1):Q(1,10)})
    result=learn_jet_enclosure(EnclosureReader(skew,Q(1,100)),base,checks=0)
    t.control(result['status']=='order_falsified' and any('integrability' in f for f in result['falsifications']),'enclosure_scope','integrability defect falsifies the order')
    # Route (ii) tightening: asymmetric designs and per-entry widths where the cubic-form intersection is strictly inside the nine-entry interval.
    rng=random.Random(505);tightened=0;attempts=0
    while tightened<40 and attempts<400:
        attempts+=1;u,v=rng.choice(TEST_VALUES),rng.choice(TEST_VALUES);energy=PolynomialEnergy.cubic(u,v)
        points=[(Q(rng.randint(-6,6),8),Q(rng.randint(-6,6),8)) for _ in range(3)]
        widths=tuple(Q(rng.randint(1,8),200) for _ in range(3))
        try:enclosure=fit_jet_enclosure(base,[(p,EnclosureReader(energy,lambda q,w=widths:w).read(p)) for p in points],1)
        except ValueError:continue
        try:both=curvature_enclosure(enclosure);nine=curvature_enclosure(enclosure,intersect=False)
        except ValueError:continue
        if both.lo>nine.lo or both.hi<nine.hi:
            tightened+=1;t.check(nine.lo<=both.lo and both.hi<=nine.hi,'enclosure_tightening')
            t.check(energy.curvature(base) in both,'enclosure_tightening')
            admissible=0
            while admissible<2:
                perturbed=PolynomialEnergy(dict(energy.coefficients)|{(i,j):energy.coefficients.get((i,j),Q(0))+Q(rng.randint(-3,3),2000) for i in range(4) for j in range(4-i) if i+j>=2})
                if all(abs(x-y)<=w for p in points for x,y,w in zip(perturbed.hessian(p),energy.hessian(p),widths)):
                    admissible+=1;t.check(perturbed.curvature(base) in both,'enclosure_tightening')
    t.check(tightened==40,'enclosure_tightening','forty strictly tightened enclosures found')
    report['enclosure_learner']=dict(design=[[str(x) for x in p] for p in design],first_layer_width_factor='8/3',route_ii_strict_tightenings=tightened,route_ii_attempts=attempts,
        grid_tolerance_half_width=dict(certified_at=str(ok),not_certified_at=str(fail),bisection_steps=20),
        scaled_design_radius='3/2',scaled_tolerance=dict(certified_at=str(ok2),not_certified_at=str(fail2)),
        exact_threshold=dict(grid_supremum='1/13',witness_case='-1,1',witness_readings=[[str(x) for x in r] for r in witness['readings']],witness_hessian=['27/13','12/13','66/13'],
                             witness_kappa='0',witness_integrable=True,scaled_supremum=str(whole2['sup']),scaled_witness_integrable=bool(whole2['witness']['integrable']),
                             per_case=per_case,integrable_witnesses=sum(1 for r in per_case.values() if r['witness_integrable']),
                             route_ii_certifies_at_route_i_threshold=rescued,learner_certifies_beyond_threshold_plus_1_over_50=rescued_learner))

    # 3b. Numerator ranges: natural >= coefficient corners >= reading corners (exact), the unattainable coefficient corner, tightening counts.
    strict=0
    for u,v in product(TEST_VALUES,repeat=2):
        energy=PolynomialEnergy.cubic(u,v)
        for w in (Q(1,100),Q(1,20)):
            enclosure=fit_jet_enclosure(base,[(p,EnclosureReader(energy,w).read(p)) for p in design],1);ranges=numerator_ranges(enclosure)
            nat,box,adm=ranges['natural'],ranges['coefficient_corners'],ranges['reading_corners']
            t.check(nat.lo<=box.lo<=adm.lo and adm.hi<=box.hi<=nat.hi,'numerator_routes',(u,v,w,'nesting'))
            truth=numerator_determinant(energy.hessian(base),*energy.hessian_jet(base,1).first_layer());t.check(truth in adm,'numerator_routes',(u,v,w,'truth inside'))
            strict+=(box.lo<adm.lo or adm.hi<box.hi)
            # route (ii) never strictly tightens either route on this symmetric design (recorded, as the note says).
            both=curvature_enclosure(enclosure);e3=curvature_enclosure(enclosure,intersect=False);both2=curvature_enclosure(enclosure,readings=False);e2=curvature_enclosure(enclosure,intersect=False,readings=False)
            t.check(both==e3 and both2==e2,'numerator_routes',(u,v,w,'route (ii) does not tighten on the symmetric design'))
            if (abs(u),abs(v))in((1,1),(1,3),(3,1),(3,3)) and w==Q(1,20):                      # endpoints attained by admissible reading corners
                values=set()
                for pick in product((0,1),repeat=9):
                    readings=[(p,tuple((enclosure.readings[q][e].lo,enclosure.readings[q][e].hi)[pick[3*q+e]] for e in range(3))) for q,p in enumerate(design)]
                    jet=fit_jet(base,readings,1);values.add(numerator_determinant(jet.hessian(),*jet.first_layer()))
                t.check(min(values)==adm.lo and max(values)==adm.hi,'numerator_routes',(u,v,'attained'))
    enclosure=fit_jet_enclosure(base,[(p,EnclosureReader(PolynomialEnergy.cubic(1,1),Q(1,16)).read(p)) for p in design],1);ranges=numerator_ranges(enclosure)
    t.check(ranges['coefficient_corners']==Interval(Q(-371,192),Q(-3,16)) and ranges['reading_corners']==Interval(Q(-3763,2304),Q(-11,24)),'numerator_routes','cubic(1,1) at 1/16')
    corner_h11=[sum(row*c for row,c in zip((Q(1),p[0],p[1]),(Q(33,16),Q(13,12),Q(1,12)))) for p in design]
    t.control(corner_h11==[Q(19,16),Q(47,16),Q(21,16)] and corner_h11[1] not in enclosure.readings[1][0],'numerator_routes','the coefficient corner (a,p1,r1) at its upper bounds has no admissible preimage')
    rng=random.Random(707);asym=dict(designs=0,reading_corners_strictly_inside=0,route_ii_tightens_reading_corners=0)
    while asym['designs']<100:
        u,v=rng.choice(TEST_VALUES),rng.choice(TEST_VALUES);energy=PolynomialEnergy.cubic(u,v)
        points=[(Q(rng.randint(-6,6),8),Q(rng.randint(-6,6),8)) for _ in range(3)];widths=tuple(Q(rng.randint(1,8),200) for _ in range(3))
        try:enclosure=fit_jet_enclosure(base,[(p,EnclosureReader(energy,lambda q,w=widths:w).read(p)) for p in points],1);both=curvature_enclosure(enclosure);e3=curvature_enclosure(enclosure,intersect=False);e2=curvature_enclosure(enclosure,intersect=False,readings=False)
        except ValueError:continue
        asym['designs']+=1;asym['reading_corners_strictly_inside']+=(e3.lo>e2.lo or e3.hi<e2.hi);asym['route_ii_tightens_reading_corners']+=(both.lo>e3.lo or both.hi<e3.hi)
        t.check(e2.lo<=e3.lo and e3.hi<=e2.hi and e3.lo<=both.lo and both.hi<=e3.hi and energy.curvature(base) in both,'numerator_routes','asymmetric nesting and validity')
    t.check(asym['reading_corners_strictly_inside']>0 and asym['route_ii_tightens_reading_corners']>0,'numerator_routes','both tightenings occur on asymmetric designs')
    report['numerator_routes']=dict(symmetric_cases=128,reading_corners_strictly_inside_coefficient_corners=strict,route_ii_strict_tightenings_on_symmetric_design=0,asymmetric=asym)

    # 3c. Design criterion on the default candidate grid: identities, the lower bound, maximal volume versus minimal width.
    cand=default_candidates(base);rows=[];maxdet=Q(0);nonsingular=collinear=0
    for triple in __import__('itertools').combinations(cand,3):
        D=[[Q(1),p[0],p[1]] for p in triple];det=D[0][0]*(D[1][1]*D[2][2]-D[1][2]*D[2][1])-D[0][1]*(D[1][0]*D[2][2]-D[1][2]*D[2][0])+D[0][2]*(D[1][0]*D[2][1]-D[1][1]*D[2][0])
        if det==0:collinear+=1;continue
        nonsingular+=1;f=width_factors(base,list(triple),1);Ds,Dv=design_spreads(triple)
        t.check(f[(1,0)]==2*Dv/abs(det) and f[(0,1)]==2*Ds/abs(det) and f[(0,0)]>=1 and f[(1,0)]>=Q(4,3) and f[(0,1)]>=Q(4,3) and abs(det)<=Ds*Dv,'design_criterion')
        rows.append((abs(det),f[(1,0)],f[(0,1)]));maxdet=max(maxdet,abs(det))
    t.check(nonsingular==17600 and collinear==824 and maxdet==Q(9,4),'design_criterion','18424 triples')
    maximal={i for i,(d,_,_) in enumerate(rows) if d==maxdet};minimal={i for i,(_,a,b) in enumerate(rows) if a==b==Q(4,3)}
    t.check(maximal==minimal and len(maximal)==24,'design_criterion','maximal volume = minimal first-layer width, 24 designs')
    rng=random.Random(808);larger_det_wider=0
    for _ in range(20000):
        i,j=rng.randrange(len(rows)),rng.randrange(len(rows))
        if rows[i][0]>rows[j][0] and rows[i][1]>rows[j][1]:larger_det_wider+=1
    t.control(larger_det_wider>0,'design_criterion','a larger |det D| with a larger (1,0) width factor occurs')
    A3=[(Q(-3,4),Q(0)),(Q(3,4),Q(0)),(Q(0),Q(1,4))];B3=[(Q(-3,4),Q(-3,4)),(Q(-1,4),Q(-3,4)),(Q(0),Q(3,4))]
    t.control(width_factors(base,A3,1)[(1,0)]==Q(4,3) and width_factors(base,B3,1)[(1,0)]==Q(4) and abs(Q(3,8))<abs(Q(3,4)),'design_criterion','A3 (det 3/8) narrower than B3 (det 3/4)')
    t.control(width_factors(base,[(0,0),(2,0),(0,2)],1)[(1,0)]==1<width_factors(base,[(0,0),(5,4),(4,5)],1)[(1,0)]==Q(10,9),'design_criterion','det 4 narrower than det 9')
    swap_cands=[(Q(-5,4),Q(-2)),(Q(-3,4),Q(0)),(Q(0),Q(1,4)),(Q(1,4),Q(1)),(Q(3,2),Q(1,2)),(Q(7,4),Q(7,4)),(Q(2),Q(-3,4))]
    g0=choose_design(base,swap_cands,1,sweeps=0);g4=choose_design(base,swap_cands,1,sweeps=4)
    best_swap=None
    for tr in __import__('itertools').combinations(swap_cands,3):
        try:f=first_layer_width_factor(base,list(tr))
        except ValueError:continue
        best_swap=f if best_swap is None or f<best_swap else best_swap
    t.check(g0[1]==Q(224,135) and not g0[2] and g4[1]==Q(100,63) and g4[2] and best_swap==Q(168,107)<g4[1]<g0[1],'design_criterion','swap descent acts: 224/135 -> 100/63, global 168/107')
    chosen={order:choose_design(base,cand,order) for order in (1,2,3)}
    t.check([chosen[o][1] for o in (1,2,3)]==[Q(8,3),Q(8,3),Q(28,3)] and all(chosen[o][2] for o in (1,2,3)),'design_criterion','orders 1, 2, 3 on the default candidates')
    greedy2=[(Q(-3,4),Q(-3,4)),(Q(3,4),Q(3,4)),(Q(-3,4),Q(3,4)),(Q(-3,4),Q(-1,2)),(Q(3,4),Q(-3,4)),(Q(0),Q(-3,4))]
    t.check(width_factors(base,greedy2,2)=={(0,0):Q(51,10),(1,0):Q(4,3),(0,1):Q(4,3),(2,0):Q(32,9),(1,1):Q(16,9),(0,2):Q(32,5)},'design_criterion','greedy order-2 design')
    report['design_criterion']=dict(triples=18424,nonsingular=nonsingular,collinear=collinear,max_abs_det='9/4',designs_with_max_det=len(maximal),min_first_layer_row_sum='4/3',
        larger_det_and_wider_pairs=larger_det_wider,random_pairs=20000,first_layer_factor_by_order={str(o):str(chosen[o][1]) for o in (1,2,3)},
        swap_descent_example=dict(greedy='224/135',after_swaps='100/63',global_minimum='168/107'))

    # 4. Quadratic phase layer: classes, 2n+1 readings, counting comparison.
    classes=[]
    for bits,n in ((2,1),(3,1),(2,2)):
        count,formula=count_functions(bits,n);t.check(count==formula,'quadratic_layer_classes',(bits,n));classes.append(dict(bits=bits,registers=n,functions=count))
    report['function_classes']=classes
    quantum=[]
    for bits in (2,3):
        M=1<<bits;clock=time.perf_counter();peak=0
        for a,b in product(range(M),repeat=2):
            r=read_quadratic_layer(((a,),),(b,),bits);t.check(r['same_function'] and r['canonical_match'] and r['oracle_uses']==3,'quadratic_layer_reading',(bits,a,b));peak=max(peak,r['peak_branches'])
        quantum.append(dict(bits=bits,registers=1,cases=M*M,oracle_uses=r['oracle_uses'],classical_lower_bound=classical_lower_bound(bits,1),peak_branches=peak,seconds=round(time.perf_counter()-clock,3)))
    rng=random.Random(404)
    for bits,n,cases in ((2,2,24),(3,2,24),(2,3,12),(3,3,8),(3,4,3)):
        M=1<<bits;clock=time.perf_counter();peak=0
        for _ in range(cases):
            A=[[0]*n for _ in range(n)]
            for i in range(n):
                for j in range(i,n):A[i][j]=A[j][i]=rng.randrange(M)
            b=tuple(rng.randrange(M) for _ in range(n))
            r=read_quadratic_layer(tuple(tuple(x) for x in A),b,bits);t.check(r['same_function'] and r['canonical_match'] and r['oracle_uses']==2*n+1,'quadratic_layer_reading',(bits,n));peak=max(peak,r['peak_branches'])
        quantum.append(dict(bits=bits,registers=n,cases=cases,oracle_uses=r['oracle_uses'],classical_lower_bound=classical_lower_bound(bits,n),peak_branches=peak,seconds=round(time.perf_counter()-clock,3)))
    for row in quantum:
        row['quantum_fewer_than_classical_bound']=row['oracle_uses']<row['classical_lower_bound']
        row['classical_complexity']=classical_complexity(row['bits'],row['registers']);row['quantum_fewer_than_classical_complexity']=row['oracle_uses']<row['classical_complexity']
    # Q3(v): exact classical complexity n(n+3)/2: P0 decodes every class; no smaller point set at (4,2); the counting bound is not attained for n >= 2.
    classical=[]
    for bits,n in ((2,1),(3,1),(2,2),(3,2)):
        M=1<<bits;entries=n*(n+1)//2;decoded=0
        for upper in product(range(M),repeat=entries):
            A=[[0]*n for _ in range(n)];k=0
            for i in range(n):
                for j in range(i,n):A[i][j]=A[j][i]=upper[k];k+=1
            for b in product(range(M),repeat=n):
                r=classical_reader(tuple(map(tuple,A)),b,bits);t.check(r['same_function'] and r['canonical_match'] and r['readings']==n*(n+3)//2,'classical_complexity',(bits,n));decoded+=1
        classical.append(dict(bits=bits,registers=n,parameter_vectors=decoded,readings=n*(n+3)//2,counting_bound=classical_lower_bound(bits,n)))
    rng=random.Random(909)
    for bits,n,cases in ((2,3,400),(3,3,200),(3,4,50)):
        M=1<<bits
        for _ in range(cases):
            A=[[0]*n for _ in range(n)]
            for i in range(n):
                for j in range(i,n):A[i][j]=A[j][i]=rng.randrange(M)
            b=tuple(rng.randrange(M) for _ in range(n));r=classical_reader(tuple(map(tuple,A)),b,bits)
            t.check(r['same_function'] and r['canonical_match'] and r['readings']==n*(n+3)//2,'classical_complexity',(bits,n))
        classical.append(dict(bits=bits,registers=n,parameter_vectors=cases,readings=n*(n+3)//2,counting_bound=classical_lower_bound(bits,n),sampled=True))
    bits,n=2,2;M=4;points=list(product(range(M),repeat=n));tables=set()
    for upper in product(range(M),repeat=3):
        A=((upper[0],upper[1]),(upper[1],upper[2]))
        for b in product(range(M),repeat=n):tables.add(tuple(evaluate(A,b,bits,p) for p in points))
    classes=list(tables);failing=0
    for sub in __import__('itertools').combinations(range(len(points)),4):
        failing+=len({tuple(tab[i] for i in sub) for tab in classes})<len(classes)
    t.check(len(classes)==128 and failing==1820,'classical_complexity','(4,2): all 1820 four-point sets fail, P0 (5 points) separates')
    t.check(len({tuple(tab[points.index(p)] for p in nonadaptive_points(2)) for tab in classes})==128,'classical_complexity','P0 separates at (4,2)')
    t.control(not same_function(((0,0),(0,0)),(0,1),((0,0),(0,1)),(0,0),2) and [evaluate(((0,0),(0,0)),(0,1),2,p) for p in ((1,0),(0,1),(1,1),(2,0))]==[evaluate(((0,0),(0,1)),(0,0),2,p) for p in ((1,0),(0,1),(1,1),(2,0))],
              'classical_complexity','x_2 and x_2^2 agree on four points')
    # Q3(vi): fewer than n shifts cannot read A mod M/2: every (n-1)-tuple at (4,2), (8,2); random tuples at (4,3), (8,3).
    blind=0
    for bits,n,tuples in ((2,2,None),(3,2,None),(2,3,60),(3,3,40)):
        M=1<<bits;allshifts=list(product(range(M),repeat=n))
        pool=list(product(allshifts,repeat=n-1)) if tuples is None else [tuple(rng.choice(allshifts) for _ in range(n-1)) for _ in range(tuples)]
        for shifts in pool:
            N,v=shift_blind_pair(list(shifts),bits,n);zero=tuple(tuple(0 for _ in range(n)) for _ in range(n))
            t.control(any(N[i][j]%(M//2) for i in range(n) for j in range(n)) and not same_function(N,(0,)*n,zero,(0,)*n,bits),'classical_complexity',('blind pair differs',bits,n))
            t.check(all(sum(2*N[i][k]*s[k] for k in range(n))%M==0 for s in shifts for i in range(n)),'classical_complexity',('blind pair reads like zero',bits,n));blind+=1
    # Q3(vi) sharpened: for exactly n shifts a blind pair exists iff the shift matrix is singular mod 2, and the shift
    # readings separate all symmetric A mod M/2 iff it is invertible mod 2; every n-tuple at (4,2), (8,2); random at (4,3), (8,3).
    square=dict(singular=0,invertible=0)
    for bits,n,tuples in ((2,2,None),(3,2,None),(2,3,300),(3,3,120)):
        M=1<<bits;allshifts=list(product(range(M),repeat=n));zero=tuple(tuple(0 for _ in range(n)) for _ in range(n))
        pool=list(product(allshifts,repeat=n)) if tuples is None else [tuple(rng.choice(allshifts) for _ in range(n)) for _ in range(tuples)]
        pairs=[(i,j) for i in range(n) for j in range(i,n)];sym=[]
        for vals in product(range(M//2),repeat=len(pairs)):
            A=[[0]*n for _ in range(n)]
            for (i,j),a in zip(pairs,vals):A[i][j]=A[j][i]=a
            sym.append(tuple(map(tuple,A)))
        for shifts in pool:
            rows=[sum((s[k]&1)<<k for k in range(n)) for s in shifts];rank=0   # rank over F_2 by elimination on bit rows
            for col in range(n):
                pivot=next((r for r in range(rank,n) if rows[r]>>col&1),None)
                if pivot is None:continue
                rows[rank],rows[pivot]=rows[pivot],rows[rank]
                for r in range(n):
                    if r!=rank and rows[r]>>col&1:rows[r]^=rows[rank]
                rank+=1
            read=lambda A:tuple(tuple(sum(2*A[i][k]*s[k] for k in range(n))%M for i in range(n)) for s in shifts)
            distinct=len({read(A) for A in sym})
            if rank<n:
                N,v=shift_blind_pair(list(shifts),bits,n);square['singular']+=1
                t.check(any(N[i][j]%(M//2) for i in range(n) for j in range(n)) and read(N)==read(zero) and distinct<len(sym),'classical_complexity',('singular mod 2: blind pair',bits,n))
                t.control(not same_function(N,(0,)*n,zero,(0,)*n,bits),'classical_complexity',('singular mod 2: blind pair differs',bits,n))
            else:
                square['invertible']+=1
                try:shift_blind_pair(list(shifts),bits,n);raised=False
                except ValueError:raised=True
                t.check(raised and distinct==len(sym),'classical_complexity',('invertible mod 2: readings separate',bits,n))
    report['classical_complexity']=dict(cases=classical,four_point_sets_failing_at_4_2=failing,shift_blind_tuples=blind,shift_square_tuples=square,
        quantum_fewer_than_exact_classical_iff='n >= 3 (2n+1 < n(n+3)/2); tie at n = 2; worse at n = 1; independent of M >= 4')
    t.check(any(not row['quantum_fewer_than_classical_bound'] for row in quantum),'quadratic_layer_reading','no separation at small n is recorded')
    t.check(any(row['quantum_fewer_than_classical_bound'] for row in quantum),'quadratic_layer_reading','separation against the counting bound at n=4, bits=3')
    t.check([row['quantum_fewer_than_classical_complexity'] for row in quantum]==[row['registers']>=3 for row in quantum],'quadratic_layer_reading','separation against the exact classical complexity iff n >= 3')
    for bits in (2,3):   # negative control: a wrong representative does not define the same function
        M=1<<bits
        for a in range(M):
            Ac,bc=canonical(((a,),),(0,),bits);t.control(not same_function(((a,),),(0,),Ac,((bc[0]+1)%M,),bits),'quadratic_layer_classes',(bits,a))
    report['quadratic_layer']=quantum

    report.update(exact_checks=t.checks,negative_controls=t.controls,sections=t.sections,seconds=round(time.perf_counter()-start,3),
                  statements_proved_here=False,proof_location='native_relational_qc/JET_READINGS_2.md')
    # New source-bound evidence; preserve the earlier collaborator snapshot.
    out=ROOT/'native_relational_qc'/'jet_readings'/'integration_20261030';out.mkdir(parents=True,exist_ok=True)
    text=json.dumps(report,indent=1,sort_keys=True);(out/'qualification2.json').write_text(text+'\n')
    stable=json.loads(text);stable.pop('seconds')
    for row in stable['quadratic_layer']:row.pop('seconds')
    (out/'EXPECTED2.sha256').write_text(hashlib.sha256(json.dumps(stable,sort_keys=True).encode()).hexdigest()+'  qualification2.json without the seconds fields\n')
    print(f"exact checks {t.checks}, negative controls {t.controls}, {report['seconds']} s -> {out/'qualification2.json'}")


if __name__=='__main__':main()
