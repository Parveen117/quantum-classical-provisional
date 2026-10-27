"""The classifier's readout noise channel from the corrected source state (v0.36).

v0.34 corrected the double-pair source sector to the Bell-diagonal state with
weights (1 - w/4, w/12, w/12, w/12) on the accepted pairs (w the double-origin
event fraction) and named the source-to-readout channel of the classifier as
the open gate. This module gives that channel to first order, exactly, and
bounds the rest. Nothing here is measured and no witness is qualified.

Lemma N1 (merge). The v0.18 type-I fusion succeeds with probability exactly 1/2
  for every Bell state of the fused pair, so a wrong pair is never heralded
  away. On success the register equals the clean register with: Z on any one
  site (Phi-), X on the unfused photon (Psi+), Y on the unfused photon (Psi-).
  Engine-checked on both click branches.
Lemma N2 (reduction). On a graph state X_v = Z_{N(v)} and Y_v ~ Z_v Z_{N(v)}
  (stabiliser K_v), so every Pauli error on the delivered cluster is a Z pattern,
  and Z commutes with every CZ: the error can be placed at allocation.
Lemma N3 (byproduct). Z on a node measured in B(a) swaps the two outcome
  branches, so after the v0.29 flow correction both branches still coincide up
  to a phase: the error becomes the byproduct Pauli X_{f(v)} Z_{N(f(v))}, and
  the readout probability is exact without branching.
Theorem N (first order). With q = w/4 the per-pair error probability and
  twelve Bell pairs in the build, |P_noisy - P_clean| <= sum over pairs of
  (w/12) sum_P |Delta_P| + R, R = 1 - (1-q)^12 - 12 q (1-q)^11, where
  Delta_P is the exact response of the readout to the single error P. The
  six Bell-pair stars give their three Z patterns exactly; the 3-star and the
  5-star are bounded by the worst Z pattern on their support.
"""
from fractions import Fraction
from itertools import combinations

from native_relational_qc.cyclotomic64 import ONE, ZERO, ZETA

from .cluster_build import _equal_up_to_phase, star_plan
from .cluster_compile import (DISCARDED, H2, NODES, ORDER, READOUT, SQRT2, XOR_CHECKPOINT, XOR_EXAMPLES, _State, _correct, _touch,
                              circuit_probability, neighbours, pattern)
from .dual_rail import FUSION_MODES, MEASURED, _register_state, fusion_outcomes
from .model import integer, rational
from .source_distillation import BELL_LABELS, source_sector

BELL_PAIRS = 12                     # six Bell-pair stars, two pairs in the 3-star, four in the 5-star
GENERIC = dict(features=(5, 11), parameters=(3, 7, 13, 21, 29))
GRADES = ("NOISE_DECLARED", "SOURCE_SECTOR_RECORDED", "READOUT_NOISE_PREDICTED")
NEVER = ("WITNESS_QUALIFIED", "TRAINED_ON_CHIP", "QUANTUM_ADVANTAGE", "ROOM_TEMPERATURE_CLASSIFIER")


# ------------------------------------------------------------------ Lemma N1

def pair_state(label):
    """Bell state of pair A (modes 0-3) times Phi+ of pair B (modes 4-7), dual-rail Fock."""
    if label not in BELL_LABELS:
        raise ValueError("label in " + ", ".join(BELL_LABELS))
    st = {}
    for x in (0, 1):
        for y in (0, 1):
            occ = [0] * FUSION_MODES
            occ[0 + x] = 1
            occ[2 + (x if label.startswith("phi") else 1 - x)] = 1
            occ[4 + y] = 1
            occ[6 + y] = 1
            amp = H2 * H2
            if label.endswith("minus") and x == 1:
                amp = -amp
            st[tuple(occ)] = st.get(tuple(occ), ZERO) + amp
    return st


def _pauli(reg, site, p):
    out = {}
    for key, amp in reg.items():
        k = list(key)
        if p in "XY":
            k[site] ^= 1
        if p in "ZY" and key[site]:
            amp = -amp
        if p == "Y":
            amp = amp * ZETA ** 16
        out[tuple(k)] = amp
    return out


def _same_up_to_phase(a, b):
    if set(a) != set(b):
        return False
    key = next(iter(a))
    if b[key] == ZERO:
        return False
    r = a[key] * b[key].inverse()
    if all(r != s * ZETA ** k for k in range(64) for s in (ONE, -ONE)):
        return False
    return all(a[k] == r * b[k] for k in a)


def merge_lemma():
    """Lemma N1 on the v0.18 engine: success 1/2 for every Bell label, and the register
    Paulis that reproduce the wrong-pair register from the clean one (site 0 = unfused A')."""
    clean = fusion_outcomes()
    clean_reg = {c: _register_state(clean["success"], c) for c in MEASURED}
    rows = {}
    for label in BELL_LABELS:
        res = fusion_outcomes(pair_state(label))
        matches = {}
        for c in MEASURED:
            reg = _register_state(res["success"], c)
            matches[c] = tuple((site, p) for site in (0, 1, 2) for p in "XYZ" if _same_up_to_phase(reg, _pauli(clean_reg[c], site, p)))
        rows[label] = dict(success_probability=res["success_probability"], register_paulis=matches)
    expected = dict(phi_plus=(), phi_minus=((0, "Z"), (1, "Z"), (2, "Z")), psi_plus=((0, "X"),), psi_minus=((0, "Y"),))
    holds = all(r["success_probability"] == H2 * H2 for r in rows.values()) and all(
        all(m == expected[l] for m in rows[l]["register_paulis"].values()) for l in BELL_LABELS if l != "phi_plus")
    return dict(holds=holds, rows=rows, never_heralded=all(r["success_probability"] == H2 * H2 for r in rows.values()))


# ------------------------------------------------------------------ Lemma N2

def stabiliser_reduction(node):
    """Z_v -> {v}; X_v -> N(v); Y_v -> {v} + N(v), as node sets of a Z pattern."""
    v = integer(node, "node")
    if not 0 <= v < NODES:
        raise ValueError("node outside the cluster")
    n = set(neighbours(v))
    return dict(Z=frozenset({v}), X=frozenset(n), Y=frozenset(n | {v}))


def _copy(st):
    s = _State()
    s.live, s.dead, s.amps = list(st.live), set(st.dead), dict(st.amps)
    return s


def reduction_lemma():
    """Engine check of Lemma N2 on the delivered graph, node by node."""
    ok = True
    for v in range(NODES):
        st = _State()
        _touch(st, v)
        a, b = _copy(st), _copy(st)
        a.x(v)
        for w in neighbours(v):
            b.z(w)
        ok = ok and _equal_up_to_phase(a, b)[0]
        c, d = _copy(st), _copy(st)
        c.z(v)
        c.x(v)
        d.z(v)
        for w in neighbours(v):
            d.z(w)
        ok = ok and _equal_up_to_phase(c, d)[0]
    return dict(holds=ok, nodes=NODES)


# ------------------------------------------------------------------ noisy runs (Lemma N3)

def noisy_run(features, parameters, z_nodes=()):
    """The v0.29 corrected run with a Z error on every node of `z_nodes`, placed at
    allocation (Lemma N2). Both outcome branches are compared up to a phase after each
    correction (Lemma N3); the exact readout probability P(readout = 1) is returned."""
    z_nodes = frozenset(integer(v, "node") for v in z_nodes)
    if any(not 0 <= v < NODES for v in z_nodes):
        raise ValueError("node outside the cluster")
    spec = pattern(features, parameters)
    st = _State()
    applied = set()

    def allocate(state, *nodes):
        _touch(state, *nodes)
        for v in state.live:
            if v in z_nodes and v not in applied:
                state.z(v)
                applied.add(v)

    for node in ORDER:
        c = spec["corrections"][node]
        allocate(st, node, c["x"], *c["z"])
        b0, b1 = st.measure(node, spec["measurement_angles"][node])
        _correct(b1, spec, node, "flow")
        same, _ = _equal_up_to_phase(b0, b1)
        if not same:
            raise ArithmeticError(f"Lemma N3 failed at node {node}")
        st = b0
        st.amps = {k: v * SQRT2 for k, v in st.amps.items()}
    allocate(st, READOUT)
    _, r1 = st.measure(READOUT, spec["measurement_angles"][READOUT])
    return dict(z_nodes=tuple(sorted(z_nodes)), readout_probability=r1.norm2())


def response_table(features, parameters):
    """Exact readout probability under every single-node error (Z, X, Y), reduced to its Z
    pattern, with the change from the clean value. Z on a discarded output is invisible."""
    clean = noisy_run(features, parameters)["readout_probability"]
    rows = {}
    for v in range(NODES):
        rows[v] = {}
        for p, nodes in stabiliser_reduction(v).items():
            r = noisy_run(features, parameters, nodes)["readout_probability"]
            rows[v][p] = dict(pattern=tuple(sorted(nodes)), p_one=r, change=r - clean)
    discarded_invisible = all(rows[v]["Z"]["change"] == ZERO for v in DISCARDED)
    return dict(features=tuple(features), parameters=tuple(parameters), clean=clean,
                clean_equals_circuit=clean == circuit_probability(features, parameters), rows=rows,
                discarded_invisible=discarded_invisible)


def xor_response():
    """On the XOR checkpoint every single-node error either flips the label or leaves it:
    the flipping set per example, and the nodes that never flip it."""
    out = {}
    for features, label in XOR_EXAMPLES:
        t = response_table(features, XOR_CHECKPOINT)
        flips = {p: tuple(v for v in range(NODES) if t["rows"][v][p]["change"] != ZERO) for p in "ZXY"}
        binary = all(t["rows"][v][p]["p_one"] in (ZERO, ONE) for v in range(NODES) for p in "ZXY")
        out[features] = dict(label=label, clean=t["clean"], flips=flips, binary=binary)
    never = tuple(v for v in range(NODES) if all(v not in e["flips"][p] for e in out.values() for p in "ZXY"))
    return dict(examples=out, never_flipping=never)


# ------------------------------------------------------------------ source map

def source_map():
    """Where each Bell pair's wrong state lands on the delivered cluster.

    Bell-pair star (centre k fused into the parent, leaf l kept): Phi- -> Z_k (any GHZ site,
    Lemma N1), Psi+ -> X on the GHZ leaf = Z_l after the leaf Hadamard, Psi- -> Y on the leaf
    = Z_k Z_l; exact. For the 3-star (centre 10) and the 5-star (centre 6), built from two
    and four pairs, any Pauli on a star photon is some Pauli string on the star's delivered
    nodes (GHZ stabilisers), hence a Z pattern supported on those nodes and their
    neighbours, discarded outputs dropped: the bound takes the worst pattern on that support.
    """
    plan = star_plan()
    exact, bounded = {}, {}
    for centre, st in plan["stars"].items():
        if st["size"] == 2:
            leaf = plan["children"][centre][0]          # the delivered node of the leaf (a child centre after its merge)
            exact[centre] = dict(phi_minus=frozenset({centre}), psi_plus=frozenset({leaf}), psi_minus=frozenset({centre, leaf}), bell_pairs=1)
        else:
            nodes = {centre} | set(plan["children"][centre])
            support = set()
            for v in nodes:
                support |= {v} | set(neighbours(v))
            support -= set(DISCARDED)
            bounded[centre] = dict(star_nodes=tuple(sorted(nodes)), support=tuple(sorted(support)), bell_pairs=st["size"] - 1,
                                   patterns=tuple(frozenset(s) for r in range(1, len(support) + 1) for s in combinations(sorted(support), r)))
    return dict(exact=exact, bounded=bounded, bell_pairs=sum(e["bell_pairs"] for e in exact.values()) + sum(b["bell_pairs"] for b in bounded.values()))


def _lower(value):
    return value.real_bounds(30)[0]


def _abs(value):
    return value if value.real_sign() >= 0 else -value


def first_order_error(features, parameters, x, eta, *, cache=None):
    """Theorem N: an upper bound on |P_noisy - P_clean| for the classifier readout at the
    corrected source sector (x, eta) of v0.34: first-order term exact on the Bell-pair
    stars, worst-pattern on the two larger stars, plus the exact two-or-more remainder."""
    sector = source_sector(x, eta)
    w = sector["double_fraction"]
    if w is None:
        raise ValueError("no accepted source event at this eta")
    q = w / 4
    clean = noisy_run(features, parameters)["readout_probability"]
    cache = {} if cache is None else cache

    def change(nodes):
        key = frozenset(nodes)
        if key not in cache:
            cache[key] = _abs(noisy_run(features, parameters, key)["readout_probability"] - clean)
        return cache[key]

    smap = source_map()
    if smap["bell_pairs"] != BELL_PAIRS:
        raise ArithmeticError("Bell-pair count changed")
    detail = {}
    exact_sum = ZERO
    for centre, m in smap["exact"].items():
        s = change(m["phi_minus"]) + change(m["psi_plus"]) + change(m["psi_minus"])
        detail[f"pair_{centre}"] = s
        exact_sum = exact_sum + s
    bound_sum = ZERO
    for centre, b in smap["bounded"].items():
        worst = ZERO
        for p in b["patterns"]:
            d = change(p)
            if _lower(d) > _lower(worst):
                worst = d
        detail[f"star_{centre}_worst"] = worst
        bound_sum = bound_sum + worst * (3 * b["bell_pairs"])
    first = (exact_sum + bound_sum) * (w / 12)
    remainder = 1 - (1 - q) ** BELL_PAIRS - BELL_PAIRS * q * (1 - q) ** (BELL_PAIRS - 1)
    lo, hi = first.real_bounds(40)
    return dict(x=Fraction(x), eta=Fraction(eta), double_fraction=w, pair_error_probability=q, clean_readout=clean,
                first_order=first, first_order_bounds=(lo, hi), remainder=remainder, total_upper_bound=hi + remainder,
                detail=detail, exact_pairs=len(smap["exact"]), bounded_stars=tuple(smap["bounded"]))


def required_double_fraction(features, parameters, target, eta="243/4000"):
    """The largest w (double-origin fraction) whose Theorem N bound stays below `target`,
    by bisection on x at the stated eta; the matching x is reported."""
    target = rational(Fraction(target), "target", 256)
    cache = {}
    lo, hi = Fraction(0), Fraction(1, 2)
    best = None
    for _ in range(24):
        mid = (lo + hi) / 2
        e = first_order_error(features, parameters, mid, eta, cache=cache)
        if e["total_upper_bound"] <= target:
            lo, best = mid, e
        else:
            hi = mid
    return dict(target=target, x=lo, double_fraction=None if best is None else best["double_fraction"],
                total_upper_bound=None if best is None else best["total_upper_bound"])


# ------------------------------------------------------------------ controls and grader

def controls(features=GENERIC["features"], parameters=GENERIC["parameters"]):
    """Negative controls: a Z pattern on a discarded output changes nothing; dropping the
    flow correction with an error present breaks Lemma N3 (branches differ); a Phi+ pair
    at the merge gives the clean register (no Pauli)."""
    t = noisy_run(features, parameters)["readout_probability"]
    discarded = all(noisy_run(features, parameters, (v,))["readout_probability"] == t for v in DISCARDED)
    spec = pattern(features, parameters)
    st = _State()
    _touch(st, 0, 1, 6)
    st.z(0)
    b0, b1 = st.measure(0, spec["measurement_angles"][0])
    uncorrected_differ = not _equal_up_to_phase(b0, b1)[0]
    clean_merge = merge_lemma()["rows"]["phi_plus"]["register_paulis"]
    return dict(discarded_invisible=discarded, uncorrected_branches_differ=uncorrected_differ,
                clean_pair_no_pauli=all(m == () for m in clean_merge.values()))


def noise_grade(record):
    """Fail-closed. NOISE_DECLARED -> SOURCE_SECTOR_RECORDED (LAB_RECORDED four Bell weights
    of the accepted pair: nonnegative, summing to one, target largest) ->
    READOUT_NOISE_PREDICTED (LAB_RECORDED readout label error rate at or below the stated
    Theorem N bound). It never qualifies a witness or grants any claim in NEVER."""
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    s = record.get("source_sector")
    if not (type(s) is dict and s.get("evidence_class") == "LAB_RECORDED" and type(s.get("bell_weights")) in (list, tuple) and len(s["bell_weights"]) == 4):
        return dict(grade="NOISE_DECLARED", reasons=["source_sector needs LAB_RECORDED four bell_weights"], never=NEVER)
    try:
        wts = [rational(Fraction(str(v)), "weight", 256) for v in s["bell_weights"]]
    except (ValueError, TypeError):
        return dict(grade="NOISE_DECLARED", reasons=["bell_weights must be rational"], never=NEVER)
    if sum(wts) != 1 or any(v < 0 for v in wts) or wts[0] < max(wts[1:]):
        return dict(grade="NOISE_DECLARED", reasons=["bell_weights must be nonnegative, sum to one, target weight largest"], never=NEVER)
    r = record.get("readout")
    if not (type(r) is dict and r.get("evidence_class") == "LAB_RECORDED" and r.get("label_error_rate") is not None and r.get("predicted_upper_bound") is not None):
        return dict(grade="SOURCE_SECTOR_RECORDED", reasons=["readout needs LAB_RECORDED label_error_rate and predicted_upper_bound"], never=NEVER)
    try:
        rate = rational(Fraction(str(r["label_error_rate"])), "rate", 256)
        bound = rational(Fraction(str(r["predicted_upper_bound"])), "bound", 256)
    except (ValueError, TypeError):
        return dict(grade="SOURCE_SECTOR_RECORDED", reasons=["rate and bound must be rational"], never=NEVER)
    if not 0 <= rate <= 1 or not 0 <= bound <= 1 or rate > bound:
        return dict(grade="SOURCE_SECTOR_RECORDED", reasons=["recorded label error rate must lie in [0,1] and within the predicted bound"], never=NEVER)
    return dict(grade="READOUT_NOISE_PREDICTED", reasons=[], never=NEVER)


def noise_plan():
    """Summary without a device: XOR checkpoint flipping sets, Theorem N bounds at the
    v0.20 x = 1/40 and at 1/200, and the x needed for a 1/100 readout error."""
    xr = xor_response()
    bounds = {}
    for x in ("1/40", "1/200"):
        e = first_order_error((0, 32), XOR_CHECKPOINT, x, "243/4000")
        bounds[x] = dict(double_fraction=str(e["double_fraction"]), first_order=str(float(e["first_order_bounds"][1])),
                         remainder=str(float(e["remainder"])), total_upper_bound=str(float(e["total_upper_bound"])))
    need = required_double_fraction((0, 32), XOR_CHECKPOINT, "1/100")
    return dict(schema="native-cluster-noise-v1", author="Monty", status="FIRST_ORDER_CHANNEL_NO_DEVICE",
                lemmas=dict(n1_merge=merge_lemma()["holds"], n2_reduction=reduction_lemma()["holds"]),
                xor=dict(never_flipping=xr["never_flipping"], flips={str(k): v["flips"] for k, v in xr["examples"].items()}),
                bounds=bounds, x_for_one_percent=dict(x=str(need["x"]), double_fraction=str(need["double_fraction"])),
                claims=dict(exact=["Lemma N1", "Lemma N2", "Lemma N3", "Bell-pair star map", "remainder"],
                            bounded=["3-star and 5-star worst pattern"],
                            never=list(NEVER) + ["measured number", "dark counts", "distinguishability", "correlated loss"]))
