"""Fusion network audit: multiplexing optimum, Theorem N1 drifts, exact hitting probabilities and N2 limit, grade."""
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
from phase_seam_foundation.fusion_network import (
    best_multiplexing, chain_walk, growth_drift, network_grade, network_plan, resource_estimate,
)


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_fusion_network.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/network'
    out.mkdir(exist_ok=True)
    plan = network_plan(2056)
    (out/'plan_2056.json').write_text(json.dumps(plan, indent=2)+'\n')
    walks = {}
    for n in (4, 5, 8, 16, 32, 64, 128, 256):
        w = chain_walk(n)
        walks[str(n)] = dict(p_reach_target=str(w['p_reach_target']) if n <= 32 else f"{float(w['p_reach_target']):.10f}",
                             expected_attempts=str(w['expected_attempts']) if n <= 32 else f"{float(w['expected_attempts']):.3f}")
    bell = {str(n): str(chain_walk(n, Fraction(1, 2), 2, 2)['p_reach_target']) for n in (4, 8, 16)}
    mux = {t: best_multiplexing(Fraction(1, 79), Fraction(t))['best_branches'] for t in ('1', '9/10', '4/5', '1/2')}
    report = dict(schema='native-fusion-network-audit-v1', author='Monty', status='NETWORK_DECLARED_N1_N2_EXACT',
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 3),
                  drifts=dict(bell_pairs=str(growth_drift(Fraction(1, 2), 2)['drift']), ghz3=str(growth_drift(Fraction(1, 2), 3)['drift']),
                              boosted_bell=str(growth_drift(Fraction(3, 4), 2)['drift'])),
                  ghz3_walk_from_3=walks, bell_pair_walk_from_2=bell, limit_3_minus_sqrt5='0.7639320225',
                  expected_bell_pairs_for_8_sites=str(resource_estimate(8)['expected_bell_pairs']),
                  best_branches_by_switch_transmission=mux, grade=network_grade(plan), boundaries=plan['boundaries'],
                  plan_sha256=hashlib.sha256((out/'plan_2056.json').read_bytes()).hexdigest())
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
