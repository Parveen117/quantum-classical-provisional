"""Reproduce exact dynamic execution, recovery and independent reference checks."""
import argparse
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import platform
import time
import unittest

import numpy as np
import qiskit
import qiskit_aer
from qiskit.quantum_info import Pauli
from qiskit_aer import AerSimulator

from .dynamic import probability, expectation
from .dynamic_examples import teleport, bitflip_recovery, shor_recovery, bell_fidelity
from .dynamic_qiskit import to_qiskit
from . import dynamic_reference as reference
from .exact import Exact, ZERO, ONE, INV_SQRT2


ROOT = Path(__file__).resolve().parents[1]


def _aer_expectations(circuit, qubits, method):
    qc = to_qiskit(circuit)
    for axis in 'XYZ':
        qc.save_expectation_value(Pauli(axis*len(qubits)), qubits, label=axis)
    result = AerSimulator(method=method, max_parallel_threads=1).run(
        qc, shots=1, seed_simulator=731).result()
    if not result.success:
        raise RuntimeError('independent Aer dynamic circuit failed')
    data = result.data(0)
    return {axis: float(data[axis]) for axis in 'XYZ'}, data.get('counts', {})


def _syndrome(error):
    bits = [0]*8
    if error is None:
        return bits
    q, name = error
    block, position = divmod(q, 3)
    if name in ('x', 'y'):
        bits[2*block] = int(position in (0, 1))
        bits[2*block+1] = int(position in (1, 2))
    if name in ('z', 'y'):
        bits[6] = int(block in (0, 1))
        bits[7] = int(block in (1, 2))
    return bits


def verify():
    if platform.python_version_tuple()[:2] != ('3', '12'):
        raise RuntimeError('verification uses Python 3.12')
    suite = unittest.TestLoader().discover(str(ROOT/'tests'), pattern='test_native*.py')
    tests = unittest.TextTestRunner(stream=io.StringIO(), verbosity=1).run(suite)
    teleport_rows = []
    preparations = [
        ('zero', (), (ZERO, ZERO, ONE)), ('one', ('x',), (ZERO, ZERO, -ONE)),
        ('plus', ('h',), (ONE, ZERO, ZERO)), ('minus', ('x', 'h'), (-ONE, ZERO, ZERO)),
        ('plus_i', ('h', 's'), (ZERO, ONE, ZERO)), ('minus_i', ('h', 'sdg'), (ZERO, -ONE, ZERO)),
        ('magic', ('h', 't'), (INV_SQRT2, INV_SQRT2, ZERO)),
        ('hth', ('h', 't', 'h'), (ZERO, -INV_SQRT2, INV_SQRT2)),
    ]
    for name, gates, expected in preparations:
        c = teleport(gates)
        states = reference.branches(c)
        aer, _ = _aer_expectations(c, [2], 'density_matrix')
        readings = {axis: expectation(c, {2: axis}) for axis in 'XYZ'}
        forward = {axis: reference.expectation(c, {2: axis}, evaluated=states) for axis in 'XYZ'}
        errors = {axis: max(abs(forward[axis]-complex(readings[axis].value).real),
                           abs(aer[axis]-complex(readings[axis].value).real)) for axis in 'XYZ'}
        teleport_rows.append({'input': name, 'preparation': gates,
            'readings': {a: r.to_dict() for a, r in readings.items()},
            'exact_match': all(readings[a].value == value for a, value in zip('XYZ', expected)),
            'density_reference': forward, 'aer_density_reference': aer,
            'maximum_reference_error': max(errors.values())})
    shor_rows = []
    for error in [None]+[(q, name) for q in range(9) for name in ('x', 'y', 'z')]:
        c = shor_recovery(error)
        start = time.perf_counter()
        value, readings = bell_fidelity(c, 0, 10)
        elapsed = time.perf_counter()-start
        syndrome = _syndrome(error)
        classical_exact = all(probability(c, classical={bit: outcome}).value == ONE
                              for bit, outcome in enumerate(syndrome))
        aer, counts = _aer_expectations(c, [0, 10], 'stabilizer')
        expected_mask = sum(bit << index for index, bit in enumerate(syndrome))
        aer_syndrome = counts == {hex(expected_mask): 1}
        maximum_error = max(abs(aer[axis]-complex(readings[axis].value).real) for axis in 'XYZ')
        shor_rows.append({'error': error, 'bell_entanglement_fidelity': value.to_dict(),
            'exact_identity_reading': value == ONE, 'syndrome_bits_low_first': syndrome,
            'exact_deterministic_syndrome': classical_exact, 'aer_syndrome_matches': aer_syndrome,
            'readings': {a: r.to_dict() for a, r in readings.items()},
            'aer_stabilizer_reference': aer, 'maximum_reference_error': maximum_error,
            'native_three_query_seconds': elapsed})
    recovery_rows = []
    p = Fraction(1, 10)
    logical_error = 3*p*p - 2*p*p*p
    for rounds in (1, 3, 8, 32, 128):
        c = bitflip_recovery(rounds=rounds, probability=p)
        start = time.perf_counter()
        value, readings = bell_fidelity(c, 0, 4)
        elapsed = time.perf_counter()-start
        expected = Exact((1+(1-2*logical_error)**rounds)/2)
        row = {'rounds': rounds, 'qubits': c.n_qubits, 'classical_bits': c.n_clbits,
            'instructions': len(c.operations), 'bell_entanglement_fidelity': value.to_dict(),
            'analytic_expected': expected.to_dict(), 'exact_match': value == expected,
            'peak_terms': max(r.peak_terms for r in readings.values()),
            'max_coefficient_bits': max(r.max_coefficient_bits for r in readings.values()),
            'native_three_query_seconds': elapsed}
        if rounds <= 3:
            states = reference.branches(c)
            row['maximum_density_reference_error'] = max(abs(
                reference.expectation(c, {0: a, 4: a}, evaluated=states)-complex(readings[a].value).real) for a in 'XYZ')
        recovery_rows.append(row)
    tele_negative = [expectation(teleport(corrections=False), {2: a}).value for a in 'XYZ']
    shor_negative, _ = bell_fidelity(shor_recovery((0, 'z'), corrections=False), 0, 10)
    bitflip_negative, _ = bell_fidelity(bitflip_recovery(corrections=False), 0, 4)
    negatives = {'teleport_no_feedback_bloch': [v.to_dict() for v in tele_negative],
        'shor_z0_no_recovery_fidelity': shor_negative.to_dict(),
        'bitflip_no_recovery_fidelity': bitflip_negative.to_dict(),
        'passed': tele_negative == [ZERO]*3 and shor_negative == ZERO and bitflip_negative == Exact(Fraction(9, 10))}
    passed = tests.wasSuccessful() and not tests.skipped and negatives['passed']
    passed &= all(r['exact_match'] and r['maximum_reference_error'] < 1e-12 for r in teleport_rows)
    passed &= all(r['exact_identity_reading'] and r['exact_deterministic_syndrome']
                  and r['aer_syndrome_matches'] and r['maximum_reference_error'] < 1e-12 for r in shor_rows)
    passed &= all(r['exact_match'] and r.get('maximum_density_reference_error', 0) < 1e-12 for r in recovery_rows)
    sources = sorted((ROOT/'native_relational_qc').glob('*.py')) + sorted((ROOT/'tests').glob('test_native*.py'))
    return {'schema': 'native-dynamic-exact-verification-v1', 'passed': bool(passed),
        'evidence_class': 'LOCAL_EXACT_DYNAMIC_CHANNEL_AND_RECOVERY_COMPARISON',
        'versions': {'python': platform.python_version(), 'numpy': np.__version__,
                     'qiskit': qiskit.__version__, 'qiskit_aer': qiskit_aer.__version__},
        'tests': {'run': tests.testsRun, 'failures': len(tests.failures), 'errors': len(tests.errors),
                  'skipped': len(tests.skipped), 'failure_details': [s for _, s in tests.failures+tests.errors]},
        'teleportation': teleport_rows, 'shor_single_pauli_recovery': shor_rows,
        'repeated_bitflip_recovery': recovery_rows, 'negative_controls': negatives,
        'protocol': {
            'native': 'complete Pauli times classical Walsh expansion; no trajectory/density/statevector construction; no truncation',
            'initial_boundary': 'quantum all-zero and classical all-zero; input preparations are part of each circuit',
            'random_crosschecks': 'unit tests include 32 seeded 1..4-qubit dynamic programs against independent forward unnormalized density branches; joint outcomes, joint moments, overwrite, feedback and rational noise',
            'shor': 'nine data qubits, one reused syndrome ancilla, one external reference; new ideal recovery circuit, not a replay of historical IBM jobs',
            'aer_shots': 'one local simulator trajectory per exported circuit; Shor syndromes are deterministic and independently checked exactly; corrected teleportation output readings are the same in every branch, checked separately by exact joint queries and forward density branches',
            'aer_readings': 'saved expectation values of simulated states, not estimates from one measured output bit',
            'noise': 'synthetic independent rational X-flip probability 1/10 on each data qubit each round; ideal syndrome operations',
            'round_formula': 'pL=3*p^2-2*p^3; entanglement fidelity after r corrected rounds = (1+(1-2*pL)^r)/2',
            'timings': 'descriptive native execution times only; no speed comparison to Aer or quantum hardware in this report',
            'limits': 'term/bit/work guards; conditional predicates and requested joint outcomes can expand exponentially; no polynomial guarantee',
        },
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        'hardware_jobs': 0, 'approximate_truncation': False,
        'claim': 'Exact selected results with measurement, reset, classical feedback and rational Pauli channels; no general quantum-computer replacement claim.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = verify()
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'tests': report['tests'],
        'teleportation_inputs': len(report['teleportation']), 'shor_cases': len(report['shor_single_pauli_recovery']),
        'recovery': [{k: r[k] for k in ('rounds', 'peak_terms', 'max_coefficient_bits', 'exact_match')}
                     for r in report['repeated_bitflip_recovery']]}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
