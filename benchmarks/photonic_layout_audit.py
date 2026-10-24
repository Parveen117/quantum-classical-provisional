"""Rebuild and independently check the optical core subassembly, with CAD tools."""
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from phase_seam_foundation.photonic_layout import build_layout,check_layout,render_layout
from phase_seam_foundation.photonic_io import calibration_template


def main():
    import gdstk
    out=ROOT/"phase_seam_foundation/layout"
    spec=build_layout(out)
    report=check_layout(out/"exchange_core.gds",spec)
    stream=io.StringIO();start=time.perf_counter()
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"),pattern="test_photonic_layout_geometry.py")
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    report["tests"]=dict(count=result.testsRun,passed=result.wasSuccessful(),failures=len(result.failures),
                         errors=len(result.errors),skipped=len(result.skipped),seconds=time.perf_counter()-start)
    report["gdstk_version"]=gdstk.__version__
    report["schema"]="native-photonic-layout-audit-v1"
    report["author"]="Monty"
    render_layout(out/"exchange_core.gds",out)
    (out/"physical_calibration_template.json").write_text(json.dumps(calibration_template(physical_layout=True),indent=2)+"\n")
    artifacts=("exchange_core.gds","exchange_core_ports.json","exchange_core.png","exchange_unit.png","physical_calibration_template.json")
    report["artifacts_sha256"]={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in artifacts}
    names=("phase_seam_foundation/photonic_layout.py","phase_seam_foundation/photonic_io.py",
           "phase_seam_foundation/photonic_process_binding.json","benchmarks/photonic_layout_audit.py",
           "tests/test_photonic_layout_geometry.py","phase_seam_foundation/layout/requirements.txt")
    names+=tuple("phase_seam_foundation/layout/vendor/cornerstone_sin300/"+n for n in ("mmi2x2.gds","heater.gds","LICENSE"))
    report["checked_sources_sha256"]={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    report["sources"]=dict(pdk_commit="3323b17b4d75c852ed2372d7d13239408cca0eb1",
        rule_pdf_url="https://cornerstone.sotonfab.co.uk/wp-content/uploads/2026/06/CORNERSTONE-Silicon-Nitride-MPW-13-Design-Guidelines.pdf",
        rule_pdf_sha256="10ad02eaa39abcf1fcb82b09ce10bc08b9795e54ed094f44007c860b0b2d9f71",
        pre_drc_archive_url="https://cornerstone.sotonfab.co.uk/wp-content/uploads/2026/06/Klayout-DRC-script-SiN_v3_0.zip",
        pre_drc_archive_sha256="df49c7fb1b75484258a3cccd6924ebc884d4411479a1acb145046e65cca9179e",
        pre_drc_read_not_executed="archive filename v3_0; internal proprietary macro declares version 4.0, 2026-05-29; not redistributed")
    (out/"layout_qualification.json").write_text(json.dumps(report,indent=2)+"\n")
    (out/"layout_test_results.txt").write_text(stream.getvalue())
    print(json.dumps(dict(geometry_passed=report["passed"],tests=report["tests"],artifacts=list(artifacts)),indent=2))
    if not report["passed"] or not result.wasSuccessful():
        print(stream.getvalue());raise SystemExit(1)


if __name__=="__main__":main()
