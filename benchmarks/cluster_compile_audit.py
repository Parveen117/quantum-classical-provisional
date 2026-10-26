"""Cluster-compile audit: lemmas at every native angle, exact end-to-end witnesses with controls, resources, codebook, grade."""
import io
import json
from fractions import Fraction
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.cluster_compile import (
    XOR_CHECKPOINT, cluster_resources, compile_grade, compile_plan, gadget_lemma, heater_codebook, propagation_lemma,
    ry_lemma, witness, xor_witnesses,
)


def _f(v):
    return None if v is None else f"{float(v):.6g}"


def _d(v):
    return v.display(12)["decimal"]


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_cluster_compile.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/cluster'
    out.mkdir(exist_ok=True)
    lemmas = dict(G1_gadget_all_64=all(gadget_lemma(k)["holds"] for k in range(64)), G2_propagation=propagation_lemma()["holds"],
                  G3_ry_all_64=all(ry_lemma(k)["prep_holds"] and ry_lemma(k)["additive_holds"] for k in range(64)))
    xor = [dict(features=r["features"], label=r["label"], predicted=r["predicted"], exact_equality=r["exact_equality"], p_one=_d(r["p_one"]),
                x_only_control_diverges=r["x_only_control_diverges"], uncorrected_paths_differ=r["uncorrected_paths_differ"]) for r in xor_witnesses()]
    generic = []
    seed = 20261027
    for _ in range(4):
        vals = []
        for _ in range(7):
            seed = (seed * 1103515245 + 12345) % (1 << 31)
            vals.append(seed % 64)
        w = witness(tuple(vals[:2]), tuple(vals[2:]))
        generic.append(dict(features=w["features"], parameters=w["parameters"], exact_equality=w["exact_equality"],
                            circuit=_d(w["circuit_probability"]), pattern=_d(w["pattern_probability"]),
                            every_branch_weight_half=w["every_branch_weight_half"],
                            uncorrected_all_zero_path=_d(w["control_no_corrections"]["all_zero_path"]),
                            uncorrected_all_one_path=_d(w["control_no_corrections"]["all_one_path"]),
                            x_only_control_diverges=w["control_x_only"]["branches_diverge"]))
    resources = {f"spare={r}": {k: (str(v) if isinstance(v, (Fraction, int, bool)) else v) for k, v in cluster_resources(r).items()} for r in (0, 2, 4, 8)}
    book = heater_codebook((0, 32), XOR_CHECKPOINT)
    grades = dict(empty=compile_grade({}), claim_rejected=compile_grade(dict(quantum_advantage=True)))
    record = dict(schema="native-cluster-compile-audit-v1", author="Monty", status="COMPILED_NO_DEVICE",
                  tests=dict(run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 2)),
                  plan=compile_plan(), lemmas=lemmas, xor_checkpoint=xor, generic_angle_witnesses=generic, resources=resources,
                  heater_codebook=book, grades=grades,
                  disclaimers=["no photonic device exists; every number is an exact consequence of declared inputs",
                               "training stays on the PC; no learning on chip, no speedup, no advantage; the pinned source's classical baseline reaches 100 %",
                               "cluster storage survival, switch/buffer losses and the hardware form of the corrections are open"])
    (out/'qualification.json').write_text(json.dumps(record, indent=1, default=str))
    (out/'test_results.txt').write_text(stream.getvalue())
    print(json.dumps(dict(tests=record["tests"], lemmas=lemmas, xor=[(r["label"], r["predicted"], r["exact_equality"]) for r in xor],
                          generic=[(g["exact_equality"], g["pattern"]) for g in generic],
                          one_shot=resources["spare=0"]["p_build_all"], spare4=resources["spare=4"]["p_build_all"],
                          bell_pairs_spare4=_f(cluster_resources(4)["expected_bell_pairs_conditional_on_success"])), indent=1))


if __name__ == "__main__":
    main()
