"""Bounded full-register 12-bit Shor check; retains failures as well as successes."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from native_relational_qc.shor import build,assess
from native_relational_qc.calculator import run_calculation,display
from native_relational_qc.cyclotomic_pow2 import field_of_order

SOURCE_FILES=('native_relational_qc/cyclotomic_pow2.py','native_relational_qc/phase_backend.py',
              'native_relational_qc/calculator.py','native_relational_qc/shor.py',
              'native_relational_qc/modular_arithmetic.py','native_relational_qc/modular_rewrite.py',
              'benchmarks/full_register_12_audit.py')


def source_hashes():
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--modulus',type=int,default=141)
    p.add_argument('--base',type=int,default=2)
    p.add_argument('--timeout',type=float,default=300);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--full-result',type=Path,help='optionally retain every exact probability and enclosure')
    a=p.parse_args()
    sources_before=source_hashes()
    start=time.perf_counter();program=build(a.modulus,a.base,precision=12,oracle='arithmetic',rewrite='panini',field='flat')
    doc=program.request('cyclotomic_pow2');doc['limits']={'max_work':1_000_000_000,'max_branches':1_048_576}
    built=time.perf_counter()-start
    print('Built',len(program.circuit.operations),'gates',flush=True)
    result=run_calculation(doc,timeout_seconds=a.timeout)
    summary={k:v for k,v in result.items() if k!='answers'}
    summary.update(program=program.metadata(),build_seconds=built,
                   answers_sha256=hashlib.sha256(json.dumps(result.get('answers',[]),sort_keys=True).encode()).hexdigest())
    if result['status']=='completed':
        assessment=assess(program,result)  # Checks every bin against the independent finite Fourier sum.
        for policy in assessment['policies'].values():
            readings=policy.pop('readings')
            policy['readings_checked']=len(readings)
            policy['factor_readings']=sum(r['status']=='factored' for r in readings)
            policy['success_probability']=display(field_of_order(4096).from_dict(policy['exact_success_probability']),12)
        summary['assessment']=assessment
        probabilities=result['answers'][0]['probabilities']
        exact={label:value['exact'] for label,value in probabilities.items()}
        summary['distribution_bins']=len(exact)
        summary['exact_distribution_sha256']=hashlib.sha256(json.dumps(exact,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if a.full_result:a.full_result.write_text(json.dumps(result,sort_keys=True)+'\n')
    if source_hashes()!=sources_before:raise RuntimeError('sources changed during the qualification run')
    summary['source_sha256']=sources_before
    summary['environment']=dict(python=platform.python_version(),platform=platform.platform(),
        numpy=__import__('numpy').__version__,blas_threads=1)
    try:
        import resource
        peak=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        summary['worker_peak_rss_mib']=peak/(1024**2 if platform.system()=='Darwin' else 1024)
    except ImportError:pass
    summary['audit_seconds']=time.perf_counter()-start
    a.out.write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
    print(summary['status'],summary.get('statistics'),flush=True)
if __name__=='__main__':main()
