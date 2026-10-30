"""Pinned arithmetic-oracle/five-bit qualification; serial fresh workers."""
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys

from .calculator import _digest,run_calculation,validate
from .cyclotomic32 import Cyclotomic32 as C,ONE,ZETA
from .phase_backend import Phase32Circuit
from .shor import build,assess,exact_phase_law

ROOT=Path(__file__).resolve().parent.parent
CASES=[
    ('21_table_4',21,2,4,'table',True),
    ('21_arithmetic_4',21,2,4,'arithmetic',True),
    ('21_table_5',21,2,5,'table',True),
    ('21_arithmetic_5',21,2,5,'arithmetic',True),
    ('15_arithmetic_5',15,7,5,'arithmetic',True),
    ('35_arithmetic_5',35,2,5,'arithmetic',True),
    ('21_bad_base_5',21,20,5,'arithmetic',True),
    ('21_no_qft_5',21,2,5,'arithmetic',False),
]


def hashes():
    paths=sorted((ROOT/'native_relational_qc').glob('*.py'))
    paths += [ROOT/'tests'/name for name in ('test_native_modular_shor.py','test_native_cyclotomic.py','test_native_shor.py')]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def request(row):
    if row['case']=='phase32_interference':
        return dict(schema='nrqc-calculator-v1',n_qubits=1,backend='cyclotomic32',
            operations=[['h',[0]],['p32',[0]],['h',[0]]],
            queries=[dict(id='phase',kind='distribution',qubits=[0])])
    return build(**row['builder']).request(row['backend'])


def prepare_protocol():
    cases=[]
    for case,n,a,m,oracle,iqft in CASES:
        args=dict(modulus=n,base=a,precision=m,oracle=oracle,inverse_qft=iqft)
        cases.append(dict(case=case,builder=args,backend='cyclotomic32' if m==5 else 'cyclotomic',
            program=build(**args).metadata(),
            expected={str(y):C.coerce(v).to_dict() for y,v in exact_phase_law(n,a,m,inverse_qft=iqft).items()}))
    p=(ONE+(ZETA+ZETA.conjugate())*Fraction(1,2))*Fraction(1,2)
    cases.append(dict(case='phase32_interference',backend='cyclotomic32',expected={'0':p.to_dict(),'1':(ONE-p).to_dict()}))
    for row in cases:row['request_sha256']=_digest(validate(request(row))[1])
    return dict(schema='nrqc-modular-shor-protocol-v1',author='Monty',
        baseline_commit='f31a06a550c5abdb700d00177c5ea568e2cece3d',source_sha256=hashes(),cases=cases,
        frozen_utc=datetime.now(timezone.utc).isoformat(),repetitions=3,timeout_seconds=20,
        prior_observations='Unit tests and a retained N=21/arithmetic/five-bit pilot preceded freeze. Not blind preregistration.',
        ordering='Serial fresh workers; reverse case order on alternate repetitions.',
        request_contract='Requests regenerated from pinned source and builder arguments, then compared with frozen normalized request digests.',
        limits='Default support 4096, coefficient bits 4096, work 10M, whole batch wall 20s. No hard RSS cap.',
        comparison='Same N/base/precision/readout across table and arithmetic oracles; different registers and gates. Polynomial construction is not a simulator speedup claim. Both exact sparse backends use the new primitive permutation execution.',
        guards=['support','coefficient','work','wall'])


def run(protocol,out):
    if hashes()!=protocol['source_sha256']:raise ValueError('source changed after protocol freeze')
    data=dict(schema='nrqc-modular-shor-results-v1',protocol_sha256=_digest(protocol),python=sys.version,
        platform=platform.platform(),started_utc=datetime.now(timezone.utc).isoformat(),runs=[],assessments={},guards=[])
    def save():out.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    for repetition in range(1,protocol['repetitions']+1):
        rows=protocol['cases'] if repetition%2 else list(reversed(protocol['cases']))
        for row in rows:
            doc=request(row)
            if _digest(validate(doc)[1])!=row['request_sha256']:raise AssertionError('reconstructed request mismatch')
            report=run_calculation(doc,timeout_seconds=protocol['timeout_seconds'])
            if report['request_sha256']!=row['request_sha256']:raise AssertionError('worker input mismatch')
            if report['status']=='completed':
                values={str(int(label,2)):C.from_dict(v['exact']).to_dict() for label,v in report['answers'][0]['probabilities'].items()}
                if values!=row['expected']:raise AssertionError('exact independent Fourier reference mismatch')
                if report['statistics']['preparation_count']!=1:raise AssertionError('preparation repeated')
                if 'builder' in row:data['assessments'][row['case']]=assess(build(**row['builder']),report)
            data['runs'].append(dict(case=row['case'],repetition=repetition,report=report));save()
            print(f"{repetition} {row['case']}: {report['status']} {report['wall_seconds']:.4f}s",flush=True)
    for guard in protocol['guards']:
        c=Phase32Circuit(13 if guard=='support' else 3)
        for q in range(c.n_qubits):c.add('h',q)
        doc=dict(schema='nrqc-calculator-v1',n_qubits=c.n_qubits,backend='cyclotomic32',
            operations=[[name,list(qs)] for name,qs in c.operations],queries=[dict(id='p',kind='probability',outcomes={'0':0})])
        if guard=='coefficient':doc['limits']={'max_coefficient_bits':2}
        if guard=='work':doc['limits']={'max_work':1}
        r=run_calculation(doc,timeout_seconds=1e-9 if guard=='wall' else 20)
        if r['status']!=('time_limit' if guard=='wall' else 'incomplete') or r['answers']:raise AssertionError('guard exposed an answer')
        data['guards'].append(dict(guard=guard,report=r));save()
    summaries=[]
    for row in protocol['cases']:
        reports=[r['report'] for r in data['runs'] if r['case']==row['case']]
        rss=[r['peak_worker_rss_bytes'] for r in reports if r.get('peak_worker_rss_bytes') is not None]
        summaries.append(dict(case=row['case'],statuses=[r['status'] for r in reports],
            median_wall_seconds=statistics.median(r['wall_seconds'] for r in reports),
            maximum_peak_worker_rss_bytes=max(rss) if rss else None))
    data.update(summaries=summaries,completed_utc=datetime.now(timezone.utc).isoformat(),
        completed_runs=sum(r['report']['status']=='completed' for r in data['runs']),
        unsuccessful_runs=sum(r['report']['status']!='completed' for r in data['runs']),
        all_completed_answers_verified=True,all_guards_verified=True)
    save()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True);group.add_argument('--prepare',action='store_true');group.add_argument('--run',action='store_true')
    p.add_argument('--protocol',type=Path,default=ROOT/'native_relational_qc/modular_protocol.json')
    p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    if args.prepare:args.out.write_text(json.dumps(prepare_protocol(),indent=2,sort_keys=True)+'\n')
    else:run(json.loads(args.protocol.read_text()),args.out)


if __name__=='__main__':main()
