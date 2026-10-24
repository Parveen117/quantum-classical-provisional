"""Matched Shor runs: nested Q(zeta_64) versus the flat Q(zeta_2**m) backend.

Each row builds the arithmetic oracle with the Panini rewrite, executes one
in-process calculator batch, and verifies every probability against the
independent exact Fourier law before decoding. Timings are local wall-clock
measurements on this machine; they are not hardware evidence.
"""
import argparse
import json
import platform
import resource
import time
from pathlib import Path

from native_relational_qc.calculator import calculate
from native_relational_qc.cyclotomic_pow2 import field_of_order
from native_relational_qc.cyclotomic64 import Cyclotomic64
from native_relational_qc.shor import build,assess

ROWS=(
    (141,2,6,'nested','cyclotomic64'),
    (141,2,6,'nested','cyclotomic_pow2'),
    (141,2,6,'flat','cyclotomic_pow2'),
    (141,2,8,'flat','cyclotomic_pow2'),
    (143,2,8,'flat','cyclotomic_pow2'),
    (187,2,8,'flat','cyclotomic_pow2'),
    (21,2,10,'flat','cyclotomic_pow2'),
)


def decimal(value,precision):
    field=field_of_order(max(8,1<<precision)) if 'sparse_coefficients' in value else Cyclotomic64
    return field.from_dict(value).display(10)['decimal']


def run(modulus,base,precision,field,backend):
    start=time.perf_counter()
    program=build(modulus,base,precision=precision,oracle='arithmetic',rewrite='panini',field=field)
    built=time.perf_counter()-start
    document=program.request(backend);document['limits']={'max_work':1_000_000_000,'max_branches':65_536}
    start=time.perf_counter();report=calculate(document);seconds=time.perf_counter()-start
    row=dict(modulus=modulus,base=base,precision_bits=precision,circuit_field=field,backend=backend,
             n_qubits=program.circuit.n_qubits,gates=len(program.circuit.operations),
             build_seconds=round(built,3),calculation_seconds=round(seconds,3),status=report['status'])
    if report['status']!='completed':return dict(row,error=report.get('error'))
    stats=report['statistics'];result=assess(program,report)
    row.update(peak_branches=stats['peak_branches'],work_used=stats['work_used'],
               representation=stats['representation'],assessment=result['status'],
               exact_fourier_law_agrees=result.get('exact_fourier_law_agrees'),
               success_probability={k:decimal(v['exact_success_probability'],precision) for k,v in result['policies'].items()})
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path('native_relational_qc/pow2_shor_audit.json'))
    args=parser.parse_args();rows=[]
    for spec in ROWS:
        rows.append(run(*spec));print(json.dumps(rows[-1],sort_keys=True),flush=True)
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out=dict(schema='nrqc-pow2-shor-audit-v1',python=platform.python_version(),machine=platform.machine(),
             process_peak_rss_kib=peak,rows=rows,
             scope='ideal local exact calculation of fixed bases; success is single-readout probability, not shots or hardware')
    args.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':main()
