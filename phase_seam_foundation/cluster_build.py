"""Building and running the classifier cluster on the route (v0.31).

v0.29 compiled the pinned classifier to a 13-photon tree cluster read by ten
measurements with active Pauli corrections. This module settles three things
the route needs and v0.29 left open, each exactly:

* the hardware form of the corrections (Lemma A): no rail switch, only the sign
  of the next measurement angle (one heater trim) and a classical relabel of
  the outcome, witnessed end to end with a tracked Pauli frame;
* the cluster from stars: seven corrected type-I merges, with the Kraus rows
  v0.30 derived in the Fock engine, produce exactly the 13-node tree graph
  state (sign-vector check at every merge) with the declared probabilities;
* the cost of that build under two declared policies (v0.30 full restart,
  v0.27 spare leaves) and the online loss ledger: feedforward depth, every
  required click, storage and detector tables.

No device, no measured number. Loss here is counted as missing clicks that
reject the run (Theorem L2), never as a fidelity.
"""
from fractions import Fraction

from native_relational_qc.cyclotomic_pow2 import field_of_order
ZERO = field_of_order(64)()
ONE = field_of_order(64)(1)
ZETA = field_of_order(64).root()

from .cluster_compile import (
    DISCARDED, EDGES, FLOW, H2, NODES, ORDER, READOUT, SQRT2, XOR_CHECKPOINT, _State, _correct, _mm, _touch,
    circuit_probability, cluster_resources, neighbours, pattern, PX, PZ,
)
from .model import ResourceLimit, integer, rational
from .optical_refresh import fusion_merge_certificate
from .tree_build import star

GRADES = ("BUILD_DECLARED", "STARS_RECORDED", "TREE_RECORDED", "ADAPTIVE_RUN_RECORDED")


# ------------------------------------------------------------------ Lemma A: adaptation

def _ket(s, a):
    return ((H2,), ((H2 if s == 0 else -H2) * ZETA ** (a % 64),))


def _proj(v):
    return tuple(tuple(v[i][0] * v[j][0].conjugate() for j in range(2)) for i in range(2))


def adaptation_lemma(a):
    """Lemma A: X^x Z^z |s_a><s_a| Z^z X^x = |s'_{a'}><s'_{a'}| with s' = s xor z and
    a' = (-1)^x a. So a byproduct X^x Z^z before a measurement in B(a) is absorbed by
    measuring in B((-1)^x a) and reading the outcome xor z. Exact 2x2 for all s, x, z."""
    a = integer(a, "angle") % 64
    ok = True
    for s in (0, 1):
        for x in (0, 1):
            for z in (0, 1):
                p = _proj(_ket(s, a))
                for g in ((PZ,) if z else ()) + ((PX,) if x else ()):
                    p = _mm(_mm(g, p), g)
                target = _proj(_ket(s ^ z, (-a) % 64 if x else a))
                ok = ok and all(p[i][j] == target[i][j] for i in range(2) for j in range(2))
    return dict(angle=a, holds=ok, heater_rule="before = (32 - a') mod 64 with a' = (-1)^x a; outcome xor z", rail_switch_needed=False)


def feedforward_layers():
    """Measurement i can only be set once every measurement that writes to its frame is
    read: its flow predecessor (X) and every node whose successor neighbours i (Z)."""
    writers = {i: set() for i in ORDER + (READOUT,)}
    for p in ORDER:
        f = FLOW[p]
        if f in writers:
            writers[f].add(p)
        for k in neighbours(f):
            if k != p and k in writers:
                writers[k].add(p)
    layer = {}
    for i in ORDER + (READOUT,):
        layer[i] = 0 if not writers[i] else 1 + max(layer[p] for p in writers[i])
    depth = max(layer.values()) + 1
    return dict(layer=layer, writers={i: tuple(sorted(w)) for i, w in writers.items()}, stages=depth,
                parallel_first_layer=tuple(i for i in ORDER if layer[i] == 0))


def _equal_up_to_phase(a, b):
    """Exact equality of two branch states up to one global phase on the native grid
    (a branch's global phase is unobservable: the outcome is classical)."""
    if a.live != b.live or set(a.amps) != set(b.amps):
        return False, None
    if not a.amps:
        return True, ONE
    key = next(iter(a.amps))
    r = a.amps[key] * b.amps[key].inverse()
    steps = next((k for k in range(64) if r == ZETA ** k or r == -ZETA ** k), None)
    if steps is None:
        return False, None
    return all(a.amps[k] == r * b.amps[k] for k in a.amps), r


def adaptive_run(features, parameters, path=None):
    """Run the pattern with a tracked Pauli frame instead of active corrections, side by
    side with the v0.29 corrected run. At every measurement and for both raw outcomes the
    frame-corrected physical branch must equal the ideal corrected branch exactly, up to a
    global phase on the native grid (Paulis anticommute, the branch is classical); the
    readout at the adapted angle with the relabelled outcome gives P(logical 1). `path`
    (raw outcomes, one per J measurement) chooses the branch followed so that non-trivial
    frames and flipped angles are exercised; both outcomes are verified at every step."""
    if path is not None and (len(path) != len(ORDER) or any(b not in (0, 1) for b in path)):
        raise ValueError("path needs one raw outcome per J measurement")
    spec = pattern(features, parameters)
    ideal = _State()
    frame = {}
    trace = []

    def allocate(state, *nodes):
        before = set(state.live)
        _touch(state, *nodes)
        for w in state.live:
            if w not in before:
                frame.setdefault(w, [0, 0])
                for v in neighbours(w):
                    if v in before and frame.get(v, [0, 0])[0]:
                        frame[w][1] ^= 1          # CZ X_v = X_v Z_w CZ (Lemma G2)

    def physical_from(state):
        p = _State()
        p.live, p.dead, p.amps = list(state.live), set(state.dead), dict(state.amps)
        for v in p.live:
            x, z = frame.get(v, [0, 0])
            if z:
                p.z(v)
            if x:
                p.x(v)
        return p

    for idx, node in enumerate(ORDER):
        c = spec["corrections"][node]
        allocate(ideal, node, c["x"], *c["z"])
        x_i, z_i = frame.get(node, [0, 0])
        nominal = spec["measurement_angles"][node]
        adapted = (-nominal) % 64 if x_i else nominal
        phys = physical_from(ideal)
        raw0, raw1 = phys.measure(node, adapted)
        i0, i1 = ideal.measure(node, nominal)
        _correct(i1, spec, node, "flow")
        if not i0.equals(i1):
            raise ArithmeticError("ideal branches differ: v0.29 witness broken")
        ok = True
        for raw_s, branch in ((0, raw0), (1, raw1)):
            s = raw_s ^ z_i
            trial = {k: list(v) for k, v in frame.items() if k != node}
            trial[c["x"]][0] ^= s
            for k in c["z"]:
                trial[k][1] ^= s
            fixed = _State()
            fixed.live, fixed.dead, fixed.amps = list(branch.live), set(branch.dead), dict(branch.amps)
            for v in fixed.live:
                xx, zz = trial[v]
                if zz:
                    fixed.z(v)
                if xx:
                    fixed.x(v)
            same, _ = _equal_up_to_phase(fixed, i0)
            ok = ok and same and branch.norm2() == H2 * H2
            if raw_s == (0 if path is None else path[idx]):
                next_frame = trial
        trace.append(dict(node=node, nominal_angle=nominal, adapted_angle=adapted, frame=(x_i, z_i), both_raw_outcomes_match_ideal=ok))
        if not ok:
            return dict(witness=False, failed_at=node, trace=trace)
        # continue along the chosen raw outcome (both are verified equal after frame correction)
        frame = next_frame
        ideal = i0
        ideal.amps = {k: v * SQRT2 for k, v in ideal.amps.items()}
    allocate(ideal, READOUT)
    x_r, z_r = frame.get(READOUT, [0, 0])
    nominal = spec["measurement_angles"][READOUT]
    adapted = (-nominal) % 64 if x_r else nominal
    phys = physical_from(ideal)
    raw = phys.measure(READOUT, adapted)
    p_logical_one = raw[1 ^ z_r].norm2()
    circuit = circuit_probability(features, parameters)
    return dict(witness=True, exact_equality=p_logical_one == circuit, pattern_probability=p_logical_one, circuit_probability=circuit,
                readout=dict(nominal_angle=nominal, adapted_angle=adapted, frame=(x_r, z_r)), trace=trace, path=path,
                angles_flipped=sum(1 for t in trace if t["adapted_angle"] != t["nominal_angle"]) + (adapted != nominal),
                outcomes_relabelled=sum(t["frame"][1] for t in trace) + z_r,
                heater_feedforward_only=True, rail_switches=0)


# ------------------------------------------------------------------ the tree from stars

def _graph_signs(labels, edges):
    """Graph state on `labels` as {bits: +-1}; the common amplitude 2^(-n/2) is implicit."""
    idx = {l: i for i, l in enumerate(labels)}
    out = {}
    for bits in range(1 << len(labels)):
        parity = sum(((bits >> idx[a]) & 1) * ((bits >> idx[b]) & 1) for a, b in edges) % 2
        out[bits] = -1 if parity else 1
    return out


def _merge_signs(signs, labels, keep, drop):
    """Corrected type-I merge |0><00| + |1><11| on (keep, drop): keep the bits where both
    agree, remove `drop`. The scalar of the Kraus row is tracked outside."""
    ik, idr = labels.index(keep), labels.index(drop)
    new_labels = tuple(l for l in labels if l != drop)
    out = {}
    for bits, sgn in signs.items():
        if ((bits >> ik) & 1) != ((bits >> idr) & 1):
            continue
        new = sum((((bits >> labels.index(l)) & 1) << i) for i, l in enumerate(new_labels))
        if new in out:
            raise ArithmeticError("merge collision")
        out[new] = sgn
    return out, new_labels


def star_plan():
    """Rooted at hub 6: a child's star centre merges into a leaf of its parent's star.
    Internal nodes with one child are Bell pairs; node 10 is a 3-star; hub 6 a 5-star."""
    children = {6: (1, 3, 5, 7), 7: (10,), 10: (9, 11), 1: (0,), 3: (2,), 5: (4,), 9: (8,), 11: (12,)}
    stars = {}
    for centre, kids in children.items():
        leaves = []
        for k in kids:
            leaves.append(k if k not in children else ("leaf", centre, k))     # placeholder leaf for a child centre
        stars[centre] = dict(size=1 + len(leaves), leaves=tuple(leaves))
    merges = tuple((k, ("leaf", c, k)) for c, kids in children.items() for k in kids if k in children)
    return dict(children=children, stars=stars, merges=merges, fusions=len(merges),
                photons_before=sum(s["size"] for s in stars.values()), photons_after=NODES)


def tree_from_stars():
    """Exact: seven corrected merges on the declared stars produce the 13-node tree graph
    state, coefficient by coefficient (as signs), for every click branch of every merge
    (2^7 = 128 branches share the same sign vector; each merge row has |scalar|^2 = 1/2)."""
    plan = star_plan()
    rows = fusion_merge_certificate()
    for r in rows:
        k = r["corrected_kraus"]
        s = r["scalar"]
        if k != ((s, ZERO, ZERO, ZERO), (ZERO, ZERO, ZERO, s)) or s.norm2() != H2 * H2:
            raise ArithmeticError("v0.30 merge row is not the corrected graph merge")
    # assemble bottom-up so the largest intermediate state has 14 photons
    def star_state(centre):
        st = plan["stars"][centre]
        labels = (centre,) + st["leaves"]
        return _graph_signs(labels, tuple((centre, l) for l in st["leaves"])), labels
    def tensor(a, la, b, lb):
        out = {}
        for ka, sa in a.items():
            for kb, sb in b.items():
                out[ka | (kb << len(la))] = sa * sb
        return out, la + lb
    def attach(parent_state, parent_labels, child_centre):
        child_state, child_labels = subtree(child_centre)
        joint, labels = tensor(parent_state, parent_labels, child_state, child_labels)
        return _merge_signs(joint, labels, child_centre, ("leaf", parent_of[child_centre], child_centre))
    parent_of = {k: c for c, kids in plan["children"].items() for k in kids}
    def subtree(centre):
        state, labels = star_state(centre)
        for k in plan["children"][centre]:
            if k in plan["children"]:
                state, labels = attach(state, labels, k)
        return state, labels
    state, labels = subtree(6)
    expected = _graph_signs(labels, tuple((a, b) for a, b in EDGES))
    matches = set(labels) == set(range(NODES)) and len(state) == len(expected) and all(state[k] == expected[k] for k in expected)
    merges = plan["fusions"]
    # amplitude 2^(-N/2) per initial basis state, times a scalar of modulus 1/sqrt2 per merge, over the kept states
    p_sequence = Fraction(len(state), 1 << plan["photons_before"]) * Fraction(1, 2) ** merges
    return dict(photons_before=plan["photons_before"], merges=merges, photons_after=len(labels), labels=labels,
                tree_graph_exact=matches, kept_states=len(state), full_final_basis=len(state) == 1 << len(labels),
                probability_per_click_sequence=p_sequence, click_sequences=2 ** merges,
                success_probability=p_sequence * 2 ** merges,
                phase_corrections_per_merge=tuple(r["correction_phase_steps"] for r in rows))


# ------------------------------------------------------------------ build cost

def build_cost():
    """Two declared policies. Full restart (v0.30): prepare all eight stars, attempt the seven
    merges in sequence, discard everything on the first failure. Spare leaves (v0.27 law,
    v0.29 numbers): parents carry spare leaves and only the failed attachment is retried,
    conditional on success. Star costs are the v0.22 walk through v0.27's star()."""
    plan = star_plan()
    prep = Fraction(0)
    detail = {}
    for centre, st in plan["stars"].items():
        s = star(st["size"])
        c = s["expected_bell_pairs"] / s["p_reach"]
        detail[centre] = dict(size=st["size"], expected_bell_pairs=c)
        prep += c
    n = plan["fusions"]
    p = Fraction(1, 2) ** n
    attempts_per_candidate = sum(Fraction(1, 2) ** k for k in range(n))      # stops at the first failure
    full = dict(policy="FULL_RESTART_V030", stars=detail, bell_pairs_per_candidate=prep, success=p,
                expected_candidates=1 / p, expected_bell_pairs_per_delivered_cluster=prep / p,
                expected_merge_rounds_per_candidate=attempts_per_candidate,
                expected_merge_rounds_per_delivered_cluster=attempts_per_candidate / p,
                storage_loss_included=False, star_preparation_time_included=False)
    spare = {r: cluster_resources(r) for r in (2, 4, 8)}
    return dict(full_restart=full,
                spare_leaves={f"spare={r}": dict(p_build=v["p_build_all"], bell_pairs_conditional=v["expected_bell_pairs_conditional_on_success"]) for r, v in spare.items()},
                note="spare-leaf numbers are conditional on success and omit star-growth storage; full restart is an unconditional expectation with zero storage loss")


# ------------------------------------------------------------------ online ledger

def online_ledger(memory, detector_efficiency, *, latency_rounds=1, require_discarded_clicks=True):
    """Every measured node must click exactly once (Theorem L2) or the run is rejected.
    A node read in feedforward layer l waits l*latency rounds after delivery with
    per-round survival m; detector efficiency eta per read node. Returns the exact
    acceptance probability; a rejected run costs rate, never fidelity."""
    m = rational(Fraction(str(memory)) if type(memory) is str else memory, "memory", 256)
    eta = rational(Fraction(str(detector_efficiency)) if type(detector_efficiency) is str else detector_efficiency, "efficiency", 256)
    d = integer(latency_rounds, "latency rounds")
    if not (0 <= m <= 1 and 0 <= eta <= 1 and 0 <= d <= 256):
        raise ValueError("memory and efficiency in [0,1], latency rounds in [0,256]")
    layers = feedforward_layers()
    read = list(ORDER) + [READOUT] + (list(DISCARDED) if require_discarded_clicks else [])
    survival = Fraction(1)
    for node in read:
        survival *= m ** (layers["layer"].get(node, 0) * d)
    accept = survival * eta ** len(read)
    return dict(memory=m, detector_efficiency=eta, latency_rounds=d, stages=layers["stages"], nodes_required=len(read),
                storage_survival=survival, acceptance=accept, rejected_runs_cost="rate only (Theorem L2)",
                unheralded_error_sources_not_modelled=["multi-pair (V1)", "dark counts (dark_readout_site)", "distinguishability (visibility law)"])


def ledger_table():
    rows = []
    for m in ("999/1000", "99/100", "9/10"):
        for eta in ("1", "9/10", "1/2"):
            l = online_ledger(m, eta)
            rows.append(dict(memory=m, efficiency=eta, acceptance=l["acceptance"]))
    return rows


# ------------------------------------------------------------------ grader

def cluster_build_grade(record):
    """Fail-closed: BUILD_DECLARED -> STARS_RECORDED (LAB_RECORDED GHZ5 and GHZ3 witnesses)
    -> TREE_RECORDED (LAB_RECORDED 13 photons, 12 stabiliser witnesses, merge phase
    corrections applied) -> ADAPTIVE_RUN_RECORDED (LAB_RECORDED feedforward latency, five
    stages, rejected runs counted, no rail switch)."""
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    reasons = []
    s = record.get("stars")
    if not (type(s) is dict and s.get("evidence_class") == "LAB_RECORDED" and s.get("ghz5_witness") is not None and s.get("ghz3_witness") is not None):
        reasons.append("stars block needs LAB_RECORDED ghz5_witness and ghz3_witness")
        return dict(grade="BUILD_DECLARED", reasons=reasons)
    t = record.get("tree")
    if not (type(t) is dict and t.get("evidence_class") == "LAB_RECORDED" and t.get("photons") == NODES
            and type(t.get("stabiliser_witnesses")) is int and t["stabiliser_witnesses"] >= len(EDGES) and t.get("merge_phases_applied") is True):
        reasons.append("tree block needs LAB_RECORDED photons == 13, >= 12 stabiliser witnesses, merge_phases_applied")
        return dict(grade="STARS_RECORDED", reasons=reasons)
    a = record.get("adaptive_run")
    if not (type(a) is dict and a.get("evidence_class") == "LAB_RECORDED" and a.get("latency_us") is not None
            and a.get("stages") == feedforward_layers()["stages"] and type(a.get("rejected_runs")) is int and a.get("rail_switches") == 0):
        reasons.append("adaptive_run block needs LAB_RECORDED latency_us, stages == 5, integer rejected_runs, rail_switches == 0")
        return dict(grade="TREE_RECORDED", reasons=reasons)
    return dict(grade="ADAPTIVE_RUN_RECORDED", reasons=reasons, allowed=["recorded cluster built from stars and read with heater-only feedforward"])


def build_plan():
    tree = tree_from_stars()
    cost = build_cost()
    layers = feedforward_layers()
    return dict(schema="native-cluster-build-v1", author="Monty", status="DECLARED_BUILD_NO_DEVICE",
                adaptation=dict(lemma_a_all_angles=all(adaptation_lemma(k)["holds"] for k in range(64)), rail_switches=0, stages=layers["stages"],
                                first_layer=layers["parallel_first_layer"]),
                tree=dict(exact=tree["tree_graph_exact"], photons_before=tree["photons_before"], merges=tree["merges"], success=str(tree["success_probability"])),
                cost=dict(full_restart_bell_pairs=str(cost["full_restart"]["expected_bell_pairs_per_delivered_cluster"]),
                          spare4_bell_pairs_conditional=str(cost["spare_leaves"]["spare=4"]["bell_pairs_conditional"])),
                claims=dict(exact=["Lemma A at all 64 angles", "adaptive end-to-end witness", "tree from seven v0.30 merges, sign-exact", "cost and ledger laws"],
                            never=["device", "measured number", "fidelity from a loss number", "speedup or advantage"],
                            open=["storage during star growth", "switch and buffer loss", "multi-pair, dark counts and visibility on the 13 nodes", "source rate at 810 nm"]))
