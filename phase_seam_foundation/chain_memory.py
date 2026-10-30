"""Memory loss in the fusion chain and the joint source/readout design point (v0.25).

FUSION_NETWORK.md's chain walk assumed the stored chain photons survive every
attempt. The route's only photonic memory is fibre delay, so each attempt
costs every stored photon a transmission m. Exact here: the Markov walk with
survival m^L per attempt (Theorem M1 gives the super-exponential bound
P(reach N) <= m^(3J + J(J-1)), J = ceil((N-3)/2)), the balanced fusion tree
as the comparison architecture (survival m^(N depth), exponential), the
declared fibre-delay table, and the joint choice of source operating point x
and readout type against a target witness and the ledger-violation budget of
v0.24. A fail-closed memory grade closes the note. Nothing is measured.
"""
from fractions import Fraction
import math

from .model import ResourceLimit, integer, rational
from .fusion_network import FUSION_SUCCESS, _solve
from .ledger_violations import error_budget, allowed_wrong_fraction
from .source_spec import heralded_statistics

GRADES = ("MEMORY_DECLARED", "DELAY_LOSS_RECORDED", "STORED_CHAIN_RECORDED", "MEMORY_QUALIFIED")


def _unit(v, label):
    if type(v) is str:
        v = Fraction(v)
    v = rational(v, label, 256)
    if not 0 <= v <= 1:
        raise ValueError(f"{label} must lie in [0, 1]")
    return v


def memory_walk(target_sites, memory, success=FUSION_SUCCESS, resource_sites=3, start_sites=None):
    """Exact absorbing chain with memory loss. From length L (0 < L < N) one
    attempt first stores the L chain photons for one round, all surviving with
    probability m^L (otherwise the ledger readout rejects: absorb at 0); then
    the fusion succeeds (L -> min(L + k - 1, N)) with s or fails (L -> L - 1)."""
    m, s = _unit(memory, "memory"), _unit(success, "success")
    k, n = int(resource_sites), int(target_sites)
    start = k if start_sites is None else int(start_sites)
    if not (2 <= k and 1 <= start < n):
        raise ValueError("need 2 <= resource sites and 1 <= start < target")
    if n > 256:
        raise ResourceLimit("target at most 256 sites")
    inner = list(range(1, n))
    idx = {L: i for i, L in enumerate(inner)}
    a = [[Fraction(0)] * len(inner) for _ in inner]
    b_hit = [Fraction(0)] * len(inner)
    b_steps = [Fraction(1)] * len(inner)
    for L in inner:
        i = idx[L]
        a[i][i] += 1
        surv = m ** L
        up = min(L + k - 1, n)
        if up >= n:
            b_hit[i] += surv * s
        else:
            a[i][idx[up]] -= surv * s
        if L - 1 >= 1:
            a[i][idx[L - 1]] -= surv * (1 - s)
    hit, steps = _solve(a, b_hit), _solve(a, b_steps)
    return dict(target_sites=n, memory=m, success=s, resource_sites=k, start_sites=start,
                p_reach_target=hit[idx[start]], expected_attempts=steps[idx[start]])


def theorem_M1_bound(target_sites, memory, start_sites=3, step_up=2):
    """Reaching N from 3 needs J = ceil((N-3)/2) successes; the j-th happens at
    length >= 3 + 2(j-1) and every stored photon must survive that attempt, so
    P(reach N) <= prod_j m^(3 + 2(j-1)) = m^(3J + J(J-1)). Quadratic exponent."""
    m = _unit(memory, "memory")
    n = int(target_sites)
    j = max(-(-(n - start_sites) // step_up), 0)
    exponent = start_sites * j + j * (j - 1)
    return dict(target_sites=n, successes_needed=j, exponent=exponent, bound=m ** exponent)


def tree_survival(sites, memory, depth=None):
    """Balanced fusion tree, one attempt round per level: every one of the N
    photons is stored for `depth` rounds, so all survive with m^(N depth).
    Exponential in N, against the chain's quadratic exponent."""
    m = _unit(memory, "memory")
    n = integer(sites, "sites")
    if n < 1 or n > 1 << 20:
        raise ValueError("sites in [1, 2^20]")
    d = (n - 1).bit_length() if depth is None else int(depth)
    exponent = n * d
    return dict(sites=n, depth=d, exponent=exponent, survival=m ** exponent if exponent <= 4096 else None,
                survival_approx=(10 ** (exponent * math.log10(m)) if m > 0 else 0.0), law="m^(N depth)")


def fibre_delay_table(*, loss_db_per_km=("2", "3"), attempt_latency_us=("1/10", "1", "10"), speed_km_per_us=Fraction(1, 5)):
    """Declared: fibre loss at 810 nm in dB/km, attempt latency in microseconds,
    light speed in fibre ~ 0.2 km/us. Length = latency x speed; memory m per
    attempt = 10^(-loss x length / 10), displayed approximately (the exact
    arithmetic above takes m as a declared rational)."""
    rows = []
    for a in loss_db_per_km:
        for t in attempt_latency_us:
            length_km = Fraction(t) * speed_km_per_us
            db = Fraction(a) * length_km
            rows.append(dict(loss_db_per_km=str(Fraction(a)), attempt_latency_us=str(Fraction(t)), fibre_length_m=str(length_km * 1000),
                             loss_db=str(db), memory_approx=round(10 ** (-float(db) / 10), 4)))
    return rows


def design_point(sites, target_witness, *, xs=("1/400", "1/100", "1/40", "1/20", "1/10"), readout="threshold",
                 herald_efficiency="1/2", max_g2="1/10", **budget_kw):
    """Joint choice: for each source operating point x, the per-site wrong
    fraction (v0.24 budget, upper bound) against the allowed 1 - V^(1/N), and
    the herald probability per source (rate), and the heralded g2 at the
    declared herald efficiency against max_g2 (the source's own single-photon
    target, since multi-pair also lowers the visibility). Feasible rows meet
    both; the best is the feasible row with the highest herald probability."""
    n = integer(sites, "sites")
    allowed_hi = allowed_wrong_fraction(target_witness, n)["max_wrong_fraction_bounds"][0]   # conservative: lower end
    rows = []
    for xv in xs:
        b = error_budget(n, x=xv, readout=readout, **budget_kw)
        wrong_hi = b["per_site"]["wrong_fraction_bounds"][1]
        h = heralded_statistics(Fraction(xv), herald_efficiency)
        g2_ok = h["g2_heralded"] <= Fraction(str(max_g2))
        rows.append(dict(x=Fraction(xv), wrong_fraction_upper=wrong_hi, allowed=allowed_hi, within_budget=wrong_hi <= allowed_hi,
                         g2_within=g2_ok, feasible=wrong_hi <= allowed_hi and g2_ok,
                         p_herald=h["p_click"], g2_heralded=h["g2_heralded"], witness_lower=b["witness_bounds"][0]))
    feasible = [r for r in rows if r["feasible"]]
    best = max(feasible, key=lambda r: r["p_herald"]) if feasible else None
    return dict(sites=n, target_witness=Fraction(str(target_witness)), readout=readout, rows=rows, best=best,
                feasible=bool(feasible))


def memory_grade(record):
    """Fail-closed: MEMORY_DECLARED -> DELAY_LOSS_RECORDED (LAB_RECORDED
    transmission of the delay line per attempt) -> STORED_CHAIN_RECORDED
    (LAB_RECORDED survival of a >= 3-site chain over one attempt round with
    the per-site rule) -> MEMORY_QUALIFIED (recorded survival at or above the
    declared m^L, within tolerance, and witness after storage at or above the
    source visibility)."""
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    reasons = []
    d = record.get("delay")
    if not (type(d) is dict and d.get("evidence_class") == "LAB_RECORDED" and d.get("transmission_per_attempt") is not None):
        reasons.append("delay block needs LAB_RECORDED transmission_per_attempt")
        return dict(grade="MEMORY_DECLARED", reasons=reasons)
    m = _unit(d["transmission_per_attempt"], "memory")
    c = record.get("stored_chain")
    if not (type(c) is dict and c.get("evidence_class") == "LAB_RECORDED" and int(c.get("sites", 0)) >= 3
            and c.get("survival") is not None and c.get("rule") == "exactly one click per site"):
        reasons.append("stored_chain block needs LAB_RECORDED sites >= 3, survival, per-site rule")
        return dict(grade="DELAY_LOSS_RECORDED", reasons=reasons, memory=m)
    L = int(c["sites"])
    surv = _unit(c["survival"], "survival")
    tol = Fraction(str(c.get("tolerance", "1/10")))
    w = c.get("witness_after_storage")
    vis = c.get("source_visibility")
    if surv < m ** L * (1 - tol):
        reasons.append(f"recorded survival {surv} below declared m^L {m ** L} beyond tolerance")
        return dict(grade="STORED_CHAIN_RECORDED", reasons=reasons, memory=m)
    if w is None or vis is None or Fraction(str(w)) < Fraction(str(vis)):
        reasons.append("witness_after_storage missing or below source_visibility")
        return dict(grade="STORED_CHAIN_RECORDED", reasons=reasons, memory=m)
    return dict(grade="MEMORY_QUALIFIED", reasons=reasons, memory=m)
