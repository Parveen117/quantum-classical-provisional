"""Re-target of the heated SiN core from 1550 nm to 810 nm (v0.19).

Exact scaling of the pinned 1550 nm geometry to the 810 nm signal of the
room-temperature route, the heater and drift re-scaling, the list of what
cannot be scaled (film thickness, vendor cells, material dispersion), and a
fail-closed design-readiness grader. All numbers are declared inputs or exact
rational consequences of them; no mode solver, DRC run or measurement exists.
"""
from fractions import Fraction
import json
from pathlib import Path

from .model import rational
from .temperature_sweep import thermo_optic_drift, DETECTOR_OPTIONS

SOURCE_WAVELENGTH_NM = 1550
TARGET_WAVELENGTH_NM = 810
RATIO = Fraction(TARGET_WAVELENGTH_NM, SOURCE_WAVELENGTH_NM)  # 81/155
FIXED_BY_PLATFORM = ("nitride_thickness_nm", "buried_oxide_thickness_nm")
# Local geometry thresholds already used by the v0.11 layout checks (nm).
LOCAL_MIN_NM = dict(strip_width=350, gap=250, filament_width=600, pad_width=2000)
READINESS = ("SCALED_NOMINAL", "SOLVER_VERIFIED", "DRC_PASSED", "FABRICATED", "MEASURED")


def _binding():
    return json.loads((Path(__file__).with_name("photonic_process_binding.json")).read_text())


def _frac(v, label):
    return rational(Fraction(str(v)) if not isinstance(v, (int, Fraction)) else v, label, 256)


def scale_invariance_statement():
    """Statement R1: with wavelength-independent indices, Maxwell's equations are
    invariant under x -> s x, lambda -> s lambda, so the scaled geometry has the
    same modes, splitting ratios and bend behaviour. Two things break it here:
    the 300 nm film thickness is fixed by the platform, and SiN/SiO2 indices
    disperse between 1550 and 810 nm. The scaled numbers are therefore the
    starting point for a mode solver, never a design in themselves."""
    return dict(ratio=RATIO, exact_under=["wavelength-independent refractive indices", "every dimension scaled, thickness included"],
                broken_by=["film thickness fixed at 300 nm", "material dispersion of SiN and SiO2",
                           "metal heater geometry set by electrical, not optical, rules"],
                status="SCALED_NOMINAL")


def scaled_geometry(pinned_um=None, *, ratio=RATIO):
    """Scale every pinned optical dimension by ratio; keep platform-fixed ones."""
    ratio = rational(ratio, "ratio", 64)
    pinned = dict(_binding()["pinned_pdk_defaults_um"]) if pinned_um is None else dict(pinned_um)
    rows = []
    for name, value in pinned.items():
        v = _frac(value, name)
        scaled = v * ratio
        nm = scaled * 1000
        check = None
        if name == "strip_width":
            check = nm >= LOCAL_MIN_NM["strip_width"]
        elif name.endswith("gap"):
            check = nm >= LOCAL_MIN_NM["gap"]
        rows.append(dict(dimension=name, source_um=v, scaled_um=scaled, scaled_nm=nm,
                         passes_local_minimum=check, status="scaled nominal; mode solver required"))
    stack = _binding()["provider_nominal_stack"]
    for name in FIXED_BY_PLATFORM:
        if name in stack:
            rows.append(dict(dimension=name, source_um=Fraction(stack[name], 1000), scaled_um=Fraction(stack[name], 1000),
                             scaled_nm=Fraction(stack[name]), passes_local_minimum=None,
                             status="fixed by platform; breaks exact scaling"))
    return rows


def thickness_ratio():
    """t/lambda rises from 300/1550 to 300/810: relatively thicker film at 810 nm,
    so vertical higher-order modes and the single-mode width need a solver."""
    return dict(source=Fraction(300, SOURCE_WAVELENGTH_NM), target=Fraction(300, TARGET_WAVELENGTH_NM),
                increase=Fraction(300, TARGET_WAVELENGTH_NM) / Fraction(300, SOURCE_WAVELENGTH_NM))


def heater_retarget(*, phase_per_power_rad_per_w_1550=None, heater_length_um_1550=None):
    """Thermo-optic phase per unit heated length scales as 1/lambda at equal dn/dT.

    So the same heater gives 155/81 more phase per watt at 810 nm; a pi shift
    needs 81/155 of the power, or 81/155 of the length at the same power.
    Values are exact multiples of declared 1550 nm inputs when supplied.
    """
    gain = 1 / RATIO
    out = dict(phase_per_power_gain=gain, power_for_pi_fraction=RATIO, length_for_pi_fraction=RATIO)
    if phase_per_power_rad_per_w_1550 is not None:
        out["phase_per_power_rad_per_w_810"] = _frac(phase_per_power_rad_per_w_1550, "phase per power") * gain
    if heater_length_um_1550 is not None:
        out["heater_length_um_810_same_power"] = _frac(heater_length_um_1550, "heater length") * RATIO
    return out


def drift_retarget(*, dn_dT_per_K="2.45e-5", path_length_difference_m="1e-3", delta_T_K=1):
    """Grid steps per kelvin per millimetre of asymmetry at both wavelengths."""
    a = thermo_optic_drift(dn_dT_per_K=dn_dT_per_K, path_length_difference_m=path_length_difference_m,
                           delta_T_K=delta_T_K, wavelength_m=Fraction(SOURCE_WAVELENGTH_NM, 10 ** 9))
    b = thermo_optic_drift(dn_dT_per_K=dn_dT_per_K, path_length_difference_m=path_length_difference_m,
                           delta_T_K=delta_T_K, wavelength_m=Fraction(TARGET_WAVELENGTH_NM, 10 ** 9))
    return dict(steps_1550=a["steps_pi_over_32"], steps_810=b["steps_pi_over_32"],
                ratio=b["steps_pi_over_32"] / a["steps_pi_over_32"],
                allowed_excursion_fraction=RATIO,
                note="to keep the same phase error between calibrations the temperature excursion allowed at 810 nm is 81/155 of the 1550 nm one; T1/T2 and the cut-and-correct rule are unchanged")


def phase_layer_is_wavelength_free():
    """Statement R2: T1, T2, D1 and D2 are identities in the phase variables.
    Wavelength enters only the map from volts and kelvin to phase, so the
    verification layer carries over to 810 nm unchanged; the calibration map
    and the component designs do not."""
    return dict(unchanged=["common-mode invariance T1", "drift dichotomy T2", "single-site Euler D1", "fusion D2",
                           "106-setting protocol and codebook", "31-channel calibration contract (context wavelength_nm becomes 810)"],
                changed=["volts and kelvin to phase map", "MMI/coupler design", "waveguide width and bend radius",
                         "source, filters and detectors", "every measured number"])


def retarget_spec():
    """The declared 810 nm re-target as a JSON-ready record."""
    det = next(o for o in DETECTOR_OPTIONS if o["option"] == "si_spad_810")
    rows = scaled_geometry()
    return dict(schema="native-core-retarget-v1", author="Monty", status="SCALED_NOMINAL",
                source_wavelength_nm=SOURCE_WAVELENGTH_NM, target_wavelength_nm=TARGET_WAVELENGTH_NM,
                ratio=str(RATIO), scaling=scale_invariance_statement() | dict(ratio=str(RATIO)),
                geometry=[{k: (str(v) if isinstance(v, Fraction) else v) for k, v in r.items()} for r in rows],
                thickness_ratio={k: str(v) for k, v in thickness_ratio().items()},
                heater={k: str(v) for k, v in heater_retarget().items()},
                drift={k: (str(v) if isinstance(v, Fraction) else v) for k, v in drift_retarget().items()},
                phase_layer=phase_layer_is_wavelength_free(),
                vendor_cells="mmi2x2.gds and heater.gds are pinned 1550 nm cells; the MMI cannot be reused at 810 nm and must be redesigned (or replaced by a directional coupler); the heater polygon may be reused subject to electrical rules",
                platform="CORNERSTONE 300 nm SiN is the pinned 1550 nm candidate; its support for 810 nm operation is not established here and must be confirmed, or a visible/NIR SiN platform selected",
                detector=det, logical_netlist="unchanged: 16 code paths, 6 exchange units, 4 bypasses, 1 guard; dual-rail route adds one coupler per fusion step",
                next_evidence=["mode solver: single-mode TE at 810 nm with width margin, effective and group index, bend loss at the scaled radius",
                               "MMI or coupler design at 810 nm with splitting ratio tolerance", "foundry rule check on the re-targeted GDS",
                               "fabricated core and bright-light transfer matrix"],
                measured_parameters=None, solver_run=False, drc_run=False, fabricated=False)


def design_readiness(record):
    """Fail-closed grade of an 810 nm design record.

    SCALED_NOMINAL is the floor. SOLVER_VERIFIED needs declared single-mode
    margin, MMI splitting tolerance and bend loss from a named solver run;
    DRC_PASSED needs a foundry rule report; FABRICATED a lot and die id;
    MEASURED a recorded bright-light transfer matrix with evidence_class
    LAB_RECORDED. Missing or synthetic items stop the grade at the last
    satisfied stage and are listed as reasons.
    """
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    reasons, grade = [], "SCALED_NOMINAL"
    solver = record.get("solver")
    ok = type(solver) is dict and solver.get("tool") and solver.get("single_mode_te_810") is True \
        and solver.get("width_margin_nm") is not None and solver.get("mmi_split_tolerance") is not None \
        and solver.get("bend_loss_db_per_90deg") is not None
    if not ok:
        reasons.append("solver block incomplete: tool, single_mode_te_810, width_margin_nm, mmi_split_tolerance, bend_loss_db_per_90deg")
        return dict(grade=grade, reasons=reasons, allowed=["scaled nominal geometry only"])
    grade = "SOLVER_VERIFIED"
    drc = record.get("drc")
    if not (type(drc) is dict and drc.get("foundry") and drc.get("passed") is True and drc.get("report_sha256")):
        reasons.append("drc block incomplete: foundry, passed, report_sha256")
        return dict(grade=grade, reasons=reasons, allowed=["solver-verified 810 nm design"])
    grade = "DRC_PASSED"
    fab = record.get("fabrication")
    if not (type(fab) is dict and fab.get("lot_id") and fab.get("die_id")):
        reasons.append("fabrication block incomplete: lot_id, die_id")
        return dict(grade=grade, reasons=reasons, allowed=["rule-checked 810 nm design"])
    grade = "FABRICATED"
    meas = record.get("measurement")
    if not (type(meas) is dict and meas.get("evidence_class") == "LAB_RECORDED" and meas.get("transfer_matrix_sha256")):
        reasons.append("measurement block incomplete or not LAB_RECORDED")
        return dict(grade=grade, reasons=reasons, allowed=["fabricated 810 nm core, unmeasured"])
    return dict(grade="MEASURED", reasons=reasons, allowed=["measured 810 nm core transfer matrix on record"])
