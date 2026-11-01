"""Record-controlled phase tracking with a bounded Bayesian planning model.

Each round consumes a fresh equatorial probe. Only past binary records reach
the controller; true source trajectories belong to the evaluator. Planning is
numerical, while frozen-policy risks use calculator-derived exact likelihoods.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
import json
from pathlib import Path
import time

import numpy as np

from .calculator import display
from .certify import exact_value, flat_field
from .delta_ogmt import digest
from .phase_interop import phase_operations

GRID = 32
AXES = (0, 4, 8, 12)  # 0, 45, 90, 135 degrees; opposite axes only relabel bits.
GUESSES = tuple(range(0, GRID, 2))
DEFAULT_POLICY = Path(__file__).parent / "calculator_examples/moving_observer_policy.json"


@dataclass(frozen=True)
class Model:
    rounds: int = 6

    def __post_init__(self):
        if type(self.rounds) is not int or not 1 <= self.rounds <= 6:
            raise ValueError("tracking supports 1..6 fresh probes")

    @property
    def hypotheses(self):
        return tuple(product(GUESSES, (-1, 0, 1)))

    def record(self):
        return dict(rounds=self.rounds, phase_grid=GRID, axes=list(AXES), guesses=list(GUESSES),
                    hypotheses=[list(h) for h in self.hypotheses], prior="uniform",
                    signal="phase(t)=initial+velocity*t modulo 32",
                    preparation="one fresh equatorial probe per round",
                    target_time=self.rounds, target="one-step-ahead source phase",
                    loss="(1-cos(actual_phase-estimate))/2")


def _argmax(values):
    # Stable floating proposal ranking. This is not an exact optimality proof.
    return int(np.argmax(np.round(values, 13)))


class Planner:
    def __init__(self, model=Model()):
        self.model = model
        h = np.array(model.hypotheses)
        self.prior = np.full(len(h), 1/len(h))
        phase = h[:, 0][None, :] + np.arange(model.rounds)[:, None]*h[:, 1][None, :]
        self.p0 = (1+np.cos((phase[:, None, :]-np.array(AXES)[None, :, None])*2*np.pi/GRID))/2
        future = h[:, 0] + model.rounds*h[:, 1]
        self.utility = np.cos((future[:, None]-np.array(GUESSES)[None, :])*2*np.pi/GRID)
        self.leaf_evaluations = 0

    def leaf(self, weights):
        self.leaf_evaluations += 1
        utilities = weights@self.utility
        index = _argmax(utilities)
        return float(utilities[index]), dict(estimate=GUESSES[index])

    def adaptive(self):
        """Full finite-horizon Bellman recursion; no hidden trajectory argument."""
        self.leaf_evaluations = 0
        started = time.perf_counter()
        def visit(weights, step):
            if step == self.model.rounds:
                return self.leaf(weights)
            options = []
            # Uniform phase prior and rotation-closed loss/guess sets allow the
            # first axis to be fixed at 0 for both adaptive and open-loop search.
            for index in ((0,) if step == 0 else range(len(AXES))):
                p0 = self.p0[step, index]
                u0, zero = visit(weights*p0, step+1)
                u1, one = visit(weights*(1-p0), step+1)
                options.append((u0+u1, dict(axis=AXES[index], zero=zero, one=one)))
            return options[_argmax([v[0] for v in options])]
        utility, tree = visit(self.prior, 0)
        return self.freeze("adaptive", tree, dict(planner="finite-horizon Bayesian Bellman recursion",
                           numerical_expected_loss=(1-utility)/2, leaf_evaluations=self.leaf_evaluations,
                           wall_seconds=time.perf_counter()-started))

    def schedule(self, axes, name="schedule"):
        if len(axes) != self.model.rounds or any(a not in AXES for a in axes):
            raise ValueError("one allowed axis per round required")
        def visit(weights, step):
            if step == self.model.rounds:
                return self.leaf(weights)
            p0 = self.p0[step, AXES.index(axes[step])]
            u0, zero = visit(weights*p0, step+1)
            u1, one = visit(weights*(1-p0), step+1)
            return u0+u1, dict(axis=axes[step], zero=zero, one=one)
        utility, tree = visit(self.prior, 0)
        return self.freeze(name, tree, dict(schedule=list(axes), numerical_expected_loss=(1-utility)/2))

    def open_loop_search(self):
        started = time.perf_counter()
        count = 2**self.model.rounds
        bits = np.array(list(product((0, 1), repeat=self.model.rounds)))
        records = []
        # Every open-loop schedule with first axis 0, with all record strings
        # and the same Bayesian terminal decoder. No evaluation cases used.
        for tail in product(AXES, repeat=self.model.rounds-1):
            axes = (0,)+tail
            weights = np.broadcast_to(self.prior, (count, len(self.prior))).copy()
            for step, axis in enumerate(axes):
                p0 = self.p0[step, AXES.index(axis)]
                weights *= np.where(bits[:, step, None] == 0, p0, 1-p0)
            utilities = weights@self.utility
            guesses = np.argmax(np.round(utilities, 13), axis=1)
            utility = float(utilities[np.arange(count), guesses].sum())
            records.append(dict(schedule=list(axes), numerical_expected_loss=(1-utility)/2))
        selected = _argmax([-r["numerical_expected_loss"] for r in records])
        policy = self.schedule(tuple(records[selected]["schedule"]), "searched_open_loop")
        policy["planning"].update(schedules=len(records), leaf_evaluations=count*len(records),
                                  wall_seconds=time.perf_counter()-started,
                                  optimality="numerical grid search; selected risk is replayed exactly")
        policy = seal({k:v for k,v in policy.items() if k != "fingerprint"})
        return policy, records

    def freeze(self, name, tree, planning):
        return seal(dict(schema="nrqc-observer-tracking-policy-v1", name=name,
                         model=self.model.record(), tree=tree, planning=planning,
                         selection_inputs="declared prior and likelihood model only; no evaluation trajectories"))


def seal(record):
    return dict(record, fingerprint=digest(record))


def validate_policy(policy):
    if not isinstance(policy, dict) or policy.get("schema") != "nrqc-observer-tracking-policy-v1":
        raise ValueError("invalid tracking policy schema")
    if policy.get("fingerprint") != digest({k:v for k,v in policy.items() if k != "fingerprint"}):
        raise ValueError("tracking policy fingerprint mismatch")
    model = Model(policy["model"]["rounds"])
    if policy["model"] != model.record():
        raise ValueError("unsupported tracking model")
    def visit(node, step):
        if step == model.rounds:
            if set(node) != {"estimate"} or type(node["estimate"]) is not int or node["estimate"] not in GUESSES:
                raise ValueError("invalid terminal estimate")
        else:
            if set(node) != {"axis", "zero", "one"} or type(node["axis"]) is not int or node["axis"] not in AXES:
                raise ValueError("invalid measurement decision")
            visit(node["zero"], step+1)
            visit(node["one"], step+1)
    visit(policy["tree"], 0)
    return model


def read_records(policy, records, *, frame_step=0):
    model = validate_policy(policy)
    if type(records) is not str or len(records) > model.rounds or any(b not in "01" for b in records):
        raise ValueError("records must be a binary string no longer than the probe budget")
    if type(frame_step) is not int or not 0 <= frame_step < GRID:
        raise ValueError("frame_step must be an integer in 0..31")
    node, history = policy["tree"], []
    for bit in records:
        axis = (node["axis"]+frame_step)%GRID
        history.append(dict(axis_step=axis, axis_degrees=axis*360/GRID, bit=int(bit)))
        node = node["zero" if bit == "0" else "one"]
    out = dict(schema="nrqc-observer-tracking-response-v1", policy_sha256=policy["fingerprint"],
               status="complete" if len(records) == model.rounds else "next_measurement",
               records=records, probes_used=len(records), probes_remaining=model.rounds-len(records),
               frame_step=frame_step, measurement_history=history, target_time=model.rounds,
               interpretation="records must come from this policy's stated preceding axes and fresh probes",
               hardware_job_id=None)
    if len(records) == model.rounds:
        estimate = (node["estimate"]+frame_step)%GRID
        out.update(predicted_phase_step=estimate, predicted_phase_degrees=estimate*360/GRID)
    else:
        axis = (node["axis"]+frame_step)%GRID
        out.update(next_axis_step=axis, next_axis_degrees=axis*360/GRID)
    return out


def _phase(ops, wire, steps):
    ops.extend([[n, list(q)] for n,q in phase_operations(Fraction(steps, GRID), (wire,))])


def calculator_request(phases, axes, record=None):
    if len(phases) != len(axes) or not 1 <= len(phases) <= 6:
        raise ValueError("one phase/axis per fresh probe, at most six")
    ops = []
    for wire, (phase, axis) in enumerate(zip(phases, axes)):
        if type(phase) is not int or type(axis) is not int:
            raise ValueError("integer phase-grid settings required")
        ops.append(["h", [wire]])
        _phase(ops, wire, phase)
        _phase(ops, wire, -axis)
        ops.append(["h", [wire]])
    if record is None:
        if len(phases) != 1:
            raise ValueError("calibration distribution requires one probe")
        query = dict(id="readout", kind="distribution", qubits=[0])
    else:
        if type(record) is not str or len(record) != len(phases) or any(b not in "01" for b in record):
            raise ValueError("one binary outcome per probe required")
        query = dict(id="path", kind="probability", outcomes={str(i):int(b) for i,b in enumerate(record)})
    return dict(schema="nrqc-calculator-v1", backend="cyclotomic_pow2", n_qubits=len(phases),
                operations=ops, queries=[query], decimal_places=12,
                limits=dict(max_work=1_000_000, max_branches=64, max_coefficient_bits=4096))


def branch_axes(policy, record):
    node, axes = policy["tree"], []
    for bit in record:
        axes.append(node["axis"])
        node = node["zero" if bit == "0" else "one"]
    return axes


def likelihoods(results):
    if len(results) != GRID or any(r.get("status") != "completed" for r in results):
        raise ValueError("all 32 completed calculator likelihoods required")
    values = tuple(exact_value(r["answers"][0]["probabilities"]["0"]["exact"]) for r in results)
    F = flat_field()
    for k, value in enumerate(values):
        if value != (2+F.root(2*k)+F.root(-2*k))*Fraction(1, 4):
            raise ArithmeticError("calculator likelihood differs from phase rule")
    return values


def exact_evaluate(policy, phases, bank, *, flip=Fraction(0), keep_branches=False):
    model = validate_policy(policy)
    if len(phases) != model.rounds+1 or any(type(p) is not int for p in phases):
        raise ValueError("source trajectory must include each probe and target time")
    if not isinstance(flip, (int, Fraction)) or isinstance(flip, bool) or not 0 <= flip <= Fraction(1, 2):
        raise ValueError("readout flip must be exact and between zero and one half")
    if len(bank) != GRID:
        raise ValueError("32 calibrated likelihoods required")
    F = flat_field()
    cosine = [(F.root(2*k)+F.root(-2*k))*Fraction(1, 2) for k in range(GRID)]
    error, hit, switches, norm = F(), F(), F(), F()
    branches = {}
    def visit(node, step, weight, record, previous):
        nonlocal error, hit, switches, norm
        if step == model.rounds:
            delta = (phases[-1]-node["estimate"])%GRID
            norm += weight
            error += weight*(1-cosine[delta])*Fraction(1, 2)
            if min(delta, GRID-delta) <= 4:
                hit += weight
            if keep_branches:
                branches[record] = weight
            return
        axis = node["axis"]
        if previous is not None and axis != previous:
            switches += weight
        p0 = bank[(phases[step]-axis)%GRID]*(1-2*flip)+flip
        visit(node["zero"], step+1, weight*p0, record+"0", axis)
        visit(node["one"], step+1, weight*(1-p0), record+"1", axis)
    visit(policy["tree"], 0, F(1), "", None)
    if norm != 1:
        raise ArithmeticError("record path probabilities are not normalized")
    return dict(error=error, within_45_degrees=hit, axis_changes=switches, normalization=norm, branches=branches)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="nrqc observer-track", description=__doc__)
    parser.add_argument("--records", default="", help="past measured bits in chronological order")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--frame-step", type=int, default=0, help="common coordinate-origin shift in 2*pi/32 units")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        result = read_records(json.loads(args.policy.read_text()), args.records, frame_step=args.frame_step)
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))
    content = json.dumps(result, sort_keys=True, indent=2)+"\n"
    if args.out:
        args.out.write_text(content)
    print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
