"""Target-specific visibility, normalization and fail-closed adapter checks."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from phase_seam_foundation.photonic_io import fingerprint
from phase_seam_foundation.photonic_observer import (
    TARGETS, observer_packet, assess_uncertainty,
)
from phase_seam_foundation.photonic_response import optical_response


def packet(theta=16, target="exchange_angle", measurements="basis", **kwargs):
    m = {"basis":4, "local":16, "reference":24}[measurements]
    nuisance = kwargs.get("nuisance_response") or {}
    options = dict(state_scales=[1]*(5+len(nuisance)), reading_scales=[1]*m,
                   target_scales=[1]*len(TARGETS[target]))
    options.update(kwargs)
    return observer_packet(((32-theta)%64, 0, 48, 48), target=target,
                           measurements=measurements, **options)


def bounds(**kwargs):
    result = dict(sensor_noise_bound=0.001, calibration_drift_operator_bound=0.002,
                  state_norm_bound=0.1, target_error_budget=0.01,
                  nonlinear_remainder_bound=0.0001)
    result.update(kwargs)
    return result


class PhotonicObserverTests(unittest.TestCase):
    def test_targets_require_different_observers_at_quadrature(self):
        expected = {"exchange_angle":(0,0,0), "relative_phases":(3,1,0),
                    "absolute_reference":(1,1,1)}
        for target, dims in expected.items():
            for family, blind in zip(("basis","local","reference"), dims):
                p = packet(target=target, measurements=family)
                self.assertEqual(p["target_blind_dimension"], blind)
                self.assertEqual(p["exact_target_faithful"], blind == 0)
                self.assertEqual(p["export_status"], "EXACT_RATIONAL")

    def test_endpoints_do_not_inherit_quadrature_visibility(self):
        for theta in (0,32):
            for family, angle_blind, phase_blind in (("basis",1,4),("local",0,2),("reference",0,1)):
                self.assertEqual(packet(theta, measurements=family)["target_blind_dimension"], angle_blind)
                self.assertEqual(packet(theta, "relative_phases", family)["target_blind_dimension"], phase_blind)

    def test_angle_target_has_native_exchange_sign(self):
        p = packet()
        # v0.12's word gives theta = pi - lower + upper. Increasing lower
        # decreases the native theta; it must not be exported with reversed sign.
        self.assertEqual(p["target"], [["-1","1","0","0","0"]])

    def test_irrational_field_is_decided_exactly_without_rational_rounding(self):
        p = packet(8)
        self.assertTrue(p["exact_target_faithful"])
        self.assertEqual(p["export_status"], "EXACT_FIELD_ONLY")
        self.assertIsNone(p["sensor"])
        report = assess_uncertainty(p, bounds=bounds())
        self.assertEqual(report["status"], "UNSUPPORTED_IRRATIONAL_ENGINE_EXPORT")
        self.assertIsNone(report["model_budget_met"])

    def test_explicit_scaling_preserves_faithfulness_and_transforms_rows(self):
        p = packet(state_scales=[2,3,4,5,6], reading_scales=[2]*4, target_scales=[5])
        self.assertTrue(p["exact_target_faithful"])
        self.assertEqual(p["sensor"][0], ["1/2","-3/4","0","0","0"])
        self.assertEqual(p["target"][0], ["-2/5","3/5","0","0","0"])

    def test_nuisance_can_hide_target_without_being_a_target(self):
        response = optical_response((16,0,48,48), measurements="basis")
        confounded = packet(nuisance_response={"readout_drift":[r[0] for r in response["jacobian"]]})
        self.assertEqual(confounded["target_blind_dimension"], 1)
        self.assertEqual(confounded["target"][0][-1], "0")
        # An entirely invisible nuisance does not need to be reconstructed.
        harmless = packet(nuisance_response={"unobserved_environment":[0]*4})
        self.assertTrue(harmless["exact_target_faithful"])

    def test_incomplete_bounds_and_no_engine_are_not_accepted(self):
        p = packet()
        for name in bounds():
            incomplete = bounds(); del incomplete[name]
            result = assess_uncertainty(p, bounds=incomplete)
            self.assertEqual(result["status"], "INCOMPLETE_UNCERTAINTY_BOUNDS")
            self.assertIsNone(result["model_budget_met"])
            self.assertFalse(result["calibration_accepted"])
        result = assess_uncertainty(p, bounds=bounds())
        self.assertEqual(result["status"], "DEVICE_ENGINE_NOT_SUPPLIED")
        self.assertFalse(result["hardware_submitted"])
        self.assertEqual(assess_uncertainty(packet(0), bounds=bounds())["status"], "BLINDNESS_DETECTED")

    def test_packet_corruption_and_resigned_wrong_decision_are_rejected(self):
        p = packet(); p["phase_steps"][0] = 0
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            assess_uncertainty(p, bounds=bounds())
        p = packet(); p["sensor_rank"] = 2
        p["packet_sha256"] = fingerprint({k:v for k,v in p.items() if k != "packet_sha256"})
        with self.assertRaisesRegex(ValueError, "decision mismatch"):
            assess_uncertainty(p, bounds=bounds())
        p = packet(); p["sensor"][0][0] = "2"
        p["packet_sha256"] = fingerprint({k:v for k,v in p.items() if k != "packet_sha256"})
        with self.assertRaisesRegex(ValueError, "differs from exact model"):
            assess_uncertainty(p, bounds=bounds())

    def test_wrong_private_source_pin_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            sentinel = Path(folder)/"executed"
            (Path(folder)/"seam_antenna.py").write_text(f"open({str(sentinel)!r}, 'w').close()")
            with self.assertRaisesRegex(ValueError, "source pin mismatch"):
                assess_uncertainty(packet(), bounds=bounds(), device_source_dir=folder)
            self.assertFalse(sentinel.exists())

    def test_small_absolute_residual_cannot_hide_bad_relative_target_reconstruction(self):
        p = packet(target_scales=[10**12])
        # A possible upstream SVD report passes its absolute-scale test, but
        # residual 1e-20 is too large relative to a target of scale 1e-12.
        upstream = dict(exact_target_faithful=True, numerical_decoder_consistent=True,
                        numerical_sensor_rank=1, target_is_zero=False,
                        decoder_gain=1e-12, combined_target_error_upper=1.3e-15,
                        decoder_reconstruction_residual=1e-20,
                        robust_status="TARGET_FAITHFUL_ROBUST")
        with patch("phase_seam_foundation.photonic_observer._device_engine",
                   return_value=lambda *args, **kwargs: upstream):
            result = assess_uncertainty(p,bounds=bounds(),device_source_dir="injected_test_engine")
        self.assertEqual(result["status"],"NUMERICAL_DECODER_UNRESOLVED")
        self.assertFalse(result["numerical_checks"]["target_relative_residual_consistent"])
        self.assertFalse(result["model_budget_met"])

    def test_bad_scales_nuisance_bounds_and_tolerances_are_rejected(self):
        for scales in ([1]*4, [0]*5, [True]*5, [0.1]*5, [-1]*5):
            with self.assertRaises(ValueError): packet(state_scales=scales)
        for nuisance in ({"reference":[0]*4}, {"drift":[0]*3}, {"drift":[0.1]*4}):
            with self.assertRaises((ValueError,TypeError)): packet(nuisance_response=nuisance)
        p = packet()
        for value in (True, float("nan"), float("inf"), -1, "0.1"):
            with self.assertRaises(ValueError): assess_uncertainty(p, bounds=bounds(sensor_noise_bound=value))
        for rcond in (True, 0, float("nan"), 0.1):
            with self.assertRaises(ValueError): assess_uncertainty(p, bounds=bounds(), rcond=rcond)
        with self.assertRaises(ValueError): assess_uncertainty(p, bounds={"unknown":0})
        with self.assertRaises(ValueError): packet(unit_index=True)


if __name__ == "__main__": unittest.main()
