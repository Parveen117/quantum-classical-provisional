"""Environment-resolved source loss and optical Bell-pair purification (v0.34).

Exact, bounded model; no certified source, experiment or general noise solver.
Loss histories with the SAME environment occupation are added coherently.
The purification device reuses the Fock-derived type-I fusion instrument.
Its noisy round starts with two supplied Bell-diagonal two-photon pairs;
conditioning a raw source on one survivor per site does not supply such pairs.
"""
from fractions import Fraction
from functools import lru_cache
from itertools import product
from math import comb

from .dual_rail import (F, ZERO, ONE, H2, SQRT2, ZETA, COUPLER, compose,
                        embed, encode, evolve, fock_amplitude)
from .model import integer, rational
from .optical_refresh import fusion_merge_certificate

BELL_LABELS = ('phi_plus', 'phi_minus', 'psi_plus', 'psi_minus')
DOUBLE_PAIR = ((2, 0, 2, 0), (1, 1, 1, 1), (0, 2, 0, 2))


def _unit(value, label):
    value = rational(Fraction(value) if type(value) is str else value, label, 256)
    if not 0 <= value <= 1:
        raise ValueError(label + ' must be in [0,1]')
    return value


def _r(value):
    """Require an exactly rational field element, never a numerical projection."""
    v = F.coerce(value)
    if any(v.coefficients[1:]):
        raise ArithmeticError('expected a rational result')
    return v.coefficients[0]


def _weights(values):
    if type(values) not in (tuple, list) or len(values) != 4:
        raise ValueError('four Bell weights in Phi+,Phi-,Psi+,Psi- order required')
    p = tuple(_unit(v, 'Bell weight') for v in values)
    if sum(p) != 1:
        raise ValueError('Bell weights must sum to one')
    return p


def _basis(value):
    if type(value) is not str or value not in ('Z', 'X'):
        raise ValueError('basis must be Z or X')
    return value


def _density(vectors, weight=Fraction(1)):
    size = len(vectors[0])
    return tuple(tuple(sum((v[i]*v[j].conjugate() for v in vectors), ZERO)*weight
                       for j in range(size)) for i in range(size))


@lru_cache(maxsize=1)
def loss_environment_vectors():
    """Unnormalised survivor vectors for losing one photon at each site.

    The common amplitude eta*(1-eta)/sqrt(3) is factored out. Only equal
    four-mode environment occupations interfere; no initial-term label is
    attached to the environment. Binomial creation factors are explicit.
    """
    rows = []
    for lost_a, lost_b in product((0, 1), repeat=2):
        env = encode((lost_a, lost_b), 4)
        vec = [ZERO]*4
        for occ in DOUBLE_PAIR:
            if any(l > n for l, n in zip(env, occ)):
                continue
            survivor = tuple(n-l for n, l in zip(occ, env))
            amplitude = ONE
            for n, l in zip(occ, env):
                amplitude *= SQRT2 if comb(n, l) == 2 else ONE
            a, b = survivor[1], survivor[3]
            vec[2*a+b] += amplitude
        rows.append(dict(environment=env, vector=tuple(vec)))
    return tuple(rows)


def double_pair_channel(eta):
    """Actual partial trace, including off-diagonal terms and zero-event cases."""
    e = _unit(eta, 'eta')
    shape = _density([r['vector'] for r in loss_environment_vectors()], Fraction(1, 12))
    shape = tuple(tuple(_r(v) for v in row) for row in shape)
    event = 4*e**2*(1-e)**2
    return dict(eta=e, event_probability=event,
                unnormalised_density=tuple(tuple(event*v for v in row) for row in shape),
                conditional_density=shape if event else None,
                conditional_bell_weights=(Fraction(3, 4),)+(Fraction(1, 12),)*3 if event else None,
                conditional_xx=Fraction(2, 3) if event else None,
                conditional_yy=Fraction(-2, 3) if event else None,
                conditional_zz=Fraction(2, 3) if event else None,
                conditional_bell_fidelity=Fraction(3, 4) if event else None,
                postselection_is_source_certification=False)


@lru_cache(maxsize=1)
def dilation_certificate():
    """Independent eight-mode, four-photon beam-splitter dilation at eta=1/2.

    Do not use the binomial construction above: obtain amplitudes directly
    from the existing permanent engine, then trace the four environment modes.
    The input vector has norm squared 3, accounted for after the contraction.
    """
    u = compose(*(embed(8, (i, i+4), COUPLER) for i in range(4)))
    vectors = []
    for a, b in product((0, 1), repeat=2):
        env = encode((a, b), 4)
        vectors.append(tuple(sum((fock_amplitude(u, occ+(0,)*4, encode(bits, 4)+env)
                                 for occ in DOUBLE_PAIR), ZERO)
                             for bits in product((0, 1), repeat=2)))
    rho = _density(vectors, Fraction(1, 3))
    rho = tuple(tuple(_r(v) for v in row) for row in rho)
    expected = double_pair_channel(Fraction(1, 2))['unnormalised_density']
    return dict(eta=Fraction(1, 2), density=rho, probability=sum(rho[i][i] for i in range(4)),
                matches_environment_channel=rho == expected, modes=8, photons=4)


def fused_double_pair_channel(eta):
    """Fuse the surviving pair with a good Bell pair using fixed detector phases.

    Each environment vector is retained until after the fusion. Corrections
    are from the instrument, never inferred from the unknown input state.
    """
    source = double_pair_channel(eta)
    if not source['event_probability']:
        return dict(source_event_probability=Fraction(0), fusion_success=None,
                    conditional_xxx=None, conditional_ghz_fidelity=None, clicks=[])
    rows = []
    total = ZERO
    xxx = ZERO
    overlap = ZERO
    for instrument in fusion_merge_certificate():
        vectors = []
        k = instrument['corrected_kraus']
        for branch in loss_environment_vectors():
            out = [ZERO]*8
            for a, b, y, c in product((0, 1), repeat=4):
                out[4*a+2*c+y] += branch['vector'][2*a+b]*H2*k[c][2*b+y]
            vectors.append(tuple(out))
        rho = _density(vectors, Fraction(1, 12))
        p = sum((rho[i][i] for i in range(8)), ZERO)
        moment = sum((rho[i][7-i] for i in range(8)), ZERO)
        fidelity_weight = (rho[0][0]+rho[7][7]+rho[0][7]+rho[7][0])/2
        rows.append(dict(click=instrument['click'], probability=_r(p),
                         conditional_xxx=_r(moment/p), conditional_ghz_fidelity=_r(fidelity_weight/p)))
        total += p; xxx += moment; overlap += fidelity_weight
    return dict(source_event_probability=source['event_probability'], fusion_success=_r(total),
                joint_event_probability=source['event_probability']*_r(total),
                conditional_xxx=_r(xxx/total), conditional_ghz_fidelity=_r(overlap/total), clicks=rows)


def source_sector(single_double_fraction, eta):
    """Diagnostic one-photon-per-site sector of a single/double-pair mixture.

    x is the probability of the stated double-pair state, not thermal pump
    brightness, nor g2/2. Higher pairs, vacuum and herald reweighting excluded.
    This destructive/virtual postselection cannot certify a reusable source.
    """
    x, e = _unit(single_double_fraction, 'double-pair probability'), _unit(eta, 'eta')
    single, double = (1-x)*e**2, x*4*e**2*(1-e)**2
    p = single+double
    w = double/p if p else None
    return dict(single_event=single, double_event=double, event_probability=p,
                double_fraction=w,
                conditional_bell_weights=(1-w/4, w/12, w/12, w/12) if p else None,
                conditional_fidelity=1-w/4 if p else None,
                conditional_xx=1-w/3 if p else None,
                first_order_double_fraction='4*(1-eta)^2*x + O(x^2)',
                source_ready=False)


def bell_density(weights):
    p, z, x, y = _weights(weights)
    a, b, c, d = (p+z)/2, (p-z)/2, (x+y)/2, (x-y)/2
    return ((a, 0, 0, b), (0, c, d, 0), (0, d, c, 0), (b, 0, 0, a))


def _recurrence(p, basis):
    a, z, x, y = p
    if basis == 'X':
        z, x = x, z
    norm = (a+z)**2+(x+y)**2
    q = ((a*a+z*z)/norm, 2*a*z/norm, (x*x+y*y)/norm, 2*x*y/norm)
    if basis == 'X':
        q = (q[0], q[2], q[1], q[3])
    return q, norm/2   # both local type-I parity checks, NOT the CNOT protocol


def purification_step(weights, basis='Z'):
    p, basis = _weights(weights), _basis(basis)
    q, success = _recurrence(p, basis)
    return dict(basis=basis, input_weights=p, output_weights=q, success_probability=success,
                input_fidelity=p[0], output_fidelity=q[0], expected_input_pairs=2/success,
                input_photons=4, detected_photons=2, output_photons=2,
                ideal_supplied_pairs=True)


def purification_schedule(weights, bases='ZXZX'):
    """Balanced recursive supply, retry failed nodes, perfect storage and optics.

    Two independently prepared previous-level pairs feed every attempt. A
    failed node discards both. Earlier successes may wait without loss. This
    is not full-tree restart and is not a rate or a noisy multi-round channel.
    """
    p = _weights(weights)
    if type(bases) is not str or len(bases) > 6 or any(b not in 'ZX' for b in bases):
        raise ValueError('at most six Z/X purification rounds')
    cost = Fraction(1)
    steps = []
    for b in bases:
        q, success = _recurrence(p, b)
        cost = 2*cost/success
        steps.append(dict(basis=b, success_probability=success, output_weights=q,
                          fidelity=q[0], expected_raw_pairs=cost))
        p = q
    return dict(bases=bases, steps=steps, output_weights=p, fidelity=p[0],
                expected_raw_pairs=cost, perfect_storage=True, noisy_rounds_composed=False)


@lru_cache(maxsize=9)
def _local_outputs(a, b):
    """Fock engine for two local sites; -1 denotes vacuum at a site."""
    occ = [0]*4
    if a >= 0: occ[a] = 1
    if b >= 0: occ[2+b] = 1
    return tuple(evolve(embed(4, (1, 2), COUPLER), {tuple(occ): ONE}).items())


def _bell_vector(label):
    # Input order Phi+, Phi-, Psi+, Psi-. Overall Psi- phase is immaterial.
    x, z = label//2, label % 2
    return tuple(((a, a ^ x), H2*(-1 if z and a else 1)) for a in (0, 1))


@lru_cache(maxsize=256)
def _round_trajectories(first, second, mask):
    """Trace lost rails by grouping amplitudes with identical loss environments.

    Returns optical vectors grouped again by the true four detector counts.
    Probabilities m^(4-|mask|)(1-m)^|mask| are factored out.
    """
    environments = {}
    for (a1, b1), c1 in _bell_vector(first):
        for (a2, b2), c2 in _bell_vector(second):
            bits = (a1, a2, b1, b2)
            env = tuple(bits[q] if (mask >> q) & 1 else -1 for q in range(4))
            inputs = tuple(-1 if (mask >> q) & 1 else bits[q] for q in range(4))
            state = environments.setdefault(env, {})
            for oa, ca in _local_outputs(*inputs[:2]):
                for ob, cb in _local_outputs(*inputs[2:]):
                    occ = oa+ob
                    state[occ] = state.get(occ, ZERO)+c1*c2*ca*cb
    result = []
    for env, state in environments.items():
        detectors = {}
        for occ, amp in state.items():
            if amp == ZERO: continue
            true = tuple(occ[i] for i in (1, 2, 5, 6))
            payload = tuple(occ[i] for i in (0, 3, 4, 7))
            detectors.setdefault(true, {})[payload] = amp
        for true, payload in detectors.items():
            result.append((env, true, tuple(payload.items())))
    return tuple(result)


def count_probability(true, observed, efficiency, dark):
    """PNR count plus independent Bernoulli (0 or 1) dark count, per mode."""
    n, r = integer(true, 'true count'), integer(observed, 'observed count')
    if not 0 <= n <= 2 or not 0 <= r <= 3:
        raise ValueError('true counts 0..2; observed counts 0..3')
    d, h = _unit(efficiency, 'efficiency'), _unit(dark, 'dark')
    return _count_probability(n, r, d, h)


def _count_probability(n, r, d, h):
    return sum((Fraction(comb(n, k))*d**k*(1-d)**(n-k)*(h if r-k else 1-h)
                for k in range(n+1) if r-k in (0, 1)), Fraction(0))


@lru_cache(maxsize=256)
def _round_density_terms(first, second, mask):
    """Cache rational channel coefficients before inserting large loss fractions."""
    phases = {r['click']-1: r['correction_phase_steps'] for r in fusion_merge_certificate()}
    groups = {}
    for env, true, payload in _round_trajectories(first, second, mask):
        norm = sum((_r(a.norm2()) for occ, a in payload), Fraction(0))
        for clicks in product((0, 1), repeat=2):
            key = (true, clicks)
            g = groups.setdefault(key, [Fraction(0), {}])
            g[0] += norm
            v = {}
            for occ, amp in payload:
                if occ[0]+occ[1] == 1 and occ[2]+occ[3] == 1:
                    a, b = occ[1], occ[3]
                    v[2*a+b] = amp*ZETA**(phases[clicks[0]]*a+phases[clicks[1]]*b)
            for i, j in product(v, repeat=2):
                g[1][(i,j)] = g[1].get((i,j), Fraction(0))+_r(v[i]*v[j].conjugate())
    return tuple((true, clicks, norm, tuple((i,j,c) for (i,j),c in rho.items() if c))
                 for (true,clicks),(norm,rho) in groups.items())


def optical_round(weights, basis='Z', *, input_survival=1, detector_efficiency=1, dark_per_mode=0):
    """Exact ONE purification round including payload-invalid accepted heralds.

    Four supplied single photons in two independent Bell-diagonal pairs.
    Uniform independent pure loss before the ideal optical network, uniform
    PNR efficiency, independent Bernoulli dark counts in four detector modes.
    All true photon-count patterns are traced, including misreported failure
    patterns. No projection onto a valid payload is treated as an observed flag.
    """
    p, basis = _weights(weights), _basis(basis)
    m = _unit(input_survival, 'input survival')
    d = _unit(detector_efficiency, 'detector efficiency')
    dark = _unit(dark_per_mode, 'dark per mode')
    if basis == 'X': p = (p[0], p[2], p[1], p[3])  # H on both halves of both pairs
    counts = {(n, r): _count_probability(n, r, d, dark) for n in range(3) for r in (0, 1)}
    observed_records = tuple(product((0, 1), repeat=2))
    branches = {clicks: dict(herald=Fraction(0), rho=[[Fraction(0)]*4 for _ in range(4)]) for clicks in observed_records}
    for first, second, mask in product(range(4), range(4), range(16)):
        lost = mask.bit_count()
        weight = p[first]*p[second]*m**(4-lost)*(1-m)**lost
        if not weight: continue
        for true, clicks, norm, entries in _round_density_terms(first, second, mask):
            observed = tuple(int(k == click) for click in clicks for k in (0, 1))
            detector_weight = weight
            for n, r in zip(true, observed): detector_weight *= counts[n, r]
            if not detector_weight: continue
            branch = branches[clicks]
            branch['herald'] += detector_weight*norm
            for i,j,coefficient in entries:
                branch['rho'][i][j] += detector_weight*coefficient
    rho = [[sum((b['rho'][i][j] for b in branches.values()), Fraction(0)) for j in range(4)] for i in range(4)]
    if basis == 'X':
        h = tuple(tuple(Fraction((-1)**((i & j).bit_count()), 2) for j in range(4)) for i in range(4))
        rho = [[sum((h[i][a]*rho[a][b]*h[b][j] for a, b in product(range(4), repeat=2)), Fraction(0))
                for j in range(4)] for i in range(4)]
    rho = tuple(tuple(row) for row in rho)
    herald = sum((b['herald'] for b in branches.values()), Fraction(0))
    valid = sum(rho[i][i] for i in range(4))
    overlap = (rho[0][0]+rho[3][3]+rho[0][3]+rho[3][0])/2
    return dict(basis=basis, input_survival=m, detector_efficiency=d, dark_per_mode=dark,
                herald_probability=herald, valid_payload_probability=valid,
                false_payload_probability=herald-valid,
                valid_payload_fraction=valid/herald if herald else None,
                conditional_fidelity=overlap/herald if herald else None,
                valid_sector_fidelity=overlap/valid if valid else None,
                fidelity_weight=overlap, valid_payload_density=rho,
                per_click_herald={str(k): b['herald'] for k, b in branches.items()},
                payload_validity_is_observed=False, noisy_rounds_composed=False)


def physical_plan():
    from .encoded_bell import basis_bridge_certificate
    bridge = basis_bridge_certificate()
    return dict(schema='native-source-distillation-plan-v1', author='Monty',
                status='EXACT_CONDITIONAL_MODEL_NO_DEVICE',
                input='two independent supplied Bell-diagonal pairs; one photon per site before loss',
                local_site_order=['A1', 'A2', 'B1', 'B2'],
                modes=8, photons_in=4, local_fusion_couplers=2, detector_modes=[1, 2, 5, 6],
                output_rails=[[0, 3], [4, 7]], accepted_record='one registered photon per local detector pair',
                phase_corrections=[dict(click=r['click'], steps=r['correction_phase_steps'])
                                   for r in fusion_merge_certificate()],
                x_basis_extra_hadamards=6, coherent_h_interface='encoded_bell.basis_bridge_certificate',
                coherent_h_heaters=bridge['coherent_heaters'],
                coherent_h_verified=bridge['coherent_h_up_to_global_phase'],
                couplers_by_basis=dict(Z=2, X=14),
                retry='offline resource preparation only; recursive ideal-supply cost includes failed nodes',
                open=['certified source sector without destructive counting', 'higher source-pair numbers',
                      'faulty multi-round supply and storage scheduling', 'imperfect mode overlap and phase control',
                      'propagation through the 12-photon encoded resource factory', 'measured component parameters'])
