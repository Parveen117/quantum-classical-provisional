# Loss budget for the 810 nm dual-rail route — v0.21

**Author: Monty.** Step 3 of the route (DUAL_RAIL.md → CORE_RETARGET_810.md →
SOURCE_SPEC_810.md). Loss was explicitly not modelled in v0.18; this note
models it. The budget itself is declared, stage by stage, and nothing in it
is measured. What is exact is what loss does to the heralded fusion step,
proved in the boson engine (Theorem L1), and the survival and chain laws
that follow.

[Code](loss_budget.py) · [Tests](../tests/test_phase_seam_loss_budget.py) ·
[Audit](../benchmarks/loss_budget_audit.py) · [Qualification](loss/qualification.json) ·
[Plan for 2056 sites](loss/plan_2056.json).

## 1. Declared chain (per site photon, source to click)

| Stage | Transmission (declared) | ≈ dB |
| --- | --- | --- |
| source fibre coupling | 1/2 | 3.0 |
| bandpass filter 810 nm | 9/10 | 0.46 |
| fibre to chip facet | 1/2 | 3.0 |
| on-chip propagation and couplers | 9/10 | 0.46 |
| chip to fibre facet | 1/2 | 3.0 |
| si_spad_810 detection | 3/5 | 2.2 |
| **end to end η** | **243/4000 ≈ 0.061** | **12.2** |

The product is exact; the dB column is display. All N site photons are
detected with probability ηᴺ (independent loss): 4 sites 3.5 × 10⁻⁵, which
is the rate problem the fusion-network note addresses with multiplexing and
heralding, not by lowering this bound. Facet loss dominates: two of the three
3 dB entries are fibre-chip interfaces, so edge-coupler design at 810 nm is
the first lever, detector efficiency the second.

## 2. Theorem L1: loss fakes the fusion herald by an exact fraction

Type-I fusion succeeds when exactly one photon is detected on the coupler's
two output detectors (D2, success 1/2 lossless). With detector-side
efficiency η_d on those two modes and two photons entering:

- P(exactly one click) = η_d(2 − η_d)/2;
- of which genuine one-photon events are η_d/2, and false heralds (two photons
  went to the detectors, one was lost) are η_d(1 − η_d)/2;
- genuine fraction **1/(2 − η_d)**, false-herald fraction **(1 − η_d)/(2 − η_d)**.

Engine check: fusion coupler followed by loss beam splitters of transmission
cos²(kπ/32) on both detected modes, 10 modes, 4 photons, every occupation
classified by (clicks, lost). The closed form holds exactly at η_d = 1, 1/2,
cos²(π/8) = (2 + √2)/4 and cos²(3π/8); total probability 1 in every case.
At the declared η_d = 3/5: one click 21/50, genuine 3/10, genuine fraction
5/7, false heralds 2/7.

Consequences, exact: a chain of F independent fusions has all heralds genuine
with probability (1/(2 − η_d))ᶠ (two fusions at 3/5: 25/49). Loss on the three
surviving rails is a missing readout click, never a wrong outcome, so it costs
rate and not fidelity. A false herald is a fidelity error and is suppressed
only by lower detector-side loss or photon-number resolution; both are design
inputs for the next note.

## 3. Grade (fail-closed)

`loss_grade(record)`: BUDGET_DECLARED → STAGES_RECORDED (every declared stage
with a LAB_RECORDED transmission) → END_TO_END_RECORDED (LAB_RECORDED end-to-end
efficiency, Klyshko-derived) → BUDGET_CONSISTENT (end-to-end within a declared
tolerance of the stage product; an end-to-end above the product fails too).
Negative controls: missing stage, synthetic stage, end-to-end too good, too
bad, modelled instead of recorded (9 tests).

## 4. Claims

Claim A unchanged, no passing record. L1 is an exact statement about the
model; the budget is a proposal and the dominant terms are named so that the
bench measures them first.
