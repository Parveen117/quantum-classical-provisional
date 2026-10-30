"""Reproduce v0.28 coherent refresh and age-aware budgets; no hardware calls."""
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_relational_qc.exact import Exact
from phase_seam_foundation.loss_refresh import memory_lifetime, recovery_plan, refresh_budget, refresh_witness


def scalar(value):
    if isinstance(value, Exact):
        return value.to_dict()
    if isinstance(value, Fraction):
        return dict(exact=str(value), decimal=float(value))
    if isinstance(value, dict):
        return {str(k): scalar(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scalar(v) for v in value]
    return value


def main():
    names = ('loss_tolerant_code', 'tree_build', 'loss_refresh')
    suite = unittest.TestSuite(unittest.defaultTestLoader.discover(
        str(ROOT/'tests'), pattern=f'test_phase_seam_{name}.py') for name in names)
    stream = io.StringIO()
    start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    coherent = [refresh_witness(lost_masks=(mask,)) for mask in range(64)
                if recovery_plan([2, 2], mask)['recoverable']]
    repeated = [refresh_witness(lost_masks=mask) for mask in ((1, 16), (8, 2), (5, 48))]
    negative = refresh_witness(lost_masks=(1,), corrections=False)
    lifetimes = [memory_lifetime([4, 3], '99/100', t) for t in (1, 10, 50, 100)]
    schedules = []
    # The cost unit is a DECLARED total cost of one reserved fresh resource
    # plus transfer attempt. No v0.27 Bell-pair estimate is silently imported.
    for transfer in ('1/2', '99/100', '1'):
        for period in (1, 2, 5, 10, 25, 50):
            budget = refresh_budget([4, 3], '99/100', [period]*(50//period),
                                    latency_rounds=0, transfer_success=transfer,
                                    resource_ready='99/100', bell_pairs_per_attempt=1)
            schedules.append(dict(storage_interval=period, transfer_success=transfer,
                                  resource_ready='99/100', latency_rounds=0,
                                  p_complete=budget['p_complete'],
                                  p_no_refresh=budget['p_no_refresh_same_elapsed_time'],
                                  expected_attempts=budget['expected_refresh_attempts'],
                                  improves_survival=budget['improves_survival']))
    latency = []
    for delay in (0, 1, 5):
        b = refresh_budget([4, 3], '99/100', [5]*10, latency_rounds=delay,
                           transfer_success='99/100', resource_ready='99/100', bell_pairs_per_attempt=1)
        latency.append({k: b[k] for k in ('elapsed_rounds', 'p_complete', 'p_no_refresh_same_elapsed_time',
                                          'expected_refresh_attempts') } | {'latency_rounds': delay})
    files = [f'tests/test_phase_seam_{n}.py' for n in names] + [
        'benchmarks/loss_refresh_audit.py', 'phase_seam_foundation/loss_refresh.py',
        'phase_seam_foundation/loss_tolerant_code.py', 'phase_seam_foundation/tree_build.py',
        'phase_seam_foundation/chain_memory.py', 'phase_seam_foundation/fusion_network.py',
        'phase_seam_foundation/model.py', 'phase_seam_foundation/LOSS_REFRESH.md',
        'phase_seam_foundation/TREE_CODE.md', 'phase_seam_foundation/TREE_BUILD.md',
        'phase_seam_foundation/README.md', 'benchmarks/loss_tolerant_code_audit.py',
        'benchmarks/tree_build_audit.py',
        'native_relational_qc/dynamic.py', 'native_relational_qc/dynamic_examples.py',
        'native_relational_qc/exact.py', 'native_relational_qc/compact.py', 'native_relational_qc/observer.py']
    report = dict(schema='native-loss-refresh-audit-v1', author='Monty',
                  status='IDEAL_CIRCUIT_VERIFIED_PHOTONIC_REFRESH_UNBUILT' if result.wasSuccessful() else 'TEST_FAILURE',
                  generated_at=datetime.now(timezone.utc).isoformat(),
                  checkout_base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
                  seconds=round(time.perf_counter()-start, 3),
                  source_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
                  correctable_six_photon_patterns=len(coherent), coherent_transfers=coherent,
                  two_transfer_schedules=repeated, no_feedback_control=negative,
                  unrefreshed_memory=lifetimes, declared_schedule_sweep=schedules,
                  latency_sweep=latency,
                  boundaries=[
                      'all quantum measurement outcomes included; erasures are known partial traces',
                      'circuit uses ideal CNOT, H, Z measurement and feedforward; no optical implementation of the decoder or teleporter',
                      'fresh supply and transfer success are independent declared inputs, not measurements or demonstrated operating points',
                      'one cost unit per attempted refresh is a normalized declared input, not a Bell-pair bill of materials',
                      'v0.26/v0.27 walk values assume perfect per-round renewal; they are not physical lower bounds',
                      'initial encoding, physical noise, source preparation and total chip temperature are not established'])
    out = ROOT/'phase_seam_foundation/refresh'
    out.mkdir(exist_ok=True)
    (out/'qualification.json').write_text(json.dumps(scalar(report), indent=2)+'\n')
    (out/'test_results.txt').write_text(stream.getvalue())
    print(json.dumps({k: report[k] for k in ('status', 'tests_run', 'failures', 'errors', 'skipped',
                                           'correctable_six_photon_patterns', 'seconds')}, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
