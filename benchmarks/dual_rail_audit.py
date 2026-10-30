"""Dual-rail route audit: exact few-photon statements and the declared plan."""
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.dual_rail import (
    distinguishable_fusion, ghz_merge, hom_from_engine, room_temperature_plan, single_site_euler, visibility_law,
)


def _r(v, bits=8):
    return str(v.real_bounds(bits)[0])


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_dual_rail.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/dual_rail'
    out.mkdir(exist_ok=True)
    euler = all(single_site_euler(t, b, a) for t in range(65) for b in (-64, -16, 0, 7, 48) for a in (-16, 0, 25, 48))
    hom = [dict(theta_pi_over_32=t, coincidence=_r(hom_from_engine(t)['coincidence']), bunched=_r(hom_from_engine(t)['bunched']))
           for t in (0, 8, 16, 24, 32)]
    g = ghz_merge()
    clicks = {str(c): dict(probability=_r(v['probability']), support_is_ghz=v['support_is_ghz'],
                           heralded_phase_steps=v['heralded_phase_steps'], corrected_xxx=_r(v['corrected_xxx']))
              for c, v in g['clicks'].items()}
    d = distinguishable_fusion()
    law = [dict(visibility=v, success=_r(visibility_law(v)['success_probability']), xxx_witness=_r(visibility_law(v)['xxx_witness']),
                exact=visibility_law(v)['witness_equals_visibility']) for v in ('1', '19/20', '1/2', '0')]
    plans = {str(n): room_temperature_plan(n) for n in (1, 4, 2056)}
    (out/'plan_2056.json').write_text(json.dumps(plans['2056'], indent=2)+'\n')
    report = dict(schema='native-dual-rail-audit-v1', author='Monty', status='EXACT_FEW_PHOTON_STATEMENTS_AND_DECLARED_PLAN',
                  evidence_class='IDEAL_COMPONENT_ALGEBRA',
                  tests=dict(count=result.testsRun, passed=result.wasSuccessful(), seconds=elapsed,
                             failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped)),
                  euler_identity_all_65_angles=euler, hom=hom,
                  fusion=dict(success_probability=_r(g['success_probability']), clicks=clicks,
                              distinguishable=dict(success=_r(d['success_probability']), corrected_xxx=_r(d['corrected_xxx']))),
                  visibility_law=law, plan_sites=list(plans), route=dict(wavelength_nm=810, detector='si_spad_810', encoding='dual_rail',
                  two_site_primitive='type-I fusion, heralded 1/2'),
                  measured_records=0, hardware_submitted=False, loss_modelled=False,
                  assumptions=['ideal lossless balanced couplers', 'at most four photons, at most two per mode',
                               'distinguishability modelled as orthogonal internal species; partial overlap as a convex mixture'],
                  open=['810 nm source and core design and fabrication', 'loss, multipair and detector budgets', 'fusion network and multiplexing'])
    names = ('phase_seam_foundation/dual_rail.py', 'benchmarks/dual_rail_audit.py', 'tests/test_phase_seam_dual_rail.py',
             'phase_seam_foundation/temperature_sweep.py', 'phase_seam_foundation/photonic_response.py',
             'native_relational_qc/cyclotomic64.py', 'native_relational_qc/exact.py', 'phase_seam_foundation/DUAL_RAIL.md')
    report['checked_sources_sha256'] = {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'test_results.txt').write_text(stream.getvalue())
    print(json.dumps(dict(tests=report['tests'], euler=euler, fusion=report['fusion'], law=law), indent=2))
    if not result.wasSuccessful():
        print(stream.getvalue()); raise SystemExit(1)


if __name__ == '__main__':
    main()
