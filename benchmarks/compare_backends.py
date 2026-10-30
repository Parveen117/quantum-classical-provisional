"""Retained same-JSON comparisons; local simulators only, never hardware.

Every engine answers the identical probability/Pauli/marginal queries.
Stim rejects non-Clifford input; Aer MPS has truncation disabled. Each trial
uses a fresh process; the headline time includes validation/conversion,
execution and answer formatting, but excludes imports. Raw wall/RSS remain.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def normalized(report):
    out={}
    for row in report['answers']:
        if row['kind']=='distribution':
            out.update({row['id']+':'+k:float(v['decimal']) for k,v in row['probabilities'].items()})
        else:out[row['id']]=float(row['value']['decimal'])
    return out


def aer(document):
    from qiskit import transpile
    from qiskit_aer import AerSimulator
    from qiskit.quantum_info import Pauli
    from native_relational_qc.calculator import validate
    from native_relational_qc.compact_qiskit import to_qiskit
    circuit,_=validate(document)
    # A simulator target's advertised width (63 here) is not an MPS limit.
    # Lower only to a universal gate alphabet, without a hardware coupling map.
    qc=transpile(to_qiskit(circuit),basis_gates=['u','cx','id'],optimization_level=0)
    for query in document['queries']:
        kind=query['kind'];label=query['id']
        if kind=='expectation':
            chars=['I']*document['n_qubits']
            for q,p in query['paulis'].items():chars[int(q)]=p
            qc.save_expectation_value(Pauli(''.join(reversed(chars))),list(range(qc.num_qubits)),label=label)
        else:
            qs=query['qubits'] if kind=='distribution' else sorted(map(int,query['outcomes']))
            qc.save_probabilities_dict(qs,label=label)
    sim=AerSimulator(method='matrix_product_state',matrix_product_state_truncation_threshold=0,
                     max_parallel_threads=1,seed_simulator=3010)
    result=sim.run(qc,shots=1).result()
    if not result.success:raise ValueError(str(result.status))
    data=result.data(0);out={}
    for query in document['queries']:
        kind=query['kind'];label=query['id'];value=data[label]
        if kind=='expectation':out[label]=float(value)
        elif kind=='probability':
            qs=sorted(map(int,query['outcomes']));key=sum(query['outcomes'][str(q)]<<i for i,q in enumerate(qs))
            out[label]=float(value.get(key,0))
        else:
            qs=query['qubits']
            for k in range(1<<len(qs)):
                bits=''.join(str(k>>i&1) for i in range(len(qs)))
                out[label+':'+bits]=float(value.get(k,0))
    return out


def stim_values(document):
    import stim
    supported={'id':'I','x':'X','y':'Y','z':'Z','h':'H','s':'S','sdg':'S_DAG',
               'sx':'SQRT_X','sxdg':'SQRT_X_DAG','cx':'CX','cz':'CZ','swap':'SWAP','k':'Z','rk':'X'}
    unknown=sorted({n for n,qs in document['operations'] if n not in supported})
    if unknown:return None,unknown
    sim=stim.TableauSimulator();sim.set_num_qubits(document['n_qubits'])
    for name,qs in document['operations']:sim.do(stim.Circuit(f'{supported[name]} '+ ' '.join(map(str,qs))))
    def probability(target):
        copy=sim.copy();p=1.0
        for q,bit in target.items():
            p*=(1+(-1 if bit else 1)*copy.peek_z(q))/2
            if not p:break
            copy.postselect_z(q,desired_value=bool(bit))
        return p
    out={}
    for query in document['queries']:
        label=query['id'];kind=query['kind']
        if kind=='probability':out[label]=probability({int(q):v for q,v in query['outcomes'].items()})
        elif kind=='expectation':
            chars=['I']*document['n_qubits']
            for q,p in query['paulis'].items():chars[int(q)]=p
            out[label]=float(sim.peek_observable_expectation(stim.PauliString(''.join(chars))))
        else:
            qs=query['qubits']
            for k in range(1<<len(qs)):
                bits=format(k,f'0{len(qs)}b');out[label+':'+bits]=probability({q:int(b) for q,b in zip(qs,bits)})
    return out,[]


def worker(path,engine):
    from native_relational_qc.calculator import calculate
    document=json.loads(path.read_text())
    # Import optional engines before timing, as NRQC is already imported.
    if engine=='aer_mps':import qiskit_aer
    elif engine=='stim':import stim
    start=time.perf_counter();extra={}
    if engine=='nrqc':
        report=calculate(document);status=report['status'];answers=normalized(report) if status=='completed' else {}
        extra={'statistics':report.get('statistics',{}),'error':report.get('error')}
    elif engine=='aer_mps':answers=aer(document);status='completed'
    else:
        answers,unknown=stim_values(document);status='unsupported' if answers is None else 'completed'
        extra={'unsupported_gates':unknown}
    return dict(status=status,answers=answers,execution_seconds=time.perf_counter()-start,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,**extra)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',choices=['nrqc','aer_mps','stim']);parser.add_argument('--input',type=Path)
    parser.add_argument('--repeats',type=int,default=3);parser.add_argument('--timeout',type=float,default=90)
    parser.add_argument('--out',type=Path,default=ROOT/'benchmarks/comparisons/results.json')
    args=parser.parse_args()
    if args.worker:
        try:result=worker(args.input,args.worker)
        except Exception as error:result=dict(status='error',error=type(error).__name__+': '+str(error))
        print(json.dumps(result));return
    results=[]
    for path in sorted((ROOT/'benchmarks/comparisons/inputs').glob('*.json')):
        case={'input':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'engines':{}}
        for engine in ('nrqc','aer_mps','stim'):
            samples=[]
            for repeat in range(args.repeats):
                start=time.perf_counter()
                try:
                    process=subprocess.run([sys.executable,__file__,'--worker',engine,'--input',str(path)],
                        capture_output=True,text=True,timeout=args.timeout,
                        env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'})
                    row=json.loads(process.stdout)
                except subprocess.TimeoutExpired:row={'status':'timeout','timeout_seconds':args.timeout}
                except ValueError:row={'status':'error','error':process.stderr[-2000:]}
                row['wall_seconds']=time.perf_counter()-start;samples.append(row)
                if row['status']!='completed':break
            case['engines'][engine]={'samples':samples,'median_seconds':statistics.median(s['execution_seconds'] for s in samples) if all(s['status']=='completed' for s in samples) else None}
        reference=case['engines']['nrqc']['samples'][0].get('answers')
        for engine,run in case['engines'].items():
            completed=[s for s in run['samples'] if s['status']=='completed']
            if reference and completed:
                errors=[max(abs(s['answers'].get(k,float('inf'))-v) for k,v in reference.items()) if set(s['answers'])==set(reference) else float('inf') for s in completed]
                run['max_absolute_difference']=max(errors);run['matches_nrqc_enclosure_display_at_1e_9']=max(errors)<1e-9
        results.append(case);print(path.name,[(e,r['samples'][0]['status']) for e,r in case['engines'].items()],flush=True)
    report={'schema':'nrqc-retained-comparison-v1','environment':{'python':platform.python_version(),'platform':platform.platform(),'cpu':platform.processor(),'cpu_count':os.cpu_count(),
        'versions':{name:importlib.metadata.version(name) for name in ('numpy','qiskit','qiskit-aer','stim')}},'repeats':args.repeats,
        'timing_scope':'fresh process; execution includes conversion, queries and output formatting, excludes imports; wall includes startup',
        'aer_options':{'method':'matrix_product_state','matrix_product_state_truncation_threshold':0,'max_parallel_threads':1},'cases':results}
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')

if __name__=='__main__':main()
