# Exact circuit reduction with a phase ledger

The calculator can now remove provably redundant gates before running either
native backend. Select `"simplify": "exact"` in the existing request format.
The default remains `"none"`. The original circuit is retained in the request
hash; the result separately identifies the executed circuit and its global phase.

This helps a circuit containing inverse blocks, repeated involutions or named
gate products that can be combined. It does not compress arbitrary entanglement
or turn a classical PC into a quantum processor. The random 16-round resource
boundary is included in the comparison, alongside the deliberately reducible
50-qubit example.

## Finite rules and guards

The reducer uses exact coefficients in `Q(sqrt(2),i)` and no numerical tolerance.
For the fixed single-qubit alphabet, it constructs a finite pair table directly
from the declared gate matrices. A replacement is admitted only when

\[
U_{\mathrm{later}}U_{\mathrm{earlier}}=\omega^k U_{\mathrm{replacement}},
\qquad \omega=(1+i)/\sqrt2,\quad k\in\{0,\ldots,7\}.
\]

The replacement is another supported named gate or identity. For example,
`H H -> I`, `T T -> S`, `T Tdg -> I`, and `SX SX -> X`. Chronological `X Y`
has operator `YX=-iZ`: its replacement is `Z` with ledger exponent 6.
The native alias `R=-iY` likewise carries phase; `R R` becomes identity with
phase -1. These are ordinary exact operator identities, not new speedup theorems.

The multi-qubit rules are explicitly limited to:

| Chronological pair | Replacement | Global phase |
| --- | --- | --- |
| CX CX, CZ CZ, CH CH | Identity | 1 |
| SWAP SWAP, CCX CCX | Identity | 1 |
| CS CS | CZ | 1 |
| CT CT | CS | 1 |

The same operand roles are required. CZ and SWAP operands and the two CCX
controls may be sorted because those roles are symmetric. CX control and target
cannot be exchanged. `CS CS` retains its conditional phase as CZ: a phase that
occurs only in one control branch is never moved into the global ledger.

A stack per wire records the latest surviving gate. A pair can combine only
when it is the common predecessor on all of the current gate's operands and has
the same operands. Consequently every crossed surviving gate has disjoint
support. For example, `H(0), T(1), H(0)` reduces to `T(1)`, but
`H(0), CX(0,1), H(0)` does not reduce by this rule. Even overlapping gates that
happen to commute are conservatively left in place.

## Correctness and termination

Let `A` and `B` be a permitted pair, and `D` the intervening disjoint operations.
The full matrix identity is

\[
BDA=DBA=\omega^k DC.
\]

Thus the replacement preserves the entire operator, up to the explicitly
recorded phase, in any surrounding circuit and for every input state. Induction
over rewrites gives

\[
U_{\mathrm{input}}=\omega^{\ell}U_{\mathrm{reduced}},
\qquad \ell=\sum k\pmod8.
\]

Every pair rewrite removes at least one gate; alias normalization is a single
finite pass. The stack algorithm therefore terminates with work and storage
linear in input length for this fixed alphabet, apart from the fixed exact-table
initialization. This is a deterministic **local reduction**, not a globally
unique normal form, minimal circuit, or confluence result. For instance, two
different orderings of disjoint X gates can remain different reduced words.

The ledger may be ignored for the calculator's terminal probabilities and Pauli
expectations because it is a unit-modulus *global* phase. An amplitude consumer
must multiply by it. A consumer that coherently controls the complete reduced
program must restore the corresponding control-branch phase. The Python API
returns both the circuit and the ledger to make this obligation explicit.

## Use

```python
from native_relational_qc.compact import CompactCircuit
from native_relational_qc.reduction import reduce_circuit

original = CompactCircuit(2).add('h', 0).add('t', 1).add('h', 0)
result = reduce_circuit(original)
print(result.circuit.operations)  # (('t', (1,)),)
print(result.to_dict())
```

In calculator JSON, add `"simplify": "exact"`. Existing inputs and the default
request hashes are unchanged when the option is absent or `"none"`.
The [phase example](calculator_examples/phase_reduction.json) and its
[saved result](calculator_examples/phase_reduction.result.json) demonstrate
the nontrivial ledger value -i together with a complete Bell-state distribution.
`circuit_sha256` and `gates` always describe the original request;
`execution_circuit_sha256` and `simplification.output_gates` describe execution.
Backend diagnostics count only executed gates. Unsupported gates and routing
are rejected against the original input before reduction, so cancellation does
not silently extend a backend's accepted scope.

The reducer has a 100,000-input-gate default cap, matching the calculator. Its
work is separate from the backend's scalar-product budget. The calculator worker
wall limit covers reduction. There is no new total process-memory guarantee.

```bash
# Generate the deliberately reducible 50-qubit example.
python -m native_relational_qc.reduction_benchmark --example /tmp/echo50.json
python -m native_relational_qc calculate /tmp/echo50.json --timeout 20

# Reproduce the complete comparison and independent exact checks.
python -m native_relational_qc.reduction_benchmark --output /tmp/reduction_results.json
python -m unittest discover -s tests -p 'test_native*.py' -v
```

## Evidence and limits

The fixed benchmark is in [reduction_benchmark.py](reduction_benchmark.py), with
all outcomes in [reduction_results.json](reduction_results.json). It is a declared
engineering comparison chosen after pilots, not a blind experiment. Its
structured case is `B, U, U-dagger`: `B` is 50-qubit, four-round brickwork with
seed 20261018, and `U` is 16-round brickwork with seed 20261023. The complete
4,932-gate program has the same full operator as the 648-gate base by construction.
This demonstrates avoiding redundant work; it is not evidence of simulating
generic 36-round entanglement at four-round cost.

Every row uses a fresh worker, one numerical thread, a 20-second worker wall cap,
and the same limits (bond 256, one million stored coefficients, coefficient bits
4096, and 100 million scalar-product slots). Wall time includes worker startup
and validation; reported calculation time excludes validation/imports but
includes exact reduction. Parent-side validation and circuit generation are not
in the worker wall measurement. Peak RSS includes imports and setup.

The reduced large echo is repeated three times and checked against the exact
base result, each wire's ordered gate sequence and the retained phase. Matching
wire projections certify equivalence by disjoint-gate swaps. The serialized
execution hash can differ from the base hash because disjoint gates may move;
each reported execution hash is checked against the reproduced reduction.
A six-qubit complete echo is also compared to
the separate expanded-observer algorithm. Unstructured 50-qubit, 12- and
16-round local queries are run with both settings, with failures preserved.
Results describe this execution environment, not the user's PC.

Recorded Python 3.12.14 / NumPy 2.3.5 results:

| Case and query | Without reduction | With exact reduction |
| --- | --- | --- |
| 50-qubit echo, all-site Z parity | Coefficient limit; no answer; 18.336 s worker wall | 4,932 -> 648 gates; exact answer; median 1.717 s worker wall (3 runs) |
| 50-qubit random 12 rounds, local P(00) | Exact answer; 2.746 s worker wall | 0 gates removed; same exact answer; 2.850 s worker wall |
| 50-qubit random 16 rounds, local P(00) | Work limit; no answer | 0 gates removed; same work limit; no answer |

The large reduced echo's median calculation time, including reduction, is
0.317 s; its worker-wall range is 1.674--1.817 s. Peak worker RSS is about
26.6 MiB, compared with 194.5 MiB before the unreduced run fails. A failure
time is not a completion time and does not establish a fixed speedup ratio.
The small six-qubit echo also reduces, but its worker wall rises from 0.201 s
to 0.228 s: preprocessing overhead can exceed the saved execution work.
These limits are why reduction is explicit rather than enabled by default.

The 11 new test methods check every ordered pair of the 14 accepted single-gate
names, all supported multi-qubit pair rules, overlap and control-direction
guards, phase-sensitive negative cases, aliases, limits and calculator hashes.
An independent small dense exact oracle also checks 24 seeded mixed three-qubit
circuits on **every input basis state**, including full operator phase. All
139 native test methods passed; see [reduction_test_results.json](reduction_test_results.json).
Finite tests are implementation evidence, not a formal proof of the runtime.

Next development should target a measured remaining cost, such as exact bond
rank reduction with reconstruction certificates. Neither a scalar invariant nor
agreement of current probabilities is a sufficient certificate for merging
states that will later interfere. No such general compression claim is made here.
