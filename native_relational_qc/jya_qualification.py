"""Source-pinned exact jya/frame comparison, including linear-fusion ablation.

Workers use identical circuits, queries and budgets in fresh processes.
Reference answers use direct local products/analytic GHZ identities or the
unchanged exact Pauli-expansion engine, never the new recurrence evaluator.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from .calculator import _digest
from .exact import ONE,ZERO,HALF,IMAG,exact_gate
from .large_register import LargeCircuit
from .compact import ResourceLimit

ROOT=Path(__file__).resolve().parent.parent
STRATEGIES=('clifford_frame','linear_fusion','jya_frame')
PAIRED=('local_512','ghz_2056_global_256','ghz_2056_full_64',
        'changing_returns','independent_t_12','clifford_only_2056')
GUARDS=('branch_limit','coefficient_limit','pair_limit','work_limit','wall_limit')


def source_hashes():
    paths=sorted((ROOT/'native_relational_qc').glob('*.py'))
    paths+=[ROOT/'tests/test_native_jya_frame.py',ROOT/'tests/test_native_clifford_frame.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def case_input(case):
    n=2056 if '2056' in case else (12 if case=='independent_t_12' else
          14 if case=='branch_limit' else 3 if case=='changing_returns' else 2 if case=='pair_limit' else 1)
    c=LargeCircuit(n);limits={};kind='expectation';target={0:'Y'}
    if '2056' in case:
        c.add('h',0)
        for q in range(n-1):c.add('cx',q,q+1)
        target={q:'X' for q in range(n)}
    if case in ('local_512','ghz_2056_global_256','ghz_2056_full_64',
                'coefficient_limit','pair_limit','work_limit','wall_limit'):
        count={'local_512':512,'ghz_2056_global_256':256,'ghz_2056_full_64':64,
               'coefficient_limit':512,'pair_limit':64,'work_limit':32,'wall_limit':32}[case]
        for _ in range(count):c.add('h',0).add('t',0)
        if case=='ghz_2056_full_64':kind='probability';target={q:0 for q in range(n)}
        if case=='pair_limit':c.add('h',1);kind='probability';target={1:0};limits={'max_pairs':1}
        if case=='coefficient_limit':limits={'max_coefficient_bits':64}
        if case=='work_limit':limits={'max_work':1}
    elif case in ('independent_t_12','branch_limit'):
        for q in range(n):c.add('h',q).add('t',q)
        target={q:'X' for q in range(n)}
    elif case=='changing_returns':
        for layer in range(3):
            for q in range(3):
                for _ in range(4):c.add('h' if (q+layer)%2 else 'sx',q).add('t' if layer%2 else 'tdg',q)
                c.add('cx',q,(q+1)%3)
        kind='probability';target={0:1,1:0,2:1}
    return c,kind,target,limits


def semantic(case):
    c,kind,target,limits=case_input(case)
    return dict(n_qubits=c.n_qubits,operations=[[name,list(qs)] for name,qs in c.operations],
                kind=kind,target={str(k):v for k,v in target.items()},limits=limits)


def _linear_local(count):
    m=((ONE,ZERO),(ZERO,ONE))
    for _ in range(count):
        for name in ('h','t'):
            gate=exact_gate(name)
            m=tuple(tuple(sum((gate[i][k]*m[k][j] for k in range(2)),ZERO)
                          for j in range(2)) for i in range(2))
    return m


def reference(case):
    if case in GUARDS:return None
    if case=='clifford_only_2056':return ONE
    if case=='independent_t_12':return HALF**6
    if case=='changing_returns':
        from .clifford_t import probability
        c,_,target,_=case_input(case)
        return probability(c,target).value
    count={'local_512':512,'ghz_2056_global_256':256,'ghz_2056_full_64':64}[case]
    matrix=_linear_local(count)
    if case=='ghz_2056_full_64':return matrix[0][0].norm2()*HALF
    if case=='local_512':
        a,b=matrix[0][0],matrix[1][0]
        return IMAG*(b.conjugate()*a-a.conjugate()*b)
    term=matrix[0][0].conjugate()*matrix[1][1]+matrix[1][0].conjugate()*matrix[0][1]
    return (term+term.conjugate())*HALF


def prepare():
    cases=[]
    for case in PAIRED+GUARDS:
        value=reference(case)
        for strategy in STRATEGIES if case in PAIRED else ('jya_frame',):
            cases.append(dict(case=case,strategy=strategy,semantic_sha256=_digest(semantic(case)),
                timeout_seconds=1e-9 if case=='wall_limit' else 20,
                expected_exact=None if value is None else value.to_dict()))
    return dict(schema='nrqc-jya-protocol-v1',author='Monty',repetitions=3,
        baseline_commit='94df948d0bfac2d9683b6b5c87bb9fb6eac8a3a5',
        created_utc=datetime.now(timezone.utc).isoformat(),source_sha256=source_hashes(),cases=cases,
        frozen_before_measured_runs=True,
        selection='Structured repeated local words, entangled GHZ, changing returns, sparse-phase and Clifford controls; selected after correctness tests, before paired timing.',
        comparison='Fresh-process wall time and peak RSS; identical circuits/queries and 10M work,4096 coefficient-bit,4096 branch,1M pair,2056 generator caps unless explicit guard override. Work units differ by algorithm.',
        ablation='linear_fusion uses the same local blocks, Pauli expansion and readout but multiplies every local gate without recurrence.',
        references='Independent sequential 2x2 products plus analytic GHZ/Y identities; unchanged clifford_t exact expansion for changing_returns; analytic 1/64 and 1 for controls.',
        scope='Ideal classical simulation of selected observations; no hardware, noise, universal complexity or quantum advantage claim.')


def worker(case,strategy):
    from . import clifford_frame as frame,jya_frame as jya
    from .pauli_engine import compile_plan,_word
    c,kind,target,limits=case_input(case)
    start=time.perf_counter();report=dict(case=case,strategy=strategy,semantic_sha256=_digest(semantic(case)))
    try:
        if strategy=='linear_fusion':
            options=dict(max_work=10_000_000,max_coefficient_bits=4096,max_branches=4096,
                         max_pairs=1_000_000,max_generators=2056,progress=None)
            options.update(limits);plan=compile_plan(c,True)
            budget=jya._Budget(c,*options.values())
            budget.stats['backend']='linear_fusion'
            cliffords,amplitudes=jya._prepare(plan,budget,fold=False)
            if kind=='expectation':
                x,z=_word(target,c.n_qubits);budget.stats['query_support']=(x|z).bit_count()
                result=frame._expectation(cliffords,amplitudes,x,z,budget)
            else:
                budget.stats.update(query_support=len(target),measurement_generators=len(target),projector_expansion_avoided=True)
                result=frame._probability(cliffords,amplitudes,target,budget)
        else:
            backend=frame if strategy=='clifford_frame' else jya
            result=getattr(backend,kind)(c,target,**limits)
        report.update(status='completed',value=result.value.to_dict(),statistics=result.statistics)
    except ResourceLimit as error:
        report.update(status='resource_limit',error=str(error),statistics=getattr(error,'statistics',{}))
    report['execution_seconds']=time.perf_counter()-start
    report['peak_rss_bytes']=next(int(line.split()[1])*1024 for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('VmHWM:'))
    return report


def run(protocol,out):
    if source_hashes()!=protocol['source_sha256']:raise ValueError('source changed after protocol freeze')
    data=dict(schema='nrqc-jya-results-v1',protocol_sha256=_digest(protocol),python=sys.version,
              platform=platform.platform(),runs=[],started_utc=datetime.now(timezone.utc).isoformat())
    for rep in range(1,protocol['repetitions']+1):
        for row in protocol['cases']:
            start=time.perf_counter()
            try:
                process=subprocess.run([sys.executable,'-m','native_relational_qc.jya_qualification',
                    '--worker',row['case'],row['strategy']],capture_output=True,text=True,timeout=row['timeout_seconds'])
                if process.returncode:raise RuntimeError(process.stderr)
                report=json.loads(process.stdout)
                if report['semantic_sha256']!=row['semantic_sha256']:raise AssertionError('circuit/query mismatch')
            except subprocess.TimeoutExpired:
                report=dict(status='time_limit',semantic_sha256=row['semantic_sha256'])
            report['wall_seconds']=time.perf_counter()-start
            if report['status']=='completed':
                if report['value']!=row['expected_exact']:raise AssertionError('exact reference mismatch')
            elif 'value' in report:raise AssertionError('failure returned a value')
            if row['case'] in GUARDS:
                wanted='time_limit' if row['case']=='wall_limit' else 'resource_limit'
                if report['status']!=wanted:raise AssertionError('guard did not reject')
            data['runs'].append(dict(case=row['case'],strategy=row['strategy'],repetition=rep,
                                    exact_or_fail_closed_verified=True,report=report))
            out.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
            print(f"{rep} {row['case']} {row['strategy']}: {report['status']} {report['wall_seconds']:.4f}s",flush=True)
    summaries=[]
    for row in protocol['cases']:
        reports=[r['report'] for r in data['runs'] if (r['case'],r['strategy'])==(row['case'],row['strategy'])]
        rss=[r['peak_rss_bytes'] for r in reports if 'peak_rss_bytes' in r]
        summaries.append(dict(case=row['case'],strategy=row['strategy'],statuses=[r['status'] for r in reports],
            median_wall_seconds=statistics.median(r['wall_seconds'] for r in reports),
            maximum_peak_rss_bytes=max(rss) if rss else None))
    data.update(summaries=summaries,completed_utc=datetime.now(timezone.utc).isoformat(),all_runs_verified=True)
    out.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',action='store_true');action.add_argument('--run',action='store_true')
    action.add_argument('--worker',nargs=2)
    parser.add_argument('--protocol',type=Path,default=ROOT/'native_relational_qc/jya_protocol.json')
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    if args.worker:print(json.dumps(worker(*args.worker),sort_keys=True));return
    if args.out is None:parser.error('--out is required')
    if args.prepare:args.out.write_text(json.dumps(prepare(),indent=2,sort_keys=True)+'\n')
    else:run(json.loads(args.protocol.read_text()),args.out)


if __name__=='__main__':main()
