# Temperature-sweep evidence contract — v0.17

**Author: Monty.** This note fixes what a temperature claim about the heated
photonic core can mean, proves the part that follows from the existing ideal
component algebra, and supplies an unrun sweep protocol with a fail-closed
verdict that grades a recorded log into the claims it supports. No heat
solve, material fit, detector datasheet or lab result is reported.

[Code](temperature_sweep.py) · [Tests](../tests/test_phase_seam_temperature_sweep.py) ·
[Audit](../benchmarks/temperature_sweep_audit.py) · [Qualification](temperature/qualification.json) ·
[Sweep plans](temperature/).

## 1. Three different claims

| Claim | What it asserts | How it is decided |
| --- | --- | --- |
| Room-temperature operation | No subsystem (chip, source, detector) is cooled below the declared room band floor during the recorded run | Subsystem temperature log, verdict `thermal_class` |
| Temperature-independent logical transfer | At every point of a declared sweep, the 106-setting protocol agrees with the exact calculator prediction within a declared total-variation tolerance after per-temperature calibration | Sweep log, verdict `logic_class` |
| Temperature-independent physics | The uncalibrated device gives the same transfer at every temperature | Only the stronger class `TEMPERATURE_INSENSITIVE_WITHOUT_CALIBRATION`; never asserted for the material |

The current v0.9 selection (1550 nm, SNSPD) cannot support the first claim:
the verdict assigns `CRYOGENIC` to any detector log near 4 K or below. The
module lists two alternative routes as declared engineering context.
InGaAs single-photon avalanche diodes at 1550 nm are thermoelectrically
cooled and would be graded `CRYOGEN_FREE`. Silicon avalanche diodes operate
inside the room band but need a signal near 810 nm, which changes the SPDC
source, the SiN cross-section and MMI targets and every calibration. Their
temperature ranges in `DETECTOR_OPTIONS` are vendor-literature context used
to state which class a recorded log in that range would receive; they are
not measurements of any unit.

## 2. Theorem T1 (common-mode heating is exactly invisible)

Let the unit word be the v0.12 component product with phases
`(l, u, b, a)` and bypass reference phase `rho`. Adding one real shift `s` to
`l`, `u` and `rho` multiplies the unit matrix and the reference amplitude by
the same global factor `exp(i s)`, so every one of the 24 basis, local and
reference-assisted probabilities is unchanged, for every `theta` and every
`s`. Uniform heating of symmetric, equal-length arms and reference path is
this direction; it is the direction `(1,1,0,0,1)` already identified as the
Jacobian kernel in v0.12, now shown invariant to all orders.

`common_mode_global_phase` checks the matrix identity
`U(l+s,u+s,b,a) = zeta^s U(l,u,b,a)` exactly at all 65 sampled angles, and
`common_mode_invariance` checks the 24 probabilities at 17 of them (exact
field arithmetic makes the probability check slow, about one second per
family and angle). The input and output
trims are relative phases between the two paths, so uniform heating leaves
them unchanged by the symmetric routing of v0.11; an asymmetric package or
gradient does change them, and that is a differential drift below.

## 3. Theorem T2 (every phase-only drift is kernel or correctable)

At every interior angle (`theta` not 0 or pi) the reference-assisted Jacobian
has exact rank four with kernel spanned by the common mode (v0.12). Hence a
phase-only drift `delta` decomposes uniquely as common mode plus a complement
`(delta_l - delta_rho, delta_u - delta_rho, delta_b, delta_a, 0)`; the common
part changes nothing (T1) and the complement is first-order visible to the
reference family. Setting the heaters by minus the complement returns the
unit exactly to its ideal transfer, since the remaining shift is common mode.
`drift_dichotomy` returns the split, the per-family visibility and the exact
correction, and verifies the corrected response is identical to the ideal.

Two negative controls follow from the same table. A common phase of the unit
alone, `(1,1,0,0,0)`, is invisible to basis powers and to all 16 local
coherent probabilities and is seen only against the bypass reference; a
trim drift `(0,0,1,0,0)` is invisible to basis powers. A temperature test
that records only output powers therefore has no power against these
drifts, whatever its temperature span.

Nothing in T1 or T2 covers splitting-ratio, loss, polarization, source
spectrum or detector efficiency changes with temperature. They are outside
the phase-only model and must be measured; the protocol records them.

## 4. Declared thermo-optic scale

`thermo_optic_drift` converts declared inputs exactly:
`phi/pi = 2 * dL * (dn/dT) * dT / lambda`. With the declared SiN value
`dn/dT = 2.45e-5 /K`, a 1 mm differential path heated by 1 K at 1550 nm gives
`phi/pi = 49/1550`, which is 784/775 of one pi/32 step: about one grid step
per kelvin per millimetre of asymmetry. At 810 nm the same asymmetry gives
155/81 times more phase. The audit writes the table for 10 um, 100 um and
1 mm asymmetries at 1, 5, 20 and 50 K. The coefficient is a declared input
for scale, not a property measured on this core.

## 5. Two-photon check at one unit

`hom_coincidence` evaluates, in the existing field, the coincidence
probability for two photons entering the two ports of one unit: `cos^2 theta`
for indistinguishable photons (`|perm U|^2`) and `|U00 U11|^2 + |U01 U10|^2`
for distinguishable ones. At quadrature the ideal values are 0 and 1/2. The
port trims cancel in both. This is the source indistinguishability check of
the sweep; the v0.9 computation uses one photon and has no two-photon gate.
The identity is checked at all 65 sampled angles.

## 6. Protocol and verdict

`sweep_protocol` emits, for each declared chip temperature: stabilization
with subsystem logs; a fresh 31-channel bright-light calibration bound to
the unchanged GDS and I/O identity with `chip_temperature_c` in its context;
the 106-setting protocol under that calibration; the same protocol under
the reference-temperature calibration (the uncalibrated control, which
measures what the correction absorbs); a deliberate miscalibration control
of +8 steps on one arm (power); the two-photon point; and the temperature
log. The plan carries no counts or voltages and its evidence class is null.

`temperature_claim_verdict` grades a record. It requires
`evidence_class = LAB_RECORDED`, three subsystem logs, a declared tolerance in
(0,1), at least three points spanning at least 20 K, every calibrated
total-variation upper bound within tolerance and every miscalibration
lower bound above it. Missing power yields `TEST_WITHOUT_POWER`; a failed
calibrated point yields `TEMPERATURE_DEPENDENT`; a sweep passing without
recalibration yields the stronger class. Heating a subsystem above the room
band is recorded, not penalized; cooling any subsystem below the floor
removes the room-temperature class. Synthetic or partial logs receive no
claim. Three statements are never allowed: a quantum computer at room
temperature (the exchange core is not a computer), temperature independence
of the physics, and any claim from a simulated log.

## 7. Reproduction

```bash
python benchmarks/temperature_sweep_audit.py
```

The audit runs the 29 new tests, checks the T1 matrix identity at all 65 angles and the probability invariance at 17, tabulates T2
for seven drift directions at three interior angles, writes the two drift
tables, the HOM values and three sweep plans (silicon-diode 810 nm, InGaAs
1550 nm, SNSPD 1550 nm), and records the verdict of an empty record.

Closed: the meaning of each temperature claim, the exact common-mode
invariance, the drift dichotomy with exact correction, a declared drift
scale, the two-photon prediction, an unrun plan and a fail-closed grader.

Open: a fabricated and packaged core, any recorded temperature log, the
two-photon source, the room-temperature detector route with its re-targeted
wavelength design, and every effect outside the phase-only model.
