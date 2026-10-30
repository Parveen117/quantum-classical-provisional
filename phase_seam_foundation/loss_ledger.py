"""Native ledger treatment of photon loss (v0.23).

The repo's own rule for loss is not a generic efficiency number: it is the
retained ledger. UGD-A0 proves total seam charge q = s + l is conserved by
every grouping while the strict state is not associative; EMK-G3 proves a
flat lift can carry sheet memory, with visible return (alpha = 0 mod K) weaker
than lifted return; the thermodynamic bridge (LTB-1) says a ledger declared
in advance separates protocols while one chosen after the data is vacuous.
Here the ledger is photon number. Theorem L2 (engine-checked): on every
outcome of the lossy fusion, clicks + lost + register photons = 4; a false
herald (L1) is exactly a one-click event whose middle site is empty, so the
readout rule "exactly one photon per site" rejects it. Conditioned on that
readout, the heralded GHZ witness is 1 for every detector-side efficiency.
Loss is therefore a rate cost; the fidelity threats are ledger violations
(dark counts, multi-pair). The loss channel is the cut to an environment
mode, whose Kraus operators are square-sourced and complete (cut-square
positivity); transmissions live on the native grid cos^2(k pi/32).
"""
from fractions import Fraction

from native_relational_qc.cyclotomic_pow2 import field_of_order
F = field_of_order(64)
ZERO = field_of_order(64)()
ONE = field_of_order(64)(1)
ZETA = field_of_order(64).root()
from .model import ResourceLimit, integer, rational
from .dual_rail import (
    FUSION_MODES, MEASURED, bell_pairs_state, compose, embed, evolve, fusion_matrix, identity, total_probability,
    _register_state, _phase_steps,
)
from .loss_budget import LOSS_MODES, loss_block, false_herald_law

SITES = ((0, 1), (2, 5), (6, 7))      # A', C = (a0, b1), B'
TOTAL_CHARGE = 4
GRADES = ("LEDGER_DECLARED", "POSTSELECTION_RECORDED", "DARK_COUNTS_BOUNDED", "LEDGER_QUALIFIED")


def _lossy_outcomes(k):
    m = FUSION_MODES + len(LOSS_MODES)
    state = {occ + (0, 0): amp for occ, amp in bell_pairs_state().items()}
    fusion = tuple(tuple(list(r) + [ZERO] * 2) for r in fusion_matrix()) + tuple(
        tuple([ZERO] * FUSION_MODES + list(r)) for r in identity(2))
    loss = compose(embed(m, (MEASURED[0], LOSS_MODES[0]), loss_block(k)), embed(m, (MEASURED[1], LOSS_MODES[1]), loss_block(k)))
    return evolve(compose(loss, fusion), state)


def charge_ledger(k):
    """Theorem L2 in the engine, transmission eta_d = cos^2(k pi/32).

    L2a: clicks + lost + register photons = 4 on every outcome (charge identity).
    L2b: one click and one lost photon <=> the middle site C is empty; one click
         and nothing lost <=> every site holds exactly one photon.
    L2c: conditioned on one click and one photon per site, the corrected GHZ
         witness <XXX> is exactly 1 (both click modes), independent of eta_d.
    Also: zero clicks with one lost photon is a genuine but missed fusion.
    """
    integer(k, "k")
    out = _lossy_outcomes(k)
    classes = {}
    charge_ok = True
    for occ, amp in out.items():
        clicks = occ[MEASURED[0]] + occ[MEASURED[1]]
        lost = occ[LOSS_MODES[0]] + occ[LOSS_MODES[1]]
        occs = tuple(occ[a] + occ[b] for a, b in SITES)
        charge_ok &= clicks + lost + sum(occs) == TOTAL_CHARGE
        classes.setdefault((clicks, lost, occs), {})[occ] = amp
    probs = {key: total_probability(st) for key, st in classes.items()}
    one_click = {key: p for key, p in probs.items() if key[0] == 1}
    false_heralds_have_empty_c = all(key[2] == (1, 0, 1) for key in one_click if key[1] == 1)
    genuine_full = all(key[2] == (1, 1, 1) for key in one_click if key[1] == 0)
    accepted = classes.get((1, 0, (1, 1, 1)), {})
    witness = {}
    for click in MEASURED:
        reg = _register_state(accepted, click)
        p = sum((a.norm2() for a in reg.values()), ZERO)
        a000, a111 = reg.get((0, 0, 0), ZERO), reg.get((1, 1, 1), ZERO)
        others = [key for key in reg if key not in ((0, 0, 0), (1, 1, 1))]
        kk = _phase_steps(a111 / a000) if a000 != ZERO else None
        corrected = None
        if kk is not None and p != ZERO:
            c = a000.conjugate() * a111 * ZETA ** (-kk)
            corrected = (c + c.conjugate()) / p
        witness[click] = dict(probability=p, support_is_ghz=not others, heralded_phase_steps=kk, corrected_xxx=corrected)
    c = (ZETA ** k + ZETA ** (-k)) / F.coerce(2)
    return dict(k=k, eta_d=c * c, charge_identity=charge_ok, classes=probs,
                false_heralds_have_empty_middle_site=false_heralds_have_empty_c, genuine_heralds_fill_every_site=genuine_full,
                accepted_probability=probs.get((1, 0, (1, 1, 1)), ZERO), rejected_false_heralds=probs.get((1, 1, (1, 0, 1)), ZERO),
                missed_genuine=probs.get((0, 1, (1, 1, 1)), ZERO), witness_after_readout=witness,
                witness_is_one=all(w["corrected_xxx"] == ONE and w["support_is_ghz"] for w in witness.values()),
                total=total_probability(out))


def kraus_completeness(k):
    """The loss beam splitter traced over the environment is the single-photon
    amplitude-damping channel with K0 = diag(1, c), K1 = s |0><1|, c^2 = eta_d.
    K0^dagger K0 + K1^dagger K1 = 1 exactly in the field: the channel is
    square-sourced (cut-square positivity), hence completely positive and
    trace preserving with no extra axiom."""
    (c, s), _ = loss_block(k)
    k0 = ((ONE, ZERO), (ZERO, c))
    k1 = ((ZERO, s), (ZERO, ZERO))
    def dag_mul(a):
        return tuple(tuple(sum((a[r][i].conjugate() * a[r][j] for r in range(2)), ZERO) for j in range(2)) for i in range(2))
    p0, p1 = dag_mul(k0), dag_mul(k1)
    total = tuple(tuple(p0[i][j] + p1[i][j] for j in range(2)) for i in range(2))
    return dict(k=k, eta_d=c * c, complete=total == ((ONE, ZERO), (ZERO, ONE)), kraus=(k0, k1))


def native_transmission_grid():
    """eta = cos^2(k pi/32), k = 0..16 (1 down to 0): the transmissions that are exact field elements."""
    rows = []
    for k in range(17):
        c = (ZETA ** k + ZETA ** (-k)) / F.coerce(2)
        eta = c * c
        lo, hi = eta.real_bounds(16)
        rows.append(dict(k=k, eta=eta, lower=lo, upper=hi))
    return rows


def nearest_grid_point(transmission):
    """Nearest native grid point to a declared rational transmission, with the
    exact residual bounds. The physical loss is not quantised; the grid is the
    sector in which every loss statement is an exact field identity."""
    t = rational(Fraction(str(transmission)) if type(transmission) is str else transmission, "transmission", 256)
    if not 0 <= t <= 1:
        raise ValueError("transmission in [0, 1]")
    best = min(native_transmission_grid(), key=lambda r: abs((r["lower"] + r["upper"]) / 2 - t))
    return dict(transmission=t, k=best["k"], eta=best["eta"], residual_bounds=(best["lower"] - t, best["upper"] - t))


def rate_not_fidelity(eta_d, fusions):
    """Under ledger readout the chain of F fusions keeps witness 1; what it
    pays is the accepted fraction (1/(2 - eta_d))^F of heralded events and the
    missed genuine fraction. Replaces the v0.22 fidelity bound."""
    law = false_herald_law(eta_d)
    f = integer(fusions, "fusions")
    if not 0 <= f <= 4096:
        raise ResourceLimit("fusions in [0, 4096]")
    return dict(eta_d=law["eta_d"], fusions=f, accepted_fraction_of_heralds=law["genuine_fraction"] ** f,
                witness_after_readout=1, fidelity_cost_from_loss=0,
                remaining_fidelity_threats=["dark counts (a click with no photon: charge violated upward)",
                                            "multi-pair emission (charge above N at the source)",
                                            "distinguishability (enters the recorded visibility, not the ledger)"])


def dark_count_table(k, dark_per_window=("1/1000", "1/100", "1/10")):
    """Exact weights of herald-by-dark-count events, by what the ledger readout
    does with them. A dark click on a zero-click outcome fakes a herald. Of
    those: (0 clicks, 1 lost, (1,1,1)) is a genuine fusion whose herald was
    missed, so the dark click yields a correct accepted state; (0,0,(1,2,1))
    holds two photons in site C and is rejected by number-resolving readout
    but passes threshold readout when both sit in one mode; (0,2,(1,0,1)) is
    rejected. Declared dark probability d per herald window and pair of
    detectors; one dark click assumed."""
    out = _lossy_outcomes(k)
    zero = {}
    for occ, amp in out.items():
        if occ[MEASURED[0]] + occ[MEASURED[1]] != 0:
            continue
        lost = occ[LOSS_MODES[0]] + occ[LOSS_MODES[1]]
        occs = tuple(occ[a] + occ[b] for a, b in SITES)
        c_same_mode = occs[1] == 2 and (occ[2] == 2 or occ[5] == 2)
        zero.setdefault((lost, occs, c_same_mode), ZERO)
        zero[(lost, occs, c_same_mode)] += amp.norm2()
    correct = zero.get((1, (1, 1, 1), False), ZERO)
    threshold_wrong = zero.get((0, (1, 2, 1), True), ZERO)
    rejected = sum((p for key, p in zero.items() if key not in ((1, (1, 1, 1), False), (0, (1, 2, 1), True))), ZERO)
    rows = []
    law = charge_ledger(k)
    genuine = law["accepted_probability"]
    for d in dark_per_window:
        dq = Fraction(d)
        wrong = threshold_wrong * F.coerce(dq)
        acc = genuine + (correct + threshold_wrong) * F.coerce(dq)
        rows.append(dict(dark_per_window=str(dq), accepted=acc, wrong_accepted_threshold=wrong,
                         wrong_fraction_threshold=(wrong / acc) if acc != ZERO else None,
                         wrong_fraction_number_resolving=ZERO))
    return dict(k=k, zero_click_classes={str(key): p for key, p in zero.items()}, correct_by_dark=correct,
                threshold_wrong_by_dark=threshold_wrong, rejected_by_dark=rejected, rows=rows)


def ledger_grade(record):
    """Fail-closed: LEDGER_DECLARED -> POSTSELECTION_RECORDED (LAB_RECORDED
    per-site one-click post-selection with the accepted fraction) ->
    DARK_COUNTS_BOUNDED (LAB_RECORDED dark rate per window below the declared
    bound) -> LEDGER_QUALIFIED (LAB_RECORDED witness after readout at or above
    the recorded visibility bound V from the source, i.e. loss did not lower it)."""
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    reasons = []
    ps = record.get("postselection")
    if not (type(ps) is dict and ps.get("evidence_class") == "LAB_RECORDED" and ps.get("rule") == "exactly one click per site"
            and ps.get("accepted_fraction") is not None):
        reasons.append("postselection block needs LAB_RECORDED rule 'exactly one click per site' and accepted_fraction")
        return dict(grade="LEDGER_DECLARED", reasons=reasons)
    dc = record.get("dark_counts")
    if not (type(dc) is dict and dc.get("evidence_class") == "LAB_RECORDED" and dc.get("per_window") is not None
            and dc.get("declared_bound") is not None and Fraction(str(dc["per_window"])) <= Fraction(str(dc["declared_bound"]))):
        reasons.append("dark_counts block needs LAB_RECORDED per_window at or below declared_bound")
        return dict(grade="POSTSELECTION_RECORDED", reasons=reasons)
    w = record.get("witness")
    if not (type(w) is dict and w.get("evidence_class") == "LAB_RECORDED" and w.get("xxx_after_readout") is not None
            and w.get("source_visibility") is not None and Fraction(str(w["xxx_after_readout"])) >= Fraction(str(w["source_visibility"]))):
        reasons.append("witness block needs LAB_RECORDED xxx_after_readout at or above source_visibility")
        return dict(grade="DARK_COUNTS_BOUNDED", reasons=reasons)
    return dict(grade="LEDGER_QUALIFIED", reasons=reasons)
