"""Static encoded Bell transfer on the native tree code (v0.32).

Local leaf Hadamards expose a quantum parity code. Transversal passive Bell
analysers then infer both logical parities from detector records, including
erasures, without an external loss oracle. The fully encoded Bell resource
is a larger offline resource than v0.30's single-port resource. All device
statements are restricted to the declared ideal/pure-loss optical model.
"""
from fractions import Fraction
from functools import lru_cache
from itertools import product

from native_relational_qc.dynamic import DynamicCircuit, expectation, probability
from native_relational_qc.exact import Exact, ONE as EONE, ZERO as EZERO
from .cluster_build import adaptation_lemma
from .cluster_compile import heater_setting
from .dual_rail import H2, ONE, ZERO, ZETA
from .loss_refresh import _encode, _groups
from .loss_tolerant_code import code, record_probability
from .model import ResourceLimit, integer
from .optical_refresh import (
    _execute_decoder, _logical_pauli, bell_analyser_certificate, decoder_plan,
    encoded_bell_factory_certificate,
)
from .photonic_response import unit_jet


def _layout(branching, pair_lost_mask=0):
    br = tuple(branching)
    c, groups = _groups(br)
    lost = integer(pair_lost_mask, 'pair erasure mask')
    if not 0 <= lost < 1 << c['photons']:
        raise ValueError('pair erasure mask outside the encoded block')
    survivors = tuple(tuple(q for q in g if not (lost >> q) & 1) for g in groups)
    complete = tuple(i for i, (g, s) in enumerate(zip(groups, survivors)) if g == s)
    return br, c, groups, survivors, complete


@lru_cache(maxsize=1)
def basis_bridge_certificate():
    """Reuse v0.29's heater interface, checking the coherent gate, not just powers.

    A measurement basis setting may have output phases invisible in detector
    probabilities. Remove their relative phase before using it as a coherent H.
    The remaining scalar is global for a one-photon dual-rail input.
    """
    setting = heater_setting(0)
    h = setting['heaters']
    raw_steps = tuple(h[k] for k in ('lower', 'upper', 'before', 'after'))
    u, _ = unit_jet(raw_steps)
    plus_phase = (u[0][0]+u[0][1])*H2
    minus_phase = (u[1][0]-u[1][1])*H2
    relative = minus_phase/plus_phase
    shift = next((k for k in range(64) if ZETA**k == relative), None)
    if shift is None:
        raise ArithmeticError('coherent output correction is not on the native grid')
    corrected_steps = raw_steps[:3]+((raw_steps[3]-shift) % 64,)
    v, _ = unit_jet(corrected_steps)
    target = ((H2, H2), (H2, -H2))
    if plus_phase.norm2() != ONE or any(v[i][j] != plus_phase*target[i][j]
                                       for i, j in product(range(2), repeat=2)):
        raise ArithmeticError('heater interface does not implement coherent H')
    return dict(source='cluster_compile.heater_setting(0)', phase_period=64,
                measurement_heaters=h, coherent_heaters=dict(zip(
                    ('lower', 'upper', 'before', 'after'), corrected_steps)),
                relative_output_phase_removed=shift, unitary=v,
                global_phase=plus_phase, coherent_h_up_to_global_phase=True,
                calibrated_voltage_or_temperature_claim=False)


@lru_cache(maxsize=1)
def coarse_instrument_certificate():
    """Coarse-grain the Fock-derived detector rows into even, Psi+, Psi-.

    Sum raw row outer products; do not replace unresolved even outcomes by a
    resolved phase bit. The equivalent full Bell reference may discard that
    bit because all measured photons are consumed and its outcomes summed.
    """
    effects = {name: [[ZERO]*4 for _ in range(4)] for name in ('even', 'odd_plus', 'odd_minus')}
    records = []
    for r in bell_analyser_certificate()['outcomes']:
        group = ('odd_minus' if r['z_correction'] else 'odd_plus') if r['accepted'] else 'even'
        row = r['row']
        for a, b in product(range(4), repeat=2):
            effects[group][a][b] += row[a].conjugate()*row[b]
        records.append(dict(counts=r['outcome'], group=group,
                            possible=any(row), zz=1 if r['accepted'] else 0,
                            xx=r['z_correction'] if r['accepted'] else None))
    target_even = [[ONE if i == j and i in (0, 3) else ZERO for j in range(4)] for i in range(4)]
    if effects['even'] != target_even:
        raise ArithmeticError('even detector outcomes are not the unresolved parity effect')
    for name, sign in (('odd_plus', 1), ('odd_minus', -1)):
        v = (ZERO, H2, sign*H2, ZERO)
        target = [[v[i]*v[j].conjugate() for j in range(4)] for i in range(4)]
        if effects[name] != target:
            raise ArithmeticError('odd detector effect is not a Bell projector')
    return dict(status='EXACT_FOCK_DERIVED_COARSE_INSTRUMENT', effects=effects,
                records=records, even_phase_resolved=False, complete=True)


def decode_counts(branching, detector_counts):
    """Infer a logical Pauli frame from actual four-mode counts for each pair.

    Zero/one total photon means that pair supplies no information. A two-
    photon even event supplies ZZ only; an odd event also supplies XX.
    Group parity contradictions, excess photons and impossible ideal patterns
    fail closed. Loss identification comes from these counts, not an oracle.
    """
    br, c, groups, _, _ = _layout(branching)
    records = tuple(tuple(v) for v in detector_counts)
    if len(records) != c['photons']:
        raise ValueError('one four-mode count record per physical pair required')
    lookup = {tuple(r['counts']): r for r in coarse_instrument_certificate()['records']}
    zz, xx, lost = [], [], 0

    def reject(reason):
        return dict(accepted=False, reason=reason, requires_external_erasure_map=False)

    for q, counts in enumerate(records):
        if len(counts) != 4 or any(type(v) is not int or v < 0 for v in counts):
            raise ValueError('four nonnegative integer detector counts required')
        total = sum(counts)
        if total > 2:
            return reject('EXCESS_PHOTONS')
        if total < 2:
            lost |= 1 << q
            zz.append(None); xx.append(None)
            continue
        r = lookup[counts]
        if not r['possible']:
            return reject('IMPOSSIBLE_IDEAL_TWO_PHOTON_PATTERN')
        zz.append(r['zz']); xx.append(r['xx'])
    parity, candidates = [], []
    for i, g in enumerate(groups):
        values = {zz[q] for q in g if zz[q] is not None}
        if not values:
            return reject('GROUP_WITH_NO_COMPLETE_PAIR')
        if len(values) != 1:
            return reject('INCONSISTENT_GROUP_PARITY')
        parity.append(next(iter(values)))
        if all(zz[q] == 1 for q in g):
            candidates.append(i)
    if not candidates:
        return reject('NO_COMPLETE_ODD_GROUP')
    phases = {sum(xx[q] for q in groups[g]) % 2 for g in candidates}
    if len(phases) != 1:
        return reject('INCONSISTENT_LOGICAL_PHASE')
    selected = candidates[0]
    logical_xx = sum(parity) % 2
    logical_zz = sum(xx[q] for q in groups[selected]) % 2
    return dict(accepted=True, branching=list(br), pair_lost_mask=lost,
                selected_group=selected, logical_xx_bit=logical_xx, logical_zz_bit=logical_zz,
                x_correction=logical_zz, z_correction=logical_xx,
                requires_external_erasure_map=False)


@lru_cache(maxsize=64)
def _checked_adaptation(angle):
    if not adaptation_lemma(angle)['holds']:
        raise ArithmeticError('collaborator angle-adaptation identity failed')
    return True


@lru_cache(maxsize=64)
def _terminal_heaters(angle):
    return heater_setting(angle)['heaters']


def measurement_handoff(branching, decoder_result, nominal_angles):
    """Track the accepted logical frame into subsequent local equatorial readout.

    Expand the logical Paulis into physical frames, then reuse v0.31's
    projector identity. Each future B(a) measurement becomes B((-1)^x a),
    followed by outcome xor z. This adapter assumes no intervening gates;
    it is not a compiler of an encoded logical classifier or logical B(a).
    """
    br, c, _, _, _ = _layout(branching)
    if (type(decoder_result) is not dict or decoder_result.get('accepted') is not True
            or decoder_result.get('branching') != list(br)):
        raise ValueError('accepted decoder result for this same code required')
    frame = [decoder_result.get(k) for k in ('x_correction', 'z_correction')]
    if any(type(v) is not int or v not in (0, 1) for v in frame):
        raise ValueError('logical frame bits must be integers 0 or 1')
    angles = tuple(nominal_angles)
    if len(angles) != c['photons'] or any(type(a) is not int or not 0 <= a < 64 for a in angles):
        raise ValueError('one native angle in 0..63 per output photon required')
    xmask, zmask = 0, 0
    for bit, name in zip(frame, ('x_logical', 'z_logical')):
        if bit:
            xmask ^= c[name][0]; zmask ^= c[name][1]
    rows = []
    for q, angle in enumerate(angles):
        _checked_adaptation(angle)
        x, z = (xmask >> q) & 1, (zmask >> q) & 1
        adapted = (-angle if x else angle) % 64
        rows.append(dict(photon=q, physical_frame=(x, z), nominal_angle=angle,
                         adapted_angle=adapted, outcome_xor=z,
                         heaters=dict(_terminal_heaters(adapted))))
    return dict(status='EXACT_TERMINAL_MEASUREMENT_FRAME_HANDOFF', branching=list(br),
                source='cluster_build.adaptation_lemma', physical_x_mask=xmask,
                physical_z_mask=zmask, rows=rows, active_pauli_gates_before_these_measurements=0,
                scope='subsequent single-photon equatorial measurements; no intervening gates',
                encoded_logical_classifier_compiled=False)


def mask_success(branching, pair_lost_mask):
    """Exact success for a fixed mask, averaged over the encoded Bell labels."""
    br, c, groups, survivors, complete = _layout(branching, pair_lost_mask)
    p = Fraction(1)-Fraction(1, 2)**len(complete) if all(survivors) else Fraction()
    return dict(branching=list(br), photons=c['photons'], pair_lost_mask=pair_lost_mask,
                complete_groups=complete, every_group_has_pair=all(survivors), success_probability=p)


def _success_exact(branching, pair_survival):
    b, c = branching
    some = 1-(1-pair_survival)**(c+1)
    complete_odd = pair_survival**(c+1)/2
    return some**b-(some-complete_odd)**b


def success_probability(branching, pair_survival):
    br, _, _, _, _ = _layout(branching)
    eta = record_probability(pair_survival, 'complete-pair survival')
    return _success_exact(br, eta)


def loss_coefficients(branching=(2, 2)):
    """Independent finite mask enumeration in Bernstein form, bounded to n<=16.

    Numerators are sums of 2^b * conditional success over masks of weight k.
    Their common denominator is 2^b. This is not a count of accepted masks.
    """
    return _loss_coefficients(tuple(branching))


@lru_cache(maxsize=32)
def _loss_coefficients(branching):
    br, c, groups, _, _ = _layout(branching)
    n, denominator = c['photons'], 1 << len(groups)
    masks = [sum(1 << q for q in g) for g in groups]
    counts = [0]*(n+1)
    for lost in range(1 << n):
        if any((lost & m) == m for m in masks):
            continue
        complete = sum(not (lost & m) for m in masks)
        counts[lost.bit_count()] += denominator-(1 << (len(groups)-complete))
    return dict(branching=list(br), photons=n, denominator=denominator,
                weighted_numerators=counts, basis='eta^(n-k) * (1-eta)^k')


def _reference(branching, pair_lost_mask, selected_group, corrections):
    """Clifford reference for the coarse optical instrument, not a CNOT device.

    Both photons of an incomplete pair are traced, representing summing all
    of its retained zero/one-photon detector records. A classical Bell phase
    exists in the adapter but is used only in the chosen complete odd group.
    """
    br, ccode, groups, survivors, complete = _layout(branching, pair_lost_mask)
    if not all(survivors) or selected_group not in complete:
        raise ValueError('no admissible complete group')
    if type(corrections) is not bool:
        raise TypeError('corrections must be bool')
    n = ccode['photons']; ref = 3*n
    d = decoder_plan(br)
    c = DynamicCircuit(ref+1, 2*n+d['measurements'])
    c.add('h', ref).add('cx', ref, 0)
    _encode(c, br, 0)
    # Supplied encoded Phi+ across the incoming Bell arm B and output C.
    c.add('h', n).add('cx', n, 2*n)
    _encode(c, br, n); _encode(c, br, 2*n)
    online_start = len(c.operations)
    for q in range(n):
        if pair_lost_mask >> q & 1:
            c.reset(q).reset(n+q)
        else:
            if ccode['level'][q] == 1:
                c.add('h', q).add('h', n+q)
            c.add('cx', q, n+q).add('h', q)
            c.measure(q, 2*q).measure(n+q, 2*q+1)
    event = {2*groups[selected_group][0]+1: 1}
    for i in complete:
        if i == selected_group:
            break
        event[2*groups[i][0]+1] = 0
    if corrections:
        for q in groups[selected_group]:
            _logical_pauli(c, br, 2*n, 'x', {2*q: 1})
        for g in survivors:
            _logical_pauli(c, br, 2*n, 'z', {2*g[0]+1: 1})
    boundary = len(c.operations)
    logical, _ = _execute_decoder(c, d, 2*n, 2*n, True)
    return dict(circuit=c, event=event, reference=ref, logical=logical,
                selected_group=selected_group, online_start=online_start, fresh_output_boundary=boundary)


def transfer_witness(branching=(2, 2), pair_lost_mask=0, *, corrections=True):
    br, c, groups, survivors, complete = _layout(branching, pair_lost_mask)
    if type(corrections) is not bool:
        raise TypeError('corrections must be bool')
    branches = []
    total, numerator = EZERO, EZERO
    if all(survivors):
        for g in complete:
            r = _reference(br, pair_lost_mask, g, corrections)
            circuit, event = r['circuit'], r['event']
            p = probability(circuit, classical=event).value
            xyz = [expectation(circuit, {r['logical']: axis, r['reference']: axis},
                               classical=event).value for axis in 'XYZ']
            joint = (p+xyz[0]-xyz[1]+xyz[2])/Exact(4)
            total += p; numerator += joint
            branches.append(dict(selected_group=g, probability=p,
                                 joint_bell_projector=joint, conditional_fidelity=joint/p))
    return dict(status='IDEAL_ENCODED_OPTICAL_TRANSFER_WITH_SUPPLIED_RESOURCE',
                branching=list(br), pair_lost_mask=pair_lost_mask,
                success_probability=total, rejected_probability=EONE-total,
                joint_bell_projector=numerator,
                conditional_entanglement_fidelity=numerator/total if total else None,
                disjoint_first_odd_group_events=branches,
                requires_external_erasure_map=False,
                witness_conditions_on_declared_erasure_pattern=True,
                even_pair_phases_used=False, output_data_photons=c['photons'])


@lru_cache(maxsize=1)
def resource_factory_certificate():
    """Entanglement-swap two certified v0.30 seven-photon resources offline.

    The Bell ports are consumed by the existing passive analyser. Each
    accepted row contracts to an encoded Phi+ after a known logical Pauli.
    Prepare BOTH input resources before every swap; discard both on failure.
    """
    source = encoded_bell_factory_certificate()
    branches = []
    for r in bell_analyser_certificate()['outcomes']:
        if not r['accepted']:
            continue
        a = tuple(tuple(r['row'][2*i+j]/2 for j in range(2)) for i in range(2))
        # X then Z on the second encoded block (matrix columns).
        corrected = tuple((row[1], (-1 if r['z_correction'] else 1)*row[0]) for row in a)
        scale = corrected[0][0]/H2
        if corrected != ((scale*H2, ZERO), (ZERO, scale*H2)) or scale.norm2() != ONE/8:
            raise ArithmeticError('port fusion failed to produce an encoded Bell resource')
        branches.append(dict(counts=r['outcome'], x_correction=1, z_correction=r['z_correction'],
                             probability=scale.norm2(), target_encoded_phi_plus=True))
    cost = 2*source['expected_bell_pairs_per_delivered_resource']
    return dict(status='EXACT_LOSSLESS_ENCODED_RESOURCE_FACTORY_NO_DEVICE', branching=[2, 2],
                seven_photon_resources_per_attempt=2, input_photons=14,
                measured_port_photons=2, output_photons=12, branches=branches,
                swap_success_probability=Fraction(1, 2),
                expected_bell_pairs_per_swap_attempt=cost,
                expected_bell_pairs_per_delivered_resource=cost*2,
                expected_source_photons_per_delivered_resource=cost*4,
                expected_swap_attempts=Fraction(2),
                policy='prepare both resources first; discard both on failed port swap',
                storage_switch_source_noise_included=False,
                preparation_latency_included=False)


def resource_stabiliser_witness(*, corrections=True):
    """Independent native dynamic check of all twelve target stabilisers."""
    if type(corrections) is not bool:
        raise TypeError('corrections must be bool')
    br = (2, 2); n = code(br)['photons']
    c = DynamicCircuit(2*n+2, 2)
    for off, port in ((0, 2*n), (n, 2*n+1)):
        c.add('h', port).add('cx', port, off); _encode(c, br, off)
    c.add('cx', 2*n, 2*n+1).add('h', 2*n)
    c.measure(2*n, 0).measure(2*n+1, 1)
    if corrections:
        _logical_pauli(c, br, n, 'x', {1: 1})
        _logical_pauli(c, br, n, 'z', {0: 1})
    p = probability(c, classical={1: 1}).value
    cc = code(br)
    generators = list(cc['stabilisers'])+[(x << n, z << n) for x, z in cc['stabilisers']]
    generators += [(x | (x << n), z | (z << n)) for x, z in (cc['x_logical'], cc['z_logical'])]
    values = []
    for x, z in generators:
        pauli = {q: 'Y' if (x >> q & 1 and z >> q & 1) else 'X' if x >> q & 1 else 'Z'
                 for q in range(2*n) if (x | z) >> q & 1}
        values.append(expectation(c, pauli, classical={1: 1}).value/p)
    return dict(success_probability=p, independent_target_generators=len(generators),
                target_expectations=values, all_target_stabilisers_plus_one=all(v == EONE for v in values))


def physical_plan(branching=(2, 2)):
    br, c, groups, _, _ = _layout(branching)
    n, b = c['photons'], len(groups)
    converters = 2*(n-b)
    return dict(schema='native-encoded-bell-plan-v1', status='IDEAL_COMPONENT_PLAN_NOT_FABRICATED',
                branching=list(br), groups=groups,
                input=dict(old_block_photons=n, resource_photons=2*n, total_photons=3*n),
                output=dict(fresh_data_photons=n, consumed_measured_photons_if_lossless=2*n),
                graph_to_parity=dict(photon_indices_per_measured_block=[q for g in groups for q in g[1:]],
                                     coherent_unit=basis_bridge_certificate(), units=converters),
                transversal_analysers=n, bell_couplers=2*n, basis_converter_couplers=2*converters,
                total_couplers_excluding_factory_and_pauli_routing=2*n+2*converters,
                detector_mode_channels=4*n,
                per_pair_mode_order=('a0', 'a1', 'b0', 'b1'),
                per_pair_coupler_modes=((0, 2), (1, 3)),
                per_pair_input_and_output_phase_steps={'2': -16, '3': -16},
                readout=coarse_instrument_certificate()['records'],
                classical_decoder='encoded_bell.decode_counts; first complete odd group',
                final_frame_order=('x', 'z'),
                terminal_measurement_frame_handoff='encoded_bell.measurement_handoff',
                adaptation_scope='Bell bases are static; subsequent terminal readout may use the tracked frame',
                logical_x=c['x_logical'], logical_z=c['z_logical'],
                nondestructive_erasure_oracle=False, quantum_adaptive_measurement_bases=False,
                fully_encoded_factory_certified_here=br == (2, 2),
                physical_latency_or_temperature_measured=False)


def budget(branching=(2, 2), *, memory, storage_rounds, detector_efficiency,
           resource_ready, pre_bell_rounds, post_bell_rounds):
    """Full-resource/no-launch supply; pure loss, ideal interference, no dark counts.

    A complete pair requires both photons and both detections. There is no
    additional eta^(2n) prefactor: incomplete pairs are already included in
    the code's success law. Fresh-payload loss is separate and unheralded.
    """
    br, c, _, _, _ = _layout(branching)
    m = record_probability(memory, 'memory')
    d = record_probability(detector_efficiency, 'detector efficiency')
    r = record_probability(resource_ready, 'resource readiness')
    times = [integer(v, 'rounds') for v in (storage_rounds, pre_bell_rounds, post_bell_rounds)]
    if min(times) < 0 or sum(times) > 256:
        raise ResourceLimit('nonnegative rounds with sum at most 256 required')
    t, pre, post = times; n = c['photons']
    eta = m**(t+2*pre)*d**2
    herald = r*_success_exact(br, eta)
    payload = m**(n*(pre+post))
    return dict(status='DECLARED_PURE_LOSS_ENCODED_TRANSFER_BUDGET', branching=list(br),
                inputs=dict(memory=m, storage_rounds=t, detector_efficiency=d, resource_ready=r,
                            pre_bell_rounds=pre, post_bell_rounds=post),
                complete_pair_probability=eta, herald_probability=herald,
                fresh_payload_survival=payload, herald_and_intact_output_probability=herald*payload,
                payload_loss_can_be_unheralded=payload < 1,
                supply_model='full correct encoded resource or no launch; partial-source false heralds excluded',
                factory_latency_and_nonzero_loss_cost_included=False,
                physical_conditional_fidelity_claimed=False)
