"""Bounded, isolated random-brickwork comparison; never submit a hardware job.

The observer uses exact algebra. Aer reference values are double precision.
Protocol and failed rows are retained. A timeout is not an algorithmic impossibility.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import re
import resource
import subprocess
import sys
import tempfile
import time

from .compact import CompactCircuit, ResourceLimit


def brickwork(n_qubits, rounds, seed):
    """Open 1D chain, all-zero input; one round has three parallel layers.

    Initial H,T on every site. Each round applies random H/SX/SXdg, random
    T/Tdg, then an alternating even/odd nearest-neighbor CZ matching. A final
    H layer makes the last CZ layer visible to the Z readout. No circuit search.
    """
    if not 2 <= n_qubits <= 256 or not 1 <= rounds <= 1000:
        raise ValueError("expected 2..256 qubits and 1..1000 rounds")
    rng = random.Random(seed)
    circuit = CompactCircuit(n_qubits)
    for q in range(n_qubits):
        circuit.add('h', q).add('t', q)
    for layer in range(rounds):
        for q in range(n_qubits):
            circuit.add(rng.choice(('h', 'sx', 'sxdg')), q)
            circuit.add(rng.choice(('t', 'tdg')), q)
        for q in range(layer % 2, n_qubits - 1, 2):
            circuit.add('cz', q, q + 1)
    for q in range(n_qubits):
        circuit.add('h', q)
    return circuit


def query_support(n, query):
    if query == 'local00':
        return [n // 2 - 1, n // 2]
    if query == 'parity':
        return list(range(n))
    raise ValueError("unknown query")


def describe(circuit, query):
    support = set(query_support(circuit.n_qubits, query))
    cone_gates = 0
    for _, qargs in reversed(circuit.operations):
        if support.intersection(qargs):
            support.update(qargs)
            cone_gates += 1
    payload = {'n_qubits': circuit.n_qubits, 'operations': circuit.operations}
    return {
        'circuit_sha256': hashlib.sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest(),
        'n_gates': len(circuit.operations),
        'n_cz': sum(name == 'cz' for name, _ in circuit.operations),
        'n_t_or_tdg': sum(name in ('t', 'tdg') for name, _ in circuit.operations),
        'structural_lightcone_qubits': len(support),
        'structural_lightcone_gates': cone_gates,
        'query_qubits': query_support(circuit.n_qubits, query),
        'dense_complex128_payload_bytes': 16 * 2**circuit.n_qubits,
    }


def _write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def _memory(pid='self', field='VmRSS'):
    try:
        data = Path(f'/proc/{pid}/status').read_text()
        return int(re.search(r'^' + field + r':\s+(\d+) kB', data, re.M).group(1)) * 1024
    except (OSError, AttributeError):
        return 0


def _worker(request_path):
    request = json.loads(Path(request_path).read_text())
    case, budget = request['case'], request['budget']
    status_path, result_path = request['status_path'], request['result_path']
    setup_start = time.perf_counter()
    circuit = brickwork(case['n'], case['rounds'], case['seed'])
    report = {**case, **describe(circuit, case['query'])}
    method = case['method']
    if method == 'observer':
        from .observer import probability, expectation
    else:
        from .compact_qiskit import to_qiskit
        from qiskit.quantum_info import Pauli
        from qiskit_aer import AerSimulator
        if method == 'statevector' and 16 * 2**case['n'] > budget['rss_bytes'] // 2:
            raise ValueError('dense allocation rejected before execution')
        qc = to_qiskit(circuit)
        if case['query'] == 'local00':
            qc.save_probabilities(query_support(case['n'], case['query']), label='value')
        else:
            qc.save_expectation_value(Pauli('Z' * case['n']), range(case['n']), label='value')
        options = dict(method='matrix_product_state' if method == 'mps' else 'statevector',
                       max_parallel_threads=1, max_parallel_experiments=1,
                       max_parallel_shots=1, max_memory_mb=budget['rss_bytes'] // 2**20,
                       enable_truncation=False, zero_threshold=0)
        if method == 'mps':
            options.update(matrix_product_state_truncation_threshold=0,
                           matrix_product_state_max_bond_dimension=None,
                           chop_threshold=0, mps_log_data=True)
        backend = AerSimulator(**options)
        report['requested_aer_options'] = options
    report['setup_seconds'] = time.perf_counter() - setup_start
    report['rss_before_execution_bytes'] = _memory()
    proc_pid = int(os.readlink('/proc/self'))
    start = time.perf_counter()
    last_write = -1.0

    def checkpoint(statistics):
        nonlocal last_write
        now = time.perf_counter()
        if now - last_write >= 0.2 or statistics.get('event') in ('resource_limit', 'completed'):
            _write(status_path, {'start_monotonic': start, 'proc_pid': proc_pid, 'statistics': statistics,
                                'rss_before_execution_bytes': report['rss_before_execution_bytes'],
                                'setup_seconds': report['setup_seconds']})
            last_write = now

    checkpoint({'event': 'execution_start'})
    try:
        if method == 'observer':
            options = dict(max_terms=budget['max_terms'], max_work=budget['max_work'],
                           max_coefficient_bits=budget['max_coefficient_bits'], progress=checkpoint)
            if case['query'] == 'local00':
                observation = probability(circuit, {q: 0 for q in query_support(case['n'], 'local00')}, **options)
            else:
                observation = expectation(circuit, {q: 'Z' for q in range(case['n'])}, **options)
            report['observation'] = observation.to_dict()
            report['value_float'] = complex(observation.value).real
            report['algebraically_exact'] = True
        else:
            result = backend.run(qc, shots=1, seed_simulator=12345).result()
            if not result.success:
                raise RuntimeError(str(result.status))
            value = result.data(0)['value']
            report['value_float'] = float(value[0] if case['query'] == 'local00' else value)
            metadata = result.results[0].metadata
            bonds = [int(token) for group in re.findall(r'BD=\[([^\]]*)\]', metadata.get('MPS_log_data', ''))
                     for token in group.split()]
            report['max_logged_bond_dimension'] = max(bonds, default=None)
            report['aer_metadata'] = {k: metadata[k] for k in (
                'method', 'device', 'time_taken', 'parallel_state_update', 'parallel_shots',
                'matrix_product_state_max_bond_dimension', 'matrix_product_state_truncation_threshold',
                'num_qubits', 'fusion') if k in metadata}
            report['algebraically_exact'] = False
        report['status'] = 'completed'
    except ResourceLimit as error:
        report.update(status='resource_limit', error=str(error),
                      statistics=getattr(error, 'statistics', {}), algebraically_exact=False)
    except Exception as error:
        report.update(status='error', error=f'{type(error).__name__}: {error}', algebraically_exact=False)
    report['execution_seconds'] = time.perf_counter() - start
    report['peak_process_rss_bytes'] = _memory(field='VmHWM')
    report['rusage_peak_rss_bytes_including_pre_exec_history'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    _write(result_path, report)


def _run_case(case, budget):
    with tempfile.TemporaryDirectory(prefix='nrqc-stress-') as temporary:
        directory = Path(temporary)
        request = dict(case=case, budget=budget, status_path=str(directory / 'status.json'),
                       result_path=str(directory / 'result.json'))
        _write(directory / 'request.json', request)
        env = {**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
               'MKL_NUM_THREADS': '1', 'PYTHONHASHSEED': '0'}
        launched = time.perf_counter()
        with (directory / 'stderr.txt').open('w') as stderr:
            process = subprocess.Popen([sys.executable, '-m', 'native_relational_qc.stress_benchmark', '--worker', str(directory / 'request.json')],
                                       env=env, stdout=subprocess.DEVNULL, stderr=stderr)
            sampled_peak, checkpoint, killed = 0, {}, None
            while process.poll() is None:
                try:
                    checkpoint = json.loads(Path(request['status_path']).read_text())
                except FileNotFoundError:
                    pass
                # /proc may expose the outer PID namespace; Popen.pid is then
                # not the /proc PID. The child resolves its own /proc/self.
                if checkpoint:
                    sampled_peak = max(sampled_peak, _memory(checkpoint['proc_pid']))
                now = time.perf_counter()
                if sampled_peak > budget['rss_bytes']:
                    killed = 'rss_limit'
                elif checkpoint and now - checkpoint['start_monotonic'] > budget['execution_seconds']:
                    killed = 'time_limit'
                elif not checkpoint and now - launched > budget['startup_seconds']:
                    killed = 'startup_limit'
                if killed:
                    process.kill()
                    break
                time.sleep(0.025)
            process.wait()
        if Path(request['result_path']).exists():
            report = json.loads(Path(request['result_path']).read_text())
        else:
            circuit = brickwork(case['n'], case['rounds'], case['seed'])
            report = {**case, **describe(circuit, case['query']), 'status': killed or 'worker_error',
                      'algebraically_exact': False, 'checkpoint': checkpoint,
                      'peak_process_rss_bytes': sampled_peak, 'peak_rss_is_sampled_lower_bound': True,
                      'execution_seconds': time.perf_counter() - checkpoint['start_monotonic'] if checkpoint else None}
        report.update(wall_seconds_including_startup=time.perf_counter() - launched,
                      sampled_peak_rss_bytes=sampled_peak, worker_exit_code=process.returncode)
        stderr_text = (directory / 'stderr.txt').read_text()
        if stderr_text:
            report['stderr'] = stderr_text[-4000:]
        return report


def run_protocol(protocol_path, output_path):
    protocol_path, output_path = Path(protocol_path), Path(output_path)
    raw = protocol_path.read_bytes()
    protocol = json.loads(raw)
    result = {'protocol_sha256': hashlib.sha256(raw).hexdigest(), 'protocol': protocol,
              'environment': {'python': sys.version, 'platform': platform.platform(),
                              'numpy': importlib.metadata.version('numpy'),
                              'qiskit': importlib.metadata.version('qiskit'),
                              'qiskit_aer': importlib.metadata.version('qiskit-aer'),
                              'cgroup_memory_max': Path('/sys/fs/cgroup/memory.max').read_text().strip(),
                              'cpu_max': Path('/sys/fs/cgroup/cpu.max').read_text().strip(),
                              'cpu_count': os.cpu_count()}, 'rows': []}
    for index, case in enumerate(protocol['cases']):
        report = _run_case(case, {**protocol['budget'], **case.get('budget_override', {})})
        result['rows'].append(report)
        _write(output_path, result)
        terms = report.get('observation', report.get('statistics', report.get('checkpoint', {}).get('statistics', {}))).get('peak_terms')
        print(f"{index + 1}/{len(protocol['cases'])} {case} => {report['status']} "
              f"{report.get('execution_seconds', 0):.3f}s terms={terms} "
              f"rss={report['peak_process_rss_bytes'] / 2**20:.1f}MiB", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker')
    parser.add_argument('--protocol')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.worker:
        _worker(args.worker)
    elif args.protocol and args.output:
        run_protocol(args.protocol, args.output)
    else:
        parser.error('provide --protocol and --output')


if __name__ == '__main__':
    main()
