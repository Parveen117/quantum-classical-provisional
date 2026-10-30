"""810 nm re-target of the SiN core: exact scaling, heater and drift laws, readiness grader."""
from fractions import Fraction
import unittest

from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.core_retarget import (
    RATIO, READINESS, design_readiness, drift_retarget, heater_retarget, phase_layer_is_wavelength_free,
    retarget_spec, scale_invariance_statement, scaled_geometry, thickness_ratio,
)


class ScalingTests(unittest.TestCase):
    def test_ratio_is_exact(self):
        self.assertEqual(RATIO, Fraction(81, 155))

    def test_pinned_optical_dimensions_scale_and_platform_ones_do_not(self):
        rows = {r["dimension"]: r for r in scaled_geometry()}
        self.assertEqual(rows["strip_width"]["scaled_nm"], Fraction(19440, 31))       # 627.1 nm
        self.assertEqual(rows["bend_radius"]["scaled_um"], Fraction(486, 31))          # 15.7 um
        self.assertEqual(rows["mmi2x2_body_length"]["scaled_um"], Fraction(18792, 155))  # 121.2 um
        self.assertEqual(rows["mmi2x2_gap"]["scaled_nm"], Fraction(25920, 31))         # 836 nm
        self.assertTrue(rows["strip_width"]["passes_local_minimum"])
        self.assertTrue(rows["mmi2x2_gap"]["passes_local_minimum"])
        self.assertEqual(rows["nitride_thickness_nm"]["scaled_nm"], 300)
        self.assertEqual(rows["buried_oxide_thickness_nm"]["scaled_nm"], 3000)
        self.assertIn("fixed by platform", rows["nitride_thickness_nm"]["status"])

    def test_scaling_is_linear_and_identity_at_ratio_one(self):
        pinned = dict(strip_width=Fraction(6, 5), mmi2x2_gap=Fraction(8, 5))
        same = {r["dimension"]: r["scaled_um"] for r in scaled_geometry(pinned, ratio=Fraction(1)) if r["dimension"] in pinned}
        self.assertEqual(same, pinned)
        half = {r["dimension"]: r["scaled_um"] for r in scaled_geometry(pinned, ratio=Fraction(1, 2))}
        self.assertEqual(half["strip_width"], Fraction(3, 5))

    def test_negative_control_too_narrow_strip_fails_local_minimum(self):
        rows = {r["dimension"]: r for r in scaled_geometry(dict(strip_width=Fraction(1, 2), mmi2x2_gap=Fraction(2, 5)))}
        self.assertFalse(rows["strip_width"]["passes_local_minimum"])  # 261 nm < 350 nm
        self.assertFalse(rows["mmi2x2_gap"]["passes_local_minimum"])   # 209 nm < 250 nm

    def test_float_ratio_is_rejected_by_the_rational_guard(self):
        with self.assertRaises(TypeError):
            scaled_geometry(dict(strip_width=Fraction(6, 5)), ratio=1.0)
        # JSON-declared dimensions such as 1.2 are read through their decimal string and stay exact
        self.assertEqual(scaled_geometry(dict(strip_width=1.2), ratio=Fraction(1))[0]["scaled_um"], Fraction(6, 5))

    def test_thickness_ratio_rises_by_inverse_ratio(self):
        t = thickness_ratio()
        self.assertEqual(t["increase"], 1 / RATIO)
        self.assertEqual(t["target"], Fraction(10, 27))

    def test_scale_invariance_statement_names_what_breaks_it(self):
        s = scale_invariance_statement()
        self.assertEqual(s["status"], "SCALED_NOMINAL")
        self.assertTrue(any("300 nm" in b for b in s["broken_by"]))
        self.assertTrue(any("dispersion" in b for b in s["broken_by"]))


class HeaterAndDriftTests(unittest.TestCase):
    def test_heater_phase_per_power_gain_is_inverse_ratio(self):
        h = heater_retarget(phase_per_power_rad_per_w_1550=100, heater_length_um_1550=400)
        self.assertEqual(h["phase_per_power_gain"], Fraction(155, 81))
        self.assertEqual(h["phase_per_power_rad_per_w_810"], Fraction(15500, 81))
        self.assertEqual(h["heater_length_um_810_same_power"], Fraction(6480, 31))
        self.assertEqual(h["power_for_pi_fraction"] * h["phase_per_power_gain"], 1)

    def test_drift_steps_scale_by_inverse_ratio_exactly(self):
        d = drift_retarget()
        self.assertEqual(d["steps_1550"], Fraction(49, 1550) * 32)
        self.assertEqual(d["ratio"], Fraction(155, 81))
        self.assertEqual(d["steps_810"], d["steps_1550"] * Fraction(155, 81))
        self.assertEqual(d["allowed_excursion_fraction"], RATIO)

    def test_drift_is_linear_in_temperature(self):
        self.assertEqual(drift_retarget(delta_T_K=2)["steps_810"], 2 * drift_retarget(delta_T_K=1)["steps_810"])

    def test_phase_layer_statement_splits_unchanged_from_changed(self):
        p = phase_layer_is_wavelength_free()
        self.assertTrue(any("T1" in u for u in p["unchanged"]))
        self.assertTrue(any("fusion D2" in u for u in p["unchanged"]))
        self.assertTrue(any("volts and kelvin" in c for c in p["changed"]))
        self.assertFalse(set(p["unchanged"]) & set(p["changed"]))


SOLVER = dict(tool="declared-solver", single_mode_te_810=True, width_margin_nm=80, mmi_split_tolerance="1/50",
              bend_loss_db_per_90deg="1/1000")
DRC = dict(foundry="declared-foundry", passed=True, report_sha256="0" * 64)
FAB = dict(lot_id="L1", die_id="D1")
MEAS = dict(evidence_class="LAB_RECORDED", transfer_matrix_sha256="1" * 64)


class ReadinessTests(unittest.TestCase):
    def test_spec_is_scaled_nominal_with_no_solver_drc_or_fabrication(self):
        s = retarget_spec()
        self.assertEqual(s["status"], "SCALED_NOMINAL")
        self.assertFalse(s["solver_run"] or s["drc_run"] or s["fabricated"])
        self.assertIsNone(s["measured_parameters"])
        self.assertEqual(s["detector"]["option"], "si_spad_810")
        self.assertEqual(design_readiness(s)["grade"], "SCALED_NOMINAL")

    def test_grades_climb_only_with_complete_blocks(self):
        rec = {}
        self.assertEqual(design_readiness(rec)["grade"], READINESS[0])
        rec["solver"] = SOLVER
        self.assertEqual(design_readiness(rec)["grade"], "SOLVER_VERIFIED")
        rec["drc"] = DRC
        self.assertEqual(design_readiness(rec)["grade"], "DRC_PASSED")
        rec["fabrication"] = FAB
        self.assertEqual(design_readiness(rec)["grade"], "FABRICATED")
        rec["measurement"] = MEAS
        r = design_readiness(rec)
        self.assertEqual((r["grade"], r["reasons"]), ("MEASURED", []))

    def test_negative_controls_stop_at_the_last_satisfied_stage(self):
        multimode = dict(solver=dict(SOLVER, single_mode_te_810=False), drc=DRC, fabrication=FAB, measurement=MEAS)
        self.assertEqual(design_readiness(multimode)["grade"], "SCALED_NOMINAL")
        no_bend = dict(solver={k: v for k, v in SOLVER.items() if k != "bend_loss_db_per_90deg"}, drc=DRC)
        self.assertEqual(design_readiness(no_bend)["grade"], "SCALED_NOMINAL")
        drc_failed = dict(solver=SOLVER, drc=dict(DRC, passed=False), fabrication=FAB, measurement=MEAS)
        self.assertEqual(design_readiness(drc_failed)["grade"], "SOLVER_VERIFIED")
        synthetic = dict(solver=SOLVER, drc=DRC, fabrication=FAB, measurement=dict(MEAS, evidence_class="SYNTHETIC"))
        self.assertEqual(design_readiness(synthetic)["grade"], "FABRICATED")
        skipped_fab = dict(solver=SOLVER, drc=DRC, measurement=MEAS)
        self.assertEqual(design_readiness(skipped_fab)["grade"], "DRC_PASSED")
        with self.assertRaises(ValueError):
            design_readiness([])


if __name__ == "__main__":
    unittest.main()
