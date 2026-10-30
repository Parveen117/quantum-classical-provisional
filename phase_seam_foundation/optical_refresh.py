"""Passive-optical lowering of the v0.28 refresh node, bounded to ideal optics.

Online: single-photon measurements/corrections, a two-coupler Bell analyser,
and a supplied encoded Bell resource. The latter is constructed for [2,2]
from three graph stars by two type-I fusions, with exact detector branches.
No deterministic online optical CNOT is assumed. Known-erasure and fixed
measurement policies have different acceptance probabilities. Payload loss
is not silently certified by a detector herald.
"""
from fractions import Fraction
from functools import lru_cache
from itertools import product

from native_relational_qc.dynamic import DynamicCircuit, expectation, probability
from native_relational_qc.exact import Exact, ONE as EONE
from .dual_rail import (
    ZERO, ONE, H2, ZETA, COUPLER, compose, embed, encode,
    fock_amplitude, phase, _patterns,
)
from .loss_refresh import _encode, _groups, memory_lifetime, recovery_plan
from .loss_tolerant_code import code, record_probability
from .model import ResourceLimit, integer


def decoder_plan(branching=(2, 2), *, known_lost_mask=None, fixed_group=0):
    """Measurement-only decoder, with a fixed policy if no erasure map exists.

    All leaves of the selected intact group are measured in graph-basis Z.
    One surviving photon in each other group is read in Z (parent) or X
    (leaf). A leaf parity Z, then H, then other-group parity Z recovers input.
    A fixed plan always selects the other parents and needs no loss oracle.
    Missing required detections reject that attempt; no adaptive claim here.
    """
    branching = tuple(branching)
    c, groups = _groups(branching)
    group = integer(fixed_group, 'fixed group')
    if not 0 <= group < len(groups):
        raise ValueError('fixed group outside the tree')
    if known_lost_mask is None:
        out = groups[group][0]
        others = tuple(g[0] for i, g in enumerate(groups) if i != group)
        policy = 'FIXED_NO_ERASURE_ORACLE'
    else:
        plan = recovery_plan(branching, known_lost_mask)
        if not plan['recoverable']:
            raise ValueError('uncorrectable known erasure pattern')
        group, out = plan['intact_group'], plan['output']
        others = plan['measured_survivors']
        policy = 'CONDITIONAL_ON_KNOWN_ERASURE_MAP'
    operations, leaf_bits, other_bits = [], [], []
    for q in groups[group][1:]:
        bit = len(operations)
        operations.append(dict(kind='measure_z', photon=q, bit=bit))
        leaf_bits.append(bit)
    for q in others:
        bit = len(operations)
        basis = 'measure_z' if q < len(groups) else 'measure_x'
        operations.append(dict(kind=basis, photon=q, bit=bit))
        other_bits.append(bit)
    measurements = len(operations)
    required = {out} | {op['photon'] for op in operations}
    operations += [dict(kind='z_parity', photon=out, bits=leaf_bits),
                   dict(kind='h', photon=out),
                   dict(kind='z_parity', photon=out, bits=other_bits)]
    return dict(branching=list(branching), photons=c['photons'], policy=policy,
                output=out, selected_group=group, measurements=measurements,
                required_photons=sorted(required), required_mask=sum(1 << q for q in required),
                discarded_photons=[q for q in range(c['photons']) if q not in required],
                operations=operations, online_two_qubit_unitaries=0)


def _execute_decoder(circuit, plan, offset, bit_offset, corrections=True):
    for op in plan['operations']:
        q = offset + op['photon']
        if op['kind'] in ('measure_z', 'measure_x'):
            if op['kind'] == 'measure_x':
                circuit.add('h', q)
            circuit.measure(q, bit_offset+op['bit'])
        elif op['kind'] == 'h':
            circuit.add('h', q)
        elif corrections:
            for bit in op['bits']:
                circuit.add('z', q, condition={bit_offset+bit: 1})
    return offset+plan['output'], bit_offset+plan['measurements']


@lru_cache(maxsize=1)
def bell_analyser_certificate():
    """Exact two-photon instrument in Q(zeta_64), including all ten patterns.

    P(-pi/2) D P(-pi/2) = H for the existing symmetric coupler D.
    Interfere corresponding rails (0,2), (1,3); count all four output modes.
    Four two-click patterns identify Psi+ or Psi-. Contract each row with
    a Phi+ resource to obtain its 2x2 teleport Kraus matrix K.
    """
    factors = []
    for a, b in ((0, 2), (1, 3)):
        factors += [phase(4, b, -16), embed(4, (a, b), COUPLER), phase(4, b, -16)]
    u = compose(*factors)
    rows, accepted_sum, full_sum = [], [[ZERO]*2 for _ in range(2)], [[ZERO]*2 for _ in range(2)]
    for outcome in _patterns(4, 2):
        row = tuple(fock_amplitude(u, encode((a, b), 4), outcome) for a, b in product((0, 1), repeat=2))
        # K[resource logical output b][unknown input a].
        k = tuple(tuple(H2*row[2*a+b] for a in (0, 1)) for b in (0, 1))
        good = (outcome[0]+outcome[2] == 1 and outcome[1]+outcome[3] == 1)
        gram = tuple(tuple(sum((k[r][a].conjugate()*k[r][b] for r in (0, 1)), ZERO)
                           for b in (0, 1)) for a in (0, 1))
        for a, b in product((0, 1), repeat=2):
            full_sum[a][b] += gram[a][b]
            if good:
                accepted_sum[a][b] += gram[a][b]
        item = dict(outcome=outcome, row=row, kraus=k, accepted=good)
        if good:
            minus = row[1] == -row[2]
            if not (row[1] and (row[1] == row[2] or minus)):
                raise ArithmeticError('accepted optical row is not a Psi Bell projection')
            # Apply X then (for Psi-) Z to the logical output: C = Z^z X.
            corrected = ((k[1][0], k[1][1]),
                         ((-1 if minus else 1)*k[0][0], (-1 if minus else 1)*k[0][1]))
            scalar = corrected[0][0]
            identity = corrected == ((scalar, ZERO), (ZERO, scalar))
            if not identity:
                raise ArithmeticError('optical teleport correction is not identity')
            item.update(bell_label='psi_minus' if minus else 'psi_plus',
                        x_correction=1, z_correction=int(minus),
                        corrected_identity=True, probability=scalar.norm2())
        rows.append(item)
    ident = [[ONE, ZERO], [ZERO, ONE]]
    if full_sum != ident or accepted_sum != [[ONE/2, ZERO], [ZERO, ONE/2]]:
        raise ArithmeticError('Bell instrument completeness or success mismatch')
    return dict(status='EXACT_TWO_PHOTON_PASSIVE_INSTRUMENT', mode_unitary=u,
                outcomes=rows, complete=True, success_probability=Fraction(1, 2),
                accepted_patterns=sum(r['accepted'] for r in rows),
                couplers=2, phase_shifts=4, detector_modes=4,
                maximum_measured_photons=2, input_independent_success=True)


@lru_cache(maxsize=1)
def fusion_merge_certificate():
    """Derive the local type-I 2->1 graph merge from the existing Fock engine.

    Mix a1,b0 (modes 1,2), detect exactly one photon there; a0,b1 are output.
    Each detector row is (|0><00| + phase |1><11|)/sqrt(2). The recorded
    phase is corrected on the surviving output photon.
    """
    u = embed(4, (1, 2), COUPLER)
    rows = []
    for click in (1, 2):
        k = []
        for output in (0, 1):
            occ = [0]*4
            occ[click] = 1
            occ[0 if output == 0 else 3] = 1
            k.append(tuple(fock_amplitude(u, encode((a, b), 4), tuple(occ))
                           for a, b in product((0, 1), repeat=2)))
        k = tuple(k)
        ratio = k[1][3]/k[0][0]
        steps = next((s for s in range(64) if ZETA**s == ratio), None)
        if steps is None:
            raise ArithmeticError('fusion correction not on the native phase grid')
        corrected = (k[0], tuple(v*ZETA**(-steps) for v in k[1]))
        scalar = corrected[0][0]
        if corrected != ((scalar, ZERO, ZERO, ZERO), (ZERO, ZERO, ZERO, scalar)):
            raise ArithmeticError('fusion is not a corrected graph merge')
        rows.append(dict(click=click, raw_kraus=k, corrected_kraus=corrected,
                         correction_phase_steps=(-steps) % 64, scalar=scalar))
    return tuple(rows)


def _graph_state(labels, edges):
    amp = H2**len(labels)
    return {bits: (-amp if sum(((bits >> labels.index(a)) & 1)*((bits >> labels.index(b)) & 1)
                              for a, b in edges) % 2 else amp)
            for bits in range(1 << len(labels))}


def _merge_state(state, labels, a, b, kraus):
    ia, ib = labels.index(a), labels.index(b)
    following_labels = tuple(q for q in labels if q != b)
    result = {}
    for bits, amp in state.items():
        pair = 2*((bits >> ia) & 1) + ((bits >> ib) & 1)
        for output in (0, 1):
            coefficient = kraus[output][pair]
            if coefficient:
                new = sum((output if q == a else (bits >> labels.index(q)) & 1) << i
                          for i, q in enumerate(following_labels))
                result[new] = result.get(new, ZERO) + amp*coefficient
    return result, following_labels


@lru_cache(maxsize=1)
def encoded_bell_factory_certificate():
    """Explicit lossless [2,2] resource: three GHZ3-equivalent graph stars.

    Prepare all three stars before each factory attempt (12 expected Bell
    pairs using the established 1/2-success GHZ3 primitive). Abort/discard on
    either attachment failure. Successful root stays unmeasured: it is the
    Bell port, unlike the root-measured v0.27 site. Four click sequences are
    checked coefficient-by-coefficient against the target seven-photon graph.
    """
    labels = tuple(range(9))
    initial = _graph_state(labels, ((0, 1), (0, 2), (3, 4), (3, 5), (6, 7), (6, 8)))
    expected_labels = (0, 1, 2, 4, 5, 7, 8)
    expected = _graph_state(expected_labels, ((0, 1), (0, 2), (1, 4), (1, 5), (2, 7), (2, 8)))
    branches = []
    for first, second in product(fusion_merge_certificate(), repeat=2):
        s, lab = _merge_state(initial, labels, 1, 3, first['corrected_kraus'])
        first_probability = sum((a.norm2() for a in s.values()), ZERO)
        if first_probability != ONE/4:
            raise ArithmeticError('first factory attachment probability mismatch')
        s, lab = _merge_state(s, lab, 2, 6, second['corrected_kraus'])
        scale = s[0]/expected[0]
        matches = lab == expected_labels and all(s.get(k, ZERO) == scale*v for k, v in expected.items())
        if not matches:
            raise ArithmeticError('factory does not produce the declared encoded Bell graph')
        p = sum((a.norm2() for a in s.values()), ZERO)
        branches.append(dict(clicks=(first['click'], second['click']),
                             phase_corrections=(first['correction_phase_steps'], second['correction_phase_steps']),
                             first_click_probability=first_probability,
                             probability=p, target_graph_matches=True))
    if any(b['probability'] != ONE/16 for b in branches):
        raise ArithmeticError('factory detector branch probability mismatch')
    return dict(status='EXACT_LOSSLESS_FACTORY_NO_MEASURED_SOURCE', branching=[2, 2],
                source_graph_stars=3, photons_supplied=9, photons_detected=2,
                photons_delivered=7, data_photons=6, bell_port_photons=1,
                input_stars=((0, 1, 2), (3, 4, 5), (6, 7, 8)),
                ghz_to_star_hadamards=(1, 2, 4, 5, 7, 8),
                fusion_sequence=((1, 3), (2, 6)),
                merge_mode_order=('a0', 'a1', 'b0', 'b1'),
                merge_coupler_modes=(1, 2), merge_detector_modes=(1, 2),
                merge_survivor_modes=(0, 3), merge_rule='exactly one detected photon',
                failure_policy='prepare all three stars first; discard entire candidate on either failure',
                output_graph_labels=expected_labels, bell_port_label=0,
                output_graph_edges=((0, 1), (0, 2), (1, 4), (1, 5), (2, 7), (2, 8)),
                code_photon_labels=expected_labels[1:],
                branches=branches, success_probability=Fraction(1, 4),
                rejected_at_first_attachment_probability=Fraction(1, 2),
                rejected_at_second_attachment_probability=Fraction(1, 4),
                expected_bell_pairs_per_factory_attempt=Fraction(12),
                expected_bell_pairs_per_delivered_resource=Fraction(48),
                expected_source_photons_per_delivered_resource=Fraction(96),
                expected_factory_attempts=Fraction(4),
                attachment_rounds_on_success=2,
                expected_attachment_rounds_per_attempt=Fraction(3, 2),
                expected_attachment_rounds_per_delivered_resource=Fraction(6),
                star_preparation_time_included=False, storage_loss_included=False,
                fresh_port_is_unmeasured=True)


def _logical_pauli(circuit, branching, offset, name, condition):
    c = code(branching)
    p = c['x_logical' if name == 'x' else 'z_logical']
    for q in range(c['photons']):
        x, z = (p[0] >> q) & 1, (p[1] >> q) & 1
        if x or z:
            circuit.add('y' if x and z else 'x' if x else 'z', offset+q, condition=condition)


def optical_reference(branching=(2, 2), lost_masks=(1,), *, known_erasures=True,
                      corrections=True):
    """Verification adapter, not the emitted physical netlist.

    Ideal gates prepare the supplied code/Bell resources. Each optical Bell
    analyser is represented by a standard Bell instrument, accepting only
    odd parity (Psi+/Psi-); bell_analyser_certificate separately derives its
    actual passive mode circuit and matching teleport Kraus operators.
    Fresh encoding happens OFFLINE before the input is touched, not online.
    """
    br, masks = tuple(branching), tuple(lost_masks)
    if type(known_erasures) is not bool or type(corrections) is not bool:
        raise TypeError('policy flags must be bool')
    if not 1 <= len(masks) <= 3:
        raise ResourceLimit('verification supports one to three transfers')
    ccode, _ = _groups(br); n = ccode['photons']
    plans = []
    for mask in masks:
        recovery_plan(br, mask)  # validates range/type even for fixed policy
        p = decoder_plan(br, known_lost_mask=mask if known_erasures else None)
        if mask & p['required_mask']:
            raise ValueError('required physical photon missing: fixed circuit cannot herald success')
        plans.append(p)
    readouts = plans[0]['measurements']
    ports = tuple(n*(len(masks)+1)+i for i in range(len(masks)))
    reference = ports[-1]+1
    c = DynamicCircuit(reference+1, len(masks)*(readouts+2)+readouts)
    c.add('h', reference).add('cx', reference, 0)
    _encode(c, br, 0)
    for i, port in enumerate(ports):
        fresh = n*(i+1)
        c.add('h', port).add('cx', port, fresh)
        _encode(c, br, fresh)
    online_start = len(c.operations)
    bit, accepted = 0, {}
    for i, (plan, mask, port) in enumerate(zip(plans, masks, ports)):
        old, fresh = n*i, n*(i+1)
        for q in range(n):
            if (mask >> q) & 1:
                c.reset(old+q)
        out, bit = _execute_decoder(c, plan, old, bit, corrections)
        # REFERENCE only; physical compiler emits two rail couplers + counts.
        c.add('cx', out, port).add('h', out)
        c.measure(out, bit).measure(port, bit+1)
        accepted[bit+1] = 1
        if corrections:
            _logical_pauli(c, br, fresh, 'x', {bit+1: 1})
            _logical_pauli(c, br, fresh, 'z', {bit: 1})
        bit += 2
    # Destructive final decoding is a verification readout, outside the
    # operational fresh-node output boundary.
    output_boundary = len(c.operations)
    logical, _ = _execute_decoder(c, decoder_plan(br), n*len(masks), bit, True)
    return dict(circuit=c, logical=logical, reference=reference, accepted=accepted,
                online_start=online_start, fresh_output_boundary=output_boundary,
                status='REFERENCE_FOR_CERTIFIED_PASSIVE_INSTRUMENT_NOT_A_CNOT_DEVICE')


def optical_witness(branching=(2, 2), lost_masks=(1,), *, known_erasures=True,
                    corrections=True):
    branching, lost_masks = tuple(branching), tuple(lost_masks)
    p = optical_reference(branching, lost_masks, known_erasures=known_erasures, corrections=corrections)
    c, event = p['circuit'], p['accepted']
    accept = probability(c, classical=event).value
    readings = {a: expectation(c, {p['logical']: a, p['reference']: a}, classical=event).value for a in 'XYZ'}
    numerator = (accept+readings['X']-readings['Y']+readings['Z'])/Exact(4)
    return dict(status='IDEAL_PASSIVE_OPTICS_WITH_SUPPLIED_RESOURCE',
                branching=list(branching), lost_masks=list(lost_masks),
                known_erasure_map_required=known_erasures,
                herald_probability=accept, rejected_probability=EONE-accept,
                joint_bell_projector=numerator,
                conditional_entanglement_fidelity=numerator/accept,
                herald_condition_reported=True, decoder_outcomes_postselected=False,
                transfers=len(lost_masks), simulator_wires=c.n_qubits)


def physical_plan(branching=(2, 2), *, known_lost_mask=None):
    branching = tuple(branching)
    d = decoder_plan(branching, known_lost_mask=known_lost_mask)
    n, measurements = d['photons'], d['measurements']
    lost = 0 if known_lost_mask is None else known_lost_mask.bit_count()
    bell_outcomes = [dict(detector_counts=r['outcome'], x=r['x_correction'], z=r['z_correction'])
                     for r in bell_analyser_certificate()['outcomes'] if r['accepted']]
    return dict(schema='native-optical-refresh-plan-v1', status='IDEAL_OPTICAL_NETLIST_NOT_FABRICATED',
                branching=list(branching), decoder=d,
                supplied_resource=dict(kind='encoded_phi_plus', photons=n+1,
                                       factory_certified_here=list(branching) == [2, 2]),
                online_operations=[{'kind':'single_photon_decoder','operations':d['operations'],
                                    'missing_required_click':'reject'},
                    {'kind':'passive_bell_analyser','modes':['old0','old1','port0','port1'],
                     'coupler_pairs':[[0,2],[1,3]], 'input_and_output_phase_steps':{'2':-16,'3':-16},
                     'phase_period':64, 'number_resolved_detection':True,
                     'detector_rule':'exactly one photon across modes 0,2 and one across 1,3',
                     'accepted_patterns_and_corrections':bell_outcomes},
                    {'kind':'logical_pauli_feedforward','x_logical':code(branching)['x_logical'],
                     'z_logical':code(branching)['z_logical'], 'order':['x','z']}],
                online_deterministic_two_photon_gates=0,
                photons=dict(old_node_slots=n, prior_losses=lost, old_photons_present=n-lost,
                             fresh_resource=n+1, maximum_input=2*n+1, input_total=2*n+1-lost,
                             detected_on_success=measurements+2,
                             discarded_old=n-measurements-1-lost, fresh_output=n),
                detector_mode_channels=2*measurements+4,
                causal_readout_stages=['decoder measurements','Bell measurement after decoder feedback','logical Pauli frame'],
                known_erasure_map_required=known_lost_mask is not None,
                physical_temperatures_measured=False)


def optical_budget(branching=(2, 2), *, memory, storage_rounds, decoder_efficiency,
                   bell_efficiency, resource_ready, pre_bell_rounds, post_bell_rounds,
                   known_erasures=False):
    """Joint herald AND intact fresh output probability in a pure-loss model.

    Supply is a full, correct resource at decoder start with probability r;
    otherwise no launch. A partial/incorrect supplied resource is outside
    this model, not assumed detectable by the Bell herald.
    Decoder measurements occur then; the decoded photon and resource wait
    pre_bell_rounds. The fresh payload waits additionally post_bell_rounds.
    Photon loss in that payload is not heralded by the consumed Bell photons.
    No dark counts, multipair photons or imperfect interference are included.
    """
    br = tuple(branching); d = decoder_plan(br); n = d['photons']
    if type(known_erasures) is not bool:
        raise TypeError('known_erasures must be bool')
    vals = {name: record_probability(v, name) for name, v in (
        ('memory', memory), ('decoder efficiency', decoder_efficiency),
        ('Bell efficiency', bell_efficiency), ('resource readiness', resource_ready))}
    times = [integer(t, 'rounds') for t in (storage_rounds, pre_bell_rounds, post_bell_rounds)]
    if min(times) < 0 or sum(times) > 256:
        raise ResourceLimit('nonnegative rounds with total at most 256 required')
    t, pre, post = times; m = vals['memory']
    input_ok = (memory_lifetime(br, m, t)['p_no_refresh'] if known_erasures
                else m**(t*len(d['required_photons'])))
    detect = vals['decoder efficiency']**d['measurements'] * vals['Bell efficiency']**2
    herald = input_ok*vals['resource readiness']*Fraction(1,2)*detect*m**(2*pre)
    payload = m**(n*(pre+post))
    return dict(status='DECLARED_PURE_LOSS_JOINT_BUDGET_NOT_MEASURED_FIDELITY',
                branching=list(br),
                inputs=dict(memory=m, storage_rounds=t, pre_bell_rounds=pre,
                            post_bell_rounds=post, decoder_efficiency=vals['decoder efficiency'],
                            bell_efficiency=vals['Bell efficiency'], resource_ready=vals['resource readiness']),
                policy='KNOWN_ERASURE_ORACLE' if known_erasures else 'FIXED_PHYSICAL_MEASUREMENTS',
                supply_model='full correct resource or no launch; partial-source false heralds excluded',
                input_usable_probability=input_ok, intrinsic_bell_success=Fraction(1,2),
                required_decoder_detections=d['measurements'], total_required_detections=d['measurements']+2,
                herald_probability=herald, fresh_payload_survival=payload,
                herald_and_intact_output_probability=herald*payload,
                payload_loss_can_be_unheralded=payload < 1,
                elapsed_rounds=t+pre+post, resource_factory_time_included=False,
                conditional_fidelity_with_payload_loss_not_claimed=True)
