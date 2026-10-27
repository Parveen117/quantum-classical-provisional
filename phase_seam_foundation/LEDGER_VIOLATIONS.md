# Ledger violations at readout: multi-pair and dark counts — v0.24

**v0.33 correction:** the multi-pair one-survivor event is 'accepted and right' for a single isolated site only. In a fused register it is accepted by the one-click rule and wrong: the conditioned state is a classical mixture with zero coherence (Theorem P1, [CLUSTER_FAULTS.md](CLUSTER_FAULTS.md)), and the per-pair wrong fraction is about 4x independent of loss. The register budgets below that credit that event as right are superseded for fused registers.

**Author: Monty.** LOSS_LEDGER.md (L2) made loss a rate under the readout rule
"exactly one click per site". This note treats the two things that rule
cannot remove, because they violate the photon ledger instead of respecting
it: a site holding two photons (multi-pair, charge above N at the source) and
a click with no photon (readout dark count). Both are exact; every number
below is a declared input or an exact consequence. It then wires the ledger
into the sweep verdict so a dual-rail run cannot claim a logical result
without recording its ledger.

[Code](ledger_violations.py) · [Tests](../tests/test_phase_seam_ledger_violations.py) ·
[Audit](../benchmarks/ledger_violations_audit.py) · [Qualification](violations/qualification.json).

## 1. Theorem V1: a doubly occupied site under the exchange unit

Two photons in one rail of a site, through the four-heater unit at native
angle θ = kπ/32 (engine, all 65 angles): both leave in one rail with
probability cos⁴θ + sin⁴θ, split with 2cos²θ sin²θ. The same-rail probability
is never below 1/2 (equal to 1/2 exactly at the balanced point k = 16, 3/4 at
k = 8, 1 at k = 0). So threshold readout accepts a multi-pair site as a
single click at least half the time; number-resolving readout rejects it
always. With site survival η the weights are: both survive η² (then the law
above), exactly one survives 2η(1 − η) (for a single-site preparation the
survivor carries the prepared state: accepted and right; in a fused register
this case is declared, not proved), none survives (the site is empty and
falls to the dark-count law).

## 2. Dark counts at readout (exact per site)

Two threshold detectors per site, dark probability d per mode per window,
photon detected with probability η: accept-right η(1 − d), accept-wrong
(1 − η)·2d(1 − d), everything else rejected. The wrong fraction is of order
2d(1 − η)/η: the detector's dark-to-efficiency ratio, not its efficiency alone.

## 3. Theorem V2: the witness law and the allowed budget

An accepted wrong site gives a random X outcome, so the corrected N-site
witness after readout is exactly (r/(r + w))ᴺ. A target witness V therefore
allows a per-site wrong fraction of at most 1 − V^{1/N}, bracketed exactly by
bisection: for V = 1/2, N = 3 allows ≈ 0.206, N = 8 ≈ 0.083, N = 64 ≈ 0.0108,
N = 2056 ≈ 3.4 × 10⁻⁴.

Declared operating point (x = 1/40, balanced angle, η = 243/4000 from
LOSS_BUDGET_810.md, d = 10⁻⁵ per mode):

| N | threshold readout: witness | number-resolving: witness | dominant |
| --- | --- | --- | --- |
| 3 | 0.9969 | 0.9991 | multi-pair / dark |
| 8 | 0.9919 | 0.9976 | |
| 64 | 0.937 | 0.981 | |
| 256 | 0.770 | 0.927 | |
| 2056 | 0.123 | 0.545 | |

With η = 1/2 and d = 10⁻⁶: N = 2056 gives 3.7 × 10⁻⁶ under threshold readout
and 0.996 under number resolution. So the statement withdrawn in v0.23 returns
in its correct form: **what gates the register size is the ledger, through
multi-pair under threshold readout (x η² (cos⁴ + sin⁴)) and the dark-to-
efficiency ratio, not loss itself.** Number-resolving readout (or x small
enough that x η²/2 ≪ 1/N) is the design input for large N; the source
operating point x and the readout type are now coupled design choices.

## 4. Dual-rail sweep verdict (fail-closed)

`dual_rail_sweep_verdict(record)` runs the v0.17 grader and then requires a
`ledger` block: readout rule "exactly one click per site", LAB_RECORDED
dark-count bound, LAB_RECORDED heralded g2 below 1/2, LAB_RECORDED source
visibility. Missing or synthetic fields set logic_class UNDETERMINED and
remove every logical claim; the thermal class is a separate ledger and is
untouched. Negative controls: no ledger, "any click" rule, g2 = 1/2,
synthetic visibility (9 tests).

## 5. Claims

Claim A unchanged, no passing record. V1 and V2 are exact statements of the
model at declared inputs; the table is a budget, not a measurement.
