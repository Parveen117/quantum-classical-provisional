"""Pinned six-bit Shor and proof-traced rewrite comparison, serial workers."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter

from .calculator import calculate,validate,run_calculation,_digest
from .cyclotomic64 import Cyclotomic64 as C
from .shor import build,assess,exact_phase_law

ROOT=Path(__file__).resolve().parent.parent


def hashes():
    paths=sorted((ROOT/'native_relational_qc').glob('*.py'))
    paths+=sorted((ROOT/'tests').glob('test_native*.py'))
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def cases():
    rows=[]
    for n in (141,143,187):
        for precision,rewrite in ((5,'none'),(6,'none'),(6,'panini')):
            rows.append(dict(case=f'{n}_2_{precision}_{rewrite}',backend=f'cyclotomic{1<<precision}',
                builder=dict(modulus=n,base=2,precision=precision,oracle='arithmetic',rewrite=rewrite)))
    for case,base,iqft in (('141_bad_base',5,True),('141_no_qft',2,False)):
        rows.append(dict(case=case,backend='cyclotomic64',
            builder=dict(modulus=141,base=base,precision=6,oracle='arithmetic',rewrite='panini',inverse_qft=iqft)))
    return rows


def prepare_protocol():
    rows=cases();references={}
    for row in rows:
        args=row['builder'];p=build(**args);doc=p.request(row['backend'])
        key=(p.modulus,p.base,p.precision,p.inverse_qft)
        if key not in references:
            references[key]={str(y):C.coerce(v).to_dict() for y,v in
                exact_phase_law(p.modulus,p.base,p.precision,inverse_qft=p.inverse_qft).items()}
        row.update(program=p.metadata(),request_sha256=_digest(validate(doc)[1]),
            rewrite_certificate_sha256=_digest(p.rewrite_certificate) if p.rewrite_certificate else None,
            expected=references[key])
    return dict(schema='nrqc-phase64-protocol-v1',author='Monty',
        baseline_commit='51a936e270966dd1af9c4ed2f48493b5f72c93fe',source_sha256=hashes(),
        frozen_utc=datetime.now(timezone.utc).isoformat(),cases=rows,repetitions=3,timeout_seconds=60,
        ordering='Serial fresh workers; reverse all cases on alternate repetitions.',
        prior_observations='Earlier five-bit N=141 diagnostic, new unit tests, and gate-count inspection preceded this freeze. Not blind preregistration.',
        comparison='At six bits, same modulus/base/readout/backend/scratch, with and without the optional rewrite. Five-bit rows measure precision change separately.',
        timing='Worker wall includes startup, arithmetic synthesis, optional rewrite and proof verification, validation, exact execution and output. Independent reference/assessment runs in parent after timing.',
        limits='Default 4096 amplitudes, 4096 coefficient bits, 10M batch work; 60s whole worker wall. No hard RSS cap. Rewrite lookback 64 and 1M checks.',
        request_contract='No factor/order input; normalized request and deterministic rewrite proof digests frozen. All outcomes retained.',
        guards=['support','coefficient','work','wall'])


def worker(row):
    import resource
    start=perf_counter();p=build(**row['builder']);compiled=perf_counter()-start
    doc=p.request(row['backend']);report=calculate(doc)
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
    return dict(program=p.metadata(),compile_and_verify_seconds=compiled,report=report,
        peak_worker_rss_bytes=rss,rewrite_verified=p.rewrite=='panini',
        rewrite_certificate_sha256=_digest(p.rewrite_certificate) if p.rewrite_certificate else None,
        compact_certificate_bytes=len(json.dumps(p.rewrite_certificate,separators=(',',':')).encode()) if p.rewrite_certificate else 0)


def run(protocol,out):
    if hashes()!=protocol['source_sha256']:raise ValueError('source changed after protocol freeze')
    data=dict(schema='nrqc-phase64-results-v1',protocol_sha256=_digest(protocol),
        python=sys.version,platform=platform.platform(),started_utc=datetime.now(timezone.utc).isoformat(),
        runs=[],assessments={},guards=[])
    def save():out.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    for repetition in range(1,protocol['repetitions']+1):
        rows=protocol['cases'] if repetition%2 else list(reversed(protocol['cases']))
        for row in rows:
            start=perf_counter()
            try:
                proc=subprocess.run([sys.executable,'-m','native_relational_qc.phase64_qualification','--worker'],
                    input=json.dumps(row),text=True,capture_output=True,env=env,timeout=protocol['timeout_seconds'])
                if proc.returncode!=0:
                    result=dict(report=dict(status='worker_error',answers=[]),error=proc.stderr,worker_exit_code=proc.returncode)
                else:result=json.loads(proc.stdout)
            except subprocess.TimeoutExpired:
                result=dict(report=dict(status='time_limit',answers=[]),timeout_seconds=protocol['timeout_seconds'])
            result.update(case=row['case'],repetition=repetition,wall_seconds=perf_counter()-start)
            report=result['report']
            if report['status']=='completed':
                if report['request_sha256']!=row['request_sha256']:raise AssertionError('worker request mismatch')
                if result['rewrite_certificate_sha256']!=row['rewrite_certificate_sha256']:raise AssertionError('rewrite proof changed')
                values={str(int(k,2)):C.from_dict(v['exact']).to_dict() for k,v in report['answers'][0]['probabilities'].items()}
                if values!=row['expected']:raise AssertionError('independent Fourier law mismatch')
                if report['statistics']['preparation_count']!=1:raise AssertionError('preparation repeated')
                if row['case'] not in data['assessments']:
                    data['assessments'][row['case']]=assess(build(**row['builder']),report)
            elif report['answers']:raise AssertionError('failed worker returned partial answers')
            data['runs'].append(result);save()
            print(f"{repetition} {row['case']}: {report['status']} {result['wall_seconds']:.4f}s",flush=True)
    for guard in protocol['guards']:
        n=13 if guard=='support' else 3
        doc=dict(schema='nrqc-calculator-v1',n_qubits=n,backend='cyclotomic64',
            operations=[['h',[q]] for q in range(n)],queries=[dict(id='p',kind='probability',outcomes={'0':0})])
        if guard=='coefficient':doc['limits']={'max_coefficient_bits':2}
        if guard=='work':doc['limits']={'max_work':1}
        report=run_calculation(doc,timeout_seconds=1e-9 if guard=='wall' else 20)
        if report['status']!=('time_limit' if guard=='wall' else 'incomplete') or report['answers']:
            raise AssertionError('resource guard exposed an answer')
        data['guards'].append(dict(guard=guard,report=report));save()
    summaries=[]
    for row in protocol['cases']:
        runs=[r for r in data['runs'] if r['case']==row['case']]
        completed=[r for r in runs if r['report']['status']=='completed']
        summaries.append(dict(case=row['case'],statuses=[r['report']['status'] for r in runs],
            median_wall_seconds=statistics.median(r['wall_seconds'] for r in runs),
            median_compile_and_verify_seconds=statistics.median(r['compile_and_verify_seconds'] for r in completed) if completed else None,
            maximum_peak_worker_rss_bytes=max((r['peak_worker_rss_bytes'] for r in completed),default=None),
            gates=row['program']['total_gates'],qubits=row['program']['n_qubits']))
    data.update(summaries=summaries,completed_utc=datetime.now(timezone.utc).isoformat(),
        completed_runs=sum(r['report']['status']=='completed' for r in data['runs']),
        unsuccessful_runs=sum(r['report']['status']!='completed' for r in data['runs']),
        all_completed_answers_verified=True,all_guards_verified=True)
    save()


def main():
    if sys.argv[1:]==['--worker']:
        print(json.dumps(worker(json.loads(sys.stdin.read()))));return
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',action='store_true');action.add_argument('--run',action='store_true')
    parser.add_argument('--protocol',type=Path,default=ROOT/'native_relational_qc/phase64_protocol.json')
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.prepare:args.out.write_text(json.dumps(prepare_protocol(),indent=2,sort_keys=True)+'\n')
    else:run(json.loads(args.protocol.read_text()),args.out)


if __name__=='__main__':main()
