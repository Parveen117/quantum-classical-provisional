# Fusion network for the 810 nm dual-rail route — v0.22

**Author: Monty.** Step 4 and last of the route notes (DUAL_RAIL.md →
CORE_RETARGET_810.md → SOURCE_SPEC_810.md → LOSS_BUDGET_810.md). It answers
how N heralded sites become one N-site register when the entangling step is
a type-I fusion of success 1/2 (D2) and the herald can be faked by loss (L1).
Everything exact is combinatorics of declared probabilities; no switch,
delay line or network exists.

[Code](fusion_network.py) · [Tests](../tests/test_phase_seam_fusion_network.py) ·
[Audit](../benchmarks/fusion_network_audit.py) · [Qualification](network/qualification.json) ·
[Plan for 2056 sites](network/plan_2056.json).

## 1. Multiplexing law

M heralded sources behind a binary switch tree (M a power of two, t per
stage): delivered probability (1 − (1 − p)ᴹ) t^{log₂ M}, exact. With the
source operating point p = 1/79 (SOURCE_SPEC_810.md) the best depth up to
256 branches is: t = 1 or 9/10 → 256 branches; t = 4/5 → 128; t = 1/2 → 1
(3 dB per switch stage: multiplexing never pays). So the switch loss decides
whether multiplexing exists at all; it is the second declared loss that the
bench must measure after the facets.

## 2. Theorem N1: Bell pairs do not grow a chain at success 1/2

Fusing a k-site resource onto the chain end adds k − 1 sites on success and
removes one on failure (the end site is measured out). The drift is s k − 1:

| Resource | s | drift | grows |
| --- | --- | --- | --- |
| Bell pair (k = 2) | 1/2 (proved) | 0 | no: a null random walk |
| 3-site GHZ (k = 3) | 1/2 (proved) | +1/2 | yes |
| Bell pair, boosted fusion | 3/4 (declared) | +1/2 | yes, at the price of an ancilla pair |

So the route builds 3-site GHZ resources first (one heralded fusion of two
Bell pairs, D2) and grows the chain with those. The smallest resource that
grows is k = ⌊1/s⌋ + 1.

## 3. Theorem N2: exact hitting probabilities and their limit

The chain length is an absorbing Markov chain on 0..N solved exactly over
rationals (up to 256 sites). From a fresh 3-site resource, with 3-site
resources and s = 1/2:

| target N | P(reach N before the chain dies) | expected attempts |
| --- | --- | --- |
| 4 | 6/7 | 2 |
| 5 | 5/6 | 8/3 |
| 8 | 7/9 | 64/9 |
| 16 | 94/123 | ≈ 19.04 |
| 32 | 2207/2889 | ≈ 43.5 |
| 256 | ≈ 0.7639320225 | ≈ 385.7 |

The limit is algebraic: the extinction probability from height 1 solves
q = q³/2 + 1/2, i.e. (q − 1)(q² + q − 1) = 0, so q = (√5 − 1)/2 and
P(reach any target) → 1 − q³ = 3 − √5 ≈ 0.7639. A chain start therefore
fails about 24 % of the time whatever N is, which is a restart cost, not a
scaling wall; attempts grow linearly (≈ 1.5 N). Control: Bell-pair growth
from 2 sites is the fair gambler's ruin, P = start/target (1/4 for 8 sites)
and dies with probability 1 as N grows.

Resources: a 3-site resource costs two Bell pairs and one heralded fusion
(expected four Bell pairs); an 8-site chain expects 274/9 ≈ 30 Bell pairs.

## 4. Fidelity bound from L1 (withdrawn in v0.23, see LOSS_LEDGER.md)

**Correction, v0.23.** Theorem L2 (LOSS_LEDGER.md) shows every false herald leaves the middle site empty, so the readout rule "exactly one click per site" rejects it and the witness after readout is 1 at every η_d. The bound below is the accepted fraction of heralds, a rate, not a fidelity; the sentence "detector-side efficiency gates the register size" is withdrawn. The original text is kept for the audit trail.

Every chain fusion can be a false herald with fraction (1 − η_d)/(2 − η_d).
With N − 2 chain fusions the bound on all heralds genuine is (1/(2 − η_d))^{N−2}:
at the declared η_d = 3/5 that is (5/7)^{N−2}, useless beyond a few sites.
This is the exact reason the detector-side efficiency (or photon-number
resolution) is the design number that gates the register size, ahead of the
source rate. Dark counts, multi-pair and distinguishability are not in this
bound; they enter through the recorded visibility (⟨XXX⟩ = V).

## 5. Architecture (declared)

N multiplexed heralded sources → Bell pairs → 3-site GHZ resources by one
heralded fusion → chain growth by fusing resources onto the end with feed-
forward of the heralded phase ζ⁴⁸ or ζ¹⁶ as a Z step on the site heater (D2)
→ fibre delay as the only photonic memory (its per-attempt transmission is
one more declared loss, not in the walk).

## 6. Grade (fail-closed)

`network_grade(record)`: NETWORK_DECLARED → FUSION_RECORDED (LAB_RECORDED
heralded ⟨XXX⟩ ≥ 1/2 from one fusion) → GROWTH_RECORDED (LAB_RECORDED chain
of ≥ 4 sites) → MULTIPLEXED_RECORDED (LAB_RECORDED delivered probability above
the bare source) → NETWORK_QUALIFIED (all network subsystems at or above the
room band floor). Negative controls: witness 2/5, synthetic witness, 3-site
chain, multiplexing below bare, detector at −40 °C (9 tests).

## 7. Claims

Claim A unchanged, no passing record. N1 and N2 are exact statements about
the declared model; success 3/4 for boosted fusion is a literature value and
is not proved here.
