"""Chain memory audit: lossy-memory walk against the M1 bound, tree law, fibre table, design points, grade."""
import io
import json
from fractions import Fraction
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.chain_memory import (
    design_point, fibre_delay_table, memory_grade, memory_walk, theorem_M1_bound, tree_survival,
)


def _f(v):
    return f"{float(v):.4g}"


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_chain_memory.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/memory'
    out.mkdir(exist_ok=True)
    walk = {}
    for m in ('1', '999/1000', '99/100', '9/10'):
        for n in (4, 8, 16, 32, 64):
            w = memory_walk(n, m); b = theorem_M1_bound(n, m)
            walk[f'm={m},N={n}'] = dict(p_reach=_f(w['p_reach_target']), M1_bound=_f(b['bound']), bound_holds=w['p_reach_target'] <= b['bound'],
                                        expected_attempts=_f(w['expected_attempts']))
    tree = {f'm={m},N={n}': _f(tree_survival(n, Fraction(m))['survival_approx']) for m in ('99/100', '999/1000', '9999/10000') for n in (16, 64, 2056)}
    designs = {}
    for label, kw in (('declared', dict()), ('eta_half_dark_1e6', dict(eta_site='1/2', dark_per_mode='1/1000000'))):
        for ro in ('threshold', 'number_resolving'):
            for n in (8, 64, 2056):
                d = design_point(n, '1/2', readout=ro, **kw)
                designs[f'{label}:{ro}:N={n}'] = dict(feasible=d['feasible'], best_x=str(d['best']['x']) if d['best'] else None,
                                                      rows=[dict(x=str(r['x']), within_budget=r['within_budget'], g2_within=r['g2_within']) for r in d['rows']])
    report = dict(schema='native-chain-memory-audit-v1', author='Monty', status='M1_EXACT_DESIGN_DECLARED',
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 3),
                  lossy_memory_walk=walk, tree_survival_approx=tree, fibre_delay_declared=fibre_delay_table(), design_points=designs,
                  grade=memory_grade({}),
                  boundaries=['memory transmission m, fibre loss and latency are declared; nothing measured',
                              'the chain walk charges every stored photon one m per attempt; the tree charges every photon one m per level, one attempt per level, no repeats',
                              'loss-tolerant encodings that would change these laws are outside this note',
                              'design points use the v0.24 budget upper bounds and the v0.20 g2 law at herald efficiency 1/2',
                              'nothing here changes the temperature verdict'])
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('tests_run', 'failures', 'tree_survival_approx')}, indent=1))
    print(json.dumps({k: dict(feasible=v['feasible'], best_x=v['best_x']) for k, v in designs.items()}, indent=1))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
