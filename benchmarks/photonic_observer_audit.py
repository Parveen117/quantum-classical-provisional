"""Serial photonic observer adapter audit; optional external pinned engine."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.photonic_observer import (
    BOUND_NAMES, DEVICE_SOURCE, TARGETS, _device_engine, _read_packet,
    observer_packet, assess_uncertainty,
)


def packet(theta=16, target="exchange_angle", family="basis", **kwargs):
    options = dict(state_scales=[1]*5, reading_scales=[1]*{"basis":4,"local":16,"reference":24}[family],
                   target_scales=[1]*len(TARGETS[target]))
    options.update(kwargs)
    return observer_packet(((32-theta)%64,0,48,48), target=target, measurements=family, **options)


def integration(source):
    engine = _device_engine(source)
    cross_checks = []
    for theta in (0,16,32):
        for family in ("basis","local","reference"):
            for target in TARGETS:
                p = packet(theta,target,family)
                s, pi = _read_packet(p)
                r = engine(s,pi)
                assert r["exact_target_faithful"] == p["exact_target_faithful"]
                cross_checks.append(dict(theta_pi_over_32=theta, family=family, target=target,
                                         faithful=p["exact_target_faithful"],
                                         blind_dimension=p["target_blind_dimension"]))
    base = dict(sensor_noise_bound=.001, calibration_drift_operator_bound=.002,
                state_norm_bound=.1, target_error_budget=.01, nonlinear_remainder_bound=.0001)
    fixtures = [
        ("bounded_angle",packet(),base,"MODEL_BUDGET_MET_NUMERICALLY"),
        ("excess_noise",packet(),{**base,"sensor_noise_bound":1},"MODEL_ERROR_BUDGET_EXCEEDED"),
        ("excess_drift",packet(),{**base,"calibration_drift_operator_bound":1},"MODEL_ERROR_BUDGET_EXCEEDED"),
        ("excess_remainder",packet(),{**base,"nonlinear_remainder_bound":1},"MODEL_ERROR_BUDGET_EXCEEDED"),
        ("tight_budget",packet(),{**base,"target_error_budget":.001},"MODEL_ERROR_BUDGET_EXCEEDED"),
        ("weak_reference",packet(target="relative_phases",family="reference",reading_scales=[1]*16+[10**15]*8),
         base,"NUMERICAL_DECODER_UNRESOLVED"),
        ("reading_unit_change",packet(reading_scales=[2]*4),
         {**base,"sensor_noise_bound":.0005,"calibration_drift_operator_bound":.001,
          "nonlinear_remainder_bound":.00005},"MODEL_BUDGET_MET_NUMERICALLY"),
        ("state_unit_change",packet(state_scales=[2]*5),
         {**base,"state_norm_bound":.05,"calibration_drift_operator_bound":.004},"MODEL_BUDGET_MET_NUMERICALLY"),
        ("target_unit_change",packet(target_scales=[2]),
         {**base,"target_error_budget":.005},"MODEL_BUDGET_MET_NUMERICALLY"),
    ]
    policies = []
    for name,p,b,expected in fixtures:
        r = assess_uncertainty(p,bounds=b,device_source_dir=source)
        assert r["status"] == expected, (name,r["status"])
        assert r["calibration_accepted"] is False and r["hardware_submitted"] is False
        if name in ("bounded_angle","reading_unit_change","state_unit_change"):
            assert abs(r["numeric_target_error_estimate"]-.0013) < 1e-15
        if name == "target_unit_change":
            assert abs(2*r["numeric_target_error_estimate"]-.0013) < 1e-15
        policies.append(dict(name=name,evidence_class="SYNTHETIC_POLICY_FIXTURE",
                             expected_status=expected,report=r))
    import numpy
    return dict(status="PASSED", source=DEVICE_SOURCE, numpy_version=numpy.__version__,
                cross_check_count=len(cross_checks), cross_checks=cross_checks,
                policy_fixture_count=len(policies), policy_fixtures=policies,
                upstream_full_test_suite_run=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-source-dir",type=Path,
                        help="authorized directory containing the two pinned private engine files")
    args = parser.parse_args()
    suite = unittest.TestSuite()
    for pattern in ("test_phase_seam_photonic_observer.py", "test_phase_seam_photonic_response.py",
                    "test_phase_seam_layout_controls.py"):
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/"tests"),pattern=pattern))
    stream = io.StringIO(); started = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    elapsed = time.perf_counter()-started
    if not result.wasSuccessful():
        print(stream.getvalue()); raise SystemExit(1)
    external = integration(args.device_source_dir) if args.device_source_dir else dict(status="NOT_RUN_ENGINE_NOT_SUPPLIED")
    template = dict(schema="native-photonic-observer-request-v1",status="UNMEASURED_REQUEST",
                    packet=packet(target="relative_phases",family="reference"),
                    bounds={name:None for name in BOUND_NAMES}, device_id=None,
                    raw_evidence_sha256=[], calibration_accepted=False, hardware_submitted=False)
    out = ROOT/"phase_seam_foundation/observer"
    out.mkdir(exist_ok=True)
    (out/"request_template.json").write_text(json.dumps(template,indent=2)+"\n")
    names = ("phase_seam_foundation/photonic_observer.py", "phase_seam_foundation/PHOTONIC_OBSERVER.md",
             "benchmarks/photonic_observer_audit.py", "tests/test_phase_seam_photonic_observer.py",
             "phase_seam_foundation/photonic_response.py", "tests/test_phase_seam_photonic_response.py",
             "tests/test_phase_seam_layout_controls.py", "phase_seam_foundation/photonic_io.py",
             "phase_seam_foundation/photonic_layout.py", "native_relational_qc/cyclotomic64.py")
    report = dict(schema="native-photonic-observer-audit-v1",author="Monty",
                  status="IDEAL_TARGET_AND_CONDITIONAL_UNCERTAINTY_CHECKS",python_version=sys.version.split()[0],
                  tests=dict(count=result.testsRun,passed=result.wasSuccessful(),seconds=elapsed,
                             failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped)),
                  integration=external,
                  checked_sources_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names},
                  request_template_sha256=hashlib.sha256((out/"request_template.json").read_bytes()).hexdigest(),
                  measured_records=0,calibration_accepted=False,hardware_submitted=False,
                  boundary="Exact local model visibility; floating-point conditional uncertainty estimates, not hardware qualification",
                  prior_validation="v0.11 complete foundation/CAD suites retained; no geometry changed or full CAD rerun")
    (out/"qualification.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    (out/"test_results.txt").write_text(stream.getvalue())
    print(json.dumps(dict(tests=report["tests"],integration_status=external["status"],
                         cross_checks=external.get("cross_check_count",0),
                         policy_fixtures=external.get("policy_fixture_count",0)),indent=2))


if __name__ == "__main__": main()
