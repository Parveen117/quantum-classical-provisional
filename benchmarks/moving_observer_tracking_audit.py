"""Freeze a bounded moving-observer controller, then certify its tracking risk."""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from math import pi
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from native_relational_qc.calculator import run_calculation, display, real_sign
from native_relational_qc.certify import exact_value, flat_field
from native_relational_qc.delta_ogmt import digest
from native_relational_qc.observer_tracking import (
    AXES, GRID, Model, Planner, branch_axes, calculator_request, exact_evaluate, likelihoods,
)
from native_relational_qc.phase_interop import phase_name

PROTOCOL_PATH = ROOT / "benchmarks/protocols/moving_observer_tracking_v1.json"


def protocol():
    return dict(schema="nrqc-moving-observer-tracking-protocol-v1", model=Model().record(),
                actions="same four analyzer axes for every controller", probes_per_decision=6,
                planning="declared uniform phase/velocity prior only; no evaluation trajectories supplied",
                policies=["adaptive", "searched_open_loop", "fixed_x", "rotating_xy", "feedback_disabled"],
                open_loop_search="all 4^5 schedules after first axis 0, same terminal decoder",
                adaptive_search="full six-step Bellman tree, first axis 0 by prior symmetry",
                numerical_ranking="13 decimal places, first candidate wins ties; exact optimality not claimed",
                primary_criterion="at least 5 percent relative reduction in exact mean circular error versus searched_open_loop on model-grid and shifted-phase cases",
                cases={"model_grid": "16 even initial phase steps x velocities -1,0,1",
                       "shifted_phase": "16 odd initial phase steps x velocities -1,0,1; never used in planning",
                       "faster_drift": "16 odd initial steps x velocities -2,+2; outside planning model",
                       "reversing_drift": "16 odd initial steps x directions -1,+1; direction reverses after three probe intervals",
                       "readout_flip_5pct": "shifted-phase cases with independent bit flips of probability 1/20; controller unchanged",
                       "randomized_readout": "shifted-phase cases with flip probability 1/2; expected error must be exactly 1/2"},
                uncertainty="exact finite-population expectation under declared preparations/noise; no physical confidence interval",
                calibration="32 one-probe exact calculator distributions",
                branch_witnesses="adaptive and searched_open_loop, source phase starts 2 and 3 with velocity +1; records 000000,111111,010101,101010",
                hardware_validated=False, computational_speedup_claimed=False,
                archive="all likelihood requests/results, frozen trees, open-loop scores, per-trajectory scores, branch witnesses and hashes")


def evaluation_cases(rounds=6):
    rows = []
    for name, starts, velocities, flip in (
        ("model_grid", range(0, 32, 2), (-1, 0, 1), Fraction(0)),
        ("shifted_phase", range(1, 32, 2), (-1, 0, 1), Fraction(0)),
        ("faster_drift", range(1, 32, 2), (-2, 2), Fraction(0)),
        ("reversing_drift", range(1, 32, 2), (-1, 1), Fraction(0)),
        ("readout_flip_5pct", range(1, 32, 2), (-1, 0, 1), Fraction(1, 20)),
        ("randomized_readout", range(1, 32, 2), (-1, 0, 1), Fraction(1, 2))):
        for start in starts:
            for velocity in velocities:
                path = [start]
                for step in range(rounds):
                    increment = -velocity if name == "reversing_drift" and step >= 3 else velocity
                    path.append((path[-1]+increment)%GRID)
                rows.append(dict(id=f"{name}_{start:02d}_{velocity:+d}", family=name,
                                 phases=path, flip=str(flip)))
    return rows


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2, allow_nan=False)+"\n")


def reference(document, result):
    from qiskit import QuantumCircuit, __version__
    from qiskit.quantum_info import Statevector
    circuit = QuantumCircuit(document["n_qubits"])
    for name, wires in document["operations"]:
        if name == "h":
            circuit.h(*wires)
        else:
            turns, controlled = phase_name(name)
            if controlled:
                raise ValueError("unexpected controlled gate in independent-probe witness")
            circuit.p(2*pi*float(turns), *wires)
    probabilities = Statevector.from_instruction(circuit).probabilities()
    query, answer = document["queries"][0], result["answers"][0]
    if query["kind"] == "probability":
        index = sum(bit << int(wire) for wire, bit in query["outcomes"].items())
        error = abs(float(probabilities[index])-float(answer["value"]["decimal"]))
    else:
        error = max(abs(float(probabilities[int(bit)])-float(value["decimal"])) for bit,value in answer["probabilities"].items())
    return dict(passed=bool(error <= 2e-10), max_absolute_error=float(error), qiskit_version=__version__)


def audit(output, protocol_commit, *, compare=False, timeout=30):
    if type(protocol_commit) is not str or len(protocol_commit) != 40 or any(c not in "0123456789abcdef" for c in protocol_commit):
        raise ValueError("a full protocol commit SHA is required")
    plan = json.loads(PROTOCOL_PATH.read_text())
    if plan != protocol():
        raise ValueError("checked-in protocol differs from implementation")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for name in ("inputs", "results", "evaluations"):
        (output/name).mkdir()
    write(output/"protocol.json", plan)
    write(output/"status.json", dict(status="running", protocol_commit=protocol_commit))
    started = time.perf_counter()
    try:
        planner = Planner()
        adaptive = planner.adaptive()
        open_loop, searched = planner.open_loop_search()
        policies = dict(adaptive=adaptive, searched_open_loop=open_loop,
                        fixed_x=planner.schedule((0,)*6, "fixed_x"),
                        rotating_xy=planner.schedule((0, 8)*3, "rotating_xy"),
                        feedback_disabled=planner.schedule(tuple(branch_axes(adaptive, "000000")), "feedback_disabled"))
        write(output/"open_loop_search.json", searched)
        write(output/"frozen_policies.json", policies)
        frozen_bytes = (output/"frozen_policies.json").read_bytes()
        print("Policies frozen before evaluation; adaptive planning seconds", adaptive["planning"]["wall_seconds"], flush=True)
        bank_results, references = [], {}
        def run(label, request):
            write(output/"inputs"/(label+".json"), request)
            result = run_calculation(request, timeout_seconds=timeout)
            write(output/"results"/(label+".json"), result)
            if result["status"] != "completed":
                raise RuntimeError(label+": "+result["status"])
            if compare:
                references[label] = reference(request, result)
                if not references[label]["passed"]:
                    raise ArithmeticError("independent reference disagreement: "+label)
            return result
        for step in range(GRID):
            bank_results.append(run(f"likelihood_{step:02d}", calculator_request([step], [0])))
        bank = likelihoods(bank_results)
        F = flat_field()
        rows = evaluation_cases()
        write(output/"evaluation_cases.json", rows)
        scores, exact_scores = {}, {}
        for name, policy in policies.items():
            grouped, evaluated = {}, []
            for row in rows:
                result = exact_evaluate(policy, row["phases"], bank, flip=Fraction(row["flip"]))
                evaluated.append(dict(row, **{k:display(result[k]) for k in ("error", "within_45_degrees", "axis_changes", "normalization")}))
                grouped.setdefault(row["family"], []).append(result)
            scores[name], exact_scores[name] = {}, {}
            for family, results in grouped.items():
                means = {key:sum((r[key] for r in results), F())*Fraction(1, len(results))
                         for key in ("error", "within_45_degrees", "axis_changes")}
                exact_scores[name][family] = means
                scores[name][family] = dict(cases=len(results), **{k:display(v) for k,v in means.items()})
                print(name, family, "mean circular error", scores[name][family]["error"]["decimal"], flush=True)
            write(output/"evaluations"/(name+".json"), evaluated)
        # Independently compile selected adaptive record paths as ordinary
        # six-probe calculator circuits, with exactly that path's analyzer axes.
        witnesses = []
        for name in ("adaptive", "searched_open_loop"):
            policy = policies[name]
            for start in (2, 3):
                phases = [(start+t)%GRID for t in range(7)]
                paths = exact_evaluate(policy, phases, bank, keep_branches=True)["branches"]
                for record in ("000000", "111111", "010101", "101010"):
                    label = f"path_{name}_{start}_{record}"
                    result = run(label, calculator_request(phases[:-1], branch_axes(policy, record), record))
                    value = exact_value(result["answers"][0]["value"]["exact"])
                    if value != paths[record]:
                        raise ArithmeticError("factorized/circuit path mismatch: "+label)
                    witnesses.append(dict(case=label, exact_match=True, probability=display(value)))
        if (output/"frozen_policies.json").read_bytes() != frozen_bytes:
            raise AssertionError("policies changed during evaluation")
        controls = {name:values["randomized_readout"]["error"] == Fraction(1, 2) for name,values in exact_scores.items()}
        if not all(controls.values()):
            raise ArithmeticError("uninformative records produced spurious information")
        comparisons, criterion = {}, True
        for family in scores["adaptive"]:
            a = exact_scores["adaptive"][family]["error"]
            b = exact_scores["searched_open_loop"][family]["error"]
            comparisons[family] = dict(open_loop_minus_adaptive_error=display(b-a),
                                       adaptive_is_better=real_sign(b-a)>0,
                                       five_percent_relative_improvement=real_sign(F(Fraction(19, 20))*b-a)>=0)
            if family in ("model_grid", "shifted_phase"):
                criterion &= comparisons[family]["five_percent_relative_improvement"]
        sources = ("native_relational_qc/observer_tracking.py", "native_relational_qc/__main__.py",
                   "native_relational_qc/calculator.py", "native_relational_qc/phase_backend.py",
                   "native_relational_qc/cyclotomic_pow2.py", "native_relational_qc/phase_interop.py",
                   "native_relational_qc/certify.py", "benchmarks/moving_observer_tracking_audit.py",
                   "benchmarks/protocols/moving_observer_tracking_v1.json")
        report = dict(schema="nrqc-observer-tracking-audit-v1", status="completed", verification_passed=True,
                      primary_improvement_passed=bool(criterion), protocol_commit=protocol_commit,
                      protocol_sha256=digest(plan), frozen_policies_sha256=hashlib.sha256(frozen_bytes).hexdigest(),
                      scores=scores, comparisons=comparisons, randomized_readout_controls=controls,
                      branch_witnesses=witnesses, numeric_references=references,
                      exact_calculator_requests=GRID+len(witnesses), exact_trajectory_evaluations=len(rows)*len(policies),
                      records_per_trajectory=64, hardware_job_id=None, hardware_validated=False,
                      computational_advantage_established=False, physical_cost_advantage_established=False,
                      evidence_class="DECLARED_IDEAL_PROBE_MODEL_WITH_STATED_READOUT_STRESS",
                      no_heldout_trajectory_used_for_planning=True, python=platform.python_version(),
                      wall_seconds=time.perf_counter()-started,
                      source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
                      caveat="These finite-family expected risks do not establish material performance, global algorithmic optimality or broad generalization.")
        write(output/"summary.json", report)
        write(output/"status.json", dict(status="completed"))
        write(output/"manifest.sha256.json", {p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                                             for p in sorted(output.rglob("*.json"))})
        return report
    except Exception as error:
        write(output/"status.json", dict(status="incomplete", verification_passed=False, error=str(error)))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--protocol-commit", required=True)
    parser.add_argument("--compare-qiskit", action="store_true")
    args = parser.parse_args(argv)
    result = audit(args.out, args.protocol_commit, compare=args.compare_qiskit)
    print(json.dumps({k:result[k] for k in ("status", "verification_passed", "primary_improvement_passed", "wall_seconds")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
