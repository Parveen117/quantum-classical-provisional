"""Reproducible structured benefit and random-circuit boundary checks.

Each calculator row uses a fresh process, the same explicit resource limits,
and a 20-second whole-worker wall cap. Failures are retained. No quantum SDK.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics

from .calculator import run_calculation
from .compact import CompactCircuit
from .stress_benchmark import brickwork


def echo_circuit(n=50, base_rounds=4, echo_rounds=16):
    """Deliberately reducible: base, U, U-dagger; not generic deep simulation."""
    base = brickwork(n, base_rounds, 20261018)
    block = brickwork(n, echo_rounds, 20261023)
    inverse = {'h':'h','t':'tdg','tdg':'t','sx':'sxdg','sxdg':'sx','cz':'cz'}
    out = CompactCircuit(n)
    for name, qubits in (base.operations + block.operations +
                         tuple((inverse[name],qs) for name,qs in reversed(block.operations))):
        out.add(name, *qubits)
    return out


def request(circuit, query, simplify='none'):
    n = circuit.n_qubits
    query = (dict(id='parity',kind='expectation',paulis={str(q):'Z' for q in range(n)})
             if query == 'parity' else
             dict(id='local00',kind='probability',outcomes={str(n//2-1):0,str(n//2):0}))
    return dict(schema='nrqc-calculator-v1',n_qubits=n,
                operations=[[name,list(qs)] for name,qs in circuit.operations],
                queries=[query],simplify=simplify,limits={'max_work':100_000_000})


def _value(report):
    if report['status'] != 'completed':
        return None
    return report['answers'][0]['value']['exact']


def run(output):
    import numpy
    from .observer import expectation
    results = dict(schema='nrqc-exact-reduction-benchmark-v1',
                   protocol='declared engineering benchmark; fixed cases after development pilots',
                   python=platform.python_version(),numpy=numpy.__version__,
                   timeout_seconds=20,rows=[],checks={})
    paths = ('reduction.py','calculator.py','reduction_benchmark.py','compact.py',
             'exact.py','factored.py','integer_matrix.py','dyadic.py','stress_benchmark.py')
    results['source_sha256'] = {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                for name in paths}
    cases = [('base50','parity',brickwork(50,4,20261018),'none',1),
             ('echo50','parity',echo_circuit(),'none',1),
             ('echo50','parity',echo_circuit(),'exact',3),
             ('small_echo','parity',echo_circuit(6,2,2),'none',1),
             ('small_echo','parity',echo_circuit(6,2,2),'exact',1)]
    for rounds in (12,16):
        for method in ('none','exact'):
            cases.append((f'random50_{rounds}r','local00',brickwork(50,rounds,20261018),method,1))
    for case,query,circuit,method,repeats in cases:
        for repeat in range(repeats):
            report = run_calculation(request(circuit,query,method),timeout_seconds=20)
            results['rows'].append(dict(case=case,query=query,simplify=method,repeat=repeat+1,result=report))
            Path(output).write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
            print(case,method,repeat+1,report['status'],round(report['wall_seconds'],3),flush=True)
    rows = results['rows']
    pick = lambda case,method:[r['result'] for r in rows if r['case']==case and r['simplify']==method]
    base = _value(pick('base50','none')[0])
    echo = pick('echo50','exact')
    results['checks']['all_reduced_echo_values_equal_exact_base'] = base is not None and all(_value(r)==base for r in echo)
    # The algorithm may move a gate past disjoint gates. Compare each wire's
    # ordered projection, a certificate of equivalence by disjoint swaps;
    # byte-identical circuit hashes are not required for equal operators.
    from .reduction import reduce_circuit
    reduced = reduce_circuit(echo_circuit())
    original = brickwork(50,4,20261018)
    results['checks']['echo_matches_base_wire_orders_and_phase'] = reduced.phase_exponent == 0 and all(
        tuple(op for op in original.operations if q in op[1]) ==
        tuple(op for op in reduced.circuit.operations if q in op[1]) for q in range(50))
    execution_hash = hashlib.sha256(json.dumps(dict(n_qubits=50,
        operations=[[name,list(qs)] for name,qs in reduced.circuit.operations]),
        sort_keys=True,separators=(',',':')).encode()).hexdigest()
    results['checks']['echo_execution_hashes_match_reproduced_reduction'] = all(
        r.get('execution_circuit_sha256')==execution_hash for r in echo)
    # Different native algorithm, exact coefficients, small complete echo.
    independent = expectation(echo_circuit(6,2,2),{q:'Z' for q in range(6)},max_work=100_000_000).value.to_dict()
    results['small_expanded_observer_reference'] = independent
    results['checks']['small_echo_both_match_expanded_observer'] = all(
        _value(r)==independent for method in ('none','exact') for r in pick('small_echo',method))
    a,b = pick('random50_12r','none')[0],pick('random50_12r','exact')[0]
    results['checks']['random12_values_equal'] = _value(a) is not None and _value(a)==_value(b)
    results['checks']['random16_no_false_completion'] = all(
        r['status']!='completed' for method in ('none','exact') for r in pick('random50_16r',method))
    results['echo_exact_medians'] = {
        key:statistics.median(r[key] for r in echo) for key in ('execution_seconds','wall_seconds','peak_worker_rss_bytes')}
    results['all_checks_pass'] = all(results['checks'].values())
    Path(output).write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
    return results['all_checks_pass']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='/tmp/reduction_results.json')
    parser.add_argument('--example',help='Write the 50-qubit echo JSON and exit')
    args = parser.parse_args()
    if args.example:
        Path(args.example).write_text(json.dumps(request(echo_circuit(),'parity','exact'),indent=2)+'\n')
    else:
        raise SystemExit(0 if run(args.output) else 1)
