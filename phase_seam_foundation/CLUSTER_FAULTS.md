# Faults on the classifier cluster: storage, switches, multi-pair, dark counts — v0.33

**Author: Monty.** Follows v0.31 (`78a7599`) and v0.32 (`6baa5d9`). Four items
v0.31 left open are settled exactly, and one earlier statement is withdrawn.
Everything here is a rate or an accepted-wrong fraction; nothing is a
fidelity from a loss number, and nothing is measured. The gate v0.32 named
(multipair, interference, dark counts on the accepted output) is priced here
for the cluster.

[Code](cluster_faults.py) · [Tests](../tests/test_phase_seam_cluster_faults.py) ·
[Audit](../benchmarks/cluster_faults_audit.py) ·
[Reproducible results](faults/qualification.json) · [Test log](faults/test_results.txt).

## 1. Claims, separated

**Exact.** Theorem S1 (growth with storage, absorbing-chain solve, m = 1
reproduces the v0.22 walk); the seven-merge success path m¹¹⁹; switch and
buffer transmissions on the native grid composed into the v0.31 acceptance;
Theorem P1 (a heralded double pair with one survivor per site is a classical
mixture; fused into a register it leaves ⟨XXX⟩ = 0, engine-checked, with the
genuine Bell pair as positive control giving 1); the per-pair wrong fraction
4x(1−η)²/((1−x)+4x(1−η)²); the number-resolving herald law; the allowed x;
the 13-node ledger by Theorem V2.

**Withdrawn.** LEDGER_VIOLATIONS.md §V1 and CHAIN_MEMORY.md took the
multi-pair one-survivor event as "accepted and right". That holds for a single
isolated site only. In a fused register it is accepted by the one-click rule
and wrong. The v0.25 design point x = 1/40 therefore fails on the cluster.

**Open.** Waiting of finished stars for the others; correlated loss; the
810 nm source rate that turns Bell-pair counts into time.

## 2. Theorem S1: growth with storage

The v0.22 walk (L → L+2 at s = 1/2, L → L−1 otherwise, one fresh 3-site
resource per round) with every stored photon surviving a round with
probability m, as an absorbing chain with sub-stochastic steps s·m^L and
(1−s)·m^L. The joint probability of reaching the star size with every stored
photon alive is solved exactly; the 3-site resource is the primitive.

| star | m = 0.999 | m = 0.99 | m = 0.9 |
| --- | --- | --- | --- |
| 5 (hub 6) | 0.9934 | 0.9363 | 0.5424 |
| 8 | 0.9868 | 0.8741 | 0.3193 |

(survival factors relative to the lossless walk.) The seven sequential merges
store 20, 19, …, 14 photons for one round each: the success path survives
m¹¹⁹, which is 0.888 at m = 0.999, 0.302 at m = 0.99, 3.6 × 10⁻⁶ at m = 0.9.
A lost photon is a missing click and rejects the run (Theorem L2). Finished
stars are taken to finish together (declared); their waiting is open.

## 3. Switches and buffers

One switch pass and one buffer pass per delivered photon, each a declared
transmission cos²(kπ/32) on the native grid. Thirteen photons:

| (k_switch, k_buffer) | per photon | multiplier on acceptance |
| --- | --- | --- |
| (1, 1) | 0.981 | 0.777 |
| (1, 2) | 0.953 | 0.533 |
| (4, 4) | 0.729 | 0.016 |

At m = 0.99 and η = 0.9 the v0.31 acceptance 0.216 becomes 0.115 with (1, 2).
Rate, not fidelity.

## 4. Theorem P1: the one-survivor case in a fused register

The heralded two-pair term on rails (A′0, A′1; A0, A1) is
(|2,0;2,0⟩ + |1,1;1,1⟩ + |0,2;0,2⟩)/√3. With each photon surviving with
probability η and exactly one survivor at A′ and one at A, every loss branch
carries a distinct environment state, so the conditioned state is the
classical mixture

(5|00⟩⟨00| + 5|11⟩⟨11| + |01⟩⟨01| + |10⟩⟨10|)/12,

reached with probability 4η²(1−η)². Its ZZ correlation is 2/3 and its
coherence is zero. Each component, as a product state with a good Bell pair,
through the exact type-I fusion of Theorem D2: heralded success stays 1/2
(the one-click rule accepts it) and the corrected ⟨XXX⟩ is 0 for every
component, hence 0 for the mixture. The genuine Bell pair gives 1.

With number-resolving readout at both sites, per heralded pair:
right = (1−x)η² (one pair, both survive), accepted-wrong = 4xη²(1−η)²
(Theorem P1), everything else rejected. The wrong fraction

w/(r+w) = 4x(1−η)² / ((1−x) + 4x(1−η)²) ≈ 4x

does not depend on η to first order: loss does not dilute it. At x = 1/40
it is 0.083 per pair; on 13 nodes the V2 witness is 0.30.

**Herald that counts.** A number-resolving herald with efficiency η_h accepts
a double pair as a single click with fraction 2x(1−η_h)/((1−x)+2x(1−η_h)):
at η_h = 0.9 and x = 1/40, 1/196 instead of 1/40. The allowed x for a 13-node
witness ≥ 0.9 from multi-pair alone is 0.0023 with a threshold herald and
0.0114 with a counting herald at 0.9.

## 5. The ledger on 13 nodes

Per node: multi-pair (P1) and dark counts (dark_readout_site) give
accepted-right and accepted-wrong, Theorem V2 gives (r/(r+w))¹³; visibility
enters the seven merges through the mixture law (witness V per merge, V⁷).
Declared inputs η = 243/4000, dark 10⁻⁵ per mode, V = 0.9:

| x | herald | wrong fraction per node | V2 witness | × V⁷ | dominant |
| --- | --- | --- | --- | --- | --- |
| 1/40 | threshold | 0.087 | 0.305 | 0.146 | multi-pair |
| 1/40 | counting 0.9 | 0.023 | 0.742 | 0.355 | multi-pair |
| 1/200 | counting 0.9 | 0.0086 | 0.894 | 0.428 | dark counts |
| 1/1000 | counting 0.9 | 0.0058 | 0.928 | 0.444 | dark counts |

Three design consequences, all exact under the declared model: the source
must run near x ≈ 1/1000 (g2 ≈ 1/500) or herald with a counting detector;
dark counts at 10⁻⁵ per mode cap the witness near 0.93 at η = 0.06, so
10⁻⁶ or a higher site efficiency is needed; and HOM visibility 0.9 alone
caps the cluster at 0.48, so V ≳ 0.99 (0.93 over seven merges) is the
requirement. The grader below reaches LEDGER_CONSISTENT at g2 = 1/500,
counting herald 0.9, dark 10⁻⁶, V = 0.99, and not at g2 = 1/100.

## 6. Grader

`fault_grade` is fail-closed: FAULTS_DECLARED → SOURCE_RECORDED (LAB_RECORDED
heralded g2 < 1/2 and herald readout, with efficiency if counting) →
NODE_FAULTS_RECORDED (LAB_RECORDED dark-count bound, site efficiency, HOM
visibility) → LEDGER_CONSISTENT (the combined bound from the recorded inputs
reaches the target on the 13 nodes). x is taken as g2/2 (SOURCE_SPEC_810.md).

## 7. Reproduce

```bash
python benchmarks/cluster_faults_audit.py
```
