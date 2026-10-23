"""Source-pinned phase-extension qualification and Shor precision comparison."""
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
from .cyclotomic import Cyclotomic as C,ZETA,ONE
from .phase_backend import PhaseCircuit
from .shor import build,assess,exact_phase_law

ROOT=Path(__file__).resolve().parent.parent
CASES={
 '15_rotation_3':(15,2,3,'rotation15',True),
 '21_table_3':(21,2,3,'table',True),
 '15_rotation_4':(15,2,4,'rotation15',True),
 '15_table_4':(15,2,4,'table',True),
 '21_table_4':(21,2,4,'table',True),
 '15_trivial_4':(15,14,4,'table',True),
 '21_no_qft_4':(21,2,4,'table',False),
}


def hashes():
    paths=sorted((ROOT/'native_relational_qc').glob('*.py'))
    paths += [ROOT/'tests/test_native_cyclotomic.py',ROOT/'tests/test_native_shor.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def program(case):
    n,a,m,oracle,iqft=CASES[case]
    return build(n,a,precision=m,oracle=oracle,inverse_qft=iqft)


def prepare_protocol():
    cases=[]
    for case in CASES:
        p=program(case)
        backends=('clifford_frame','jya_frame','cyclotomic') if p.precision==3 else ('cyclotomic',)
        cases.append(dict(case=case,program=p.metadata(),requests={b:p.request(b) for b in backends},
            expected={str(y):C.coerce(v).to_dict() for y,v in exact_phase_law(
                p.modulus,p.base,p.precision,inverse_qft=p.inverse_qft).items()}))
    phase=dict(schema='nrqc-calculator-v1',n_qubits=1,backend='cyclotomic',
        operations=[['h',[0]],['p16',[0]],['h',[0]]],queries=[dict(id='phase',kind='distribution',qubits=[0])])
    value=(ONE+(ZETA+ZETA.conjugate())*Fraction(1,2))*Fraction(1,2)
    cases.append(dict(case='phase16_interference',requests={'cyclotomic':phase},
                      expected={'0':value.to_dict(),'1':(ONE-value).to_dict()}))
    for row in cases:
        row['request_sha256']={b:_digest(validate(d)[1]) for b,d in row['requests'].items()}
    return dict(schema='nrqc-phase16-protocol-v1',author='Monty',baseline_commit='cfabd608b6dc28b1640a507bba4716c7de30e6c0',
        created_utc=datetime.now(timezone.utc).isoformat(),source_sha256=hashes(),cases=cases,
        repetitions=3,timeout_seconds=20,frozen_before_paired_timing=True,
        prior_observations='Unit tests and one 21/table/4-bit cyclotomic pilot preceded freeze. Not blind preregistration.',
        ordering='Serial fresh workers; backend ordering reverses on alternate repetitions.',
        limits='All default limits. Whole-batch wall 20s. Cyclotomic work/branch/bit budgets apply to one shared preparation and every readout; old frame scalar budgets reset per outcome. No hard RSS cap.',
        comparison='Same three-bit circuits on all backends; four-bit circuits require the new backend. Timings combine number field, representation and preparation reuse; no isolated arithmetic or quantum speedup claim.',
        references='Independent exact finite Fourier sum, with separate full-state Qiskit/formula tests. H-P16-H uses analytic (1+cos(pi/8))/2.',
        guards='One each: support overflow, coefficient bits, work, and deliberate wall timeout; whole batch must return no answers.')


def run(protocol,out):
    if hashes()!=protocol['source_sha256']:raise ValueError('source changed after protocol freeze')
    data=dict(schema='nrqc-phase16-results-v1',protocol_sha256=_digest(protocol),python=sys.version,
        platform=platform.platform(),started_utc=datetime.now(timezone.utc).isoformat(),runs=[],assessments={},guards=[])
    def save():out.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    for repetition in range(1,protocol['repetitions']+1):
        for row in protocol['cases']:
            backends=list(row['requests'])
            if repetition%2==0:backends.reverse()
            for backend in backends:
                r=run_calculation(row['requests'][backend],timeout_seconds=protocol['timeout_seconds'])
                if r.get('request_sha256')!=row['request_sha256'][backend]:raise AssertionError('input digest mismatch')
                if r['status']=='completed':
                    probabilities=r['answers'][0]['probabilities']
                    values={str(int(label,2)):C.from_dict(v['exact']).to_dict() for label,v in probabilities.items()}
                    if values!=row['expected']:raise AssertionError('independent exact reference mismatch')
                    if backend=='cyclotomic' and r['statistics']['preparation_count']!=1:raise AssertionError('state preparation was not reused')
                    if row['case'] in CASES:
                        assessment=assess(program(row['case']),r)
                        # Different field serializations remain explicit; compare canonical values below.
                        data['assessments'].setdefault(row['case'],{})[backend]=assessment
                data['runs'].append(dict(case=row['case'],backend=backend,repetition=repetition,report=r))
                save();print(f"{repetition} {row['case']} {backend}: {r['status']} {r['wall_seconds']:.4f}s",flush=True)
    for guard in ('support','coefficient','work','wall'):
        c=PhaseCircuit(13 if guard=='support' else 3)
        for q in range(c.n_qubits):c.add('h',q)
        request=dict(schema='nrqc-calculator-v1',n_qubits=c.n_qubits,backend='cyclotomic',
            operations=[[name,list(qs)] for name,qs in c.operations],
            queries=[dict(id='p',kind='probability',outcomes={'0':0})])
        if guard=='coefficient':request['limits']={'max_coefficient_bits':2}
        if guard=='work':request['limits']={'max_work':1}
        r=run_calculation(request,timeout_seconds=1e-9 if guard=='wall' else 20)
        if r['status']!=('time_limit' if guard=='wall' else 'incomplete') or r['answers']:
            raise AssertionError('resource guard did not fail closed')
        data['guards'].append(dict(guard=guard,report=r));save()
    summaries=[]
    for row in protocol['cases']:
        for backend in row['requests']:
            reports=[r['report'] for r in data['runs'] if r['case']==row['case'] and r['backend']==backend]
            rss=[r['peak_worker_rss_bytes'] for r in reports if r.get('peak_worker_rss_bytes') is not None]
            summaries.append(dict(case=row['case'],backend=backend,statuses=[r['status'] for r in reports],
                median_wall_seconds=statistics.median(r['wall_seconds'] for r in reports),
                maximum_peak_worker_rss_bytes=max(rss) if rss else None))
    for case,backends in data['assessments'].items():
        policies={}
        for backend,assessment in backends.items():
            for policy,result in assessment['policies'].items():
                v=C.from_dict(result['exact_success_probability'])
                if policy in policies and policies[policy]!=v:raise AssertionError('backend factor policy disagreement')
                policies[policy]=v
    data.update(summaries=summaries,completed_utc=datetime.now(timezone.utc).isoformat(),
        completed_runs=sum(r['report']['status']=='completed' for r in data['runs']),
        unsuccessful_runs=sum(r['report']['status']!='completed' for r in data['runs']),
        all_completed_answers_verified=True,all_guards_verified=True)
    save()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    a=p.add_mutually_exclusive_group(required=True);a.add_argument('--prepare',action='store_true');a.add_argument('--run',action='store_true')
    p.add_argument('--protocol',type=Path,default=ROOT/'native_relational_qc/phase_protocol.json')
    p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    if args.prepare:args.out.write_text(json.dumps(prepare_protocol(),indent=2,sort_keys=True)+'\n')
    else:run(json.loads(args.protocol.read_text()),args.out)


if __name__=='__main__':main()
