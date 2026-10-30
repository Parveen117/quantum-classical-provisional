"""810 nm heralded single-photon source for the room-temperature route (v0.20).

Declared source: 405 nm continuous-wave pump, type-II periodically poled KTP,
degenerate pairs at 810 nm, one photon heralds the other, silicon
single-photon diodes. The exact content is the photon statistics of a
two-mode squeezed vacuum under threshold detection: heralded g2(0),
multi-pair contamination, Klyshko efficiency, the Gaussian joint-spectral
purity law, and the all-herald probability for N sources. Every rate,
width and efficiency is a declared input; no source has been built or
measured. A fail-closed grader says what a recorded bench may claim.
"""
from fractions import Fraction

from .model import ResourceLimit, rational
from .temperature_sweep import DETECTOR_OPTIONS

PUMP_NM = 405
SIGNAL_NM = 810
IDLER_NM = 810
GRADES = ("SPEC_DECLARED", "PAIRS_RECORDED", "HERALDED_SINGLE_PHOTON", "INDISTINGUISHABLE", "SOURCE_QUALIFIED")
SINGLE_PHOTON_G2_BOUND = Fraction(1, 2)   # heralded g2(0) below 1/2: non-classical, single-photon regime
DECLARED_G2_TARGET = Fraction(1, 20)       # the operating point this note proposes
DECLARED_VISIBILITY_TARGET = Fraction(9, 10)


def _q(v, label, bits=256):
    if type(v) is str:
        v = Fraction(v)
    return rational(v, label, bits)


def _unit(v, label):
    v = _q(v, label)
    if not 0 <= v <= 1:
        raise ValueError(f"{label} must lie in [0, 1]")
    return v


def energy_conservation(pump_nm=PUMP_NM, signal_nm=SIGNAL_NM, idler_nm=IDLER_NM):
    """1/lambda_p = 1/lambda_s + 1/lambda_i, exact in rationals."""
    p, s, i = (_q(v, n) for v, n in ((pump_nm, "pump"), (signal_nm, "signal"), (idler_nm, "idler")))
    return dict(pump_nm=p, signal_nm=s, idler_nm=i, exact=Fraction(1) / p == Fraction(1) / s + Fraction(1) / i,
                degenerate=s == i)


def pair_distribution(x, n_max):
    """Two-mode squeezed vacuum: p(n) = (1-x) x^n, x = tanh^2 r in [0, 1)."""
    x = _unit(x, "x")
    if x == 1:
        raise ValueError("x must be below 1")
    n_max = int(n_max)
    if n_max > 64:
        raise ResourceLimit("n_max at most 64")
    return [(1 - x) * x ** n for n in range(n_max + 1)]


def mean_pairs(x):
    x = _unit(x, "x")
    return x / (1 - x)


def _s0(z):
    return z / (1 - z)                 # sum_{n>=1} z^n


def _s1(z):
    return z / (1 - z) ** 2            # sum n z^n


def _s2(z):
    return 2 * z ** 2 / (1 - z) ** 3   # sum n(n-1) z^n


def heralded_statistics(x, herald_efficiency=1):
    """Exact conditional statistics of the signal given a threshold herald click.

    Click probability given n pairs is 1-(1-eta)^n. With y = x(1-eta):
    P(click) = (1-x)[S0(x) - S0(y)], <n|click>, <n(n-1)|click> likewise, so
    heralded g2(0) = <n(n-1)> P(click) / <n>^2 exactly. Lossless herald:
    g2 = 2x, P(n>=2 | click) = x. Signal-side loss cancels in g2.
    """
    x = _unit(x, "x")
    eta = _unit(herald_efficiency, "herald efficiency")
    if x == 1 or eta == 0 or x == 0:
        raise ValueError("need 0 < x < 1 and herald efficiency > 0")
    y = x * (1 - eta)
    w = 1 - x
    p_click = w * (_s0(x) - _s0(y))
    m1 = w * (_s1(x) - _s1(y))
    m2 = w * (_s2(x) - _s2(y))
    p_single = w * x * eta                       # exactly one pair and it heralds
    return dict(x=x, herald_efficiency=eta, p_click=p_click, mean_given_click=m1 / p_click,
                g2_heralded=m2 * p_click / m1 ** 2, p_multipair_given_click=1 - p_single / p_click,
                single_photon_regime=m2 * p_click / m1 ** 2 < SINGLE_PHOTON_G2_BOUND)


def klyshko(x, eta_signal, eta_idler):
    """Coincidence and singles under threshold detection; Klyshko ratio C/S_i -> eta_s as x -> 0."""
    x = _unit(x, "x")
    es, ei = _unit(eta_signal, "signal efficiency"), _unit(eta_idler, "idler efficiency")
    if x == 1:
        raise ValueError("x must be below 1")
    w = 1 - x
    s_i = w * (_s0(x) - _s0(x * (1 - ei)))
    s_s = w * (_s0(x) - _s0(x * (1 - es)))
    # coincidence = 1 - P(no s click) - P(no i click) + P(neither)
    c = w * (_s0(x) - _s0(x * (1 - es)) - _s0(x * (1 - ei)) + _s0(x * (1 - es) * (1 - ei)))
    return dict(singles_signal=s_s, singles_idler=s_i, coincidence=c,
                klyshko_signal=c / s_i if s_i else None, klyshko_idler=c / s_s if s_s else None,
                klyshko_overestimates_by=(c / s_i - es) if s_i else None)


def spectral_purity(pump_width, phase_matching_width):
    """Gaussian joint spectral amplitude: Schmidt number K = (a^2 + b^2) / (2ab), purity 1/K.

    a is the pump bandwidth along the sum frequency, b the phase-matching
    bandwidth along the difference frequency (same units, declared). Purity
    is 1 exactly when a = b; filtering the pair narrows b toward a.
    """
    a, b = _q(pump_width, "pump width"), _q(phase_matching_width, "phase-matching width")
    if a <= 0 or b <= 0:
        raise ValueError("widths must be positive")
    k = (a * a + b * b) / (2 * a * b)
    return dict(schmidt_number=k, purity=1 / k, separable=k == 1)


def hom_visibility_bound(purity, x):
    """Two identical heralded sources, single-pair limit: V = purity; multi-pair
    reduces it further, so V <= purity and the recorded V is the number that
    enters dual_rail.visibility_law. The multi-pair penalty is bounded here by
    the conditional two-pair probability x (lossless herald): V >= purity (1 - 2x)
    is NOT claimed; only the upper bound is exact."""
    p = _unit(purity, "purity")
    x = _unit(x, "x")
    return dict(upper_bound=p, single_pair_limit_exact=True, multipair_conditional=x,
                statement="V <= purity; equality in the single-pair, lossless, identical-source limit")


def all_herald_probability(sites, p_herald):
    """N independent sources each heralding with probability p: all N in one shot is p^N exactly."""
    n = int(sites)
    if not 1 <= n <= 1 << 20:
        raise ValueError("sites in [1, 2^20]")
    p = _unit(p_herald, "herald probability")
    if n > 4096:
        return dict(sites=n, p_all=None, log2_p_all_bound=None, note="exponent too large to expand; p^N")
    return dict(sites=n, p_all=p ** n, needs_multiplexing=n > 1)


def operating_table(xs=("1/100", "1/40", "1/20", "1/10", "1/4"), herald_efficiency="1/2"):
    rows = []
    for xv in xs:
        h = heralded_statistics(xv, herald_efficiency)
        rows.append(dict(x=str(h["x"]), p_click=str(h["p_click"]), g2_heralded=str(h["g2_heralded"]),
                         p_multipair_given_click=str(h["p_multipair_given_click"]), single_photon_regime=h["single_photon_regime"]))
    return rows


def source_spec():
    det = next(o for o in DETECTOR_OPTIONS if o["option"] == "si_spad_810")
    e = energy_conservation()
    return dict(schema="native-source-spec-v1", author="Monty", status="SPEC_DECLARED",
                pump=dict(wavelength_nm=PUMP_NM, mode="continuous wave, single longitudinal mode", linewidth="declared at bench",
                          power_mW="declared at bench; pair rate per mW is a measured brightness, not derived here"),
                crystal=dict(material="ppKTP", process="type-II, collinear, degenerate", poling_period_um="declared by vendor for 405 -> 810 + 810",
                             oven_c="heated above room ambient, typically 25 to 60; heating is recorded, never cooling",
                             length_mm="declared; sets phase-matching width b"),
                pairs=dict(signal_nm=SIGNAL_NM, idler_nm=IDLER_NM, energy_conservation_exact=e["exact"], degenerate=e["degenerate"],
                           polarization="orthogonal (type-II); polarizing splitter separates herald and signal"),
                filtering="bandpass at 810 nm on both arms, width chosen to bring b toward a (purity law); single-mode fibre on both arms",
                detector=det, herald="idler click within a declared window heralds one signal photon; threshold detector",
                operating_point=dict(x_target="1/40", g2_target=str(DECLARED_G2_TARGET), visibility_target=str(DECLARED_VISIBILITY_TARGET),
                                     rationale="g2 = 2x lossless; x = 1/40 gives g2 = 1/20 with 1/40 conditional multi-pair"),
                exact_laws=["p(n) = (1-x) x^n", "heralded g2 = 2x (lossless herald), closed form for any herald efficiency",
                            "P(n >= 2 | click) = x (lossless)", "Klyshko ratio C/S_i -> eta_s, exact multi-pair correction",
                            "purity = 2ab / (a^2 + b^2)", "all-herald probability p^N"],
                temperature="pump diode, crystal oven, detectors all at or above the room band floor; crystal oven temperature is itself a sweep variable",
                measured_parameters=None, built=False, boundaries=[
                    "pair rate, brightness, efficiencies and bandwidths are declared, not derived",
                    "HOM visibility is bounded above by purity; its value is measured, not predicted",
                    "N heralded sources succeed together with probability p^N: the fusion network note handles multiplexing",
                    "nothing here changes the temperature verdict, which grades recorded logs only"])


def source_grade(record):
    """Fail-closed grade of a source bench record.

    SPEC_DECLARED floor. PAIRS_RECORDED: LAB_RECORDED singles and coincidence
    with Klyshko efficiencies. HERALDED_SINGLE_PHOTON: recorded heralded g2(0)
    below 1/2. INDISTINGUISHABLE: recorded HOM visibility between two heralded
    photons at or above 1/2 (and the value is carried forward). SOURCE_QUALIFIED:
    all of the above with every source subsystem temperature logged at or above
    the room band floor.
    """
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    reasons = []
    pairs = record.get("pairs")
    if not (type(pairs) is dict and pairs.get("evidence_class") == "LAB_RECORDED" and pairs.get("coincidence_rate_hz") is not None
            and pairs.get("klyshko_signal") is not None):
        reasons.append("pairs block incomplete or not LAB_RECORDED")
        return dict(grade="SPEC_DECLARED", reasons=reasons)
    g2 = record.get("heralded_g2")
    if not (type(g2) is dict and g2.get("evidence_class") == "LAB_RECORDED" and g2.get("value") is not None):
        reasons.append("heralded g2 block incomplete or not LAB_RECORDED")
        return dict(grade="PAIRS_RECORDED", reasons=reasons)
    g2v = _q(g2["value"], "g2")
    if not g2v < SINGLE_PHOTON_G2_BOUND:
        reasons.append(f"heralded g2 {g2v} not below 1/2")
        return dict(grade="PAIRS_RECORDED", reasons=reasons)
    hom = record.get("hom")
    if not (type(hom) is dict and hom.get("evidence_class") == "LAB_RECORDED" and hom.get("visibility") is not None):
        reasons.append("hom block incomplete or not LAB_RECORDED")
        return dict(grade="HERALDED_SINGLE_PHOTON", reasons=reasons)
    v = _unit(hom["visibility"], "visibility")
    if v < Fraction(1, 2):
        reasons.append(f"visibility {v} below 1/2: classical bound not beaten")
        return dict(grade="HERALDED_SINGLE_PHOTON", reasons=reasons)
    temps = record.get("subsystem_temperatures_c")
    floor = Fraction(15)
    if not (type(temps) is dict and temps and all(_q(t, k) >= floor for k, t in temps.items())):
        reasons.append("subsystem temperatures missing or some subsystem below the room band floor")
        return dict(grade="INDISTINGUISHABLE", reasons=reasons, visibility=v)
    return dict(grade="SOURCE_QUALIFIED", reasons=reasons, visibility=v, g2=g2v)
