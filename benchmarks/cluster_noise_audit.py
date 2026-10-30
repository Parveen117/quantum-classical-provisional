"""Cluster noise audit: Lemmas N1-N3, response tables (XOR and generic angles), source map, Theorem N bounds, controls, grade."""
import io
import json
from fractions import Fraction
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.cluster_compile import NODES, XOR_CHECKPOINT
from phase_seam_foundation.cluster_noise import (
    GENERIC, controls, first_order_error, merge_lemma, noise_grade, noise_plan, reduction_lemma, required_double_fraction, response_table,
    source_map, xor_response,
)


def _f(v):
    if v is None:
        return None
    if hasattr(v, "display"):
        return v.display(8)["decimal"]
    return f"{float(v):.6g}"


def _d(v):
    return v.display(8)["decimal"]


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_cluster_noise.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/noise'
    out.mkdir(exist_ok=True)
    m = merge_lemma()
    xr = xor_response()
    gen = response_table(GENERIC["features"], GENERIC["parameters"])
    generic_rows = {v: {p: dict(pattern=r["pattern"], p_one=_d(r["p_one"]), change=_d(r["change"])) for p, r in row.items()} for v, row in gen["rows"].items()}
    cache = {}
    bounds = {}
    for label, (features, parameters) in (("xor_0_32", ((0, 32), XOR_CHECKPOINT)), ("generic", (GENERIC["features"], GENERIC["parameters"]))):
        c = cache.setdefault(label, {})
        bounds[label] = {}
        for x in ("1/40", "1/200", "1/1000"):
            e = first_order_error(features, parameters, x, "243/4000", cache=c)
            bounds[label][x] = dict(double_fraction=_f(e["double_fraction"]), pair_error=_f(e["pair_error_probability"]), first_order=_f(e["first_order_bounds"][1]),
                                    remainder=_f(e["remainder"]), total_upper_bound=_f(e["total_upper_bound"]),
                                    detail={k: _d(v) for k, v in e["detail"].items()})
    need = {label: required_double_fraction(fp[0], fp[1], "1/100") for label, fp in (("xor_0_32", ((0, 32), XOR_CHECKPOINT)),)}
    smap = source_map()
    record = dict(schema="native-cluster-noise-audit-v1", author="Monty", status="FIRST_ORDER_CHANNEL_NO_DEVICE",
                  tests=dict(run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 2)),
                  lemma_n1=dict(holds=m["holds"], rows={l: dict(success=_f(r["success_probability"]), register_paulis={str(c): v for c, v in r["register_paulis"].items()}) for l, r in m["rows"].items()}),
                  lemma_n2=reduction_lemma(),
                  xor_response=dict(never_flipping=xr["never_flipping"], examples={str(k): dict(label=v["label"], clean=_d(v["clean"]), flips=v["flips"], binary=v["binary"]) for k, v in xr["examples"].items()}),
                  generic_response=dict(features=GENERIC["features"], parameters=GENERIC["parameters"], clean=_d(gen["clean"]), clean_equals_circuit=gen["clean_equals_circuit"],
                                        discarded_invisible=gen["discarded_invisible"], rows=generic_rows),
                  source_map=dict(exact={k: {l: sorted(s) for l, s in v.items() if l != "bell_pairs"} for k, v in smap["exact"].items()},
                                  bounded={k: dict(star_nodes=v["star_nodes"], support=v["support"], bell_pairs=v["bell_pairs"], patterns=len(v["patterns"])) for k, v in smap["bounded"].items()},
                                  bell_pairs=smap["bell_pairs"]),
                  theorem_n=bounds,
                  x_for_one_percent={k: dict(x=str(v["x"]), x_float=_f(v["x"]), double_fraction=_f(v["double_fraction"]), bound=_f(v["total_upper_bound"])) for k, v in need.items()},
                  controls=controls(),
                  grades=dict(empty=noise_grade({})),
                  plan=noise_plan(),
                  disclaimers=["no device; every number is an exact consequence of declared inputs",
                               "first order in the per-pair error; the remainder is the exact two-or-more-errors probability",
                               "3-star and 5-star contributions are worst-pattern bounds, not exact responses",
                               "dark counts, distinguishability, correlated loss and the 810 nm rate are outside this channel",
                               "no witness is qualified; the grade only compares a recorded error rate with the stated bound"])
    (out/'qualification.json').write_text(json.dumps(record, indent=1, default=str))
    (out/'test_results.txt').write_text(stream.getvalue())
    if not result.wasSuccessful():
        print(stream.getvalue())
        raise SystemExit(1)
    print(json.dumps(dict(tests=record["tests"], lemmas=(m["holds"], record["lemma_n2"]["holds"]), never_flipping=xr["never_flipping"],
                          bounds={k: {x: v["total_upper_bound"] for x, v in b.items()} for k, b in bounds.items()},
                          need=record["x_for_one_percent"], generic_clean=record["generic_response"]["clean"]), indent=1))


if __name__ == "__main__":
    main()
