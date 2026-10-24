# Exact phase observations and future-complete recognition

Author: Monty · 24 October 2026

`observer32` evaluates selected observations in Q(exp(i*pi/16)) without preparing
computational-basis amplitudes. It extends the calculator's **existing** exact
Pauli/Heisenberg method to the p16/p32 phase family. A separate `future_bank`
API constructs an exact, sparse, future-closed Pauli coordinate representation
for a declared gate alphabet. These are bounded classical algorithms, not a
physical processor or a general efficient quantum simulation theorem.

For the saved connected 50-qubit graph circuit, the X0 Z1 measurement uses at
most two Pauli terms and equals cos(pi/16) exactly. The sparse amplitude backend
exceeds its default 4096-amplitude limit on the same circuit. A retained reverse
example has a one-amplitude state while the observer exceeds its term cap.

## Run the calculator

```bash
python -m native_relational_qc calculate \
  native_relational_qc/calculator_examples/observer_graph50.json \
  --timeout 20 --out /tmp/observer50.json
```

Select `"backend": "observer32"` explicitly. Supported gates are the compact
alphabet (including nonadjacent controls and CCX) and
`p16/p16dg/cp16/cp16dg/p32/p32dg/cp32/cp32dg`. Input width is 1–256 qubits.
Probability, Pauli expectation and marginal distribution queries use the
existing JSON format and all-zero input. Geometry, automatic backend selection,
arbitrary rotation angles and `simplify: "exact"` are not implemented here.

Defaults are 4096 Pauli terms, 10 million work units and 4096 coefficient bits,
shared across the **whole query batch**. Each query has its own pullback;
request-local gate images are cached. A joint k-site projector starts with 2^k
terms and is rejected before allocation if it exceeds the term cap. This is
not the wide-projector method already provided by `clifford_frame`.

A work unit counts a gate scan, term visit, emitted transition, or explicitly
budgeted field multiplication/addition. The old fixed gate-image builder is
reused on matrices of at most 8 by 8; its internal arithmetic is not included
in these work units. `local_images_built` records such images. Work counters
are representation-specific, not CPU instruction counts. Term caps bound each
live expansion, not total resident memory or stored transition certificates.
The fresh calculator worker enforces the existing whole-batch wall timeout;
the direct Python APIs have no wall or RSS cap.

If any query exceeds a resource limit, **all answers are discarded**, including
a completed prefix. No nonzero coefficient is truncated. Completed reports
have an `error_ledger`: exact arithmetic error 0, analytic truncation error 0,
and separate outward decimal enclosures on each value. This describes the
specified ideal calculation; it makes no claim about physical noise or model
error. Failed batches have no successful zero-error ledger.

## Theory reviewed and what is actually used

[Source pins](observer_source_pins.json) contain commit IDs, complete-file
hashes, links and review boundaries. No source repository is modified.

| Source | Result used or boundary established | Calculator consequence |
| --- | --- | --- |
| RKF MR-04, Future-Complete Linear Recognition | The observation row space must be closed under every declared future action | Exact gate-specific transition rows for `future_bank`; no minimum-rank claim |
| RKF MR-06, Guarded Lopa | A record sufficient now need not admit correct future updates | Delayed-reveal tests; no pruning merely because a term currently has zero source expectation |
| Morphic Algebra A0 and certification status | Absorption/congruence are hypotheses; full-manuscript mathematical certification is false, with open obligations | Prove the specific quantum intertwining relation instead of assuming a universal collapse rule |
| Representation LaTeX, bilateral observer completion | Retain target-relevant blind directions; completion need not be small | Mathematical motivation for retaining every required Pauli coordinate; no small-rank premise |
| NSB2 nonlinear spectral closure | Spectral powers can miss directional/mixed responses; finite jets do not establish all analytic responses | Keep signed X/Y/Z directions, wire labels and cross-gate mixing; spectrum alone does not authorize compression |
| RKF Theorem 45, arithmetic–analytic closure | Arithmetic error and analytic tail have distinct bounds | The exact finite sector has zero arithmetic/truncation error; decimal display remains separately enclosed |
| Recent RH fixed-source packet, BRT-T64–T70 | Bounded-source positivity through L=17/20; all-width positivity and RH remain open | Useful example of residual/error accounting, not a quantum gate-compression premise; RH certificates were not rerun |

The source theorem and this adapter use standard finite-dimensional linear
closure and Heisenberg evolution. Source labels, executable checks and this
qualification do not amount to independent external mathematical review or
proof-assistant certification. Existing EMK geometry, UGD contracts and
Surya/jya recurrence remain separate, unchanged implementations.

## Exact adapter argument

For a supported gate U and Hermitian Pauli P, compute its local image

\[
 U^\dagger P U=\sum_Q t_{P,Q}Q,
 \qquad t_{P,Q}=2^{-k}\operatorname{Tr}(Q U^\dagger P U).
\]

Here k is the gate's one-, two- or three-qubit arity. Every supported U has
entries in K=Q(zeta_32), which is closed under conjugation. Thus the trace
formula lies in K and is evaluated exactly. For Hermitian P and Q the resulting
coefficients are real elements of K. Hermitian Y conventions are retained.
Diagonal phase gates preserve the X mask, so only their local Z masks need
enumeration; no global 4^n matrix is constructed.

For a fixed chronological circuit U1,...,Um, start with the requested Pm and
apply Pt-1=Ut† Pt Ut in reverse order. The trace identity

\[
 \operatorname{Tr}(P_t U_t\rho U_t^\dagger)
 =\operatorname{Tr}(P_{t-1}\rho)
\]

proves each step and their composition. At the final source boundary only,
Paulis with nonzero X mask have zero expectation on |0...0>. Applying that rule
earlier is unsound: H can turn an X into Z. Probability queries use the exact
product of (I+(-1)^b Z)/2 projectors. Completed distributions are checked to
normalize to exactly one.

This fixed-circuit algorithm says nothing about a different future suffix.
The all-future API below has a stronger, separate scope.

## Future bank API and certificate

```python
from native_relational_qc.phase_backend import Phase32Circuit
from native_relational_qc.observer32 import future_bank

alphabet = Phase32Circuit(1).add('h', 0).add('p32', 0)
bank = future_bank(alphabet, {0: 'Z'}, max_terms=4096)
assert bank['retained_dimension'] == 3  # Z, X, Y, in discovery order
```

`circuit.operations` declares an alphabet of distinct **wire-labelled** gates.
Repeated entries are deduplicated. The certificate covers all finite words
over that alphabet, not just the circuit's listed order. An action on another
wire is a different action. Only one Pauli seed is accepted by this first API;
it is not a general arbitrary-linear-observation parser.

Starting with the seed, the compiler adds every Pauli with a nonzero exact
coefficient in each generator image, until no new coordinate appears. If it
finishes, the span V of the retained Pauli basis satisfies U† V U subset V for
every generator. Let R(rho) list all retained expectations. The returned rows
T_U therefore satisfy

\[
 R(U\rho U^\dagger)=T_U R(\rho).
\]

Induction proves equality for every finite chronological word and every density
operator. Its original seed reading is coordinate `seed_index`. No assumption
about a particular initial state is required by this identity. The linear
algebra argument of MR-04 applies over this exact algebraic field as well:
finite spans, kernels and closure need field operations, not floating rank
tolerances. The identities then extend by linearity to physical density
operators with arbitrary complex entries.

The serialized certificate contains the exact basis, action alphabet and its
digest, and one sparse matrix row per action and basis element. Masks are
decimal strings with q0 as the least significant bit; coefficients use the
existing sixteen-rational field encoding. To update the vector of readings,
multiply by the rows for each chronological gate. This is distinct from
backwards pullback of a final observable.

**Coordinate closure can retain more dimensions than the minimum MR-04 linear
row space.** It does not perform exact Gaussian row reduction or prove minimal
additional memory. The `minimality_claim` field is false. The ambient operator
dimension 4^n is reported symbolically as an integer string, never allocated.
Closure may grow exponentially; exceeding a budget raises `ResourceLimit`
and returns no partial closure certificate. A fixed-path pullback may succeed
when an all-future bank is too large.

## Measured qualification

[Frozen protocol](observer_protocol.json), [every run and bank certificate](observer_results.json),
[source/artifact manifest](observer_verification.json) and [test log](observer_test_results.txt)
are committed. Freeze followed implementation tests; it was not blind
preregistration. Each calculator row below has three serial fresh-worker runs,
with reversed case order on alternate repetitions. Wall time includes startup.
RSS is Linux worker high-water memory including imports and setup.

| Circuit / selected observation | Backend | Status in all 3 runs | Peak terms or amplitudes | Median wall s | Maximum RSS MiB |
| --- | --- | --- | ---: | ---: | ---: |
| 5-site graph, X0 Z1 | observer32 | completed | 2 | 0.1060 | 23.5 |
| Same | cyclotomic32 | completed | 32 | 0.1310 | 23.4 |
| 50-site graph, X0 Z1 | observer32 | completed | 2 | 0.1206 | 23.6 |
| Same | cyclotomic32 | support limit | 4096 | 1.1786 | 33.4 |
| 7 local p32 gates on zero input, global X | observer32 | term limit 64 | 64 | 0.1221 | 23.6 |
| Same, amplitude limit also 64 | cyclotomic32 | completed | 1 | 0.0880 | 23.3 |

The graph is H on every wire, CZ along a connected chain, then p32 on every
wire. Its stabilizer X0 Z1 gives the independent analytic value cos(pi/16),
approximately 0.980785280403. This is one selected observable with a small
backwards expansion, not the full graph-state output law. In the reverse
example every diagonal gate fixes the input |0>; global X has expectation 0.
The sparse method sees one amplitude while this observer implementation still
expands the global operator before reaching its source boundary. Failed times
measure time to rejection and are not successful-run speed ratios.

Separate single fresh-process compiler checks retain 3 coordinates for a
50-wire alphabet of local H/p32 gates, and 6 for the two-wire entangling alphabet
H0, CP32(0,1), CX(1,0). These are **not** future banks for the 50-site connected
graph. A cap-2 closure attempt fails without a certificate. No automatic
fallback or best-known-classical performance comparison is claimed.

**279 native test methods passed in 115.683 seconds, with no failures, errors
or skips.** The 11 new methods cover all new local phase images against
independent complex matrices; mixed-gate exact comparisons with the sparse
backend; Qiskit checks of full conjugated operators and forty chronological
updates of a mixed density matrix; controlled gates, Y signs and wire ordering;
delayed-reveal counterexamples; graph and reverse resource boundaries;
whole-batch late failures; width, gate, projector and timeout rejection.

Replay the frozen protocol from the commit containing it:

```bash
python -m unittest discover -s tests -p 'test_native*.py' -v
python -m native_relational_qc.observer_qualification --run \
  --out /tmp/observer-replay.json
```

No 2056-qubit arbitrary-phase execution, larger Shor instance, new quantum
hardware capability, quantum advantage or universal small representation has
been established by this upgrade. A next bounded experiment is exact row-space
closure against this coordinate-bank baseline, with a retained failure when
the required rank or coefficient size exceeds the declared budget.
