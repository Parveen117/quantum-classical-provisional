# Building the encoded site: fusion cost and storage — v0.27

**Author: Monty.** TREE_CODE.md priced a logical site in photons and showed
the gain in the chain walk. This note prices the build itself: the fusions
that make the tree and the storage rounds they take. The result is a
negative theorem and a design law: building sites in series with the
register is a second cliff of the M1 type, and the encoding pays only when
sites are built offline, retried until built and stored, and switched in.
Everything is exact or a labelled bound; nothing is measured.

[Code](tree_build.py) · [Tests](../tests/test_phase_seam_tree_build.py) ·
[Audit](../benchmarks/tree_build_audit.py) · [Qualification](build/qualification.json).

## 1. Stars are GHZ states

A star graph state (centre with leaves) is a GHZ state up to local
Hadamards, so every star is grown exactly as in FUSION_NETWORK.md: from one
3-site GHZ by fusing 3-site resources at success 1/2. A 4-photon star reaches
with 6/7 and costs 12 Bell pairs in expectation; an 8-photon star 292/9 ≈ 32.

## 2. Attachment law (exact)

The tree [b₀, b₁] is a root star with b₀ block stars (b₁ + 1 photons each)
attached, one type-I fusion per block between a spare root leaf and the block
centre. A failure costs that leaf and the whole block, so with r spare leaves
the build succeeds exactly when at most r attachments fail:

P = Σ_{f ≤ r} C(b₀ − 1 + f, f) (1/2)^{b₀ + f}.

b₀ = 4: r = 0 gives 1/16, r = 4 gives 163/256 ≈ 0.64, r = 8 ≈ 0.93. Each
attempt consumes a block, so blocks consumed = b₀ + expected failures.

## 3. Storage during the build (exact PGF, labelled bound)

Each attachment takes a geometric number of rounds; during them the root star
and the blocks already attached pay m per photon per round. The expectation of
the total survival is an exact product of generating functions
E[yᴳ] = y/(2 − y), expanded over failure counts up to r. Star-growth rounds are
not charged (optimistic) and the root star is counted whole (pessimistic); the
label is on the number.

| m | [3,3], r = 3 (12 photons) | [4,3], r = 4 (16 photons) |
| --- | --- | --- |
| 1 | P_attach 0.656, survival 1, ≈ 97 Bell pairs | 0.637, 1, ≈ 137 |
| 999/1000 | survival 0.951 | 0.910 |
| 99/100 | 0.608 | 0.396 |
| 9/10 | 0.010 | 2.9 × 10⁻⁴ |

## 4. Theorem B1: one-shot building is a second cliff; multiplexed building pays

One shot (every site built once, in series with the register): all N sites
are built and stored with (P_attach × survival)ᴺ, which at m = 0.99, [4,3],
N = 16 is 2.7 × 10⁻¹⁰, worse than the bare chain. So the v0.26 gain is not
available that way, at any m, including m = 1 (0.64¹⁶).

Site-multiplexed (sites built offline, retried until built and stored, then
switched in): the register walk runs at m_eff and the price is
Bell pairs per delivered site = (Bell pairs per build)/(P_attach × survival):

| m | tree | per delivered site | register of 64 | encoded P(reach 64) vs bare |
| --- | --- | --- | --- | --- |
| 999/1000 | [3,3] | ≈ 156 | ≈ 10⁴ | 0.761 vs 0.027 |
| 99/100 | [3,3] | ≈ 243 | ≈ 1.6 × 10⁴ | 0.604 vs 4.5 × 10⁻¹⁰ |
| 99/100 | [4,3] | ≈ 543 | ≈ 3.5 × 10⁴ | 0.756 vs 4.5 × 10⁻¹⁰ |
| 9/10 | [4,3] | ≈ 7.4 × 10⁵ | ≈ 4.8 × 10⁷ | 7.7 × 10⁻¹³ vs 3.6 × 10⁻⁵⁵ |

So the design law: the attempt loop must give m ≳ 0.99 (the 0.1 µs class of
CHAIN_MEMORY.md), the sites are built off-line and multiplexed (one more
buffer and switch, whose loss is not counted here), and a 64-site encoded
register costs of order 10⁴ Bell pairs. At m = 0.9 the encoding still beats
bare on paper but at 10⁵ to 10⁶ Bell pairs per site, which is not a design.

## 5. Grade (fail-closed)

`build_grade(record)`: BUILD_DECLARED → BLOCK_RECORDED (LAB_RECORDED GHZ
witness of a block star under the per-site rule) → ATTACHMENT_RECORDED
(LAB_RECORDED heralded attachment with stabiliser witness and success rate) →
BUILD_QUALIFIED (recorded attachment success and storage survival at or above
the declared values within tolerance). Negative controls: low success rate,
low survival, unheralded attachment, "any click" rule (6 tests).

## 6. Claims

Claim A unchanged, no passing record. B1 and the tables are exact statements
of the declared model with labelled bounds; the Bell-pair counts are expected
values, not a bill of materials.
