"""Serial, fixed-protocol learning experiment; synthetic labels, no hardware jobs."""
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
from native_relational_qc.self_learning import FIELD,Evaluator,fit,assess,load_packet,information_ceiling,digest
from native_relational_qc.learning_tasks import xor_examples,curvature_splits,classical_baselines

SOURCE_COMMIT="f2b969769e5c9fc5c3009ce33ddf2dd9095cb0b4"
PINS={"native_relational_qc/phase_backend.py":"74932a5d1a79ed5970c05850db4a52127a947498",
      "native_relational_qc/cyclotomic_pow2.py":"43aa0a7918598364e69fe20def96e0be2bf3a978"}


def verify_training(result,examples,evaluator):
    if result["model"]["training_sha256"]!=digest([e.record() for e in examples]):
        raise ValueError("model is not bound to the stated training split")
    for restart in result["trace"]:
        previous=None
        for event in restart["events"]:
            params=tuple(event["parameters"])
            errors=[evaluator.probability(e.features,params)-e.target for e in examples]
            value=sum((e*e for e in errors),FIELD())/len(examples)
            if value!=FIELD.from_dict(event["loss"]):raise ValueError("training loss replay mismatch")
            if previous is not None and (value-previous).real_sign()>=0:raise ValueError("accepted update did not improve")
            previous=value


def main():
    for name,sha in PINS.items():
        data=(ROOT/name).read_bytes()
        if hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()!=sha:
            raise ValueError("collaboration source changed: "+name)
    suite=unittest.TestSuite()
    for pattern in ("test_self_learning.py","test_native_calculator.py","test_phase_seam_photonic_response.py"):
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/"tests"),pattern=pattern))
    stream=io.StringIO(); start=time.perf_counter()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    test_seconds=time.perf_counter()-start
    if not result.wasSuccessful():print(stream.getvalue());raise SystemExit(1)
    print(f"Regression checks passed: {result.testsRun}; starting fixed learning protocol",flush=True)
    runs={};sources={}
    for view in ("xor_bits","first_layer","point_only"):
        evaluator=Evaluator();start=time.perf_counter()
        if view=="xor_bits":
            train=xor_examples();splits={"training_truth_table":train}
        else:
            splits,source=curvature_splits(view=view);train=splits["train"];sources[view]=source
        trained=fit(train,view=view,evaluator=evaluator,seeds=(17,41,73),sweeps=3)
        fit_seconds=time.perf_counter()-start
        # The model is fixed before any validation/test call. There is no
        # score-dependent retry or model selection after this point.
        frozen=json.loads(json.dumps(trained["model"]))
        verify_training(trained,train,evaluator)
        scores={name:assess(frozen,rows,evaluator=evaluator) for name,rows in splits.items()}
        if frozen!=trained["model"]:raise ValueError("model changed after freezing")
        runs[view]=dict(training=trained,scores=scores,fit_wall_seconds=fit_seconds,
                        total_wall_seconds=time.perf_counter()-start,resources=dict(evaluator.stats),
                        information_ceilings={k:information_ceiling(v) for k,v in splits.items()})
        print(view,{k:v["accuracy"] for k,v in scores.items()},"fit_seconds",round(fit_seconds,3),flush=True)
    full,_=curvature_splits();start=time.perf_counter()
    baselines=classical_baselines(full["train"],full["test"])
    baseline_seconds=time.perf_counter()-start
    checked=("native_relational_qc/self_learning.py","native_relational_qc/learning_tasks.py",
             "native_relational_qc/SELF_LEARNING.md","native_relational_qc/phase_backend.py",
             "native_relational_qc/cyclotomic_pow2.py","native_relational_qc/compact.py",
             "native_relational_qc/exact.py","phase_seam_foundation/constitutive_response.py",
             "native_relational_qc/emk_tensor.py","tests/test_self_learning.py",
             "tests/test_native_calculator.py","tests/test_phase_seam_photonic_response.py",
             "benchmarks/self_learning_audit.py")
    changes=[]
    for folder in ("response","observer","constitutive","weyl_bus","bus_hamiltonian"):
        old=json.loads((ROOT/"phase_seam_foundation"/folder/"qualification.json").read_text())
        for name,sha in old["checked_sources_sha256"].items():
            actual=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            if actual!=sha:changes.append(dict(historical_manifest=folder,path=name,old_sha256=sha,current_sha256=actual))
    if {x["path"] for x in changes}!={"native_relational_qc/phase_backend.py"}:
        raise ValueError("unexpected historical dependency changes")
    report=dict(schema="native-self-learning-audit-v1",author="Monty",status="SYNTHETIC_EXACT_SIMULATOR_TRAINING",
        python_version=sys.version.split()[0],
        tests=dict(count=result.testsRun,passed=result.wasSuccessful(),seconds=test_seconds,
                   failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped)),
        collaboration=dict(commit=SOURCE_COMMIT,unchanged_git_blobs=PINS,full_upstream_suite_replayed=False,
                           wider_shor_and_calculator_registration_imported=False),
        checked_sources_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in checked},
        historical_dependency_updates=changes,
        protocol=dict(seeds=[17,41,73],sweeps=3,parameter_grid_pi_over_32=list(range(0,64,8)),
            model_selection="training Brier loss only",test_evaluated_after_model_frozen=True,
            external_blind_test=False,architecture_contains_parity_connectivity=True),
        runs=runs,classical_same_feature_baselines=baselines,classical_baseline_wall_seconds=baseline_seconds,
        physical_measurements_used=False,hardware_jobs=0,heater_commands=0,quantum_speedup_established=False,
        rh_or_yang_mills_proof_claim=False,universal_generalization_claim=False)
    folder=ROOT/"native_relational_qc"/"learning";folder.mkdir(exist_ok=True)
    (folder/"qualification.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    (folder/"datasets.json").write_text(json.dumps(sources,indent=2,allow_nan=False)+"\n")
    for name,run in runs.items():
        (folder/(name+"_model.json")).write_text(json.dumps(run["training"]["model"],indent=2)+"\n")
    (folder/"test_results.txt").write_text(stream.getvalue())
    print(json.dumps(dict(tests=report["tests"],held_out_accuracy=runs["first_layer"]["scores"]["test"]["accuracy"],
                         blind_accuracy=runs["point_only"]["scores"]["test"]["accuracy"],baselines=baselines),indent=2))


if __name__=="__main__":main()
