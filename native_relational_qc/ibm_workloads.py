"""Execute pinned IBM logical workloads on native software registers.

Default execution reads saved native programs and does not import Qiskit/Aer.
Preparation and an optional independent local reference use the original Qiskit
builders. No Runtime service, account, hardware job or physical qubit is used.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

from .dynamic import DynamicCircuit, probability
from .exact import ZERO
from .readout import classical_distribution

ROOT = Path(__file__).resolve().parents[1]
INPUTS = Path(__file__).with_name('ibm_workload_inputs.json')
SOURCE_COMMIT = '2a9eaf3e54e56236f1a92caf0a799f2e953ec125'
SOURCE_BLOBS = {"qec_error_control_lab/qec_repetition.py":"3d121d267ccd88785f59d54de2aed1d576bc5679","qec_error_control_lab/qec_shor.py":"6581d5b46b1153bffc86c2b3a6205ef78b5eed22","qec_error_control_lab/qec_circuit_spec.py":"0827f2d4e15b54a9818a3fc5dc75d1ff119c5e24","qec_error_control_lab/ibm_shor_3round_hardware.py":"1463391fc1ce42e43b54acafec4d3e19aa7023fa","qec_error_control_lab/hardware_evidence/ibm_shor_3round_submission_da2sogk3jnrc73aebcfg.json":"a51890a7e976c69024da8772e35be698944970cb","qec_error_control_lab/hardware_evidence/ibm_shor_submission_da2raps3jnrc73ae9n80.json":"392653bc4d8f7fafa461de5755fad2d2892412ff","qec_error_control_lab/hardware_evidence/da2raps3jnrc73ae9n80_hardware_certificate.json":"b155f84a0579e8dacc54200c538d4e5e088acc9d"}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _sources():
    hashes = {}
    for name, expected in SOURCE_BLOBS.items():
        data = (ROOT/name).read_bytes()
        blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if blob != expected:
            raise ValueError('pinned source differs: '+name)
        hashes[name] = hashlib.sha256(data).hexdigest()
    return hashes


def _originals():
    _sources()
    sys.path.insert(0, str(ROOT/'qec_error_control_lab'))
    try:
        from qec_circuit_spec import materialize_qiskit_experiment
        from ibm_shor_3round_hardware import materialize_case, EXPECTED, ERRORS, protocol_specification
        receipt = json.loads((ROOT/'qec_error_control_lab/hardware_evidence/ibm_shor_3round_submission_da2sogk3jnrc73aebcfg.json').read_text())
        if protocol_specification()['spec_sha256'] != receipt['protocol_spec_sha256']:
            raise ValueError('three-round submitted specification hash does not match')
        return [(rounds, name, expected,
                 materialize_qiskit_experiment(injected_error=ERRORS[name]) if rounds == 1 else materialize_case(name))
                for rounds in (1, 3) for name, expected in EXPECTED.items()]
    finally:
        sys.path.pop(0)


def _encode(rounds, label, expected, qc):
    from .dynamic_qiskit import from_qiskit
    circuit = from_qiskit(qc)
    operations = []
    for op in circuit.operations:
        if op.condition or op.weights:
            raise ValueError('unexpected source instruction')
        operations.append([op.kind, op.name, list(op.qargs), op.cbit])
    return {'id': f'{rounds}round:{label}', 'rounds': rounds, 'case': label,
        'expected_syndrome_validation_only': expected, 'n_qubits': circuit.n_qubits,
        'n_clbits': circuit.n_clbits, 'operations': operations,
        'registers': {reg.name: [qc.find_bit(bit).index for bit in reg] for reg in qc.cregs},
        'ignored_barriers': sum(item.operation.name == 'barrier' for item in qc.data)}


def prepare():
    evidence = ROOT/'qec_error_control_lab/hardware_evidence'
    body = {'schema': 'native-ibm-shor-logical-inputs-v1', 'source_commit': SOURCE_COMMIT,
        'source_sha256': _sources(), 'source_git_blobs': SOURCE_BLOBS,
        'programs': [_encode(*item) for item in _originals()],
        'single_round_hardware': json.loads((evidence/'da2raps3jnrc73ae9n80_hardware_certificate.json').read_text()),
        'three_round_submission': json.loads((evidence/'ibm_shor_3round_submission_da2sogk3jnrc73aebcfg.json').read_text())}
    return {**body, 'input_sha256': _digest(body)}


def restore(program):
    circuit = DynamicCircuit(program['n_qubits'], program['n_clbits'])
    for kind, name, qargs, cbit in program['operations']:
        if kind == 'gate':
            circuit.add(name, *qargs)
        elif kind == 'measure' and len(qargs) == 1:
            circuit.measure(qargs[0], cbit)
        elif kind == 'reset' and len(qargs) == 1:
            circuit.reset(qargs[0])
        else:
            raise ValueError('unsupported saved workload instruction')
    return circuit


def _aer_reference(program):
    from qiskit_aer import AerSimulator
    for rounds, label, expected, qc in _originals():
        if f'{rounds}round:{label}' == program['id']:
            break
    else:
        raise ValueError('original circuit not found')
    if _encode(rounds, label, expected, qc) != program:
        raise ValueError('saved native input differs from original logical builder')
    # Replace only the terminal data readout with a saved Z distribution;
    # all syndrome measurements/resets remain in the original circuit.
    data_bits = program['registers']['data_readout']
    for _ in data_bits:
        last = qc.data.pop()
        if last.operation.name != 'measure' or qc.find_bit(last.clbits[0]).index not in data_bits:
            raise ValueError('unexpected terminal measurement layout')
    qc.save_probabilities(list(range(9)), label='data_probs')
    result = AerSimulator(method='stabilizer', max_parallel_threads=1).run(qc, shots=1, seed_simulator=731).result()
    if not result.success:
        raise RuntimeError('local Aer reference failed')
    values = result.data(0)
    counts = values['counts']
    if len(counts) != 1 or sum(counts.values()) != 1:
        raise ArithmeticError('unexpected trajectory result')
    memory = int(next(iter(counts)), 16)
    outcomes = {}
    for index, value in enumerate(values['data_probs']):
        if value:
            output = memory
            for q, bit in enumerate(data_bits):
                output = (output & ~(1 << bit)) | (((index >> q) & 1) << bit)
            outcomes[format(output, f'0{program["n_clbits"]}b')] = float(value)
    return outcomes


def run(*, compare_aer=False, run_tests=False):
    inputs = json.loads(INPUTS.read_text())
    digest = inputs.pop('input_sha256')
    if _digest(inputs) != digest or inputs['source_commit'] != SOURCE_COMMIT:
        raise ValueError('native input snapshot hash mismatch')
    rows = []
    for program in inputs['programs']:
        circuit = restore(program)
        start = time.perf_counter()
        distribution = classical_distribution(circuit, max_outcomes=16, max_queries=1000)
        elapsed = time.perf_counter()-start
        fixed = dict(distribution.deterministic_bits)
        syndromes = {}
        for name, bits in program['registers'].items():
            if name != 'data_readout':
                syndromes[name] = ''.join(str(fixed[bit]) for bit in reversed(bits))
        matches = all(s == program['expected_syndrome_validation_only'] for s in syndromes.values())
        row = {'id': program['id'], 'qubits': circuit.n_qubits, 'classical_bits': circuit.n_clbits,
            'native_instructions': len(circuit.operations), 'native_seconds': elapsed,
            'syndrome_registers': syndromes, 'expected_syndromes_match': matches,
            'distribution': distribution.to_dict()}
        if compare_aer:
            reference = _aer_reference(program)
            if any(value.b or value.c or value.d for _, value in distribution.probabilities):
                raise ArithmeticError('unexpected non-rational workload output')
            native = {key: float(value.a) for key, value in distribution.probabilities}
            row['aer_maximum_probability_error'] = max(abs(native.get(k, 0)-reference.get(k, 0))
                                                       for k in native.keys()|reference.keys())
            row['aer_same_support'] = native.keys() == reference.keys()
        rows.append(row)
        print(json.dumps({'id': row['id'], 'syndromes': syndromes,
            'support': len(distribution.probabilities), 'native_seconds': elapsed}), flush=True)
    negative = probability(restore(inputs['programs'][0]), classical={0: 1}).value == ZERO
    historical = inputs['single_round_hardware']
    hardware_rows = [{'case': c['label'], 'shots': c['shots'], 'expected_syndrome': c['expected_syndrome'],
        'recorded_hardware_expected_rate': c['expected_syndrome_rate'],
        'ideal_native_expected_rate': 1, 'syndrome_tvd_hardware_vs_ideal': 1-c['expected_syndrome_rate']}
        for c in historical['cases']]
    tests = None
    if run_tests:
        suite = unittest.TestLoader().discover(str(ROOT/'tests'), pattern='test_native*.py')
        result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        tests = {'run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
            'skipped': len(result.skipped), 'passed': result.wasSuccessful() and not result.skipped,
            'details': [s for _, s in result.failures+result.errors]}
    passed = negative and all(r['expected_syndromes_match'] and r.get('aer_same_support', True)
        and r.get('aer_maximum_probability_error', 0) < 1e-12 for r in rows)
    if tests is not None:
        passed = passed and tests['passed']
    sources = sorted((ROOT/'native_relational_qc').glob('*.py'))+sorted((ROOT/'tests').glob('test_native*.py'))
    return {'schema': 'native-ibm-shor-workload-replay-v1', 'passed': bool(passed),
        'evidence_class': 'LOCAL_NATIVE_IDEAL_EXECUTION_OF_PINNED_IBM_LOGICAL_WORKLOADS',
        'input_sha256': digest, 'source_commit': SOURCE_COMMIT, 'tests': tests, 'cases': rows,
        'wrong_syndrome_negative_control_passed': negative,
        'historical_hardware': {'job_id': historical['job_id'], 'backend': historical['backend'], 'cases': hardware_rows},
        'three_round_receipt': {'job_id': inputs['three_round_submission']['job_id'],
            'status_as_saved': inputs['three_round_submission']['status'],
            'interpretation': 'historical receipt only; no three-round hardware result in the pinned source set; current status was not queried'},
        'execution': {'engine': 'native exact dynamic observer and sparse readout', 'physical_qubits': 0,
            'hardware_jobs_submitted': 0, 'runtime_service_used': False,
            'qiskit_used_for_native_execution': False, 'aer_used_for_native_execution': False,
            'independent_local_aer_comparison_performed': compare_aer,
            'native_only_command_needs_quantum_sdk': False,
            'comparison_details': 'original pinned circuits; one trajectory for deterministic syndrome instruments; saved data probabilities, not one-shot probability estimates'},
        'scope': 'original logical builders/register layouts; no bit-for-bit device-transpiled ISA or calibrated noise replay. Ideal results are not claimed to match noisy hardware counts or outperform hardware.',
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--compare-aer', action='store_true')
    parser.add_argument('--run-tests', action='store_true')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.prepare:
        INPUTS.write_text(json.dumps(prepare(), indent=2, sort_keys=True)+'\n')
        print('Prepared native inputs from pinned logical builders.')
        if args.out is None:
            return 0
    if args.out is None:
        parser.error('--out is required for execution')
    report = run(compare_aer=args.compare_aer, run_tests=args.run_tests)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps({'passed': report['passed'], 'cases': len(report['cases']), 'tests': report['tests']}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
