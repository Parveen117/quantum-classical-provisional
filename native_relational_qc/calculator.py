"""Exact ideal-circuit calculator with strict JSON input and bounded execution."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from math import isfinite, isqrt
import os
from pathlib import Path
import subprocess
import sys
import time

from .compact import CompactCircuit, ResourceLimit, _integer
from .exact import Exact, ONE, ZERO

INPUT_SCHEMA = 'nrqc-calculator-v1'
OUTPUT_SCHEMA = 'nrqc-calculator-result-v1'
MAX_INPUT_BYTES = 2 * 1024 * 1024
DEFAULT_LIMITS = dict(max_work=10_000_000, max_coefficient_bits=4096,
                      max_bond=256, max_coefficients=1_000_000, max_terms=100_000,
                      max_generators=2056)
LIMIT_RANGES = dict(max_work=(1,1_000_000_000), max_coefficient_bits=(2,8192),
                    max_bond=(1,1024), max_coefficients=(1,1_000_000),
                    max_terms=(1,1_000_000), max_generators=(1,2056))


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _object(value, required, optional=()):
    if not isinstance(value, dict) or set(required)-value.keys() or value.keys()-set(required)-set(optional):
        raise ValueError('object requires keys ' + ', '.join(sorted(required)) +
                         '; optional keys: ' + ', '.join(sorted(optional)))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def loads(text):
    """Reject duplicate keys and non-JSON numeric constants instead of guessing."""
    if len(text.encode('utf-8')) > MAX_INPUT_BYTES:
        raise ValueError('calculator input exceeds 2 MiB')
    def reject(value):
        raise ValueError('invalid JSON numeric constant: ' + value)
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=reject)


def _site_map(value, n, paulis=False):
    if not isinstance(value, dict):
        raise ValueError('query site map must be an object with decimal qubit keys')
    out = {}
    for key, reading in value.items():
        if not isinstance(key,str) or not key.isascii() or not key.isdecimal() or str(int(key)) != key:
            raise ValueError('qubit keys must be canonical nonnegative decimal strings')
        q = _integer(int(key), 'qubit', 0, n-1)
        if paulis:
            if reading not in ('I','X','Y','Z'):
                raise ValueError('Pauli readings must be I/X/Y/Z')
        else:
            _integer(reading, 'outcome', 0, 1)
        out[q] = reading
    return out


def _geometry_generators(value, n):
    from .emk_tensor import validate_generators
    if not isinstance(value,list) or not 1<=len(value)<=8:
        raise ValueError('geometry requires 1..8 signed Pauli generators')
    generators=[]
    for item in value:
        _object(item,('paulis',),('sign',))
        generators.append((item.get('sign',1),_site_map(item['paulis'],n,paulis=True)))
    return validate_generators(generators,n)


def validate(document):
    _object(document, ('schema','n_qubits','operations','queries'),
            ('backend','decimal_places','limits','simplify','contraction'))
    if document['schema'] != INPUT_SCHEMA:
        raise ValueError('unsupported calculator input schema')
    backend = document.get('backend','factored')
    if backend not in ('factored','observer','stabilizer','clifford_t'):
        raise ValueError('backend must be factored, observer, stabilizer or clifford_t; no implicit fallback')
    if backend in ('stabilizer','clifford_t'):
        from .large_register import LargeCircuit
        circuit = LargeCircuit(document['n_qubits'])
    else:
        circuit = CompactCircuit(document['n_qubits'])
    contraction = document.get('contraction','integer')
    if contraction not in ('integer','sparse','reuse','streaming'):
        raise ValueError('contraction must be integer, sparse, reuse or streaming')
    if backend != 'factored' and 'contraction' in document:
        raise ValueError('contraction applies only to the factored backend')
    simplify = document.get('simplify','none')
    if simplify not in ('none','exact'):
        raise ValueError('simplify must be none or exact')
    operations = document['operations']
    if not isinstance(operations,list) or len(operations)>100_000:
        raise ValueError('operations must be a list of at most 100000 gates')
    for operation in operations:
        if (not isinstance(operation,list) or len(operation)!=2 or
            not isinstance(operation[0],str) or not isinstance(operation[1],list)):
            raise ValueError('each operation must be [gate_name, [qubit_indices]]')
        name, qs = operation
        circuit.add(name,*qs)
        if backend == 'factored' and (len(qs)>2 or (len(qs)==2 and abs(qs[0]-qs[1])!=1)):
            raise ValueError('factored backend needs adjacent two-site gates; route explicitly or select observer')
    if backend in ('stabilizer','clifford_t'):
        from .pauli_engine import compile_plan
        compile_plan(circuit,allow_t=backend=='clifford_t')
    digits = _integer(document.get('decimal_places',12),'decimal_places',0,60)
    supplied = document.get('limits',{})
    applicable = {'max_work','max_coefficient_bits'} | {
        'factored':{'max_bond','max_coefficients'}, 'observer':{'max_terms'},
        'stabilizer':{'max_generators'}, 'clifford_t':{'max_terms'}}[backend]
    _object(supplied, (), applicable)
    limits = {k:DEFAULT_LIMITS[k] for k in applicable}
    for k,v in supplied.items():
        limits[k] = _integer(v,k,*LIMIT_RANGES[k])
    queries = document['queries']
    if not isinstance(queries,list) or not 1<=len(queries)<=32:
        raise ValueError('queries must contain 1..32 entries')
    seen, evaluations = set(), 0
    for query in queries:
        if not isinstance(query,dict):
            raise ValueError('each query must be an object')
        kind = query.get('kind')
        field = {'probability':'outcomes','expectation':'paulis','distribution':'qubits',
                 'geometry':'generators'}.get(kind)
        if field is None:
            raise ValueError('query kind must be probability, expectation, distribution or geometry')
        _object(query, ('id','kind',field))
        label = query['id']
        if not isinstance(label,str) or not 1<=len(label)<=80 or label in seen:
            raise ValueError('query IDs must be unique nonempty strings of at most 80 characters')
        seen.add(label)
        if kind=='geometry':
            from .emk_tensor import evaluation_count
            evaluations += evaluation_count(_geometry_generators(query[field],circuit.n_qubits))
        elif kind=='distribution':
            sites=query[field]
            if not isinstance(sites,list) or not 1<=len(sites)<=8:
                raise ValueError('distribution queries require 1..8 distinct qubits')
            for q in sites:
                _integer(q,'qubit',0,circuit.n_qubits-1)
            if len(set(sites))!=len(sites):
                raise ValueError('distribution qubits must be distinct')
            evaluations += 2**len(sites)
        else:
            _site_map(query[field],circuit.n_qubits,paulis=kind=='expectation')
            evaluations += 1
    if evaluations>256:
        raise ValueError('a request may contain at most 256 scalar evaluations')
    canonical = dict(schema=INPUT_SCHEMA,n_qubits=circuit.n_qubits,
                     operations=[[name,list(qs)] for name,qs in circuit.operations],
                     queries=queries,backend=backend,decimal_places=digits,limits=limits)
    if simplify == 'exact':
        canonical['simplify'] = simplify
    if contraction != 'integer':
        canonical['contraction'] = contraction
    return circuit, canonical


def real_sign(value):
    """Compare a+b*sqrt(2) to zero using rational arithmetic only."""
    if value.c or value.d:
        raise ValueError('a real value is required')
    a,b=value.a,value.b
    sign=lambda x:(x>0)-(x<0)
    if not a:return sign(b)
    if not b or sign(a)==sign(b):return sign(a)
    return sign(a*a-2*b*b) if a>0 else sign(2*b*b-a*a)


def _fixed(n, places):
    sign='-' if n<0 else ''; n=abs(n)
    if not places:return sign+str(n)
    scale=10**places
    return f'{sign}{n//scale}.{n%scale:0{places}d}'


def display(value, decimal_places=12):
    """Return an exact value and a rationally certified decimal enclosure.

    Integer square root bounds sqrt(2); directed integer division rounds the
    resulting rational bounds outwards. The midpoint's error bound concerns
    decimal display, not uncertainty in the exact computation or hardware.
    """
    places=_integer(decimal_places,'decimal_places',0,60)
    if value.c or value.d:raise ValueError('only real observations can be displayed')
    a,b=value.a,value.b
    # |b| < 2**bits <= 10**extra; 30103/100000 > log10(2).
    bits=max(0,abs(b.numerator).bit_length()-b.denominator.bit_length()+1)
    extra=(bits*30103+99999)//100000
    precision=places+extra+4; denominator=10**precision
    root=isqrt(2*denominator*denominator)
    lower,upper=Fraction(root,denominator),Fraction(root+1,denominator)
    if b<0:lower,upper=upper,lower
    lower,upper=a+b*lower,a+b*upper
    scale=10**places
    low=(lower*scale).__floor__(); high=(upper*scale).__ceil__()
    expression=str(a) if not b else (f'{b}*sqrt(2)' if not a else f'({a}) + ({b})*sqrt(2)')
    return dict(exact=value.to_dict(),expression=expression,
                decimal=_fixed((low+high)*5,places+1),
                decimal_enclosure=dict(lower=_fixed(low,places),upper=_fixed(high,places),
                    maximum_absolute_display_error=str(Fraction(high-low,2*scale)),
                    method='integer-square-root bounds and outward rational rounding'))


def _summary(observations):
    maxima,totals={},{}
    for observation in observations:
        for k,v in observation.items():
            if k.startswith('peak_') or k=='max_coefficient_bits':
                maxima[k]=max(maxima.get(k,0),v)
            if k in ('scalar_products','term_visits','row_products','forward_gates','gates_examined'):
                totals[k]=totals.get(k,0)+v
    return dict(completed_scalar_evaluations=len(observations),maxima=maxima,work_totals=totals)


def calculate(document):
    """In-process API: exact backend budgets apply; no wall-clock/RSS guard."""
    circuit,request=validate(document)
    if request['backend']=='factored':
        from .factored import probability,expectation
    elif request['backend']=='stabilizer':
        from .stabilizer import probability,expectation
    elif request['backend']=='clifford_t':
        from .clifford_t import probability,expectation
    else:
        from .observer import probability,expectation
    started=time.perf_counter()
    reduction = None
    if request.get('simplify') == 'exact':
        from .reduction import reduce_circuit
        reduction = reduce_circuit(circuit)
        circuit = reduction.circuit
    simplification_seconds = time.perf_counter()-started
    report=dict(schema=OUTPUT_SCHEMA,status='completed',
                evidence_class='LOCAL_IDEAL_CALCULATION',hardware_job_id=None,
                input_state='all_zero',backend=request['backend'],
                circuit_sha256=_digest(dict(n_qubits=circuit.n_qubits,operations=request['operations'])),
                request_sha256=_digest(request),n_qubits=circuit.n_qubits,
                gates=len(request['operations']),limits_per_scalar_evaluation=request['limits'],answers=[])
    options = dict(request['limits'])
    if request['backend'] == 'factored':
        options['contraction'] = request.get('contraction','integer')
    if reduction is not None:
        report['simplification'] = dict(reduction.to_dict(),execution_seconds=simplification_seconds)
        report['execution_circuit_sha256'] = _digest(dict(n_qubits=circuit.n_qubits,
            operations=[[name,list(qs)] for name,qs in circuit.operations]))
    for query in request['queries']:
        start=time.perf_counter(); observations=[]
        row=dict(id=query['id'],kind=query['kind'])
        try:
            if query['kind']=='geometry':
                from .emk_tensor import geometry, serialize
                tensor=geometry(circuit,_geometry_generators(query['generators'],circuit.n_qubits),
                                backend=request['backend'],**options)
                row.update(status='completed',algebraically_exact=True,
                           geometry=serialize(tensor,lambda v:display(v,request['decimal_places'])),
                           statistics=_summary(tensor['scalar_statistics']))
            elif query['kind']=='distribution':
                sites=query['qubits']; values={}; total=ZERO
                for i in range(2**len(sites)):
                    label=format(i,f'0{len(sites)}b')
                    obs=probability(circuit,{q:int(bit) for q,bit in zip(sites,label)},**options)
                    if real_sign(obs.value)<0 or real_sign(ONE-obs.value)<0:
                        raise ArithmeticError('probability outside [0,1]')
                    observations.append(obs.to_dict());total+=obs.value
                    values[label]=display(obs.value,request['decimal_places'])
                if total!=ONE:raise ArithmeticError('distribution does not sum to one exactly')
                row.update(status='completed',algebraically_exact=True,probabilities=values,
                           bitstring_qubits_left_to_right=sites,normalization=total.to_dict(),
                           statistics=_summary(observations))
            else:
                is_expectation=query['kind']=='expectation'
                field='paulis' if is_expectation else 'outcomes'
                target=_site_map(query[field],circuit.n_qubits,paulis=is_expectation)
                obs=(expectation if is_expectation else probability)(circuit,target,**options)
                minimum=-ONE if is_expectation else ZERO
                if real_sign(obs.value-minimum)<0 or real_sign(ONE-obs.value)<0:
                    raise ArithmeticError('observation outside its mathematical range')
                statistics=obs.to_dict();statistics.pop('value')
                row.update(status='completed',algebraically_exact=True,
                           value=display(obs.value,request['decimal_places']),statistics=statistics)
        except ResourceLimit as error:
            row.update(status='resource_limit',algebraically_exact=False,error=str(error),
                       statistics=getattr(error,'statistics',{}))
            if observations:row['discarded_partial_distribution_cost']=_summary(observations)
            report['status']='incomplete'
        row['execution_seconds']=time.perf_counter()-start
        report['answers'].append(row)
    report['execution_seconds']=time.perf_counter()-started
    return report


def run_calculation(document, *, timeout_seconds=20):
    """Fresh-process API. Wall cap covers the entire batch and worker startup.

    A wall timeout returns no answers, including any unfinished batch prefix.
    Internal resource failures may coexist with completed independent queries.
    No total RSS cap is promised by this wrapper.
    """
    if (isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float)) or
        not isfinite(timeout_seconds) or not 0<timeout_seconds<=300):
        raise ValueError('timeout_seconds must be finite, greater than zero, and at most 300')
    _,canonical=validate(document)
    data=_json(canonical)
    if len(data.encode())>MAX_INPUT_BYTES:raise ValueError('calculator input exceeds 2 MiB')
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
    started=time.perf_counter()
    try:
        process=subprocess.run([sys.executable,'-m','native_relational_qc.calculator','--worker'],
                               input=data,text=True,capture_output=True,timeout=timeout_seconds,env=env)
    except subprocess.TimeoutExpired:
        return dict(schema=OUTPUT_SCHEMA,status='time_limit',answers=[],
                    request_sha256=_digest(canonical),timeout_seconds=timeout_seconds,
                    wall_seconds=time.perf_counter()-started,algebraically_exact=False,
                    error='Batch exceeded its wall budget; no partial batch is returned.')
    if process.returncode not in (0,1,2):
        return dict(schema=OUTPUT_SCHEMA,status='worker_error',answers=[],
                    request_sha256=_digest(canonical),error='Calculator worker terminated without a result.',
                    worker_exit_code=process.returncode,wall_seconds=time.perf_counter()-started)
    try:
        result=json.loads(process.stdout)
    except (ValueError,TypeError):
        result=dict(schema=OUTPUT_SCHEMA,status='worker_error',answers=[],error='Invalid worker result.')
    result.update(wall_seconds=time.perf_counter()-started,timeout_seconds=timeout_seconds)
    return result


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    worker=argv==['--worker']
    if not worker:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('input',help='JSON request path, or - for stdin')
        parser.add_argument('--out',type=Path)
        parser.add_argument('--timeout',type=float,default=20,help='whole-batch wall seconds, including worker startup')
        args=parser.parse_args(argv)
    try:
        if worker or args.input=='-':
            raw=sys.stdin.buffer.read(MAX_INPUT_BYTES+1)
        else:
            with Path(args.input).open('rb') as stream:raw=stream.read(MAX_INPUT_BYTES+1)
        if len(raw)>MAX_INPUT_BYTES:raise ValueError('calculator input exceeds 2 MiB')
        document=loads(raw.decode('utf-8'))
        result=calculate(document) if worker else run_calculation(document,timeout_seconds=args.timeout)
        if worker:
            try:
                result['peak_worker_rss_bytes']=next(
                    int(line.split()[1])*1024 for line in Path('/proc/self/status').read_text().splitlines()
                    if line.startswith('VmHWM:'))
                result['peak_worker_rss_source']='Linux /proc/self/status VmHWM, including imports/setup'
            except (OSError,StopIteration):
                result['peak_worker_rss_bytes']=None
    except (ValueError,TypeError,OSError,RecursionError) as error:
        result=dict(schema=OUTPUT_SCHEMA,status='invalid_request',answers=[],error=str(error))
    except (ArithmeticError,MemoryError) as error:
        result=dict(schema=OUTPUT_SCHEMA,status='calculation_error',answers=[],error=str(error))
    rendered=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n'
    if not worker and args.out:
        args.out.write_text(rendered,encoding='utf-8')
    print(rendered,end='')
    return 0 if result['status']=='completed' else (2 if result['status']=='invalid_request' else 1)


if __name__=='__main__':
    raise SystemExit(main())
