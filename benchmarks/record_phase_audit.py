"""Record-conditioned phase estimation against the full-register program.

Each row runs the one-control-wire record protocol exactly, checks every
record probability against the independent Fourier law, decodes, and, where
the full-register circuit fits the calculator's branch cap, also runs that
circuit and checks the two distributions for exact equality. Timings are
local wall-clock readings on this machine; nothing here is hardware evidence.
"""
import argparse
import json
import platform
import resource
import time
from pathlib import Path

from native_relational_qc.calculator import calculate
from native_relational_qc.cyclotomic_pow2 import field_of_order
from native_relational_qc.record_phase import build_record,run_record,assess_record
from native_relational_qc.shor import build

ROWS=(
    (141,2,8,True),(143,2,8,True),(187,2,8,True),
    (141,2,10,True),(143,2,10,True),(187,2,10,True),
    (141,2,12,False),(143,2,12,False),(187,2,12,False),
)


def run(modulus,base,precision,compare_full):
    start=time.perf_counter();program=build_record(modulus,base,precision=precision)
    distribution,budget=run_record(program);seconds=time.perf_counter()-start
    result=assess_record(program,distribution);F=program.field
    row=dict(modulus=modulus,base=base,precision_bits=precision,record_wires=program.n_qubits,
        multiplier_gates=program.metadata()['total_multiplier_gates'],record_seconds=round(seconds,3),
        nodes=budget.stats['nodes'],leaves=budget.stats['leaves'],pruned_records=budget.stats['pruned_records'],
        peak_support=budget.stats['peak_support'],work_used=budget.stats['work_used'],
        exact_fourier_law_agrees=result['exact_fourier_law_agrees'],
        success_probability={k:F.from_dict(v['exact_success_probability']).display(10)['decimal'] for k,v in result['policies'].items()})
    if compare_full:
        start=time.perf_counter()
        full=build(modulus,base,precision=precision,oracle='arithmetic',rewrite='panini',field='flat')
        document=full.request('cyclotomic_pow2');document['limits']={'max_work':1_000_000_000,'max_branches':65_536}
        report=calculate(document);seconds=time.perf_counter()-start
        row.update(full_wires=full.circuit.n_qubits,full_gates=len(full.circuit.operations),full_seconds=round(seconds,3),
                   full_status=report['status'])
        if report['status']=='completed':
            Z=field_of_order(max(8,1<<precision))
            probabilities=report['answers'][0]['probabilities']
            row['record_equals_full_register']=all(Z.from_dict(probabilities[format(y,f'0{precision}b')]['exact'])==v
                                                   for y,v in distribution.items())
            row['full_peak_branches']=report['statistics']['peak_branches']
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path('native_relational_qc/record_phase_audit.json'))
    args=parser.parse_args();rows=[]
    for spec in ROWS:
        rows.append(run(*spec));print(json.dumps(rows[-1],sort_keys=True),flush=True)
    out=dict(schema='nrqc-record-phase-audit-v1',python=platform.python_version(),machine=platform.machine(),
             process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,rows=rows,
             scope='ideal local exact calculation of fixed bases; success is single-record probability, not shots or hardware')
    args.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':main()
