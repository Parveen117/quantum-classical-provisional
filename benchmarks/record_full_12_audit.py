"""Theorem R1 at twelve bits: the record-conditioned distribution equals the full register, element by element.

For each modulus the one-control-wire record protocol is executed exactly and
compared, bin by bin in the flat field Q(zeta_4096), with a retained
full-register twelve-bit result from the same source revision. The earlier
record-phase audit could only check its twelve-bit rows against the Fourier
law because the full register exceeded the 65,536-branch cap; with the
1,048,576 cap those rows are now witnessed directly. Timings are single
local wall-clock readings; nothing here is hardware evidence or a sample.
"""
import argparse
import gzip
import hashlib
import json
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from native_relational_qc.cyclotomic_pow2 import field_of_order
from native_relational_qc.record_phase import build_record,run_record,assess_record
from native_relational_qc.shor import build,exact_phase_law

SCHEMA='nrqc-record-full-12-audit-v1'
PRECISION=12
SOURCE_FILES=('native_relational_qc/cyclotomic_pow2.py','native_relational_qc/phase_backend.py','native_relational_qc/calculator.py',
              'native_relational_qc/shor.py','native_relational_qc/modular_arithmetic.py','native_relational_qc/modular_rewrite.py',
              'native_relational_qc/record_phase.py','benchmarks/record_full_12_audit.py')


def read_json(path):
    data=Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def source_hashes():
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def full_distribution(result,modulus,base):
    """The 4096 exact bins of a retained full-register result, bound to the workload it claims."""
    program=build(modulus,base,precision=PRECISION,oracle='arithmetic',rewrite='panini',field='flat')
    if result['status']!='completed':raise ValueError('retained full-register result is not completed')
    answer=result['answers'][0]
    if answer['bitstring_qubits_left_to_right']!=list(reversed(program.controls)):raise ValueError('retained result reads other wires')
    Z=field_of_order(1<<PRECISION)
    bins={label:Z.from_dict(value['exact']) for label,value in answer['probabilities'].items()}
    if len(bins)!=1<<PRECISION:raise ValueError('retained result is not a complete twelve-bit distribution')
    return dict(bins=bins,gates=len(program.circuit.operations),wires=program.circuit.n_qubits,
                request_sha256=result.get('request_sha256'),wall_seconds=result.get('wall_seconds'),
                peak_branches=result.get('statistics',{}).get('peak_branches'))


def compare(modulus,base,full):
    start=time.perf_counter();program=build_record(modulus,base,precision=PRECISION)
    distribution,budget=run_record(program,max_work=1_000_000_000);record_seconds=time.perf_counter()-start
    assessment=assess_record(program,distribution)          # every record bin against the Fourier law
    F=program.field;Z=field_of_order(1<<PRECISION)
    equal=[Z(distribution[y])==full['bins'][format(y,f'0{PRECISION}b')] for y in range(1<<PRECISION)]
    law=exact_phase_law(modulus,base,PRECISION,field='flat')
    full_law=all(full['bins'][format(y,f'0{PRECISION}b')]==Z(law[y]) for y in range(1<<PRECISION))
    # negative controls: a cyclic relabelling of the record bins must not match the full register,
    # and one altered bin must be detected
    shifted=sum(Z(distribution[(y+1)%(1<<PRECISION)])==full['bins'][format(y,f'0{PRECISION}b')] for y in range(1<<PRECISION))
    altered=dict(full['bins']);label=format(5,f'0{PRECISION}b');altered[label]=altered[label]+Z(1)/(1<<40)
    altered_detected=any(Z(distribution[y])!=altered[format(y,f'0{PRECISION}b')] for y in range(1<<PRECISION))
    total=sum((Z(v) for v in distribution.values()),Z())
    return dict(modulus=modulus,base=base,precision_bits=PRECISION,
        record=dict(wires=program.n_qubits,multiplier_gates=program.metadata()['total_multiplier_gates'],seconds=round(record_seconds,3),
                    nodes=budget.stats['nodes'],leaves=budget.stats['leaves'],peak_support=budget.stats['peak_support'],work_used=budget.stats['work_used'],
                    exact_fourier_law_agrees=assessment['exact_fourier_law_agrees']),
        full=dict(wires=full['wires'],gates=full['gates'],request_sha256=full['request_sha256'],wall_seconds=full['wall_seconds'],
                  peak_branches=full['peak_branches'],exact_fourier_law_agrees=full_law),
        bins=1<<PRECISION,bins_equal=sum(equal),record_equals_full_register=all(equal),record_sums_to_one=total==Z(1),
        success_probability={k:F.from_dict(v['exact_success_probability']).display(10)['decimal'] for k,v in assessment['policies'].items()},
        negative_controls=dict(shifted_bins_matching=shifted,shifted_relabelling_rejected=shifted<(1<<PRECISION),altered_bin_detected=altered_detected))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full',nargs='+',required=True,help='modulus=path pairs of retained full-register results (json or json.gz)')
    parser.add_argument('--base',type=int,default=2)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    before=source_hashes();rows=[];files={}
    for item in args.full:
        modulus,path=item.split('=',1);modulus=int(modulus)
        files[str(modulus)]=dict(path=str(Path(path).name),sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest())
        full=full_distribution(read_json(path),modulus,args.base)
        rows.append(compare(modulus,args.base,full));print(json.dumps(rows[-1],sort_keys=True),flush=True)
    if source_hashes()!=before:raise RuntimeError('sources changed during the audit')
    try:revision=subprocess.run(['git','-C',str(ROOT),'rev-parse','HEAD'],capture_output=True,text=True,timeout=10,check=True).stdout.strip()
    except (OSError,subprocess.SubprocessError):revision=None
    out=dict(schema=SCHEMA,status='witnessed' if all(r['record_equals_full_register'] and r['record']['exact_fourier_law_agrees'] and r['full']['exact_fourier_law_agrees']
                                                      and all(r['negative_controls'][k] for k in ('shifted_relabelling_rejected','altered_bin_detected')) for r in rows) else 'failed',
             claim='Theorem R1 at twelve bits: for each modulus the one-control-wire record distribution equals the full-register distribution in every one of the 4096 bins',
             rows=rows,full_results=files,source_sha256=before,revision=revision,
             environment=dict(python=platform.python_version(),numpy=__import__('numpy').__version__,platform=platform.platform(),machine=platform.machine()),
             process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             scope='ideal local exact calculation of fixed bases, one run per row; success is single-record probability, not shots or hardware')
    args.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print('status',out['status'])
    return 0 if out['status']=='witnessed' else 1


if __name__=='__main__':raise SystemExit(main())
