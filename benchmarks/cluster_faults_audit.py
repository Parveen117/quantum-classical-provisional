"""Cluster faults audit: S1 storage during growth, switches, P1 double-pair one-survivor, herald counting, 13-node ledger, grade."""
import io
import json
from fractions import Fraction
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phase_seam_foundation.cluster_faults import (
    acceptance_with_switches, allowed_x, assembly_storage, cluster_fault_ledger, double_pair_survivors, fault_grade, fault_plan,
    fused_one_survivor_witness, ledger_table, multi_pair_fused_fraction, number_resolving_herald, star_growth_with_storage, switch_buffer,
)


def _f(v):
    return None if v is None else f"{float(v):.6g}"


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern='test_phase_seam_cluster_faults.py')
    stream = io.StringIO(); start = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    elapsed = time.perf_counter()-start
    out = ROOT/'phase_seam_foundation/faults'
    out.mkdir(exist_ok=True)
    storage = {f"size={n},m={m}": _f(star_growth_with_storage(n, m)["survival_factor"]) for n in (4, 5, 8) for m in ("999/1000", "99/100", "9/10")}
    assembly = {m: dict(merge_path=_f(assembly_storage(m)["merge_success_path_survival"]), candidate=_f(assembly_storage(m)["candidate_success_with_storage"])) for m in ("999/1000", "99/100", "9/10")}
    switches = {f"k_switch={a},k_buffer={b}": _f(switch_buffer(a, b)["bounds"][0]) for a, b in ((0, 0), (1, 1), (1, 2), (2, 4), (4, 4))}
    composed = {k: tuple(_f(v) for v in acceptance_with_switches("99/100", "9/10", a, b)["acceptance_bounds"]) for k, (a, b) in (("1,2", (1, 2)), ("4,4", (4, 4)))}
    p1 = fused_one_survivor_witness("243/4000")
    mp = {eta: dict(one_survivor_each=_f(double_pair_survivors(eta)["p_one_survivor_each"]), wrong_fraction_x_1_over_40=_f(multi_pair_fused_fraction("1/40", eta)["wrong_fraction"]))
          for eta in ("243/4000", "1/2", "9/10")}
    herald = {eh: _f(number_resolving_herald("1/40", eh)["double_pair_fraction_given_one_click"]) for eh in ("1/2", "9/10", "99/100", "1")}
    ax = allowed_x("9/10", 13, "243/4000", "9/10")
    record = dict(schema="native-cluster-faults-audit-v1", author="Monty", status="DECLARED_FAULT_LEDGER_NO_DEVICE",
                  tests=dict(run=result.testsRun, failures=len(result.failures), errors=len(result.errors), seconds=round(elapsed, 2)),
                  plan=fault_plan(), star_growth_survival_factor=storage, assembly=assembly, switch_buffer_multiplier_lower=switches, acceptance_with_switches=composed,
                  theorem_p1=dict(mixture={str(k): str(v) for k, v in double_pair_survivors("243/4000")["mixture"].items()},
                                  zz_correlation="2/3", fused_corrected_xxx=p1["mixture_corrected_xxx"].display(6)["decimal"],
                                  positive_control=p1["positive_control_bell_pair_xxx"].display(6)["decimal"], every_success_half=p1["every_success_half"]),
                  multi_pair=mp, number_resolving_herald_x_1_over_40=herald,
                  allowed_x=dict(threshold=tuple(_f(v) for v in ax["x_bounds"]), nr_herald_0_9=tuple(_f(v) for v in ax["with_number_resolving_herald"]["x_bounds"])),
                  ledger=[dict(r, wrong_fraction=_f(r["wrong_fraction"]), witness=_f(r["witness"]), combined=_f(r["combined"])) for r in ledger_table()],
                  grades=dict(empty=fault_grade({})),
                  disclaimers=["no device; every number is an exact consequence of declared inputs",
                               "withdrawn: the v0.24 single-site 'one survivor is right' statement does not extend to a fused register",
                               "finished-star waiting, correlated loss and the 810 nm source rate are open"])
    (out/'qualification.json').write_text(json.dumps(record, indent=1, default=str))
    (out/'test_results.txt').write_text(stream.getvalue())
    print(json.dumps(dict(tests=record["tests"], p1=record["theorem_p1"]["fused_corrected_xxx"], ledger=[(r["x"], r["herald"], r["combined"]) for r in record["ledger"]],
                          allowed_x=record["allowed_x"]), indent=1))


if __name__ == "__main__":
    main()
