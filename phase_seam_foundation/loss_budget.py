"""Loss budget for the 810 nm dual-rail route (v0.21).

Declared per-stage transmissions multiply to one exact end-to-end photon
survival eta per site. What loss does to the heralded fusion step is proved
in the exact boson engine: a lost photon can fake the one-click herald, the
false-herald fraction is exactly (1 - eta)/(2 - eta), so the heralded fusion
fidelity factor from detector-side loss is 1/(2 - eta). Loss on the surviving
rails is detected at readout as a missing click, never as a wrong answer.
No stage has been measured; a fail-closed grader says what a recorded chain
may claim.
"""
from fractions import Fraction
import math

from native_relational_qc.cyclotomic_pow2 import field_of_order
F = field_of_order(64)
ZERO = field_of_order(64)()
ONE = field_of_order(64)(1)
ZETA = field_of_order(64).root()
from native_relational_qc.exact import IMAG
from .model import ResourceLimit, rational
from .dual_rail import (
    FUSION_MODES, MEASURED, bell_pairs_state, compose, embed, evolve, fusion_matrix, identity, total_probability,
)

LOSS_MODES = (8, 9)          # environment modes for the two detected modes; 10 modes = engine ceiling
I = F(IMAG)
DECLARED_STAGES = (           # linear transmissions, declared, not measured (dB shown approximately)
    ("source fibre coupling", Fraction(1, 2)),
    ("bandpass filter 810 nm", Fraction(9, 10)),
    ("fibre to chip facet", Fraction(1, 2)),
    ("on-chip propagation and couplers", Fraction(9, 10)),
    ("chip to fibre facet", Fraction(1, 2)),
    ("si_spad_810 detection efficiency", Fraction(3, 5)),
)
GRADES = ("BUDGET_DECLARED", "STAGES_RECORDED", "END_TO_END_RECORDED", "BUDGET_CONSISTENT")


def _unit(v, label):
    if type(v) is str:
        v = Fraction(v)
    v = rational(v, label, 256)
    if not 0 <= v <= 1:
        raise ValueError(f"{label} must lie in [0, 1]")
    return v


def _db(t):
    return None if t == 0 else round(-10 * math.log10(t), 3)


def budget(stages=DECLARED_STAGES):
    """Exact product of declared stage transmissions; dB column is approximate display."""
    rows, eta = [], Fraction(1)
    for name, t in stages:
        t = _unit(t, name)
        eta *= t
        rows.append(dict(stage=name, transmission=t, loss_db_approx=_db(t)))
    return dict(stages=rows, eta=eta, loss_db_approx=_db(eta))


def site_survival(eta, sites):
    """All N site photons detected: eta^N exactly (independent loss)."""
    eta = _unit(eta, "eta")
    n = int(sites)
    if not 1 <= n <= 4096:
        raise ResourceLimit("sites in [1, 4096] for exact expansion")
    return dict(sites=n, eta=eta, all_survive=eta ** n, at_least_one_lost=1 - eta ** n)


def false_herald_law(eta_d):
    """Closed form: with two photons entering the fusion coupler and detector
    efficiency eta_d on the two detected modes, P(exactly one click) =
    eta_d (2 - eta_d) / 2, of which the genuine one-photon events are eta_d / 2.
    Genuine fraction 1/(2 - eta_d); false-herald fraction (1 - eta_d)/(2 - eta_d)."""
    e = _unit(eta_d, "detector-side efficiency")
    if e == 0:
        raise ValueError("efficiency must be positive")
    return dict(eta_d=e, p_one_click=e * (2 - e) / 2, p_genuine=e / 2, genuine_fraction=1 / (2 - e),
                false_herald_fraction=(1 - e) / (2 - e), lossless_success=Fraction(1, 2))


def loss_block(k):
    """Real beam splitter with transmission cos^2(k pi/32), exact in Q(zeta_64)."""
    c = (ZETA ** k + ZETA ** (-k)) / F.coerce(2)
    s = (ZETA ** k - ZETA ** (-k)) / (F.coerce(2) * I)
    return ((c, s), (-s, c))


def lossy_fusion_from_engine(k):
    """Theorem L1 check in the engine: fusion coupler, then loss beam splitters
    of transmission eta = cos^2(k pi/32) on both detected modes (10 modes,
    4 photons). Classify by photons in the detected modes (clicks) and in the
    loss modes (lost)."""
    m = FUSION_MODES + len(LOSS_MODES)
    state = {occ + (0, 0): amp for occ, amp in bell_pairs_state().items()}
    fusion = tuple(tuple(list(r) + [ZERO] * 2) for r in fusion_matrix()) + tuple(
        tuple([ZERO] * FUSION_MODES + list(r)) for r in identity(2))
    loss = compose(embed(m, (MEASURED[0], LOSS_MODES[0]), loss_block(k)), embed(m, (MEASURED[1], LOSS_MODES[1]), loss_block(k)))
    out = evolve(compose(loss, fusion), state)
    classes = {}
    for occ, amp in out.items():
        clicks = occ[MEASURED[0]] + occ[MEASURED[1]]
        lost = occ[LOSS_MODES[0]] + occ[LOSS_MODES[1]]
        classes.setdefault((clicks, lost), {})[occ] = amp
    probs = {key: total_probability(st) for key, st in classes.items()}
    one_click = sum((p for (c, _), p in probs.items() if c == 1), ZERO)
    genuine = probs.get((1, 0), ZERO)
    c = (ZETA ** k + ZETA ** (-k)) / F.coerce(2)
    eta = c * c
    return dict(k=k, eta=eta, probabilities=probs, p_one_click=one_click, p_genuine=genuine,
                genuine_fraction=genuine / one_click if one_click != ZERO else None,
                total=total_probability(out),
                matches_closed_form=(one_click == eta * (F.coerce(2) - eta) / F.coerce(2)) and (genuine == eta / F.coerce(2)))


def fusion_chain_fidelity(eta_d, fusions):
    """Independent fusions: all heralds genuine with probability (1/(2-eta_d))^F exactly."""
    g = false_herald_law(eta_d)["genuine_fraction"]
    f = int(fusions)
    if not 0 <= f <= 4096:
        raise ResourceLimit("fusions in [0, 4096]")
    return dict(fusions=f, all_genuine=g ** f, at_least_one_false=1 - g ** f)


def loss_plan(sites):
    b = budget()
    n = int(sites)
    det = DECLARED_STAGES[-1][1]
    return dict(schema="native-loss-budget-v1", author="Monty", status="BUDGET_DECLARED", sites=n,
                stages=[dict(stage=r["stage"], transmission=str(r["transmission"]), loss_db_approx=r["loss_db_approx"]) for r in b["stages"]],
                eta_per_site=str(b["eta"]), loss_db_approx=b["loss_db_approx"],
                all_sites_survive=str(site_survival(b["eta"], n)["all_survive"]) if n <= 64 else f"({b['eta']})^{n}",
                fusion=dict(detector_side_efficiency=str(det), **{k: str(v) for k, v in false_herald_law(det).items() if k != "eta_d"}),
                fusions_for_chain=max(n - 2, 0),
                all_heralds_genuine=str(fusion_chain_fidelity(det, max(n - 2, 0))["all_genuine"]) if n <= 66
                else f"({false_herald_law(det)['genuine_fraction']})^{n - 2}",
                exact_laws=["eta = product of stage transmissions", "all N survive: eta^N",
                            "L1: P(one click) = eta_d(2-eta_d)/2, genuine eta_d/2, false fraction (1-eta_d)/(2-eta_d)",
                            "chain of F fusions all genuine: (1/(2-eta_d))^F",
                            "loss on surviving rails is a missing readout click, never a wrong outcome"],
                boundaries=["every transmission is declared; none measured", "detector dark counts and afterpulsing not modelled",
                            "false heralds need photon-number resolution or lower loss to suppress; multiplexing note handles rates",
                            "nothing here changes the temperature verdict"])


def loss_grade(record, tolerance=Fraction(1, 10)):
    """Fail-closed: BUDGET_DECLARED -> STAGES_RECORDED (every declared stage has a
    LAB_RECORDED transmission) -> END_TO_END_RECORDED (LAB_RECORDED Klyshko-derived
    end-to-end efficiency) -> BUDGET_CONSISTENT (end-to-end within tolerance of the
    stage product, and not above it by more than tolerance)."""
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    reasons = []
    stages = record.get("stages")
    names = [n for n, _ in DECLARED_STAGES]
    ok = type(stages) is dict and all(type(stages.get(n)) is dict and stages[n].get("evidence_class") == "LAB_RECORDED"
                                      and stages[n].get("transmission") is not None for n in names)
    if not ok:
        reasons.append("every declared stage needs a LAB_RECORDED transmission")
        return dict(grade="BUDGET_DECLARED", reasons=reasons)
    product = Fraction(1)
    for n in names:
        product *= _unit(stages[n]["transmission"], n)
    e2e = record.get("end_to_end")
    if not (type(e2e) is dict and e2e.get("evidence_class") == "LAB_RECORDED" and e2e.get("efficiency") is not None):
        reasons.append("end-to-end block incomplete or not LAB_RECORDED")
        return dict(grade="STAGES_RECORDED", reasons=reasons, stage_product=product)
    eff = _unit(e2e["efficiency"], "end-to-end efficiency")
    if abs(eff - product) > tolerance * product:
        reasons.append(f"end-to-end {eff} not within tolerance of stage product {product}")
        return dict(grade="END_TO_END_RECORDED", reasons=reasons, stage_product=product, end_to_end=eff)
    return dict(grade="BUDGET_CONSISTENT", reasons=reasons, stage_product=product, end_to_end=eff)
