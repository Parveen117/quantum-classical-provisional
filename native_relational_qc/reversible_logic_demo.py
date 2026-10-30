"""Generate calculator examples and verify coherent arithmetic and search.

Run: python -m native_relational_qc.reversible_logic_demo --example search
or:  python -m native_relational_qc.reversible_logic_demo --verify --out RESULT.json
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import time

from .calculator import run_calculation
from .compact import CompactCircuit,CompactState
from .entropy_logic import ThresholdModel,transport_split,expected_carry_activity
from .exact import ONE,INV_SQRT2,OMEGA,IMAG
from .reversible_logic import BooleanMap,compile_oracle,gate_function,ripple_adder


def addition_example():
    program=ripple_adder(4);circuit=CompactCircuit(17)
    word=7|(9<<4)|(1<<8)
    for q in program.inputs:
        if word&(1<<q):circuit.add('x',q)
    program.append_to(circuit)
    return request(circuit,[
        dict(id='7_plus_9_plus_1_equals_17',kind='probability',outcomes={str(q):(17>>i)&1 for i,q in enumerate(program.outputs)}),
        dict(id='temporary_carries_clean',kind='probability',outcomes={str(q):0 for q in program.scratch})])


def kickback_example():
    oracle=compile_oracle(gate_function('xor'))
    circuit=CompactCircuit(3).add('h',0).add('h',1).add('x',2).add('h',2)
    oracle.append_to(circuit)
    circuit.add('h',0).add('h',1)
    return request(circuit,[dict(id='interference_11',kind='probability',outcomes={'0':1,'1':1}),
                            dict(id='phase_marker_x',kind='expectation',paulis={'2':'X'})])


def addition_search_circuit(*, uncompute=True):
    """One exact Grover iteration finds A in {0,1,2,3} with A+1=3.

    This is an 11-qubit ideal software example, not a runtime-speedup claim.
    uncompute=False is a deliberate negative control, not a valid alternative
    implementation of the search oracle.
    """
    if type(uncompute) is not bool:
        raise ValueError('uncompute must be boolean')
    adder=ripple_adder(2)
    equals_three=compile_oracle(BooleanMap(3,1,tuple(int(x==3) for x in range(8))))
    marker=9;comparison_scratch=(10,)
    circuit=CompactCircuit(11)
    for q in (0,1):circuit.add('h',q)
    circuit.add('x',2)
    circuit.add('x',marker).add('h',marker)
    adder.append_to(circuit)
    equals_three.append_to(circuit,(*adder.outputs,marker,*comparison_scratch))
    if uncompute:
        adder.append_to(circuit,inverse=True)
    # Diffusion on A. The overall minus sign is retained in exact execution.
    for q in (0,1):circuit.add('h',q).add('x',q)
    circuit.add('cz',0,1)
    for q in (0,1):circuit.add('x',q).add('h',q)
    return circuit


def search_example():
    circuit=addition_search_circuit()
    return request(circuit,[dict(id='found_A_2',kind='probability',outcomes={'0':0,'1':1}),
                            dict(id='workspace_clean',kind='probability',outcomes={str(q):0 for q in (5,6,7,8,10)})])


def request(circuit,queries):
    # CCX and nonadjacent gates explicitly select the existing observer backend.
    return dict(schema='nrqc-calculator-v1',n_qubits=circuit.n_qubits,backend='observer',
                operations=[[name,list(qs)] for name,qs in circuit.operations],queries=queries)


def _require(condition,message):
    if not condition:
        raise ArithmeticError(message)


def verify():
    started=time.perf_counter();program=ripple_adder(4)
    state=CompactState(17)
    for q in program.inputs:state.apply('h',q)
    state.apply('t',0).apply('s',4)
    before=state.fingerprint()
    for name,qs in program.circuit.operations:state.apply(name,*qs)
    factor=INV_SQRT2**9
    for word in range(512):
        total=(word&15)+((word>>4)&15)+(word>>8)
        wanted=factor*(OMEGA if word&1 else ONE)*(IMAG if word&16 else ONE)
        _require(state.amplitude(word|(total<<9))==wanted,f'incorrect coherent adder amplitude: {word}')
    _require(state.probability({q:0 for q in program.scratch})==ONE,'adder workspace is not clean')
    stats=state.stats()
    for name,qs in reversed(program.circuit.operations):state.apply(name,*qs)
    _require(state.fingerprint()==before,'inverse failed to restore the initial state')
    coherent_seconds=time.perf_counter()-started
    good,bad=addition_search_circuit().state(),addition_search_circuit(uncompute=False).state()
    good_probability=good.probability({0:0,1:1})
    bad_probability=bad.probability({0:0,1:1})
    _require(good_probability==ONE and bad_probability.to_dict()['coefficients']==['1/4','0','0','0'],
             'search or its negative control has the wrong probability')
    _require(good.probability({q:0 for q in (5,6,7,8,10)})==ONE,'search workspace is not clean')
    threshold=ThresholdModel(k3=1,theta=2,threshold=2,margin=1,high_is_one=False)
    threshold_report=threshold.check(gate_function('nand'))
    _require(threshold_report['passed'],'NAND threshold example failed')
    transport=transport_split(((2,3),(-1,4)),(1,2))
    sources=('reversible_logic.py','entropy_logic.py','reversible_logic_demo.py','compact.py','exact.py','calculator.py','observer.py')
    output=dict(schema='nrqc-reversible-logic-verification-v1',python=platform.python_version(),
                source_sha256={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in sources},
                four_bit_adder={k:v for k,v in program.to_dict().items() if k!='operations'},
                coherent_arithmetic=dict(exact_complex_amplitudes_checked=512,workspace_clean=True,
                    inverse_restores_exact_fingerprint=True,calculation_and_check_seconds=coherent_seconds,statistics=stats,
                    statevector_constructed=False),
                search=dict(input_domain=[0,1,2,3],predicate='A+1=3',solution=2,grover_iterations=1,
                    probability=good_probability.to_dict(),without_uncomputation=bad_probability.to_dict(),workspace_clean=True),
                threshold_model=threshold_report,
                algebra_checks=dict(transport_quadratic=str(transport['total']),
                    antisymmetric_quadratic=str(transport['antisymmetric']),
                    four_bit_activity_fair_cin=str(expected_carry_activity(4)),
                    four_bit_activity_zero_cin=str(expected_carry_activity(4,Fraction(0)))),
                calculator_examples={},physical_energy_estimated=False,hardware_job_id=None)
    for name,document in (('addition',addition_example()),('kickback',kickback_example()),('search',search_example())):
        result=run_calculation(document,timeout_seconds=20)
        output['calculator_examples'][name]=result
        if result['status']!='completed':
            raise RuntimeError(f'{name} calculator example did not complete')
        for row in result['answers']:
            wanted=['-1','0','0','0'] if row['id']=='phase_marker_x' else ['1','0','0','0']
            if row['value']['exact']['coefficients']!=wanted:
                raise ArithmeticError(f'{name}: incorrect exact observation')
    output['all_checks_pass']=True
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--example',choices=('addition','kickback','search'))
    mode.add_argument('--verify',action='store_true')
    parser.add_argument('--out')
    args=parser.parse_args()
    result=verify() if args.verify else {'addition':addition_example,'kickback':kickback_example,'search':search_example}[args.example]()
    text=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.out:Path(args.out).write_text(text)
    else:print(text,end='')
