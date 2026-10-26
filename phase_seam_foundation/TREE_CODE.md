# Loss-tolerant encoding of a site: the tree code, exactly — v0.26

**v0.28 correction:** [Age-aware memory and coherent refresh](LOSS_REFRESH.md)
supersedes the repeated-storage interpretation below. A fixed block survives
`t` rounds with `P_both(1-m^t)`. The v0.26 chain table assumes perfect fresh
encoding after every round and perfect encoded fusions; it is not a physical
lower bound. Single-round stabiliser polynomials are unchanged.

**Author: Monty.** CHAIN_MEMORY.md (Theorem M1) showed that any memory loss
m < 1 suppresses sequential growth as m^(3J + J(J−1)). The one lever left
inside the model is to let a logical site survive the loss of some of its
photons. This note encodes a dual-rail site in a tree graph state and derives
everything from the stabilisers over GF(2): no literature recursion, no
float. The price is photons per logical site; the gain is an effective memory
m_eff that feeds the v0.25 walk. Nothing is measured; no encoded site exists.

[Code](loss_tolerant_code.py) · [Tests](../tests/test_phase_seam_loss_tolerant_code.py) ·
[Audit](../benchmarks/loss_tolerant_code_audit.py) · [Qualification](code/qualification.json).

## 1. The code (derived)

Tree with branching [b₀, b₁]: b₀ level-1 photons, each with b₁ leaves; the
root carries the logical input and is measured out in X. For a node v with
parent p and children C, K_v = Z_p X_v ∏_C Z_c is a graph stabiliser. Level ≥ 1
nodes give code stabilisers directly; for level-1 nodes only pairwise products
K_a K_b survive (the root Z cancels). The logical operators follow by pushing
the root's Paulis through the CZ edges: Z_L = X_a ∏_{children(a)} Z_c for any
level-1 a, and X_L = ∏_a Z_a. Checked exactly: all stabilisers commute with
each other and with both logicals, the logicals anticommute, and the stabiliser
rank is (photons − 1): one logical qubit.

## 2. Recovery under loss (exact, every pattern)

A logical measurement survives a loss set Λ when some representative
(logical × stabiliser) acts as identity on Λ: a GF(2) membership question on
the lost coordinates. Enumerating every loss pattern gives the number of
recoverable patterns of each weight, hence P(ε) = Σⱼ aⱼ εʲ (1 − ε)ⁿ⁻ʲ exactly
for Z_L, X_L and both together. Controls: the bare photon [1] gives 1 − ε; the
repetition block [b] protects Z_L (1 − εᵇ) but not X_L ((1 − ε)ᵇ) and never
beats the bare photon on both.

| tree | photons | P_both at ε = 1/10 | at ε = 1/5 | bare 1 − ε | beats bare up to ε ≈ |
| --- | --- | --- | --- | --- | --- |
| [2,2] | 6 | 0.925 | 0.754 | 0.9 / 0.8 | 0.146 |
| [3,2] | 9 | 0.977 | 0.866 | | 0.275 |
| [3,3] | 12 | 0.959 | 0.791 | | 0.192 |
| [4,3] | 16 | 0.986 | 0.873 | | 0.266 |

Both-basis counts for [3,3]: [1, 12, 66, 156, 204, 144, 48, 0, …]: every loss
of up to two photons out of twelve is recoverable in both bases. At three
losses only 156 of the 220 patterns are recoverable; none of seven or more
is recoverable. Crossovers are bracketed exactly by bisection on the
polynomial.

## 3. Historical ideal-refresh chain reference

An encoded site is recoverable after one round with m_eff = P_both(1 − m).
Reusing it as a memoryless survival probability assumes full fresh-block
renewal after each round, with zero time/cost and perfect encoded fusions.
Flooring to 20 bits gives a lower bound only within this idealised model:

| m | tree | N | bare P(reach N) | encoded (lower bound) | photons in register |
| --- | --- | --- | --- | --- | --- |
| 9/10 | [3,3] | 16 | 5.0 × 10⁻⁵ | 6.1 × 10⁻³ | 192 |
| 9/10 | [4,3] | 16 | 5.0 × 10⁻⁵ | 0.094 | 256 |
| 99/100 | [3,3] | 16 | 0.163 | 0.755 | 192 |
| 99/100 | [3,3] | 64 | 4.5 × 10⁻¹⁰ | 0.604 | 768 |
| 99/100 | [4,3] | 64 | 4.5 × 10⁻¹⁰ | 0.756 | 1024 |

So with m = 0.99 per attempt (≈ 0.04 dB, 0.1 µs latency in the declared fibre
table) the ideal-refresh [4,3] chain of 64 sites gives about 0.756, still below
the v0.22 lossless limit 3 − √5 ≈ 0.764, at 16 photons per site. With m = 0.9 (1 µs
latency) even [4,3] leaves 16 sites at 9 %: the encoding does not rescue a
slow attempt loop. Theorem M1 still holds with m_eff in place of m; the
encoding moves the base, not the quadratic exponent.

## 4. What this costs and does not cover

The missing renewal/coupling costs are addressed as explicit inputs in
LOSS_REFRESH.md; no physical lower bound follows from this table.
Each encoded site is itself built by fusions (one per edge in the tree, each
heralded at 1/2 before boosting) and those fusions store photons too; that
cost is not counted here and is the next open item. The polynomials assume
independent loss per photon and perfect stabiliser preparation; the ledger
violations of v0.24 (multi-pair, dark counts) act on every photon of the
encoded site and multiply accordingly.

## 5. Grade (fail-closed)

`code_grade(record)`: CODE_DECLARED → ENCODED_SITE_RECORDED (LAB_RECORDED tree
state with stabiliser witnesses) → LOSS_RECOVERY_RECORDED (LAB_RECORDED logical
X and Z recovery with a deliberately removed photon) → CODE_QUALIFIED (recorded
recovery at or above the exact polynomial within tolerance). Negative controls:
low recovery, no removed photon, simulated site (8 tests).

## 6. Claims

Claim A unchanged, no passing record. The code and its polynomials are exact
statements of the declared model; the table is a budget, not a measurement.
