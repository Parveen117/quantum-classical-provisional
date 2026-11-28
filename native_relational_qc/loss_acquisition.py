"""Retained click-event accounting with a declared conditional instrument model.

Counts, yield and readout errors are exact. Instrument probabilities, detector
flags and physical provenance remain declared by the supplied source artifacts.
"""
import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from .calculator import MAX_INPUT_BYTES, _object, loads
from .compact import ResourceLimit, _integer
from .model_experiment import (
    _acquisition_context, _fraction, _rational, _seal, _sha, _text, _unseal, verify_plan,
)
from .self_learning import FIELD, digest


PLAN_SCHEMA = "nrqc-loss-experiment-plan-v1"
REPORT_SCHEMA = "nrqc-loss-observation-v1"
CONTROLLER_SCHEMA = "nrqc-controller-events-v1"
ACQUISITION_SCHEMA = "nrqc-loss-acquisition-result-v1"
REJECTS = ("unclassified", "no_herald", "guard_or_code_violation", "no_click", "ambiguous_click")
FLAGS = ("timing_invalid", "counter_overflow", "unclassified")
OUTCOMES = ("accepted:0", "accepted:1") + tuple("rejected:" + key for key in REJECTS)
ACQUISITION_FIELDS = ("schema", "plan_fingerprint", "binding_fingerprint", "program_sha256",
                      "policy_fingerprint", "controller_program_sha256", "job_id", "origin",
                      "provider", "backend", "started_at", "completed_at", "attempts",
                      "window_ns", "events", "source_sha256")


def _window(document):
    _object(document, ("start", "stop"))
    start = _integer(document["start"], "window start nanoseconds", 0, 1_000_000_000)
    stop = _integer(document["stop"], "window stop nanoseconds", 1, 1_000_000_000)
    if start >= stop:
        raise ValueError("detection window must have positive width")
    return dict(start=start, stop=stop)


def click_policy(document, experiment):
    _object(document, ("schema", "encoding", "channels", "readout_pairs", "herald_counts",
                       "guard_channels", "window_ns", "controller_program_sha256", "rejection_priority"))
    if document["schema"] != "nrqc-click-policy-v1" or document["encoding"] != "dual_rail_one_click_per_measured_wire":
        raise ValueError("unsupported click policy or two-level detector encoding")
    channels = document["channels"]
    if not isinstance(channels, list) or not 2 <= len(channels) <= 32:
        raise ValueError("click policy requires 2..32 ordered detector channels")
    for channel in channels:
        _text(channel, "detector channel", 48)
    if len(set(channels)) != len(channels):
        raise ValueError("detector channels must be unique")
    pairs, used = document["readout_pairs"], set()
    if not isinstance(pairs, list) or len(pairs) != len(experiment["measure_wires"]):
        raise ValueError("one ordered detector pair is required per measured physical wire")
    for pair, wire in zip(pairs, experiment["measure_wires"]):
        _object(pair, ("physical_wire", "zero", "one"))
        _integer(pair["physical_wire"], "physical readout wire", 0, experiment["prediction"]["device"]["n_qubits"] - 1)
        if pair["physical_wire"] != wire:
            raise ValueError("detector pairs must follow the frozen physical-to-classical measurement map")
        for bit in ("zero", "one"):
            if pair[bit] not in channels or pair[bit] in used:
                raise ValueError("readout detectors must be known and disjoint")
            used.add(pair[bit])
    herald = document["herald_counts"]
    if not isinstance(herald, dict):
        raise ValueError("herald counts require an explicit detector-to-count object")
    for channel, count in herald.items():
        if channel not in channels or channel in used:
            raise ValueError("herald detectors must be known and separate from the data readout")
        _integer(count, "required herald detector count", 0, 16)
        used.add(channel)
    guards = document["guard_channels"]
    if not isinstance(guards, list):
        raise ValueError("guard channels require an explicit list")
    for channel in guards:
        if channel not in channels or channel in used:
            raise ValueError("guard detectors must be known and disjoint")
        used.add(channel)
    if document["rejection_priority"] != list(REJECTS):
        raise ValueError("unsupported rejection precedence")
    _sha(document["controller_program_sha256"], "full controller instrument program hash")
    result = copy.deepcopy(document)
    result["window_ns"] = _window(document["window_ns"])
    return result


def _probability(document):
    value = FIELD.from_dict(document)
    if value.max_bits > 4096:
        raise ResourceLimit("instrument probability coefficient budget exceeded")
    if value != value.conjugate() or value.real_sign() < 0 or (value - 1).real_sign() > 0:
        raise ValueError("instrument probabilities must be real values in [0,1]")
    return value


def instrument_reference(specification, experiment, policy):
    _object(specification, ("schema", "kind", "model_id", "source_sha256", "parameters"))
    if specification["schema"] != "nrqc-loss-reference-v1":
        raise ValueError("unsupported conditional instrument reference")
    _text(specification["model_id"], "instrument model identity")
    _sha(specification["source_sha256"], "instrument model source hash")
    parameters = specification["parameters"]
    if specification["kind"] == "scalar_survival":
        _object(parameters, ("survival", "rejection_weights"))
        survival = _fraction(parameters["survival"])
        if not survival:
            raise ValueError("reference accepted probability must be positive")
        weights = parameters["rejection_weights"]
        _object(weights, REJECTS)
        weights = {key: _fraction(weights[key]) for key in REJECTS}
        if sum(weights.values()) != 1:
            raise ValueError("conditional rejection weights must sum to one")
        p = FIELD.from_dict(experiment["prediction"]["probability_one"])
        joint = {"accepted:0": (1 - p) * survival, "accepted:1": p * survival}
        joint.update({"rejected:" + key: FIELD((1 - survival) * weight) for key, weight in weights.items()})
        canonical = dict(survival=_rational(survival), rejection_weights={key: _rational(q) for key, q in weights.items()})
        basis = "declared input-independent scalar survival multiplying the ideal channel"
    elif specification["kind"] == "declared_joint":
        _object(parameters, ("joint_distribution",))
        _object(parameters["joint_distribution"], OUTCOMES)
        joint = {key: _probability(parameters["joint_distribution"][key]) for key in OUTCOMES}
        canonical = dict(joint_distribution={key: q.to_dict() for key, q in joint.items()})
        basis = "declared input-specific accepted/rejected probabilities; no channel reconstruction"
    else:
        raise ValueError("select scalar_survival or declared_joint explicitly")
    if sum(joint.values(), FIELD(0)) != FIELD(1):
        raise ValueError("instrument joint distribution must sum exactly to one")
    accepted = joint["accepted:0"] + joint["accepted:1"]
    if accepted.real_sign() <= 0:
        raise ValueError("reference accepted probability must be positive")
    conditional = joint["accepted:1"] / accepted
    if conditional.max_bits > 4096:
        raise ResourceLimit("conditional reference coefficient budget exceeded")
    spec = dict(specification, parameters=canonical)
    reference = dict(prediction_fingerprint=experiment["prediction"]["fingerprint"],
                     policy_fingerprint=digest(policy), joint_distribution={key: q.to_dict() for key, q in joint.items()},
                     accepted_probability=accepted.to_dict(), conditional_probability_one=conditional.to_dict(),
                     basis=basis, evidence_class="DECLARED_INSTRUMENT_MODEL", source_authentication="not_performed")
    return spec, reference


def _thresholds(document, attempts):
    _object(document, ("minimum_yield", "minimum_accepted", "conditional_tolerance", "joint_tolerance", "maximum_unclassified"))
    result = {key: _rational(_fraction(document[key])) for key in document if key != "minimum_accepted"}
    result["minimum_accepted"] = _integer(document["minimum_accepted"], "minimum accepted attempts", 1, attempts)
    return result


def loss_plan(experiment, policy, reference_spec, thresholds):
    verify_plan(experiment)
    policy = click_policy(policy, experiment)
    spec, reference = instrument_reference(reference_spec, experiment, policy)
    thresholds = _thresholds(thresholds, experiment["shots"])
    return _seal(dict(schema=PLAN_SCHEMA, experiment=copy.deepcopy(experiment), click_policy=policy,
                      reference_spec=spec, reference=reference, thresholds=thresholds,
                      statistic="joint per-attempt outcomes and conditional accepted Z marginal",
                      evidence_class="OFFLINE_LOSS_EXPERIMENT_PLAN", hardware_submissions=0))


def verify_loss_plan(plan):
    _unseal(plan, PLAN_SCHEMA)
    replay = loss_plan(plan["experiment"], plan["click_policy"], plan["reference_spec"], plan["thresholds"])
    if replay != plan:
        raise ValueError("loss experiment plan differs from exact regenerated plan")
    return dict(status="verified", fingerprint=plan["fingerprint"])


def _acquisition(plan, document):
    _object(document, ACQUISITION_FIELDS)
    if document["schema"] != ACQUISITION_SCHEMA:
        raise ValueError("unsupported retained-event acquisition schema")
    attempts = _acquisition_context(plan["experiment"], document, plan_fingerprint=plan["fingerprint"], shots_key="attempts")
    policy = plan["click_policy"]
    if document["policy_fingerprint"] != digest(policy) or document["controller_program_sha256"] != policy["controller_program_sha256"]:
        raise ValueError("raw events differ from the frozen click policy or full controller program")
    if _window(document["window_ns"]) != policy["window_ns"]:
        raise ValueError("raw detector window differs from the frozen policy")
    events = document["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= 4096:
        raise ValueError("raw event histogram requires 1..4096 rows")
    seen, total = set(), 0
    for event in events:
        _object(event, ("clicks", "flags", "count"))
        clicks, flags = event["clicks"], event["flags"]
        if not isinstance(clicks, list) or len(clicks) != len(policy["channels"]):
            raise ValueError("every event must retain all declared detector channels")
        for count in clicks:
            _integer(count, "detector click count", 0, 16)
        if (not isinstance(flags, list) or len(flags) > len(FLAGS) or
                any(flag not in FLAGS for flag in flags) or len(set(flags)) != len(flags)):
            raise ValueError("event flags must be unique declared diagnostics")
        key = tuple(clicks), tuple(sorted(flags))
        if key in seen:
            raise ValueError("duplicate histogram rows must be combined by the controller")
        seen.add(key)
        total += _integer(event["count"], "event multiplicity", 1, attempts)
    if total != attempts:
        raise ValueError("accepted and rejected raw events must account for every attempted shot")
    return copy.deepcopy(document)


def decode_events(policy, events):
    accepted, rejected = {}, dict.fromkeys(REJECTS, 0)
    matched, flag_counts = dict.fromkeys(REJECTS, 0), dict.fromkeys(FLAGS, 0)
    known = set(policy["herald_counts"]) | set(policy["guard_channels"])
    known |= {pair[bit] for pair in policy["readout_pairs"] for bit in ("zero", "one")}
    for event in events:
        values = dict(zip(policy["channels"], event["clicks"]))
        count = event["count"]
        sums = [values[pair["zero"]] + values[pair["one"]] for pair in policy["readout_pairs"]]
        predicates = dict(unclassified=bool(event["flags"]) or any(values[ch] for ch in values if ch not in known),
                          no_herald=any(values[ch] != expected for ch, expected in policy["herald_counts"].items()),
                          guard_or_code_violation=any(values[ch] for ch in policy["guard_channels"]),
                          no_click=any(value == 0 for value in sums), ambiguous_click=any(value > 1 for value in sums))
        for key in REJECTS:
            matched[key] += count if predicates[key] else 0
        for flag in event["flags"]:
            flag_counts[flag] += count
        reject = next((key for key in REJECTS if predicates[key]), None)
        if reject is not None:
            rejected[reject] += count
        else:
            bits = [values[pair["one"]] for pair in policy["readout_pairs"]]
            key = "".join(map(str, reversed(bits)))
            accepted[key] = accepted.get(key, 0) + count
    return dict(accepted_counts=accepted, rejected_counts=rejected,
                matched_predicate_counts=matched, diagnostic_flag_counts=flag_counts)


def _absolute(value):
    return -value if value.real_sign() < 0 else value


def _approximate(value):
    low, high = value.real_bounds(20)
    return float((low + high) / 2)


def _bridge(plan, acquired, counts):
    experiment = plan["experiment"]
    return dict(root=dict(prediction_fingerprint=experiment["prediction"]["fingerprint"],
                          model_fingerprint=experiment["prediction"]["model"]["fingerprint"]),
                template=dict(plan_fingerprint=plan["fingerprint"], program_sha256=experiment["program_sha256"],
                              controller_program_sha256=plan["click_policy"]["controller_program_sha256"],
                              policy_fingerprint=digest(plan["click_policy"])),
                phase=dict(binding=experiment["binding"], job_id=acquired["job_id"],
                           started_at=acquired["started_at"], completed_at=acquired["completed_at"]),
                observed=counts, backend=acquired["backend"], shots=acquired["attempts"],
                expected_model=dict(model_id=digest(plan["reference"]), model_type="nrqc_loss_joint_readout_v1",
                                    distribution={key: _approximate(FIELD.from_dict(value)) for key, value in plan["reference"]["joint_distribution"].items()},
                                    tolerance=float(_fraction(plan["thresholds"]["joint_tolerance"])),
                                    metadata=dict(floating_bridge_view=True, scope=plan["statistic"])),
                metadata=dict(evidence_origin=acquired["origin"], source_sha256=acquired["source_sha256"],
                              source_authentication="not_performed", hardware_submissions=0,
                              exact_classification_in=REPORT_SCHEMA, physical_phase_observation=False))


def observe_loss(plan, acquisition):
    verify_loss_plan(plan)
    acquired = _acquisition(plan, acquisition)
    decoded = decode_events(plan["click_policy"], acquired["events"])
    accepted = sum(decoded["accepted_counts"].values())
    attempts = acquired["attempts"]
    bit = plan["experiment"]["readout_classical_bit"]
    one = sum(count for key, count in decoded["accepted_counts"].items() if key[-1 - bit] == "1")
    joint = {"accepted:0": accepted - one, "accepted:1": one}
    joint.update({"rejected:" + key: count for key, count in decoded["rejected_counts"].items()})
    if sum(joint.values()) != attempts:
        raise ArithmeticError("event partition did not conserve attempted shots")
    reference = {key: FIELD.from_dict(value) for key, value in plan["reference"]["joint_distribution"].items()}
    joint_error = sum((_absolute(FIELD(Fraction(joint[key], attempts)) - reference[key]) for key in OUTCOMES), FIELD(0)) / 2
    conditional = Fraction(one, accepted) if accepted else None
    conditional_error = _absolute(FIELD(conditional) - FIELD.from_dict(plan["reference"]["conditional_probability_one"])) if accepted else None
    thresholds = plan["thresholds"]
    yield_value = Fraction(accepted, attempts)
    gates = dict(minimum_yield=yield_value >= _fraction(thresholds["minimum_yield"]),
                 minimum_accepted=accepted >= thresholds["minimum_accepted"],
                 maximum_unclassified=Fraction(decoded["rejected_counts"]["unclassified"], attempts) <= _fraction(thresholds["maximum_unclassified"]),
                 joint_error=(joint_error - _fraction(thresholds["joint_tolerance"])).real_sign() <= 0,
                 conditional_error=conditional_error is not None and (conditional_error - _fraction(thresholds["conditional_tolerance"])).real_sign() <= 0)
    complete = accepted > 0 and gates["minimum_accepted"]
    qualified = complete and all(gates.values())
    return _seal(dict(schema=REPORT_SCHEMA, plan=copy.deepcopy(plan), acquisition=acquired, **decoded,
                      attempts=attempts, accepted=accepted, accepted_yield=_rational(yield_value),
                      accepted_marginal_counts={"0": accepted - one, "1": one}, joint_counts=joint,
                      observed_joint_distribution={key: _rational(Fraction(count, attempts)) for key, count in joint.items()},
                      conditional_probability_one=_rational(conditional) if conditional is not None else None,
                      expected_conditional_probability_one=plan["reference"]["conditional_probability_one"],
                      ideal_unitary_probability_one=plan["experiment"]["prediction"]["probability_one"],
                      conditional_absolute_error=conditional_error.to_dict() if conditional_error is not None else None,
                      joint_total_variation_error=joint_error.to_dict(), qualification_gates=gates,
                      qualification_passed=qualified, status="complete" if complete else "incomplete",
                      classification="QUALIFIED" if qualified else "RESIDUE" if complete else "INCOMPLETE",
                      bridge_payload=_bridge(plan, acquired, joint),
                      evidence_class={"synthetic": "SYNTHETIC_LOSS_OBSERVATION", "simulator": "DECLARED_SIMULATOR_LOSS_OBSERVATION",
                                      "physical_backend": "DECLARED_PHYSICAL_LOSS_OBSERVATION"}[acquired["origin"]],
                      source_authentication="not_performed", hardware_submissions=0,
                      scope="declared click policy and input-specific instrument probabilities; no inferred lost-photon labels"))


def _controller(source_bytes):
    if not isinstance(source_bytes, bytes) or len(source_bytes) > MAX_INPUT_BYTES:
        raise ValueError("controller events require at most 64 MiB of UTF-8 JSON bytes")
    document = loads(source_bytes.decode("utf-8"))
    _object(document, ACQUISITION_FIELDS[:-1])
    if document["schema"] != CONTROLLER_SCHEMA:
        raise ValueError("unsupported controller-events schema")
    return dict(document, schema=ACQUISITION_SCHEMA, source_sha256=hashlib.sha256(source_bytes).hexdigest())


def import_loss_events(plan, source_bytes):
    return observe_loss(plan, _controller(source_bytes))


def verify_loss_observation(report, *, source_bytes=None):
    _unseal(report, REPORT_SCHEMA)
    replay = observe_loss(report["plan"], report["acquisition"])
    if replay != report:
        raise ValueError("loss observation differs from deterministic exact replay")
    if source_bytes is not None:
        acquired = _acquisition(report["plan"], _controller(source_bytes))
        if acquired != report["acquisition"]:
            raise ValueError("controller event artifact bytes differ from the recorded acquisition")
    return dict(status="verified", fingerprint=report["fingerprint"], qualification_passed=report["qualification_passed"],
                classification=report["classification"], source_artifact_hash_verified=source_bytes is not None,
                source_authentication="not_performed")


def main(argv=None, *, command="loss-plan"):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path)
    if command == "loss-plan":
        for name in ("policy", "reference", "thresholds"):
            parser.add_argument("--" + name, type=Path, required=True)
    elif command == "import-loss-events":
        parser.add_argument("artifact", type=Path)
    else:
        parser.add_argument("--source-artifact", type=Path)
    args = parser.parse_args(argv)
    def read_bytes(path):
        with path.open("rb") as stream:
            return stream.read(MAX_INPUT_BYTES + 1)
    def read(path):
        return loads(read_bytes(path).decode("utf-8"))
    try:
        document = read(args.input)
        if command == "loss-plan":
            output = loss_plan(document, read(args.policy), read(args.reference), read(args.thresholds))
        elif command == "import-loss-events":
            output = import_loss_events(document, read_bytes(args.artifact))
        else:
            output = verify_loss_observation(document, source_bytes=read_bytes(args.source_artifact) if args.source_artifact else None)
        code = 0
    except (ValueError, TypeError, KeyError, OSError) as error:
        output, code = dict(status="invalid_request", error=str(error)), 2
    except ResourceLimit as error:
        output, code = dict(status="incomplete", error=str(error)), 1
    except ArithmeticError as error:
        output, code = dict(status="verification_failed", error=str(error)), 1
    rendered = json.dumps(output, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return code
