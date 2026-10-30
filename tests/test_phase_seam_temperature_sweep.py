"""Exact temperature-sweep statements, protocol guards and fail-closed verdicts."""
from fractions import Fraction
import unittest

from native_relational_qc.cyclotomic64 import ZERO
from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.temperature_sweep import (
    COMMON_MODE, DETECTOR_OPTIONS, FAMILIES, common_mode_global_phase, common_mode_invariance, deviation, drift_dichotomy,
    drift_table, hom_coincidence, shifted_response, sweep_protocol, temperature_claim_verdict,
    thermo_optic_drift,
)


def record(**changes):
    rows = [dict(chip_temperature_c=t, calibrated_tvd_upper_bound="0.01",
                 uncalibrated_tvd_upper_bound=u, miscalibration_tvd_lower_bound="0.1")
            for t, u in ((20, "0.01"), (35, "0.08"), (50, "0.2"))]
    base = dict(evidence_class="LAB_RECORDED", tvd_tolerance="0.02", sweep=rows,
                subsystem_temperatures_c=dict(chip=[20, 50], source=[22, 24], detector=[18, 26]))
    base.update(changes)
    return base


class CommonModeTests(unittest.TestCase):
    def test_common_mode_is_a_global_phase_at_every_angle(self):
        for theta in range(65):
            for shift in (-64, -17, 1, 5, 32, 64):
                self.assertTrue(common_mode_global_phase(theta, shift))
        with self.assertRaises(ValueError):
            common_mode_global_phase(16, 65)

    def test_common_mode_heating_changes_no_probability(self):
        for theta in (0, 8, 16, 32, 64):
            for shift in (-17, 5, 32):
                self.assertEqual(common_mode_invariance(theta, shift), {f: True for f in FAMILIES})

    def test_common_mode_is_the_declared_kernel_direction(self):
        self.assertEqual(COMMON_MODE, (1, 1, 0, 0, 1))
        for theta in (8, 16, 24):
            self.assertTrue(drift_dichotomy(theta, tuple(3*c for c in COMMON_MODE))["in_kernel"])

    def test_unit_common_phase_without_reference_is_visible_only_to_reference_family(self):
        d = drift_dichotomy(16, (2, 2, 0, 0, 0))
        self.assertFalse(d["in_kernel"])
        self.assertEqual(d["first_order_visible"], dict(basis=False, local=False, reference=True))

    def test_arm_drift_is_visible_and_exactly_corrected(self):
        d = drift_dichotomy(16, (3, 0, 0, 0, 0))
        self.assertFalse(d["in_kernel"])
        self.assertTrue(all(d["first_order_visible"].values()))
        self.assertEqual(d["exact_correction_steps"], (-3, 0, 0, 0, 0))
        self.assertTrue(d["corrected_equals_common_mode"])
        self.assertTrue(d["corrected_response_identical"])
        self.assertEqual(d["reference_rank"], 4)

    def test_trim_drift_is_invisible_to_basis_powers_negative_control(self):
        d = drift_dichotomy(16, (0, 0, 4, 0, 0))
        self.assertEqual(d["first_order_visible"], dict(basis=False, local=True, reference=True))

    def test_deviation_is_zero_only_in_the_kernel(self):
        self.assertTrue(deviation(16, (5, 5, 0, 0, 5))["squared_deviation_is_zero"])
        moved = deviation(16, (5, 0, 0, 0, 0))
        self.assertFalse(moved["squared_deviation_is_zero"])
        self.assertGreater(moved["max_abs_shift_lower_bound"], 0)
        self.assertGreaterEqual(moved["max_abs_shift_upper_bound"], moved["max_abs_shift_lower_bound"])

    def test_shifted_response_wraps_steps_and_rejects_bad_drift(self):
        wrapped = shifted_response(16, (64, 0, 0, 0, 0))
        same = shifted_response(16, (-64, 0, 0, 0, 0))
        self.assertEqual(wrapped["probabilities"], same["probabilities"])
        with self.assertRaises(ValueError):
            shifted_response(16, (65, 0, 0, 0, 0))
        with self.assertRaises(TypeError):
            shifted_response(16, (1.0, 0, 0, 0, 0))
        with self.assertRaises(ValueError):
            drift_dichotomy(16, (1, 2, 3))


class ThermoOpticTests(unittest.TestCase):
    def test_declared_sin_numbers_give_about_one_step_per_kelvin_per_millimetre(self):
        d = thermo_optic_drift(dn_dT_per_K="2.45e-5", path_length_difference_m="1e-3",
                               delta_T_K=1, wavelength_m="1.55e-6")
        self.assertEqual(d["phi_over_pi"], Fraction(49, 1550))
        self.assertEqual(d["nearest_step"], 1)
        self.assertTrue(d["inputs_are_declared"])

    def test_shorter_wavelength_scales_inversely(self):
        a = thermo_optic_drift(dn_dT_per_K="2.45e-5", path_length_difference_m="1e-3", delta_T_K=1, wavelength_m="1.55e-6")
        b = thermo_optic_drift(dn_dT_per_K="2.45e-5", path_length_difference_m="1e-3", delta_T_K=1, wavelength_m="8.1e-7")
        self.assertEqual(b["phi_over_pi"]/a["phi_over_pi"], Fraction(155, 81))

    def test_guards(self):
        with self.assertRaises(ValueError):
            thermo_optic_drift(dn_dT_per_K="2.45e-5", path_length_difference_m="1e-3", delta_T_K=1, wavelength_m=0)
        with self.assertRaises(TypeError):
            thermo_optic_drift(dn_dT_per_K=2.45e-5, path_length_difference_m="1e-3", delta_T_K=1, wavelength_m="1.55e-6")
        with self.assertRaises(ResourceLimit):
            drift_table(dn_dT_per_K="1", wavelength_m="1", path_length_differences_m=list(range(100)), delta_Ts_K=list(range(50)))

    def test_table_rows(self):
        rows = drift_table(dn_dT_per_K="2.45e-5", wavelength_m="1.55e-6",
                           path_length_differences_m=["1e-5", "1e-3"], delta_Ts_K=[1, 10])
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[-1]["nearest_step"], 10)


class HomTests(unittest.TestCase):
    def test_coincidence_matches_cos_squared_at_all_angles(self):
        for theta in range(0, 65):
            self.assertTrue(hom_coincidence(theta)["closed_form_matches"])

    def test_quadrature_separates_indistinguishable_from_distinguishable(self):
        h = hom_coincidence(16)
        self.assertEqual(h["indistinguishable"], ZERO)
        self.assertEqual(h["distinguishable"].real_bounds(6), (Fraction(1, 2), Fraction(1, 2)))

    def test_endpoints_cannot_distinguish(self):
        for theta in (0, 32, 64):
            h = hom_coincidence(theta)
            self.assertEqual(h["indistinguishable"], h["distinguishable"])


class ProtocolTests(unittest.TestCase):
    def test_plan_binds_layout_and_lists_controls(self):
        plan = sweep_protocol([20, 30, 40, 50], wavelength_nm=810, detector_option="si_spad_810")
        self.assertEqual(plan["status"], "NOT_RUN")
        self.assertIsNone(plan["evidence_class"])
        self.assertEqual(plan["point_count"], 4)
        self.assertEqual(len(plan["layout_gds_sha256"]), 64)
        stages = [s["stage"] for s in plan["points"][0]["stages"]]
        self.assertEqual(stages, ["stabilize", "bright_light_calibration", "protocol_calibrated",
                                  "protocol_uncalibrated_control", "miscalibration_control",
                                  "two_photon_hom", "temperature_log"])
        self.assertEqual(plan["points"][0]["stages"][1]["channels"], 31)

    def test_detector_option_and_wavelength_must_agree(self):
        with self.assertRaises(ValueError):
            sweep_protocol([20, 30], wavelength_nm=1550, detector_option="si_spad_810")
        with self.assertRaises(ValueError):
            sweep_protocol([20, 30], wavelength_nm=1550, detector_option="unknown")
        self.assertEqual(sweep_protocol([20, 30], wavelength_nm=1550, detector_option="snspd_1550")
                         ["detector_option"]["thermal_class_if_recorded"], "CRYOGENIC")

    def test_sweep_guards(self):
        with self.assertRaises(ValueError):
            sweep_protocol([], wavelength_nm=810, detector_option="si_spad_810")
        with self.assertRaises(ValueError):
            sweep_protocol([20, 20], wavelength_nm=810, detector_option="si_spad_810")
        with self.assertRaises(ValueError):
            sweep_protocol([20, 30], wavelength_nm=810, detector_option="si_spad_810", reference_temperature_c=25)
        with self.assertRaises(ValueError):
            sweep_protocol([-300], wavelength_nm=810, detector_option="si_spad_810")
        with self.assertRaises(ValueError):
            sweep_protocol(list(range(65)), wavelength_nm=810, detector_option="si_spad_810")

    def test_detector_table_covers_three_thermal_classes(self):
        self.assertEqual({o["thermal_class_if_recorded"] for o in DETECTOR_OPTIONS},
                         {"CRYOGENIC", "CRYOGEN_FREE", "ROOM_TEMPERATURE"})


class VerdictTests(unittest.TestCase):
    def test_recorded_room_temperature_sweep_with_calibration(self):
        v = temperature_claim_verdict(record())
        self.assertEqual(v["thermal_class"], "ROOM_TEMPERATURE")
        self.assertEqual(v["logic_class"], "TEMPERATURE_INDEPENDENT_AFTER_CALIBRATION")
        self.assertEqual(len(v["claims_allowed"]), 2)
        self.assertTrue(any("heated to 50" in r for r in v["reasons"]))

    def test_synthetic_log_allows_nothing(self):
        v = temperature_claim_verdict(record(evidence_class="SYNTHETIC_TEST_FIXTURE"))
        self.assertFalse(v["evidence_recorded"])
        self.assertEqual(v["claims_allowed"], [])

    def test_cooled_detector_is_not_room_temperature(self):
        v = temperature_claim_verdict(record(subsystem_temperatures_c=dict(chip=[20, 50], source=[22, 24], detector=[-60, -40])))
        self.assertEqual(v["thermal_class"], "CRYOGEN_FREE")
        self.assertIn("cryogen-free operation; not room temperature", v["claims_allowed"])
        v = temperature_claim_verdict(record(subsystem_temperatures_c=dict(chip=[20, 50], source=[22, 24], detector=[-271, -270])))
        self.assertEqual(v["thermal_class"], "CRYOGENIC")

    def test_missing_subsystem_is_undetermined(self):
        v = temperature_claim_verdict(record(subsystem_temperatures_c=dict(chip=[20, 50], source=[22, 24])))
        self.assertEqual(v["thermal_class"], "UNDETERMINED")

    def test_power_is_required(self):
        rows = record()["sweep"]
        rows[1]["miscalibration_tvd_lower_bound"] = "0.01"
        v = temperature_claim_verdict(record(sweep=rows))
        self.assertEqual(v["logic_class"], "TEST_WITHOUT_POWER")
        self.assertEqual([c for c in v["claims_allowed"] if "logical transfer" in c], [])

    def test_calibrated_failure_is_temperature_dependent(self):
        rows = record()["sweep"]
        rows[2]["calibrated_tvd_upper_bound"] = "0.05"
        self.assertEqual(temperature_claim_verdict(record(sweep=rows))["logic_class"], "TEMPERATURE_DEPENDENT")

    def test_uncalibrated_pass_is_the_stronger_class(self):
        rows = record()["sweep"]
        for row in rows:
            row["uncalibrated_tvd_upper_bound"] = "0.015"
        v = temperature_claim_verdict(record(sweep=rows))
        self.assertEqual(v["logic_class"], "TEMPERATURE_INSENSITIVE_WITHOUT_CALIBRATION")

    def test_span_and_point_count(self):
        rows = record()["sweep"][:2]
        self.assertEqual(temperature_claim_verdict(record(sweep=rows))["logic_class"], "UNDETERMINED")
        rows = record()["sweep"]
        for row, t in zip(rows, (20, 25, 30)):
            row["chip_temperature_c"] = t
        v = temperature_claim_verdict(record(sweep=rows))
        self.assertEqual(v["logic_class"], "UNDETERMINED")
        self.assertTrue(any("span" in r for r in v["reasons"]))

    def test_tolerance_and_row_guards(self):
        self.assertEqual(temperature_claim_verdict(record(tvd_tolerance="1"))["logic_class"], "UNDETERMINED")
        self.assertEqual(temperature_claim_verdict(record(tvd_tolerance=None))["logic_class"], "UNDETERMINED")
        rows = record()["sweep"]
        del rows[0]["miscalibration_tvd_lower_bound"]
        self.assertEqual(temperature_claim_verdict(record(sweep=rows))["logic_class"], "UNDETERMINED")
        with self.assertRaises(ValueError):
            temperature_claim_verdict([])

    def test_never_allowed_list_is_always_present(self):
        for rec in (record(), record(evidence_class=None)):
            self.assertEqual(len(temperature_claim_verdict(rec)["claims_never_allowed"]), 3)


if __name__ == "__main__":
    unittest.main()
