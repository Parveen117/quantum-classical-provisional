# Optical preparation, readout and calibration binding

Author: Monty. Version 0.10. Status: complete logical experiment routes,
exact calculator export and offline calibration interface. No physical
experiment, fabricated chip, placed/routed mask or measured calibration.

This note records the v0.10 interface. The subsequent
[v0.11 layout](PHOTONIC_LAYOUT.md) adds a core GDS subassembly and an explicit
31-channel physical profile; the original nine-channel logical profile is
retained for its earlier scope.

The [v0.9 exchange core](PHOTONIC_EXCHANGE.md) now has explicit input and
output operations for all 106 proposed settings. The adapter compiles the
whole experiment into the existing exact phase calculator, including the
coherent preparation, exchange, optional guard injection and analyzer.
"Whole experiment" means those ordered stages for the declared inputs;
the 106 settings are still not complete process tomography.

[I/O design](photonic_io_design.json) ·
[Unmeasured calibration template](photonic_calibration_template.json) ·
[Process candidate binding](photonic_process_binding.json) ·
[Implementation](photonic_io.py).

## 1. Ordered optical stages

The code remains restricted to grid 4, fixed pair sum and reference zero,
and two fixed spectator modes. Paths 0–15 encode data and pointer; path 16
is the optical guard. Ordered pairs matter for phase and detector labels.

| Stage | Basis settings | Coherence settings | Guard controls |
| --- | --- | --- | --- |
| Source routing | Inject the named path | Inject the first preparation port | Inject path 4 |
| Preparation | Physically bypass | Balanced H on (p,0), then relative phase on 0 | Physically bypass |
| Exchange core | Six MZIs at the named angle | Six MZIs at π | Six MZIs at zero |
| Guard test | Physically bypass/remove | Physically bypass/remove | Bypass for baseline; active half-transfer on (4,16) for injection |
| Analysis | Direct path readout | Phase −φ on path 0, then H on (r,0) | Direct path readout |
| Detection | All 17 outputs plus herald | All 17 outputs plus herald; r is plus, 0 is minus | All 17 outputs plus herald |

Here (p,r) is one of the six exchange pairs. The preparation and analysis
modules are external, phase-calibrated optical modules patched between
settings. This specifies their ports and transfer laws, not a fast switching
fabric or a fully integrated chip. Repatching requires phase calibration
and a corresponding assembly revision in the calibration context.

Every nonparticipating output remains connected to its detector. The analyzer
mixes its two selected paths only; it does not discard the other outputs.
Unexpected outputs, guard events and losses must still be counted using
the existing full-herald accounting interface.

The installed module inventory is 12 balanced couplers in the core, one
in preparation, one in analysis, and two in the bypassable guard MZI:
**16 balanced couplers in this logical bench assembly**. The nine logical
variable phases are six core arms, preparation, analysis and guard. Extra
port trims, polarization control and stabilization remain additional and
their actuator counts are not fixed. The complete apparatus still includes
source/filtering, patch routing, electronics, 18 detector channels in the
parallel configuration, cooling and time tagging.

## 2. Exact readout composition

Use the calibrated Hadamard convention
\(H=(1/\sqrt2)\begin{pmatrix}1&1\\1&-1\end{pmatrix}\).
For a coherent setting, the preparation gives
\[
|p\rangle\longmapsto (|p\rangle+|0\rangle)/\sqrt2.
\]
The completed core exchange maps this to
\((|r\rangle+|0\rangle)/\sqrt2\). The analyzer is
\[
A_\phi=H\operatorname{diag}(1,e^{-i\phi})
\]
on ordered ports (r,0), so the final amplitudes are
\[
\alpha_\phi=(1+e^{-i\phi})/2,\qquad
\beta_\phi=(1-e^{-i\phi})/2.
\]
Their squared magnitudes reproduce the earlier plus/minus predictions.
Checking these complex amplitudes also checks the analyzer phase sign;
population checks alone at symmetric analyzer angles can miss that error.

The machine interface uses phase units π/32, with actual arm phase
\(e^{ik\pi/32}\), k modulo 64. Thus the exchange angle θ requires arm
phase −θ. A target phase of zero does not imply zero drive voltage: bias,
port trims and thermal cross-talk can require nonzero drives.

## 3. Reuse of the existing calculator

`verification_circuit(setting_id)` returns a `Phase64Circuit`. Five binary
label bits represent the 17 optical paths; one equality flag and two clean
ladder bits give eight **verification wires**. They are not eight physical
qubits in the optical apparatus.

For any ordered optical pair (p,q), an invertible X/CX mapping sends p to
zero and q to one selected bit. The existing multi-control ladder computes
the condition that the other four bits are zero. Controlled H and exact
phase gates act only on that pair. Reversing the mapping and ladder restores
the workspace and fixes every spectator basis label. This permits direct
comparison of complete optical-setting amplitudes with the existing native
exchange coefficients, without adding an amplitude backend.

The binary decomposition is only a verification circuit. Its intermediate
binary labels need not remain in the optical code; it is not a proposed
physical propagation path. The optical design still uses its disjoint
couplers, phases and bypass routes.

```python
from native_relational_qc.phase_backend import prepare
from phase_seam_foundation.photonic_io import io_design, verification_circuit

design = io_design()
assert len(design["settings"]) == 106
state = prepare(verification_circuit("phase_0_0"))
assert state.amplitudes == {4: state.field(1)}  # plus detector for pair (1,4)
assert design["measurement_status"] == "NOT_RUN"
```

The adapter is fixed to this grid-4 experiment. Export has a 10,000-gate
cap, and existing phase-engine work/support caps remain available. The
process binding is cached once per interpreter; restart after editing it.
Returned I/O data are copied so caller edits cannot alter later targets.

## 4. A specific process candidate and an integration mismatch

The selected planning candidate is **CORNERSTONE 300 nm SiN, TE, nominal
1550 nm**. The [provider's platform page](https://cornerstone.sotonfab.co.uk/mpw/technology-platforms/)
lists a 300 nm nitride layer on 3 μm buried oxide. This is a provider nominal
stack, not a measurement of our device.

The binding pins [gdsfactory/cspdk commit
3323b17b4d75c852ed2372d7d13239408cca0eb1](https://github.com/gdsfactory/cspdk/tree/3323b17b4d75c852ed2372d7d13239408cca0eb1/cspdk/sin300)
and records Git blob identities for the inspected component, technology and
model files. Its C-band software defaults include 1.2 μm strip width,
30 μm bend radius, and a 2×2 MMI body of 232 μm by 18 μm with specified
tapers. These defaults provide a concrete starting reference; no mask is
generated or design-rule result claimed here.

There is an important interface mismatch: the pinned `mzi_nc` factory
defaults to a **1×2 input splitter**. The exchange needs a two-input unitary.
Our recipe explicitly selects `mmi2x2_nc` for both splitter and combiner,
with nominal arm-length difference zero. Heated arms, electrical ports,
phase trims, path matching and layout routing must still be added and checked.
The factory name alone does not provide an electrically tunable native gate.

The pinned `models.py` has no implemented heater transfer model. Therefore
its default optical models cannot supply a measured voltage-to-phase law.
No PDK package was executed and no restricted software was accessed.
Provider/run-specific design rules and the heated layout still need review.

## 5. Joint calibration lookup

The calibration interface accepts a **recorded voltage vector for the whole
setting**, with all nine logical channels included. It does not independently
fit each heater, interpolate between settings, extrapolate a voltage, or
substitute a theoretical target for a measurement. This design accommodates
thermal interaction between channels within a measured configuration.
It does not solve the calibration inverse problem or compensate future drift.

[Taballione et al.](https://arxiv.org/html/2203.01801v5) describe phase-voltage
characterization and cross-talk compensation in a physical SiN processor.
That motivates measuring the assembled system; their calibration, rates and
losses are not imported into this prototype.

`calibration_template()` leaves every voltage, device identity, validity
interval and context value unset. A populated JSON profile supplies:

- `status="RECORDED"` and an explicit `LAB_RECORDED` or
  `SYNTHETIC_TEST_FIXTURE` evidence class;
- device/calibration IDs and the canonical I/O fingerprint, which also
  binds the core and process-candidate manifest;
- an explicitly timezone-aware validity interval [start,end), wavelength,
  chip temperature, assembly revision and fixed-trim revision;
- nine distinct driver channel names and device-supplied voltage limits;
- one or more rows containing `setting_id`, `target_sha256`, a complete
  `volts` dictionary, and an `evidence_sha256` reference to the raw record.

Numeric calibration values are integers or finite rational/decimal strings,
such as `"1.125"`. A row's target fingerprint includes its route, bypass
configuration and phase targets. Reusing another setting's voltage row
therefore requires a separately recorded binding. A partial profile can
support its recorded settings without pretending the other settings were run.

`compile_drive_plan(setting_id, profile, device_id=..., context=...,
at_utc=...)` rejects stale design/route fingerprints, another device, changed
context, an expired interval, duplicate rows, missing channels and values
outside the supplied limits. On success it returns the exact recorded
voltage vector, driver mapping and provenance as an **offline plan**.
No hardware or network calls exist in this adapter.

These checks establish data consistency only. A supplied hash does not
authenticate a measurement, a declared validity interval does not prove
stability, and matching temperatures does not establish adequate sensor
precision. Fidelity, source purity, detector response, loss, phase residuals,
settling and tolerances require actual characterization. Bright-light
calibration and quantum qualification remain separate. Test voltages are
explicitly synthetic and are not saved as device calibration.

## 6. Qualification and remaining work

The combined audit passes **193 tests in 121.041 seconds**, with no failures,
errors or skips: 12 new I/O/calibration tests plus all 181 earlier targeted
checks. Full native/Shor suites and physical hardware jobs were not rerun.

The new tests compare all 106 complete setting circuits with their exact
complex targets, check spectator labels and workspace restoration, and
exercise device/context/expiry, missing-data, voltage-limit and stale-binding
failures. The generated route and calibration-template artifacts are hashed
by the combined register audit. Current test counts and timing are in
[register qualification](register_qualification.json).

Closed: explicit preparation/core/guard/analyzer composition, a concrete
process-candidate mapping, exact end-to-end verification, and an offline
interface for complete measured voltage vectors.

New choices: external phase-calibrated patch modules, the pinned CORNERSTONE
software candidate, and configuration-specific calibration lookup.

Open: a placed/routed heated mask and foundry checks, calibration acquisition
and inverse fitting, real source/detector/coherence data, and physical
acceptance. The earlier fixed-sector, destructive-readout and scaling limits
remain. This step does not derive a new probability law or build a physical
quantum computer.
