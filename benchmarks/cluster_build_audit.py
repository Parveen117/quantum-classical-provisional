"""Cluster build audit: Lemma A, adaptive witnesses along outcome paths, tree from v0.30 merges, cost policies, online ledger, grade."""
import io
import json
from fractions import Fraction
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.cluster_build import (
    adaptation_lemma, adaptive_run, build_cost, build_plan, cluster_build_grade, feedforward_layers, ledger_table, tree_from_stars,
)
from phase_seam_foundation.cluster_compile import XOR_CHECKPOINT


def _s(v):
    return str(v) if isinstance(v, (Fraction, int)) else v


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_cluster_build.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/cluster_build'
    out.mkdir(exist_ok=True)
    runs = []
    cases = [((0, 0), XOR_CHECKPOINT), ((0, 32), XOR_CHECKPOINT), ((32, 0), XOR_CHECKPOINT), ((32, 32), XOR_CHECKPOINT),
             ((5, 17), (3, 41, 22, 9, 50)), ((61, 2), (7, 13, 29, 44, 58))]
    paths = [None, (1,)*9, (1, 0, 1, 1, 0, 1, 1, 0, 1), (0, 1, 1, 0, 1, 0, 1, 1, 1)]
    for feats, params in cases:
        for path in paths:
            r = adaptive_run(feats, params, path)
            runs.append(dict(features=list(feats), parameters=list(params), path=path, exact_equality=r["exact_equality"],
                             probability=r["pattern_probability"].display(12)["decimal"], angles_flipped=r["angles_flipped"],
                             outcomes_relabelled=r["outcomes_relabelled"], readout=r["readout"]))
    tree = {k: _s(v) for k, v in tree_from_stars().items()}
    cost = build_cost()
    record = dict(schema="native-cluster-build-audit-v1", author="Monty", status="DECLARED_BUILD_NO_DEVICE",
                  tests=dict(run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 2)),
                  plan=build_plan(), lemma_a_all_64=all(adaptation_lemma(k)["holds"] for k in range(64)), feedforward=feedforward_layers(),
                  adaptive_runs=runs, tree_from_stars=tree,
                  cost=dict(full_restart={k: _s(v) for k, v in cost["full_restart"].items() if k != "stars"},
                            stars={str(k): {kk: _s(vv) for kk, vv in v.items()} for k, v in cost["full_restart"]["stars"].items()},
                            spare_leaves={k: {kk: _s(vv) for kk, vv in v.items()} for k, v in cost["spare_leaves"].items()}),
                  ledger=[dict(r, acceptance=f"{float(r['acceptance']):.6g}") for r in ledger_table()],
                  grades=dict(empty=cluster_build_grade({})),
                  disclaimers=["no device; every number is an exact consequence of declared inputs",
                               "loss is counted as rejected runs (rate), never as fidelity",
                               "storage during star growth, switch/buffer loss, multi-pair, dark counts and visibility on the 13 nodes are open"])
    (out/'qualification.json').write_text(json.dumps(record, indent=1, default=str))
    (out/'test_results.txt').write_text(stream.getvalue())
    print(json.dumps(dict(tests=record["tests"], runs_exact=all(r["exact_equality"] for r in runs), runs=len(runs),
                          tree=tree["tree_graph_exact"], stages=record["feedforward"]["stages"],
                          full_restart=record["cost"]["full_restart"]["expected_bell_pairs_per_delivered_cluster"]), indent=1))


if __name__ == "__main__":
    main()
