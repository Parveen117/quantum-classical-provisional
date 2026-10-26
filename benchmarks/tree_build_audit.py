"""Tree-site build audit: star costs, attachment law, storage survival, site cost and net benefit, grade."""
import io
import json
from fractions import Fraction
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.tree_build import attachments, build_grade, net_benefit, site_build, star


def _f(v):
    return None if v is None else f"{float(v):.4g}"


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_tree_build.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/build'
    out.mkdir(exist_ok=True)
    stars = {str(n): dict(p_reach=str(star(n)['p_reach']), bell_pairs=str(star(n)['expected_bell_pairs'])) for n in (3, 4, 5, 8)}
    att = {f'blocks=4,spare={r}': str(attachments(4, r)['p_build']) for r in (0, 2, 4, 8)}
    sites, net = {}, {}
    for m in ('1', '999/1000', '99/100', '9/10'):
        for br, r in (([3, 3], 3), ([4, 3], 4)):
            s = site_build(br, r, m)
            sites[f'm={m},tree={br},spare={r}'] = dict(photons=s['photons_in_site'], p_attach_all=_f(s['p_attach_all']),
                                                       bell_pairs_lower=_f(s['expected_bell_pairs_per_site_lower_bound']),
                                                       storage_survival_lower=_f(s['build_storage_survival_lower_bound']))
            for n in (16, 64):
                nb = net_benefit(n, br, r, m)
                net[f'm={m},tree={br},N={n}'] = dict(bare=_f(nb['p_reach_bare']), encoded=_f(nb['p_reach_encoded_lower_bound']),
                                                     one_shot_all_sites=_f(nb['one_shot']['p_all_sites']), one_shot_pays=nb['one_shot']['pays'],
                                                     bell_pairs_per_delivered_site=_f(nb['site_multiplexed']['bell_pairs_per_delivered_site']),
                                                     bell_pairs_register=_f(nb['site_multiplexed']['bell_pairs_for_register']),
                                                     multiplexed_pays=nb['site_multiplexed']['pays'])
    report = dict(schema='native-tree-build-audit-v1', author='Monty', status='BUILD_COST_EXACT_NO_SITE_BUILT',
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 3),
                  star_growth=stars, attachment_p_build=att, site_builds=sites, net_benefit=net, grade=build_grade({}),
                  boundaries=['star growth rounds are not charged to storage; the root star is counted whole: a mixed bound, labelled',
                              'spare leaves and block sizes are design choices; m is declared',
                              'site multiplexing needs a buffer and a switch, whose loss is not counted here',
                              'nothing here changes the temperature verdict'])
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('tests_run', 'failures', 'site_builds', 'net_benefit')}, indent=1))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
