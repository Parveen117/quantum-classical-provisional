"""Ledger violations at readout: multi-pair and dark counts (v0.24).

LOSS_LEDGER.md (L2) made loss a rate under the readout rule "exactly one
click per site". What the rule cannot remove is a violation of the photon
ledger: a site holding two photons (multi-pair emission, charge above N)
or a click with no photon (readout dark count, charge above the register).
Both are exact here. Theorem V1: a doubly occupied site passes threshold
readout exactly when both photons leave the exchange unit in one rail,
with probability cos^4 + sin^4 of the native angle, never below 1/2;
number-resolving readout rejects it always. Theorem V2: with per-site
accept-right weight r and accept-wrong weight w, the N-site corrected
witness after readout is exactly (r/(r+w))^N, so a target witness V fixes
the per-site wrong fraction at most 1 - V^(1/N), tabulated as exact
rational brackets. A dual-rail sweep verdict wraps the v0.17 grader and
fails closed unless the ledger fields are recorded.
"""
from fractions import Fraction

from native_relational_qc.cyclotomic64 import Cyclotomic64 as F, ZERO, ONE
from .model import ResourceLimit, integer, rational
from .dual_rail import fock_amplitude, unit_matrix
from .temperature_sweep import temperature_claim_verdict

READOUT = ("threshold", "number_resolving")
LEDGER_FIELDS = ("readout_rule", "dark_count_bound", "heralded_g2", "source_visibility")


def _unit(v, label):
    if type(v) is str:
        v = Fraction(v)
    v = rational(v, label, 256)
    if not 0 <= v <= 1:
        raise ValueError(f"{label} must lie in [0, 1]")
    return v


def double_occupancy(theta_steps):
    """Theorem V1 in the engine: two photons in one rail of a site, through the
    four-heater unit at the native angle. Returns the exact probabilities of
    both leaving in rail 0, both in rail 1, and one each."""
    u = unit_matrix(theta_steps)
    both0 = fock_amplitude(u, (2, 0), (2, 0)).norm2()
    both1 = fock_amplitude(u, (2, 0), (0, 2)).norm2()
    split = fock_amplitude(u, (2, 0), (1, 1)).norm2()
    return dict(theta_steps=theta_steps, same_rail=both0 + both1, split=split, total=both0 + both1 + split,
                threshold_accepts=both0 + both1, number_resolving_accepts=ZERO)


def double_occupancy_table(angles=range(0, 65, 4)):
    rows = []
    for t in angles:
        d = double_occupancy(t)
        rows.append(dict(theta_steps=t, same_rail=d["same_rail"], split=d["split"], unit_total=d["total"] == ONE))
    return rows


def multi_pair_site(theta_steps, x, eta_site=1):
    """Per-site weights from a second pair (conditional probability x, lossless
    herald, SOURCE_SPEC_810.md) at a site with photon survival eta. Both photons
    survive (eta^2): threshold readout accepts the same-rail outcome of V1 as a
    wrong click pattern, rejects the split; number resolution rejects both.
    Exactly one survives (2 eta (1 - eta)): for a single-site preparation the
    survivor carries the prepared state, so it is accepted and right (this is
    a single-site statement; in a fused register the surviving photon is not
    guaranteed to be the heralded one, so that case is declared, not proved).
    None survives: the site is empty and falls to the dark-count law."""
    x, e = _unit(x, "x"), _unit(eta_site, "eta")
    d = double_occupancy(theta_steps)
    lo, hi = d["same_rail"].real_bounds(16)
    both = x * e * e
    return dict(theta_steps=theta_steps, x=x, eta=e, same_rail_bounds=(lo, hi),
                wrong_threshold_bounds=(both * lo, both * hi), wrong_number_resolving=Fraction(0),
                right_one_survivor=x * 2 * e * (1 - e), rejected_split_bounds=(both * (1 - hi), both * (1 - lo)))


def dark_readout_site(eta_site, dark_per_mode):
    """Per-site readout with two threshold detectors, each dark-clicking with
    probability d per window, photon detected with probability eta.
    accept-right: photon clicks (eta) and the other rail is dark-free (1-d);
    accept-wrong: no photon (1-eta) and exactly one dark click (2d(1-d));
    everything else is rejected (zero or two clicks)."""
    e, d = _unit(eta_site, "eta"), _unit(dark_per_mode, "dark per mode")
    right = e * (1 - d)
    wrong = (1 - e) * 2 * d * (1 - d)
    rejected = 1 - right - wrong
    return dict(eta=e, dark=d, accept_right=right, accept_wrong=wrong, rejected=rejected,
                wrong_fraction=wrong / (right + wrong) if right + wrong else None)


def witness_law(right, wrong, sites):
    """Theorem V2: an accepted wrong site contributes a random X outcome, so the
    corrected N-site witness after readout is exactly (r/(r+w))^N."""
    r, w = _unit(right, "right"), _unit(wrong, "wrong")
    n = integer(sites, "sites")
    if not 1 <= n <= 4096:
        raise ResourceLimit("sites in [1, 4096]")
    if r + w == 0:
        raise ValueError("nothing accepted")
    f = r / (r + w)
    return dict(sites=n, per_site_right_fraction=f, witness=f ** n, accepted_probability=(r + w) ** n)


def _nth_root_bracket(v, n, bits=40):
    """Exact rational bracket of v^(1/n) by bisection."""
    lo, hi = Fraction(0), Fraction(1)
    for _ in range(bits):
        mid = (lo + hi) / 2
        if mid ** n <= v:
            lo = mid
        else:
            hi = mid
    return lo, hi


def allowed_wrong_fraction(target_witness, sites):
    """The per-site wrong fraction 1 - f that still gives witness >= V on N
    sites: f >= V^(1/N). Returned as exact rational bounds."""
    v = _unit(target_witness, "target witness")
    n = integer(sites, "sites")
    lo, hi = _nth_root_bracket(v, n)
    return dict(sites=n, target_witness=v, max_wrong_fraction_bounds=(1 - hi, 1 - lo))


def error_budget(sites, *, x="1/40", theta_steps=16, eta_site="243/4000", dark_per_mode="1/100000", readout="threshold"):
    """Combined per-site budget at the declared operating point and the
    witness it leaves on N sites. All inputs declared; nothing measured."""
    if readout not in READOUT:
        raise ValueError("readout must be threshold or number_resolving")
    mp = multi_pair_site(theta_steps, x, eta_site)
    dk = dark_readout_site(eta_site, dark_per_mode)
    wrong_mp = mp["wrong_threshold_bounds"] if readout == "threshold" else (Fraction(0), Fraction(0))
    right = dk["accept_right"] + mp["right_one_survivor"]
    wrong_lo, wrong_hi = dk["accept_wrong"] + wrong_mp[0], dk["accept_wrong"] + wrong_mp[1]
    w_lo = witness_law(right, wrong_hi, sites)["witness"]
    w_hi = witness_law(right, wrong_lo, sites)["witness"]
    return dict(sites=sites, readout=readout, inputs=dict(x=str(Fraction(x)), theta_steps=theta_steps, eta_site=str(Fraction(eta_site)),
                                                          dark_per_mode=str(Fraction(dark_per_mode))),
                per_site=dict(accept_right=right, accept_wrong_bounds=(wrong_lo, wrong_hi),
                              wrong_fraction_bounds=(wrong_lo / (right + wrong_lo), wrong_hi / (right + wrong_hi))),
                witness_bounds=(w_lo, w_hi), dominant="multi-pair" if wrong_mp[0] > dk["accept_wrong"] else "dark counts")


def dual_rail_sweep_verdict(record, **kw):
    """Fail-closed verdict for a dual-rail sweep record: the v0.17 grader plus
    the ledger fields. A record missing readout_rule == 'exactly one click per
    site', a LAB_RECORDED dark_count_bound, a LAB_RECORDED heralded_g2 below
    1/2 or a LAB_RECORDED source_visibility is downgraded: logic_class
    UNDETERMINED and no logical claim allowed; the thermal class is untouched
    because temperature logs are a separate ledger."""
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    base = temperature_claim_verdict(record, **kw)
    reasons = list(base["reasons"])
    ledger = record.get("ledger")
    ok = type(ledger) is dict and ledger.get("readout_rule") == "exactly one click per site"
    for key in ("dark_count_bound", "heralded_g2", "source_visibility"):
        blk = ledger.get(key) if ok else None
        if not (type(blk) is dict and blk.get("evidence_class") == "LAB_RECORDED" and blk.get("value") is not None):
            ok = False
            reasons.append(f"ledger.{key} missing or not LAB_RECORDED")
            break
    if ok and not Fraction(str(ledger["heralded_g2"]["value"])) < Fraction(1, 2):
        ok = False
        reasons.append("ledger.heralded_g2 not below 1/2")
    if type(ledger) is dict and ledger.get("readout_rule") != "exactly one click per site":
        reasons.append("ledger.readout_rule is not 'exactly one click per site'")
    out = dict(base)
    out["ledger_recorded"] = ok
    if not ok:
        out["logic_class"] = "UNDETERMINED"
        out["claims_allowed"] = [c for c in base["claims_allowed"] if c.startswith("complete apparatus") or c.startswith("cryogen-free")]
    out["reasons"] = reasons
    return out
