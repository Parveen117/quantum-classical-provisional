"""Register-family audit: the 2056 design as one point, engines run wider."""
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_relational_qc.register_family import (
    DESIGN_2056, carrier_scaling, cost_laws, qualify_ghz, register_plan,
)


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_native_register_family.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'native_relational_qc/register_family'
    out.mkdir(exist_ok=True)
    plans = [register_plan(**DESIGN_2056)] + [register_plan(b, 32, 8) for b in (128, 256, 512, 1024)]
    for plan in plans:
        plan.pop('bank_ranges', None)
    runs = []
    for n in (2056, 4112, 8224, 16448, 32896):
        r = qualify_ghz(n)
        r['family_a_seconds'] = round(r['family_a_seconds'], 3)
        r['family_b_seconds'] = round(r['family_b_seconds'], 3)
        runs.append(r)
    costs = [{k: (str(v) if not isinstance(v, int) else v) for k, v in cost_laws(n, chi_max=64).items()}
             for n in (256, 2056, 4112, 8224, 16448, 32896)]
    carriers = {str(n): [carrier_scaling(n, 'single_photon_path'), carrier_scaling(n, 'dual_rail'),
                         carrier_scaling(n, 'banked_path', bank_width=4)] for n in (4, 32, 2056, 32896)}
    report = dict(schema='nrqc-register-family-audit-v1', author='Monty',
                  status='PARAMETRIC_FAMILY_WITH_WIDER_EXACT_RUNS', evidence_class='EXACT_SIMULATION',
                  tests=dict(count=result.testsRun, passed=result.wasSuccessful(), seconds=elapsed,
                             failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped)),
                  design_point=DESIGN_2056, plans=plans, cost_laws_chi64=costs, carrier_scaling=carriers,
                  ghz_family_runs=runs, all_runs_passed=all(r['family_a_passed'] and r['family_b_passed'] for r in runs),
                  default_bound_after_audit=2056,
                  boundary=['2056 is a default declared bound; engines are polynomial in N for the admitted families',
                            'no claim of efficient simulation of arbitrary circuits at any N',
                            'carrier counts are identities, not device budgets; dual-rail needs photon-photon gates'])
    names = ('native_relational_qc/register_family.py', 'native_relational_qc/large_register.py',
             'native_relational_qc/pauli_engine.py', 'native_relational_qc/clifford_frame.py',
             'native_relational_qc/stabilizer.py', 'native_relational_qc/clifford_t.py',
             'tests/test_native_register_family.py', 'benchmarks/register_family_audit.py',
             'native_relational_qc/REGISTER_FAMILY.md')
    report['checked_sources_sha256'] = {n: hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    (out/'qualification.json').write_text(json.dumps(report, indent=2, default=str)+'\n')
    (out/'test_results.txt').write_text(stream.getvalue())
    print(json.dumps(dict(tests=report['tests'], runs=runs), indent=2, default=str))
    if not result.wasSuccessful():
        print(stream.getvalue()); raise SystemExit(1)


if __name__ == '__main__':
    main()
