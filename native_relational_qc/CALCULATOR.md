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
shots. It currently repeats scalar calculations rather than sharing evolution
between outcomes, so select individual observations for large registers.

The example returns P(00)=1/2, YY=-1, and probabilities 1/2 at 00/11 and zero
at 01/10. Phase-sensitive and 50-qubit inputs/results are also saved in
[calculator_examples](calculator_examples).

## Engines and limits

`factored` is the default: product-observer propagation plus exact sparse MPS
contraction. It accepts named single-qubit gates and adjacent
`cx/cz/ch/cs/ct/swap`. `observer` explicitly selects the existing expanded Pauli
engine, which also accepts nonadjacent gates and `ccx`. No automatic backend
switch, routing approximation, gate-name guessing, or arbitrary-angle rounding
occurs. Unsupported gates are rejected before execution.

Named single-qubit gates are `id/x/y/z/h/s/sdg/t/tdg/sx/sxdg` and the native
`r/k/rk` operators. Arbitrary continuous rotations, general QAOA angles, dynamic
measurements, reset and noise are not added by this calculator interface.

| Limit | Default | Meaning |
| --- | --- | --- |
| Wall time | 20 s | Entire child batch including startup; adjustable through `--timeout`, at most 300 s |
| Qubits | 1–256 | Accepted register width, not a performance guarantee |
| Gates | 100,000 | Maximum declared operations |
| Queries | 32 | Unique IDs required |
| Scalar evaluations | 256 | Total across queries; a k-site distribution costs 2^k evaluations |
| Distribution width | 8 sites | Prevent accidental enumeration of a whole large register |
| Work | 10,000,000 | Backend work budget per scalar evaluation |
| Coefficient bits | 4,096 | Backend coefficient budget per scalar evaluation |
| Factored bond | 256 | Allocated representation dimension, not a minimal Schmidt rank |
| Factored coefficients | 1,000,000 | Inspected coefficient-collection cap |
| Observer terms | 100,000 | Expanded Pauli term cap |

Set applicable backend limits with a `limits` object, for example
`"limits": {"max_work": 1000000, "max_bond": 64}` for `factored`, or
`"limits": {"max_terms": 16384}` for `observer`. Unknown fields, duplicate JSON
keys, non-finite JSON constants, repeated query IDs and ambiguous qubit keys are
rejected. Files are limited to 2 MiB. Parent-side input parsing/validation is
bounded by these size caps and is outside the child wall timer.

Each independent query can complete or hit an internal resource limit. Failed
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

The exact answer remains four rational coefficients in the basis
`1, sqrt(2), i, i*sqrt(2)`; real observations have zero imaginary coefficients.
For an answer `a+b*sqrt(2)`, integer square root gives rational lower and upper
bounds on sqrt(2). Multiplication respects the sign of b. Rational endpoints
are rounded outwards to the requested decimal grid, and the reported decimal
is their midpoint.

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

## Recorded verification

[calculator_verification.json](calculator_verification.json) records the current
tests, source hashes, sample outputs and their agreement with the prior exact
50-qubit benchmark. The [factored benchmark](FACTORED.md) remains a historical
performance record. This interface does not change its engine or remove the
12-round timeout boundary, and it does not establish a speed advantage over Aer
MPS. No release, merge or hardware submission is part of this update.


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
