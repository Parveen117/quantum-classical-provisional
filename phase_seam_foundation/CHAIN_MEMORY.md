# Memory loss in the chain and the joint source/readout design point — v0.25

**v0.33 correction:** the design point x = 1/40 chosen below credits the multi-pair one-survivor event as right; in a fused register it is wrong (Theorem P1, [CLUSTER_FAULTS.md](CLUSTER_FAULTS.md)). For fused registers the source must run near x ≈ 1/1000 or herald with a counting detector; the memory law M1 and the readout conclusions are unchanged.

**Author: Monty.** FUSION_NETWORK.md built the register by fusing 3-site
resources onto a chain and assumed the stored chain photons wait for free.
The route's only photonic memory is fibre delay, so every attempt charges
every stored photon one transmission m. This note makes that exact, shows
what it does to sequential growth (Theorem M1), compares the balanced tree,
and then closes the design loop opened in v0.24 by choosing the source
operating point x and the readout type together. Everything is declared or
exact; nothing is measured.

[Code](chain_memory.py) · [Tests](../tests/test_phase_seam_chain_memory.py) ·
[Audit](../benchmarks/chain_memory_audit.py) · [Qualification](memory/qualification.json).

## 1. The lossy-memory walk (exact)

From chain length L one attempt first stores the L photons for a round, all
surviving with probability mᴸ (otherwise the per-site readout rule rejects the
run: absorb at 0), then the fusion succeeds with s = 1/2 (L → L + 2) or fails
(L → L − 1). Absorbing Markov chain solved over rationals; m = 1 recovers the
v0.22 values (6/7, 7/9, 2207/2889).

| m per attempt | N = 8 | 16 | 32 | 64 |
| --- | --- | --- | --- | --- |
| 1 | 0.778 | 0.764 | 0.764 | 0.764 |
| 999/1000 | 0.753 | 0.637 | 0.333 | 0.027 |
| 99/100 | 0.572 | 0.163 | 0.0018 | 4.5 × 10⁻¹⁰ |
| 9/10 | 0.069 | 5 × 10⁻⁵ | 7 × 10⁻¹⁶ | 4 × 10⁻⁵⁵ |

## 2. Theorem M1: sequential growth is super-exponentially suppressed

Reaching N from 3 needs J = ⌈(N − 3)/2⌉ successes; the j-th happens at length
at least 3 + 2(j − 1) and every stored photon must survive that attempt, so

P(reach N) ≤ ∏ⱼ m^{3 + 2(j−1)} = m^{3J + J(J−1)}.

The exponent is quadratic in N (N = 2056: 1 056 183). The bound holds against
the exact walk at every tested (m, N) and is the reason the table above falls
off a cliff: no fibre delay (m < 1) supports a long sequential chain, however
good the fusion. Control: m = 1 gives bound 1 and the v0.22 limit 3 − √5.

## 3. The tree, for comparison

A balanced fusion tree with one attempt round per level stores every photon for
⌈log₂ N⌉ rounds: all survive with m^{N·depth}, exponential rather than quadratic
(m = 99/100: N = 64 gives 0.021 against the chain's 4.5 × 10⁻¹⁰; N = 2056 needs
m = 9999/10000 for 0.085, and m = 999/1000 gives 2 × 10⁻¹¹). Repeat-until-success
inside the tree multiplies the stored rounds and is not modelled. The exact
message: the architecture must be shallow and the delay short; loss-tolerant
encodings, which would change both laws, are outside this note.

## 4. Declared fibre delay at 810 nm

Light in fibre ≈ 0.2 km/µs; declared loss 2 to 3 dB/km at 810 nm. An attempt
latency of 0.1 µs is 20 m and ≈ 0.04 dB (m ≈ 0.991); 1 µs is 200 m and ≈ 0.4 dB
(m ≈ 0.91); 10 µs is 2 km and ≈ 4 dB (m ≈ 0.40). So the detector-and-switch
latency per attempt is itself a register-size parameter: 1 µs latency already
puts m at 0.91, where 16 sites survive sequentially with 5 × 10⁻⁵. These numbers
are display; the laws above take m as a declared rational.

## 5. Joint design point: x and readout together

For target witness V on N sites, the allowed per-site wrong fraction is
1 − V^{1/N} (v0.24). For each source operating point x the budget upper bound
(multi-pair under the chosen readout, dark counts) is compared with it, the
heralded g2 at herald efficiency 1/2 is capped at 1/10, and the herald
probability is the rate. Results (V = 1/2):

| N | η = 243/4000, d = 10⁻⁵ | η = 1/2, d = 10⁻⁶ |
| --- | --- | --- |
| 8, 64 | feasible with either readout, best x = 1/40 | same |
| 2056 | threshold readout: no x feasible; number-resolving: x = 1/40 | same |

The g2 cap, not the ledger budget, is what stops x at 1/40 for small N;
at 2056 sites threshold readout fails at every x because of V1. So the
design is: x = 1/40, number-resolving readout for large registers, threshold
acceptable up to the tens of sites.

## 6. Grade (fail-closed)

`memory_grade(record)`: MEMORY_DECLARED → DELAY_LOSS_RECORDED (LAB_RECORDED
delay-line transmission per attempt) → STORED_CHAIN_RECORDED (LAB_RECORDED
survival of a ≥ 3-site chain over one round under the per-site rule) →
MEMORY_QUALIFIED (survival at or above the declared mᴸ within tolerance and
witness after storage at or above the source visibility). Negative controls:
low survival, 2-site chain, "any click" rule, witness below visibility,
modelled delay (9 tests).

## 7. Claims

Claim A unchanged, no passing record. M1 and the walk are exact statements of
the declared model; the fibre numbers are declared; the design point is a
proposal that the bench measurements (g2, dark rate, delay loss) will move.
