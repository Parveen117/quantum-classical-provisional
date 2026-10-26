"""Loss budget audit: declared chain, Theorem L1 engine check at four efficiencies, fail-closed grade."""
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.loss_budget import loss_grade, loss_plan, lossy_fusion_from_engine


def _r(v, bits=8):
    return str(v.real_bounds(bits)[0])


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_loss_budget.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/loss'
    out.mkdir(exist_ok=True)
    plans = {str(n): loss_plan(n) for n in (1, 4, 2056)}
    (out/'plan_2056.json').write_text(json.dumps(plans['2056'], indent=2)+'\n')
    engine = {}
    for k in (0, 8, 4, 12):
        r = lossy_fusion_from_engine(k)
        engine[str(k)] = dict(eta_approx=_r(r['eta']), p_one_click=_r(r['p_one_click']), p_genuine=_r(r['p_genuine']),
                              genuine_fraction=_r(r['genuine_fraction']), matches_closed_form=r['matches_closed_form'],
                              classes={f'clicks={c},lost={l}': _r(v) for (c, l), v in r['probabilities'].items()})
    report = dict(schema='native-loss-budget-audit-v1', author='Monty', status='BUDGET_DECLARED_L1_EXACT',
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 3),
                  eta_per_site=plans['4']['eta_per_site'], loss_db_approx=plans['4']['loss_db_approx'],
                  fusion=plans['4']['fusion'], engine_check_L1=engine, grade=loss_grade(plans['4']),
                  boundaries=plans['4']['boundaries'], plan_sha256=hashlib.sha256((out/'plan_2056.json').read_bytes()).hexdigest())
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
