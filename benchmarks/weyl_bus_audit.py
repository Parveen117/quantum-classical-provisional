"""Serial exact audit of the conditional bus/EMK gate and its error boundary."""
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.weyl_bus import (
    rectangle, echoed_rectangle, certificate, fault_certificate, native_interaction_bridge,
)


def main():
    suite = unittest.TestSuite()
    for pattern in ("test_weyl_bus.py", "test_phase_seam_joint.py"):
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=pattern))
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter() - start
    if not result.wasSuccessful():
        print(stream.getvalue()); raise SystemExit(1)
    retained = {}
    for version, folder in (("v0.12", "response"), ("v0.13", "observer"), ("v0.14", "constitutive")):
        previous = json.loads((ROOT / "phase_seam_foundation" / folder / "qualification.json").read_text())
        for name, expected in previous["checked_sources_sha256"].items():
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
                raise ValueError("historical checked source changed: " + name)
        retained[version] = "CHECKED_SOURCE_HASHES_UNCHANGED_SUITES_NOT_RERUN"
    sources = (
        "phase_seam_foundation/weyl_bus.py", "phase_seam_foundation/WEYL_BUS.md",
        "tests/test_weyl_bus.py", "tests/test_phase_seam_joint.py", "benchmarks/weyl_bus_audit.py",
        "phase_seam_foundation/joint.py", "phase_seam_foundation/model.py",
        "native_relational_qc/exact.py", "native_relational_qc/cyclotomic.py",
        "native_relational_qc/cyclotomic32.py", "native_relational_qc/cyclotomic64.py",
    )
    bridge = native_interaction_bridge()
    report = dict(
        schema="native-weyl-bus-audit-v1", author="Monty", status="CONDITIONAL_OPERATOR_CHECKS",
        python_version=sys.version.split()[0],
        tests=dict(count=result.testsRun, passed=result.wasSuccessful(), seconds=elapsed,
                   failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped)),
        checked_sources_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources},
        retained_sources=retained,
        admitted_control_contract="two independent data qubits; coherent signed X/Z bus kicks and their inverses",
        examples_evidence_class="EXACT_IDEAL_OPERATOR_MODELS",
        rectangle=certificate(rectangle()), echoed=certificate(echoed_rectangle(drift=(7,-11))),
        smallest_signed_rectangle=certificate(rectangle(1,1),dimension=8),
        smallest_identical_half_echo=certificate(echoed_rectangle(1,1),dimension=16),
        unit_faults=[fault_certificate(rectangle(),after=j,x=1,z=1) for j in range(5)],
        echo_fault_counterexample=fault_certificate(echoed_rectangle(),after=1,z=1),
        initialized_bus_false_positive=certificate(rectangle()[:-1]),
        native_emk_bridge=dict(equal=bridge["native_gate"]==bridge["target"],
                               target=bridge["target"].to_dict()),
        coverage=dict(rectangle_parameter_cases=5460, single_weyl_fault_seam_cases=20480,
                      selected_64_level_words_checked_on_all_256_columns=4,
                      seeded_mixed_words=48, external_bus_reference_checked=True),
        protection=dict(arbitrary_bus_initial_state=True,
                        equal_integrated_local_z_drift_with_ideal_echo=True,
                        arbitrary_midgate_bus_noise=False, correlated_zz_drift=False,
                        control_area_error=False, loss_or_leakage=False),
        prior_art=["https://arxiv.org/abs/1402.6674", "https://arxiv.org/abs/0804.3240"],
        novelty_established=False, physical_device_built=False, hardware_submitted=False,
        open=["derive conditional kicks from a physical interaction Hamiltonian",
              "control and leakage/loss costs with realistic bus dynamics",
              "end-to-end resource comparison and fault-tolerant architecture"],
    )
    folder = ROOT / "phase_seam_foundation" / "weyl_bus"
    folder.mkdir(exist_ok=True)
    (folder / "qualification.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    (folder / "test_results.txt").write_text(stream.getvalue())
    print(json.dumps(dict(tests=report["tests"],coverage=report["coverage"],
                         bridge=report["native_emk_bridge"]["equal"]),indent=2))


if __name__ == "__main__": main()
