"""Grid-4 optical preparation/readout compiler and offline calibration binding.

The binary export uses the existing phase engine to verify optical transfer.
It is neither a new simulator nor a hardware driver. Calibration records bind
whole configurations; no independent-heater fit or unmeasured voltage is used.
"""
from datetime import datetime, timezone
from fractions import Fraction
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import hashlib
import json

from native_relational_qc.modular_arithmetic import _mcx
from native_relational_qc.phase_backend import Phase64Circuit
from .model import ResourceLimit, index, integer
from .photonic_exchange import design_photonic_exchange

CHANNELS = tuple(f"core_{i}" for i in range(6)) + ("preparation", "analysis", "guard")
MAX_EXPORT_GATES = 10000


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _route(setting):
    coherence = setting["kind"] == "cross_block_coherence"
    guard = setting["kind"] == "deliberate_guard_coupling"
    core_step = setting.get("phase_steps_pi_over_32", 0)
    active_guard = guard and setting["injection_configuration"] == "inserted_active"
    phases = {channel: (-core_step) % 64 for channel in CHANNELS[:6]}
    phases.update(preparation=0,
                  analysis=(-setting["analyzer_relative_phase_steps"]) % 64 if coherence else 0,
                  guard=(-setting["extra_test_phase_steps_pi_over_32"]) % 64 if active_guard else 0)
    return dict(setting_id=setting["id"], kind=setting["kind"],
                input_path=setting["input_paths"][0] if coherence else setting["input_path"],
                preparation_ports=setting["input_paths"] if coherence else None,
                analysis_ports=setting["analysis_paths"] if coherence else None,
                core_angle_steps=core_step, phase_targets_pi_over_32=phases,
                guard_ports=setting["extra_test_coupler_ports"] if active_guard else None,
                guard_configuration="inserted_active" if active_guard else "physically_bypassed_or_removed",
                plus_detector=setting["analysis_paths"][0] if coherence else None,
                minus_detector=setting["analysis_paths"][1] if coherence else None)


@lru_cache(maxsize=1)
def _build_design():
    layout = design_photonic_exchange()
    process = json.loads(Path(__file__).with_name("photonic_process_binding.json").read_text())
    return dict(schema="native-photonic-io-v1", author="Monty", status="DESIGN_ONLY",
                domain="grid=4, pair_sum=0, reference=0, two spectators zero",
                core_netlist_sha256=fingerprint(layout.netlist()),
                process_binding_sha256=fingerprint(process),
                stage_order=["source routing", "preparation", "exchange core", "guard test", "analysis", "detectors"],
                preparation="H on ordered ports, then phase on second port; physically bypassed for basis inputs",
                analysis="phase on second ordered port, then H; all other ports retain direct detection",
                routing="external phase-calibrated patching between settings; no fast switch network claimed",
                phase_convention="exp(i*k*pi/32), k modulo 64, relative to calibrated Hadamard ports",
                channels=list(CHANNELS), core_pairs=[list(p) for p in layout.pairs],
                resources=dict(core_balanced_couplers=12,preparation_balanced_couplers=1,
                               analysis_balanced_couplers=1,guard_test_balanced_couplers=2,
                               installed_balanced_couplers=16,logical_variable_phases=9,
                               signal_and_guard_detectors=17,herald_detectors=1,
                               extra_port_trims_and_stabilization_actuators=None),
                settings=[_route(s) for s in layout.experiment_plan()["settings"]],
                measurement_status="NOT_RUN", fabricated=False,
                geometry="PDK candidate binding is separate; no placed/routed GDS or DRC result")


def io_design():
    """Return isolated logical routes; patching occurs between physical runs.

    The process binding is read once per interpreter; restart after changing
    it. Returned data cannot mutate the cached design or later calibrations.
    """
    return deepcopy(_build_design())


def _setting(setting_id, design=None):
    if type(setting_id) is not str: raise TypeError("setting ID must be a string")
    rows = (io_design() if design is None else design)["settings"]
    for row in rows:
        if row["setting_id"] == setting_id: return row
    raise ValueError("unknown protocol setting")


def _two_path(circuit, ports, word):
    """Exact two-level export: five label bits, flag 5, clean ladder 6/7.

    Affine X/CX maps ordered p,q to 0,2**pivot. A four-bit equality flag
    restricts H/phase to this pair. Uncompute restores every workspace bit.
    These binary gates are verification only, not an optical propagation path.
    """
    p, q = ports
    index(p,17,"optical path"); index(q,17,"optical path")
    if p == q: raise ValueError("distinct optical ports required")
    pivot = ((p ^ q) & -(p ^ q)).bit_length()-1
    mapping = [("x",(b,)) for b in range(5) if (p >> b) & 1]
    mapping += [("cx",(pivot,b)) for b in range(5) if b != pivot and ((p ^ q) >> b) & 1]
    controls = tuple(b for b in range(5) if b != pivot)
    prefix = mapping + [("x",(b,)) for b in controls] + _mcx(controls,5,(6,7))
    for gate, bits in prefix: circuit.add(gate,*bits)
    for kind, steps in word:
        if kind == "h": circuit.add("ch",5,pivot)
        elif kind == "phase":
            integer(steps,"phase steps")
            k = steps % 64
            gate, count = ("cp64",k) if k <= 32 else ("cp64dg",64-k)
            for _ in range(count): circuit.add(gate,5,pivot)
        else: raise ValueError("unsupported two-path operation")
    for gate, bits in reversed(prefix): circuit.add(gate,*bits)


def verification_circuit(setting_id, *, max_gates=MAX_EXPORT_GATES):
    """Export all stages of one protocol setting to the existing calculator."""
    integer(max_gates,"verification gate cap")
    if not 1 <= max_gates <= MAX_EXPORT_GATES: raise ValueError("invalid gate cap")
    design = io_design(); row = _setting(setting_id,design)
    c = Phase64Circuit(8)
    for bit in range(5):
        if (row["input_path"] >> bit) & 1: c.add("x",bit)
    phases = row["phase_targets_pi_over_32"]
    if row["preparation_ports"] is not None:
        _two_path(c,row["preparation_ports"],(("h",0),("phase",phases["preparation"])))
    for i, ports in enumerate(design["core_pairs"]):
        _two_path(c,ports,(("h",0),("phase",phases[f"core_{i}"]),("h",0)))
    if row["guard_ports"] is not None:
        _two_path(c,row["guard_ports"],(("h",0),("phase",phases["guard"]),("h",0)))
    if row["analysis_ports"] is not None:
        _two_path(c,row["analysis_ports"],(("phase",phases["analysis"]),("h",0)))
    if len(c.operations) > max_gates: raise ResourceLimit("photonic verification gate cap; no circuit returned")
    return c


def calibration_template():
    """No measured values or pretend zero-voltage defaults."""
    return dict(schema="native-photonic-calibration-v1",status="UNMEASURED_TEMPLATE",
                evidence_class=None,device_id=None,calibration_id=None,
                io_sha256=fingerprint(io_design()),valid_from_utc=None,valid_until_utc=None,
                context=dict(wavelength_nm=None,chip_temperature_c=None,
                             assembly_revision=None,fixed_trim_revision=None),
                actuator_map={ch:None for ch in CHANNELS},
                voltage_limits={ch:None for ch in CHANNELS},settings=[],
                row_contract="setting_id, target_sha256, volts for all nine logical channels, evidence_sha256",
                scope="full-configuration lookup; no interpolation or independent-heater assumption")


def _text(value, name):
    if type(value) is not str or not value.strip() or len(value) > 256:
        raise ValueError(f"{name} needs a nonempty bounded string")
    return value


def _hash(value, name):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"invalid {name} SHA256")
    return value


def _number(value):
    if type(value) not in (int,str) or (type(value) is str and len(value)>128):
        raise ValueError("finite rational/decimal string required")
    try: result = Fraction(value)
    except (ValueError,ZeroDivisionError): raise ValueError("finite rational/decimal string required") from None
    if max(result.numerator.bit_length(),result.denominator.bit_length()) > 1024:
        raise ValueError("numeric field exceeds bit cap")
    return result


def _context(value):
    keys = {"wavelength_nm","chip_temperature_c","assembly_revision","fixed_trim_revision"}
    if type(value) is not dict or set(value) != keys: raise ValueError("complete calibration context required")
    out = {k:_number(value[k]) for k in ("wavelength_nm","chip_temperature_c")}
    if out["wavelength_nm"] <= 0 or out["chip_temperature_c"] <= Fraction(-27315,100):
        raise ValueError("invalid wavelength/temperature")
    out.update({k:_text(value[k],k) for k in ("assembly_revision","fixed_trim_revision")})
    return out


def _utc(value):
    _text(value,"timestamp")
    try: result = datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError: raise ValueError("ISO timestamp required") from None
    if result.tzinfo is None: raise ValueError("timezone-aware timestamp required")
    return result.astimezone(timezone.utc)


def compile_drive_plan(setting_id, calibration, *, device_id, context, at_utc):
    """Bind recorded joint voltages to a route. Returns an OFFLINE plan only.

    Evidence hashes identify supplied records; they do not authenticate the
    measurements or establish fidelity. No instrument/network calls exist.
    """
    design = io_design(); route = _setting(setting_id,design)
    if type(calibration) is not dict or calibration.get("schema") != "native-photonic-calibration-v1":
        raise ValueError("calibration schema required")
    if calibration.get("status") != "RECORDED": raise ValueError("no recorded calibration")
    evidence = calibration.get("evidence_class")
    if evidence not in ("LAB_RECORDED","SYNTHETIC_TEST_FIXTURE"): raise ValueError("explicit evidence class required")
    if _text(device_id,"device ID") != _text(calibration.get("device_id"),"calibration device"):
        raise ValueError("calibration belongs to another device")
    calibration_id = _text(calibration.get("calibration_id"),"calibration ID")
    if calibration.get("io_sha256") != fingerprint(design): raise ValueError("stale I/O design binding")
    if _context(context) != _context(calibration.get("context")): raise ValueError("calibration context mismatch")
    start,end,now = (_utc(calibration.get("valid_from_utc")),_utc(calibration.get("valid_until_utc")),_utc(at_utc))
    if not start <= now < end: raise ValueError("outside declared calibration validity interval")
    channels = set(CHANNELS)
    mapping,limits = calibration.get("actuator_map"),calibration.get("voltage_limits")
    if type(mapping) is not dict or set(mapping) != channels: raise ValueError("complete actuator mapping required")
    if len({_text(v,"driver channel") for v in mapping.values()}) != len(channels):
        raise ValueError("driver channels must be distinct")
    if type(limits) is not dict or set(limits) != channels: raise ValueError("complete voltage bounds required")
    bounds = {}
    for ch,pair in limits.items():
        if type(pair) not in (list,tuple) or len(pair) != 2: raise ValueError("voltage bounds need two values")
        low,high = map(_number,pair)
        if not 0 <= low <= high: raise ValueError("invalid heater voltage bounds")
        bounds[ch] = low,high
    rows = calibration.get("settings")
    if type(rows) is not list or not 1 <= len(rows) <= 106: raise ValueError("bounded recorded setting list required")
    seen = set(); chosen = None
    for row in rows:
        if type(row) is not dict: raise ValueError("invalid calibration row")
        canonical = _setting(row.get("setting_id"),design); sid = canonical["setting_id"]
        if sid in seen: raise ValueError("duplicate calibration setting")
        seen.add(sid)
        if row.get("target_sha256") != fingerprint(canonical): raise ValueError("route/phase target mismatch")
        evidence_hash = _hash(row.get("evidence_sha256"),"evidence")
        volts = row.get("volts")
        if type(volts) is not dict or set(volts) != channels: raise ValueError("complete joint voltage vector required")
        values = {ch:_number(v) for ch,v in volts.items()}
        if any(not bounds[ch][0] <= v <= bounds[ch][1] for ch,v in values.items()):
            raise ValueError("voltage outside supplied device limits")
        if sid == setting_id: chosen = values,evidence_hash
    if chosen is None: raise ValueError("requested setting has no joint calibration")
    values,evidence_hash = chosen
    return dict(status="OFFLINE_CALIBRATION_BOUND_PLAN",evidence_class=evidence,
                device_id=device_id,calibration_id=calibration_id,io_sha256=fingerprint(design),
                calibration_sha256=fingerprint(calibration),target_sha256=fingerprint(route),
                evidence_sha256=evidence_hash,setting_id=setting_id,route=route,
                commands=[dict(logical_channel=ch,driver_channel=mapping[ch],volts=str(values[ch])) for ch in CHANNELS],
                physical_acceptance="NOT_ASSESSED",hardware_submitted=False,
                boundary="lookup and provenance consistency only; source/detector/loss/coherence qualification remains separate")
