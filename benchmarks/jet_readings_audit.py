"""Exact witnesses for the readings-to-jet learner; synthetic declared energies, no hardware.

Every check compares exact rationals or exact flat-field elements. Checks and
negative controls are counted separately. Regression evidence only: the
statements in JET_READINGS.md are proved there, not here.
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
from native_relational_qc.jet_readings import (EXISTING_FIRST_LAYER_MODEL,SCHEMA,PolynomialEnergy,Reader,classify_first_layer,
    digest,first_layer_steps,ghost_energy,learn_jet,quadratic_phase_distribution,read_linear_layer)

PINNED=('native_relational_qc/jet_readings.py','native_relational_qc/phase_backend.py','native_relational_qc/cyclotomic_pow2.py',
        'native_relational_qc/shor.py','native_relational_qc/compact.py','tests/test_native_jet_readings.py')
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


def main():
    start=time.perf_counter();t=Tally();report=dict(schema=SCHEMA+'-audit',evidence_class='LOCAL_IDEAL_CALCULATION',
        hardware_jobs=0,source_blob_sha1={p:blob_sha1(p) for p in PINNED})

    # 1. The existing identity for the cubic family.
    for u,v in product(range(-7,8),repeat=2):
        if u and v:t.check(PolynomialEnergy.cubic(u,v).curvature((0,0))==Q(u*v,324),'cubic_identity',(u,v))

    # 2. Readings -> jet on the existing held-out test grid; existing frozen model fed from readings.
    rows=[];readings=set()
    for u,v in product(TEST_VALUES,repeat=2):
        energy=PolynomialEnergy.cubic(u,v);reader=Reader(energy);result=learn_jet(reader,(0,0))
        t.check(result['status']=='consistent_at_order_1','readings_to_jet',(u,v))
        t.check(result['jet']==energy.hessian_jet((0,0),1),'readings_to_jet',(u,v))
        t.check(first_layer_steps(result['jet'])==(16+2*u,16+2*v),'readings_to_jet',(u,v))
        predicted,p=classify_first_layer(result['jet']);label=int(Q(u*v,324)<0)
        t.check(predicted==label,'existing_model_from_readings',(u,v))
        readings.add(reader.readings)
        rows.append(dict(u=u,v=v,readings=reader.readings,requests=reader.requests,label=label,predicted=predicted,
                         probability_one=p.display(10)['decimal'],curvature_from_jet=str(result['jet'].curvature())))
    report['test_grid']=dict(cases=len(rows),readings_per_case=sorted(readings),existing_model=EXISTING_FIRST_LAYER_MODEL,rows=rows)

    # 3. Richer declared families: the learner finds the order and the exact jet.
    rng=random.Random(2026);rich=[]
    for degree in (2,3,4,5,6,7,8):
        for _ in range(6):
            energy=random_energy(rng,degree);order=degree-2;base=(Q(rng.randint(-2,2),3),Q(rng.randint(-2,2),4))
            reader=Reader(energy);result=learn_jet(reader,base,max_order=6)
            t.check(result['status']==f'consistent_at_order_{order}','richer_families',degree)
            t.check(result['jet']==energy.hessian_jet(base,order),'richer_families',degree)
            rich.append(dict(degree=degree,order=order,readings=reader.readings,base=[str(x) for x in base],
                             design_size=(order+1)*(order+2)//2,orders_falsified=[h['order'] for h in result['history'] if h['mismatches']]))
    report['richer_families']=rich

    # 4. Linear chart change: curvature invariant, first layer covariant, existing model chart-dependent.
    rng=random.Random(7);invariance=0
    while invariance<40:
        energy=random_energy(rng,rng.choice((3,4,5)));base=(Q(rng.randint(-2,2),3),Q(rng.randint(-2,2),5))
        A=((rng.randint(-3,3),rng.randint(-3,3)),(rng.randint(-3,3),rng.randint(-3,3)))
        if not A[0][0]*A[1][1]-A[0][1]*A[1][0]:continue
        try:kappa=energy.curvature(base)
        except ValueError:continue
        jet=energy.hessian_jet(base,2);moved=jet.transport(A)
        t.check(moved.curvature()==kappa,'chart_invariance',A)
        t.check(energy.compose_linear(A).hessian_jet(moved.base,2)==moved,'chart_invariance',A)
        if A!=((1,0),(0,1)) and A!=((-1,0),(0,-1)):t.control(moved.first_layer()!=jet.first_layer() or moved.hessian()!=jet.hessian(),'chart_invariance',A)
        invariance+=1
    shear=((1,1),(0,1));correct=invariant=cases=skipped=0
    for u,v in product(TEST_VALUES,repeat=2):
        jet=PolynomialEnergy.cubic(u,v).hessian_jet((0,0),1).transport(shear);label=int(Q(u*v,324)<0)
        try:predicted,_=classify_first_layer(jet)
        except ValueError:skipped+=1;continue
        cases+=1;correct+=predicted==label;invariant+=int(jet.curvature()<0)==label
    t.control(correct<cases,'existing_model_in_sheared_chart','accuracy must drop');t.check(invariant==cases,'existing_model_in_sheared_chart')
    report['sheared_chart']=dict(chart=shear,encodable_cases=cases,outside_encoding=skipped,existing_model_correct=correct,
                                 existing_model_accuracy=str(Q(correct,cases)),invariant_sign_correct=invariant)

    # 5. Ghost energies: same readings, same learned jet, different field elsewhere.
    elsewhere=(Q(1,41),Q(-1,43));ghosts=0
    for u,v in product(TEST_VALUES,repeat=2):
        energy=PolynomialEnergy.cubic(u,v);reader=Reader(energy);learned=learn_jet(reader,(0,0))
        ghost=ghost_energy(energy,list(reader.record),scale=Q(1,1000))
        for point,reading in reader.record.items():t.check(ghost.hessian(point)==reading,'ghost_energy',(u,v))
        twin=learn_jet(Reader(ghost),(0,0))
        t.check(twin['jet']==learned['jet'] and twin['status']==learned['status'],'ghost_energy',(u,v))
        t.control(ghost.hessian_jet(elsewhere,1)!=energy.hessian_jet(elsewhere,1),'ghost_energy',(u,v))
        t.control(ghost.curvature(elsewhere)!=energy.curvature(elsewhere),'ghost_energy',(u,v));ghosts+=1
    report['ghost_energies']=dict(cases=ghosts,ghost_hessian_degree=ghost.hessian_degree(),scale='1/1000',elsewhere=[str(x) for x in elsewhere])

    # 6. One-query quantum reading of a linear layer; quadratic negative control.
    quantum=[]
    for bits,n in ((3,1),(3,2),(2,3),(4,1),(2,4),(3,3)):
        M=1<<bits;peak=0;work=0;clock=time.perf_counter()
        for layer in product(range(M),repeat=n):
            distribution,stats=read_linear_layer(layer,bits);F=distribution[layer].__class__
            t.check({k:v for k,v in distribution.items() if v}=={layer:F(1)},'linear_layer_one_query',(bits,n,layer))
            peak=max(peak,stats['peak_branches']);work=max(work,stats['work_used'])
        quantum.append(dict(bits=bits,registers=n,layers_enumerated=M**n,qubits=bits*n,peak_branches=peak,max_work=work,
                            classical_readings_needed=n,quantum_queries=1,seconds=round(time.perf_counter()-clock,3)))
    report['linear_layer']=quantum
    controls=[]
    for bits in (2,3,4):
        M=1<<bits
        for a in range(1,M):
            for b in range(M):
                distribution=quadratic_phase_distribution(a,b,bits);F=next(iter(distribution.values())).__class__
                if a==M//2:t.check({k:v for k,v in distribution.items() if v}=={(a+b)%M:F(1)},'quadratic_layer',(a,b,bits));continue
                t.control(all((F(1)-p).real_sign()>0 for p in distribution.values()),'quadratic_layer',(a,b,bits))
                top=max(float(p.real_bounds(20)[1]) for p in distribution.values())
                controls.append(dict(bits=bits,a=a,b=b,max_probability_upper=round(top,6)))
    report['quadratic_layer']=dict(cases=len(controls),note='a=M/2 is a linear layer in disguise and is read exactly; every other a!=0 is not concentrated',
                                   max_probability_over_cases=max(c['max_probability_upper'] for c in controls))

    report.update(exact_checks=t.checks,negative_controls=t.controls,sections=t.sections,seconds=round(time.perf_counter()-start,3),
                  statements_proved_here=False,proof_location='native_relational_qc/JET_READINGS.md')
    out=ROOT/'native_relational_qc'/'jet_readings';out.mkdir(exist_ok=True)
    text=json.dumps(report,indent=1,sort_keys=True);(out/'qualification.json').write_text(text+'\n')
    stable=json.loads(text);stable.pop('seconds')
    for row in stable['linear_layer']:row.pop('seconds')
    (out/'EXPECTED.sha256').write_text(hashlib.sha256(json.dumps(stable,sort_keys=True).encode()).hexdigest()
                                      +'  qualification.json without the seconds fields\n')
    print(f"exact checks {t.checks}, negative controls {t.controls}, {report['seconds']} s -> {out/'qualification.json'}")


if __name__=='__main__':main()
