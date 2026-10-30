"""810 nm core re-target audit: exact scaled geometry, heater and drift laws, readiness grade."""
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.core_retarget import design_readiness, retarget_spec


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_core_retarget.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/core_retarget'
    out.mkdir(exist_ok=True)
    spec = retarget_spec()
    (out/'retarget_810.json').write_text(json.dumps(spec, indent=2)+'\n')
    grade = design_readiness(spec)
    negatives = dict(
        multimode=design_readiness(dict(solver=dict(tool='x', single_mode_te_810=False, width_margin_nm=1, mmi_split_tolerance='1', bend_loss_db_per_90deg='1')))['grade'],
        synthetic_measurement=design_readiness(dict(solver=dict(tool='x', single_mode_te_810=True, width_margin_nm=1, mmi_split_tolerance='1', bend_loss_db_per_90deg='1'),
                                                    drc=dict(foundry='x', passed=True, report_sha256='0'), fabrication=dict(lot_id='a', die_id='b'),
                                                    measurement=dict(evidence_class='SYNTHETIC', transfer_matrix_sha256='1')))['grade'])
    report = dict(schema='native-core-retarget-audit-v1', author='Monty', status='SCALED_NOMINAL_NO_SOLVER_NO_DRC_NO_FABRICATION',
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 3),
                  ratio=spec['ratio'], strip_width_nm_810=next(r['scaled_nm'] for r in spec['geometry'] if r['dimension'] == 'strip_width'),
                  heater=spec['heater'], drift=spec['drift'], readiness=grade, negative_controls=negatives,
                  boundaries=['no mode solver has been run; scaled numbers are the solver input, not a design',
                              'film thickness 300 nm and material dispersion break exact scaling',
                              'vendor 1550 nm MMI and heater cells are not reused; MMI must be redesigned at 810 nm',
                              'foundry support for 810 nm not established; platform selection open',
                              'nothing here changes the temperature verdict, which grades recorded logs only'],
                  spec_sha256=hashlib.sha256((out/'retarget_810.json').read_bytes()).hexdigest())
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
