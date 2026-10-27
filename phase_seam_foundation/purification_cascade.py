"""Two noisy optical purification levels with the entire payload retained (v0.35).

No projection onto one photon per site is made between rounds. Sparse density
coefficients use unnormalised creation monomials: |n) = prod(a_i^dagger)^n_i|0>.
Their Gram weight is prod(n_i!), so trace and environment traces need factorials.
This exact representation includes vacuum, one-photon and excess-photon sectors.

The supported family starts with independent Bell-diagonal two-photon pairs,
uniform pure loss, native H/phase controls and symmetric PNR detectors with
Bernoulli dark counts. States are real and block diagonal in local photon totals.
At most two levels are admitted: no number-sector truncation is used to fit a
larger request. A local second-level fusion has at most four input photons.
"""
from collections import defaultdict
from fractions import Fraction as Q
from functools import lru_cache
from itertools import product
from math import comb, factorial

from .model import integer, ResourceLimit
from .optical_refresh import fusion_merge_certificate
from .source_distillation import _unit, _weights, bell_density, physical_plan as round_plan

MAX_LEVELS = 2
MAX_PHOTONS_PER_SITE = 4
VACUUM = (0, 0, 0, 0)
QUBIT = tuple((1-a, a, 1-b, b) for a,b in product((0,1), repeat=2))


@lru_cache(maxsize=512)
def _gram(occupation):
    result = 1
    for n in occupation:
        result *= factorial(n)
    return result


def _clean(state):
    return {key: value for key,value in state.items() if value}


def _trace(state):
    return sum((c*_gram(n) for (n,m),c in state.items() if n == m), Q(0))


def _initial(weights):
    matrix = bell_density(weights)
    return {(n,m): Q(matrix[i][j]) for i,n in enumerate(QUBIT)
            for j,m in enumerate(QUBIT) if matrix[i][j]}


def _max_site(state):
    return max((max(sum(n[:2]),sum(n[2:])) for n,m in state), default=0)


def _check_structure(state):
    """Structural check only; positivity is inherited from the explicit CP maps."""
    for (n,m),c in state.items():
        if (type(c) is not Q or len(n) != 4 or len(m) != 4
                or any(type(k) is not int or k < 0 for k in n+m)):
            raise ValueError('exact rational monomial density required')
        if sum(n[:2]) != sum(m[:2]) or sum(n[2:]) != sum(m[2:]):
            raise ValueError('local photon-number block structure required')
        if state.get((m,n), Q(0)) != c:
            raise ValueError('real Hermitian state required')
        if max(sum(n[:2]),sum(n[2:])) > MAX_PHOTONS_PER_SITE:
            raise ResourceLimit('payload exceeds the two-level photon bound')
    return True


def _loss(state, eta):
    """Pure loss with equal ket/bra environment occupations coherently retained."""
    out = defaultdict(Q)
    for (n,m),c in state.items():
        if sum(n) != sum(m):
            raise ValueError('fixed-number density blocks required')
        for lost in product(*(range(min(a,b)+1) for a,b in zip(n,m))):
            k = sum(lost)
            factor = eta**(sum(n)-k)*(1-eta)**k
            if not factor: continue
            for a,b,l in zip(n,m,lost):
                factor *= comb(a,l)*comb(b,l)*factorial(l)
            ket = tuple(a-l for a,l in zip(n,lost))
            bra = tuple(a-l for a,l in zip(m,lost))
            out[ket,bra] += c*factor
    return _clean(out)


@lru_cache(maxsize=25)
def _h_polynomial(n0,n1):
    """Integer coefficients of (x+y)^n0 (x-y)^n1; 2^(-N/2) factored out."""
    total = n0+n1
    rows = []
    for ones in range(total+1):
        value = sum((-1)**j*comb(n1,j)*comb(n0,ones-j)
                    for j in range(n1+1) if 0 <= ones-j <= n0)
        if value: rows.append(((total-ones,ones),value))
    return tuple(rows)


def _hadamards(state):
    out = defaultdict(Q)
    for (n,m),c in state.items():
        if sum(n[:2]) != sum(m[:2]) or sum(n[2:]) != sum(m[2:]):
            raise ValueError('local charge blocks required')
        scale = c/Q(2)**sum(n)
        for (a,ca),(b,cb),(aa,caa),(bb,cbb) in product(
                _h_polynomial(*n[:2]),_h_polynomial(*n[2:]),
                _h_polynomial(*m[:2]),_h_polynomial(*m[2:])):
            out[a+b,aa+bb] += scale*ca*cb*caa*cbb
    return _clean(out)


def detector_probability(true, observed, efficiency, dark):
    """PNR thinning plus a 0/1 Bernoulli dark count; true counts through four."""
    n, r = integer(true,'true count'), integer(observed,'observed count')
    if not 0 <= n <= 4 or not 0 <= r <= 5:
        raise ValueError('true count 0..4 and observed count 0..5 required')
    d, h = _unit(efficiency,'efficiency'),_unit(dark,'dark')
    return _detector_probability(n,r,d,h)


def _detector_probability(n,r,d,h):
    return sum((Q(comb(n,k))*d**k*(1-d)**(n-k)*(h if r-k else 1-h)
                for k in range(n+1) if r-k in (0,1)), Q(0))


@lru_cache(maxsize=25)
def _coupler_polynomial(n1,n2):
    """Coefficient at measured occupation (r,N-r) is S_r*i^(n1+r)/sqrt(2)^N."""
    return tuple(sum((-1)**j*comb(n1,j)*comb(n2,r-j)
                     for j in range(n1+1) if 0 <= r-j <= n2)
                 for r in range(n1+n2+1))


@lru_cache(maxsize=1)
def _correction_quarters():
    rows = fusion_merge_certificate()
    if tuple(r['click'] for r in rows) != (1,2) or any(r['correction_phase_steps'] % 16 for r in rows):
        raise ArithmeticError('native fusion correction changed')
    return tuple(r['correction_phase_steps']//16 for r in rows)


@lru_cache(maxsize=8192)
def _merge_coefficient(n,m,d,h):
    """Local two-site -> one-site density map, summing true AND observed counts.

    Input order a0,a1,b0,b1; retained rails a0,b1. Both input copies are in
    separate local charge blocks. Feedforward phases act on every photon in
    output rail b1, including excess-photon sectors, before any output H.
    """
    if sum(n[:2]) != sum(m[:2]) or sum(n[2:]) != sum(m[2:]):
        raise ValueError('each input copy needs equal ket/bra local photon total')
    if max(sum(n[:2]),sum(n[2:])) > 2:
        raise ResourceLimit('a second-level local input has at most two photons per copy')
    count = n[1]+n[2]
    if count != m[1]+m[2]:
        return Q(0)   # different environments cannot interfere
    ket, bra = _coupler_polynomial(n[1],n[2]), _coupler_polynomial(m[1],m[2])
    delta = n[3]-m[3]
    result = Q(0)
    for r in range(count+1):
        if not ket[r] or not bra[r]: continue
        raw = Q(ket[r]*bra[r]*factorial(r)*factorial(count-r),2**count)
        for click,quarter in enumerate(_correction_quarters()):
            exponent = (n[1]-m[1]+quarter*delta) % 4
            if exponent % 2:
                raise ArithmeticError('declared real charge-block family not preserved')
            sign = -1 if exponent == 2 else 1
            likelihood = (_detector_probability(r,int(click==0),d,h)
                          *_detector_probability(count-r,int(click==1),d,h))
            result += raw*sign*likelihood
    return result


def _merge(left,right,basis,d,h):
    if max(_max_site(left),_max_site(right)) > 2:
        raise ResourceLimit('local input photon bound exceeded; no truncation is applied')
    if basis == 'X':
        left,right = _hadamards(left),_hadamards(right)
    out = defaultdict(Q)
    for (n,m),c in left.items():
        for (nn,mm),cc in right.items():
            a = _merge_coefficient(n[:2]+nn[:2],m[:2]+mm[:2],d,h)
            if not a: continue
            b = _merge_coefficient(n[2:]+nn[2:],m[2:]+mm[2:],d,h)
            if not b: continue
            ket = (n[0],nn[1],n[2],nn[3])
            bra = (m[0],mm[1],m[2],mm[3])
            out[ket,bra] += c*cc*a*b
    state = _clean(out)
    if basis == 'X': state = _hadamards(state)
    _check_structure(state)
    return state


def _metrics(state):
    trace = _trace(state)
    sectors = defaultdict(Q)
    for (n,m),c in state.items():
        if n == m:
            sectors[sum(n[:2]),sum(n[2:])] += c*_gram(n)
    valid = sectors.get((1,1),Q(0))
    a,b = QUBIT[0],QUBIT[3]
    overlap = (state.get((a,a),Q(0))+state.get((a,b),Q(0))
               +state.get((b,a),Q(0))+state.get((b,b),Q(0)))/2
    return dict(trace=trace, valid_payload_weight=valid, target_overlap_weight=overlap,
                fidelity=overlap/trace if trace else None,
                valid_payload_fraction=valid/trace if trace else None,
                valid_sector_fidelity=overlap/valid if valid else None,
                photon_sector_weights=dict(sorted(sectors.items())),
                max_photons_per_site=_max_site(state), density_entries=len(state))


def _project_for_negative_control(state):
    """An unimplemented inter-round sector flag; used ONLY as a negative control."""
    projected = {(n,m):c for (n,m),c in state.items() if n in QUBIT and m in QUBIT}
    trace = _trace(projected)
    return {key:c/trace for key,c in projected.items()} if trace else {}


def _parameters(input_survival,detector_efficiency,dark_per_mode,memory,left_wait_rounds,right_wait_rounds):
    t1,t2 = integer(left_wait_rounds,'left wait'),integer(right_wait_rounds,'right wait')
    if not 0 <= t1 <= 32 or not 0 <= t2 <= 32:
        raise ResourceLimit('waits must be 0..32 declared rounds')
    m,d,h,mu = (_unit(input_survival,'input survival'),_unit(detector_efficiency,'detector efficiency'),
                _unit(dark_per_mode,'dark per mode'),_unit(memory,'memory'))
    return dict(input_survival=m,detector_efficiency=d,dark_per_mode=h,memory=mu,
                left_wait_rounds=t1,right_wait_rounds=t2,
                left_survival=m*mu**t1,right_survival=m*mu**t2)


def cascade(weights, bases='ZX', *, input_survival=1, detector_efficiency=1,
            dark_per_mode=0, memory=1, left_wait_rounds=0, right_wait_rounds=0):
    """At most two fully composed noisy rounds; every heralded sector is retained.

    Two independent accepted previous-level outputs are supplied to each
    attempt. Fixed declared waits can differ between the two copies. They
    are charged at EVERY level, including the first. This is a conditional
    supply/age model, not a stochastic scheduler or a measured time budget.
    Expected raw-pair cost counts all heralds, including invalid outputs.
    """
    p = _weights(weights)
    if type(bases) is not str or len(bases) > MAX_LEVELS or any(b not in 'ZX' for b in bases):
        raise ResourceLimit('at most two Z/X levels; larger requests are not truncated')
    cfg = _parameters(input_survival,detector_efficiency,dark_per_mode,memory,left_wait_rounds,right_wait_rounds)
    state = _initial(p)
    cost,tree_probability = Q(1),Q(1)
    levels = []
    for level,basis in enumerate(bases,1):
        left = _loss(state,cfg['left_survival'])
        right = _loss(state,cfg['right_survival'])
        raw = _merge(left,right,basis,cfg['detector_efficiency'],cfg['dark_per_mode'])
        probability = _trace(raw)
        if not 0 <= probability <= 1:
            raise ArithmeticError('invalid accepted probability')
        tree_probability = tree_probability**2*probability
        cost = 2*cost/probability if probability else None
        state = {key:c/probability for key,c in raw.items()} if probability else {}
        levels.append(dict(level=level,basis=basis,herald_probability=probability,
                           expected_raw_pairs=cost,one_tree_probability=tree_probability,
                           **_metrics(state)))
        if not probability: break
    return dict(status='NO_HERALDS' if not state else 'EXACT_FULL_PAYLOAD_CASCADE_NO_DEVICE',
                bases=bases,parameters=cfg,levels=levels,expected_raw_pairs=cost,
                one_tree_probability=tree_probability,final_state=state,
                state_basis='unnormalised_creation_monomials; trace uses factorial Gram weights',
                **_metrics(state),payload_validity_is_observed=False,
                intermediate_sector_projection=False,stochastic_waiting_modelled=False)


def projection_bias(weights, *, input_survival=1, detector_efficiency=1, dark_per_mode=0):
    """Compare ZX with an added valid-sector flag absent from the physical plan."""
    cfg = _parameters(input_survival,detector_efficiency,dark_per_mode,1,0,0)
    first = cascade(weights,'Z',input_survival=input_survival,
                    detector_efficiency=detector_efficiency,dark_per_mode=dark_per_mode)
    selected = _project_for_negative_control(first['final_state'])
    wrong = _merge(_loss(selected,cfg['left_survival']),_loss(selected,cfg['right_survival']),
                   'X',cfg['detector_efficiency'],cfg['dark_per_mode']) if selected else {}
    actual = cascade(weights,'ZX',input_survival=input_survival,
                     detector_efficiency=detector_efficiency,dark_per_mode=dark_per_mode)
    return dict(actual=_metrics(actual['final_state']),
                extra_sector_projection=_metrics(wrong),projection_is_available=False)


def scan_schedules(weights, **parameters):
    """Seven declared choices only; report fidelity and supply cost without selecting a winner."""
    rows = []
    for bases in ('','Z','X','ZZ','ZX','XZ','XX'):
        result = cascade(weights,bases,**parameters)
        rows.append(dict(bases=bases,fidelity=result['fidelity'],
                         valid_payload_fraction=result['valid_payload_fraction'],
                         expected_raw_pairs=result['expected_raw_pairs']))
    return rows


def physical_plan():
    return dict(schema='native-purification-cascade-plan-v1',author='Monty',
                status='EXACT_TWO_LEVEL_MODEL_NO_DEVICE',single_round=round_plan(),
                maximum_levels=MAX_LEVELS,raw_pairs_per_unretried_tree=4,
                raw_photons_per_unretried_tree=8,local_fusion_input_photons_max=4,
                output_photons_per_site_max=4,output_total_photons_max=8,
                preserved_sectors='all, including vacuum and excess photons; no truncation',
                correction='native phase shift applied to every photon in the selected output rail',
                waiting='fixed per-copy survival at every level; random preparation latency remains open',
                cost='recursive retry: 2*previous_cost/current_herald_probability, counts false heralds',
                open=['certified raw-source statistics','higher source-pair inputs','more than two noisy levels',
                      'random completion times and scheduling','mode mismatch and phase errors',
                      '12-photon encoded-factory channel','physical validation'])
