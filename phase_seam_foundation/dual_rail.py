"""Dual-rail route for room-temperature operation (v0.18).

One photon per site in two modes, the existing four-heater exchange unit as
the single-site gate, and type-I fusion on a balanced coupler as the two-site
primitive. A small exact boson engine (permanents in the calculator's
Q(zeta_64) field) evaluates few-photon interference, so Hong-Ou-Mandel,
fusion success and the effect of distinguishable photons are exact field
statements, not simulations with rounding.

Nothing here is a loss budget, a fabricated device or a measured visibility.
The plan declares 810 nm and silicon single-photon detectors so that the
temperature verdict of v0.17 can grade a recorded run as room temperature.
"""
from fractions import Fraction
from itertools import combinations_with_replacement, permutations

from native_relational_qc.cyclotomic64 import Cyclotomic64 as F, ZERO, ONE, ZETA
from native_relational_qc.exact import IMAG, INV_SQRT2
from .model import ResourceLimit, integer
from .photonic_response import D as COUPLER, unit_jet, _multiply as _mm
from .temperature_sweep import DETECTOR_OPTIONS, _point

I, H2 = F(IMAG), F(INV_SQRT2)
SQRT2 = ONE / H2
MAX_MODES = 10
MAX_PHOTONS = 4
MAX_PER_MODE = 2
ROUTE_WAVELENGTH_NM = 810
ROUTE_DETECTOR = "si_spad_810"


# ---------------------------------------------------------------- boson engine

def _check_matrix(u):
    if type(u) is not tuple or not 1 <= len(u) <= MAX_MODES or any(type(r) is not tuple or len(r) != len(u) for r in u):
        raise ValueError("square tuple matrix of at most ten modes required")
    return len(u)


def identity(m):
    return tuple(tuple(ONE if r == c else ZERO for c in range(m)) for r in range(m))


def embed(m, pair, block):
    """Place a 2x2 block on modes pair=(p,q) of an m-mode identity."""
    p, q = pair
    integer(p, "mode"); integer(q, "mode")
    if not (0 <= p < m and 0 <= q < m and p != q):
        raise ValueError("distinct modes inside the register required")
    u = [list(r) for r in identity(m)]
    (a, b), (c, d) = block
    u[p][p], u[p][q], u[q][p], u[q][q] = a, b, c, d
    return tuple(tuple(r) for r in u)


def phase(m, mode, steps):
    integer(steps, "phase steps")
    u = [list(r) for r in identity(m)]
    u[mode][mode] = ZETA ** steps
    return tuple(tuple(r) for r in u)


def compose(*factors):
    """Apply factors left to right in time: compose(A, B) = B A."""
    m = _check_matrix(factors[0])
    u = identity(m)
    for f in factors:
        _check_matrix(f)
        u = _mm(f, u)
    return u


def _permanent(rows):
    n = len(rows)
    if n == 0:
        return ONE
    if n > MAX_PHOTONS:
        raise ResourceLimit("at most four photons")
    total = ZERO
    for perm in permutations(range(n)):
        term = ONE
        for r, c in enumerate(perm):
            term = term * rows[r][c]
            if term == ZERO:
                break
        total = total + term
    return total


def _occupation(n, m):
    if type(n) is not tuple or len(n) != m:
        raise ValueError("one occupation per mode required")
    for v in n:
        integer(v, "occupation")
        if not 0 <= v <= MAX_PER_MODE:
            raise ResourceLimit("occupations above two per mode are outside this engine")
    if sum(n) > MAX_PHOTONS:
        raise ResourceLimit("at most four photons")
    return n


def _norm(n):
    # 1/sqrt(prod n_k!) with n_k <= 2: one factor 1/sqrt2 per doubly occupied mode
    f = ONE
    for v in n:
        if v == 2:
            f = f * H2
    return f


def fock_amplitude(u, n_in, n_out):
    """<n_out| U |n_in> = perm(U[out,in]) / sqrt(prod n_in! prod n_out!)."""
    m = _check_matrix(u)
    n_in, n_out = _occupation(n_in, m), _occupation(n_out, m)
    if sum(n_in) != sum(n_out):
        return ZERO
    cols = [k for k in range(m) for _ in range(n_in[k])]
    rows = [k for k in range(m) for _ in range(n_out[k])]
    sub = [[u[r][c] for c in cols] for r in rows]
    return _permanent(sub) * _norm(n_in) * _norm(n_out)


def _patterns(m, photons):
    seen = set()
    for combo in combinations_with_replacement(range(m), photons):
        occ = [0] * m
        for k in combo:
            occ[k] += 1
        t = tuple(occ)
        if t not in seen:
            seen.add(t)
            yield t


def _factorial_product(n):
    f = 1
    for v in n:
        for k in range(2, v + 1):
            f *= k
    return f


def _scaled_amplitude(u, n_in, n_out, m):
    """sqrt(prod n_out!) * <n_out|U|n_in>, which stays in the field for any n_out."""
    cols = [k for k in range(m) for _ in range(n_in[k])]
    rows = [k for k in range(m) for _ in range(n_out[k])]
    return _permanent([[u[r][c] for c in cols] for r in rows]) * _norm(n_in)


def evolve(u, state, *, overflow=None):
    """Evolve {occupation: amplitude} exactly through the mode unitary u.

    Output patterns with at most two photons per mode are returned with exact
    amplitudes. A pattern with three or more photons in one mode has an
    amplitude outside the field (sqrt(3!)); its exact probability is added to
    overflow[0] when a one-element list is supplied, and otherwise raises.
    """
    m = _check_matrix(u)
    out = {}
    photons = None
    for n_in in state:
        _occupation(n_in, m)
        photons = sum(n_in) if photons is None else photons
        if sum(n_in) != photons:
            raise ValueError("fixed photon number required")
    for n_out in _patterns(m, photons):
        scaled = ZERO
        for n_in, amp in state.items():
            scaled = scaled + amp * _scaled_amplitude(u, n_in, n_out, m)
        if scaled == ZERO:
            continue
        if max(n_out) <= MAX_PER_MODE:
            out[n_out] = scaled * _norm(n_out)
        elif overflow is not None:
            overflow[0] = overflow[0] + scaled.norm2() / F.coerce(_factorial_product(n_out))
        else:
            raise ResourceLimit("three or more photons in one output mode; pass overflow=[ZERO] to account for them")
    return out


def total_probability(state):
    return sum((a.norm2() for a in state.values()), ZERO)


# ----------------------------------------------------------- dual-rail objects

def rails(site):
    integer(site, "site")
    return 2 * site, 2 * site + 1


def encode(bits, m):
    """Fock occupation of a dual-rail computational basis string."""
    occ = [0] * m
    for site, b in enumerate(bits):
        if b not in (0, 1):
            raise ValueError("bits must be 0 or 1")
        occ[rails(site)[b]] = 1
    return tuple(occ)


def unit_matrix(theta_steps, *, m=2, pair=(0, 1)):
    """The v0.12 four-heater word at the native exchange target, as a mode block."""
    u, _ = unit_jet(_point(theta_steps))
    return embed(m, pair, u)


def single_site_euler(theta_steps, b_steps, a_steps):
    """Theorem D1 witness: word(l,u,b,a) = diag(1,z^{a+16}) * [H diag(1,e^{-i theta}) H] * diag(1,z^{b+16}).

    The middle factor is e^{-i theta/2} R_x(theta) and the diagonal factors are
    Z rotations up to global phase, so the unit realises a Z-X-Z Euler
    decomposition: every single-site unitary, at continuous angles.
    """
    for s in (b_steps, a_steps):
        integer(s, "trim steps")
        if not -64 <= s <= 64:
            raise ValueError("trim steps outside [-64,64]")
    l, u_, _, _ = _point(theta_steps)
    word, _ = unit_jet((l, u_, b_steps, a_steps))
    hx = ((ONE, ZERO), (ZERO, ZETA ** (-theta_steps)))
    hadamard = ((H2, H2), (H2, -H2))
    middle = _mm(_mm(hadamard, hx), hadamard)
    left = ((ONE, ZERO), (ZERO, ZETA ** (a_steps + 16)))
    right = ((ONE, ZERO), (ZERO, ZETA ** (b_steps + 16)))
    expected = _mm(_mm(left, middle), right)
    return all(word[r][c] == expected[r][c] for r in range(2) for c in range(2))


def hom_from_engine(theta_steps):
    """Two photons on one exchange unit, one per input mode, via the boson engine."""
    u = unit_matrix(theta_steps)
    out = evolve(u, {(1, 1): ONE})
    return dict(coincidence=out.get((1, 1), ZERO).norm2(),
                bunched=(out.get((2, 0), ZERO).norm2() + out.get((0, 2), ZERO).norm2()))


# ----------------------------------------------------------------- fusion gate

FUSION_MODES = 8  # A'0 A'1 | a0 a1 | b0 b1 | B'0 B'1
MEASURED = (3, 4)  # a1 and b0 meet on the balanced coupler and are detected


def bell_pairs_state():
    """|Phi+>_{A'A} (x) |Phi+>_{BB'} as a dual-rail Fock superposition (8 modes, 4 photons)."""
    state = {}
    for x in (0, 1):
        for y in (0, 1):
            occ = [0] * FUSION_MODES
            occ[0 + x] = 1; occ[2 + x] = 1      # A' and A share x
            occ[4 + y] = 1; occ[6 + y] = 1      # B and B' share y
            state[tuple(occ)] = F.coerce(Fraction(1, 2))
    return state


def fusion_matrix():
    return embed(FUSION_MODES, MEASURED, COUPLER)


def fusion_outcomes(state=None):
    """Exact type-I fusion: coupler on (a1, b0), detect both; classify every pattern.

    success: exactly one photon on the detected pair; the remaining three
    photons form a dual-rail register on (A', C=(a0,b1), B'). failure: zero or
    two detected photons. Returns probabilities and the post-selected states.
    """
    state = bell_pairs_state() if state is None else state
    out = evolve(fusion_matrix(), state)
    success, failure = {}, {}
    for occ, amp in out.items():
        k = occ[MEASURED[0]] + occ[MEASURED[1]]
        (success if k == 1 else failure)[occ] = amp
    return dict(success_probability=total_probability(success),
                failure_probability=total_probability(failure),
                success=success, failure=failure)


def _register_state(branch, click_mode):
    """Three-site dual-rail amplitudes (A', C, B') for one detector click."""
    reg = {}
    for occ, amp in branch.items():
        if occ[click_mode] != 1:
            continue
        ap = 0 if occ[0] else 1
        c = 0 if occ[2] else 1          # C = (a0, b1): photon in a0 -> |0>, in b1 -> |1>
        bp = 0 if occ[6] else 1
        if occ[0] + occ[1] != 1 or occ[2] + occ[5] != 1 or occ[6] + occ[7] != 1:
            raise ValueError("success branch is not a dual-rail register")
        reg[(ap, c, bp)] = reg.get((ap, c, bp), ZERO) + amp
    return reg


def _phase_steps(value):
    for k in range(64):
        if value == ZETA ** k:
            return k
    return None


def ghz_merge():
    """Theorem D2 witness: each click heralds a 3-site GHZ state up to a known Z phase.

    The heralded relative phase is a power of zeta_64 (here +-pi/2); feeding it
    forward as a Z rotation on one site gives <XXX> = 1 exactly.
    """
    res = fusion_outcomes()
    report = dict(success_probability=res["success_probability"], clicks={})
    for click in MEASURED:
        reg = _register_state(res["success"], click)
        p = sum((a.norm2() for a in reg.values()), ZERO)
        a000, a111 = reg.get((0, 0, 0), ZERO), reg.get((1, 1, 1), ZERO)
        others = [k for k in reg if k not in ((0, 0, 0), (1, 1, 1))]
        ratio = a111 / a000 if a000 != ZERO else None
        k = _phase_steps(ratio) if ratio is not None else None
        corrected = None
        if k is not None and p != ZERO:
            c = a000.conjugate() * a111 * ZETA ** (-k)
            corrected = (c + c.conjugate()) / p
        report["clicks"][click] = dict(probability=p, support_is_ghz=not others,
                                       heralded_phase_steps=k, equal_weights=a000.norm2() == a111.norm2(),
                                       corrected_xxx=corrected)
    return report


def distinguishable_fusion(phases=None):
    """Negative control: photon from A and photon from B in different internal modes.

    Species are evolved independently through the same mode unitary; a
    detector sees only the total count. The same feed-forward phases as the
    indistinguishable case are applied. Success stays 1/2; the corrected
    <XXX> collapses to zero because (000) and (111) never share a species in C.
    """
    phases = phases or {c: v["heralded_phase_steps"] for c, v in ghz_merge()["clicks"].items()}
    u = fusion_matrix()
    pairs = {}
    for x in (0, 1):
        s1 = [0] * FUSION_MODES; s1[x] = 1; s1[2 + x] = 1
        for y in (0, 1):
            s2 = [0] * FUSION_MODES; s2[4 + y] = 1; s2[6 + y] = 1
            pairs[(tuple(s1), tuple(s2))] = F.coerce(Fraction(1, 2))
    joint = {}
    for (n1, n2), amp in pairs.items():
        e1 = evolve(u, {n1: ONE}); e2 = evolve(u, {n2: ONE})
        for o1, a1 in e1.items():
            for o2, a2 in e2.items():
                joint[(o1, o2)] = joint.get((o1, o2), ZERO) + amp * a1 * a2
    success_p, coherence = ZERO, ZERO
    for click in MEASURED:
        reg = {}
        for (o1, o2), amp in joint.items():
            tot = tuple(a + b for a, b in zip(o1, o2))
            if tot[MEASURED[0]] + tot[MEASURED[1]] != 1 or tot[click] != 1:
                continue
            success_p = success_p + amp.norm2()
            (key,) = _register_state({tot: ONE}, click)
            species_in_c = 1 if o1[2] + o1[5] == 1 else 2
            reg[(key, species_in_c)] = reg.get((key, species_in_c), ZERO) + amp
        for sp in (1, 2):
            a0 = reg.get(((0, 0, 0), sp), ZERO); a1 = reg.get(((1, 1, 1), sp), ZERO)
            c = a0.conjugate() * a1 * ZETA ** (-phases[click])
            coherence = coherence + c + c.conjugate()
    return dict(success_probability=success_p,
                corrected_xxx=coherence / success_p if success_p != ZERO else None)


def corrected_witness(report):
    """Feed-forward-corrected <XXX> averaged over the two heralding clicks."""
    num, den = ZERO, ZERO
    for c in report["clicks"].values():
        if c["probability"] == ZERO or c["corrected_xxx"] is None:
            continue
        num = num + c["probability"] * c["corrected_xxx"]
        den = den + c["probability"]
    return num / den


def visibility_law(visibility):
    """Mixture model: weight V indistinguishable, 1-V distinguishable.

    Heralded success probability is 1/2 in both components, so the corrected
    GHZ witness <XXX> of the merged register equals V exactly. V is the HOM
    visibility the temperature sweep records at every point.
    """
    v = Fraction(visibility)
    if not 0 <= v <= 1:
        raise ValueError("visibility in [0,1]")
    ind = ghz_merge()
    dis = distinguishable_fusion({c: x["heralded_phase_steps"] for c, x in ind["clicks"].items()})
    w_ind, w_dis = corrected_witness(ind), (dis["corrected_xxx"] or ZERO)
    p_ind, p_dis = ind["success_probability"], dis["success_probability"]
    p = F.coerce(v) * p_ind + F.coerce(1 - v) * p_dis
    w = (F.coerce(v) * p_ind * w_ind + F.coerce(1 - v) * p_dis * w_dis) / p
    return dict(visibility=v, success_probability=p, xxx_witness=w,
                witness_equals_visibility=w == F.coerce(v))


# ------------------------------------------------------------------- the plan

def room_temperature_plan(sites):
    """Declared room-temperature route for N dual-rail sites."""
    n = integer(sites, "sites")
    if not 1 <= n <= 1 << 20:
        raise ValueError("sites in [1, 2^20]")
    det = next(o for o in DETECTOR_OPTIONS if o["option"] == ROUTE_DETECTOR)
    return dict(schema="native-dual-rail-plan-v1", author="Monty", status="DECLARED_DESIGN",
                sites=n, modes=2 * n, photons_per_shot=n,
                single_site_gate="four-heater exchange unit per site (Z-X-Z Euler, Theorem D1)",
                heaters_single_site=4 * n,
                two_site_primitive="type-I fusion on one balanced coupler, heralded success 1/2 (Theorem D2)",
                fusion_couplers_per_entangling_step=1,
                wavelength_nm=ROUTE_WAVELENGTH_NM, detector=det,
                source="degenerate SPDC pairs near 810 nm from a 405 nm pump; heralded",
                thermal_class_target="ROOM_TEMPERATURE",
                measurement_order=["bright-light calibration", "heralded g2(0)", "HOM visibility V at one unit",
                                   "single-site protocol", "fusion of two heralded pairs: success rate and <XXX> against V",
                                   "temperature sweep of all of the above"],
                claim_boundary=["loss, multi-pair emission and detector efficiency are not modelled: success 1/2 is the lossless identity",
                                "fusion is heralded and probabilistic; a computer needs multiplexing or a fusion network, not supplied here",
                                "no fabricated 810 nm core exists; the v0.11 GDS targets 1550 nm",
                                "the temperature verdict grades only recorded logs"])
