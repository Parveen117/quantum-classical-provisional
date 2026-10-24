"""Recheck saved phase64 runs and measure Linux executable RSS separately.

Linux ru_maxrss can retain the launching process's high-water mark across
exec. The original timing harness's ru_maxrss values are preserved but are
not used as isolated-worker memory comparisons. This audit uses /proc/self
VmHWM, including the current executable's imports, compilation and proof.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
from time import perf_counter

from native_relational_qc.calculator import calculate,_digest
from native_relational_qc.cyclotomic64 import Cyclotomic64 as C
from native_relational_qc.phase64_qualification import hashes
from native_relational_qc.shor import build

ROOT=Path(__file__).resolve().parent.parent


def memory_worker(row):
    start=perf_counter();p=build(**row['builder']);compile_seconds=perf_counter()-start
    report=calculate(p.request(row['backend']))
    rss=next(int(s.split()[1])*1024 for s in Path('/proc/self/status').read_text().splitlines() if s.startswith('VmHWM:'))
    return dict(report=report,peak_worker_rss_bytes=rss,compile_and_verify_seconds=compile_seconds,
        rss_source='Linux /proc/self/status VmHWM, current executable including imports/setup/proof',
        rewrite_certificate_sha256=_digest(p.rewrite_certificate) if p.rewrite_certificate else None)


def check_report(row,result):
    report=result['report']
    if report['status']!='completed' or report['request_sha256']!=row['request_sha256']:
        raise AssertionError('run did not complete its frozen request')
    if result['rewrite_certificate_sha256']!=row['rewrite_certificate_sha256']:
        raise AssertionError('rewrite witness digest mismatch')
    values={str(int(k,2)):C.from_dict(v['exact']).to_dict() for k,v in report['answers'][0]['probabilities'].items()}
    if values!=row['expected']:raise AssertionError('independent Fourier reference mismatch')


def audit(out):
    directory=ROOT/'native_relational_qc'
    protocol_path=directory/'phase64_protocol.json';results_path=directory/'phase64_results.json'
    protocol=json.loads(protocol_path.read_text());data=json.loads(results_path.read_text())
    if hashes()!=protocol['source_sha256'] or data['protocol_sha256']!=_digest(protocol):
        raise ValueError('source or protocol binding changed')
    rows={r['case']:r for r in protocol['cases']}
    counts=Counter((r['case'],r['repetition']) for r in data['runs'])
    wanted=Counter((name,rep) for name in rows for rep in range(1,protocol['repetitions']+1))
    if counts!=wanted:raise AssertionError('missing or duplicated run')
    for result in data['runs']:check_report(rows[result['case']],result)
    guards={g['guard']:g['report'] for g in data['guards']}
    if len(data['guards'])!=len(protocol['guards']) or set(guards)!=set(protocol['guards']):
        raise AssertionError('missing or duplicated guard')
    for name,report in guards.items():
        if report['answers'] or report['status']!=('time_limit' if name=='wall' else 'incomplete'):
            raise AssertionError('resource guard failed')
    summaries=[]
    for name,row in rows.items():
        runs=[r for r in data['runs'] if r['case']==name]
        summaries.append(dict(case=name,gates=row['program']['total_gates'],qubits=row['program']['n_qubits'],
            median_wall_seconds=statistics.median(r['wall_seconds'] for r in runs),
            median_compile_and_verify_seconds=statistics.median(r['compile_and_verify_seconds'] for r in runs),
            statistics=runs[0]['report']['statistics'],compact_certificate_bytes=runs[0]['compact_certificate_bytes'],
            success={key:C.from_dict(value['exact_success_probability']).display(12) for key,value in data['assessments'][name]['policies'].items()}))
    result=dict(schema='nrqc-phase64-audit-v1',author='Monty',completed_runs=len(data['runs']),
        all_saved_runs_reverified=True,all_guards_reverified=True,
        protocol_sha256=_digest(protocol),results_file_sha256=hashlib.sha256(results_path.read_bytes()).hexdigest(),
        audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),summaries=summaries,memory_runs=[],
        memory_correction='Original ru_maxrss readings can include the parent high-water mark inherited across exec. They are retained in raw results but excluded from isolated-worker memory claims.',
        memory_scope='One additional serial fresh worker per six-bit comparison, same source/requests/proof digests. Timings below are not pooled into the three-repetition timing medians.',
        started_utc=datetime.now(timezone.utc).isoformat())
    def save():out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    save()
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    for row in protocol['cases']:
        if row['case'] not in {f'{n}_2_6_{rewrite}' for n in (141,143,187) for rewrite in ('none','panini')}:continue
        start=perf_counter()
        try:
            proc=subprocess.run([sys.executable,'-m','benchmarks.phase64_audit','--memory-worker'],
                input=json.dumps(row),text=True,capture_output=True,env=env,timeout=protocol['timeout_seconds'])
            if proc.returncode:raise RuntimeError(proc.stderr)
            measurement=json.loads(proc.stdout)
            measurement['wall_seconds']=perf_counter()-start
            check_report(row,measurement)
        except subprocess.TimeoutExpired:
            measurement=dict(report=dict(status='time_limit',answers=[]),wall_seconds=perf_counter()-start)
        measurement['case']=row['case'];result['memory_runs'].append(measurement);save()
        print(row['case'],measurement['report']['status'],measurement.get('peak_worker_rss_bytes'),flush=True)
    result['completed_utc']=datetime.now(timezone.utc).isoformat();save()


def main():
    if sys.argv[1:]==['--memory-worker']:
        print(json.dumps(memory_worker(json.loads(sys.stdin.read()))));return
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();audit(args.out)


if __name__=='__main__':main()
