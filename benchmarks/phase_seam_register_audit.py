"""Serial register audit with all prior targeted foundation checks."""
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from phase_seam_foundation.register_qualification import report


def main():
    suite=unittest.TestSuite(); loader=unittest.TestLoader()
    patterns=("test_phase_seam_controller.py","test_phase_seam_sector.py","test_phase_seam_register.py","test_phase_seam_encoding.py",
              "test_phase_seam_joint.py","test_phase_seam_foundation.py","test_native_calculator.py")
    for pattern in patterns:
        suite.addTests(loader.discover(str(ROOT/"tests"),pattern=pattern))
    # Only the existing measurement/reset/feedback checks relevant to this adapter.
    from test_native_dynamic import DynamicTests
    dynamic_tests=("test_initial_classical_memory_and_empty_query",
                   "test_measurement_retains_quantum_classical_correlation",
                   "test_measurement_overwrites_old_memory",
                   "test_reset_preserves_remote_mixed_state_and_old_record",
                   "test_repeated_measurement_and_later_basis_change",
                   "test_feedforward_uses_current_memory_and_zero_condition",
                   "test_budgets_fail_without_modifying_program")
    suite.addTests(DynamicTests(name) for name in dynamic_tests)
    stream=io.StringIO(); start=time.perf_counter()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    elapsed=time.perf_counter()-start
    out=report()
    out["validation"]=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                          skipped=len(result.skipped),passed=result.wasSuccessful(),seconds=elapsed,
                          scope="controller, compressed/full register, v0.3, v0.2, v0.1, calculator smoke and seven existing dynamic checks; full native/Shor suite not rerun",
                          selected_dynamic_tests=list(dynamic_tests))
    names=("phase_seam_foundation/register.py","phase_seam_foundation/register_qualification.py",
           "phase_seam_foundation/register_source_manifest.json","phase_seam_foundation/model.py",
           "phase_seam_foundation/encoding.py","phase_seam_foundation/joint.py",
           "native_relational_qc/modular_arithmetic.py","native_relational_qc/compact.py",
           "native_relational_qc/phase_backend.py","native_relational_qc/exact.py",
           "native_relational_qc/cyclotomic.py","native_relational_qc/cyclotomic32.py",
           "native_relational_qc/cyclotomic64.py","benchmarks/phase_seam_register_audit.py")
    names += ("phase_seam_foundation/controller.py","native_relational_qc/dynamic.py","tests/test_native_dynamic.py")
    names += tuple("tests/"+p for p in patterns)
    out["checked_sources_sha256"]={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    (ROOT/"phase_seam_foundation/register_qualification.json").write_text(json.dumps(out,indent=2)+"\n")
    (ROOT/"phase_seam_foundation/register_test_results.txt").write_text(stream.getvalue())
    print(json.dumps(out["validation"],indent=2))
    if not result.wasSuccessful():
        print(stream.getvalue()); raise SystemExit(1)


if __name__ == "__main__": main()
