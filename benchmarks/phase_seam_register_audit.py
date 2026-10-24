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
    patterns=("test_phase_seam_sector.py","test_phase_seam_register.py","test_phase_seam_encoding.py",
              "test_phase_seam_joint.py","test_phase_seam_foundation.py","test_native_calculator.py")
    for pattern in patterns:
        suite.addTests(loader.discover(str(ROOT/"tests"),pattern=pattern))
    stream=io.StringIO(); start=time.perf_counter()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    elapsed=time.perf_counter()-start
    out=report()
    out["validation"]=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                          skipped=len(result.skipped),passed=result.wasSuccessful(),seconds=elapsed,
                          scope="compressed/full register, v0.3, v0.2, v0.1 and calculator smoke; full native/Shor suite not rerun")
    names=("phase_seam_foundation/register.py","phase_seam_foundation/register_qualification.py",
           "phase_seam_foundation/register_source_manifest.json","phase_seam_foundation/model.py",
           "phase_seam_foundation/encoding.py","phase_seam_foundation/joint.py",
           "native_relational_qc/modular_arithmetic.py","native_relational_qc/compact.py",
           "native_relational_qc/phase_backend.py","native_relational_qc/exact.py",
           "native_relational_qc/cyclotomic.py","native_relational_qc/cyclotomic32.py",
           "native_relational_qc/cyclotomic64.py","benchmarks/phase_seam_register_audit.py")
    names += tuple("tests/"+p for p in patterns)
    out["checked_sources_sha256"]={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    (ROOT/"phase_seam_foundation/register_qualification.json").write_text(json.dumps(out,indent=2)+"\n")
    (ROOT/"phase_seam_foundation/register_test_results.txt").write_text(stream.getvalue())
    print(json.dumps(out["validation"],indent=2))
    if not result.wasSuccessful():
        print(stream.getvalue()); raise SystemExit(1)


if __name__ == "__main__": main()
