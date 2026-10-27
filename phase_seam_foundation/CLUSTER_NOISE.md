# The classifier's readout noise channel from the corrected source — v0.36

**Author: Monty.** Follows v0.34 (`dbb840a`) and Codex's v0.35 (`06e80f1`, noisy purification cascade). v0.34 corrected the v0.33 source
state and named the source-to-readout channel of the classifier as the open
gate. This packet gives that channel to first order, exactly, with a rigorous
remainder. Nothing is measured and no witness is qualified: the output is an
upper bound on the readout error of the delivered classifier as a function of
the v0.34 double-origin fraction w.

[Code](cluster_noise.py) · [Tests](../tests/test_phase_seam_cluster_noise.py) ·
[Audit](../benchmarks/cluster_noise_audit.py) ·
[Reproducible results](noise/qualification.json) · [Test log](noise/test_results.txt).

## 1. Claims, separated

**Exact (engine-checked in Q(ζ64)):** Lemma N1 (what a wrong Bell pair does
at a corrected type-I merge), Lemma N2 (every Pauli error on the delivered
cluster is a Z pattern), Lemma N3 (a Z error survives the flow correction as
a byproduct Pauli, so the readout probability is exact without branching),
the response table of every single-node error, the source map of the six
Bell-pair stars, and the remainder term.

**Bounded:** the two larger stars (3-star at node 10, 5-star at the hub 6)
enter through the worst Z pattern on their support, not their exact response.

**Never claimed:** a witness, an on-chip learning claim, any advantage, any
measured number. Dark counts, distinguishability (HOM visibility below 1),
correlated loss and the 810 nm rate are outside this channel.

## 2. Lemma N1: a wrong pair is not heralded away, it propagates

Feeding the v0.18 fusion (`dual_rail.fusion_outcomes`) with pair A in each
Bell state and pair B in Φ+:

| pair A | success | register on success (A', C, B') |
|---|---|---|
| Φ+ | 1/2 | clean GHZ register |
| Φ− | 1/2 | Z on any one site (GHZ stabiliser Z_iZ_j) |
| Ψ+ | 1/2 | X on A', the unfused photon |
| Ψ− | 1/2 | Y on A' |

Both click branches, exact equality up to a phase on the native grid. The
success probability is 1/2 for all four, so **the fusion never rejects a
wrong pair**: the v0.33 intuition that Ψ-type errors would show up as failed
heralds is wrong, and the whole Bell-diagonal error of v0.34 reaches the
cluster. (Control: Φ+ reproduces the clean register with no Pauli.)

## 3. Lemma N2 and N3: everything is a Z pattern, and Z survives the correction

On a graph state K_v = X_v Z_{N(v)} stabilises, so X_v ≡ Z_{N(v)} and
Y_v ≡ Z_v Z_{N(v)} up to a phase (checked node by node on the delivered
graph). Z commutes with every CZ, so a Z pattern can be placed at allocation.
A Z on a node measured in B(a) swaps the two outcome branches, so after the
v0.29 flow correction both branches again coincide up to a phase (the error
has become the byproduct X_{f(v)} Z_{N(f(v))}); `noisy_run` asserts this at
every measurement and returns the exact readout probability. Control: with
the correction removed the branches differ.

## 4. The response table

For every node v and every Pauli P ∈ {Z, X, Y}, the exact P(readout = 1) with
P on v, reduced to its Z pattern. Z on a discarded output (1, 3, 7) changes
nothing (control).

On the **XOR checkpoint** (parameters (32, 0, 0, 32, 0), all four examples)
every entry is 0 or 1 and the channel is a parity channel:

* X on any node never flips the label (its Z pattern lands on an even
  number of wire nodes or on discarded outputs only);
* Z or Y on any of the seven **measured wire nodes 0, 2, 4, 6, 8, 10, 12**
  always flips it;
* Z or Y on the six odd nodes 1, 3, 5, 7, 9, 11 never does.

For **generic angles** (features (5, 11), parameters (3, 7, 13, 21, 29),
clean readout 0.6370…) the entries are irrational field elements, listed in
the audit with their decimal display; the clean run equals the circuit
probability of v0.29.

## 5. Source map and Theorem N

Each delivered node comes from a star of the v0.31 build: six Bell-pair
stars (centres 1, 3, 5, 7, 9, 11; centre fused into the parent, leaf kept),
one 3-star (10) from two pairs, one 5-star (6) from four pairs: twelve Bell
pairs. By Lemma N1 a Bell-pair star (k, l) with a wrong pair gives, exactly,
Z_k (Φ−), Z_l (Ψ+, the GHZ X on the leaf becomes Z after the leaf Hadamard)
or Z_k Z_l (Ψ−). For the larger stars a Pauli on any star photon is, by the
GHZ stabilisers, some Pauli string on the star's delivered nodes, hence a Z
pattern supported on those nodes and their neighbours (discarded outputs
dropped): support (0, 2, 4, 5, 6, 10) for the hub, (8, 9, 10, 11, 12) for
node 10.

With q = w/4 the per-pair error probability (v0.34 weights
(1 − w/4, w/12, w/12, w/12)) and Δ(S) the exact change of the readout
probability under the Z pattern S,

|P_noisy − P_clean| ≤ (w/12) [ Σ_{Bell-pair stars} (Δ(Φ−) + Δ(Ψ+) + Δ(Ψ−))
 + 3·2·max_S Δ_10(S) + 3·4·max_S Δ_6(S) ] + R,
R = 1 − (1 − q)^12 − 12 q (1 − q)^11.

The first bracket is the exact first-order term (one wrong pair, any label),
the maxima bound the larger stars, and R is the exact probability of two or
more wrong pairs, where the change is at most 1.

Numbers on the XOR checkpoint at η = 243/4000 (the v0.21 per-site budget):

| x (double-pair prob.) | w | bound on readout error |
|---|---|---|
| 1/40 (v0.20 proposal) | 0.0830 | 0.232 |
| 1/200 | 0.0180 | 0.045 |
| 1/1000 | 0.0036 | 0.0089 |
| ≈ 1/885 (bisection) | 0.0040 | 0.0100 |

At the generic angles the same bound is much smaller (0.046, 0.0057, 0.00096
at x = 1/40, 1/200, 1/1000): a non-Clifford readout responds to most single
Z patterns by a fraction of a label, so the XOR checkpoint is the worst case
of the two.

So the readout-error bound of the delivered classifier is about 2.8 w, and a
1 % label error needs w ≲ 0.004, i.e. x ≲ 1/885 at this η, or the counting
herald of v0.33 which brings w down by the heralding factor. This replaces
the withdrawn v0.33 thresholds with a bound derived from the circuit itself.

## 6. Grader

Fail-closed, never a witness: NOISE_DECLARED → SOURCE_SECTOR_RECORDED
(LAB_RECORDED four Bell weights, nonnegative, summing to one, target largest)
→ READOUT_NOISE_PREDICTED (LAB_RECORDED label error rate within the stated
Theorem N bound). WITNESS_QUALIFIED, TRAINED_ON_CHIP, QUANTUM_ADVANTAGE and
ROOM_TEMPERATURE_CLASSIFIER are never granted.

## 7. Open

Exact (not worst-pattern) propagation inside the 3-star and 5-star; the XOR
parity channel composed exactly over all twelve pairs (the bound above is
first order); dark counts and HOM visibility as node errors through the same
response table; correlated loss; the 810 nm source rate. First bench
measurements unchanged: facet loss and detector efficiency at 810 nm, then
g2 and HOM.
