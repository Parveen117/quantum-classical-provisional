# Faults on the classifier cluster: storage, switches, multi-pair, dark counts — v0.33

**Author: Monty.** Follows v0.31 (`78a7599`) and v0.32 (`6baa5d9`). The storage and switch calculations extend v0.31. **The original P1 source
claim and its 13-node witness interpretation are corrected in v0.34 below.**
Storage rates and source-state fidelity are distinct outputs of stated
models; nothing is measured. The complete source-to-cluster accepted-output
noise channel remains open. The v0.34 device channel covers one purification
round, not the full classifier.

[Code](cluster_faults.py) · [Tests](../tests/test_phase_seam_cluster_faults.py) ·
[Audit](../benchmarks/cluster_faults_audit.py) ·
[Reproducible results](faults/qualification.json) · [Test log](faults/test_results.txt).

## 1. Claims, separated

**Retained:** the stated S1 storage walk, success-path storage m^119,
and native-grid switch/buffer transmission calculations.

**Corrected in v0.34:** the source partial trace retains coherence. The
conditional Bell/GHZ fidelity is 3/4 and corrected fused XXX is 2/3.

**Withdrawn as physical bounds:** the zero-response 13-node product and
source thresholds inferred from it. Source-to-cluster noise propagation,
finished-star waiting, correlated loss and measured rates remain open.

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

## 4. P1 correction in v0.34

The original v0.33 partial trace incorrectly gave every *input term* a
separate environment label. Distinct input terms can lose photons into the
same environment occupation, so those amplitudes must interfere. For the
stated coherent double-pair input and uniform pure loss, the correct state
conditioned on one survivor per site is

```
rho = [[5,0,0,4], [0,1,0,0], [0,0,1,0], [4,0,0,5]] / 12
```

Its Bell weights are `(3/4,1/12,1/12,1/12)`; XX and ZZ are 2/3, YY is -2/3.
The event probability remains `4 eta^2 (1-eta)^2`. The existing type-I fusion
with a good Bell pair succeeds with probability 1/2 and leaves corrected
XXX = 2/3 and GHZ fidelity = 3/4. At eta = 0 or 1 this selected source event
has probability zero and no conditional state is reported.

The diagonal mixture, zero-XXX result and their derived physical conclusions
are withdrawn. The event is neither an ideal Bell pair nor a fully dephased
pair. An eight-mode beam-splitter dilation independently verifies the density
matrix. See [SOURCE_DISTILLATION.md](SOURCE_DISTILLATION.md) for the full
corrected derivation and new device/channel tests.

## 5. Event fraction is not state infidelity

For a declared mixture of one and two pairs with double weight x, the
selected double-origin fraction is still

`w = 4x(1-eta)^2 / ((1-x)+4x(1-eta)^2)`.

But the selected state has fidelity `1-w/4`, and a subsequent ideal GHZ merge
has XXX `1-w/3`. The leading term of **w** at small x is
`4(1-eta)^2 x`; `4x` additionally requires small eta. This mixture weight x
is not automatically the thermal pump parameter in SOURCE_SPEC_810.md.
That document's `g2=2x` relation has its own source and ideal-threshold-herald
assumptions. It cannot be transferred to this truncated mixture or reapplied
after counting-herald conditioning without deriving the new statistics.

`number_resolving_herald` remains a one/double-number mixture calculation;
it is not a nondestructive method of certifying both surviving photons.

## 6. The 13-node physical fault gate remains open

The old score `(r/(r+w))^13 * V^7` is retained in `cluster_fault_ledger` only
as `toy_score`, with `is_physical_witness_bound=False`. A pair-level source
fault can propagate and correlate across a fused cluster. Assigning every
fault response zero and multiplying a single-site dark-count model into it
has not established either the actual circuit witness or a conservative
bound for that circuit. The earlier numerical source thresholds and claimed
LEDGER_CONSISTENT design point are therefore withdrawn as device claims.

`fault_grade` checks the source and node fields but stops at
NODE_FAULTS_RECORDED. It does not infer x from g2 or qualify a witness until
a source-conditioning map and the actual accepted-output circuit channel
are supplied. These record dictionaries are synthetic examples, not lab logs.
The storage/switch results in sections 2–3 are retained under their stated
models; simultaneous star completion and unknown physical rates remain open.

## 7. Reproduce

```bash
python benchmarks/cluster_faults_audit.py
python benchmarks/source_distillation_audit.py
```

The v0.33 packet remains in Git history at `90bc68d`; the current audit is
regenerated against the corrected code and includes the changed expectations.
