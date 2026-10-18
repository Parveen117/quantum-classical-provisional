"""Matched selected-observation benchmarks; no hardware and no sampled measurement.

Compare exact observer propagation, exact state DD, Qiskit dense Statevector and
Qiskit Aer MPS. Report no-truncation settings, exact scope and different memory
metrics honestly. The 2**n dense byte count is theoretical where not executed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import statistics
import time
import unittest
from fractions import Fraction

import numpy as np
import qiskit
import qiskit_aer
from qiskit.quantum_info import Statevector
from qiskit_aer import AerSimulator
from qiskit_aer.library import save_probabilities, save_matrix_product_state

from .compact import CompactCircuit
from .compact_qiskit import to_qiskit
from .exact import Exact
from .observer import probability, _conjugate, _matrix


ROOT = Path(__file__).resolve().parents[1]


def chain(n):
    circuit = CompactCircuit(n)
    for q in range(n):
        circuit.add('h', q).add('t', q)
    for q in range(n - 1):
        circuit.add('cz', q, q + 1)
    return circuit.add('h', 0)


def _timed(fn, repeats=3):
    start = time.perf_counter()
    result = fn()
    cold = time.perf_counter() - start
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - start)
    return result, {"first_seconds": cold, "warm_seconds": times,
                    "warm_median_seconds": statistics.median(times)}


def benchmark():
    if platform.python_version_tuple()[:2] != ('3', '12'):
        raise RuntimeError('benchmark uses Python 3.12')
    suite = unittest.TestLoader().discover(str(ROOT/'tests'), pattern='test_native*.py')
    tests = unittest.TextTestRunner(stream=io.StringIO(), verbosity=1).run(suite)
    expected = Exact(Fraction(1, 4), Fraction(1, 8))
    expected_float = complex(expected).real
    backend = AerSimulator(method='matrix_product_state', max_parallel_threads=1,
                           matrix_product_state_truncation_threshold=0, zero_threshold=0,
                           chop_threshold=0, enable_truncation=False)
    rows = []
    for n in (8, 16, 20, 32, 64, 128):
        circuit = chain(n)
        qc = to_qiskit(circuit)
        _conjugate.cache_clear()
        _matrix.cache_clear()
        result, timer = _timed(lambda: probability(circuit, {0:0, 1:0}))
        row = {"qubits": n, "gates": len(circuit.operations),
               "expected": expected.to_dict(), "dense_theoretical_amplitude_bytes": 16*2**n,
               "observer": {**result.to_dict(), **timer, "exact_match": result.value == expected}}
        if n <= 64:
            def dd():
                state = circuit.state()
                value = state.probability({0:0, 1:0})
                return state, value
            (state, value), timer = _timed(dd, repeats=1)
            row['exact_dd'] = {**state.stats(), **timer, "value": value.to_dict(), "exact_match": value == expected}
        else:
            row['exact_dd'] = {"executed": False, "reason": "bounded benchmark stops DD execution at 64 qubits"}
        if n <= 20:
            def dense():
                state = Statevector.from_instruction(qc)
                return float(state.probabilities([0,1])[0]), state
            (value, dense_state), timer = _timed(dense)
            # An independent compensated sum audits SDK readout accumulation.
            # It is outside the timing, so the baseline remains the SDK query.
            audited = math.fsum(float(a.real)**2 + float(a.imag)**2 for a in dense_state.data[::4])
            row['qiskit_dense'] = {**timer, "probability": value, "absolute_error": abs(value-expected_float),
                                    "amplitude_payload_bytes": dense_state.data.nbytes,
                                    "compensated_sum_probability": audited,
                                    "compensated_sum_absolute_error": abs(audited-expected_float)}
        else:
            row['qiskit_dense'] = {"executed": False, "reason": "dense runs deliberately limited to 20 qubits"}
        mps_qc = qc.copy()
        mps_qc.save_probabilities([0,1])

        def mps():
            raw = backend.run(mps_qc, shots=1).result()
            if not raw.success:
                raise RuntimeError('MPS baseline failed')
            return float(raw.data(0)['probabilities'][0])
        value, timer = _timed(mps)
        # Exporting all MPS tensors is an extra task. Audit its retained memory
        # in a separate execution outside the selected-query timing.
        mps_audit = qc.copy()
        mps_audit.save_matrix_product_state()
        audit = backend.run(mps_audit, shots=1).result()
        if not audit.success:
            raise RuntimeError('MPS memory audit failed')
        tensors, bonds = audit.data(0)['matrix_product_state']
        payload = sum(a.nbytes for pair in tensors for a in pair) + sum(a.nbytes for a in bonds)
        max_bond = max((len(a) for a in bonds), default=1)
        row['qiskit_aer_mps'] = {**timer, "probability": value, "absolute_error": abs(value-expected_float),
                                "retained_numeric_payload_bytes": payload, "maximum_bond_dimension": max_bond}
        rows.append(row)
        print(json.dumps({"qubits": n, "observer_terms": row['observer']['peak_terms'],
                          "invariant_gates": row['observer']['gates_proved_invariant'],
                          "observer_seconds": row['observer']['warm_median_seconds'],
                          "mps_seconds": timer['warm_median_seconds']}), flush=True)
    growth = []
    for pairs in range(1,8):
        crossed = CompactCircuit(2*pairs)
        adjacent = CompactCircuit(2*pairs)
        for q in range(pairs):
            crossed.add('h',q).add('cx',q,q+pairs)
            adjacent.add('h',2*q).add('cx',2*q,2*q+1)
        a, b = crossed.state(), adjacent.state()
        growth.append({"pairs": pairs, "crossed_nodes": a.stats()['live_nodes'],
                       "adjacent_nodes": b.stats()['live_nodes'],
                       "crossed_formula": 3*2**pairs-3, "adjacent_formula": 3*pairs})
    passed = tests.wasSuccessful() and not tests.skipped
    passed = passed and all(r['observer']['exact_match'] and r['qiskit_aer_mps']['absolute_error'] < 1e-12 for r in rows)
    passed = passed and all(r['exact_dd'].get('exact_match',True)
                           and r['qiskit_dense'].get('compensated_sum_absolute_error',0)<1e-12 for r in rows)
    passed = passed and all(r['crossed_nodes']==r['crossed_formula'] and r['adjacent_nodes']==r['adjacent_formula'] for r in growth)
    sources = sorted((ROOT/'native_relational_qc').glob('*.py')) + sorted((ROOT/'tests').glob('test_native*.py'))
    return {"schema": "native-exact-compact-observer-benchmark-v1", "passed": bool(passed),
            "evidence_class": "BOUNDED_LOCAL_EXACT_CALCULATION_AND_RESOURCE_COMPARISON",
            "versions": {"python": platform.python_version(), "numpy": np.__version__,
                         "qiskit": qiskit.__version__, "qiskit_aer": qiskit_aer.__version__},
            "tests": {"run": tests.testsRun, "failures": len(tests.failures), "errors": len(tests.errors),
                      "skipped": len(tests.skipped), "failure_details": [s for _,s in tests.failures+tests.errors]},
            "rows": rows, "ordering_growth_control": growth,
            "protocol": {
                "input": "zero state; H,T at each site; nearest-neighbor CZ; final H on q0",
                "query": "P(q0=0,q1=0)", "analytic_answer": "(2+sqrt(2))/8",
                "input_construction_timed": False, "timing_clock": "perf_counter",
                "observer_transfer_tables": "cleared before first execution at each size; reused for warm executions",
                "mps": "zero truncation threshold, no maximum bond dimension, one thread; timed selected-probability save only; full tensor memory audit in separate untimed execution; no sampled measurement",
                "memory": "DD full retained Python graph and MPS numeric tensor payload are distinct metrics; neither is peak process RSS",
                "dense_unexecuted_sizes": "only theoretical amplitude bytes; no claim of a measured allocation failure",
                "dense_correctness_audit": "SDK readout error is retained; independently audit the same amplitudes with math.fsum at unchanged 1e-12 tolerance, outside timing",
                "preliminary_diagnostic": "first aggregate run failed the 1e-12 dense-readout check at n=20 (1.144140338027455e-12); compensated summation of the same entries had 1.9984014443252818e-15 error",
                "baseline_scope": "one maintained MPS implementation and one dense reference, not a best-known-classical search",
                "task_scope": "selected local observable in this structured family, not a full-distribution benchmark",
            },
            "source_sha256": {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            "hardware_jobs": 0, "approximate_truncation": False,
            "claim": "Exact native selected-observation execution and bounded compression; no quantum-hardware obsolescence claim."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    report=benchmark()
    args.out.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'tests':report['tests']},indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
