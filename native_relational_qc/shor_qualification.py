"""Frozen, paired small-Shor calculator qualification; no hardware jobs."""
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
from .exact import Exact
from .shor import build,assess,exact_phase_law

ROOT=Path(__file__).resolve().parent.parent
BACKENDS=('clifford_frame','jya_frame')
CASES={
    '15_rotation':(15,2,'rotation15',True,'1/2','3/4'),
    '15_table':(15,2,'table',True,'1/2','3/4'),
    '15_base7':(15,7,'table',True,'1/2','3/4'),
    '21_table':(21,2,'table',True,'0','1/4'),
    '15_trivial_gcd':(15,14,'table',True,'0','0'),
    '15_no_qft':(15,2,'rotation15',False,'1/4','5/8'),
}


def source_hashes():
    paths=sorted((ROOT/'native_relational_qc').glob('*.py'))
    paths+=[ROOT/'tests/test_native_shor.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def program_for(case):
    n,a,oracle,iqft,*_=CASES[case]
    return build(n,a,precision=3,oracle=oracle,inverse_qft=iqft)


def prepare():
    rows=[]
    for case,values in CASES.items():
        p=program_for(case);requests={b:p.request(b) for b in BACKENDS}
        semantic=dict(requests[BACKENDS[0]]);semantic.pop('backend')
        rows.append(dict(case=case,program=p.metadata(),semantic_sha256=_digest(semantic),
            requests=requests,request_sha256={b:_digest(validate(d)[1]) for b,d in requests.items()},
            expected_probabilities={str(y):v.to_dict() for y,v in exact_phase_law(
                p.modulus,p.base,p.precision,inverse_qft=p.inverse_qft).items()},
            expected_success={policy:Exact(Fraction(value)).to_dict() for policy,value in zip(
                ('convergents_only','convergents_and_doubles'),values[-2:])}))
    return dict(schema='nrqc-shor-protocol-v1',author='Monty',repetitions=3,
        baseline_commit='fcc53d49098ddc86a2eee098dc3d9c6f6ce44133',
        created_utc=datetime.now(timezone.utc).isoformat(),source_sha256=source_hashes(),
        timeout_seconds=20,cases=rows,backends=list(BACKENDS),
        frozen_before_paired_timing=True,
        prior_observations='Correctness tests and one N=15 rotation/jya pilot preceded this freeze; pilot retained separately. No claim of blind preregistration.',
        selection='Six fixed cases: structured modular multiplier, equivalent truth-table oracle, second base, non-power-of-two period, trivial-gcd control, no-QFT control.',
        ordering='Serial fresh workers; backend order alternates by repetition and case. Same circuits, readouts and default limits.',
        budgets='20 seconds per whole eight-outcome batch; per scalar 10M work,4096 coefficient bits,4096 branches,1M pairs,2056 generators. No hard RSS cap.',
        guards='After timed cases, max_work=1 and timeout=1e-9 once for each backend; failures must return no assessment/factors.',
        interpretation='Fixed-base ideal single-readout success, not sampled hardware success. Doubled denominators are an explicit bounded classical candidate rule. Three-bit precision is not general Shor precision.',
        reference='Direct exact finite Fourier sum of f(x)=pow(a,x,N), independent of circuit lowering and simulator. Separate full-state Qiskit test checks amplitudes including phase.')


def run(protocol,out):
    if source_hashes()!=protocol['source_sha256']:raise ValueError('source changed after protocol freeze')
    data=dict(schema='nrqc-shor-results-v1',protocol_sha256=_digest(protocol),
        python=sys.version,platform=platform.platform(),started_utc=datetime.now(timezone.utc).isoformat(),
        runs=[],assessments={},guards=[])
    def save():out.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    for repetition in range(1,protocol['repetitions']+1):
        for index,row in enumerate(protocol['cases']):
            p=program_for(row['case'])
            for backend in BACKENDS if (repetition+index)%2 else tuple(reversed(BACKENDS)):
                request=row['requests'][backend]
                semantic=dict(request);semantic.pop('backend')
                if _digest(semantic)!=row['semantic_sha256']:raise AssertionError('semantic mismatch')
                report=run_calculation(request,timeout_seconds=protocol['timeout_seconds'])
                if report.get('request_sha256')!=row['request_sha256'][backend]:raise AssertionError('request mismatch')
                assessment=assess(p,report)
                if assessment['status']=='verified':
                    for policy,result in assessment['policies'].items():
                        if result['exact_success_probability']!=row['expected_success'][policy]:
                            raise AssertionError('success probability mismatch')
                    actual={str(int(label,2)):value['exact'] for label,value in report['answers'][0]['probabilities'].items()}
                    if actual!=row['expected_probabilities']:raise AssertionError('frozen Fourier reference mismatch')
                    previous=data['assessments'].setdefault(row['case'],assessment)
                    if previous!=assessment:raise AssertionError('paired assessment mismatch')
                data['runs'].append(dict(case=row['case'],backend=backend,repetition=repetition,
                    assessment_status=assessment['status'],report=report))
                save()
                print(f"{repetition} {row['case']} {backend}: {report['status']} {report['wall_seconds']:.4f}s",flush=True)
    for backend in BACKENDS:
        for guard in ('work','wall'):
            p=program_for('15_rotation');request=p.request(backend)
            if guard=='work':request['limits']={'max_work':1}
            report=run_calculation(request,timeout_seconds=1e-9 if guard=='wall' else 20)
            assessment=assess(p,report)
            wanted='time_limit' if guard=='wall' else 'incomplete'
            if report['status']!=wanted or assessment['status']!='unavailable':raise AssertionError('guard failed')
            if any('probabilities' in answer for answer in report['answers']):raise AssertionError('guard exposed partial distribution')
            data['guards'].append(dict(backend=backend,guard=guard,report=report,assessment=assessment))
            save()
    summaries=[]
    for row in protocol['cases']:
        for backend in BACKENDS:
            reports=[r['report'] for r in data['runs'] if r['case']==row['case'] and r['backend']==backend]
            rss=[r['peak_worker_rss_bytes'] for r in reports if 'peak_worker_rss_bytes' in r]
            summaries.append(dict(case=row['case'],backend=backend,statuses=[r['status'] for r in reports],
                median_wall_seconds=statistics.median(r['wall_seconds'] for r in reports),
                maximum_peak_worker_rss_bytes=max(rss) if rss else None))
    data.update(summaries=summaries,completed_utc=datetime.now(timezone.utc).isoformat(),
        all_completed_answers_verified=True,all_guards_verified=True,
        completed_runs=sum(r['report']['status']=='completed' for r in data['runs']),
        unsuccessful_runs=sum(r['report']['status']!='completed' for r in data['runs']))
    save()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',action='store_true');action.add_argument('--run',action='store_true')
    parser.add_argument('--protocol',type=Path,default=ROOT/'native_relational_qc/shor_protocol.json')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.prepare:args.out.write_text(json.dumps(prepare(),indent=2,sort_keys=True)+'\n')
    else:run(json.loads(args.protocol.read_text()),args.out)


if __name__=='__main__':main()
