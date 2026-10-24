# Native quantum-circuit calculator

The exact engines now accept a user-defined circuit and measurement queries
through one JSON request. The calculator returns exact algebraic answers,
certified decimal enclosures, execution cost and explicit failures. It runs on
the local classical computer; default calculation does not import Qiskit or
connect to IBM. It uses the existing native phase-preserving engines.

## Run

From the repository root, in the Python 3.12 environment:

```bash
python -m native_relational_qc calculate \
  native_relational_qc/calculator_examples/bell.json --out /tmp/bell-result.json

python -m native_relational_qc calculate \
  native_relational_qc/calculator_examples/brickwork_50q_8r.json \
  --timeout 20 --out /tmp/brickwork-result.json
```

The CLI writes JSON to stdout and optionally to `--out`. Use `-` as the input
path to read stdin. Exit codes are 0 for a complete calculation, 1 for an
incomplete/resource/worker failure, and 2 for invalid input. The earlier
`bell`, `ghz`, `bv`, `grover` and `order-memory` commands still work.

## Define your own calculation

```json
{
  "schema": "nrqc-calculator-v1",
  "n_qubits": 2,
  "operations": [["h", [0]], ["cx", [0, 1]]],
  "queries": [
    {"id": "p00", "kind": "probability", "outcomes": {"0": 0, "1": 0}},
    {"id": "yy", "kind": "expectation", "paulis": {"0": "Y", "1": "Y"}},
    {"id": "law", "kind": "distribution", "qubits": [1, 0]}
  ],
  "backend": "factored",
  "decimal_places": 12
}
```

Input is the all-zero state. Gates run in listed order; a controlled gate lists
control first, target second. A probability query specifies final Z-basis
outcomes and marginalizes every unlisted site. A Pauli query returns the
expectation of the product of the listed I/X/Y/Z operators; unlisted sites are
identity. Empty probability/Pauli maps ask for the normalized identity value 1.

For a distribution, output strings follow `qubits` **left to right**. Thus
`[1,0]` and string `"10"` mean q1=1, q0=0. With `[0,1]`, the same string means
q0=1, q1=0. This ordering is explicitly repeated in each result. A completed
distribution is checked to sum to 1 in exact algebra; it is not a histogram of
shots. The original backends repeat scalar calculations between outcomes, so
select individual observations for large registers. The explicit `cyclotomic`
and `cyclotomic32` backends prepare once and share that state across the entire query batch.

The example returns P(00)=1/2, YY=-1, and probabilities 1/2 at 00/11 and zero
at 01/10. Phase-sensitive and 50-qubit inputs/results are also saved in
[calculator_examples](calculator_examples).

## Engines and limits

An additional `"kind": "geometry"` query computes the finite-cut EMK/CID-D2
information and curvature tensor from 1–8 signed Pauli generators. It returns
both tensor halves, distinct real/complex ranks, and exact reconstruction
witnesses for dependent real directions. See [EMK_GEOMETRY.md](EMK_GEOMETRY.md)
for the source contract, request format, proof and UGD compatibility boundaries.
Its distinct nonidentity expectations count toward the same 256-evaluation cap.

`factored` is the default: product-observer propagation plus exact sparse MPS
contraction. It accepts named single-qubit gates and adjacent
`cx/cz/ch/cs/ct/swap`. `observer` explicitly selects the existing expanded Pauli
engine, which also accepts nonadjacent gates and `ccx`.

The new [large-register backends](LARGE_REGISTER.md) explicitly accept 1–2056
sites. `stabilizer` performs exact Clifford Pauli pullback and commuting
generator elimination for joint probabilities. `clifford_t` additionally admits
T/Tdg with bounded exact Pauli expansion. They support
`id/x/y/z/h/s/sdg/sx/sxdg/r/k/rk/cx/cz/swap`, plus `t/tdg` only for `clifford_t`.
They reject `ch/cs/ct/ccx` before simplification. Logical nonadjacent gates are
accepted; this does not supply hardware routing. Both support geometry queries.

The explicit [Clifford-frame backend](CLIFFORD_FRAME.md), `clifford_frame`,
admits the same 1–2056 sites and gate alphabet as `clifford_t`. It retains a
Clifford circuit and an exact sparse residual vector, and calculates wide
joint probabilities by generator elimination and phase-sensitive matrix
elements. It avoids initial 2^k projector enumeration, with separate branch
and candidate-pair limits. It also supports distributions and geometry.

No automatic backend
switch, routing approximation, gate-name guessing, or arbitrary-angle rounding
occurs. Unsupported gates are rejected before execution.

The explicit [jya-frame backend](JYA_FRAME.md), `jya_frame`, uses the same
gate alphabet, width and query types as `clifford_frame`. It combines adjacent
single-qubit words containing T/Tdg, evaluates repeated prefixes by exact
trace/determinant recurrence, and retains every resulting complex coefficient.
An entangling gate or another wire ends a block. Input remains an ordinary
expanded operation list; no repeat syntax, angle rounding or implicit fallback
is added. Work includes input scanning and recurrence arithmetic. The existing
frame branch/pair limits still apply.

The explicit [cyclotomic backend](PHASE_EXTENSION.md), `cyclotomic`, retains
exact amplitudes in Q(exp(i*pi/8)). It supports the existing compact gate
alphabet, including nonadjacent controlled gates and CCX, plus named
`p16/p16dg/cp16/cp16dg` phases of ±22.5 degrees. Input width is 1–256, with
bounded sparse computational-basis support; this is not a wide Clifford-frame
representation. Probability, Pauli expectation and distribution queries share
one preparation. Geometry and `simplify: "exact"` are rejected on this backend.

The explicit [cyclotomic32 backend](MODULAR_SHOR.md) extends this to Q(exp(i*pi/16))
with sixteen rational coefficients and `p32/p32dg/cp32/cp32dg` gates. It retains
the same width, query, support and whole-batch limit contracts. Both sparse
phase backends move unchanged amplitudes for X/CX/CCX/SWAP permutations while
counting every primitive visit; neither skips whole arithmetic circuits.

The explicit [observer32 backend](OBSERVER_RECOGNITION.md) accepts the same
1–256-site phase gate alphabet, but expands selected Pauli observations
backwards without preparing amplitudes. Its default `max_terms` is 4096;
`max_work` and `max_coefficient_bits` default to 10M and 4096. These limits
apply to the whole batch, which is discarded on any resource failure.
Joint projectors still require 2^k initial terms. Geometry and exact circuit
reduction are unavailable. The separate Python `future_bank` compiler
returns exact transition rows for all words of a declared action alphabet;
it does not claim minimum rank or an efficient bank for arbitrary circuits.

Named single-qubit gates are `id/x/y/z/h/s/sdg/t/tdg/sx/sxdg` and the native
`r/k/rk` operators. Arbitrary continuous rotations, general QAOA angles, dynamic
measurements, reset and noise are not added by this calculator interface.

| Limit | Default | Meaning |
| --- | --- | --- |
| Wall time | 20 s | Entire child batch including startup; adjustable through `--timeout`, at most 300 s |
| Qubits | 1–256 or 1–2056 | 2056 only for explicit `stabilizer`/`clifford_t`/`clifford_frame`/`jya_frame`; not a performance guarantee |
| Gates | 100,000 | Maximum declared operations |
| Queries | 32 | Unique IDs required |
| Scalar outputs | 256 | Total across queries; a k-site distribution counts 2^k outputs; cyclotomic shares evolution |
| Distribution width | 8 sites | Prevent accidental enumeration of a whole large register |
| Work | 10,000,000 | Per scalar evaluation on original backends; whole batch on cyclotomic |
| Coefficient bits | 4,096 | Per scalar evaluation on original backends; whole batch on cyclotomic |
| Factored bond | 256 | Allocated representation dimension, not a minimal Schmidt rank |
| Factored coefficients | 1,000,000 | Inspected coefficient-collection cap |
| Observer / Clifford+T terms | 100,000 | Expanded Pauli term cap |
| Stabilizer generators | 2,056 | Requested joint-probability generator cap |
| Frame residual branches | 4,096 | Exact sparse amplitudes, not classical mixture weights |
| Frame candidate pairs | 1,000,000 | All upper-triangle candidates after diagonal filtering, including zero transitions |
| Cyclotomic amplitude support | 4,096 | Per sparse amplitude map, including intermediate maps; requested maximum 65,536 |

Set applicable backend limits with a `limits` object, for example
`"limits": {"max_work": 1000000, "max_bond": 64}` for `factored`, or
`"limits": {"max_terms": 16384}` for `observer` or `clifford_t`, or
`"limits": {"max_generators": 2056}` for `stabilizer`. A stabilizer joint
probability can specify all sites without enumerating outcomes. Clifford+T
probabilities explicitly expand 2^k projector terms for k requested sites and
may therefore reject a wide probability query even when its circuit is easy.
For `clifford_frame` and `jya_frame`, applicable representation limits are `max_generators`,
`max_branches` and `max_pairs`, in addition to work/coefficient bits. For example,
`"limits": {"max_branches": 4096, "max_pairs": 1000000}`. `max_terms` and
`contraction` do not apply to that backend. Its wide probabilities avoid the
initial projector expansion but can still fail on residual or pair growth.
For `cyclotomic` and `cyclotomic32`, applicable limits are `max_work`, `max_coefficient_bits` and
`max_branches`; they apply to one preparation and **all** readouts together.
Its report uses `limits_per_batch` and shared `statistics`, including
`preparation_count`. A resource failure discards the entire batch, even if a
previous query had completed. Work includes amplitude visits and fixed-field
arithmetic; decimal rendering is covered by wall time, not field-work units.
Unknown fields, duplicate JSON
keys, non-finite JSON constants, repeated query IDs and ambiguous qubit keys are
rejected. Files are limited to 2 MiB. Parent-side input parsing/validation is
bounded by these size caps and is outside the child wall timer.

On the original backends, each independent query can complete or hit an internal resource limit. Failed
queries have no value. An unfinished distribution is discarded rather than
returned with a false normalization. A whole-batch wall timeout kills the child
and returns no answers, including any completed prefix inside that child.
There is no hard total-RSS cap in this calculator wrapper. On Linux, successful
worker reports include peak process RSS from `/proc/self/status`, including
imports and setup; other systems may report null.

Python callers can use `calculate(document)` for in-process execution with
backend budgets, or `run_calculation(document, timeout_seconds=20)` for isolated
wall-limited execution. Only the latter imposes the child timeout.

## What the decimal certificate certifies

On the original backends, an exact answer has four rational coefficients in the basis
`1, sqrt(2), i, i*sqrt(2)`; real observations have zero imaginary coefficients.
For an answer `a+b*sqrt(2)`, integer square root gives rational lower and upper
bounds on sqrt(2). Multiplication respects the sign of b. Rational endpoints
are rounded outwards to the requested decimal grid, and the reported decimal
is their midpoint.

The cyclotomic result explicitly declares eight coefficients, adding
`z, z*sqrt(2), i*z, i*z*sqrt(2)` for `z=exp(i*pi/8)`. Its certified real bounds
also enclose `sqrt(2+sqrt(2))/2` and `sqrt(2-sqrt(2))/2` using rational intervals
and integer square roots. The display error contract below remains the same.
The `cyclotomic32` basis contains these eight coefficients and eight more
multiplied by `w=exp(i*pi/16)`. Further rational half-angle bounds give the same
outward display-error contract. Backend and basis identifiers remain explicit.

`maximum_absolute_display_error` is half that interval width and is at most
10^(-decimal_places). A decimal can have one extra digit because it is a
midpoint. Rational answers exactly on the grid have zero display error.
This computation uses no binary floating-point conversion, including when
large exact coefficients almost cancel. The bound concerns **decimal display**;
it does not certify the physical device, circuit-model fidelity or a formal
proof of the Python implementation.

The result hashes the canonical circuit separately from the full normalized
request, so changing an observable changes the request hash while preserving
the circuit hash. Hashes identify inputs; they are not a proof of correctness.

## Reversible logic examples

The [reversible logic layer](REVERSIBLE_LOGIC.md) generates ordinary calculator
requests for exact addition, phase kickback and an arithmetic search. These
examples explicitly use `"backend": "observer"` for CCX and nonadjacent gates:

```bash
python -m native_relational_qc.reversible_logic_demo --example search --out /tmp/search.json
python -m native_relational_qc calculate /tmp/search.json --timeout 20
```

The mathematical interface retains inputs and returns temporary workspace to
zero; its logical gate counts are not physical entropy or energy estimates.

## Optional exact reduction

Optional `"simplify": "exact"` now applies [guarded exact gate reduction](EXACT_REDUCTION.md)
before the selected backend. It removes supported inverse pairs and combines named
gate products while recording the complete global phase. Results retain the
original circuit hash and identify the reduced execution circuit separately.
The default is `"none"`; this does not remove the resource limits on arbitrary
deep circuits. Generate the 50-qubit structured example with:

```bash
python -m native_relational_qc.reduction_benchmark --example /tmp/echo50.json
```

## Integer-contraction upgrade

The default factored engine now uses exact integer matrix contraction. The
selected 50-qubit, 12-round local and all-site parity cases complete under the
original per-query benchmark budget. See [the implementation and measured
scope](INTEGER_CONTRACTION.md), [the input](calculator_examples/brickwork_50q_12r.json)
and [the recorded output](calculator_examples/brickwork_50q_12r.result.json).
Results identify `contraction: "integer"`; all existing exactness and
display-enclosure contracts remain. The example explicitly raises the per-query
work limit and allows 40 seconds for its two-query batch.

## Optional streaming contraction

Set `"contraction": "streaming"` on the factored backend to build and contract
one site at a time using exact signed reuse and bounded integer limbs. The
default remains `integer`; `sparse` and `reuse` are explicit ablation choices.
The explicit `max_work` ceiling is now 1,000,000,000; the default remains
10,000,000. See [the contracts and measured limits](STREAMING_CONTRACTION.md).

The saved 50-qubit, 16-round local request chooses 300,000,000 work units:

```bash
python -m native_relational_qc calculate \
  native_relational_qc/calculator_examples/brickwork_50q_16r_streaming.json \
  --timeout 90 --out /tmp/local16.json
```

## Shor factoring integration

The [small Shor builder](SHOR.md) produces ordinary calculator requests for
modular exponentiation and inverse QFT, then verifies continued-fraction period
candidates before extracting factors. Both frame backends support up to three
control bits through exact Clifford+T lowering. The explicit `cyclotomic`
backend adds a fourth bit with an exact controlled 22.5-degree phase;
`cyclotomic32` adds a fifth with 11.25-degree phases. Six or more bits remain
unsupported. The `arithmetic` oracle constructs modular multipliers from
X/CX/CCX additions, with no truth table; it requires one of these two sparse
phase backends. Saved three-bit inputs:
[15](calculator_examples/shor15.json) and
[21](calculator_examples/shor21.json). The assessment reports both strict CF and
optional doubled-denominator policies, with their distinct success probabilities.
Four-bit inputs and results are documented in [PHASE_EXTENSION.md](PHASE_EXTENSION.md).
For N=21, strict CF success is still zero; the declared doubled-denominator
policy improves from 1/4 to `3/16+5*sqrt(2)/64`, approximately 29.8%.
At five bits, strict CF success is approximately 22.95%, and CF with doubles
approximately 55.69%; see [MODULAR_SHOR.md](MODULAR_SHOR.md) for exact evidence.

## Historical interface verification at 8004981

[calculator_verification.json](calculator_verification.json) records the original
tests, source hashes, sample outputs and their agreement with the prior exact
50-qubit benchmark. The [factored benchmark](FACTORED.md) remains a historical
performance record. That interface-only revision did not change the engine or
remove its 12-round timeout boundary. The subsequent integer-contraction upgrade
is documented separately above. Neither record establishes general superiority
over Aer MPS.


The recorded calculator smoke runs are:

| Input | Requested answers | Calculation s | Child wall s | Peak worker MiB |
| --- | --- | --- | --- | --- |
| Bell, 2 sites | Distribution, YY, XX | 0.006 | 0.100 | 30.1 |
| H–T–H, 1 site | P(0), distribution | 0.004 | 0.101 | 30.3 |
| Random brickwork, 50 sites / 8 rounds | Local P(00), all-site Z parity | 2.939 | 3.290 | 32.5 |

These are single end-to-end smoke measurements; the 50-site batch contains two
queries and is not a new speed comparison against the earlier one-query rows.
Both exact 50-site values equal the previously recorded benchmark coefficients.
The local decimal is `0.2471937985278930165`, enclosed between
`0.247193798527893016` and `0.247193798527893017`; its maximum absolute display
error is `1/2000000000000000000` (5e-19).

**116 native test methods passed with no failures, errors or skips.** The 12 new
methods cover interference, YY signs, marginal bit ordering, exact normalization,
strict input rejection, explicit backend choice, resource failure without guessed
answers, CLI compatibility, a real worker timeout, input hashes, signed decimal
bounds and severe algebraic cancellation. A separate fresh-process import blocker
also verified a Bell calculation while Qiskit/Aer imports were prohibited.
