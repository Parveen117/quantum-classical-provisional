"""Faults on the classifier cluster: storage during growth, switches, multi-pair, dark counts (v0.33).

Four open items of v0.31, each exact and each a rate or an accepted-wrong
fraction, never a fidelity from a loss number:

* Theorem S1: the v0.22 star walk with per-round survival m on every stored
  photon, solved as an absorbing chain; and the success-path storage of the
  seven cluster merges (m^119).
* Switch and buffer transmissions on the native grid cos^2(k pi/32),
  composed into the v0.31 acceptance.
* Theorem P1 (closes the v0.24 declared case): a heralded double pair with
  exactly one survivor at each site is NOT a Bell pair but the classical
  mixture (5|00><00| + 5|11><11| + |01><01| + |10><10|)/12; fused into a
  register it leaves <XXX> = 0 while passing the one-click rule. The accepted
  wrong fraction per pair is 4x(1-eta)^2 / ((1-x) + 4x(1-eta)^2), independent
  of eta to first order: the source x must satisfy x <~ f/4 for a target
  per-node wrong fraction f, or the herald must count photons.
* The per-node ledger on the 13 nodes (Theorem V2) with multi-pair, dark
  counts and visibility, the allowed x, and a fail-closed grader.
"""
from fractions import Fraction

from native_relational_qc.cyclotomic64 import Cyclotomic64 as F, ZERO, ONE, ZETA

from .cluster_build import online_ledger, star_plan
from .cluster_compile import NODES
from .dual_rail import FUSION_MODES, H2, MEASURED, _register_state, _phase_steps, fusion_outcomes, ghz_merge
from .fusion_network import FUSION_SUCCESS, _solve
from .ledger_violations import allowed_wrong_fraction, dark_readout_site, witness_law
from .loss_ledger import native_transmission_grid
from .model import ResourceLimit, integer, rational
from .tree_build import star

MERGE_PHOTON_ROUNDS = 119          # 20 + 19 + ... + 14: photons stored during the seven sequential merges
GRADES = ("FAULTS_DECLARED", "SOURCE_RECORDED", "NODE_FAULTS_RECORDED", "LEDGER_CONSISTENT")


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
    """Exact: the two-pair term (|2,0;2,0> + |1,1;1,1> + |0,2;0,2>)/sqrt3 on rails
    (A'0,A'1;A0,A1), each photon surviving with eta, conditioned on exactly one survivor
    at A' and one at A. Different lost photons are orthogonal environment states, so the
    conditioned state is a classical mixture; weights are exact rationals."""
    e = _unit(eta, "eta")
    # keep 1 of 2 in a mode: amplitude sqrt(2) sqrt(eta (1-eta)); keep 1 of 1: sqrt(eta); lose 1 of 1: sqrt(1-eta)
    w = Fraction(1, 3) * e ** 2 * (1 - e) ** 2
    weights = {(0, 0): 4 * w + w, (1, 1): 4 * w + w, (0, 1): w, (1, 0): w}      # (A' rail, A rail)
    total = sum(weights.values())
    return dict(eta=e, p_one_survivor_each=total, mixture={k: v / total for k, v in weights.items()},
                coherence=Fraction(0), zz_correlation=(weights[(0, 0)] + weights[(1, 1)] - weights[(0, 1)] - weights[(1, 0)]) / total,
                closed_form_check=total == 4 * e ** 2 * (1 - e) ** 2)


def _merge_witness(state):
    """Corrected <XXX> of the register heralded by each click, for an arbitrary 4-photon input."""
    res = fusion_outcomes(state)
    out = {}
    for click in MEASURED:
        reg = _register_state(res["success"], click)
        p = sum((a.norm2() for a in reg.values()), ZERO)
        a000, a111 = reg.get((0, 0, 0), ZERO), reg.get((1, 1, 1), ZERO)
        if p == ZERO:
            out[click] = dict(probability=p, corrected_xxx=None)
            continue
        if a000 == ZERO or a111 == ZERO:
            out[click] = dict(probability=p, corrected_xxx=ZERO)
            continue
        k = _phase_steps(a111 / a000)
        c = a000.conjugate() * a111 * (ZETA ** (-k) if k is not None else ONE)
        out[click] = dict(probability=p, corrected_xxx=(c + c.conjugate()) / p, phase_steps=k)
    return dict(success_probability=res["success_probability"], clicks=out)


def fused_one_survivor_witness(eta):
    """Each mixture component (a product state on A'A) with a good Bell pair BB' through the
    exact type-I fusion: the heralded success probability stays 1/2 but the corrected
    <XXX> is 0 for every component, so the mixture gives 0. Positive control: the
    genuine Bell pair gives 1 (Theorem D2)."""
    mix = double_pair_survivors(eta)
    rows = {}
    xxx = ZERO
    for (ra, rb), weight in mix["mixture"].items():
        state = {}
        for y in (0, 1):
            occ = [0] * FUSION_MODES
            occ[0 + ra] = 1; occ[2 + rb] = 1          # product state on A' and A
            occ[4 + y] = 1; occ[6 + y] = 1            # good Bell pair on B, B'
            state[tuple(occ)] = H2                    # amplitude 1/sqrt2 per Bell branch
        w = _merge_witness(state)
        rows[(ra, rb)] = dict(weight=weight, success=w["success_probability"],
                              corrected_xxx={c: v["corrected_xxx"] for c, v in w["clicks"].items()})
        for c, v in w["clicks"].items():
            if v["corrected_xxx"] is not None:
                xxx = xxx + F.coerce(weight) * v["probability"] * v["corrected_xxx"]
    good = ghz_merge()
    control = sum((v["probability"] * v["corrected_xxx"] for v in good["clicks"].values()), ZERO) / good["success_probability"]
    return dict(eta=mix["eta"], components=rows, mixture_corrected_xxx=xxx, every_success_half=all(r["success"] == H2 * H2 for r in rows.values()),
                positive_control_bell_pair_xxx=control, one_survivor_is_wrong_in_a_fused_register=xxx == ZERO and control == ONE)


def multi_pair_fused_fraction(x, eta):
    """Per heralded pair with number-resolving readout at both sites: right = (1-x) eta^2
    (single pair, both survive); accepted-wrong = x * 4 eta^2 (1-eta)^2 (double pair, one
    survivor each, Theorem P1); four survivors and other patterns are rejected by the
    one-click rule. wrong fraction = 4x(1-eta)^2 / ((1-x) + 4x(1-eta)^2)."""
    xv, e = _unit(x, "x"), _unit(eta, "eta")
    right = (1 - xv) * e ** 2
    wrong = xv * double_pair_survivors(e)["p_one_survivor_each"]
    frac = wrong / (right + wrong) if right + wrong else None
    return dict(x=xv, eta=e, accept_right=right, accept_wrong=wrong, wrong_fraction=frac,
                first_order="4x", eta_independent_to_first_order=True)


def number_resolving_herald(x, herald_efficiency):
    """Fraction of accepted single-click heralds that carry a double pair when the herald
    detector counts photons with efficiency eta_h: 2x(1-eta_h) / ((1-x) + 2x(1-eta_h))."""
    xv, eh = _unit(x, "x"), _unit(herald_efficiency, "herald efficiency")
    single = (1 - xv) * eh
    double = xv * 2 * eh * (1 - eh)
    return dict(x=xv, herald_efficiency=eh, double_pair_fraction_given_one_click=double / (single + double) if single + double else None,
                threshold_herald_fraction=xv, catches_all_at_unit_efficiency=True)


def allowed_x(target_witness, sites, eta, herald_efficiency=None):
    """Largest source x whose multi-pair wrong fraction alone keeps the V2 witness >= target
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
    """Per-node accepted-right / accepted-wrong from multi-pair (Theorem P1), dark counts
    (dark_readout_site) and the V2 law on the 13 nodes; visibility enters the seven merges
    through the mixture law (witness V per merge). All inputs declared."""
    xv = _unit(x, "x")
    if herald_efficiency is not None:
        xv = number_resolving_herald(xv, herald_efficiency)["double_pair_fraction_given_one_click"]
    mp = multi_pair_fused_fraction(xv, eta)
    dk = dark_readout_site(eta, dark_per_mode)
    right = mp["accept_right"] * (1 - dk["dark"])
    wrong = mp["accept_wrong"] * (1 - dk["dark"]) + dk["accept_wrong"]
    v2 = witness_law(right, wrong, sites)
    vis = _unit(visibility, "visibility")
    merges = star_plan()["fusions"]
    return dict(sites=sites, inputs=dict(x=str(Fraction(str(x))), effective_x=xv, eta=mp["eta"], dark=dk["dark"], visibility=vis, herald_efficiency=herald_efficiency),
                per_node=dict(accept_right=right, accept_wrong=wrong, wrong_fraction=wrong / (right + wrong), multi_pair_share=mp["accept_wrong"] * (1 - dk["dark"]) / wrong if wrong else None),
                witness_multi_pair_and_dark=v2["witness"], accepted_probability=v2["accepted_probability"],
                visibility_witness_bound=vis ** merges, merges=merges,
                combined_witness_bound=v2["witness"] * vis ** merges,
                dominant="multi-pair" if mp["accept_wrong"] * (1 - dk["dark"]) > dk["accept_wrong"] else "dark counts")


def ledger_table():
    rows = []
    for x in ("1/40", "1/200", "1/1000"):
        for eh in (None, "9/10"):
            l = cluster_fault_ledger(x=x, herald_efficiency=eh)
            rows.append(dict(x=x, herald=eh or "threshold", wrong_fraction=l["per_node"]["wrong_fraction"], witness=l["witness_multi_pair_and_dark"],
                             combined=l["combined_witness_bound"], dominant=l["dominant"]))
    return rows


# ------------------------------------------------------------------ grader

def fault_grade(record, target_witness="9/10"):
    """Fail-closed: FAULTS_DECLARED -> SOURCE_RECORDED (LAB_RECORDED heralded_g2 < 1/2 and
    herald readout with efficiency) -> NODE_FAULTS_RECORDED (LAB_RECORDED dark_count_bound,
    site efficiency, HOM visibility) -> LEDGER_CONSISTENT (the computed combined witness
    bound from the recorded inputs reaches the target on the 13 nodes)."""
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    reasons = []
    s = record.get("source")
    if not (type(s) is dict and s.get("evidence_class") == "LAB_RECORDED" and s.get("heralded_g2") is not None
            and s.get("herald_readout") in ("threshold", "number_resolving")):
        reasons.append("source block needs LAB_RECORDED heralded_g2 and herald_readout")
        return dict(grade="FAULTS_DECLARED", reasons=reasons)
    g2 = _unit(s["heralded_g2"], "g2") if Fraction(str(s["heralded_g2"])) <= 1 else Fraction(str(s["heralded_g2"]))
    if g2 >= Fraction(1, 2):
        return dict(grade="FAULTS_DECLARED", reasons=["heralded g2 must be below 1/2"])
    if s["herald_readout"] == "number_resolving" and s.get("herald_efficiency") is None:
        return dict(grade="FAULTS_DECLARED", reasons=["number-resolving herald needs herald_efficiency"])
    n = record.get("nodes")
    if not (type(n) is dict and n.get("evidence_class") == "LAB_RECORDED" and n.get("dark_count_bound") is not None
            and n.get("site_efficiency") is not None and n.get("hom_visibility") is not None):
        reasons.append("nodes block needs LAB_RECORDED dark_count_bound, site_efficiency, hom_visibility")
        return dict(grade="SOURCE_RECORDED", reasons=reasons)
    x = g2 / 2                                             # g2 = 2x for the heralded source (SOURCE_SPEC_810.md)
    led = cluster_fault_ledger(x=x, eta=n["site_efficiency"], dark_per_mode=n["dark_count_bound"], visibility=n["hom_visibility"],
                               herald_efficiency=s.get("herald_efficiency") if s["herald_readout"] == "number_resolving" else None)
    target = _unit(target_witness, "target")
    if led["combined_witness_bound"] < target:
        reasons.append(f"combined witness bound {float(led['combined_witness_bound']):.4f} below target {float(target):.4f}; dominant: {led['dominant']}")
        return dict(grade="NODE_FAULTS_RECORDED", reasons=reasons, ledger=led)
    return dict(grade="LEDGER_CONSISTENT", reasons=reasons, ledger=led)


def fault_plan():
    p1 = fused_one_survivor_witness("243/4000")
    s1 = assembly_storage("99/100")
    return dict(schema="native-cluster-faults-v1", author="Monty", status="DECLARED_FAULT_LEDGER_NO_DEVICE",
                theorem_p1=dict(one_survivor_wrong_in_fused_register=p1["one_survivor_is_wrong_in_a_fused_register"],
                                wrong_fraction_first_order="4x", design_point_x_1_over_40_fails_on_13_nodes=cluster_fault_ledger()["witness_multi_pair_and_dark"] < Fraction(9, 10)),
                theorem_s1=dict(merge_success_path_survival_m099=str(s1["merge_success_path_survival"]),
                                star5_survival_factor_m099=str(s1["stars_with_storage"]["6"]["survival_factor"])),
                withdrawn="v0.24/v0.25: 'multi-pair one-survivor is accepted and right' holds for a single isolated site only; in a fused register it is accepted and wrong (coherence 0)",
                claims=dict(exact=["S1 chain solve", "P1 mixture and fused witness", "switch grid", "V2 ledger"], never=["device", "measured number", "fidelity from loss"],
                            open=["finished-star waiting", "correlated loss", "source rate at 810 nm (time per Bell pair)"]))
