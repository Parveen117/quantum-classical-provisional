"""Serial model audit, with optional unchanged Publications/TLM comparison."""
import argparse
from fractions import Fraction as Q
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from phase_seam_foundation.constitutive_response import (
    CubicEnergy,response_record,phase_observer_bounds,harmonic_phase_noise,
)
from phase_seam_foundation.photonic_observer import observer_packet

SOURCE_COMMIT="babb4fb1922bd91c2eadc82abd4b9538a19745d0"
SOURCE_PINS={
    "papers/native-tvsp-lambda-matrices/tvsp_adapter.cjs":"4a95a2c43a8c372057ee1cd6ef4204e656286b42",
    "papers/native-common-cone-limit/native_engine/native_operator.cjs":"7b188defee82aa0edafc586eb3091baf0ceb6900",
    "papers/native-common-cone-limit/native_engine/paninian_operator.cjs":"39d0cc2d2c0b42db319b02f4cd29c045910edbbc",
}
PHASE=((1,0),(0,1),(0,0),(0,0),(Q(1,2),Q(1,2)))


def serial(value):
    if isinstance(value,Q): return str(value)
    if isinstance(value,dict): return {k:serial(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)): return [serial(v) for v in value]
    return value


def compare_tlm(source):
    for name,expected in SOURCE_PINS.items():
        data=(source/name).read_bytes()
        digest=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
        if digest!=expected: raise ValueError("upstream source pin mismatch: "+name)
    script=r'''
const L=require(process.argv[1]);
const radial=c=>{if(!c.turn.zero())throw Error('nonreal source');return c.rad.toString();};
const cases=['0','1','-1','5','-5','1/3'].map(mu=>{
 const f=L.buildFixture(mu,1), tower=L.responseTower(f,1);
 const names=Object.keys(f.responses);
 return {mu,values:Object.fromEntries(names.map(n=>[n,radial(L.outer(f.responses[n]))])),
   first:Object.fromEntries(names.map(n=>[n,['0','1'].map(w=>radial(L.outer(tower[1].components[n][w])))])),
   hessian:L.matrixOuter(f.H).map(row=>row.map(radial)),
   hessian_first:[[1,0],[0,1]].map(([a,b])=>f.H.rows.map(row=>row.map(x=>radial(L.coefficient(x,a,b)))))};
});
process.stdout.write(JSON.stringify(cases));
'''
    path=(source/"papers/native-tvsp-lambda-matrices/tvsp_adapter.cjs").resolve()
    cases=json.loads(subprocess.check_output(["node","-e",script,str(path)],text=True,timeout=60))
    for case in cases:
        record=serial(response_record(CubicEnergy((2,1,5),(0,Q(case["mu"]),0,0),(10,-10))))
        assert record["responses"]==case["values"]
        assert record["response_first"]==case["first"]
        assert record["hessian"]==case["hessian"]
        assert record["hessian_first"]==case["hessian_first"]
    return dict(status="PASSED",repository="Parveen117/Publications",commit=SOURCE_COMMIT,
                source_git_blobs=SOURCE_PINS,node_version=subprocess.check_output(["node","--version"],text=True).strip(),
                case_count=len(cases),cases=cases,upstream_full_suite_replayed=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tlm-source-dir",type=Path,help="Publications root containing the three pinned source files")
    args=parser.parse_args()
    suite=unittest.TestSuite()
    for pattern in ("test_constitutive_response.py","test_phase_seam_photonic_response.py",
                    "test_phase_seam_photonic_observer.py","test_phase_seam_layout_controls.py"):
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/"tests"),pattern=pattern))
    stream=io.StringIO(); start=time.perf_counter()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    elapsed=time.perf_counter()-start
    if not result.wasSuccessful(): print(stream.getvalue()); raise SystemExit(1)
    upstream=compare_tlm(args.tlm_source_dir) if args.tlm_source_dir else dict(status="NOT_RUN_SOURCE_NOT_SUPPLIED")
    p=observer_packet((16,0,48,48),target="exchange_angle",measurements="reference",
                      state_scales=[1]*5,reading_scales=[1]*24,target_scales=[1])
    example=phase_observer_bounds(CubicEnergy((2,1,5),(0,1,0,0),(10,-10)),(0,0),PHASE,p,
                                  patch_radius=Q(1,20),force_radius=Q(1,100))
    markers=[]
    for mu in (0,1,5,-5):
        r=response_record(CubicEnergy((2,1,5),(0,mu,0,0),(10,-10)))
        markers.append(dict(mu=mu,responses=r["responses"],lambdaV_first=r["response_first"]["lambdaV"],
                            curvature=r["selected_response_curvature"]))
    noise=harmonic_phase_noise(CubicEnergy((1,0,1)),((1,0),(1,0),(0,0),(0,0),(1,0)),thermal_scale=Q(1,10))
    sources=("phase_seam_foundation/constitutive_response.py","phase_seam_foundation/CONSTITUTIVE_RESPONSE.md",
             "tests/test_constitutive_response.py","benchmarks/constitutive_response_audit.py",
             "phase_seam_foundation/photonic_response.py","phase_seam_foundation/photonic_observer.py",
             "phase_seam_foundation/photonic_io.py","phase_seam_foundation/photonic_layout.py",
             "native_relational_qc/emk_tensor.py","native_relational_qc/exact.py",
             "native_relational_qc/cyclotomic64.py","native_relational_qc/cyclotomic32.py",
             "native_relational_qc/cyclotomic.py")
    previous={}
    for version,path in (("v0.12","phase_seam_foundation/response/qualification.json"),
                         ("v0.13","phase_seam_foundation/observer/qualification.json")):
        old=json.loads((ROOT/path).read_text())
        assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in old["checked_sources_sha256"].items())
        previous[version]="PRIOR_CHECKED_SOURCE_HASHES_UNCHANGED"
    report=dict(schema="native-constitutive-response-audit-v1",author="Monty",status="DECLARED_MODEL_CHECKS",
                python_version=sys.version.split()[0],tests=dict(count=result.testsRun,passed=result.wasSuccessful(),
                seconds=elapsed,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped)),
                tlm_comparison=upstream,checked_sources_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sources},
                retained_sources=previous,same_value_different_layer=markers,bound_example=example,
                harmonic_common_mode_example=noise,examples_evidence_class="DECLARED_SYNTHETIC_MODELS",
                measured_records=0,calibration_accepted=False,hardware_submitted=False,
                open=["material and conjugate-force calibration","dynamic thermal/electromagnetic response and bath spectra",
                      "nonideal optical loss/preparation/analyzer response","PH2 cycle-to-optical-gate compiler"])
    out=ROOT/"phase_seam_foundation/constitutive"; out.mkdir(exist_ok=True)
    (out/"qualification.json").write_text(json.dumps(serial(report),indent=2,allow_nan=False)+"\n")
    (out/"test_results.txt").write_text(stream.getvalue())
    print(json.dumps(dict(tests=report["tests"],tlm_status=upstream["status"],tlm_cases=upstream.get("case_count",0)),indent=2))


if __name__=="__main__": main()
