"""Serial bridge qualification; retains prior suites without rerunning Shor."""
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from phase_seam_foundation.encoding_qualification import report


def main():
    suite=unittest.TestSuite(); loader=unittest.TestLoader()
    for pattern in ("test_phase_seam_encoding.py","test_phase_seam_joint.py",
                    "test_phase_seam_foundation.py","test_native_calculator.py"):
        suite.addTests(loader.discover(str(ROOT/"tests"),pattern=pattern))
    stream=io.StringIO(); start=time.perf_counter()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    elapsed=time.perf_counter()-start
    out=report()
    out["validation"]=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                          skipped=len(result.skipped),passed=result.wasSuccessful(),seconds=elapsed,
                          scope="encoding, joint, v0.1 and calculator smoke; full native/Shor suites not rerun")
    paths=[ROOT/name for name in (
        "phase_seam_foundation/encoding.py","phase_seam_foundation/encoding_qualification.py",
        "phase_seam_foundation/encoding_source_manifest.json","phase_seam_foundation/model.py",
        "phase_seam_foundation/joint.py","native_relational_qc/exact.py",
        "native_relational_qc/cyclotomic.py","native_relational_qc/cyclotomic32.py",
        "native_relational_qc/cyclotomic64.py","tests/test_phase_seam_encoding.py",
        "tests/test_phase_seam_joint.py","tests/test_phase_seam_foundation.py",
        "tests/test_native_calculator.py","benchmarks/phase_seam_encoding_audit.py")]
    out["checked_sources_sha256"]={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (ROOT/"phase_seam_foundation/encoding_qualification.json").write_text(json.dumps(out,indent=2)+"\n")
    (ROOT/"phase_seam_foundation/encoding_test_results.txt").write_text(stream.getvalue())
    print(json.dumps(out["validation"],indent=2))
    if not result.wasSuccessful():
        print(stream.getvalue());raise SystemExit(1)


if __name__=="__main__":main()
