"""Bind a replayed saved-model prediction to declared acquisitions and raw counts.

This is an offline contract and evidence adapter. It neither submits a job nor
authenticates a provider's assertion that supplied counts came from hardware.
"""
import argparse
import copy
from datetime import datetime
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

from .calculator import MAX_INPUT_BYTES, _object, loads
from .compact import ResourceLimit, _integer
from .model_runtime import verify_prediction
from .self_learning import FIELD, digest


PLAN_SCHEMA = "nrqc-model-experiment-plan-v1"
BINDING_SCHEMA = "nrqc-acquisition-binding-v1"
RESULT_SCHEMA = "nrqc-acquisition-result-v1"
CONTROLLER_SCHEMA = "nrqc-controller-counts-v1"
REPORT_SCHEMA = "nrqc-model-observation-v1"
ORIGINS = ("synthetic", "simulator", "physical_backend")
RESULT_FIELDS = ("schema", "plan_fingerprint", "binding_fingerprint", "program_sha256",
                 "job_id", "origin", "provider", "backend", "started_at", "completed_at",
                 "shots", "counts", "source_sha256")


def _text(value, name, maximum=160):
    if (not isinstance(value, str) or not 1 <= len(value) <= maximum or
            value != value.strip() or any(ord(c) < 32 for c in value)):
        raise ValueError(f"{name} requires nonempty bounded text without control characters")
    return value


def _sha(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{name} requires a lowercase SHA-256 digest")
    return value


def _time(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value):
        raise ValueError("timestamps require UTC YYYY-MM-DDTHH:MM:SSZ")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def _fraction(value):
    _object(value, ("numerator", "denominator"))
    numerator = _integer(value["numerator"], "tolerance numerator", 0, 1_000_000_000)
    denominator = _integer(value["denominator"], "tolerance denominator", 1, 1_000_000_000)
    if numerator > denominator:
        raise ValueError("absolute probability tolerance must be in [0,1]")
    return Fraction(numerator, denominator)


def _rational(value):
    return dict(numerator=value.numerator, denominator=value.denominator)


def acquisition_binding(document):
    _object(document, ("schema", "origin", "provider", "backend", "device_fingerprint", "calibration"))
    if document["schema"] != BINDING_SCHEMA or document["origin"] not in ORIGINS:
        raise ValueError("unsupported acquisition binding or undeclared data origin")
    for key in ("provider", "backend"):
        _text(document[key], key)
    _sha(document["device_fingerprint"], "device fingerprint")
    calibration = document["calibration"]
    _object(calibration, ("calibration_id", "source_sha256", "captured_at", "valid_until"))
    _text(calibration["calibration_id"], "calibration identity")
    _sha(calibration["source_sha256"], "calibration source hash")
    if _time(calibration["captured_at"]) >= _time(calibration["valid_until"]):
        raise ValueError("calibration validity must end after capture")
    return copy.deepcopy(document)


def _seal(payload):
    payload = copy.deepcopy(payload)
    return dict(payload, fingerprint=digest(payload))


def _unseal(document, schema):
    if not isinstance(document, dict) or document.get("schema") != schema:
        raise ValueError(f"a {schema} document is required")
    payload = {k: v for k, v in document.items() if k != "fingerprint"}
    if document.get("fingerprint") != digest(payload):
        raise ValueError("document fingerprint mismatch")
    return payload


def experiment_plan(prediction, binding, *, run_id, shots, tolerance, measure_wires=None):
    """Freeze the exact program, raw-count convention and absolute tolerance."""
    verify_prediction(prediction)
    binding = acquisition_binding(binding)
    if binding["device_fingerprint"] != digest(prediction["device"]):
        raise ValueError("acquisition device differs from the compiled prediction")
    _text(run_id, "run identity")
    shots = _integer(shots, "planned shots", 1, 1_000_000_000)
    tolerance = _fraction(tolerance)
    readout = prediction["mapping"]["final_layout"]["3"]
    wires = [readout] if measure_wires is None else measure_wires
    n = prediction["device"]["n_qubits"]
    if not isinstance(wires, list) or not 1 <= len(wires) <= n:
        raise ValueError("measured physical wires require a nonempty list")
    for q in wires:
        _integer(q, "measured physical wire", 0, n - 1)
    if len(set(wires)) != len(wires) or readout not in wires:
        raise ValueError("measured wires must be unique and include the final model readout")
    # The static unitary importer deliberately excludes measurements. Retain its
    # exact text and append only a regenerated, terminal Z measurement map.
    lines = prediction["openqasm"].splitlines()
    lines.insert(3, f"creg c[{len(wires)}];")
    lines += [f"measure q[{q}] -> c[{bit}];" for bit, q in enumerate(wires)]
    program = "\n".join(lines) + "\n"
    return _seal(dict(schema=PLAN_SCHEMA, run_id=run_id, prediction=copy.deepcopy(prediction),
                      binding=binding, shots=shots, tolerance=_rational(tolerance),
                      measure_wires=wires.copy(), readout_classical_bit=wires.index(readout),
                      counts_bit_order="c[width-1]...c[0], most significant bit on the left",
                      measured_openqasm=program,
                      program_sha256=hashlib.sha256(program.encode()).hexdigest(),
                      statistic="raw Z-readout marginal absolute probability error",
                      acceptance_policy="fixed absolute engineering tolerance; no significance claim",
                      evidence_class="OFFLINE_EXPERIMENT_PLAN", hardware_submissions=0))


def verify_plan(plan):
    _unseal(plan, PLAN_SCHEMA)
    replay = experiment_plan(plan["prediction"], plan["binding"], run_id=plan["run_id"],
                             shots=plan["shots"], tolerance=plan["tolerance"],
                             measure_wires=plan["measure_wires"])
    if replay != plan:
        raise ValueError("experiment plan differs from exact regenerated plan")
    return dict(status="verified", fingerprint=plan["fingerprint"])


def _result(plan, document):
    _object(document, RESULT_FIELDS)
    if document["schema"] != RESULT_SCHEMA:
        raise ValueError("unsupported acquisition-result schema")
    for key, expected in (("plan_fingerprint", plan["fingerprint"]),
                          ("binding_fingerprint", digest(plan["binding"])),
                          ("program_sha256", plan["program_sha256"])):
        if document[key] != expected:
            raise ValueError(f"acquisition {key} mismatch")
    for key in ("origin", "provider", "backend"):
        if document[key] != plan["binding"][key]:
            raise ValueError(f"acquisition {key} differs from the frozen binding")
    _text(document["job_id"], "acquisition job identity")
    _sha(document["source_sha256"], "raw acquisition artifact hash")
    start, end = _time(document["started_at"]), _time(document["completed_at"])
    calibration = plan["binding"]["calibration"]
    if not _time(calibration["captured_at"]) <= start <= end < _time(calibration["valid_until"]):
        raise ValueError("acquisition is outside the frozen calibration validity window")
    shots = _integer(document["shots"], "result shots", 1, 1_000_000_000)
    if shots != plan["shots"]:
        raise ValueError("result shot count differs from the planned unconditional shots")
    counts = document["counts"]
    width = len(plan["measure_wires"])
    if not isinstance(counts, dict) or not 1 <= len(counts) <= 1 << width:
        raise ValueError("raw counts require a bounded binary histogram")
    for key, count in counts.items():
        if not isinstance(key, str) or not re.fullmatch(r"[01]{" + str(width) + r"}", key):
            raise ValueError("count keys must have the declared binary width and bit order")
        _integer(count, "raw count", 0, shots)
    if sum(counts.values()) != shots:
        raise ValueError("raw counts must sum to unconditional shots without postselection")
    return copy.deepcopy(document)


def _bridge_payload(plan, result, marginal, probability):
    lower, upper = probability.real_bounds(20)
    p = float((lower + upper) / 2)
    return dict(
        root=dict(model_fingerprint=plan["prediction"]["model"]["fingerprint"],
                  prediction_fingerprint=plan["prediction"]["fingerprint"],
                  features=plan["prediction"]["features"], feature_view=plan["prediction"]["feature_view"]),
        template=dict(plan_fingerprint=plan["fingerprint"], program_sha256=plan["program_sha256"],
                      measure_wires=plan["measure_wires"], readout_classical_bit=plan["readout_classical_bit"]),
        phase=dict(binding=plan["binding"], job_id=result["job_id"],
                   started_at=result["started_at"], completed_at=result["completed_at"]),
        observed=marginal, backend=result["backend"], shots=result["shots"],
        expected_model=dict(model_id=plan["prediction"]["fingerprint"],
                            model_type="nrqc_saved_model_Z_marginal_v1",
                            distribution={"0": 1 - p, "1": p},
                            tolerance=float(_fraction(plan["tolerance"])),
                            metadata=dict(probability_one_exact=probability.to_dict(),
                                          scope=plan["statistic"], floating_bridge_view=True)),
        metadata=dict(evidence_origin=result["origin"], source_sha256=result["source_sha256"],
                      source_authentication="not_performed", plan_fingerprint=plan["fingerprint"],
                      hardware_submissions=0, exact_classification_in="nrqc-model-observation-v1"))


def observe(plan, result):
    """Validate a raw result and compare its marginal using exact arithmetic."""
    verify_plan(plan)
    result = _result(plan, result)
    bit = plan["readout_classical_bit"]
    one = sum(count for key, count in result["counts"].items() if key[-1 - bit] == "1")
    marginal = {"0": result["shots"] - one, "1": one}
    observed = Fraction(one, result["shots"])
    expected = FIELD.from_dict(plan["prediction"]["probability_one"])
    difference = FIELD(observed) - expected
    gap = -difference if difference.real_sign() < 0 else difference
    tolerance = _fraction(plan["tolerance"])
    if (gap - tolerance).real_sign() <= 0:
        classification = "RECOGNITION"
    elif (gap - 2 * tolerance).real_sign() <= 0:
        classification = "BOUNDED_RESIDUE"
    else:
        classification = "ACTIONABLE_RESIDUE"
    return _seal(dict(schema=REPORT_SCHEMA, plan=copy.deepcopy(plan), acquisition=result,
                      marginal_counts=marginal, observed_probability_one=_rational(observed),
                      expected_probability_one=expected.to_dict(), absolute_error=gap.to_dict(),
                      absolute_error_display=gap.display(16), classification=classification,
                      exact_tolerance_decision=True,
                      bridge_payload=_bridge_payload(plan, result, marginal, expected),
                      evidence_class={"synthetic": "SYNTHETIC_OBSERVATION",
                                      "simulator": "DECLARED_SIMULATOR_OBSERVATION",
                                      "physical_backend": "DECLARED_PHYSICAL_OBSERVATION"}[result["origin"]],
                      source_authentication="not_performed", hardware_submissions=0,
                      scope="unconditional raw Z marginal; no readout mitigation or state tomography"))


def _controller_result(source_bytes):
    if not isinstance(source_bytes, bytes) or len(source_bytes) > MAX_INPUT_BYTES:
        raise ValueError("controller artifact requires at most 64 MiB of UTF-8 JSON bytes")
    controller = loads(source_bytes.decode("utf-8"))
    _object(controller, RESULT_FIELDS[:-1])
    if controller["schema"] != CONTROLLER_SCHEMA:
        raise ValueError("unsupported controller-counts schema; implicit vendor conversion is disabled")
    return dict(controller, schema=RESULT_SCHEMA, source_sha256=hashlib.sha256(source_bytes).hexdigest())


def import_observation(plan, source_bytes):
    """Compute the artifact hash from actual bytes before validating raw counts."""
    return observe(plan, _controller_result(source_bytes))


def verify_observation(document, *, source_bytes=None):
    _unseal(document, REPORT_SCHEMA)
    replay = observe(document["plan"], document["acquisition"])
    if replay != document:
        raise ValueError("observation report differs from deterministic exact replay")
    if source_bytes is not None:
        acquired = _result(document["plan"], _controller_result(source_bytes))
        if acquired != document["acquisition"]:
            raise ValueError("controller artifact bytes do not match the recorded acquisition")
    return dict(status="verified", fingerprint=document["fingerprint"],
                classification=document["classification"], evidence_class=document["evidence_class"],
                source_artifact_hash_verified=source_bytes is not None,
                source_authentication="not_performed")


def main(argv=None, *, command="experiment-plan"):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path)
    if command == "experiment-plan":
        parser.add_argument("--binding", type=Path, required=True)
        parser.add_argument("--run-id", required=True)
        parser.add_argument("--shots", type=int, required=True)
        parser.add_argument("--tolerance", required=True, help="exact numerator/denominator in [0,1]")
        parser.add_argument("--measure-wires", nargs="+", type=int)
        parser.add_argument("--qasm-out", type=Path)
    elif command in ("observe-model", "import-model-counts"):
        parser.add_argument("result", type=Path)
    else:
        parser.add_argument("--source-artifact", type=Path)
    args = parser.parse_args(argv)

    def read(path):
        with path.open("rb") as stream:
            return loads(stream.read(MAX_INPUT_BYTES + 1).decode("utf-8"))
    try:
        document = read(args.input)
        if command == "experiment-plan":
            try:
                tolerance = Fraction(args.tolerance)
            except (ValueError, ZeroDivisionError) as error:
                raise ValueError("tolerance requires an exact fraction in [0,1]") from error
            output = experiment_plan(document, read(args.binding), run_id=args.run_id, shots=args.shots,
                                     tolerance=_rational(tolerance), measure_wires=args.measure_wires)
            if args.qasm_out:
                args.qasm_out.write_text(output["measured_openqasm"], encoding="utf-8")
        elif command == "observe-model":
            output = observe(document, read(args.result))
        elif command == "import-model-counts":
            with args.result.open("rb") as stream:
                output = import_observation(document, stream.read(MAX_INPUT_BYTES + 1))
        else:
            source_bytes = None
            if args.source_artifact:
                with args.source_artifact.open("rb") as stream:
                    source_bytes = stream.read(MAX_INPUT_BYTES + 1)
            output = verify_observation(document, source_bytes=source_bytes)
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
