"""Photonic target/uncertainty adapter to the existing observer framework.

The exact field decides target visibility. An optional, separately supplied
pinned device engine evaluates a numerical Euclidean decoder gain. No private
engine is vendored, no measured coefficients are inferred and no drive is sent.
"""
from fractions import Fraction
import hashlib
import math
from pathlib import Path
import re
import sys
from types import ModuleType
import uuid

from .photonic_io import fingerprint
from .photonic_response import PHASE_ORDER, _real_matrix, exact_rank, optical_response, response_plan

TARGETS = {
    "exchange_angle": ((-1, 1, 0, 0, 0),),  # theta = pi - lower + upper
    "relative_phases": ((1, 0, 0, 0, -1), (0, 1, 0, 0, -1),
                        (0, 0, 1, 0, 0), (0, 0, 0, 1, 0)),
    "absolute_reference": ((0, 0, 0, 0, 1),),
}
DEVICE_SOURCE = {
    "repository": "Parveen117/EMK-Tensor-Cell-Devices",
    "commit": "a116985f667e258696334be8a6b07f85879eb1c4",
    "git_blobs": {
        "seam_antenna.py": "d91f704ae7a3ca9c66183eb4e81a4cd2e37e2062",
        "robust_faithfulness.py": "d47765b99f4c5d89e0368c53435096218264b94e",
    },
}
BOUND_NAMES = ("sensor_noise_bound", "calibration_drift_operator_bound",
               "state_norm_bound", "target_error_budget", "nonlinear_remainder_bound")


def _scales(values, size, name):
    if not isinstance(values, (tuple, list)) or len(values) != size:
        raise ValueError(f"{name} requires {size} explicit positive rational scales")
    if any(type(v) not in (int, Fraction) or v <= 0 for v in values):
        raise ValueError(f"{name} requires positive exact int/Fraction entries")
    if any(max(Fraction(v).numerator.bit_length(), Fraction(v).denominator.bit_length()) > 4096
           for v in values):
        raise ValueError("scale coefficient bit limit")
    return tuple(Fraction(v) for v in values)


def observer_packet(phase_steps, *, target, measurements, state_scales,
                    reading_scales, target_scales, reference_steps=0,
                    unit_index=0, nuisance_response=None):
    """Build a local ideal target contract in explicit normalized coordinates.

    x_native=Dx z, y_native=Dy ybar, t_native=Dt tbar. Scales have native
    units per normalized coordinate. Extra named nuisance columns are admitted
    as unknown state coordinates and have zero target columns. No nuisance
    prior is silently counted as a measurement. Rational export is lossless;
    irrational field entries remain exact but are not rounded for the engine.
    """
    if target not in TARGETS:
        raise ValueError("unknown photonic target")
    if type(unit_index) is not int or not 0 <= unit_index < 6:
        raise ValueError("unit_index must be an integer in 0..5")
    response = optical_response(phase_steps, measurements=measurements, reference_steps=reference_steps)
    sensor = [list(row) for row in response["jacobian"]]
    pi = [list(row) for row in TARGETS[target]]
    nuisance = {} if nuisance_response is None else nuisance_response
    if not isinstance(nuisance, dict) or len(nuisance) > 27:
        raise ValueError("at most 27 named nuisance columns are supported")
    for name, column in nuisance.items():
        if (not isinstance(name, str) or not name or len(name) > 64 or name in PHASE_ORDER
                or not isinstance(column, (tuple, list)) or len(column) != len(sensor)):
            raise ValueError("invalid nuisance name or column length")
        for row, value in zip(sensor, column):
            row.append(value)
        for row in pi:
            row.append(0)
    sensor, pi = _real_matrix(sensor), _real_matrix(pi)
    dx = _scales(state_scales, len(sensor[0]), "state_scales")
    dy = _scales(reading_scales, len(sensor), "reading_scales")
    dt = _scales(target_scales, len(pi), "target_scales")
    sensor = _real_matrix([[v*dx[j]/dy[i] for j, v in enumerate(row)] for i, row in enumerate(sensor)])
    pi = _real_matrix([[v*dx[j]/dt[i] for j, v in enumerate(row)] for i, row in enumerate(pi)])
    rank = exact_rank(sensor)
    blind = exact_rank(sensor+pi)-rank  # rank(Pi restricted to ker S)
    rational = all(not any(v.coefficients[1:]) for row in sensor+pi for v in row)
    plan = response_plan()
    result = dict(
        schema="native-photonic-target-packet-v1", author="Monty",
        scope="LOCAL_PHASE_ONLY_IDEAL_COMPONENT", evidence_class="IDEAL_COMPONENT_ALGEBRA",
        unit=f"exchange_{unit_index}", phase_steps=list(phase_steps), reference_steps=reference_steps,
        target_name=target, measurement_family=measurements, measurement_labels=list(response["labels"]),
        state_order=[*PHASE_ORDER, *nuisance], native_phase_unit="radian",
        scales=dict(state=[str(v) for v in dx], reading=[str(v) for v in dy], target=[str(v) for v in dt]),
        norm_model="NORMALIZED_EUCLIDEAN_2_NORM",
        sensor_rank=rank, target_rank=exact_rank(pi), target_blind_dimension=blind,
        exact_target_faithful=blind == 0,
        export_status="EXACT_RATIONAL" if rational else "EXACT_FIELD_ONLY",
        sensor=[[str(v.coefficients[0]) for v in row] for row in sensor] if rational else None,
        target=[[str(v.coefficients[0]) for v in row] for row in pi] if rational else None,
        exact_model_sha256=fingerprint([[v.to_dict() for v in row] for row in sensor+pi]),
        layout_binding={k:plan[k] for k in ("io_sha256", "layout_spec_sha256", "layout_gds_sha256")},
        device_id=None, hardware_submitted=False, calibration_accepted=False,
    )
    result["packet_sha256"] = fingerprint(result)
    return result


def _read_packet(packet):
    if not isinstance(packet, dict) or packet.get("schema") != "native-photonic-target-packet-v1":
        raise ValueError("photonic target packet required")
    unsigned = {k:v for k, v in packet.items() if k != "packet_sha256"}
    if fingerprint(unsigned) != packet.get("packet_sha256"):
        raise ValueError("target packet hash mismatch")
    if packet.get("scope") != "LOCAL_PHASE_ONLY_IDEAL_COMPONENT" or packet.get("calibration_accepted") is not False:
        raise ValueError("unsupported target packet scope")
    if packet.get("export_status") != "EXACT_RATIONAL":
        return None, None
    # Recompute the exact decision before trusting a serialized packet.
    def rational_rows(rows):
        if not isinstance(rows, list) or not 1 <= len(rows) <= 128:
            raise ValueError("bounded rational rows required")
        for row in rows:
            if not isinstance(row, list) or not 1 <= len(row) <= 32:
                raise ValueError("bounded rational columns required")
            if any(not isinstance(v, str) or len(v) > 2500 or
                   re.fullmatch(r"-?[0-9]+(?:/[1-9][0-9]*)?", v) is None for v in row):
                raise ValueError("bounded rational strings required")
        parsed = [[Fraction(v) for v in row] for row in rows]
        _real_matrix(parsed)
        if [[str(v) for v in row] for row in parsed] != rows:
            raise ValueError("canonical rational strings required")
        return parsed
    sensor, target = rational_rows(packet["sensor"]), rational_rows(packet["target"])
    if len(sensor[0]) != len(target[0]):
        raise ValueError("sensor/target width mismatch")
    field_rows = _real_matrix(sensor+target)
    if fingerprint([[v.to_dict() for v in row] for row in field_rows]) != packet["exact_model_sha256"]:
        raise ValueError("rational export differs from exact model")
    rank = exact_rank(sensor)
    blind = exact_rank(sensor+target)-rank
    if (rank != packet["sensor_rank"] or exact_rank(target) != packet["target_rank"]
            or blind != packet["target_blind_dimension"]
            or (blind == 0) != packet["exact_target_faithful"]):
        raise ValueError("target packet exact decision mismatch")
    return sensor, target


def _device_engine(source_dir):
    """Load only explicitly supplied, byte-pinned files in an isolated package.

    Both files are verified before either is executed. No checkout, network
    lookup, sys.path insertion or private source copying is performed.
    """
    sources = {}
    for name, expected in DEVICE_SOURCE["git_blobs"].items():
        data = (Path(source_dir)/name).read_bytes()
        actual = hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
        if actual != expected:
            raise ValueError(f"device source pin mismatch: {name}")
        sources[name] = data
    package_name = "_photonic_device_"+uuid.uuid4().hex
    package = ModuleType(package_name); package.__path__ = []
    sys.modules[package_name] = package
    try:
        loaded = {}
        for name, data in sources.items():
            module_name = package_name+"."+name[:-3]
            module = ModuleType(module_name)
            module.__package__ = package_name
            module.__file__ = str(Path(source_dir)/name)
            sys.modules[module_name] = module
            exec(compile(data, module.__file__, "exec"), module.__dict__)
            loaded[name] = module
        return loaded["robust_faithfulness.py"].analyze_robustness
    finally:
        for name in list(sys.modules):
            if name == package_name or name.startswith(package_name+"."):
                del sys.modules[name]


def _bound(value, name):
    if value is None:
        return None
    if type(value) not in (int, float, Fraction):
        raise ValueError(f"{name} must be a finite nonnegative number")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} exceeds floating point range") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return value


def assess_uncertainty(packet, *, bounds, device_source_dir=None, rcond=1e-12):
    """Numerical, conditional model-budget gate using the existing device code.

    All five bounds must be explicit, including zero drift/remainder. They
    apply in the packet's normalized coordinates. The nonlinear remainder is
    a *measurement-space* norm bound and is added to sensor noise. Values are
    caller assumptions, not certified measurements or statistical confidence.
    This function never accepts a physical calibration or authorizes a drive.
    """
    sensor, target = _read_packet(packet)
    if not isinstance(bounds, dict) or set(bounds)-set(BOUND_NAMES):
        raise ValueError("unknown uncertainty bound")
    declared = {name:_bound(bounds.get(name), name) for name in BOUND_NAMES}
    if type(rcond) not in (int, float) or not math.isfinite(rcond) or not 0 < rcond < 0.01:
        raise ValueError("finite SVD rcond in (0,0.01) required")
    result = dict(schema="native-photonic-uncertainty-v1", packet_sha256=packet["packet_sha256"],
                  norm_model=packet["norm_model"], bounds=declared, bound_evidence="CALLER_ASSUMPTIONS",
                  status=None, model_budget_met=None, numeric_target_error_estimate=None,
                  numerical_gain_is_certified_upper_bound=False, calibration_accepted=False,
                  hardware_submitted=False, engine_source=None, engine_report=None, numerical_checks=None)
    if sensor is None:
        result["status"] = "UNSUPPORTED_IRRATIONAL_ENGINE_EXPORT"
    elif not packet["exact_target_faithful"]:
        result.update(status="BLINDNESS_DETECTED", model_budget_met=False)
    elif any(v is None for v in declared.values()):
        result["status"] = "INCOMPLETE_UNCERTAINTY_BOUNDS"
    elif device_source_dir is None:
        result["status"] = "DEVICE_ENGINE_NOT_SUPPLIED"
    else:
        eta = declared["sensor_noise_bound"]+declared["nonlinear_remainder_bound"]
        if not math.isfinite(eta):
            raise ValueError("combined sensor/remainder bound overflow")
        engine = _device_engine(device_source_dir)
        report = engine(sensor, target, sensor_noise_bound=eta,
                        calibration_drift_operator_bound=declared["calibration_drift_operator_bound"],
                        state_norm_bound=declared["state_norm_bound"],
                        target_error_budget=declared["target_error_budget"], rcond=rcond)
        result["engine_source"] = {**DEVICE_SOURCE, "git_blobs":dict(DEVICE_SOURCE["git_blobs"])}
        result["engine_report"] = report
        error = report.get("combined_target_error_upper")
        gain = report.get("decoder_gain")
        residual = report.get("decoder_reconstruction_residual")
        # A unit absolute tolerance would hide errors in a tiny scaled target.
        # max|Pi_ij| <= ||Pi||_2 gives a conservative target-relative check.
        target_scale = max(abs(float(v)) for row in target for v in row)
        checks = dict(
            exact_faithfulness_agrees=report.get("exact_target_faithful") is True,
            upstream_decoder_consistent=report.get("numerical_decoder_consistent") is True,
            sensor_rank_agrees=report.get("numerical_sensor_rank") == packet["sensor_rank"],
            zero_target_agrees=report.get("target_is_zero") == (packet["target_rank"] == 0),
            finite_nonnegative_gain=type(gain) is float and math.isfinite(gain) and gain >= 0,
            finite_nonnegative_error=type(error) is float and math.isfinite(error) and error >= 0,
            target_relative_residual_consistent=(type(residual) is float and math.isfinite(residual)
                                                 and 0 <= residual <= 100*rcond*target_scale),
        )
        result["numerical_checks"] = checks
        good = all(checks.values())
        if not good:
            # Never allow an upstream success label to override these guards.
            result["status"] = "NUMERICAL_DECODER_UNRESOLVED"
            result["model_budget_met"] = False
            # Avoid non-finite JSON in a failed numerical report.
            result["engine_report"] = None
        else:
            result["numeric_target_error_estimate"] = error
            result["model_budget_met"] = error <= declared["target_error_budget"]
            result["status"] = ("MODEL_BUDGET_MET_NUMERICALLY" if result["model_budget_met"]
                                else "MODEL_ERROR_BUDGET_EXCEEDED")
    result["report_sha256"] = fingerprint(result)
    return result
