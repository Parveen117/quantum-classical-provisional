"""Temperature-sweep evidence contract for the heated photonic core (v0.17).

Exact statements about what a chip temperature change can and cannot do to
the ideal exchange unit, an unrun sweep protocol, and a fail-closed verdict
that classifies the temperature claims a recorded sweep would support.

Nothing here is a heat solve, a material fit, a detector datasheet or a lab
result. Every material number is an explicit caller input; the module only
converts it exactly and refuses to grade claims without recorded evidence.
"""
from fractions import Fraction

from native_relational_qc.cyclotomic64 import Cyclotomic64 as F, ZERO, ONE, ZETA
from .model import ResourceLimit, integer, rational
from .photonic_response import PHASE_ORDER, optical_response, exact_rank, unit_jet
from .photonic_io import calibration_template, fingerprint

COMMON_MODE = (1, 1, 0, 0, 1)
FAMILIES = ("basis", "local", "reference")
ROOM_BAND_C = (Fraction(15), Fraction(35))
CRYOGEN_FREE_FLOOR_C = Fraction(-100)
MAX_SWEEP_POINTS = 64

# Candidate detector routes. The temperature classes are what the verdict
# below would assign to a recorded log in those ranges; the ranges are declared
# engineering context from vendor literature, not measurements of any unit.
DETECTOR_OPTIONS = (
    dict(option="snspd_1550", signal_band_nm=[1500, 1600], detector_temperature_c_range=[-272, -269],
         thermal_class_if_recorded="CRYOGENIC", design_change="none; v0.9 selection"),
    dict(option="ingaas_spad_1550", signal_band_nm=[1500, 1600], detector_temperature_c_range=[-70, -30],
         thermal_class_if_recorded="CRYOGEN_FREE", design_change="detector only; same SiN core and SPDC source"),
    dict(option="si_spad_810", signal_band_nm=[700, 900], detector_temperature_c_range=[15, 35],
         thermal_class_if_recorded="ROOM_TEMPERATURE",
         design_change="signal wavelength near 810 nm: new SPDC crystal/pump, re-targeted SiN cross-section and MMI, new calibration"),
)


def _fraction(value, label, bits=256):
    if type(value) is str:
        try:
            value = Fraction(value)
        except (ValueError, ZeroDivisionError):
            raise ValueError(f"{label} must be a finite decimal/rational string") from None
    return rational(value, label, bits)


def _steps(values, size):
    if type(values) is not tuple or len(values) != size:
        raise ValueError(f"a tuple of {size} phase steps is required")
    for value in values:
        integer(value, "phase step")
        if not -64 <= value <= 64:
            raise ValueError("phase step outside [-64,64]")
    return values


def _wrap(values):
    return tuple(((v + 64) % 128) - 64 for v in values)


def _point(theta_steps):
    integer(theta_steps, "theta steps")
    if not 0 <= theta_steps <= 64:
        raise ValueError("theta steps must be in [0,64]")
    return ((32 - theta_steps) % 64, 0, 48, 48)


def shifted_response(theta_steps, drift_steps, *, measurements="reference"):
    """Exact probabilities after adding drift to (lower,upper,in,out,reference)."""
    drift = _steps(drift_steps, 5)
    l, u, b, a = _point(theta_steps)
    l, u, b, a, r = _wrap((l + drift[0], u + drift[1], b + drift[2], a + drift[3], drift[4]))
    return optical_response((l, u, b, a), measurements=measurements, reference_steps=r)


def deviation(theta_steps, drift_steps, *, measurements="reference"):
    """Exact squared deviation and a rational enclosure of the largest shift.

    Compares drifted and ideal probabilities label by label. The squared sum
    is exact in the field; max |delta p| is enclosed by rational bounds since
    the field has no exact absolute value without a sign decision.
    """
    ideal = optical_response(_point(theta_steps), measurements=measurements)
    moved = shifted_response(theta_steps, drift_steps, measurements=measurements)
    assert ideal["labels"] == moved["labels"]
    total = ZERO
    low = high = Fraction(0)
    for p, q in zip(ideal["probabilities"], moved["probabilities"]):
        d = q - p
        total = total + d * d
        lo, hi = d.real_bounds(12)
        abs_lower = lo if lo > 0 else (-hi if hi < 0 else Fraction(0))
        low, high = max(low, abs_lower), max(high, abs(lo), abs(hi))
    return dict(labels=ideal["labels"], squared_deviation=total,
                squared_deviation_is_zero=total == ZERO,
                max_abs_shift_lower_bound=low, max_abs_shift_upper_bound=high,
                measurements=measurements, drift_steps=tuple(drift_steps))


def common_mode_invariance(theta_steps, shift_steps):
    """Theorem T1 witness: a common shift of lower arm, upper arm and reference
    changes no probability in any family, exactly, at the sampled point.

    Uniform heating of symmetric, equal-length arms and reference is this
    direction; it multiplies the unit and the reference by one global phase.
    The theorem holds for every real shift; the engine samples pi/32 steps.
    """
    integer(shift_steps, "shift steps")
    if not -64 <= shift_steps <= 64:
        raise ValueError("shift steps outside [-64,64]")
    drift = tuple(shift_steps * c for c in COMMON_MODE)
    result = {}
    for family in FAMILIES:
        ideal = optical_response(_point(theta_steps), measurements=family)["probabilities"]
        moved = shifted_response(theta_steps, drift, measurements=family)["probabilities"]
        result[family] = len(ideal) == len(moved) and all(p == q for p, q in zip(ideal, moved))
    return result


def common_mode_global_phase(theta_steps, shift_steps):
    """Theorem T1 at the matrix level: U(l+s, u+s, b, a) = zeta^s U(l, u, b, a).

    One exact 2x2 identity per angle and shift. Together with the reference
    amplitude picking up the same factor, it implies the probability-level
    invariance checked by `common_mode_invariance` for every family.
    """
    integer(shift_steps, "shift steps")
    if not -64 <= shift_steps <= 64:
        raise ValueError("shift steps outside [-64,64]")
    l, u, b, a = _point(theta_steps)
    base, _ = unit_jet((l, u, b, a))
    moved, _ = unit_jet(_wrap((l + shift_steps, u + shift_steps, b, a)))
    factor = ZETA ** shift_steps
    return all(moved[r][c] == factor * base[r][c] for r in range(2) for c in range(2))


def drift_dichotomy(theta_steps, drift_steps):
    """Theorem T2: at the sampled point every phase-only drift is either in the
    exact common-mode kernel or first-order visible to the reference family.

    Returns the kernel/complement split, the first-order visibility of the
    drift in each family, and the exact correction (minus the drift) under
    which the unit returns to its ideal transfer. Visibility is a statement
    about the ideal Jacobian, not about noise or finite counting statistics.
    """
    drift = _steps(drift_steps, 5)
    out = dict(drift_steps=drift, phase_order=PHASE_ORDER)
    # Decompose along the common-mode direction with the natural projection
    # (reference coordinate carries the common part; trims never do).
    common = drift[4]
    complement = (drift[0] - common, drift[1] - common, drift[2], drift[3], 0)
    out["common_mode_steps"] = common
    out["complement_steps"] = complement
    out["in_kernel"] = complement == (0, 0, 0, 0, 0)
    visible = {}
    for family in FAMILIES:
        jac = optical_response(_point(theta_steps), measurements=family)["jacobian"]
        image = [sum((row[i] * F.coerce(drift[i]) for i in range(5)), ZERO) for row in jac]
        visible[family] = any(v != ZERO for v in image)
    out["first_order_visible"] = visible
    out["exact_correction_steps"] = tuple(-v for v in complement)
    corrected = tuple(d + c for d, c in zip(drift, out["exact_correction_steps"]))
    out["corrected_equals_common_mode"] = corrected == tuple(common * c for c in COMMON_MODE)
    out["corrected_response_identical"] = all(
        common_mode_invariance(theta_steps, common)[f] for f in FAMILIES)
    out["reference_rank"] = exact_rank(optical_response(_point(theta_steps))["jacobian"])
    return out


def thermo_optic_drift(*, dn_dT_per_K, path_length_difference_m, delta_T_K, wavelength_m):
    """Exact differential phase from a declared thermo-optic coefficient.

    phi/pi = 2 * dL * (dn/dT) * dT / lambda. All four inputs are declared by
    the caller; none is a measured property of the fabricated core. The step
    count is phi in pi/32 units with its rounding residual kept.
    """
    dn = _fraction(dn_dT_per_K, "dn/dT")
    dl = _fraction(path_length_difference_m, "path length difference")
    dt = _fraction(delta_T_K, "temperature change")
    lam = _fraction(wavelength_m, "wavelength")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    phi_over_pi = 2 * dl * dn * dt / lam
    steps = phi_over_pi * 32
    nearest = round(steps)
    return dict(phi_over_pi=phi_over_pi, steps_pi_over_32=steps, nearest_step=int(nearest),
                residual_steps=steps - nearest, inputs_are_declared=True)


def drift_table(*, dn_dT_per_K, wavelength_m, path_length_differences_m, delta_Ts_K):
    rows = []
    for dl in path_length_differences_m:
        for dt in delta_Ts_K:
            d = thermo_optic_drift(dn_dT_per_K=dn_dT_per_K, path_length_difference_m=dl,
                                   delta_T_K=dt, wavelength_m=wavelength_m)
            rows.append(dict(path_length_difference_m=str(Fraction(dl)), delta_T_K=str(Fraction(dt)),
                             phi_over_pi=str(d["phi_over_pi"]), steps_pi_over_32=str(d["steps_pi_over_32"]),
                             nearest_step=d["nearest_step"]))
    if len(rows) > 4096:
        raise ResourceLimit("drift table too large")
    return rows


def _cos(steps):
    return (ZETA ** steps + ZETA ** (-steps)) / 2


def hom_coincidence(theta_steps):
    """Exact two-photon coincidence at one exchange unit, both inputs occupied.

    Indistinguishable photons: |perm U|^2 = cos^2(theta). Fully distinguishable
    photons: |U00 U11|^2 + |U01 U10|^2. The ideal unit at quadrature gives 0
    against 1/2. This is the source/indistinguishability check of the sweep;
    the v0.9 computation itself uses one photon and no two-photon gate.
    """
    u, _ = unit_jet(_point(theta_steps))
    # The v0.12 word equals H diag(1, e^{-i theta}) H up to the fixed trims,
    # which cancel in both coincidence probabilities (they are port phases).
    perm = u[0][0] * u[1][1] + u[0][1] * u[1][0]
    indistinguishable = perm.norm2()
    distinguishable = (u[0][0] * u[1][1]).norm2() + (u[0][1] * u[1][0]).norm2()
    c = _cos(theta_steps)
    return dict(theta_pi_over_32=theta_steps, indistinguishable=indistinguishable,
                distinguishable=distinguishable, closed_form_matches=indistinguishable == c * c,
                visibility_definition="V = 1 - P_cc(indistinguishable)/P_cc(distinguishable) at the quadrature setting")


def sweep_protocol(temperatures_c, *, wavelength_nm, detector_option, reference_temperature_c=None,
                   miscalibration_steps=8):
    """Unrun temperature-sweep plan bound to the existing physical calibration scope.

    Each temperature point carries a fresh 31-channel calibration, the full
    106-setting protocol under that calibration, the same protocol under the
    reference-temperature calibration (uncalibrated control), a deliberate
    miscalibration control, a two-photon HOM point and a subsystem temperature
    log. The plan contains no counts, voltages or verdicts.
    """
    if type(temperatures_c) not in (list, tuple) or not 1 <= len(temperatures_c) <= MAX_SWEEP_POINTS:
        raise ValueError(f"1..{MAX_SWEEP_POINTS} sweep temperatures required")
    temps = [_fraction(t, "sweep temperature") for t in temperatures_c]
    if len(set(temps)) != len(temps):
        raise ValueError("sweep temperatures must be distinct")
    if any(t <= Fraction(-27315, 100) for t in temps):
        raise ValueError("temperature below absolute zero")
    option = next((o for o in DETECTOR_OPTIONS if o["option"] == detector_option), None)
    if option is None:
        raise ValueError("unknown detector option")
    lam = _fraction(wavelength_nm, "wavelength")
    lo, hi = option["signal_band_nm"]
    if not lo <= lam <= hi:
        raise ValueError("wavelength outside the detector option's signal band")
    ref = temps[0] if reference_temperature_c is None else _fraction(reference_temperature_c, "reference temperature")
    if ref not in temps:
        raise ValueError("reference temperature must be one of the sweep points")
    integer(miscalibration_steps, "miscalibration steps")
    if not 1 <= miscalibration_steps <= 32:
        raise ValueError("miscalibration steps must be in [1,32]")
    template = calibration_template(physical_layout=True)
    points = []
    for t in sorted(temps):
        points.append(dict(
            chip_temperature_c=str(t),
            stages=[
                dict(stage="stabilize", record=["chip stage temperature trace", "source crystal temperature",
                                                "detector temperature", "ambient temperature", "settling time"]),
                dict(stage="bright_light_calibration", channels=len(template["actuator_map"]),
                     context=dict(wavelength_nm=str(lam), chip_temperature_c=str(t)),
                     output="RECORDED calibration profile for this temperature; evidence_class LAB_RECORDED"),
                dict(stage="protocol_calibrated", settings=106, calibration="this temperature",
                     compare_to="exact ideal probabilities from the calculator", statistic="total-variation bound with declared confidence"),
                dict(stage="protocol_uncalibrated_control", settings=106,
                     calibration=f"profile recorded at {ref} C", purpose="measures raw drift the correction must absorb"),
                dict(stage="miscalibration_control", settings=106,
                     perturbation=f"core_0 lower arm +{miscalibration_steps} steps of pi/32 from the calibrated value",
                     purpose="establishes that the statistic has power to see a known phase error"),
                dict(stage="two_photon_hom", unit="exchange_0", theta_pi_over_32=16,
                     ideal=dict(indistinguishable="0", distinguishable="1/2"),
                     record=["coincidences versus relative delay", "heralded g2(0) of the source at this temperature"]),
                dict(stage="temperature_log", subsystems=["chip", "source", "detector", "electronics"]),
            ]))
    return dict(schema="native-photonic-temperature-sweep-v1", author="Monty", status="NOT_RUN",
                evidence_class=None, detector_option=option, wavelength_nm=str(lam),
                reference_temperature_c=str(ref), points=points, point_count=len(points),
                io_sha256=template["io_sha256"], layout_spec_sha256=template["layout_spec_sha256"],
                layout_gds_sha256=template["layout_gds_sha256"],
                exact_statements=["T1 common-mode heating is in the exact kernel of all 24 observables",
                                  "T2 every phase-only drift is kernel or first-order visible to the reference family at interior angles",
                                  "T3 the verdict never promotes a synthetic or partial log to a temperature claim"],
                not_modelled=["splitting-ratio and loss changes with temperature", "source spectrum and detector efficiency versus temperature",
                              "thermal gradients inside one unit beyond the five phase coordinates", "dynamics, hysteresis and settling"],
                plan_sha256=None)


def _band(value, label):
    if type(value) not in (list, tuple) or len(value) != 2:
        raise ValueError(f"{label} needs [min,max]")
    lo, hi = (_fraction(v, label) for v in value)
    if lo > hi:
        raise ValueError(f"{label} min exceeds max")
    return lo, hi


def temperature_claim_verdict(record, *, room_band_c=ROOM_BAND_C, minimum_span_K=20, minimum_points=3):
    """Fail-closed classification of a recorded sweep into allowed claims.

    thermal_class: ROOM_TEMPERATURE needs chip, source and detector never cooled
    below the declared room band floor (heating above it is a sweep, not a
    violation); CRYOGEN_FREE needs all above the cryogen-free floor; otherwise
    CRYOGENIC. logic_class: TEMPERATURE_INDEPENDENT_AFTER_CALIBRATION
    needs enough points and span, every calibrated TVD upper bound within the
    declared tolerance, and the miscalibration control's TVD lower bound above
    tolerance (power). TEMPERATURE_INSENSITIVE_WITHOUT_CALIBRATION additionally
    needs every uncalibrated control within tolerance. Anything missing or
    synthetic yields UNDETERMINED with reasons; no claim is allowed then.
    """
    reasons = []
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    room_lo, room_hi = _band(room_band_c, "room band")
    span_min = _fraction(minimum_span_K, "minimum span")
    integer(minimum_points, "minimum points")
    evidence = record.get("evidence_class")
    recorded = evidence == "LAB_RECORDED"
    if not recorded:
        reasons.append(f"evidence_class is {evidence!r}, not LAB_RECORDED")
    temps = record.get("subsystem_temperatures_c")
    thermal = "UNDETERMINED"
    if type(temps) is dict and {"chip", "source", "detector"} <= set(temps):
        try:
            bands = {k: _band(temps[k], f"{k} temperature") for k in ("chip", "source", "detector")}
        except ValueError as exc:
            reasons.append(str(exc))
            bands = None
        if bands:
            # Heating a subsystem above the room band is allowed (a sweep does
            # exactly that); cooling any subsystem below it is what the room
            # temperature claim excludes.
            if all(lo >= room_lo for lo, _ in bands.values()):
                thermal = "ROOM_TEMPERATURE"
            elif all(lo >= CRYOGEN_FREE_FLOOR_C for lo, _ in bands.values()):
                thermal = "CRYOGEN_FREE"
            else:
                thermal = "CRYOGENIC"
            for k, (lo, hi) in bands.items():
                if lo < room_lo:
                    reasons.append(f"{k} was cooled to {lo} C, below the room band floor {room_lo} C")
                if hi > room_hi:
                    reasons.append(f"{k} was heated to {hi} C, above the room band ceiling {room_hi} C (allowed, recorded)")
    else:
        reasons.append("subsystem_temperatures_c must log chip, source and detector")
    logic = "UNDETERMINED"
    record_span = None
    sweep = record.get("sweep")
    tolerance = record.get("tvd_tolerance")
    try:
        tol = _fraction(tolerance, "tvd tolerance") if tolerance is not None else None
    except (ValueError, TypeError):
        tol = None
    if tol is None or tol <= 0 or tol >= 1:
        reasons.append("tvd_tolerance must be a declared rational in (0,1)")
    elif type(sweep) is not list or len(sweep) < minimum_points:
        reasons.append(f"sweep needs at least {minimum_points} recorded temperature points")
    else:
        try:
            rows = []
            for row in sweep:
                if type(row) is not dict:
                    raise ValueError("sweep rows must be dicts")
                rows.append(dict(
                    t=_fraction(row["chip_temperature_c"], "chip temperature"),
                    cal_hi=_fraction(row["calibrated_tvd_upper_bound"], "calibrated tvd"),
                    uncal_hi=_fraction(row["uncalibrated_tvd_upper_bound"], "uncalibrated tvd"),
                    mis_lo=_fraction(row["miscalibration_tvd_lower_bound"], "miscalibration tvd")))
        except (KeyError, ValueError, TypeError) as exc:
            rows = None
            reasons.append(f"incomplete sweep row: {exc}")
        if rows:
            span = max(r["t"] for r in rows) - min(r["t"] for r in rows)
            calibrated_ok = all(r["cal_hi"] <= tol for r in rows)
            uncalibrated_ok = all(r["uncal_hi"] <= tol for r in rows)
            power = all(r["mis_lo"] > tol for r in rows)
            if span < span_min:
                reasons.append(f"sweep span {span} K is below the declared minimum {span_min} K")
            elif not power:
                logic = "TEST_WITHOUT_POWER"
                reasons.append("a miscalibration control did not exceed tolerance; the statistic cannot see a known phase error")
            elif not calibrated_ok:
                logic = "TEMPERATURE_DEPENDENT"
                reasons.append("a calibrated point exceeded the TVD tolerance")
            elif uncalibrated_ok:
                logic = "TEMPERATURE_INSENSITIVE_WITHOUT_CALIBRATION"
            else:
                logic = "TEMPERATURE_INDEPENDENT_AFTER_CALIBRATION"
            record_span = span
    allowed = []
    if recorded and thermal == "ROOM_TEMPERATURE":
        allowed.append("complete apparatus operated inside the declared room band during the recorded sweep")
    if recorded and thermal == "CRYOGEN_FREE":
        allowed.append("cryogen-free operation; not room temperature")
    if recorded and logic == "TEMPERATURE_INDEPENDENT_AFTER_CALIBRATION":
        allowed.append(f"logical transfer within TVD {tol} of the exact prediction at every point after per-temperature calibration, over a {record_span} K span")
    if recorded and logic == "TEMPERATURE_INSENSITIVE_WITHOUT_CALIBRATION":
        allowed.append(f"logical transfer within TVD {tol} of the exact prediction at every point with one fixed calibration, over a {record_span} K span")
    never = ["a quantum computer at room temperature (a single-photon exchange core is not a computer)",
             "temperature independence of the physics (only of the calibrated logical transfer, within tolerance, over the recorded span)",
             "any temperature claim from a synthetic, simulated or partial log"]
    return dict(thermal_class=thermal, logic_class=logic, evidence_recorded=recorded,
                claims_allowed=allowed, claims_never_allowed=never, reasons=reasons,
                room_band_c=[str(room_lo), str(room_hi)], cryogen_free_floor_c=str(CRYOGEN_FREE_FLOOR_C))
