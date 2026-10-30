"""Paired fresh-process coordinate/linear-bank qualification, serial only."""
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
import time

from .calculator import _digest
from .compact import ResourceLimit
from .cyclotomic32 import Cyclotomic32 as C,ZERO,ONE
from .linear_observer import linear_future_bank,run_linear_bank
from .observer32 import Budget,future_bank
from .phase_backend import Phase32Circuit,prepare

ROOT=Path(__file__).resolve().parent.parent
CASES=('ch2','cp32','ccx3','no_reduction','ccx3_cap48')


def hashes():
    paths=sorted((ROOT/'native_relational_qc').glob('*.py'))
    paths += [ROOT/'tests/test_native_linear_observer.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def workload(name):
    limits={}
    if name=='ch2':c=Phase32Circuit(2).add('ch',0,1);seed={1:'Z'};initial=1
    elif name=='cp32':c=Phase32Circuit(2).add('cp32',0,1);seed={1:'X'};initial=3
    elif name=='no_reduction':c=Phase32Circuit(1).add('h',0).add('p32',0);seed={0:'Z'};initial=0
    elif name in ('ccx3','ccx3_cap48','rank_guard','storage_guard'):
        c=Phase32Circuit(7)
        for q in range(3):c.add('ccx',2*q,2*q+1,6)
        seed={6:'Z'};initial=63
        if name=='ccx3_cap48':limits={'max_terms':48}
        if name=='rank_guard':limits={'max_rank':4}
        if name=='storage_guard':limits={'max_coefficients':32}
    else:raise ValueError('unknown workload')
    sequence=[i%len(c.operations) for i in range(127)]
    return c,seed,initial,sequence,limits


def exact_reference(name):
    c,seed,initial,sequence,_=workload(name);state=Phase32Circuit(c.n_qubits)
    for q in range(c.n_qubits):
        if initial&(1<<q):state.add('x',q)
    for i in sequence:state.add(c.operations[i][0],*c.operations[i][1])
    return prepare(state).expectation(seed).to_dict()


def coordinate_replay(bank,initial,sequence,**limits):
    # Baseline application of the old bank's actual serialized sparse matrices.
    # New-bank run additionally verifies its certificate; disclose this cost.
    b=Budget(**limits);values=[];transfers=[]
    for p in bank['basis']:
        x,z=int(p['x']),int(p['z'])
        values.append(ZERO if x else -ONE if (z&initial).bit_count()%2 else ONE)
    for rows in bank['transition_rows']:
        transfers.append([[(t['column'],C.from_dict(t['coefficient'])) for t in row] for row in rows])
    for action in sequence:
        updated=[]
        for row in transfers[action]:
            value=ZERO
            for i,v in row:value=b.add(value,b.mul(v,values[i]))
            updated.append(value)
        values=updated
    return values[0].to_dict(),b.stats


def worker(name,method):
    c,seed,initial,sequence,limits=workload(name)
    started=time.perf_counter();phase='compile'
    try:
        bank=(linear_future_bank if method=='linear' else future_bank)(c,seed,**limits)
        compiled=time.perf_counter();phase='replay'
        if method=='linear':
            r=run_linear_bank(c,seed,bank,action_sequence=sequence,input_basis=initial,**limits)
            value,stats=r['value'],r['statistics']
        else:value,stats=coordinate_replay(bank,initial,sequence,**limits)
        finished=time.perf_counter()
        result=dict(status='completed',value=value,rank=bank['retained_dimension'],
            compile_seconds=compiled-started,replay_seconds=finished-compiled,
            end_to_end_seconds=finished-started,compile_statistics=bank['statistics'],replay_statistics=stats,
            certificate_bytes=len(json.dumps(bank,sort_keys=True,separators=(',',':')).encode()),
            certificate_sha256=_digest(bank))
        if name=='ccx3' and method=='linear':result['certificate']=bank
    except ResourceLimit as error:
        result=dict(status='incomplete',answers=[],error=str(error),failure_phase=phase,
            statistics=error.statistics,end_to_end_seconds=time.perf_counter()-started)
    result['peak_worker_rss_bytes']=next(int(line.split()[1])*1024 for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('VmHWM:'))
    return result


def frozen_protocol():
    rows=[]
    for name in CASES:
        c,seed,initial,sequence,limits=workload(name)
        for method in ('coordinate','linear'):
            rows.append(dict(case=name,method=method,n_qubits=c.n_qubits,
                actions=[[g,list(q)] for g,q in c.operations],seed={str(q):p for q,p in seed.items()},
                input_basis=initial,sequence=sequence,limits=limits,expected=exact_reference(name),
                expected_status='incomplete' if name=='ccx3_cap48' and method=='coordinate' else 'completed'))
    return dict(schema='nrqc-linear-observer-protocol-v1',author='Monty',
        baseline_commit='45024799070275b06e0564db8d242a9435046431',source_sha256=hashes(),
        source_theorem='observer_source_pins.json: RKF MR-04 at b72432d3efba6c462848fe9ce9adb98c827a6089',
        frozen_utc=datetime.now(timezone.utc).isoformat(),cases=rows,repetitions=3,timeout_seconds=20,
        prior_observations='Unit tests and a same-process pilot preceded freeze. Pilot cache reuse makes its timings unsuitable for comparison. Not blind preregistration.',
        comparison='Compile each bank, then replay the same 127-gate chronological word on the same computational basis input. Linear replay additionally verifies provenance, independence and closure; baseline uses its compiled rows without a separate verifier.',
        limits='Default 4096 terms per vector (coordinate bank: entire set), 10M work, 4096 coefficient bits. Linear additionally: rank128 and stored65536 scalar coefficients. Cap48 is the same numeric limit on different representation units; not a matched RSS budget.',
        scope='Actual 1,2,7-qubit workloads; 50-wire padded unit test is width compatibility only. Smaller rank need not reduce compile time or RSS.',
        ordering='Serial fresh workers; alternate reversed ordering; no warmup discarded.',
        guards=['rank_guard','storage_guard','wall_guard'])


def fresh(name,method,timeout):
    started=time.perf_counter();env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    try:
        p=subprocess.run([sys.executable,'-m','native_relational_qc.linear_qualification','--worker',name,method],text=True,capture_output=True,timeout=timeout,env=env,check=True)
        r=json.loads(p.stdout)
    except subprocess.TimeoutExpired:r=dict(status='time_limit',answers=[])
    r['wall_seconds']=time.perf_counter()-started;return r


def run(protocol,out):
    if hashes()!=protocol['source_sha256']:raise ValueError('source differs from frozen protocol')
    data=dict(schema='nrqc-linear-observer-results-v1',protocol_sha256=_digest(protocol),
        started_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,platform=platform.platform(),runs=[],guards=[])
    def save():out.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
    for repetition in range(1,protocol['repetitions']+1):
        rows=protocol['cases'] if repetition%2 else list(reversed(protocol['cases']))
        for row in rows:
            c,seed,initial,sequence,limits=workload(row['case'])
            if (row['actions']!=[[g,list(q)] for g,q in c.operations] or row['seed']!={str(q):v for q,v in seed.items()} or
                row['input_basis']!=initial or row['sequence']!=sequence or row['limits']!=limits):raise AssertionError('workload mismatch')
            r=fresh(row['case'],row['method'],protocol['timeout_seconds'])
            if r['status']!=row['expected_status']:raise AssertionError('unexpected status: '+str(r))
            if r['status']=='completed' and r['value']!=row['expected']:raise AssertionError('sparse state reference mismatch')
            if 'certificate' in r:
                certificate=r.pop('certificate')
                if repetition==1:data['example_certificate']=certificate
            data['runs'].append(dict(case=row['case'],method=row['method'],repetition=repetition,report=r));save()
            print(f"{repetition} {row['case']} {row['method']}: {r['status']} {r['wall_seconds']:.4f}s",flush=True)
    for name in protocol['guards']:
        r=fresh('ccx3' if name=='wall_guard' else name,'linear',1e-9 if name=='wall_guard' else 20)
        if r['status']!=('time_limit' if name=='wall_guard' else 'incomplete') or r.get('answers')!=[]:raise AssertionError('guard leaked a result')
        data['guards'].append(dict(case=name,report=r));save()
    summaries=[]
    for row in protocol['cases']:
        rs=[v['report'] for v in data['runs'] if (v['case'],v['method'])==(row['case'],row['method'])]
        item=dict(case=row['case'],method=row['method'],statuses=[r['status'] for r in rs],
            median_wall_seconds=statistics.median(r['wall_seconds'] for r in rs),maximum_peak_worker_rss_bytes=max(r['peak_worker_rss_bytes'] for r in rs))
        if rs[0]['status']=='completed':
            if len({r['certificate_sha256'] for r in rs})!=1:raise AssertionError('non-deterministic certificate')
            item.update(rank=rs[0]['rank'],certificate_bytes=rs[0]['certificate_bytes'],
                median_compile_seconds=statistics.median(r['compile_seconds'] for r in rs),
                median_replay_seconds=statistics.median(r['replay_seconds'] for r in rs))
        summaries.append(item)
    data.update(summaries=summaries,completed_utc=datetime.now(timezone.utc).isoformat(),
        all_completed_values_verified=True,all_expected_statuses_verified=True,all_guards_verified=True);save()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--run',action='store_true');g.add_argument('--worker',nargs=2)
    p.add_argument('--protocol',type=Path,default=ROOT/'native_relational_qc/linear_protocol.json')
    p.add_argument('--out',type=Path,default=ROOT/'native_relational_qc/linear_results.json');args=p.parse_args()
    if args.prepare:args.protocol.write_text(json.dumps(frozen_protocol(),sort_keys=True,indent=2)+'\n')
    elif args.worker:print(json.dumps(worker(*args.worker),sort_keys=True))
    else:run(json.loads(args.protocol.read_text()),args.out)


if __name__=='__main__':main()
