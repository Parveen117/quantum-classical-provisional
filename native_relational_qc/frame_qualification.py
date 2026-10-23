"""Frozen paired Clifford-frame qualification, with analytic exact references.

Author: Monty. Each case uses 2056 sites and fresh bounded calculator workers.
No expected answer is obtained by executing either compared backend.
"""
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
from .exact import Exact,ONE,ZERO,HALF,INV_SQRT2

N=2056
ROOT=Path(__file__).resolve().parent.parent
PAIRED=('ghz_t_full','ghz_x_interference_full','ghz_y_t_full','ghz_y_tdg_full',
        'six_t_full','six_t_global','twelve_t_global','twelve_t_local')
GUARDS=('branch_limit','pair_limit','coefficient_limit','work_limit','generator_limit','wall_limit')


def source_hashes():
    files=sorted((ROOT/'native_relational_qc').glob('*.py'))
    files += [ROOT/'tests/test_native_clifford_frame.py',ROOT/'tests/test_native_large_register.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def request(case,backend):
    operations=[['h',[0]]]+[['cx',[q,q+1]] for q in range(N-1)]
    limits={};kind='probability';target={str(q):0 for q in range(N)}
    if case in ('ghz_t_full','ghz_x_interference_full','ghz_y_t_full','ghz_y_tdg_full',
                'coefficient_limit','work_limit','generator_limit','wall_limit'):
        operations.append(['tdg' if case=='ghz_y_tdg_full' else 't',[0]])
        if case in ('ghz_y_t_full','ghz_y_tdg_full'):operations.append(['sdg',[0]])
        if case in ('ghz_x_interference_full','ghz_y_t_full','ghz_y_tdg_full','coefficient_limit'):
            operations += [['h',[q]] for q in range(N)]
        if case=='coefficient_limit':limits={'max_coefficient_bits':64}
        if case=='work_limit':limits={'max_work':8}
        if case=='generator_limit':limits={'max_generators':8}
    else:
        active=12 if case in ('twelve_t_global','twelve_t_local','branch_limit') else 6
        operations=[['h',[q]] for q in range(N)]
        for q in range(active):operations += [['t',[q]],['h',[q]]]
        if case in ('six_t_global','twelve_t_global','branch_limit'):
            kind='expectation';target={str(q):'Z' if q<active else 'X' for q in range(N)}
        elif case=='twelve_t_local':kind='expectation';target={'2055':'Z'}
        elif case=='pair_limit':target={'2055':0};limits={'max_pairs':128}
        if case=='branch_limit':limits={'max_branches':128}
    return dict(schema='nrqc-calculator-v1',n_qubits=N,operations=operations,
                backend=backend,limits=limits,decimal_places=16,
                queries=[dict(id=case,kind=kind,**{'paulis' if kind=='expectation' else 'outcomes':target})])


def expected(case):
    if case=='ghz_t_full':return HALF
    if case in ('ghz_x_interference_full','ghz_y_t_full'):
        return (ONE+INV_SQRT2)*Exact(Fraction(1,1<<N))
    if case=='ghz_y_tdg_full':return (ONE-INV_SQRT2)*Exact(Fraction(1,1<<N))
    if case=='six_t_full':return (ONE+INV_SQRT2)**6*Exact(Fraction(1,1<<N))
    if case=='six_t_global':return Exact(Fraction(1,8))
    if case=='twelve_t_global':return Exact(Fraction(1,64))
    if case=='twelve_t_local':return ZERO
    return None


def prepare():
    rows=[]
    for case in PAIRED+GUARDS:
        for backend in (('clifford_t','clifford_frame') if case in PAIRED else ('clifford_frame',)):
            document=request(case,backend);_,canonical=validate(document)
            value=expected(case)
            if case=='wall_limit':allowed=['time_limit']
            elif case in GUARDS:allowed=['incomplete']
            elif backend=='clifford_t' and case.endswith('_full'):allowed=['incomplete']
            elif backend=='clifford_t' and case=='twelve_t_global':allowed=['completed','time_limit']
            else:allowed=['completed']
            rows.append(dict(case=case,backend=backend,request_sha256=_digest(canonical),
                semantic_sha256=_digest({k:document[k] for k in ('n_qubits','operations','queries')}),
                timeout_seconds=1e-9 if case=='wall_limit' else 20,
                allowed_statuses=allowed,expected_exact=value.to_dict() if value is not None else None))
    return dict(schema='nrqc-frame-protocol-v1',author='Monty',created_utc=datetime.now(timezone.utc).isoformat(),
                baseline_commit='d0b87fca3d7d1667c26ac4e1ed7e5bb7f6c62820',n_qubits=N,repetitions=3,
                source_sha256=source_hashes(),cases=rows,protocol_frozen_before_measured_runs=True,
                ordering='round-robin case order, old then frame for paired cases',
                pilot_note='Unit/regression tests and an unmeasured 12-T frame smoke informed case selection; no paired benchmark runs preceded this freeze.',
                comparison='same ideal circuit and scalar query, default applicable work/coefficient/representation limits and 20-second wall cap; different algorithms count different work units',
                scope='bounded exact ideal selected observations; no physical quantum execution or universal T-depth efficiency claim')


def check(case,report):
    if report['request_sha256']!=case['request_sha256']:raise AssertionError('request hash mismatch')
    if report['status'] not in case['allowed_statuses']:raise AssertionError('unexpected status: '+report['status'])
    if report['status']=='time_limit':
        if report['answers']:raise AssertionError('timeout returned a partial batch')
        return
    if report['n_qubits']!=N:raise AssertionError('wrong width')
    answer=report['answers'][0]
    if report['status']=='incomplete':
        if answer['status']!='resource_limit' or 'value' in answer:raise AssertionError('resource failure returned value')
    elif answer['value']['exact']!=case['expected_exact']:
        raise AssertionError('exact reference mismatch')


def run(protocol,out):
    if protocol['source_sha256']!=source_hashes():raise ValueError('source changed after protocol freeze')
    result=dict(schema='nrqc-frame-results-v1',author='Monty',protocol_sha256=_digest(protocol),
                python=sys.version,platform=platform.platform(),started_utc=datetime.now(timezone.utc).isoformat(),runs=[])
    for repetition in range(protocol['repetitions']):
        for case in protocol['cases']:
            report=run_calculation(request(case['case'],case['backend']),timeout_seconds=case['timeout_seconds'])
            row=dict(case=case['case'],backend=case['backend'],repetition=repetition+1,report=report)
            result['runs'].append(row)
            out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
            check(case,report);row['expected_outcome_verified']=True
            print(f"{repetition+1} {case['case']} {case['backend']}: {report['status']} {report['wall_seconds']:.6f}s",flush=True)
    summaries=[]
    for case in protocol['cases']:
        reports=[r['report'] for r in result['runs'] if r['case']==case['case'] and r['backend']==case['backend']]
        rss=[r['peak_worker_rss_bytes'] for r in reports if r.get('peak_worker_rss_bytes') is not None]
        summaries.append(dict(case=case['case'],backend=case['backend'],statuses=[r['status'] for r in reports],
            median_wall_seconds=statistics.median(r['wall_seconds'] for r in reports),
            wall_seconds_range=[min(r['wall_seconds'] for r in reports),max(r['wall_seconds'] for r in reports)],
            maximum_peak_worker_rss_bytes=max(rss) if rss else None))
    result.update(summaries=summaries,completed_utc=datetime.now(timezone.utc).isoformat(),all_expected_outcomes_verified=True)
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',action='store_true');action.add_argument('--run',action='store_true')
    action.add_argument('--example',choices=PAIRED+GUARDS)
    parser.add_argument('--backend',choices=('clifford_t','clifford_frame'),default='clifford_frame')
    parser.add_argument('--protocol',type=Path,default=ROOT/'native_relational_qc/frame_protocol.json')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.prepare:value=prepare()
    elif args.example:value=request(args.example,args.backend)
    else:
        run(json.loads(args.protocol.read_text()),args.out);return
    args.out.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':main()
