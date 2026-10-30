# 810 nm heralded single-photon source — v0.20

**Author: Monty.** Step 2 of the route fixed in DUAL_RAIL.md and started in
CORE_RETARGET_810.md: the photon source for the room-temperature device.
Declared source: 405 nm continuous-wave pump, type-II periodically poled KTP,
degenerate pairs at 810 nm, the idler click heralds the signal photon,
silicon single-photon diodes. No source has been built or measured; every
rate, efficiency and bandwidth is a declared input. What is exact is the
photon statistics, and the grader says what a recorded bench may claim.

[Code](source_spec.py) · [Tests](../tests/test_phase_seam_source_spec.py) ·
[Audit](../benchmarks/source_spec_audit.py) · [Qualification](source/qualification.json) ·
[Declared spec](source/source_810.json).

## 1. Declared source

| Item | Declared | Status |
| --- | --- | --- |
| Pump | 405 nm CW, single longitudinal mode; linewidth and power at bench | declared |
| Crystal | ppKTP, type-II, collinear, degenerate; poling period from vendor; oven 25 to 60 °C | declared; heating recorded, never cooling |
| Pairs | 810 + 810 nm, orthogonal polarizations, split on a polarizer | energy conservation exact: 1/405 = 1/810 + 1/810 |
| Filtering | bandpass at 810 nm both arms, single-mode fibre | declared; width set by the purity law below |
| Detector | si_spad_810, room band 15 to 35 °C | from TEMPERATURE_SWEEP.md |
| Operating point | x = 1/40, heralded g2 target 1/20, HOM visibility target 9/10 | proposed, not measured |

## 2. Exact laws (two-mode squeezed vacuum, threshold detectors)

Pair number n is thermal: p(n) = (1 − x) xⁿ with x = tanh² r in [0, 1),
mean pairs x/(1 − x). A threshold herald with efficiency η clicks on n pairs
with probability 1 − (1 − η)ⁿ. Closed forms follow from the three sums
Σxⁿ, Σn xⁿ, Σn(n − 1)xⁿ and y = x(1 − η):

- **Heralded g2(0)** = ⟨n(n−1)⟩ P(click) / ⟨n⟩² exactly. Lossless herald: **g2 = 2x**, and
  P(n ≥ 2 | click) = x. Signal-arm loss cancels; herald loss raises g2
  (x = 1/40: g2 = 1/20 lossless, 748802/10233601 ≈ 0.073 at η = 1/2).
- **Single-photon regime** means recorded g2 below 1/2. At x = 1/4 the lossless
  value is exactly 1/2 and the grader refuses it.
- **Klyshko efficiency** C/S_i tends to η_s as x → 0 and overestimates it at finite x
  by an exact amount (x = 1/40, η_s = 1/2: 2461/4819 ≈ 0.511, excess 103/9638).
- **Spectral purity** of a Gaussian joint spectral amplitude with pump width a
  (sum frequency) and phase-matching width b (difference frequency):
  Schmidt number K = (a² + b²)/(2ab), purity 1/K; purity 1 exactly at a = b.
  Unfiltered (a : b = 1 : 10) purity is 20/101; filtering b toward a is the
  only lever (a : b = 2 : 3 gives 12/13).
- **HOM visibility bound**: two identical heralded sources in the single-pair
  lossless limit give V = purity, so V ≤ purity. V is measured, never predicted;
  the recorded V is the number dual_rail.visibility_law turns into ⟨XXX⟩.
- **All-herald probability** for N sources each heralding with probability p is pⁿ
  (p = 1/79 at x = 1/40, η = 1/2: 1/6241 for two, 1/38950081 for four). This is why
  step 4 is a multiplexed fusion network and not N bare sources.

## 3. Operating table (herald efficiency 1/2)

| x | P(click) | g2 heralded | P(multi-pair \| click) | regime |
| --- | --- | --- | --- | --- |
| 1/100 | 1/199 | ≈ 0.030 | 299/20000 | single photon |
| 1/40 | 1/79 | ≈ 0.073 | 119/3200 | single photon (proposed) |
| 1/20 | 1/39 | ≈ 0.143 | 59/800 | single photon |
| 1/10 | 1/19 | ≈ 0.273 | 29/200 | single photon, visibility suffers |
| 1/4 | 1/7 | ≈ 0.601 | 11/32 | refused |

Brightness (pairs per second per mW per nm) is a measured property of the
crystal and coupling and is not derived here; x at a given pump power is read
off the recorded singles and coincidences through the Klyshko law.

## 4. Grade (fail-closed)

`source_grade(record)`: SPEC_DECLARED → PAIRS_RECORDED (LAB_RECORDED singles,
coincidence, Klyshko) → HERALDED_SINGLE_PHOTON (recorded g2 < 1/2) →
INDISTINGUISHABLE (recorded HOM V ≥ 1/2, carried forward) → SOURCE_QUALIFIED
(every source subsystem logged at or above the room band floor). Negative
controls: g2 = 1/2, synthetic g2, V = 2/5, detector at −40 °C, missing
temperatures, simulated pairs (11 tests).

## 5. Claims

Claim A is unchanged and still has no passing record. This note adds no
physics claim: the laws are exact consequences of the declared source model,
and the operating point is a proposal.
