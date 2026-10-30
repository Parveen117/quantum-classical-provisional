"""Serial temperature-sweep audit; exact statements and an unrun plan only."""
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.temperature_sweep import (
    common_mode_invariance, common_mode_global_phase, drift_dichotomy, drift_table, hom_coincidence, sweep_protocol,
    temperature_claim_verdict, DETECTOR_OPTIONS,
)


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_temperature_sweep.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/temperature'
    out.mkdir(exist_ok=True)
    matrix_identity = all(common_mode_global_phase(theta, shift)
                          for theta in range(65) for shift in (-64, -9, 1, 7, 32, 64))
    invariance = all(common_mode_invariance(theta, shift)[f]
                     for theta in range(0, 65, 4) for shift in (-9, 32) for f in ('basis', 'local', 'reference'))
    dichotomy = []
    for theta in (8, 16, 24):
        for drift in ((1, 0, 0, 0, 0), (0, 1, 0, 0, 0), (0, 0, 1, 0, 0), (0, 0, 0, 1, 0), (0, 0, 0, 0, 1), (1, 1, 0, 0, 0), (1, 1, 0, 0, 1)):
            d = drift_dichotomy(theta, drift)
            dichotomy.append(dict(theta_pi_over_32=theta, drift=list(drift), in_kernel=d['in_kernel'],
                                  first_order_visible=d['first_order_visible'], correction=list(d['exact_correction_steps'])))
    interior_ok = all(row['in_kernel'] or row['first_order_visible']['reference'] for row in dichotomy)
    hom = [dict(theta_pi_over_32=t, indistinguishable=str(hom_coincidence(t)['indistinguishable'].real_bounds(8)[0]),
                distinguishable=str(hom_coincidence(t)['distinguishable'].real_bounds(8)[0])) for t in (0, 8, 16, 24, 32)]
    table = drift_table(dn_dT_per_K='2.45e-5', wavelength_m='1.55e-6',
                        path_length_differences_m=['1e-5', '1e-4', '1e-3'], delta_Ts_K=[1, 5, 20, 50])
    table810 = drift_table(dn_dT_per_K='2.45e-5', wavelength_m='8.1e-7',
                           path_length_differences_m=['1e-5', '1e-4', '1e-3'], delta_Ts_K=[1, 5, 20, 50])
    plans = {}
    for option, lam in (('si_spad_810', 810), ('ingaas_spad_1550', 1550), ('snspd_1550', 1550)):
        plan = sweep_protocol([15, 25, 35, 45, 55], wavelength_nm=lam, detector_option=option)
        text = json.dumps(plan, indent=2, sort_keys=True)
        plan['plan_sha256'] = hashlib.sha256(text.encode()).hexdigest()
        (out/f'sweep_plan_{option}.json').write_text(json.dumps(plan, indent=2)+'\n')
        plans[option] = plan['plan_sha256']
    empty = temperature_claim_verdict(dict(evidence_class=None))
    report = dict(schema='native-photonic-temperature-sweep-audit-v1', author='Monty',
                  status='EXACT_STATEMENTS_AND_UNRUN_PLAN', evidence_class='IDEAL_COMPONENT_ALGEBRA',
                  tests=dict(count=result.testsRun, passed=result.wasSuccessful(), seconds=elapsed,
                             failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped)),
                  common_mode_matrix_identity_all_65_angles=matrix_identity,
                  common_mode_probability_invariance_17_angles=invariance,
                  dichotomy_rows=dichotomy, interior_kernel_or_reference_visible=interior_ok,
                  hom_coincidence=hom,
                  declared_drift_table_1550nm=table, declared_drift_table_810nm=table810,
                  declared_material_inputs=dict(dn_dT_per_K='2.45e-5 (declared SiN value for the table; not measured on this core)'),
                  detector_options=list(DETECTOR_OPTIONS), plan_sha256=plans,
                  empty_record_verdict=dict(thermal=empty['thermal_class'], logic=empty['logic_class'], claims_allowed=empty['claims_allowed']),
                  measured_records=0, hardware_submitted=False, thermal_solved=False, material_parameters_fitted=False,
                  assumptions=['ideal lossless balanced couplers and calibrated coherent preparation/analyzers',
                               'phase-only drift; splitting ratio, loss, source spectrum and detector efficiency drift are outside the model',
                               'exact statements are at pi/32 samples; the common-mode theorem holds for every real shift by global phase'],
                  open=['fabricated core, packaged bench and any recorded temperature log',
                        'two-photon source and HOM measurement at the exchange unit',
                        'room-temperature detector route and its re-targeted wavelength design'])
    names = ('phase_seam_foundation/temperature_sweep.py', 'benchmarks/temperature_sweep_audit.py',
             'tests/test_phase_seam_temperature_sweep.py', 'phase_seam_foundation/photonic_response.py',
             'phase_seam_foundation/photonic_io.py', 'phase_seam_foundation/photonic_layout.py',
             'phase_seam_foundation/model.py', 'native_relational_qc/cyclotomic64.py', 'native_relational_qc/exact.py',
             'phase_seam_foundation/TEMPERATURE_SWEEP.md')
    report['checked_sources_sha256'] = {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    (out/'qualification.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'test_results.txt').write_text(stream.getvalue())
    print(json.dumps(dict(tests=report['tests'], matrix_identity=matrix_identity, invariance=invariance, interior_ok=interior_ok, plans=plans), indent=2))
    if not result.wasSuccessful():
        print(stream.getvalue()); raise SystemExit(1)


if __name__ == '__main__':
    main()
