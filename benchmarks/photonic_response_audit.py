"""Serial local-response audit; no material simulations or hardware jobs."""
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.photonic_response import optical_response, exact_rank, response_plan


def main():
    suite = unittest.TestSuite()
    for pattern in ('test_phase_seam_photonic_response.py', 'test_phase_seam_layout_controls.py'):
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=pattern))
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/response'
    out.mkdir(exist_ok=True)
    plan = response_plan()
    (out/'acquisition_plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    ranks = []
    for theta in (0,8,16,32):
        point = ((32-theta)%64,0,48,48)
        ranks.append(dict(theta_pi_over_32=theta, ranks={kind:exact_rank(
            optical_response(point,measurements=kind)['jacobian'])
            for kind in ('basis','local','reference')}))
    response = optical_response((16,0,48,48))
    witness_labels = ('local:0->0','local:+->0','local:0->+','reference:0->0:analyzer_0')
    witness = [response['jacobian'][response['labels'].index(label)] for label in witness_labels]
    assert all(not any(v.coefficients[1:]) for row in witness for v in row)
    report = dict(schema='native-photonic-response-audit-v1', author='Monty',
                  status='IDEAL_LOCAL_RESPONSE_CHECKS', evidence_class='IDEAL_COMPONENT_ALGEBRA',
                  tests=dict(count=result.testsRun, passed=result.wasSuccessful(), seconds=elapsed,
                             failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped)),
                  phase_order=list(response['phase_order']), derivative_unit='per radian',
                  representative_ranks=ranks, angle_test_scope='all 64 pi/32 samples, three measurement families',
                  quadrature_witness_labels=list(witness_labels),
                  quadrature_witness_jacobian=[[str(v.coefficients[0]) for v in row] for row in witness],
                  common_unobservable_direction=[1,1,0,0,1],
                  reference_note='reference phase is a fifth variable; rank four is relative, never absolute phase',
                  layout_gds_sha256=plan['layout_gds_sha256'],layout_spec_sha256=plan['layout_spec_sha256'],
                  material_parameters_fitted=False, maxwell_solved=False, thermal_solved=False,
                  measured_records=0, hardware_submitted=False,
                  prior_validation='199 foundation and 9 CAD tests passed at v0.11; those full suites were not rerun here',
                  assumptions=['ideal balanced lossless D couplers','calibrated coherent preparation/analyzers',
                               'local differentiability; exact rank does not establish noise conditioning',
                               'phase-only chain omits power-dependent loss and splitter changes'],
                  open=['complex component transfer','joint electrothermal response and settling',
                        'uncertainty, loss, reference drift and full device qualification'])
    names = ('phase_seam_foundation/photonic_response.py','benchmarks/photonic_response_audit.py',
             'tests/test_phase_seam_photonic_response.py','tests/test_phase_seam_layout_controls.py',
             'phase_seam_foundation/photonic_io.py','phase_seam_foundation/photonic_layout.py',
             'phase_seam_foundation/model.py','phase_seam_foundation/photonic_exchange.py',
             'phase_seam_foundation/photonic_process_binding.json','phase_seam_foundation/PHOTONIC_RESPONSE.md',
             'phase_seam_foundation/sector_control.py','native_relational_qc/cyclotomic64.py',
             'native_relational_qc/cyclotomic32.py','native_relational_qc/cyclotomic.py',
             'native_relational_qc/exact.py','native_relational_qc/phase_backend.py')
    report['checked_sources_sha256']={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    report['plan_sha256']=hashlib.sha256((out/'acquisition_plan.json').read_bytes()).hexdigest()
    (out/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'test_results.txt').write_text(stream.getvalue())
    print(json.dumps(dict(tests=report['tests'],ranks=ranks),indent=2))
    if not result.wasSuccessful():
        print(stream.getvalue());raise SystemExit(1)


if __name__ == '__main__': main()
