"""Serial Hamiltonian/JC model audit with a pinned collaboration arithmetic source."""
from fractions import Fraction as Q
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from phase_seam_foundation.bus_hamiltonian import (
    BusDesign, least_area_cz_design, matched_area_sensitivity,
    implementation_bound, jc_gate_bound, jc_schedule,
)

SOURCE_COMMIT="f2b969769e5c9fc5c3009ce33ddf2dd9095cb0b4"
SOURCE_PATH="native_relational_qc/cyclotomic_pow2.py"
SOURCE_BLOB="43aa0a7918598364e69fe20def96e0be2bf3a978"


def serial(value):
    if isinstance(value,Q):return str(value)
    if isinstance(value,dict):return {k:serial(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [serial(v) for v in value]
    return value


def main():
    data=(ROOT/SOURCE_PATH).read_bytes()
    digest=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
    if digest!=SOURCE_BLOB:raise ValueError("collaboration arithmetic source changed")
    suite=unittest.TestSuite()
    for pattern in ("test_bus_hamiltonian.py","test_weyl_bus.py","test_phase_seam_joint.py"):
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/"tests"),pattern=pattern))
    stream=io.StringIO(); start=time.perf_counter()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    elapsed=time.perf_counter()-start
    if not result.wasSuccessful():print(stream.getvalue());raise SystemExit(1)
    retained={}
    for version,folder in (("v0.12","response"),("v0.13","observer"),("v0.14","constitutive"),("v0.15","weyl_bus")):
        old=json.loads((ROOT/"phase_seam_foundation"/folder/"qualification.json").read_text())
        for name,expected in old["checked_sources_sha256"].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
                raise ValueError("historical checked source changed: "+name)
        retained[version]="CHECKED_SOURCE_HASHES_UNCHANGED"
    costs=[]
    for d in (8,16,32,64):
        for echo in (False,True):
            design=least_area_cz_design(d,echo=echo)
            costs.append(dict(dimension=d,echo=echo,admitted=design is not None,
                              strengths=[design.a,design.b] if design else None,
                              resources=design.resources() if design else None))
    microscopic=[]
    for ratio in (Q(1,100),Q(1,1000),Q(1,2000)):
        bound=jc_gate_bound(BusDesign(),ratio=ratio,area_bounds=[0]*4,fourier_bounds=[0]*4,
                            flip_bounds=[0]*4,compensation_bounds=[0]*4,other_action_bound=0)
        microscopic.append(dict(ratio=ratio,result=bound))
    sensitivity=matched_area_sensitivity(BusDesign(64,2,4))
    sources=(SOURCE_PATH,"phase_seam_foundation/bus_hamiltonian.py",
             "phase_seam_foundation/BUS_HAMILTONIAN.md","tests/test_bus_hamiltonian.py",
             "benchmarks/bus_hamiltonian_audit.py","phase_seam_foundation/weyl_bus.py",
             "phase_seam_foundation/joint.py","phase_seam_foundation/model.py",
             "native_relational_qc/exact.py","native_relational_qc/cyclotomic64.py",
             "native_relational_qc/cyclotomic32.py","native_relational_qc/cyclotomic.py",
             "native_relational_qc/compact.py")
    import numpy
    report=dict(schema="native-bus-hamiltonian-audit-v1",author="Monty",status="CONDITIONAL_HAMILTONIAN_MODEL_CHECKS",
                python_version=sys.version.split()[0],numpy_version=numpy.__version__,
                tests=dict(count=result.testsRun,passed=result.wasSuccessful(),seconds=elapsed,
                           failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped)),
                collaboration_reuse=dict(repository="Parveen117/quantum-classical-provisional",
                   commit=SOURCE_COMMIT,path=SOURCE_PATH,git_blob=SOURCE_BLOB,source_unchanged=True,
                   full_upstream_suite_replayed=False,calculator_shor_integration_imported=False),
                checked_sources_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources},
                retained_sources=retained,least_area_schedules=costs,
                signed_displacement_schedule=BusDesign().schedule(),fixed_sign_jc_schedule=jc_schedule(BusDesign()),
                matched_area_sensitivity_64=sensitivity,
                finite_unitary_bound_example=implementation_bound(BusDesign(),area_bounds=[Q(1,10000)]*4,
                   fourier_bounds=[Q(1,100000)]*4,flip_bounds=[],residual_action_bound=Q(1,100000)),
                declared_jc_examples=microscopic,
                coverage=dict(new_tests=13,retained_tests=41,exact_64_level_columns=256,
                    exact_literal_schedule_columns=192,continuous_derivative_cases=24,
                    continuous_jc_excitation_block_cases=96,high_precision_spectral_remainder_cases=192),
                evidence_class="DECLARED_EFFECTIVE_AND_JAYNES_CUMMINGS_MODELS",
                control_bounds_are_measurements=False,calibration_accepted=False,hardware_submitted=False,
                novelty_established=False,
                open=["finite Fock-code Fourier operations and conditional-coupling isolation",
                      "material parameters, dissipative noise, multilevel and counter-rotating effects",
                      "total hardware-resource comparison and scalable control architecture"])
    folder=ROOT/"phase_seam_foundation"/"bus_hamiltonian";folder.mkdir(exist_ok=True)
    (folder/"qualification.json").write_text(json.dumps(serial(report),indent=2,allow_nan=False)+"\n")
    (folder/"test_results.txt").write_text(stream.getvalue())
    print(json.dumps(dict(tests=report["tests"],collaboration_source_unchanged=True,coverage=report["coverage"]),indent=2))


if __name__=="__main__":main()
