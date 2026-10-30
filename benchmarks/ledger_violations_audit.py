"""Ledger violations audit: V1 table over all 65 angles, dark law, V2 budgets for N = 3 .. 2056, allowed wrong fractions."""
import hashlib
import io
import json
from fractions import Fraction
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.ledger_violations import (
    allowed_wrong_fraction, double_occupancy, dual_rail_sweep_verdict, error_budget,
)


def _f(v):
    return f"{float(v):.6g}"


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_ledger_violations.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/violations'
    out.mkdir(exist_ok=True)
    v1 = {str(t): str(double_occupancy(t)['same_rail'].real_bounds(12)[0]) for t in range(0, 65, 4)}
    budgets = {}
    for n in (3, 8, 64, 256, 2056):
        for ro in ('threshold', 'number_resolving'):
            b = error_budget(n, readout=ro)
            budgets[f'{n}:{ro}'] = dict(witness=_f(b['witness_bounds'][0]), wrong_fraction=_f(b['per_site']['wrong_fraction_bounds'][1]), dominant=b['dominant'])
    better = {f'{n}': dict(threshold=_f(error_budget(n, eta_site='1/2', dark_per_mode='1/1000000')['witness_bounds'][0]),
                           number_resolving=_f(error_budget(n, eta_site='1/2', dark_per_mode='1/1000000', readout='number_resolving')['witness_bounds'][0]))
              for n in (64, 2056)}
    allowed = {str(n): [str(x) for x in allowed_wrong_fraction(Fraction(1, 2), n)['max_wrong_fraction_bounds']] for n in (3, 8, 64, 2056)}
    report = dict(schema='native-ledger-violations-audit-v1', author='Monty', status='V1_V2_EXACT_BUDGET_DECLARED',
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 3),
                  V1_same_rail_by_angle=v1, declared_point=dict(x='1/40', theta_steps=16, eta_site='243/4000', dark_per_mode='1/100000'),
                  budgets_declared_point=budgets, budgets_eta_half_dark_1e6=better, max_wrong_fraction_for_witness_half=allowed,
                  verdict_without_ledger=dual_rail_sweep_verdict({})['logic_class'],
                  boundaries=['x, eta, dark rate and angle are declared; nothing measured',
                              'one-survivor multi-pair case is right for a single-site preparation only; in a fused register it is declared',
                              'the witness law treats an accepted wrong site as a random X outcome',
                              'thermal class is a separate ledger and is untouched by the dual-rail verdict'])
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('tests_run', 'failures', 'budgets_declared_point', 'budgets_eta_half_dark_1e6', 'max_wrong_fraction_for_witness_half')}, indent=1))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
