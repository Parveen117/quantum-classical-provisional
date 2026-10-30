"""Loss-tolerant encoding of a dual-rail site: the tree code, exactly (v0.26).

CHAIN_MEMORY.md showed that any memory loss m < 1 suppresses sequential
growth as m^(3J + J(J-1)). The only lever left inside the model is to make a
logical site survive the loss of some of its photons. This note encodes a
site in a tree graph state (branching [b0, b1]: b0 level-1 photons each with
b1 leaves; the root is the logical input, measured out in X). Everything is
derived here from the graph-state stabilisers over GF(2): the code
stabilisers, the logical operators Z_L = X_a prod Z_children(a) (any level-1
a) and X_L = prod_a Z_a, and for EVERY loss pattern whether a representative
of each logical operator survives on the remaining photons. The success
probabilities are therefore exact polynomials in the photon loss epsilon,
not a literature recursion. Controls: the bare photon (1 - epsilon) and the
depth-1 repetition block, which protects Z_L but not X_L. The effective
per-site survival feeds the v0.25 walk as m_eff = P_both(1 - m) ONLY under
ideal renewal of every surviving block after every round. Without renewal,
loss accumulates: see loss_refresh.py and LOSS_REFRESH.md (v0.28). Nothing is
measured; photon counts per logical site alone do not price a refresh.
"""
from fractions import Fraction
from itertools import combinations

from .model import ResourceLimit, integer, rational
from .chain_memory import memory_walk

MAX_PHOTONS = 16


def tree(branching):
    """Nodes 0..n-1 below the root (root is -1 and not a physical photon).
    Returns the parent list and the levels; branching [b0, b1, ...]."""
    b = [integer(v, "branching") for v in branching]
    if not b or any(v < 1 for v in b):
        raise ValueError("branching entries must be positive")
    parent, level = [], []
    frontier = [-1]
    for depth, count in enumerate(b):
        if len(parent) + len(frontier) * count > MAX_PHOTONS:
            raise ResourceLimit(f"at most {MAX_PHOTONS} photons per logical site")
        new = []
        for p in frontier:
            for _ in range(count):
                parent.append(p)
                level.append(depth)
                new.append(len(parent) - 1)
        frontier = new
    if len(parent) > MAX_PHOTONS:
        raise ResourceLimit(f"at most {MAX_PHOTONS} photons per logical site")
    return parent, level


def _children(parent, v):
    return [c for c, p in enumerate(parent) if p == v]


def code(branching):
    """Code stabilisers and logical operators as (x_mask, z_mask) pairs.

    For a node v with parent p and children C: K_v = Z_p X_v prod_C Z_c. Nodes
    at level >= 1 (parent a physical photon) give stabilisers directly. Level-0
    nodes have the root as parent, so only pairwise products K_a K_b (the root
    Z cancels) are stabilisers; a single K_a with the root Z replaced by the
    logical input gives Z_L; the root's own X, pushed through the edges, is
    X_L = prod_a Z_a. Proofs: CZ conjugation, as in any graph state."""
    parent, level = tree(branching)
    n = len(parent)
    def k(v):
        x, z = 1 << v, 0
        for c in _children(parent, v):
            z |= 1 << c
        if parent[v] >= 0:
            z |= 1 << parent[v]
        return (x, z)
    gens = [k(v) for v in range(n) if level[v] >= 1]
    tops = [v for v in range(n) if level[v] == 0]
    for a, b in zip(tops, tops[1:]):
        ka, kb = k(a), k(b)
        gens.append((ka[0] ^ kb[0], ka[1] ^ kb[1]))
    z_logical = k(tops[0])
    x_logical = (0, sum(1 << a for a in tops))
    return dict(branching=list(branching), photons=n, parent=parent, level=level, stabilisers=gens,
                z_logical=z_logical, x_logical=x_logical)


def _commute(p, q):
    return bin((p[0] & q[1]) ^ (p[1] & q[0])).count("1") % 2 == 0


def check_code(c):
    """Every stabiliser commutes with every other and with both logicals; the
    logicals anticommute; the stabiliser count is photons - 1 (one logical qubit)."""
    s = c["stabilisers"]
    ok = all(_commute(p, q) for p in s for q in s)
    ok &= all(_commute(p, c["z_logical"]) and _commute(p, c["x_logical"]) for p in s)
    ok &= not _commute(c["z_logical"], c["x_logical"])
    return dict(commute=ok, rank=_rank(s), expected_rank=c["photons"] - 1, one_logical_qubit=_rank(s) == c["photons"] - 1)


def _rank(vectors, n_bits=2 * MAX_PHOTONS):
    rows = [(x << MAX_PHOTONS) | z for x, z in vectors]
    rank = 0
    for bit in reversed(range(n_bits)):
        piv = next((r for r in rows if (r >> bit) & 1), None)
        if piv is None:
            continue
        rows = [r ^ piv if ((r >> bit) & 1) and r != piv else r for r in rows]
        rows.remove(piv)
        rank += 1
    return rank


def recoverable(logical, stabilisers, lost_mask):
    """Does some representative logical * s, s in the stabiliser group, act as
    identity on every lost photon? A GF(2) linear question on the lost
    coordinates: the restriction of the logical must lie in the span of the
    restricted stabilisers."""
    def restrict(p):
        return ((p[0] & lost_mask) << MAX_PHOTONS) | (p[1] & lost_mask)
    target = restrict(logical)
    if target == 0:
        return True
    basis = [restrict(s) for s in stabilisers]
    return _in_span(target, [b for b in basis if b])


def _in_span(target, basis):
    reduced = []
    for v in basis:
        for r in reduced:
            v = min(v, v ^ r)
        if v:
            reduced.append(v)
            reduced.sort(reverse=True)
    for r in reduced:
        target = min(target, target ^ r)
    return target == 0


def loss_polynomials(branching):
    """Exact success probabilities as polynomials in epsilon: coefficient lists
    a_j = number of loss patterns of weight j under which the logical is
    recoverable, so P(eps) = sum_j a_j eps^j (1-eps)^(n-j). Computed for Z_L,
    X_L and both together by enumerating every loss pattern."""
    c = code(branching)
    n = c["photons"]
    if n > MAX_PHOTONS:
        raise ResourceLimit("too many photons")
    counts = dict(z=[0] * (n + 1), x=[0] * (n + 1), both=[0] * (n + 1))
    for j in range(n + 1):
        for lost in combinations(range(n), j):
            mask = sum(1 << v for v in lost)
            rz = recoverable(c["z_logical"], c["stabilisers"], mask)
            rx = recoverable(c["x_logical"], c["stabilisers"], mask)
            counts["z"][j] += rz
            counts["x"][j] += rx
            counts["both"][j] += rz and rx
    return dict(branching=list(branching), photons=n, counts=counts, check=check_code(c))


def evaluate(poly, epsilon):
    e = rational(Fraction(str(epsilon)) if type(epsilon) is str else epsilon, "epsilon", 256)
    if not 0 <= e <= 1:
        raise ValueError("epsilon in [0, 1]")
    n = poly["photons"]
    def ev(counts):
        return sum(Fraction(a) * e ** j * (1 - e) ** (n - j) for j, a in enumerate(counts))
    return dict(epsilon=e, p_z=ev(poly["counts"]["z"]), p_x=ev(poly["counts"]["x"]), p_both=ev(poly["counts"]["both"]),
                bare=1 - e, beats_bare_both=ev(poly["counts"]["both"]) > 1 - e)


def effective_memory(branching, memory):
    """One-round recoverability P_both(1-m), not an unrefreshed memory channel.
    Reusing this probability each round requires fresh-block renewal."""
    m = rational(Fraction(str(memory)) if type(memory) is str else memory, "memory", 256)
    poly = loss_polynomials(branching)
    return dict(branching=list(branching), photons=poly["photons"], memory=m, m_eff=evaluate(poly, 1 - m)["p_both"])


def encoded_walk(target_sites, branching, memory, bits=20):
    """Ideal-refresh reference model, NOT a physical lower bound.

    Every surviving logical site is restored to a fresh code block after
    every attempt, at zero latency/cost and with perfect logical fusions.
    Flooring m_eff gives a lower bound only within that stronger model.
    """
    bits = integer(bits, "floor bits")
    if not 1 <= bits <= 32:
        raise ResourceLimit("floor bits in [1, 32]")
    e = effective_memory(branching, memory)
    floor = Fraction(int(e["m_eff"] * (1 << bits)), 1 << bits)
    bare = memory_walk(target_sites, memory)
    enc = memory_walk(target_sites, floor)
    return dict(target_sites=target_sites, branching=list(branching), photons_per_site=e["photons"], memory=e["memory"], m_eff=e["m_eff"],
                m_eff_floored=floor, p_reach_bare=bare["p_reach_target"], p_reach_encoded_lower_bound=enc["p_reach_target"],
                photons_in_register=target_sites * e["photons"],
                status="IDEAL_REFRESH_REFERENCE_NOT_HARDWARE_BOUND",
                ideal_refresh_every_round=True, physical_lower_bound=False,
                assumption="perfect fresh-block renewal and logical fusion; zero refresh latency and resource cost")


def crossover(branching, lo=Fraction(0), hi=Fraction(1, 2), bits=24):
    """Largest epsilon below 1/2 (bracketed) up to which P_both(eps) > 1 - eps;
    None when the code never beats the bare photon on [0, 1/2]."""
    poly = loss_polynomials(branching)
    if not evaluate(poly, Fraction(1, 1000))["beats_bare_both"]:
        return dict(branching=list(branching), beats_bare_at_small_loss=False, crossover_bounds=None)
    a, b = lo, hi
    if evaluate(poly, b)["beats_bare_both"]:
        return dict(branching=list(branching), beats_bare_at_small_loss=True, crossover_bounds=(b, None))
    for _ in range(bits):
        mid = (a + b) / 2
        if evaluate(poly, mid)["beats_bare_both"]:
            a = mid
        else:
            b = mid
    return dict(branching=list(branching), beats_bare_at_small_loss=True, crossover_bounds=(a, b))


def record_probability(value, label):
    """Strict rational validation for evidence fields; no float/bool coercion."""
    if type(value) is str:
        value = Fraction(value)
    value = rational(value, label, 256)
    if not 0 <= value <= 1:
        raise ValueError(f"{label} must lie in [0, 1]")
    return value


def record_tolerance(value):
    tol = record_probability(value, "tolerance")
    if tol == 1:
        raise ValueError("tolerance must be less than one")
    return tol


def code_grade(record):
    """Fail-closed: CODE_DECLARED -> ENCODED_SITE_RECORDED (LAB_RECORDED tree
    state of the declared branching with its stabiliser witnesses) ->
    LOSS_RECOVERY_RECORDED (LAB_RECORDED logical X and Z recovery rates with a
    deliberately removed photon) -> CODE_QUALIFIED (recorded recovery at or
    above the exact polynomial at the recorded loss, within tolerance)."""
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    reasons = []
    s = record.get("encoded_site")
    if not (type(s) is dict and s.get("evidence_class") == "LAB_RECORDED" and s.get("branching") and s.get("stabiliser_witnesses") is not None):
        reasons.append("encoded_site block needs LAB_RECORDED branching and stabiliser_witnesses")
        return dict(grade="CODE_DECLARED", reasons=reasons)
    n = code(s["branching"])["photons"]
    witnesses = s["stabiliser_witnesses"]
    if type(witnesses) is not int or witnesses < n - 1:
        return dict(grade="CODE_DECLARED", reasons=["need a nonnegative integer count of at least photons-1 stabiliser witnesses"])
    r = record.get("recovery")
    if not (type(r) is dict and r.get("evidence_class") == "LAB_RECORDED" and r.get("epsilon") is not None
            and r.get("p_x") is not None and r.get("p_z") is not None and r.get("removed_photon") is True):
        reasons.append("recovery block needs LAB_RECORDED epsilon, p_x, p_z with a deliberately removed photon")
        return dict(grade="ENCODED_SITE_RECORDED", reasons=reasons)
    poly = loss_polynomials(s["branching"])
    epsilon = record_probability(r["epsilon"], "epsilon")
    if not 0 < epsilon < 1:
        raise ValueError("loss recovery evidence needs 0 < epsilon < 1")
    ex = evaluate(poly, epsilon)
    tol = record_tolerance(r.get("tolerance", "1/10"))
    px = record_probability(r["p_x"], "p_x")
    pz = record_probability(r["p_z"], "p_z")
    if px < ex["p_x"] * (1 - tol) or pz < ex["p_z"] * (1 - tol):
        reasons.append("recorded recovery below the exact polynomial beyond tolerance")
        return dict(grade="LOSS_RECOVERY_RECORDED", reasons=reasons, exact=dict(p_x=ex["p_x"], p_z=ex["p_z"]))
    return dict(grade="CODE_QUALIFIED", reasons=reasons, exact=dict(p_x=ex["p_x"], p_z=ex["p_z"]))
