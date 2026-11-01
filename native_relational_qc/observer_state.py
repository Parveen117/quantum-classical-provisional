"""Joint contrast/phase tracking through a declared qubit source channel.

The radius is transverse Bloch contrast, not physical distance. Source motion
is a rotation followed by a convex mixture with an equatorial preparation.
Observer changes transport the complete affine update. No mechanical force
is inserted into a qubit gate or a measurement likelihood.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import product
import json
from pathlib import Path

import numpy as np

from .certify import flat_field
from .delta_ogmt import digest
from .observer_tracking import AXES, GRID, GUESSES, Planner as PhasePlanner, _argmax, seal

RADII = (Q(0), Q(1, 4), Q(1, 2), Q(3, 4), Q(1))
DEFAULT_POLICY = Path(__file__).parent / "calculator_examples/moving_observer_state_policy.json"


@dataclass(frozen=True)
class Model:
    kind: str = "driven"
    rounds: int = 6

    def __post_init__(self):
        if self.kind not in ("driven", "constant_radius", "legacy_phase"):
            raise ValueError("unknown source model")
        if type(self.rounds) is not int or not 1 <= self.rounds <= 6:
            raise ValueError("one to six fresh probes required")

    @property
    def hypotheses(self):
        values = (-8, 8) if self.kind == "driven" else (("1",) if self.kind == "legacy_phase" else tuple(map(str, RADII[1:])))
        return tuple(product(GUESSES, (-1, 0, 1), values))

    @property
    def guesses(self):
        return (((0, Q(0)),) if self.kind != "legacy_phase" else ()) + tuple(
            (angle, radius) for radius in (RADII[1:] if self.kind != "legacy_phase" else (Q(1),)) for angle in GUESSES)

    def record(self):
        return dict(kind=self.kind, rounds=self.rounds, grid=GRID, axes=list(AXES),
                    hypotheses=[list(h) for h in self.hypotheses], prior="uniform",
                    guesses=[dict(phase=a, radius=str(r)) for a,r in self.guesses],
                    retention="3/4" if self.kind == "driven" else "1",
                    target_time=self.rounds, radius_meaning="transverse Bloch contrast",
                    loss="squared complex coherence prediction error divided by four",
                    source="rotation then mixture with a declared equatorial preparation" if self.kind == "driven" else "constant contrast with linear phase drift")


class Planner(PhasePlanner):
    """Reuse the bounded Bellman/schedule search, with a joint-state objective."""
    def __init__(self, model=Model()):
        self.model = model
        h = model.hypotheses
        angles = np.array([x[0] for x in h])*2*np.pi/GRID
        rotations = np.exp(1j*np.array([x[1] for x in h])*2*np.pi/GRID)
        if model.kind == "driven":
            state = np.exp(1j*angles)
            drive = np.exp(1j*(angles+np.array([x[2] for x in h])*2*np.pi/GRID))
        else:
            state = np.array([float(Q(x[2])) for x in h])*np.exp(1j*angles)
        states = [state]
        for _ in range(model.rounds):
            state = rotations*state
            if model.kind == "driven":
                state = 0.75*state+0.25*drive
            states.append(state)
        states = np.array(states)
        self.prior = np.full(len(h), 1/len(h))
        self.p0 = (1+(states[:-1, None, :]*np.exp(-1j*np.array(AXES)[None, :, None]*2*np.pi/GRID)).real)/2
        guesses = np.array([float(r)*np.exp(1j*a*2*np.pi/GRID) for a,r in model.guesses])
        self.utility = 1-np.abs(states[-1, :, None]-guesses[None, :])**2/2
        self.leaf_evaluations = 0

    def leaf(self, weights):
        self.leaf_evaluations += 1
        scores = weights@self.utility
        index = _argmax(scores)
        angle, radius = self.model.guesses[index]
        return float(scores[index]), dict(phase=angle, radius=str(radius))

    def freeze(self, name, tree, planning):
        return seal(dict(schema="nrqc-observer-state-policy-v1", name=name, model=self.model.record(),
                         tree=tree, planning=planning, selection_inputs="declared prior only; no evaluation trajectories"))

    def redecode(self, phase_policy):
        """Keep the old policy's measurement tree; fit only the joint decoder."""
        from .observer_tracking import validate_policy as validate_phase
        validate_phase(phase_policy)
        if phase_policy["model"]["rounds"] != self.model.rounds:
            raise ValueError("record budgets must match")
        def visit(node, step, weights):
            if step == self.model.rounds:
                return self.leaf(weights)
            axis = node["axis"]
            p0 = self.p0[step, AXES.index(axis)]
            u0, zero = visit(node["zero"], step+1, weights*p0)
            u1, one = visit(node["one"], step+1, weights*(1-p0))
            return u0+u1, dict(axis=axis, zero=zero, one=one)
        utility, tree = visit(phase_policy["tree"], 0, self.prior)
        return self.freeze("phase_axes_joint_decoder", tree, dict(numerical_expected_loss=(1-utility)/2,
                           axes_source=phase_policy["fingerprint"], angle_search=False))


def legacy_policy(phase_policy):
    from .observer_tracking import validate_policy as validate_phase
    original = validate_phase(phase_policy)
    def convert(node):
        if "estimate" in node:
            return dict(phase=node["estimate"], radius="1")
        return dict(axis=node["axis"], zero=convert(node["zero"]), one=convert(node["one"]))
    return Planner(Model("legacy_phase", original.rounds)).freeze("legacy_phase", convert(phase_policy["tree"]),
                   dict(source_policy=phase_policy["fingerprint"], calibration="unchanged unit-radius decoder"))


def no_record_policy(rounds=6):
    def tree(t):
        return dict(phase=0, radius="0") if t == rounds else dict(axis=0, zero=tree(t+1), one=tree(t+1))
    return Planner(Model(rounds=rounds)).freeze("no_records", tree(0), dict(decoder="prior mean zero; outcomes ignored"))


def validate_policy(policy):
    if not isinstance(policy, dict) or policy.get("schema") != "nrqc-observer-state-policy-v1":
        raise ValueError("invalid joint-observer policy schema")
    if policy.get("fingerprint") != digest({k:v for k,v in policy.items() if k != "fingerprint"}):
        raise ValueError("policy fingerprint mismatch")
    model = Model(policy["model"]["kind"], policy["model"]["rounds"])
    if policy["model"] != model.record():
        raise ValueError("unsupported joint-observer model")
    guesses = {(a, str(r)) for a,r in model.guesses}
    def visit(node, t):
        if t == model.rounds:
            if set(node) != {"phase", "radius"} or type(node["phase"]) is not int or (node["phase"], node["radius"]) not in guesses:
                raise ValueError("invalid joint-state estimate")
        else:
            if set(node) != {"axis", "zero", "one"} or type(node["axis"]) is not int or node["axis"] not in AXES:
                raise ValueError("invalid measurement node")
            visit(node["zero"], t+1); visit(node["one"], t+1)
    visit(policy["tree"], 0)
    return model


def source_mixtures(start, velocity, offset, *, retention=Q(3, 4), rounds=6):
    """Exact convex preparations for rho' = l U rho U† + (1-l) rho_drive."""
    if any(type(x) is not int for x in (start, velocity, offset, rounds)) or not 1 <= rounds <= 6:
        raise ValueError("integer phase settings and 1..6 rounds required")
    if type(retention) not in (int, Q) or not 0 <= retention <= 1 or Q(retention).denominator > 16:
        raise ValueError("retention must be exact in [0,1], denominator at most 16")
    current, rows = {start%GRID: Q(1)}, []
    for t in range(rounds+1):
        if sum(current.values()) != 1 or any(v < 0 for v in current.values()):
            raise ArithmeticError("source preparation is not convex")
        rows.append(tuple(sorted(current.items())))
        updated = {}
        for angle, weight in current.items():
            key = (angle+velocity)%GRID
            updated[key] = updated.get(key, Q(0))+retention*weight
        key = (start+offset)%GRID
        updated[key] = updated.get(key, Q(0))+1-retention
        current = {k:v for k,v in updated.items() if v}
    return tuple(rows)


def coherence(mixture):
    F = flat_field()
    return sum((F.root(2*a)*w for a,w in mixture), F())


def transport(q, source_rotation, displacement_in_old_axes, observer_delta):
    """Rotate the entire affine update into the next observer axes."""
    if any(type(a) is not int for a in (source_rotation, observer_delta)):
        raise ValueError("integer phase-grid angles required")
    F = flat_field()
    return F.root(-2*observer_delta)*(F.root(2*source_rotation)*q+displacement_in_old_axes)


def frame_acceleration(q, velocity, lab_acceleration, origin_acceleration, angle, omega, angular_acceleration):
    """Exact second-derivative identity; not a force law for a qubit radius."""
    if type(angle) is not int or any(type(x) not in (int, Q) for x in (omega, angular_acceleration)):
        raise ValueError("exact angular rates and integer angle required")
    F = flat_field(); i = F.imag()
    terms = dict(transformed_external=F.root(-2*angle)*(lab_acceleration-origin_acceleration),
                 coriolis=-2*i*omega*velocity, euler=-i*angular_acceleration*q,
                 centrifugal=omega*omega*q)
    return dict(terms, total=sum(terms.values(), F()))


def exact_evaluate(policy, mixtures, bank, *, flip=Q(0), keep_branches=False):
    model = validate_policy(policy)
    if len(mixtures) != model.rounds+1 or len(bank) != GRID:
        raise ValueError("one source preparation per round plus target, and 32 likelihoods required")
    if type(flip) not in (int, Q) or not 0 <= flip <= Q(1, 2):
        raise ValueError("exact readout flip in [0,1/2] required")
    for mixture in mixtures:
        if sum((w for _,w in mixture), Q(0)) != 1 or any(type(a) is not int or type(w) not in (int,Q) or w < 0 for a,w in mixture):
            raise ValueError("normalized positive exact preparation required")
    F = flat_field()
    target = coherence(mixtures[-1]); radius_squared = target*target.conjugate()
    table = [[sum((bank[(a-axis)%GRID]*w for a,w in mixture), F())*(1-2*flip)+flip for axis in AXES]
             for mixture in mixtures[:-1]]
    guesses = {}
    for angle, radius in model.guesses:
        estimate = F.root(2*angle)*radius
        residual = target-estimate
        guesses[(angle, str(radius))] = (residual*residual.conjugate()*Q(1, 4), (radius_squared-radius*radius)**2)
    error, radial_error, changes, norm = F(), F(), F(), F()
    branches = {}
    def visit(node, step, weight, record, previous):
        nonlocal error, radial_error, changes, norm
        if step == model.rounds:
            loss, radial = guesses[(node["phase"], node["radius"])]
            error += weight*loss; radial_error += weight*radial; norm += weight
            if keep_branches:
                branches[record] = weight
            return
        axis = node["axis"]
        if previous is not None and previous != axis:
            changes += weight
        p0 = table[step][AXES.index(axis)]
        visit(node["zero"], step+1, weight*p0, record+"0", axis)
        visit(node["one"], step+1, weight*(1-p0), record+"1", axis)
    visit(policy["tree"], 0, F(1), "", None)
    if norm != 1:
        raise ArithmeticError("record probabilities did not normalize exactly")
    return dict(error=error, squared_contrast_error=radial_error, axis_changes=changes,
                normalization=norm, target_radius_squared=radius_squared, branches=branches)


def read_records(policy, records, *, frame_step=0):
    model = validate_policy(policy)
    if type(records) is not str or len(records) > model.rounds or any(b not in "01" for b in records):
        raise ValueError("binary records within the probe budget required")
    if type(frame_step) is not int or not 0 <= frame_step < GRID:
        raise ValueError("common frame step must be in 0..31")
    node, history = policy["tree"], []
    for bit in records:
        axis = (node["axis"]+frame_step)%GRID
        history.append(dict(axis_degrees=axis*360/GRID, bit=int(bit)))
        node = node["zero" if bit == "0" else "one"]
    out = dict(schema="nrqc-observer-state-response-v1", status="complete" if len(records) == model.rounds else "next_measurement",
               policy_sha256=policy["fingerprint"], records=records, measurement_history=history,
               probes_remaining=model.rounds-len(records), target_time=model.rounds, frame_step=frame_step,
               radius_meaning="predicted transverse Bloch contrast, not distance or confidence",
               interpretation="records must use this policy's preceding axes and fresh source probes", hardware_job_id=None)
    if len(records) == model.rounds:
        radius = Q(node["radius"])
        out.update(predicted_radius=str(radius), predicted_phase_degrees=((node["phase"]+frame_step)%GRID)*360/GRID if radius else None)
    else:
        out["next_axis_degrees"] = ((node["axis"]+frame_step)%GRID)*360/GRID
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="nrqc observer-state", description=__doc__)
    parser.add_argument("--records", default="")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--frame-step", type=int, default=0)
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
