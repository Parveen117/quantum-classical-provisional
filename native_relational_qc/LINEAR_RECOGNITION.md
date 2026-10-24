# Minimum linear future-observation banks

Author: Monty · 24 October 2026

The new `linear_future_bank` compiler replaces Pauli **coordinate** closure
with exact **row-space** closure over Q(zeta_32). It retains independent linear
combinations of Paulis needed by a seed observable under every word of a
declared wire-labelled gate alphabet. `verify_linear_bank` checks an explicit
minimality witness, and `run_linear_bank` verifies then executes a chosen word
using the retained readings. Existing calculator backends are unchanged.

This closes the minimum-linear-dimension obligation left open by
[the previous observer upgrade](OBSERVER_RECOGNITION.md), for this finite
supported input class whenever the resource budgets permit completion. It does
not establish minimum RAM, minimum execution time, affine compression on
normalized states, or a general efficient quantum simulator.

## What reduction means

Distinct Pauli operators are linearly independent. The old bank's coordinates
are not redundant as descriptions of arbitrary operators or states. Instead,
the orbit of a **particular future measurement** can occupy a smaller subspace
of those coordinates. The new compiler preserves that subspace without first
constructing the whole old coordinate bank.

For one controlled-H or CCX gate and a suitable Pauli seed, conjugation is an
involution: the seed and its image span at most two directions. The old
coordinate expansion uses four Paulis; exact row closure uses two combined
readings. For CP32, the corresponding seed orbit has rank three, with
frequencies 0 and ±pi/16, while coordinate closure uses four Paulis.

The seven-qubit example uses three commuting CCX gates, with disjoint control
pairs (0,1), (2,3), (4,5) and shared target 6. Its seed is Z6. The old coordinate
bank has dimension 64; the new linear bank has dimension 8. Its basis still
contains **64 nonzero Pauli coefficients in total**. The transition matrices
shrink from 768 nonzero coefficients to 48. Eight combined readings can be
updated without maintaining 64 individual Pauli readings. This is a specific
reversible-gate example, not a full Shor circuit or general seven-qubit state
compression result.

## Run it on the PC

```python
from native_relational_qc.phase_backend import Phase32Circuit
from native_relational_qc.linear_observer import (
    linear_future_bank, verify_linear_bank, run_linear_bank,
)

alphabet = Phase32Circuit(7)
for q in range(3):
    alphabet.add('ccx', 2*q, 2*q+1, 6)
seed = {6: 'Z'}

bank = linear_future_bank(alphabet, seed)
checked = verify_linear_bank(alphabet, seed, bank)
assert checked['retained_dimension'] == 8

# All six controls are 1, target is 0. Each gate flips the target.
result = run_linear_bank(
    alphabet, seed, bank,
    input_basis=63,
    action_sequence=[i % 3 for i in range(127)],
)
print(result['value'])  # exact -1 after 127 flips
```

The circuit's distinct operations, in first-appearance order, declare the
alphabet. `action_sequence` contains alphabet indices in chronological order.
Omitting it executes the supplied circuit's own operation list. The optional
`input_basis` is a computational-basis integer, q0 least significant; default
0 is the all-zero input. The mathematical certificate covers every density
operator; this first execution API initializes computational-basis states.

The three APIs are explicit Python interfaces, not a new default calculator
backend. The compiler accepts one Pauli seed, the existing Phase32Circuit gate
alphabet and 1–256 wires. It does not accept arbitrary seed matrices or gates,
dynamic measurements or arbitrary-angle rotations. Duplicate seed sites,
out-of-range masks and noncanonical coefficient encodings are rejected.

## Exact construction and certificate

Let K=Q(zeta_32), let E be the seed Pauli, and write
L_a(P)=U_a† P U_a for each supported action. The required row space is

\[
 W=\operatorname{span}_K\{L_{a_1}\cdots L_{a_k}(E): k\ge0\}.
\]

This is the finite-linear closure of RKF MR-04. The exact source revision and
hash are already recorded in [observer_source_pins.json](observer_source_pins.json),
at commit `b72432d3efba6c462848fe9ce9adb98c827a6089`. We use its standard linear
closure argument; no new physical assumption or spectral-rank shortcut is
introduced. The earlier coordinate compiler deliberately made no minimum-rank
claim. Its historical qualification remains unchanged.

The new compiler starts with E. Each image of each retained basis row is
reduced by exact insertion-order Gaussian elimination. A nonzero remainder is
normalized at a deterministic pivot and appended to the basis. Later rows
vanish on earlier pivots, which proves independence without numerical rank
tolerances. Newly added rows are also processed under every action. A second
pass expresses every final image in the finished basis.

The certificate includes:

- Sparse Pauli coefficients for every basis vector and its pivot.
- Each vector's provenance: seed or image of an earlier basis vector, the
  earlier rows subtracted, and the nonzero normalization divisor.
- Exact sparse transition matrices, the seed, alphabet and alphabet digest.
- The precise homogeneous-linear minimality scope and resource counters.

The verifier uses direct exact reconstruction, **not the eliminator**. It checks
input binding, independence, provenance and closure. Provenance establishes
that every retained vector belongs to W. Closure plus seed reconstruction
establishes that W lies in the retained span. Consequently the two spaces are
equal. This rules out both an insufficient bank and an unnecessarily inflated
closed bank claimed to be minimal.

If B_i are the retained observables and R(rho)_i=Tr(B_i rho), the checked rows
satisfy

\[
 L_a(B_i)=\sum_j T_{a,ij}B_j,
 \qquad R(U_a\rho U_a^\dagger)=T_a R(\rho).
\]

The identities hold for every finite chronological word, by induction. The
source seed is reconstructed from the first normalized basis row and its
recorded divisor. The implementation does not assume intermediate readings
are probabilities or lie in [-1,1]; normalized basis combinations need not be
unit-norm Paulis.

For any other homogeneous K-linear observation map S that recovers the seed
and admits exact updates under every generator, its row space contains E and
is invariant under every L_a. It must therefore contain W. Its rank is at least
dim(W), which the constructed independent basis attains. This is the precise
minimality claim. State-specific, nonlinear, approximate or affine summaries
are outside this comparison. In particular, treating known trace one as a free
affine offset changes the minimization problem.

An independent Qiskit/dense-matrix test checks conjugated operators and
forty chronological updates on arbitrary mixed density matrices. Numerical
tests corroborate the implementation; exact coefficient identities and pivot
witnesses carry the algebraic rank decision. This is not proof-assistant or
external mathematical certification.

## Bounded execution and failures

Default limits are rank 128, 4096 terms in each sparse vector, 65,536 stored
coefficient slots, 10 million work units and 4096 coefficient bits. Coefficient
slots count basis, transition and provenance scalars. They do not measure
Python object memory, local gate-image caches, integer limbs or temporary
vectors. A rank-r basis can require many more than r stored coefficients.

The work ledger counts gate/term operations, elimination scans, parsing and
explicit field arithmetic calls, including field inversions. An inverse's
internal field arithmetic is not separately charged. The reused constant-size
gate-image construction has the same counter limitation documented for
observer32. Bounds apply to emitted/retained coefficients, not a claim to meter
every temporary machine operation. Direct APIs have no wall or RSS cap; the
qualification harness runs fresh processes with a wall timeout.

Compilation failure returns no bank. Verification failure returns no successful
certificate. Execution verifies first and shares a work budget between
verification and evolution; failure returns no partial answer. A changed gate
alphabet requires a newly bound certificate. The data structure's saved
`statistics` are not trusted by the verifier, which reports its own counters.

Even lower rank can cost more to compile: Gaussian reduction and exact inverses
add work. Basis coefficients may grow, and full future closure may be much
harder than one fixed-circuit pullback. The old `observer32` remains the direct
selected-measurement path. No automatic switching or state approximation is
added.

## Qualification and reproduction

[Frozen protocol](linear_protocol.json), [all measured runs and an example certificate](linear_results.json),
[verification manifest](linear_verification.json) and [test log](linear_test_results.txt)
record the comparison. A retained [pilot](linear_pilot.json) preceded freeze;
it ran in one process with shared caches, so its timings are not comparative
evidence. Unit tests and the pilot were not blind preregistration.

Both methods compile the same alphabet and replay the same 127-gate word on
the same input. The new method's replay time also includes independent exact
certificate verification; the old method applies its generated rows without
a separate verifier. Each timed run uses a fresh process, serial execution,
and alternating case order. These are local measurements, not a comparison
against the best available classical simulator.

The cap-48 case uses the same numeric cap on **different representation
units**: the old bank's whole coordinate set versus a new-bank sparse vector.
The new bank's largest intermediate vector has 36 terms, while old closure
needs 64 coordinates. This is a demonstrated resource-boundary difference,
not a matched total-memory experiment. A 50-wire padded unit test checks width
compatibility only; timed circuits have 1, 2 or 7 active qubits.

All 30 paired fresh-process runs had their expected status: 27 completed with
exact sparse-state reference agreement and three retained coordinate-cap
failures. Separate rank, stored-coefficient and wall guards also failed without
a partial answer. Successful certificate hashes were identical across repeats.
Three repetitions per case give the following medians; columns show
**coordinate bank → linear bank**.

| Alphabet / seed | Dimension | Compile s | Whole-worker wall s | Compact certificate bytes |
| --- | ---: | ---: | ---: | ---: |
| CH(0,1) / Z1 | 4 → 2 | 0.0076 → 0.0131 | 0.2625 → 0.1669 | 4,538 → 3,578 |
| CP32(0,1) / X1 | 4 → 3 | 0.0222 → 0.0404 | 0.2148 → 0.2221 | 4,644 → 5,842 |
| Three CCX gates, 7 wires / Z6 | 64 → 8 | 0.0545 → 0.2726 | 3.4831 → 0.7382 | 184,447 → 31,628 |
| H0, P32(0) / Z0 | 3 → 3 | 0.0064 → 0.0104 | 0.2229 → 0.2479 | 2,657 → 4,606 |

The CCX example's repeated execution is faster even after the new method's
larger compilation cost and certificate verification. Maximum worker RSS was
27.5 MiB for the coordinate route and 25.8 MiB for the linear route, including
imports and setup. Rank reduction is much larger than RSS reduction. CP32 is
an explicit counterexample to equating lower rank with a smaller certificate
or faster total execution. H/P32 gives no rank reduction and costs more.
The cap-48 linear case completes at median wall time 0.7587 s; the old route
rejects at 0.1611 s, which is not a successful-run speed comparison.

**289 native test methods passed in 118.474 seconds, with no failures, errors
or skips.** Ten new methods cover exact rank reduction and the phase-orbit
polynomial, independent operator/mixed-state checks, old-bank and sparse-state
agreement, delayed revelation, no-reduction cases, malformed/tampered or
inflated certificates, and rank/work/bit/term/storage boundaries. A late runtime
work failure also verifies that no partial answer is returned. The previous
observer and arithmetic engines remain unchanged.

```bash
python -m unittest discover -s tests -p 'test_native*.py' -v
python -m native_relational_qc.linear_qualification --run \
  --out /tmp/linear-replay.json
```

Replay frozen protocols at the commit containing their matching source. The
current experiment establishes minimum linear dimension for successful
declared banks and exact repeated execution. Large arbitrary-phase circuits,
larger Shor factoring, scalable low-rank closure and physical hardware remain
separate development targets.
