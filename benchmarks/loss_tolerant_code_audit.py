"""Tree-code audit: exact recovery polynomials for trees up to 16 photons, crossovers, encoded walks, grade."""
import io
import json
from fractions import Fraction
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.loss_tolerant_code import code_grade, crossover, encoded_walk, evaluate, loss_polynomials


def _f(v):
    return f"{float(v):.4g}"


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_loss_tolerant_code.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/code'
    out.mkdir(exist_ok=True)
    polys, cross = {}, {}
    for br in ([1], [2], [3], [2, 2], [2, 3], [3, 2], [3, 3], [4, 3]):
        p = loss_polynomials(br)
        key = ','.join(map(str, br))
        polys[key] = dict(photons=p['photons'], check=p['check'], counts=p['counts'],
                          at_eps={e: dict(p_z=_f(evaluate(p, Fraction(e))['p_z']), p_x=_f(evaluate(p, Fraction(e))['p_x']),
                                          p_both=_f(evaluate(p, Fraction(e))['p_both']), bare=_f(1 - Fraction(e)))
                                  for e in ('1/100', '1/10', '1/5', '3/10')})
        c = crossover(br)
        cross[key] = None if c['crossover_bounds'] is None else [_f(x) if x is not None else None for x in c['crossover_bounds']]
    walks = {}
    for m in ('9/10', '99/100'):
        for br in ([3, 3], [4, 3]):
            for n in (16, 64):
                w = encoded_walk(n, br, m)
                walks[f'm={m},tree={br},N={n}'] = dict(m_eff=_f(w['m_eff']), bare=_f(w['p_reach_bare']), encoded_lower_bound=_f(w['p_reach_encoded_lower_bound']),
                                                        photons_in_register=w['photons_in_register'])
    report = dict(schema='native-loss-tolerant-code-audit-v1', author='Monty', status='TREE_CODE_EXACT_NO_ENCODED_SITE_BUILT',
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 3),
                  polynomials=polys, crossover_eps_where_code_stops_beating_bare=cross, encoded_walks=walks, grade=code_grade({}),
                  boundaries=['recovery is a stabiliser-support statement over every loss pattern; no literature recursion is used',
                              'photon loss epsilon is declared; the encoded site must itself be built by fusions, whose cost is not counted here',
                              'encoded walk results are rigorous lower bounds (m_eff floored to 20 bits)',
                              'nothing here changes the temperature verdict'])
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('tests_run', 'failures', 'crossover_eps_where_code_stops_beating_bare', 'encoded_walks')}, indent=1))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
