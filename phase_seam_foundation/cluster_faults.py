"""Storage and declared fault scores (v0.33), source coherence corrected in v0.34.

The storage and switch calculations are unchanged. The original P1 claim
that loss removes every off-diagonal term was incorrect: equal environment
occupations retain coherence. The source channel now comes from an exact
partial trace in source_distillation. The old independent zero-response
score is labelled a toy model, never a certified 13-node witness bound.
"""
from fractions import Fraction

from native_relational_qc.cyclotomic64 import Cyclotomic64 as F, ZERO, ONE, ZETA

from .cluster_build import online_ledger, star_plan
from .cluster_compile import NODES
from .fusion_network import FUSION_SUCCESS, _solve
from .ledger_violations import allowed_wrong_fraction, dark_readout_site
from .loss_ledger import native_transmission_grid
from .model import ResourceLimit, integer, rational
from .tree_build import star
from .source_distillation import double_pair_channel, fused_double_pair_channel, source_sector

MERGE_PHOTON_ROUNDS = 119          # 20 + 19 + ... + 14: photons stored during the seven sequential merges
GRADES = ("FAULTS_DECLARED", "SOURCE_RECORDED", "NODE_FAULTS_RECORDED")


def _unit(v, label):
    v = rational(Fraction(str(v)) if type(v) is str else v, label, 256)
    if not 0 <= v <= 1:
        raise ValueError(f"{label} in [0, 1]")
    return v


# ------------------------------------------------------------------ Theorem S1: growth with storage

def star_growth_with_storage(size, memory, start=3, success=FUSION_SUCCESS):
    """The v0.22 walk (L -> L+2 at s, L -> L-1 at 1-s, fresh 3-site resource each round)
    with every stored photon surviving a round with probability m. Joint probability of
    reaching `size` with every stored photon alive at every round, exactly; m = 1
    reproduces star()'s p_reach. Fresh resources are taken lossless at arrival (declared)."""
    n, m, s = integer(size, "size"), _unit(memory, "memory"), _unit(success, "success")
    start = integer(start, "start")
    if not 1 <= start <= n <= 256:
        raise ValueError("1 <= start <= size <= 256")
    if n == start:          # the 3-site resource itself is the primitive (star(3): p_reach 1, no stored rounds)
        return dict(size=n, memory=m, start=start, p_reach_and_survive=Fraction(1), p_reach_lossless=Fraction(1), survival_factor=Fraction(1))
    inner = list(range(1, n))
    idx = {L: i for i, L in enumerate(inner)}
    a = [[Fraction(0)] * len(inner) for _ in inner]
    b = [Fraction(0)] * len(inner)
    for L in inner:
        i = idx[L]
        a[i][i] += 1
        keep = m ** L
        up = min(L + 2, n)
        if up >= n:
            b[i] += s * keep
        else:
            a[i][idx[up]] -= s * keep
        if L - 1 >= 1:
            a[i][idx[L - 1]] -= (1 - s) * keep
    hit = _solve(a, b)
    lossless = star(n, s)["p_reach"] if n >= 3 else Fraction(1)
    return dict(size=n, memory=m, start=start, p_reach_and_survive=hit[idx[start]], p_reach_lossless=lossless,
                survival_factor=hit[idx[start]] / lossless if lossless else None)


def assembly_storage(memory):
    """Success path of the seven sequential merges: 20, 19, ..., 14 photons stored one round each."""
    m = _unit(memory, "memory")
    plan = star_plan()
    rounds = sum(plan["photons_before"] - j for j in range(plan["fusions"]))
    if rounds != MERGE_PHOTON_ROUNDS:
        raise ArithmeticError("merge storage count changed")
    stars = {str(c): star_growth_with_storage(st["size"], m) for c, st in plan["stars"].items() if st["size"] >= 3}
    bell = sum(1 for st in plan["stars"].values() if st["size"] == 2)
    return dict(memory=m, merge_photon_rounds=rounds, merge_success_path_survival=m ** rounds,
                stars_with_storage=stars, bell_pairs=bell,
                candidate_success_with_storage=Fraction(1, 2) ** plan["fusions"] * m ** rounds,
                note="stars finished simultaneously (declared); finished-star waiting not charged; a lost photon is a missing click and rejects the run")


# ------------------------------------------------------------------ switches and buffers

def switch_buffer(k_switch, k_buffer, photons=NODES):
    """Declared transmissions on the native grid: one switch pass and one buffer pass per
    delivered photon. Returns the exact grid elements and the multiplier on acceptance."""
    grid = native_transmission_grid()
    ks, kb = integer(k_switch, "switch grid index"), integer(k_buffer, "buffer grid index")
    n = integer(photons, "photons")
    if not (0 <= ks <= 16 and 0 <= kb <= 16 and 1 <= n <= 4096):
        raise ValueError("grid indices in [0, 16], photons in [1, 4096]")
    eta = grid[ks]["eta"] * grid[kb]["eta"]
    factor = eta ** n
    lo, hi = factor.real_bounds(30)
    return dict(k_switch=ks, k_buffer=kb, per_photon=eta, photons=n, acceptance_multiplier=factor, bounds=(lo, hi),
                switch_bounds=(grid[ks]["lower"], grid[ks]["upper"]), buffer_bounds=(grid[kb]["lower"], grid[kb]["upper"]))


def acceptance_with_switches(memory, detector_efficiency, k_switch, k_buffer):
    base = online_ledger(memory, detector_efficiency)
    sw = switch_buffer(k_switch, k_buffer)
    lo, hi = sw["bounds"]
    return dict(base_acceptance=base["acceptance"], switch_buffer_bounds=(lo, hi),
                acceptance_bounds=(base["acceptance"] * lo, base["acceptance"] * hi))


# ------------------------------------------------------------------ Theorem P1: double pair, one survivor each

def double_pair_survivors(eta):
    """Compatibility entry point for the corrected, environment-resolved channel.

    At eta=0 or 1 the selected event has zero probability and its conditional
    state is None. Diagonal populations alone are not an ensemble decomposition.
    """
    c = double_pair_channel(eta)
    return dict(eta=c["eta"], p_one_survivor_each=c["event_probability"],
                density=c["conditional_density"], unnormalised_density=c["unnormalised_density"],
                coherence=c["conditional_xx"], zz_correlation=c["conditional_zz"],
                bell_fidelity=c["conditional_bell_fidelity"], closed_form_check=True,
                v033_diagonal_mixture_withdrawn=True)


def fused_one_survivor_witness(eta):
    """Corrected P1: success 1/2, conditional XXX=2/3 and GHZ fidelity 3/4.

    The fixed detector correction is applied to each coherent loss branch;
    the one-survivor event still does not produce an ideal Bell resource.
    """
    return fused_double_pair_channel(eta)


def multi_pair_fused_fraction(x, eta):
    """Fraction of selected events originating from a double pair, NOT infidelity.

    This uses a declared one/double-pair mixture, not the thermal source's
    brightness x. The overlap of the double-origin output with the target
    GHZ state is 3/4; its XXX moment is 2/3, rather than zero.
    """
    c = source_sector(x, eta)
    return dict(x=_unit(x, "x"), eta=_unit(eta, "eta"),
                single_event=c["single_event"], double_event=c["double_event"],
                double_fraction=c["double_fraction"], conditional_ghz_fidelity=c["conditional_fidelity"],
                conditional_xxx=c["conditional_xx"], first_order=c["first_order_double_fraction"],
                eta_independent_to_first_order=False)


def number_resolving_herald(x, herald_efficiency):
    """Fraction of accepted single-click heralds that carry a double pair when the herald
    detector counts photons with efficiency eta_h: 2x(1-eta_h) / ((1-x) + 2x(1-eta_h))."""
    xv, eh = _unit(x, "x"), _unit(herald_efficiency, "herald efficiency")
    single = (1 - xv) * eh
    double = xv * 2 * eh * (1 - eh)
    return dict(x=xv, herald_efficiency=eh, double_pair_fraction_given_one_click=double / (single + double) if single + double else None,
                threshold_herald_fraction=xv, catches_all_at_unit_efficiency=True)


def allowed_x(target_witness, sites, eta, herald_efficiency=None):
    """Legacy independent zero-response SCORE threshold, not a cluster witness bound.

    Largest declared double-pair mixture weight whose double-origin fraction
    keeps that toy score >= target
    on `sites` nodes: x <= f / (f + 4(1-eta)^2 (1-f)) with f the allowed wrong fraction;
    with a number-resolving herald the effective x is 2x(1-eta_h)/(...) and the bound loosens."""
    f_lo, f_hi = allowed_wrong_fraction(target_witness, sites)["max_wrong_fraction_bounds"]
    e = _unit(eta, "eta")
    def bound(f):
        return f / (f + 4 * (1 - e) ** 2 * (1 - f))
    out = dict(sites=sites, target_witness=Fraction(str(target_witness)), eta=e, x_bounds=(bound(f_lo), bound(f_hi)))
    if herald_efficiency is not None:
        eh = _unit(herald_efficiency, "herald efficiency")
        # effective double-pair fraction x_eff = 2x(1-eh)/((1-x)+2x(1-eh)) <= X  =>  x <= X / (2(1-eh)(1-X) + X)
        def source(xe):
            return xe / (2 * (1 - eh) * (1 - xe) + xe) if eh < 1 else Fraction(1)
        out["with_number_resolving_herald"] = dict(herald_efficiency=eh, x_bounds=(source(bound(f_lo)), source(bound(f_hi))))
    return out


# ------------------------------------------------------------------ the ledger on 13 nodes

def cluster_fault_ledger(*, x="1/40", eta="243/4000", dark_per_mode="1/100000", visibility="9/10", herald_efficiency=None, sites=NODES):
    """Legacy independent zero-response model, retained for numerical comparison.

    Double-origin events are not orthogonal failures. Assigning every such
    event response zero and multiplying over 13 sites is not derived for the
    classifier circuit; nor is combining its pairwise loss with a single-site
    dark-count model. These scores are NOT physical witness bounds.
    """
    xv = _unit(x, "x")
    if herald_efficiency is not None:
        xv = number_resolving_herald(xv, herald_efficiency)["double_pair_fraction_given_one_click"]
        if xv is None:
            return dict(status="NO_HERALDS", toy_score=None, is_physical_witness_bound=False)
    mp = multi_pair_fused_fraction(xv, eta)
    dk = dark_readout_site(eta, dark_per_mode)
    clean = mp["single_event"]*(1-dk["dark"])
    fault = mp["double_event"]*(1-dk["dark"])+dk["accept_wrong"]
    vis = _unit(visibility, "visibility")
    merges = star_plan()["fusions"]
    n = integer(sites, "sites")
    if not 1 <= n <= 4096:
        raise ValueError("sites must be in [1,4096]")
    score = (clean/(clean+fault))**n if clean+fault else None
    return dict(status="UNVALIDATED_INDEPENDENT_ZERO_RESPONSE_MODEL", sites=n,
                inputs=dict(x=_unit(x, "x"), effective_x=xv, eta=mp["eta"], dark=dk["dark"], visibility=vis, herald_efficiency=herald_efficiency),
                per_node=dict(clean_weight=clean, fault_weight=fault,
                              assigned_fault_fraction=fault/(clean+fault) if clean+fault else None),
                toy_score_before_visibility=score, toy_visibility_factor=vis**merges,
                toy_score=score*vis**merges if score is not None else None,
                is_physical_witness_bound=False,
                dominant="multi-pair" if mp["double_event"]*(1-dk["dark"]) > dk["accept_wrong"] else "dark counts")


def ledger_table():
    rows = []
    for x in ("1/40", "1/200", "1/1000"):
        for eh in (None, "9/10"):
            l = cluster_fault_ledger(x=x, herald_efficiency=eh)
            rows.append(dict(x=x, herald=eh or "threshold", assigned_fault_fraction=l["per_node"]["assigned_fault_fraction"], score_before_visibility=l["toy_score_before_visibility"],
                             score=l["toy_score"], dominant=l["dominant"]))
    return rows


# ------------------------------------------------------------------ grader

def fault_grade(record, target_witness="9/10"):
    """Record presence/validity only: full circuit noise propagation is still open.

    Never infer double-pair mixture weight from g2/2 without the matching
    source/conditioning model. Never promote the toy product to a qualified
    physical witness. Synthetic example dictionaries are not lab evidence.
    """
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    _unit(target_witness, "target")
    s = record.get("source")
    if not (type(s) is dict and s.get("evidence_class") == "LAB_RECORDED" and s.get("heralded_g2") is not None
            and s.get("herald_readout") in ("threshold", "number_resolving")):
        return dict(grade="FAULTS_DECLARED", reasons=["source needs recorded g2 and herald readout"])
    g2 = rational(Fraction(s["heralded_g2"]) if type(s["heralded_g2"]) is str else s["heralded_g2"], "g2", 256)
    if not 0 <= g2 < Fraction(1, 2):
        return dict(grade="FAULTS_DECLARED", reasons=["heralded g2 must be in [0,1/2)"])
    if s["herald_readout"] == "number_resolving":
        if s.get("herald_efficiency") is None or _unit(s["herald_efficiency"], "herald efficiency") == 0:
            return dict(grade="FAULTS_DECLARED", reasons=["counting herald needs positive efficiency"])
    n = record.get("nodes")
    fields = ("dark_count_bound", "site_efficiency", "hom_visibility")
    if not (type(n) is dict and n.get("evidence_class") == "LAB_RECORDED" and all(n.get(k) is not None for k in fields)):
        return dict(grade="SOURCE_RECORDED", reasons=["nodes need recorded dark counts, efficiency and visibility"])
    for k in fields:
        _unit(n[k], k)
    return dict(grade="NODE_FAULTS_RECORDED", reasons=[
        "source-conditioning map and circuit-level accepted-output channel required; the v0.33 product is not a witness bound"],
        witness_qualified=False)


def fault_plan():
    p1 = fused_one_survivor_witness("243/4000")
    s1 = assembly_storage("99/100")
    return dict(schema="native-cluster-faults-v2", author="Monty", status="SOURCE_CHANNEL_CORRECTED_CIRCUIT_NOISE_OPEN",
                corrected_p1=p1,
                theorem_s1=dict(merge_success_path_survival_m099=str(s1["merge_success_path_survival"]),
                                star5_survival_factor_m099=str(s1["stars_with_storage"]["6"]["survival_factor"])),
                withdrawn=["P1 diagonal mixture and zero XXX", "eta-independent first-order 4x at arbitrary eta",
                           "13-node product as a physical witness bound", "g2/2 as a general double-pair mixture weight"],
                claims=dict(exact=["S1 chain solve under its stated start policy", "source environment trace", "switch grid"],
                            open=["classifier circuit noise channel", "finished-star waiting", "correlated loss", "source rate at 810 nm"]))
