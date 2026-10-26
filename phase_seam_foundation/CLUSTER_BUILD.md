# Building and running the classifier cluster on the route — v0.31

**Author: Monty.** Follows v0.29 (`4b17975`, the classifier as a 13-photon tree
cluster) and uses v0.30 (`0d6dc92`, passive optical refresh) where it helps:
its corrected type-I merge rows, derived in the exact Fock engine, are the
primitive that builds the cluster. Three things v0.29 left open are settled
exactly; nothing is measured.

[Code](cluster_build.py) · [Tests](../tests/test_phase_seam_cluster_build.py) ·
[Audit](../benchmarks/cluster_build_audit.py) ·
[Reproducible results](cluster_build/qualification.json) · [Test log](cluster_build/test_results.txt).

## 1. Claims, separated

**Exact.** Lemma A (angle adaptation) at all 64 native angles; an end-to-end
adaptive witness with a tracked Pauli frame equal to the circuit probability
for the XOR checkpoint and generic angles along four outcome paths each; the
13-node tree graph state from seven corrected merges, sign-exact at every
merge; the cost under two declared policies; the online acceptance ledger.

**Never.** A device, a measured number, a fidelity from a loss number, speedup
or advantage (CLUSTER_COMPILE.md §1 stands).

**Open.** Storage during star growth; switch and buffer loss; multi-pair, dark
counts and visibility on the 13 nodes (LEDGER_VIOLATIONS.md applies per node);
the 810 nm source rate that turns Bell-pair counts into time.

## 2. Lemma A: the corrections are heater trims and a relabel

X^x Z^z |s_a⟩⟨s_a| Z^z X^x = |s'_{a'}⟩⟨s'_{a'}| with s' = s ⊕ z and
a' = (−1)^x a. A Pauli byproduct in front of a measurement in B(a) is absorbed
by measuring in B((−1)^x a) and reading the outcome ⊕ z. On the route that is
the `before` trim of Theorem D1 set to (32 − a') mod 64 instead of (32 − a),
and a classical bit flip. No rail switch exists in the pattern. Checked as an
exact 2×2 identity for every a, s, x, z.

**Feedforward depth.** A node can be set once every measurement that writes to
its frame is read: its flow predecessor (X) and every node whose successor
neighbours it (Z). Layers: {0, 2, 4, 8} → {5, 9} → {6} → {10} → {11} →
readout 12. Six stages, so the cluster is held for five feedforward latencies
after delivery; the first four measurements need no feedforward at all.

**Adaptive witness.** The engine of v0.29 runs the ideal corrected pattern;
beside it a physical copy carries the frame instead of corrections. At each
measurement, for both raw outcomes, the frame-corrected physical branch must
equal the ideal branch exactly up to a global phase on the native grid (the
branch is classical; Paulis anticommute), and both weights are 1/2. A chosen
outcome path is then followed so that non-trivial frames, flipped angles and
relabelled outcomes are exercised. The readout at the adapted angle with the
relabelled outcome equals the circuit probability exactly: 24 runs (six
inputs × four paths) in the audit, all exact. Along the path
(1,1,0,1,0,1,1,1,0) at generic angles the readout flips from 14 to 50 steps.

## 3. The tree from stars, exactly

Root the tree at hub 6. Each internal node is a star: a child's centre merges
into a leaf of its parent's star. Six internal nodes have one child and are
Bell pairs; node 10 is a 3-star; hub 6 a 5-star. Twenty photons, seven
merges, thirteen left.

Each merge uses the corrected Kraus row of v0.30's `fusion_merge_certificate`,
checked here to be scalar·(|0⟩⟨00| + |1⟩⟨11|) with |scalar|² = 1/2 and phase
corrections 16 or 48 steps. Assembled bottom-up (largest intermediate state 14
photons), the surviving sign vector equals the graph state of the 12 declared
edges on all 2¹³ basis states, for every one of the 128 click sequences, each
of probability 2⁻¹⁴; success 1/128, as v0.29 counted.

## 4. What it costs, two policies

| policy | success | expected Bell pairs per delivered cluster | merge rounds |
| --- | --- | --- | --- |
| full restart (v0.30: prepare all eight stars, discard on the first failure) | 1/128 | 17664/5 ≈ 3533 (27.6 per candidate) | 254 |
| spare leaves (v0.27 law, v0.29 numbers), 4 spare per parent | ≈ 0.549 | ≈ 202, conditional on success | — |

Star costs are the v0.22 walk (Bell pair 1, 3-star 4, 5-star 92/5 Bell pairs
per reach). The full-restart figure is an unconditional expectation with zero
storage loss and no star-preparation time; the spare-leaf figure is
conditional and omits star-growth storage. Neither is a device number. The
lesson of Theorem B1 stands: build offline, multiplexed, at m ≳ 0.99.

## 5. Online ledger

Every measured node must click exactly once (Theorem L2); a missing click
rejects the run and costs rate, never fidelity. A node read in layer ℓ waits
ℓ·d rounds at per-round survival m; detector efficiency η per read node, all
13 nodes required (the three discarded nodes included, conservatively).

| m | η = 1 | η = 0.9 | η = 0.5 |
| --- | --- | --- | --- |
| 0.999 | 0.984 | 0.250 | 1.2 × 10⁻⁴ |
| 0.99 | 0.851 | 0.216 | 1.0 × 10⁻⁴ |
| 0.9 | 0.185 | 0.047 | 2.3 × 10⁻⁵ |

Detector efficiency dominates (η¹³); storage at the 0.1 µs class costs little.
Multi-pair, dark counts and distinguishability are not in this table and are
the unheralded sources LEDGER_VIOLATIONS.md gates per node.

## 6. Grader

`cluster_build_grade` is fail-closed: BUILD_DECLARED → STARS_RECORDED
(LAB_RECORDED GHZ5 and GHZ3 witnesses) → TREE_RECORDED (LAB_RECORDED 13
photons, at least 12 stabiliser witnesses, merge phases applied) →
ADAPTIVE_RUN_RECORDED (LAB_RECORDED latency, six stages, rejected runs counted,
zero rail switches).

## 7. Reproduce

```bash
python benchmarks/cluster_build_audit.py
```
