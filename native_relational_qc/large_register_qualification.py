"""Frozen, bounded 2056-qubit qualification; SDK used only to prepare references.

Author: Monty. Run from the repository root; see LARGE_REGISTER.md.
Preparation never calls the new execution engine to obtain expected answers.
"""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import sys

from .calculator import _digest, run_calculation, validate
from .exact import Exact, ONE, ZERO, INV_SQRT2

N = 2056
ROOT = Path(__file__).resolve().parent.parent
CASES = ('ghz_global', 'ghz_full_probability', 'ghz_t', 'ghz_tdg',
         'uniform_full_probability', 'six_t_global', 'seeded_clifford',
         'term_limit', 'projector_limit', 'work_limit', 'generator_limit',
         'coefficient_limit', 'wall_limit')


def source_hashes():
    files = sorted((ROOT/'native_relational_qc').glob('*.py'))
    files += [ROOT/'tests/test_native_large_register.py']
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def word(letter):
    return {str(q):letter for q in range(N)}


def expectation(label, paulis):
    return dict(id=label, kind='expectation', paulis=paulis)


def probability(label, outcomes):
    return dict(id=label, kind='probability', outcomes=outcomes)


def seeded_operations():
    rng = random.Random(2056)
    operations = [['h',[0]]] + [['cx',[q,q+1]] for q in range(N-1)]
    for _ in range(4):
        for q in range(N):
            operations.append([rng.choice(('h','s','sdg','sx','sxdg','x','y','z')),[q]])
        order = list(range(N)); rng.shuffle(order)
        for i in range(0,N,2):
            operations.append([rng.choice(('cx','cz','swap')),order[i:i+2]])
    return operations


def request(case, reference=None):
    operations = [['h',[0]]] + [['cx',[q,q+1]] for q in range(N-1)]
    backend='stabilizer'; limits={}
    x=word('X'); y={**x,'0':'Y'}
    if case=='ghz_global':
        queries=[expectation('global_x',x),expectation('global_z',word('Z')),
                 expectation('local_z',{'0':'Z'}),expectation('end_zz',{'0':'Z','2055':'Z'})]
    elif case=='ghz_full_probability':
        queries=[probability('all_zero',{str(q):0 for q in range(N)}),
                 probability('mismatch',{'0':0,'2055':1})]
    elif case in ('ghz_t','ghz_tdg'):
        operations.append(['t' if case=='ghz_t' else 'tdg',[0]]);backend='clifford_t'
        queries=[expectation('global_x',x),expectation('global_y',y),
                 probability('end_00',{'0':0,'2055':0})]
        if case=='ghz_t':
            queries.append(dict(id='emk',kind='geometry',generators=[
                dict(paulis=x),dict(paulis=y),dict(paulis={'0':'Z'})]))
    elif case in ('uniform_full_probability','coefficient_limit'):
        operations=[['h',[q]] for q in range(N)]
        queries=[probability('all_zero',{str(q):0 for q in range(N)})]
        if case=='coefficient_limit':limits={'max_coefficient_bits':2048}
    elif case in ('six_t_global','term_limit'):
        operations=[['h',[q]] for q in range(N)]
        active=6 if case=='six_t_global' else 12
        operations += [['t',[q]] for q in range(active)]
        operations += [['h',[q]] for q in range(active)]
        queries=[expectation('global_mixed',{str(q):'Z' if q<active else 'X' for q in range(N)})]
        backend='clifford_t'
        if case=='term_limit':limits={'max_terms':128}
    elif case=='seeded_clifford':
        operations=seeded_operations()
        if reference is None:raise ValueError('seeded case requires frozen independent reference')
        queries=reference['queries']
    elif case=='projector_limit':
        operations.append(['t',[0]]);backend='clifford_t';limits={'max_terms':128}
        queries=[probability('all_zero',{str(q):0 for q in range(N)})]
    elif case in ('work_limit','wall_limit'):
        queries=[expectation('global_x',x)]
        if case=='work_limit':limits={'max_work':1}
    elif case=='generator_limit':
        queries=[probability('all_zero',{str(q):0 for q in range(N)})]
        limits={'max_generators':8}
    else:raise ValueError('unknown case')
    return dict(schema='nrqc-calculator-v1',n_qubits=N,operations=operations,
                queries=queries,backend=backend,limits=limits,decimal_places=16)


def qiskit_reference():
    # Optional reference only: independent forward tableau, no native pullback.
    import qiskit
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Clifford, Pauli, StabilizerState
    qc=QuantumCircuit(N)
    for name,qs in seeded_operations():getattr(qc,name)(*qs)
    tableau=Clifford(qc); state=StabilizerState(tableau)
    witness=Pauli('Z'*N).evolve(tableau,frame='s')
    witness.phase=0
    label=witness.to_label()
    witness_word={str(q):p for q,p in enumerate(reversed(label)) if p!='I'}
    queries=[expectation('global_x',word('X')),expectation('global_z',word('Z')),
             expectation('dense_stabilizer',witness_word),probability('end_00',{'0':0,'2055':0})]

    def exact_read(paulis):
        label=''.join(paulis.get(str(q),'I') for q in reversed(range(N)))
        value=complex(state.expectation_value(Pauli(label)))
        if value.imag or value.real not in (-1,0,1):raise ArithmeticError('non-stabilizer reference value')
        return Exact(int(value.real))

    values={q['id']:exact_read(q['paulis']).to_dict() for q in queries if q['kind']=='expectation'}
    total=ONE+exact_read({'0':'Z'})+exact_read({'2055':'Z'})+exact_read({'0':'Z','2055':'Z'})
    values['end_00']=(total*Exact(Fraction(1,4))).to_dict()
    if values['dense_stabilizer'] not in (ONE.to_dict(),(-ONE).to_dict()):
        raise ArithmeticError('dense independent stabilizer witness failed')
    return dict(method='Qiskit independent forward Clifford tableau and StabilizerState Pauli observations',
                version=qiskit.__version__,seed=2056,rounds=4,gates=len(seeded_operations()),
                witness_support=len(witness_word),queries=queries,expected_values=values,
                performance_comparison=False)


def expected(case, reference):
    if case=='seeded_clifford':return reference['expected_values']
    if case=='ghz_global':return dict(global_x=ONE.to_dict(),global_z=ONE.to_dict(),
                                     local_z=ZERO.to_dict(),end_zz=ONE.to_dict())
    if case=='ghz_full_probability':return dict(all_zero=Exact(Fraction(1,2)).to_dict(),mismatch=ZERO.to_dict())
    if case in ('ghz_t','ghz_tdg'):
        return dict(global_x=INV_SQRT2.to_dict(),
                    global_y=(INV_SQRT2 if case=='ghz_t' else -INV_SQRT2).to_dict(),
                    end_00=Exact(Fraction(1,2)).to_dict())
    if case=='uniform_full_probability':return dict(all_zero=Exact(Fraction(1,1<<N)).to_dict())
    if case=='six_t_global':return dict(global_mixed=Exact(Fraction(1,8)).to_dict())
    return {}


def prepare():
    reference=qiskit_reference()
    return dict(schema='nrqc-2056-qualification-v1',author='Monty',
        created_utc=datetime.now(timezone.utc).isoformat(),n_qubits=N,repetitions=3,
        order='round-robin in declared case order',source_sha256=source_hashes(),
        independent_reference=reference,
        scope='ideal selected observations; no hardware, no noise, no general T-depth efficiency claim',
        protocol_frozen_before_measured_runs=True,
        cases=[dict(name=name,request_sha256=_digest(validate(request(name,reference))[1]),
                    timeout_seconds=1e-9 if name=='wall_limit' else 60,
                    expected_status='time_limit' if name=='wall_limit' else
                        ('incomplete' if name.endswith('_limit') else 'completed'),
                    expected_values=expected(name,reference)) for name in CASES])


def check(case,report):
    if report['status']!=case['expected_status']:
        raise AssertionError(f"{case['name']}: unexpected status {report['status']}")
    if report['request_sha256']!=case['request_sha256']:raise AssertionError('request mismatch')
    if report['status']=='time_limit':
        if report['answers']:raise AssertionError('wall timeout returned a partial batch')
        return
    answers={row['id']:row for row in report['answers']}
    if report['status']=='incomplete':
        for row in answers.values():
            if row['status']!='resource_limit' or 'value' in row or 'probabilities' in row:
                raise AssertionError('resource failure returned an answer')
        return
    for label,value in case['expected_values'].items():
        if answers[label]['value']['exact']!=value:raise AssertionError(f'{label}: exact mismatch')
    if case['name']=='ghz_t':
        g=answers['emk']['geometry']
        if (g['real_tangent_rank'],g['complex_gram_rank'])!=(2,1):raise AssertionError('geometry ranks')
        if not g['dependencies']['full_tensor_reconstruction_exact']:raise AssertionError('tensor reconstruction')
        for a,b in ((1,2),(2,0)):
            if g['curvature'][a][b]['exact']!=INV_SQRT2.to_dict():raise AssertionError('curvature phase')


def run(protocol, output):
    if protocol['source_sha256']!=source_hashes():raise ValueError('source changed after protocol freeze')
    result=dict(schema='nrqc-2056-results-v1',author='Monty',
                protocol_sha256=_digest(protocol),python=sys.version,platform=platform.platform(),
                started_utc=datetime.now(timezone.utc).isoformat(),runs=[])
    for repetition in range(protocol['repetitions']):
        for case in protocol['cases']:
            document=request(case['name'],protocol['independent_reference'])
            report=run_calculation(document,timeout_seconds=case['timeout_seconds'])
            row=dict(case=case['name'],repetition=repetition+1,report=report)
            result['runs'].append(row)
            output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
            check(case,report)
            row['expected_outcome_verified']=True
            print(f"{repetition+1} {case['name']}: {report['status']} {report['wall_seconds']:.6f}s",flush=True)
    summaries=[]
    for case in protocol['cases']:
        reports=[r['report'] for r in result['runs'] if r['case']==case['name']]
        rss=[r['peak_worker_rss_bytes'] for r in reports if r.get('peak_worker_rss_bytes') is not None]
        summaries.append(dict(case=case['name'],status=case['expected_status'],
            median_wall_seconds=statistics.median(r['wall_seconds'] for r in reports),
            wall_seconds_range=[min(r['wall_seconds'] for r in reports),max(r['wall_seconds'] for r in reports)],
            maximum_peak_worker_rss_bytes=max(rss) if rss else None))
    result.update(completed_utc=datetime.now(timezone.utc).isoformat(),all_expected_outcomes_verified=True,
                  summaries=summaries)
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',action='store_true')
    action.add_argument('--run',action='store_true')
    action.add_argument('--example',choices=CASES)
    parser.add_argument('--protocol',type=Path,default=ROOT/'native_relational_qc/large_register_protocol.json')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.prepare:value=prepare()
    else:
        protocol=json.loads(args.protocol.read_text())
        if args.run:
            run(protocol,args.out);return
        value=request(args.example,protocol['independent_reference'])
    args.out.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':main()
