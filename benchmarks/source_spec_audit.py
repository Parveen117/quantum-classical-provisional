"""810 nm heralded source audit: exact statistics, operating table, declared spec, fail-closed grade."""
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
from phase_seam_foundation.source_spec import (
    all_herald_probability, heralded_statistics, klyshko, operating_table, source_grade, source_spec, spectral_purity,
)


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_source_spec.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/source'
    out.mkdir(exist_ok=True)
    spec = source_spec()
    (out/'source_810.json').write_text(json.dumps(spec, indent=2)+'\n')
    lossless = {str(x): str(heralded_statistics(Fraction(x))['g2_heralded']) for x in ('1/100', '1/40', '1/20', '1/10', '1/4')}
    k = klyshko(Fraction(1, 40), Fraction(1, 2), Fraction(3, 10))
    purity = {f'{a}:{b}': str(spectral_purity(a, b)['purity']) for a, b in ((1, 1), (2, 3), (1, 10))}
    herald = {str(n): str(all_herald_probability(n, Fraction(1, 79))['p_all']) for n in (1, 2, 4, 8)}
    negatives = dict(
        g2_at_half=source_grade(dict(pairs=dict(evidence_class='LAB_RECORDED', coincidence_rate_hz=1, klyshko_signal='1/2'),
                                     heralded_g2=dict(evidence_class='LAB_RECORDED', value='1/2')))['grade'],
        synthetic_pairs=source_grade(dict(pairs=dict(evidence_class='SYNTHETIC', coincidence_rate_hz=1, klyshko_signal='1/2')))['grade'])
    report = dict(schema='native-source-spec-audit-v1', author='Monty', status='SPEC_DECLARED_NO_SOURCE_BUILT',
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 3),
                  g2_lossless_by_x=lossless, g2_half_herald_at_x_1_40=str(heralded_statistics(Fraction(1, 40), Fraction(1, 2))['g2_heralded']),
                  operating_table_half_herald=operating_table(),
                  klyshko_x_1_40=dict(signal=str(k['klyshko_signal']), true_signal='1/2', idler=str(k['klyshko_idler']), true_idler='3/10'),
                  purity_by_widths=purity, all_herald_probability_p_1_79=herald, grade=source_grade(spec), negative_controls=negatives,
                  boundaries=spec['boundaries'], spec_sha256=hashlib.sha256((out/'source_810.json').read_bytes()).hexdigest())
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
