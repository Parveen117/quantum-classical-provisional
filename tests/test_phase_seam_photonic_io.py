"""End-to-end exact optical transfer and offline calibration provenance checks."""
from copy import deepcopy
from fractions import Fraction as F
import unittest

from native_relational_qc.cyclotomic64 import Cyclotomic64 as C, ZETA
from native_relational_qc.exact import exact_gate
from native_relational_qc.phase_backend import Phase64Circuit, prepare
from phase_seam_foundation.model import ResourceLimit
from phase_seam_foundation.photonic_exchange import design_photonic_exchange
from phase_seam_foundation.photonic_io import (
    CHANNELS, _two_path, calibration_template, compile_drive_plan,
    fingerprint, io_design, verification_circuit,
)
from phase_seam_foundation.sector_control import pulse_coefficients


def fixture(setting_id="phase_0_16"):
    """Artificial voltages exercise binding only; never a measured calibration."""
    data=calibration_template()
    data.update(status="RECORDED",evidence_class="SYNTHETIC_TEST_FIXTURE",
                device_id="test-only-device",calibration_id="test-only-calibration",
                valid_from_utc="2026-10-24T00:00:00Z",valid_until_utc="2026-10-25T00:00:00Z",
                context=dict(wavelength_nm="1550",chip_temperature_c="25",
                             assembly_revision="fixture-assembly",fixed_trim_revision="fixture-trims"),
                actuator_map={ch:f"dac_{i}" for i,ch in enumerate(CHANNELS)},
                voltage_limits={ch:["0","2"] for ch in CHANNELS})
    route=next(r for r in io_design()["settings"] if r["setting_id"]==setting_id)
    data["settings"]=[dict(setting_id=setting_id,target_sha256=fingerprint(route),
                           volts={ch:"3/2" for ch in CHANNELS},evidence_sha256="a"*64)]
    return data


def bind(data,setting="phase_0_16",**overrides):
    kwargs=dict(device_id="test-only-device",context=fixture()["context"],at_utc="2026-10-24T12:00:00Z")
    kwargs.update(overrides)
    return compile_drive_plan(setting,data,**kwargs)


class PhotonicIOTests(unittest.TestCase):
    def test_returned_design_cannot_mutate_later_targets(self):
        design=io_design();before=fingerprint(design)
        design["settings"][0]["phase_targets_pi_over_32"]["core_0"]=7
        self.assertEqual(fingerprint(io_design()),before)
        self.assertEqual(len(io_design()["process_binding_sha256"]),64)

    def test_routes_keep_guard_isolated_and_all_outputs_observed(self):
        design=io_design();rows=design["settings"]
        self.assertEqual(len(rows),106)
        self.assertEqual(len({r["setting_id"] for r in rows}),106)
        self.assertEqual(design["resources"]["installed_balanced_couplers"],16)
        for r in rows:
            self.assertEqual(set(r["phase_targets_pi_over_32"]),set(CHANNELS))
            self.assertTrue(all(0<=n<64 for n in r["phase_targets_pi_over_32"].values()))
            if r["setting_id"]=="guard_16":
                self.assertEqual(r["guard_ports"],[4,16])
            else:
                self.assertIsNone(r["guard_ports"])
                self.assertEqual(r["guard_configuration"],"physically_bypassed_or_removed")
            if r["kind"]=="cross_block_coherence":
                self.assertEqual(r["preparation_ports"][1],0)
                self.assertEqual(r["analysis_ports"],[r["plus_detector"],r["minus_detector"]])
            else:self.assertIsNone(r["analysis_ports"])

    def test_all_106_complete_circuits_match_exact_complex_targets(self):
        layout=design_photonic_exchange()
        for s in layout.experiment_plan()["settings"]:
            c=verification_circuit(s["id"]);state=prepare(c)
            self.assertTrue(all(label<17 for label in state.amplitudes),s["id"])
            if s["kind"]=="basis_transfer":
                expected=dict(layout.column(s["input_path"],s["phase_steps_pi_over_32"]))
            elif s["kind"]=="cross_block_coherence":
                alpha,beta=pulse_coefficients(s["analyzer_relative_phase_steps"])
                q,f=s["analysis_paths"];expected={q:alpha,f:beta}
            else:
                alpha,beta=pulse_coefficients(s["extra_test_phase_steps_pi_over_32"])
                expected={4:alpha,16:beta}
            expected={p:a for p,a in expected.items() if a}
            self.assertEqual(state.amplitudes,expected,s["id"])

    def test_two_level_export_fixes_spectators_and_uncomputes_workspace(self):
        for ports in ((11,14),(14,11),(4,16),(1,0)):
            p,q=ports
            for source in range(32):
                c=Phase64Circuit(8)
                for b in range(5):
                    if (source>>b)&1:c.add("x",b)
                _two_path(c,ports,(("h",0),("phase",16)))
                actual=prepare(c).amplitudes
                if source in ports:
                    col=ports.index(source);h=exact_gate("h")
                    expected={p:C(h[0][col]),q:C(h[1][col])*ZETA**16}
                else:expected={source:C(1)}
                self.assertEqual(actual,expected,(ports,source))

    def test_unknown_settings_and_gate_caps_reject_without_returning_partial_export(self):
        for setting in ("missing",True,0):
            with self.assertRaises((ValueError,TypeError)):verification_circuit(setting)
        for cap in (True,0,10001):
            with self.assertRaises((ValueError,TypeError)):verification_circuit("basis_0_0",max_gates=cap)
        with self.assertRaises(ResourceLimit):verification_circuit("basis_0_0",max_gates=1)


class CalibrationBindingTests(unittest.TestCase):
    def test_empty_template_cannot_generate_commands(self):
        template=calibration_template()
        self.assertEqual(template["settings"],[])
        self.assertTrue(all(v is None for v in template["voltage_limits"].values()))
        with self.assertRaises(ValueError):bind(template)

    def test_joint_vector_preserves_evidence_and_nonzero_zero_phase_drive(self):
        data=fixture();before=deepcopy(data);out=bind(data)
        self.assertEqual(data,before)
        self.assertEqual(out["status"],"OFFLINE_CALIBRATION_BOUND_PLAN")
        self.assertEqual(out["evidence_class"],"SYNTHETIC_TEST_FIXTURE")
        self.assertFalse(out["hardware_submitted"])
        self.assertEqual(out["physical_acceptance"],"NOT_ASSESSED")
        self.assertEqual(out["calibration_sha256"],fingerprint(data))
        self.assertEqual(len(out["commands"]),9)
        self.assertEqual(out["route"]["phase_targets_pi_over_32"]["preparation"],0)
        self.assertTrue(all(F(c["volts"])==F(3,2) for c in out["commands"]))

    def test_device_context_and_validity_must_match(self):
        data=fixture()
        bad_contexts=[dict(data["context"],wavelength_nm="1551"),dict(data["context"],chip_temperature_c="26"),
                      dict(data["context"],assembly_revision="another"),dict(data["context"],fixed_trim_revision="changed")]
        for context in bad_contexts:
            with self.assertRaises(ValueError):bind(data,context=context)
        with self.assertRaises(ValueError):bind(data,device_id="other")
        for when in ("2026-10-23T23:59:59Z","2026-10-25T00:00:00Z","2026-10-24T12:00:00"):
            with self.assertRaises(ValueError):bind(data,at_utc=when)
        self.assertEqual(bind(data,at_utc="2026-10-24T17:30:00+05:30")["setting_id"],"phase_0_16")

    def test_stale_design_target_and_missing_setting_cannot_be_reused(self):
        for key in ("io_sha256","target_sha256"):
            data=fixture()
            if key=="io_sha256":data[key]="b"*64
            else:data["settings"][0][key]="b"*64
            with self.assertRaises(ValueError):bind(data)
        with self.assertRaises(ValueError):bind(fixture(),setting="phase_0_48")

    def test_malformed_joint_voltage_vectors_and_limits_fail(self):
        for value in (True,float("nan"),"NaN","Infinity","1/0","-1","3",None,"9"*129):
            data=fixture();data["settings"][0]["volts"]["core_0"]=value
            with self.assertRaises(ValueError):bind(data)
        data=fixture();del data["settings"][0]["volts"]["core_0"]
        with self.assertRaises(ValueError):bind(data)
        for bounds in (["2","1"],["-1","2"],["0"],None):
            data=fixture();data["voltage_limits"]["core_0"]=bounds
            with self.assertRaises(ValueError):bind(data)

    def test_ambiguous_actuators_rows_and_provenance_rejected(self):
        data=fixture();data["actuator_map"]["core_0"]=data["actuator_map"]["core_1"]
        with self.assertRaises(ValueError):bind(data)
        data=fixture();data["settings"]*=2
        with self.assertRaises(ValueError):bind(data)
        data=fixture();data["settings"][0]["evidence_sha256"]="fake"
        with self.assertRaises(ValueError):bind(data)
        data=fixture();data["evidence_class"]="certified"
        with self.assertRaises(ValueError):bind(data)

    def test_valid_numeric_strings_are_not_interpolated_or_relabelled(self):
        data=fixture();data["settings"][0]["volts"]["analysis"]="1.125"
        out=bind(data,context=dict(data["context"],wavelength_nm=1550,chip_temperature_c=25))
        command=next(c for c in out["commands"] if c["logical_channel"]=="analysis")
        self.assertEqual(command["volts"],"9/8")
        self.assertEqual(command["driver_channel"],data["actuator_map"]["analysis"])


if __name__=="__main__":unittest.main()
