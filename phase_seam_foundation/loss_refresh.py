"""Age-aware tree memory and an ideal coherent refresh circuit (v0.28).

Reuse the v0.26 stabiliser code and the existing native dynamic calculator.
Known erasures are partial traces; a decoder never operates on a lost wire.
The Clifford decoder/teleporter is a circuit specification, NOT a compiled
linear-optical device. Its physical success, latency and resource supply are
explicit inputs to the separate lifetime budget.
"""
from collections import Counter
from fractions import Fraction
from functools import lru_cache

from native_relational_qc.dynamic import DynamicCircuit
from native_relational_qc.dynamic_examples import bell_fidelity

from .loss_tolerant_code import code, loss_polynomials
from .model import ResourceLimit, integer, rational

MAX_ROUNDS = 256
MAX_TRANSFERS = 4


def _unit(value, label):
    if type(value) is str:
        value = Fraction(value)
    value = rational(value, label, 256)
    if not 0 <= value <= 1:
        raise ValueError(f"{label} must lie in [0, 1]")
    return value


def _rounds(value, label="rounds", minimum=0):
    value = integer(value, label)
    if not minimum <= value <= MAX_ROUNDS:
        raise ResourceLimit(f"{label} must lie in [{minimum}, {MAX_ROUNDS}]")
    return value


@lru_cache(maxsize=32)
def _counts(branching):
    p = loss_polynomials(branching)
    return p["photons"], tuple(p["counts"]["both"])


def _survival(branching, memory, rounds):
    n, counts = _counts(tuple(branching))
    alive = memory ** rounds
    lost = 1 - alive
    # The inputs are bounded before exponentiation. Do not round the derived
    # loss to fit evaluate()'s 256-bit *input* bound at long storage times.
    return sum((Fraction(a) * lost**j * alive**(n-j)
                for j, a in enumerate(counts)), Fraction())


def memory_lifetime(branching, memory, rounds):
    """Exact P_both(1-m**t) for ONE block with no photon replenishment.

    Independent identical loss each round composes to per-photon survival
    m**t. Correctable erasure sets are downward closed, so recoverability at
    the final time also implies recoverability at all earlier times.
    """
    branching = tuple(branching)
    m, t = _unit(memory, "memory"), _rounds(rounds)
    n, _ = _counts(tuple(branching))
    one = _survival(branching, m, 1)
    return dict(branching=list(branching), photons=n, memory=m, rounds=t,
                p_no_refresh=_survival(branching, m, t),
                p_ideal_refresh_every_round=one**t,
                effective_photon_loss=1-m**t,
                status="EXACT_INDEPENDENT_ERASURE_MODEL_NO_DEVICE")


def refresh_budget(branching, memory, storage_intervals, *, latency_rounds,
                   transfer_success, resource_ready, bell_pairs_per_attempt):
    """A fresh block after EACH interval, including the last interval.

    The incoming encoded input is supplied. The old block ages during both
    storage and transfer latency. `resource_ready` is whole-resource readiness
    at the deadline (including its buffer/switch losses), independent of old
    block erasures. `transfer_success` is a heralded, input-independent success
    probability; conditioned on success its channel is the identity.
    `bell_pairs_per_attempt` prices a reserved fresh resource PLUS transfer.
    These are declared engineering inputs, not inferred from v0.27 estimates.
    Costs are expected over independent input trials, with early abort; an
    unknown input cannot be recreated/retried after an uncorrectable loss.
    """
    branching = tuple(branching)
    m = _unit(memory, "memory")
    delay = _rounds(latency_rounds, "latency rounds")
    q = _unit(transfer_success, "transfer success")
    ready = _unit(resource_ready, "resource readiness")
    cost = rational(Fraction(bell_pairs_per_attempt) if type(bell_pairs_per_attempt) is str
                    else bell_pairs_per_attempt, "Bell pairs per attempt", 256)
    if cost < 0:
        raise ValueError("Bell-pair cost must be nonnegative")
    intervals = list(storage_intervals)
    if not 1 <= len(intervals) <= MAX_ROUNDS:
        raise ResourceLimit("supply 1..256 storage intervals")
    intervals = [_rounds(v, "storage interval", 1) for v in intervals]
    total = _rounds(sum(intervals) + len(intervals)*delay, "elapsed rounds")
    n, _ = _counts(tuple(branching))
    survival, attempts, rows = Fraction(1), Fraction(), []
    for t in intervals:
        attempts += survival  # resource reservation charged even if this cycle fails
        recover = _survival(branching, m, t + delay)
        cycle = recover * ready * q
        survival *= cycle
        rows.append(dict(storage_rounds=t, latency_rounds=delay,
                         p_recover_before_transfer=recover, p_cycle=cycle,
                         p_reach_fresh_block=survival))
    bare = _survival(branching, m, total)
    return dict(status="DECLARED_REFRESH_BUDGET_NOT_HARDWARE_BOUND",
                branching=list(branching), photons_per_block=n,
                elapsed_rounds=total, transfers=len(intervals), cycles=rows,
                transfer_success=q, resource_ready=ready,
                p_complete=survival, p_no_refresh_same_elapsed_time=bare,
                improves_survival=survival > bare,
                expected_refresh_attempts=attempts,
                expected_bell_pairs_per_input_trial=cost*attempts,
                bell_pairs_on_all_success_path=cost*len(intervals),
                initial_encoding_cost_included=False,
                physical_refresh_implemented=False)


def _groups(branching):
    br = tuple(branching)
    if len(br) != 2:
        raise ValueError("the coherent decoder currently supports depth-two trees")
    c = code(br)  # uses the same shape/integer/16-photon limits as v0.26
    b, leaves = br
    groups = tuple((i,) + tuple(b+i*leaves+j for j in range(leaves)) for i in range(b))
    return c, groups


def recovery_plan(branching, lost_mask):
    """A depth-two tree is locally a concatenated repetition code.

    X_L is available iff every group has a survivor; Z_L iff one group is
    completely intact. Use that intact group as output, measure one survivor
    in every other group, and retain their parity as a phase correction.
    """
    c, groups = _groups(branching)
    lost = integer(lost_mask, "lost mask")
    if not 0 <= lost < 1 << c["photons"]:
        raise ValueError("lost mask outside the encoded block")
    survivors = [tuple(q for q in group if not (lost >> q) & 1) for group in groups]
    intact = next((i for i, g in enumerate(groups) if survivors[i] == g), None)
    ok = intact is not None and all(survivors)
    return dict(branching=list(branching), photons=c["photons"], lost_mask=lost,
                recoverable=ok, intact_group=intact if ok else None,
                output=groups[intact][0] if ok else None,
                measured_survivors=tuple(g[0] for i, g in enumerate(survivors)
                                         if i != intact) if ok else (),
                groups=groups)


def _encode(circuit, branching, offset):
    _, groups = _groups(branching)
    for g in groups[1:]:
        circuit.add("cx", offset, offset+g[0])
    for g in groups:
        circuit.add("h", offset+g[0])
        for q in g[1:]:
            circuit.add("cx", offset+g[0], offset+q).add("h", offset+q)


def _decode(circuit, plan, offset, bit, corrections):
    if not plan["recoverable"]:
        raise ValueError("uncorrectable erasure pattern; no recovery circuit emitted")
    # Local Hadamards take the graph code to block-GHZ form. Lost wires are
    # inaccessible even though the calculator retains a reset placeholder.
    for group in plan["groups"]:
        for q in group[1:]:
            if not (plan["lost_mask"] >> q) & 1:
                circuit.add("h", offset+q)
    for j, q in enumerate(plan["measured_survivors"]):
        circuit.measure(offset+q, bit+j)
    out = offset+plan["output"]
    for q in plan["groups"][plan["intact_group"]][1:]:
        circuit.add("cx", out, offset+q)
    circuit.add("h", out)
    if corrections:
        for j in range(len(plan["measured_survivors"])):
            circuit.add("z", out, condition={bit+j: 1})
    return out, bit+len(plan["measured_survivors"])


def refresh_circuit(branching=(2, 2), lost_masks=(1,), *, corrections=True):
    """Reference-entangled input -> erase/decode/teleport/re-encode -> decode.

    All measurement branches are included, with explicit classical feedback.
    Lost wires are traced/reset and never accessed by the decoder. Fresh
    blocks use new wires, not resets pretending to recover the lost input.
    An empty schedule gives an encode/decode control. At most four transfers.
    Deterministic CNOTs and perfect readout are *ideal circuit assumptions*;
    no equivalence to the probabilistic optical fusion primitive is asserted.
    """
    if type(corrections) is not bool:
        raise TypeError("corrections must be bool")
    branching, masks = tuple(branching), tuple(lost_masks)
    if len(masks) > MAX_TRANSFERS:
        raise ResourceLimit("at most four coherent refresh transfers")
    empty = recovery_plan(branching, 0)
    plans = [recovery_plan(branching, lost) for lost in masks]
    if any(not p["recoverable"] for p in plans):
        raise ValueError("uncorrectable erasure pattern; unknown input cannot be retried")
    n, b = empty["photons"], len(empty["groups"])
    helper = n*(len(masks)+1)
    reference = helper+1
    c = DynamicCircuit(reference+1, (b+1)*len(masks)+b-1)
    c.add("h", reference).add("cx", reference, 0)
    _encode(c, branching, 0)
    bit, offset = 0, 0
    for plan in plans:
        for q in range(n):
            if (plan["lost_mask"] >> q) & 1:
                c.reset(offset+q)  # partial trace, not a postselected outcome
        out, bit = _decode(c, plan, offset, bit, corrections)
        fresh = offset+n
        c.reset(helper).add("h", helper).add("cx", helper, fresh)
        c.add("cx", out, helper).add("h", out)
        c.measure(out, bit).measure(helper, bit+1)
        if corrections:
            c.add("x", fresh, condition={bit+1: 1}).add("z", fresh, condition={bit: 1})
        bit += 2
        _encode(c, branching, fresh)
        offset = fresh
    out, _ = _decode(c, empty, offset, bit, corrections)
    return dict(circuit=c, logical=out, reference=reference, lost_masks=masks,
                photons_per_block=n, transfers=len(masks),
                peak_live_data_and_helper_wires=2*n+1 if masks else n,
                status="IDEAL_COHERENT_CIRCUIT_NO_PHOTONIC_COMPILATION")


def refresh_witness(branching=(2, 2), lost_masks=(1,), *, corrections=True):
    """Exact Choi/Bell test, averaged over every syndrome/teleport outcome.

    Bell fidelity one for this trace-preserving channel establishes identity
    on arbitrary inputs, including inputs entangled with an external system.
    """
    branching, lost_masks = tuple(branching), tuple(lost_masks)
    program = refresh_circuit(branching, lost_masks, corrections=corrections)
    fidelity, readings = bell_fidelity(program["circuit"], program["logical"], program["reference"])
    return dict(status=program["status"], branching=list(branching), lost_masks=list(lost_masks),
                transfers=program["transfers"], entanglement_fidelity=fidelity,
                correlations={axis: r.value for axis, r in readings.items()},
                operations=dict(Counter(op.kind for op in program["circuit"].operations)),
                simulator_wires=program["circuit"].n_qubits,
                peak_live_data_and_helper_wires=program["peak_live_data_and_helper_wires"],
                external_reference_wires=1, outcomes_postselected=False,
                peak_observer_terms=max(r.peak_terms for r in readings.values()))
