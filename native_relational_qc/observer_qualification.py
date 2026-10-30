"""Source-pinned, serial fresh-process observer32 qualification."""
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from .calculator import _digest,run_calculation,validate
from .compact import ResourceLimit
from .cyclotomic32 import Cyclotomic32 as C,ZERO,ZETA
from .observer32 import future_bank
from .phase_backend import Phase32Circuit

ROOT=Path(__file__).resolve().parent.parent


def hashes():
    paths=sorted((ROOT/'native_relational_qc').glob('*.py'))
    paths += [ROOT/'tests/test_native_observer32.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def graph_request(n,backend):
    operations=[['h',[q]] for q in range(n)]
    operations += [['cz',[q,q+1]] for q in range(n-1)]
    operations += [['p32',[q]] for q in range(n)]
    return dict(schema='nrqc-calculator-v1',backend=backend,n_qubits=n,operations=operations,
        queries=[dict(id='k0',kind='expectation',paulis={'0':'X','1':'Z'})])


def prepare_protocol():
    cases=[];cosine=(ZETA+ZETA.conjugate())*Fraction(1,2)
    for n in (5,50):
        for backend in ('observer32','cyclotomic32'):
            cases.append(dict(case=f'graph{n}_{backend}',request=graph_request(n,backend),
                expected_status='incomplete' if n==50 and backend=='cyclotomic32' else 'completed',
                expected_value=cosine.to_dict(),reference='graph stabilizer X0 Z1; local Z phase rotates X0 by pi/16'))
    for backend,limit in (('observer32','max_terms'),('cyclotomic32','max_branches')):
        # Both limits are 64. The input |0> is unchanged by these diagonal gates;
        # a global X pullback still expands to 128 nonzero Pauli coordinates.
        doc=dict(schema='nrqc-calculator-v1',backend=backend,n_qubits=7,
            operations=[['p32',[q]] for q in range(7)],limits={limit:64},
            queries=[dict(id='global',kind='expectation',paulis={str(q):'X' for q in range(7)})])
        cases.append(dict(case=f'diagonal7_{backend}',request=doc,
            expected_status='incomplete' if backend=='observer32' else 'completed',
            expected_value=ZERO.to_dict(),reference='diagonal phases fix |0000000>; global X expectation is zero'))
    for row in cases:row['request_sha256']=_digest(validate(row['request'])[1])
    return dict(schema='nrqc-observer-protocol-v1',author='Monty',
        baseline_commit='b0126895e22b4999a6f63d6d56b96b6acd792b8f',source_sha256=hashes(),
        frozen_utc=datetime.now(timezone.utc).isoformat(),repetitions=3,timeout_seconds=20,cases=cases,
        prior_observations='Implementation and correctness tests preceded freeze, including graph50 and a different global-X failure. Not blind preregistration.',
        ordering='Serial fresh workers, reverse order on alternate repetitions; no warmup discarded.',
        limits='Defaults: 4096 terms or amplitudes, 10M work, coefficient bits4096. Diagonal7 uses64 for both representation limits. No hard RSS cap.',
        bank_cases=['local50','entangling2','closure_limit'],
        boundaries='Graph50 is one local observation, not all amplitudes or all measurements. Future banks preserve every word of a declared alphabet, not arbitrary gates. Coordinate closure is not minimum row-space closure.')


def bank_worker(name):
    started=time.perf_counter()
    if name=='local50':
        c=Phase32Circuit(50)
        for q in range(50):c.add('h',q).add('p32',q)
        limits={}
    elif name=='entangling2':c=Phase32Circuit(2).add('h',0).add('cp32',0,1).add('cx',1,0);limits={}
    elif name=='closure_limit':c=Phase32Circuit(1).add('h',0).add('p32',0);limits={'max_terms':2}
    else:raise ValueError('unknown bank case')
    try:report=dict(status='completed',certificate=future_bank(c,{0:'Z'},**limits))
    except ResourceLimit as e:report=dict(status='incomplete',error=str(e),statistics=e.statistics)
    report['execution_seconds']=time.perf_counter()-started
    report['peak_worker_rss_bytes']=next(int(line.split()[1])*1024 for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('VmHWM:'))
    return report


def run(protocol,out):
    if hashes()!=protocol['source_sha256']:raise ValueError('source changed after protocol freeze')
    data=dict(schema='nrqc-observer-results-v1',protocol_sha256=_digest(protocol),python=sys.version,
        platform=platform.platform(),started_utc=datetime.now(timezone.utc).isoformat(),runs=[],bank_runs=[])
    def save():out.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    for repetition in range(1,protocol['repetitions']+1):
        rows=protocol['cases'] if repetition%2 else list(reversed(protocol['cases']))
        for row in rows:
            if _digest(validate(row['request'])[1])!=row['request_sha256']:raise AssertionError('normalized input mismatch')
            r=run_calculation(row['request'],timeout_seconds=protocol['timeout_seconds'])
            if r['request_sha256']!=row['request_sha256']:raise AssertionError('worker input mismatch')
            if r['status']!=row['expected_status']:raise AssertionError('unexpected completion status')
            if r['status']=='completed':
                if C.from_dict(r['answers'][0]['value']['exact'])!=C.from_dict(row['expected_value']):raise AssertionError('analytic reference mismatch')
            elif r['answers']:raise AssertionError('failed batch exposed an answer')
            data['runs'].append(dict(case=row['case'],repetition=repetition,report=r));save()
            print(f"{repetition} {row['case']}: {r['status']} {r['wall_seconds']:.4f}s",flush=True)
    for name in protocol['bank_cases']:
        started=time.perf_counter()
        proc=subprocess.run([sys.executable,'-m','native_relational_qc.observer_qualification','--bank-worker',name],capture_output=True,text=True,timeout=20,check=True)
        r=json.loads(proc.stdout);r['wall_seconds']=time.perf_counter()-started
        if name=='closure_limit':
            if r['status']!='incomplete' or 'certificate' in r:raise AssertionError('partial closure certificate returned')
        elif r['status']!='completed':raise AssertionError('bank did not close')
        if name=='local50' and r['certificate']['retained_dimension']!=3:raise AssertionError('wrong bank dimension')
        data['bank_runs'].append(dict(case=name,report=r));save()
        print(f"bank {name}: {r['status']}",flush=True)
    data['summaries']=[]
    for row in protocol['cases']:
        rs=[v['report'] for v in data['runs'] if v['case']==row['case']]
        data['summaries'].append(dict(case=row['case'],statuses=[r['status'] for r in rs],
            median_wall_seconds=statistics.median(r['wall_seconds'] for r in rs),
            median_execution_seconds=statistics.median(r['execution_seconds'] for r in rs),
            maximum_peak_worker_rss_bytes=max(r['peak_worker_rss_bytes'] for r in rs),
            peak_representation=max(r['statistics'].get('peak_terms',r['statistics'].get('peak_branches',0)) for r in rs)))
    data.update(completed_utc=datetime.now(timezone.utc).isoformat(),all_expected_statuses_verified=True,all_completed_values_exactly_verified=True)
    save()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--run',action='store_true');g.add_argument('--bank-worker')
    p.add_argument('--protocol',type=Path,default=ROOT/'native_relational_qc/observer_protocol.json')
    p.add_argument('--out',type=Path,default=ROOT/'native_relational_qc/observer_results.json');a=p.parse_args()
    if a.prepare:a.protocol.write_text(json.dumps(prepare_protocol(),sort_keys=True,indent=2)+'\n')
    elif a.bank_worker:print(json.dumps(bank_worker(a.bank_worker),sort_keys=True))
    else:run(json.loads(a.protocol.read_text()),a.out)


if __name__=='__main__':main()
