"""Bounded full-register 12-bit Shor check; retains failures as well as successes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from native_relational_qc.shor import build,assess
from native_relational_qc.calculator import run_calculation


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--modulus',type=int,default=141)
    p.add_argument('--timeout',type=float,default=300);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    start=time.perf_counter();program=build(a.modulus,2,precision=12,oracle='arithmetic',rewrite='panini',field='flat')
    doc=program.request('cyclotomic_pow2');doc['limits']={'max_work':1_000_000_000,'max_branches':1_048_576}
    built=time.perf_counter()-start
    print('Built',len(program.circuit.operations),'gates',flush=True)
    result=run_calculation(doc,timeout_seconds=a.timeout)
    summary={k:v for k,v in result.items() if k!='answers'}
    summary.update(program=program.metadata(),build_seconds=built,
                   answers_sha256=hashlib.sha256(json.dumps(result.get('answers',[]),sort_keys=True).encode()).hexdigest())
    if result['status']=='completed':summary['assessment']=assess(program,result)
    a.out.write_text(json.dumps(summary,sort_keys=True,indent=2)+'\n')
    print(summary['status'],summary.get('statistics'),flush=True)
if __name__=='__main__':main()
