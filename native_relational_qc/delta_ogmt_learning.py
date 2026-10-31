"""Bounded proposal search and exact readout scoring for Delta OGMT.

The proposal evaluator reuses the native NumPy gate algebra. Frozen models are
re-evaluated by the existing exact calculator. Labels never enter a circuit.
No electrical/thermal calibration or quantum advantage is inferred.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import combinations, product
from math import comb, pi
import random

import numpy as np

from .algebra import apply_local, controlled, gate
from .delta_ogmt import INPUT_STEPS, OUTER, INNER, BRIDGES, _mix, _phase, digest
from .phase_interop import phase_name

MODES = ("M1", "M2", "M3", "E_CA")
PROFILES = tuple(product((1, 2, 4), repeat=2))
PROJECTIONS = ((1, 1), (2, 2), (4, 2), (2, 4), (4, 4), (8, 2), (2, 8), (8, 8))
SHOTS = 64


@dataclass(frozen=True)
class Parameters:
    outer_scale: int = 1
    memory_scale: int = 1
    readout_A: int = 4
    readout_C: int = 2
    observer_step: int = 0

    def __post_init__(self):
        for name in ("outer_scale", "memory_scale"):
            if type(getattr(self, name)) is not int or getattr(self, name) not in (1, 2, 4):
                raise ValueError("coupling scales must be 1, 2 or 4")
        for name in ("readout_A", "readout_C"):
            if type(getattr(self, name)) is not int or getattr(self, name) not in (1, 2, 4, 8):
                raise ValueError("readout weights must be 1, 2, 4 or 8")
        if type(self.observer_step) is not int or not 0 <= self.observer_step < 16:
            raise ValueError("observer step must be in 0..15")


def _history(history):
    if type(history) is not str or not 4 <= len(history) <= 16 or any(t not in "AB" for t in history):
        raise ValueError("history must be a 4..16 character A/B string")
    return history


def event_operations(token, mode, params, *, commuting=False):
    if token not in INPUT_STEPS or mode not in (*MODES, "M0") or type(params) is not Parameters:
        raise ValueError("invalid event, mode or parameters")
    active = (3,) if mode == "M1" else (() if mode == "M0" else (3, 4, 5))
    ops = []
    _mix(ops, 1, INPUT_STEPS[token], commuting)
    _mix(ops, 0, 1, commuting)
    _mix(ops, 2, 2, commuting)
    for wire in active:
        _mix(ops, wire, {3: 2, 4: 1, 5: 1}[wire], commuting)
        _phase(ops, [wire], wire - 2)
    edges = [(name, a, b, w * params.outer_scale) for name, a, b, w in OUTER]
    edges += [(name, a, b, w * params.memory_scale) for name, a, b, w in BRIDGES if b in active]
    if mode in ("M3", "E_CA"):
        edges += [(name, a, b, w * params.memory_scale) for name, a, b, w in INNER]
    if mode == "E_CA":
        edges = [e for e in edges if e[0] != "CA"]
    for _, a, b, weight in edges:
        _phase(ops, [a, b], weight)
    return ops


def build_request(history, mode, params, *, variant="nominal"):
    history = _history(history)
    if variant not in ("nominal", "equal_inputs", "commuting_updates", "projection_off"):
        raise ValueError("unknown negative control")
    commuting = variant == "commuting_updates"
    ops = [["h", [q]] for q in (range(6) if commuting else (0,))]
    if mode != "M0":
        for token in history:
            ops.extend(event_operations("A" if variant == "equal_inputs" else token, mode, params, commuting=commuting))
    for token in ("hold", "R"):
        ops.extend(event_operations(token, mode, params, commuting=commuting))
    ops.append(["h", [6]])
    if variant != "projection_off":
        _phase(ops, [0, 6], params.readout_A)
        _phase(ops, [2, 6], params.readout_C)
    ops.append(["h", [6]])
    # Rx(observer angle) after the fixed projection.
    if params.observer_step:
        _mix(ops, 6, params.observer_step, False)
    request = dict(schema="nrqc-calculator-v1", backend="cyclotomic_pow2", n_qubits=7,
                   operations=ops, decimal_places=12,
                   limits=dict(max_work=100_000_000, max_branches=4096, max_coefficient_bits=4096),
                   queries=[dict(id="drain", kind="distribution", qubits=[6])])
    return request, dict(history=history, mode=mode, parameters=asdict(params), variant=variant,
                         reset_operation_indices=[], reset_wires=[], reset_environment_wires=[])


def group_key(history):
    return min(history, history[::-1].translate(str.maketrans("AB", "BA")))


def make_splits(seed=20261031):
    """12 events, six A/six B, endpoints A/B; keep reverse-complement twins together."""
    groups = {0: {}, 1: {}}
    for positions in combinations(range(1, 11), 5):
        history = ["B"] * 12
        history[0] = "A"
        for p in positions:
            history[p] = "A"
        history = "".join(history)
        changes = sum(a != b for a, b in zip(history, history[1:]))
        label = int(changes >= 7)
        row = dict(history=history, target=label, transitions=changes, group=group_key(history))
        groups[label].setdefault(row["group"], []).append(row)
    splits = {name: [] for name in ("train", "validation", "test", "reserve")}
    for label in (0, 1):
        remaining = list(groups[label].values())
        random.Random(seed + label).shuffle(remaining)
        for split, count in (("train", 16), ("validation", 16), ("test", 32)):
            chosen, unused, size = [], [], 0
            for group in remaining:
                if size + len(group) <= count:
                    chosen += group
                    size += len(group)
                else:
                    unused.append(group)
            if size != count:
                raise ValueError("cannot fill declared grouped split")
            splits[split] += chosen
            remaining = unused
        splits["reserve"] += [row for group in remaining for row in group]
    for rows in splits.values():
        rows.sort(key=lambda r: r["history"])
    return splits


@lru_cache(maxsize=256)
def _native_event(mode, outer_scale, memory_scale, token):
    ops = event_operations(token, mode, Parameters(outer_scale, memory_scale))
    matrices = []
    for name, wires in ops:
        if name == "h":
            matrix = gate("h")
        else:
            turns, is_controlled = phase_name(name)
            matrix = gate("p", 2 * pi * float(turns))
            if is_controlled:
                matrix = controlled(matrix)
        matrices.append((matrix, tuple(wires)))
    return tuple(matrices)


class ProposalEvaluator:
    """Native NumPy algebra with cached event-prefix states; not exact certification."""
    def __init__(self):
        self.cache = {}
        self.histories_evaluated = set()
        self.gate_applications = 0

    def populations(self, history, mode, profile):
        history = _history(history)
        if mode not in (*MODES, "M0") or tuple(profile) not in PROFILES:
            raise ValueError("invalid proposal mode/profile")
        self.histories_evaluated.add(history)
        prefix = ()
        key = (mode, tuple(profile), prefix)
        if key not in self.cache:
            state = np.zeros(64, dtype=complex)
            state[0] = 1
            self.cache[key] = apply_local(state, gate("h"), (0,))
        state = self.cache[key]
        for token in (() if mode == "M0" else tuple(history)) + ("hold", "R"):
            prefix += (token,)
            key = (mode, tuple(profile), prefix)
            if key not in self.cache:
                for matrix, wires in _native_event(mode, *profile, token):
                    state = apply_local(state, matrix, wires)
                    self.gate_applications += 1
                self.cache[key] = state
            state = self.cache[key]
        norm = float(np.vdot(state, state).real)
        if not np.isfinite(norm) or abs(norm - 1) > 1e-9:
            raise ArithmeticError("proposal evolution failed normalization")
        index = np.arange(64)
        labels = ((index & 1) << 1) | ((index >> 2) & 1)
        return np.bincount(labels, weights=np.abs(state) ** 2, minlength=4)

    def probabilities(self, histories, mode, params):
        populations = np.array([self.populations(h, mode, (params.outer_scale, params.memory_scale)) for h in histories])
        phases = np.array([params.readout_A * a + params.readout_C * c + params.observer_step
                           for a, c in product((0, 1), repeat=2)]) * (2 * pi / 16)
        values = (1 - populations @ np.cos(phases)) / 2
        if not np.isfinite(values).all() or values.min() < -1e-9 or values.max() > 1 + 1e-9:
            raise ArithmeticError("invalid proposal probabilities")
        return np.clip(values, 0, 1)


def decision_scores(probabilities, labels, shots=SHOTS):
    """Expected class-balanced accuracy for every K>=cut and its complement."""
    p = np.asarray(probabilities, dtype=float)
    if p.ndim == 1:
        p = p[None, :]
    labels = np.asarray(labels)
    if type(shots) is not int or not 1 <= shots <= 256 or p.shape[1] != len(labels):
        raise ValueError("invalid shots or dataset shape")
    if set(labels.tolist()) != {0, 1} or not np.isfinite(p).all() or np.any((p < 0) | (p > 1)):
        raise ValueError("binary classes and probabilities in [0,1] required")
    mass = np.stack([float(comb(shots, k)) * p ** k * (1 - p) ** (shots - k) for k in range(shots + 1)], axis=-1)
    tail = np.concatenate((np.cumsum(mass[..., ::-1], axis=-1)[..., ::-1], np.zeros((*p.shape, 1))), axis=-1)
    tail[..., 0] = 1
    score = (tail[:, labels == 1].mean(axis=1) + 1 - tail[:, labels == 0].mean(axis=1)) / 2
    return np.stack((score, 1 - score), axis=1)


def freeze_model(mode, params, orientation, cutoff, training, validation, *, shots=SHOTS):
    if mode not in (*MODES, "M0") or type(params) is not Parameters:
        raise ValueError("invalid model")
    if type(orientation) is not int or orientation not in (1, -1):
        raise ValueError("orientation must be +1 or -1")
    if type(shots) is not int or not 1 <= shots <= 256 or type(cutoff) is not int or not 0 <= cutoff <= shots + 1:
        raise ValueError("invalid shot/count threshold")
    record = dict(schema="delta-ogmt-frozen-classifier-v1", mode=mode, parameters=asdict(params),
                  orientation=orientation, cutoff=cutoff, shots=shots,
                  training_sha256=digest(training), validation_sha256=digest(validation),
                  decision="positive if K>=cutoff" if orientation == 1 else "positive if K<cutoff")
    return dict(record, fingerprint=digest(record))


def check_frozen(model):
    record = {k: v for k, v in model.items() if k != "fingerprint"}
    if model.get("fingerprint") != digest(record):
        raise ValueError("frozen model fingerprint mismatch")
    if model.get("schema") != "delta-ogmt-frozen-classifier-v1" or model.get("mode") not in (*MODES, "M0"):
        raise ValueError("invalid frozen model schema or mode")
    if type(model.get("shots")) is not int or not 1 <= model["shots"] <= 256:
        raise ValueError("invalid frozen shot budget")
    if type(model.get("cutoff")) is not int or not 0 <= model["cutoff"] <= model["shots"] + 1:
        raise ValueError("invalid frozen count threshold")
    if type(model.get("orientation")) is not int or model["orientation"] not in (-1, 1):
        raise ValueError("invalid frozen orientation")
    return Parameters(**model["parameters"])


def fit(training, validation, mode):
    """Train on a fixed grid, shortlist four distinct dynamics, select on validation.

    The signature intentionally has no test-set argument. Every mode has the
    same 9 dynamics x 8 projections x 16 angles x 2 orientations x 66 cuts.
    """
    if mode not in MODES:
        raise ValueError("unknown trainable mode")
    train_groups = {r["group"] for r in training}
    if train_groups & {r["group"] for r in validation}:
        raise ValueError("training and validation share related histories")
    evaluator = ProposalEvaluator()
    candidates, winners = [], []
    histories = [r["history"] for r in training]
    labels = [r["target"] for r in training]
    for profile in PROFILES:
        params = [Parameters(*profile, *projection, angle) for projection in PROJECTIONS for angle in range(16)]
        scores = decision_scores([evaluator.probabilities(histories, mode, p) for p in params], labels)
        profile_rows = []
        for index, param in enumerate(params):
            # Round only for stable numerical ranking. Exact final evaluation
            # does not use these rounded scores as a certificate.
            flat = int(np.argmax(np.round(scores[index], 12)))
            direction, cut = np.unravel_index(flat, scores[index].shape)
            row = dict(parameters=asdict(param), orientation=1 if direction == 0 else -1,
                       cutoff=int(cut), training_score=float(scores[index, direction, cut]))
            profile_rows.append(row)
        best = max(range(len(profile_rows)), key=lambda i: round(profile_rows[i]["training_score"], 12))
        winners.append(profile_rows[best])
        candidates += profile_rows
    shortlist = sorted(winners, key=lambda r: -round(r["training_score"], 12))[:4]
    for row in shortlist:
        probabilities = evaluator.probabilities([r["history"] for r in validation], mode, Parameters(**row["parameters"]))
        scores = decision_scores(probabilities, [r["target"] for r in validation])
        row["validation_score"] = float(scores[0, 0 if row["orientation"] == 1 else 1, row["cutoff"]])
    selected = max(shortlist, key=lambda r: (round(r["validation_score"], 12), round(r["training_score"], 12)))
    frozen = freeze_model(mode, Parameters(**selected["parameters"]), selected["orientation"], selected["cutoff"], training, validation)
    return dict(model=frozen, candidates=candidates, shortlist=shortlist,
                selected_training_score=selected["training_score"], selected_validation_score=selected["validation_score"],
                proposal_engine="native NumPy gate algebra; exact final replay required",
                histories_evaluated=sorted(evaluator.histories_evaluated), native_gate_applications=evaluator.gate_applications)


def binomial_tail(probability, shots, cutoff):
    """Exact rational Pr(K>=cutoff), using integer binomial terms, no samples."""
    p = Fraction(probability)
    if not 0 <= p <= 1 or type(shots) is not int or not 1 <= shots <= 256 or type(cutoff) is not int or not 0 <= cutoff <= shots + 1:
        raise ValueError("invalid probability or shot/count bound")
    if cutoff == 0:
        return Fraction(1)
    if cutoff > shots or p == 0:
        return Fraction(0)
    if p == 1:
        return Fraction(1)
    numerator, denominator = p.numerator, p.denominator
    other = denominator - numerator
    term = other ** shots
    total = 0
    for k in range(shots + 1):
        if k >= cutoff:
            total += term
        if k < shots:
            term = term * (shots - k) * numerator // ((k + 1) * other)
    return Fraction(total, denominator ** shots)


def success_bounds(probability_display, target, model):
    check_frozen(model)
    if type(target) is not int or target not in (0, 1):
        raise ValueError("binary target required")
    enclosure = probability_display["decimal_enclosure"]
    lo = max(Fraction(0), Fraction(enclosure["lower"]))
    hi = min(Fraction(1), Fraction(enclosure["upper"]))
    if lo > hi:
        raise ValueError("invalid probability enclosure")
    a = binomial_tail(lo, model["shots"], model["cutoff"])
    b = binomial_tail(hi, model["shots"], model["cutoff"])
    if model["orientation"] == -1:
        a, b = 1 - b, 1 - a
    return (a, b) if target else (1 - b, 1 - a)


def rounded_bounds(lo, hi, places=12):
    if lo > hi:
        raise ValueError("interval out of order")
    scale = 10 ** places
    low = lo.numerator * scale // lo.denominator
    high = -((-hi.numerator * scale) // hi.denominator)
    def fmt(value):
        sign = "-" if value < 0 else ""
        value = abs(value)
        return f"{sign}{value // scale}.{value % scale:0{places}d}"
    return dict(lower=fmt(low), upper=fmt(high), kind="exact propagated arithmetic bounds; not a sampling confidence interval")
