"""Fusion network for the 810 nm dual-rail route (v0.22).

How N heralded sites become one N-site register with type-I fusions of
success 1/2 (D2) under loss (L1). Exact statements: multiplexing law for
heralded sources through a switch tree; Theorem N1, growing a chain by
fusing Bell pairs is a null random walk at success 1/2, while fusing
pre-built 3-site GHZ resources has drift +1/2; exact hitting probabilities
and expected attempt counts from a finite Markov chain solved in rationals;
fidelity bound from the false-herald fraction. Boosted fusion and photonic
memory are declared options, not derived. No network exists.
"""
from fractions import Fraction

from .model import ResourceLimit, rational
from .loss_budget import false_herald_law, budget

FUSION_SUCCESS = Fraction(1, 2)      # Theorem D2, proved in dual_rail.py
BOOSTED_SUCCESS = Fraction(3, 4)     # literature value with one ancilla Bell pair; declared, not derived here
GRADES = ("NETWORK_DECLARED", "FUSION_RECORDED", "GROWTH_RECORDED", "MULTIPLEXED_RECORDED", "NETWORK_QUALIFIED")


def _unit(v, label):
    if type(v) is str:
        v = Fraction(v)
    v = rational(v, label, 256)
    if not 0 <= v <= 1:
        raise ValueError(f"{label} must lie in [0, 1]")
    return v


def multiplex(p_herald, branches, switch_transmission=1):
    """M heralded sources behind a binary switch tree (M a power of two).

    P(at least one herald) = 1 - (1-p)^M; the chosen photon crosses log2 M
    switch stages, each with transmission t, so the delivered probability is
    (1 - (1-p)^M) t^(log2 M). Exact; M = 1 is the bare source.
    """
    p, t = _unit(p_herald, "herald probability"), _unit(switch_transmission, "switch transmission")
    m = int(branches)
    if m < 1 or m & (m - 1):
        raise ValueError("branches must be a power of two")
    if m > 1 << 16:
        raise ResourceLimit("branches at most 2^16")
    depth = m.bit_length() - 1
    at_least_one = 1 - (1 - p) ** m
    return dict(branches=m, depth=depth, p_at_least_one=at_least_one, delivered=at_least_one * t ** depth,
                gain_over_bare=(at_least_one * t ** depth) / p if p else None)


def best_multiplexing(p_herald, switch_transmission, max_depth=8):
    rows = [multiplex(p_herald, 1 << d, switch_transmission) for d in range(max_depth + 1)]
    best = max(rows, key=lambda r: r["delivered"])
    return dict(rows=rows, best_branches=best["branches"], best_delivered=best["delivered"])


def growth_drift(success, resource_sites):
    """Theorem N1. Fusing a k-site resource onto the chain end: +(k-1) sites on
    success, -1 on failure (the end site is measured out). Drift s k - 1.
    Bell pairs (k = 2) at s = 1/2: drift 0, a null walk that never grows in
    expectation. 3-site GHZ resources at s = 1/2: drift +1/2."""
    s = _unit(success, "success")
    k = int(resource_sites)
    if k < 2:
        raise ValueError("a resource has at least two sites")
    drift = s * k - 1
    return dict(success=s, resource_sites=k, step_up=k - 1, step_down=1, drift=drift, grows=drift > 0,
                minimum_resource_sites_for_growth=None if s == 0 else int(1 / s) + 1)   # smallest k with s k > 1


def _solve(a, b):
    """Exact Gaussian elimination over Fractions."""
    n = len(a)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = next(r for r in range(c, n) if m[r][c] != 0)
        m[c], m[piv] = m[piv], m[c]
        inv = 1 / m[c][c]
        m[c] = [v * inv for v in m[c]]
        for r in range(n):
            if r != c and m[r][c] != 0:
                f = m[r][c]
                m[r] = [vr - f * vc for vr, vc in zip(m[r], m[c])]
    return [m[i][n] for i in range(n)]


def chain_walk(target_sites, success=FUSION_SUCCESS, resource_sites=3, start_sites=None):
    """Exact absorbing Markov chain: state = chain length L in [0, target]; from
    0 < L < target, L -> min(L + k - 1, target) with probability s, L -> L - 1
    with 1 - s. Returns the probability of reaching the target before the
    chain dies, and the expected number of fusion attempts until either end.
    Rational exact; sizes up to 256 states."""
    s = _unit(success, "success")
    k = int(resource_sites)
    n = int(target_sites)
    start = k if start_sites is None else int(start_sites)
    if not (2 <= k and 1 <= start < n):
        raise ValueError("need 2 <= resource sites and 1 <= start < target")
    if n > 256:
        raise ResourceLimit("target at most 256 sites for exact solve")
    inner = list(range(1, n))
    idx = {L: i for i, L in enumerate(inner)}
    a = [[Fraction(0)] * len(inner) for _ in inner]
    b_hit = [Fraction(0)] * len(inner)
    b_steps = [Fraction(1)] * len(inner)
    for L in inner:
        i = idx[L]
        a[i][i] += 1
        up = min(L + k - 1, n)
        if up >= n:
            b_hit[i] += s
        else:
            a[i][idx[up]] -= s
        down = L - 1
        if down >= 1:
            a[i][idx[down]] -= 1 - s
    hit = _solve(a, b_hit)
    steps = _solve(a, b_steps)
    return dict(target_sites=n, success=s, resource_sites=k, start_sites=start,
                p_reach_target=hit[idx[start]], expected_attempts=steps[idx[start]],
                resources_per_attempt=1, note="each attempt consumes one k-site resource; a 3-site resource costs two Bell pairs and one heralded fusion (expected four Bell pairs at s = 1/2)")


def extinction_cubic(q):
    """Theorem N2: for +2 / -1 steps at s = 1/2 the extinction probability from
    height 1 solves q = q^3/2 + 1/2, i.e. (q - 1)(q^2 + q - 1) = 0, so
    q = (sqrt 5 - 1)/2 and the chain from height 3 reaches any target with
    probability tending to 1 - q^3 = 3 - sqrt 5. Returns the cubic residual."""
    q = rational(Fraction(str(q)) if type(q) is str else q, "q", 256)
    return q ** 3 / 2 + Fraction(1, 2) - q


def resource_estimate(target_sites, success=FUSION_SUCCESS, resource_sites=3):
    w = chain_walk(target_sites, success, resource_sites)
    pairs_per_resource = Fraction(2) / success if resource_sites == 3 else None
    return dict(**w, expected_bell_pairs=(w["expected_attempts"] * pairs_per_resource + 2) if pairs_per_resource else None,
                heralded_fusions=w["expected_attempts"] + (w["expected_attempts"] / success if resource_sites == 3 else 0))


def chain_fidelity_bound(eta_d, fusions):
    g = false_herald_law(eta_d)["genuine_fraction"]
    f = int(fusions)
    if f > 4096:
        raise ResourceLimit("fusions at most 4096")
    return dict(eta_d=_unit(eta_d, "eta_d"), fusions=f, all_heralds_genuine=g ** f)


def network_plan(sites, *, p_herald=Fraction(1, 79), switch_transmission=Fraction(9, 10), eta_d=Fraction(3, 5)):
    n = int(sites)
    if not 3 <= n <= 1 << 20:
        raise ValueError("sites in [3, 2^20]")
    mux = best_multiplexing(p_herald, switch_transmission)
    bell = growth_drift(FUSION_SUCCESS, 2)
    ghz3 = growth_drift(FUSION_SUCCESS, 3)
    walk = chain_walk(min(n, 256)) if n >= 4 else None
    fid = chain_fidelity_bound(eta_d, n - 2)
    return dict(schema="native-fusion-network-v1", author="Monty", status="NETWORK_DECLARED", sites=n,
                inputs=dict(p_herald=str(p_herald), switch_transmission=str(switch_transmission), eta_d=str(eta_d),
                            fusion_success=str(FUSION_SUCCESS), boosted_success_declared=str(BOOSTED_SUCCESS)),
                multiplexing=dict(best_branches_up_to_256=mux["best_branches"], best_delivered_approx=float(mux["best_delivered"]),
                                  gain_over_bare_approx=float(mux["best_delivered"] / p_herald), exact="multiplex(p, M, t) returns the rational"),
                theorem_N1=dict(bell_pair_drift=str(bell["drift"]), ghz3_drift=str(ghz3["drift"]), bell_pairs_grow=bell["grows"], ghz3_grows=ghz3["grows"]),
                chain_walk=None if walk is None else dict(target=walk["target_sites"], p_reach_target=str(walk["p_reach_target"]),
                                                          p_reach_target_approx=float(walk["p_reach_target"]),
                                                          expected_attempts=str(walk["expected_attempts"]),
                                                          expected_attempts_approx=float(walk["expected_attempts"]), exact_up_to_sites=256,
                                                          limit="p_reach -> 3 - sqrt(5) as target -> infinity (Theorem N2)"),
                fidelity=dict(minimum_fusions=n - 2, all_heralds_genuine_bound=str(fid["all_heralds_genuine"]) if n - 2 <= 64 else f"(1/(2-eta_d))^{n - 2}"),
                architecture=["N multiplexed heralded sources (SOURCE_SPEC_810.md), each a switch tree of the best depth above",
                              "Bell pairs from pairs of heralded photons on a coupler, or directly from type-II SPDC with heralding",
                              "3-site GHZ resources by one heralded fusion of two Bell pairs (D2)",
                              "chain growth by fusing 3-site resources onto the chain end; failure shortens the chain by one",
                              "feed-forward: heralded phase zeta^48 or zeta^16 per fusion (D2) applied as a Z step on the heater",
                              "fibre delay as the only photonic memory; its transmission per attempt is a further declared loss"],
                boundaries=["fusion success 1/2 is proved; boosted 3/4 is a declared literature option with one ancilla Bell pair",
                            "fidelity bound counts false heralds only (L1); dark counts, multi-pair and distinguishability enter through the recorded visibility",
                            "the walk assumes independent attempts and no memory loss; memory loss per attempt lowers every number",
                            "no network, switch or delay line exists; nothing changes the temperature verdict"])


def network_grade(record):
    """Fail-closed: NETWORK_DECLARED -> FUSION_RECORDED (LAB_RECORDED heralded
    3-site witness <XXX> >= 1/2 from one fusion) -> GROWTH_RECORDED (LAB_RECORDED
    chain of >= 4 sites built by at least one chain fusion) -> MULTIPLEXED_RECORDED
    (LAB_RECORDED delivered probability above the bare source) -> NETWORK_QUALIFIED
    (all three with every network subsystem at or above the room band floor)."""
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    reasons = []
    f = record.get("fusion")
    if not (type(f) is dict and f.get("evidence_class") == "LAB_RECORDED" and f.get("xxx_witness") is not None
            and -1 <= Fraction(str(f["xxx_witness"])) <= 1 and Fraction(str(f["xxx_witness"])) >= Fraction(1, 2)):
        reasons.append("fusion block needs a LAB_RECORDED heralded <XXX> >= 1/2")
        return dict(grade="NETWORK_DECLARED", reasons=reasons)
    g = record.get("growth")
    if not (type(g) is dict and g.get("evidence_class") == "LAB_RECORDED" and int(g.get("sites", 0)) >= 4):
        reasons.append("growth block needs a LAB_RECORDED chain of at least 4 sites")
        return dict(grade="FUSION_RECORDED", reasons=reasons)
    m = record.get("multiplexing")
    if not (type(m) is dict and m.get("evidence_class") == "LAB_RECORDED" and m.get("delivered") is not None and m.get("bare") is not None
            and _unit(m["delivered"], "delivered") > _unit(m["bare"], "bare")):
        reasons.append("multiplexing block needs LAB_RECORDED delivered probability above the bare source")
        return dict(grade="GROWTH_RECORDED", reasons=reasons)
    temps = record.get("subsystem_temperatures_c")
    if not (type(temps) is dict and temps and all(rational(Fraction(str(t)), k, 256) >= 15 for k, t in temps.items())):
        reasons.append("subsystem temperatures missing or some subsystem below the room band floor")
        return dict(grade="MULTIPLEXED_RECORDED", reasons=reasons)
    return dict(grade="NETWORK_QUALIFIED", reasons=reasons)
