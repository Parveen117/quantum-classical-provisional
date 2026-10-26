"""Loss ledger audit: Theorem L2 at four efficiencies, Kraus completeness, native grid, dark-count table, grade."""
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.loss_ledger import (
    charge_ledger, dark_count_table, kraus_completeness, ledger_grade, native_transmission_grid, nearest_grid_point,
    rate_not_fidelity,
)


def _r(v, bits=8):
    return str(v.real_bounds(bits)[0])


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_loss_ledger.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/ledger'
    out.mkdir(exist_ok=True)
    l2 = {}
    for k in (0, 8, 4, 12):
        r = charge_ledger(k)
        l2[str(k)] = dict(eta_d=_r(r['eta_d']), charge_identity=r['charge_identity'],
                          false_heralds_have_empty_middle_site=r['false_heralds_have_empty_middle_site'],
                          genuine_heralds_fill_every_site=r['genuine_heralds_fill_every_site'], witness_is_one=r['witness_is_one'],
                          accepted=_r(r['accepted_probability']), rejected_false=_r(r['rejected_false_heralds']), missed_genuine=_r(r['missed_genuine']),
                          classes={str(key): _r(p) for key, p in r['classes'].items()})
    grid = [dict(k=row['k'], lower=str(row['lower']), upper=str(row['upper'])) for row in native_transmission_grid()]
    near = {t: nearest_grid_point(t)['k'] for t in ('3/5', '1/2', '9/10', '243/4000')}
    dark = dark_count_table(8)
    rate = rate_not_fidelity('3/5', 6)
    report = dict(schema='native-loss-ledger-audit-v1', author='Monty', status='L2_EXACT_LEDGER_READOUT',
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 3),
                  theorem_L2=l2, kraus_complete={str(k): kraus_completeness(k)['complete'] for k in (0, 4, 8, 12, 16)},
                  native_grid_cos2_k_pi_32=grid, nearest_grid_k=near,
                  rate_not_fidelity_eta_3_5_six_fusions=dict(accepted=str(rate['accepted_fraction_of_heralds']), witness=rate['witness_after_readout']),
                  dark_counts_k8=dict(correct_by_dark=_r(dark['correct_by_dark']), threshold_wrong_by_dark=_r(dark['threshold_wrong_by_dark']),
                                      rejected_by_dark=_r(dark['rejected_by_dark'])),
                  grade=ledger_grade({}),
                  boundaries=['the ledger is photon number; readout must record exactly one click per site, declared in advance',
                              'dark counts at readout itself and multi-pair emission violate the ledger and are not removed here',
                              'threshold detectors suffice for the fusion herald; number resolution is not required by L2',
                              'the native grid is the exact sector, not a quantisation of physical loss',
                              'nothing here changes the temperature verdict'])
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('status', 'tests_run', 'failures', 'kraus_complete', 'nearest_grid_k', 'dark_counts_k8')}, indent=1))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
