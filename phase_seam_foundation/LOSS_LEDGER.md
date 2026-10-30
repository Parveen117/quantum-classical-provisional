# Loss as a retained ledger — v0.23

**Author: Monty.** Reply to the question "hardware loss ya detector ke liye
repo mein native solution hoga": yes. The repo's rule for a quantity that
leaves the observed sector is not an efficiency number, it is a ledger
declared in advance. Three pinned places say so (Publications bebf4cf):

- UGD-A0: strict carry addition is not associative, but the total seam charge
  q = s + ℓ is conserved by every grouping; deleting the ledger changes charge.
- EMK-G3 (helical sheet memory): a flat lift carries monodromy; visible return
  (α ≡ 0 mod K) is weaker than lifted return (α = β = q = 0); a non-faithful
  projection that drops the sheet sector maps an open lift to a closed image.
- LTB-1 (thermodynamic bridge): a ledger fixed before the data separates
  protocols; one set after the data is identically zero.

Here the ledger is photon number. v0.21 proved (L1) that detector-side loss
fakes the fusion herald with fraction (1 − η_d)/(2 − η_d) and v0.22 turned
that into a fidelity bound (1/(2 − η_d))^(N−2). That bound was the
non-faithful projection: it dropped the ledger. This note restores it.

[Code](loss_ledger.py) · [Tests](../tests/test_phase_seam_loss_ledger.py) ·
[Audit](../benchmarks/loss_ledger_audit.py) · [Qualification](ledger/qualification.json).

## 1. Theorem L2 (engine-checked at η_d = 1, 1/2, cos²(π/8), cos²(3π/8))

Lossy fusion as in L1: two Bell pairs, balanced coupler, loss beam splitters
of transmission η_d = cos²(kπ/32) on both detected modes, 10 modes, 4 photons.
Classify every outcome by (clicks, lost, photons per site A′, C, B′).

- **L2a, charge identity.** clicks + lost + register photons = 4 on every outcome
  (the UGD-A0 identity q(x ⊕ y) = q(x) + q(y) with photons as charge).
- **L2b, the false herald is visible in the ledger.** One click with one lost photon
  occurs only with site occupations (1, 0, 1): the middle site is empty. One click
  with nothing lost occurs only with (1, 1, 1). So the readout rule **exactly one
  click per site**, declared in advance, rejects every false herald. Zero clicks with
  one lost photon is a genuine fusion whose herald was missed: a rate loss.
- **L2c, witness after readout.** Conditioned on one click and one photon per site,
  the heralded phases are ζ⁴⁸ and ζ¹⁶ as in D2 and the corrected ⟨XXX⟩ is exactly 1,
  for every η_d. Control: lossless (k = 0) has no rejected class and the same witness.

At η_d = 1/2 the classes are: accepted 1/4, rejected false heralds 1/8, missed
genuine 1/4, no click and nothing lost 1/4 (failure, (1, 2, 1)), two photons lost
1/16, two clicks 1/16.

**Consequence.** Loss costs rate, not fidelity: a chain of F fusions keeps witness 1
and accepts the fraction (1/(2 − η_d))ᶠ of its heralds (at 3/5 and six fusions,
15625/117649). The v0.22 sentence "detector-side efficiency gates the register
size" is withdrawn; FUSION_NETWORK.md §4 now points here. What the ledger cannot
remove are ledger violations: a click with no photon (dark count) and a photon
with no site (multi-pair). Distinguishability is not a ledger quantity; it enters
through the recorded visibility.

## 2. Dark counts under the same rule (exact, η_d = 1/2)

A dark click on a zero-click outcome fakes a herald. Of the zero-click weight:
1/4 is a genuine fusion whose herald was lost, so the dark click yields a
correct accepted state; 5/16 is rejected by the per-site rule; and the failure
class (1, 2, 1) always has its two C photons in different modes, so even a
threshold readout sees two clicks at site C and rejects it. Under ledger readout
the herald dark count produces no wrong accepted state at all. Dark counts at the
readout itself remain a declared bound in the grade.

## 3. The loss channel is square-sourced

Tracing the loss beam splitter over its environment mode gives the single-photon
amplitude-damping channel with Kraus operators K₀ = diag(1, c), K₁ = s|0⟩⟨1|,
c² = η_d. K₀†K₀ + K₁†K₁ = 1 exactly in Q(ζ₆₄) on the native grid: completely
positive and trace preserving because its generators are cut squares, the same
reason the thermo paper's dissipator is physical. No √2 is chosen here; the
balanced coupler is the exchange unit at k = 8 on the grid, and every transmission
used in a theorem is a grid point cos²(kπ/32), k = 0..16. A declared physical
transmission is placed at its nearest grid point with exact residual bounds
(3/5 → k = 7, 1/2 → 8, 9/10 → 3, 243/4000 → 14); the grid is the exact sector,
not a quantisation of physical loss.

## 4. Grade (fail-closed)

`ledger_grade(record)`: LEDGER_DECLARED → POSTSELECTION_RECORDED (LAB_RECORDED
rule "exactly one click per site" with accepted fraction) → DARK_COUNTS_BOUNDED
(LAB_RECORDED dark probability per window at or below the declared bound) →
LEDGER_QUALIFIED (LAB_RECORDED witness after readout at or above the source's
recorded visibility: loss lowered nothing). Negative controls: "any click" rule,
dark rate above bound, witness below visibility, synthetic witness (10 tests).

## 5. Claims

Claim A unchanged, no passing record. L2 is an exact statement of the model;
the helix and thermodynamic correspondences are structural (ledger declared in
advance, visible versus lifted return), not identifications of photon number
with any thermodynamic coordinate.
