"""Physical phase convention and complete actuator binding, without CAD imports."""
from copy import deepcopy
import unittest

from native_relational_qc.phase_backend import Phase64Circuit,prepare
from phase_seam_foundation.sector_control import pulse_coefficients
from phase_seam_foundation.photonic_io import (
    calibration_template,calibration_target,compile_drive_plan,fingerprint,
)
from phase_seam_foundation.photonic_layout import EXTRA_CHANNELS,layout_spec,physical_phase_targets


def physical_fixture():
    c=calibration_template(physical_layout=True)
    c.update(status="RECORDED",evidence_class="SYNTHETIC_TEST_FIXTURE",device_id="fixture",
             calibration_id="fixture",valid_from_utc="2026-10-24T00:00:00Z",valid_until_utc="2026-10-25T00:00:00Z",
             context=dict(wavelength_nm=1550,chip_temperature_c=25,assembly_revision="fixture",fixed_trim_revision="fixture"))
    c["actuator_map"]={n:f"dac_{i}" for i,n in enumerate(c["actuator_map"])}
    c["voltage_limits"]={n:[0,2] for n in c["actuator_map"]}
    c["settings"]=[dict(setting_id="basis_16_1",target_sha256=fingerprint(calibration_target("basis_16_1",physical_layout=True)),
                         volts={n:"1" for n in c["actuator_map"]},evidence_sha256="a"*64)]
    return c


def bind(c,**kw):
    return compile_drive_plan("basis_16_1",c,device_id="fixture",context=c["context"],
                              at_utc="2026-10-24T12:00:00Z",**kw)


class LayoutControlTests(unittest.TestCase):
    def test_directional_couplers_and_port_trims_match_all_exact_angles(self):
        for step in range(64):
            targets=physical_phase_targets({f"core_{i}":(-step)%64 for i in range(6)})
            for bit in (0,1):
                c=Phase64Circuit(1)
                if bit:c.add("x",0)
                def phase(k):
                    for _ in range(k%64):c.add("p64",0)
                def coupler():
                    phase(16);c.add("h",0);phase(16)  # D=Z^dag H Z^dag
                phase(targets["core_0_input_trim"]);coupler()
                phase(targets["core_0"]);coupler();phase(targets["core_0_output_trim"])
                a,b=pulse_coefficients(step)
                expected={bit:a,1-bit:b};expected={k:v for k,v in expected.items() if v}
                self.assertEqual(prepare(c).amplitudes,expected,(step,bit))

    def test_layout_template_requires_all_physical_and_external_channels(self):
        c=calibration_template(physical_layout=True)
        chip={h["channel"] for h in layout_spec()["heaters"]}
        self.assertEqual(len(chip),28);self.assertEqual(len(EXTRA_CHANNELS),22)
        self.assertEqual(set(c["actuator_map"]),chip|{"preparation","analysis","guard"})
        self.assertEqual(c["settings"],[])
        self.assertTrue(all(v is None for v in c["actuator_map"].values()))

    def test_physical_profile_requires_explicit_scope_and_full_vector(self):
        c=physical_fixture()
        with self.assertRaises(ValueError):bind(c)
        old=deepcopy(c);old["schema"]="native-photonic-calibration-v1"
        with self.assertRaises(ValueError):bind(old,physical_layout=True)
        for section in ("actuator_map","voltage_limits"):
            bad=deepcopy(c);del bad[section]["core_0_common"]
            with self.assertRaises(ValueError):bind(bad,physical_layout=True)
        bad=deepcopy(c);del bad["settings"][0]["volts"]["bypass_0"]
        with self.assertRaises(ValueError):bind(bad,physical_layout=True)

    def test_stale_gds_spec_and_logical_only_target_cannot_bind(self):
        for key in ("layout_gds_sha256","layout_spec_sha256"):
            c=physical_fixture();c[key]="b"*64
            with self.assertRaises(ValueError):bind(c,physical_layout=True)
        c=physical_fixture();c["settings"][0]["target_sha256"]=fingerprint(calibration_target("basis_16_1"))
        with self.assertRaises(ValueError):bind(c,physical_layout=True)

    def test_full_physical_binding_remains_offline_and_preserves_synthetic_evidence(self):
        c=physical_fixture();before=deepcopy(c);out=bind(c,physical_layout=True)
        self.assertEqual(c,before);self.assertEqual(len(out["commands"]),31)
        self.assertTrue(out["physical_layout"]);self.assertFalse(out["hardware_submitted"])
        self.assertEqual(out["evidence_class"],"SYNTHETIC_TEST_FIXTURE")
        self.assertEqual(out["route"]["physical_phase_targets_pi_over_32"]["core_0"],16)
        self.assertEqual(out["route"]["physical_phase_targets_pi_over_32"]["core_0_input_trim"],48)

    def test_scope_is_not_truthiness_coerced(self):
        for value in (1,"yes",None):
            with self.assertRaises(TypeError):calibration_template(physical_layout=value)
            with self.assertRaises(TypeError):calibration_target("basis_0_0",physical_layout=value)


if __name__=="__main__":unittest.main()
