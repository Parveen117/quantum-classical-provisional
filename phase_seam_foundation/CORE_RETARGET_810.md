# Re-target of the SiN core to 810 nm — v0.19

**Author: Monty.** First step of the route fixed in DUAL_RAIL.md: move the
heated SiN core from the 1550 nm / SNSPD design of v0.9 to v0.17 to the
810 nm signal that silicon single-photon diodes detect in the room band.
This note gives the exact scaled starting geometry, the two laws that carry
over exactly, the list of what does not scale, and a fail-closed readiness
grade. No mode solver has been run, no rule check, no fabrication, no
measurement: the grade of everything here is SCALED_NOMINAL.

[Code](core_retarget.py) · [Tests](../tests/test_phase_seam_core_retarget.py) ·
[Audit](../benchmarks/core_retarget_audit.py) · [Qualification](core_retarget/qualification.json) ·
[Declared re-target](core_retarget/retarget_810.json).

## 1. Statement R1: exact scaling and what breaks it

With wavelength-independent refractive indices, Maxwell's equations are
invariant under x -> s x, lambda -> s lambda. So a design scaled by
s = 810/1550 = 81/155 in every dimension keeps its modes, splitting ratios
and bend behaviour exactly. Two things break this here, and both are declared:

1. the film thickness is fixed by the platform at 300 nm and is not scaled, so
   t/lambda rises from 6/31 to 10/27 (×155/81): the film is relatively
   thicker, vertical higher-order modes and the single-mode width need a solver;
2. SiN and SiO2 indices disperse between 1550 and 810 nm.

The scaled numbers are the solver's input, not a design.

| Pinned 1550 nm dimension (µm) | Scaled 810 nm (exact) | ≈ | local minimum |
| --- | --- | --- | --- |
| strip width 1.2 | 486/775 µm | 627 nm | ≥ 350 nm: passes |
| bend radius 30 | 486/31 µm | 15.7 µm | solver |
| MMI 2×2 body 232 × 18 | 18792/155 × 1458/155 µm | 121.2 × 9.4 µm | solver, redesign |
| MMI taper 50 / 4.5 | 810/31 µm / 729/310 µm | 26.1 µm / 2.35 µm | solver |
| MMI gap 1.6 | 648/775 µm | 836 nm | ≥ 250 nm: passes |
| nitride 0.3, BOX 3.0 | unchanged | | fixed by platform |

The unit length 3164 µm, the 300 µm transitions and the 253 µm centreline
radius of the v0.11 layout are routing lengths, not optical designs; they are
re-laid out after the solver fixes width and bend radius.

## 2. Statement R2: the phase layer is wavelength-free

T1 (common-mode invariance), T2 (drift dichotomy), D1 (single-site Euler) and
D2 (fusion) are identities in the phase variables. Wavelength enters only the
map from volts and kelvin to phase. So the verification layer, the 106-setting
protocol, the codebook and the 31-channel calibration contract carry over to
810 nm unchanged (context `wavelength_nm` becomes 810); the calibration map,
every component design and every measured number do not.

## 3. Heater and drift laws (exact at equal dn/dT)

- Thermo-optic phase per heated length scales as 1/lambda: the same heater gives
  155/81 more phase per watt at 810 nm; a pi shift needs 81/155 of the power, or
  81/155 of the length at the same power. `heater_retarget()` returns exact
  multiples of declared 1550 nm inputs.
- Drift: 1 mm asymmetry × 1 K at the declared dn/dT 2.45e-5 is 784/775 grid
  steps (one π/32 step) at 1550 nm and 784/405 steps (≈1.94) at 810 nm. To keep
  the same phase error between calibrations the allowed temperature excursion at
  810 nm is 81/155 of the 1550 nm one. T1/T2 and the cut-and-correct rule of
  TEMPERATURE_SWEEP.md are unchanged.

## 4. What is not reused and what is open

- The pinned vendor cells (`mmi2x2.gds`, `heater.gds`, cspdk 3323b17) are 1550 nm
  cells. The MMI cannot be reused at 810 nm; it is redesigned or replaced by a
  directional coupler. The heater polygon may be reused subject to electrical rules.
- CORNERSTONE 300 nm SiN is the pinned 1550 nm candidate. Its support for
  810 nm operation is not established here: it is confirmed, or a visible/NIR
  SiN platform is selected. This is the long pole (MPW slot).
- Source, filters and detectors are the next notes (source spec, loss budget).
- The logical netlist is unchanged: 16 code paths, 6 exchange units, 4 bypasses,
  1 guard; the dual-rail route adds one coupler per fusion step.

## 5. Readiness grade (fail-closed)

`design_readiness(record)` grades a record SCALED_NOMINAL → SOLVER_VERIFIED
(named tool, single-mode TE at 810 nm, width margin, MMI split tolerance, bend
loss) → DRC_PASSED (foundry, passed, report hash) → FABRICATED (lot and die id)
→ MEASURED (bright-light transfer matrix, evidence class LAB_RECORDED). A missing,
failed or synthetic block stops the grade at the last satisfied stage and is
listed as a reason. The declared re-target grades SCALED_NOMINAL; negative
controls (multimode solver result, failed DRC, synthetic measurement, skipped
fabrication) stop where they should (14 tests).

## 6. Claims

- Claim A (room-temperature operation) is unchanged: it is graded by
  TEMPERATURE_SWEEP.md on recorded logs only, and still has no passing record.
- This note adds no physics claim. R1 and R2 are exact statements about the
  model; the geometry is a scaled nominal, not a design.
