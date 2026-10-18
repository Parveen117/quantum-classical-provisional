# Exact factored evaluation: recovered stress-test cases

The new backend recovers exact scalar answers on circuits where the previous
expanded Pauli observer exhausted its budget. It keeps a product observable
factored, then contracts the remaining circuit using exact sparse matrix-product
state (MPS) factors. The frozen comparisons below also retain its deeper failures.
Aer MPS is still faster on these tests. This is an implementation improvement
using tensor-network structure, not evidence of a new general quantum speedup.

## Mathematical contract

For the all-zero input, the requested answer is

\[
v=\langle 0^n|U^\dagger O U|0^n\rangle.
\]

A Pauli-string expectation has a product observable. A selected output
probability uses `(I+Z)/2` or `(I-Z)/2` on each queried site, and identity elsewhere.
The evaluator performs three exact steps:

1. Remove gates outside the structural backward causal cone of the query. This
   is an exact identity cancellation, not a low-entanglement assumption.
2. Write `U = V W` in execution order and propagate the suffix `V` backwards
   while `V† O V` can be retained as a product of local Pauli sums. Local
   conjugations retain signs and complex phases. A two-site gate is consumed
   only when its implemented rule proves the product form is preserved;
   otherwise suffix propagation stops.
3. Apply `W` forwards to sparse exact MPS factors and contract the returned local
   operators. A controlled gate uses `P0 ⊗ I + P1 ⊗ G`, with a shared bond label
   between its two sites. Those labels retain interference and correlations;
   they are summed only by the boundary contraction.

The final boundary update is `E' = sum_ab O[a,b] A[a]† E A[b]`. It is evaluated
as two sparse matrix products. Every nonzero exact entry is retained. There is
no SVD, numerical rank threshold, term truncation, sampling, or dense statevector.
This is a hybrid backward-observer / forward-MPS evaluator, not a pure
Heisenberg MPO implementation. It does not claim a novel tensor-network identity.

Arithmetic stores `(a+b√2+i(c+d√2))/2^k` as integer numerators and an integer
exponent. Named supported gates stay in this ring. `Exact` rational coefficients
remain the public interchange format. Prime residues/CRT are not needed in this
version: the measured failure was expansion count, not big-integer arithmetic.
No claim here relies on certification of a Surya Siddhanta draft.

## What the expansion count means

For the original 50-qubit, 4-round global parity case, after 174 reverse gates
the returned observable is a product of **50 local factors containing 100
coefficients**. Its fully expanded Pauli sum would contain **2^50 terms**.
The backend does not allocate those terms. The next coupled portion of the
circuit is handled by shared bonds; it is not assumed to remain a product.

`prefix_expanded_terms` reports this counterfactual product expansion at the
suffix boundary. It is not the peak term count of the complete circuit.
`peak_stored_coefficients` counts the largest inspected suffix/MPS coefficient
collection; `peak_temporary_coefficients` counts the largest inspected boundary
or intermediate product. Neither is a total process-memory measurement.
`peak_bond` is the allocated exact representation dimension, not a computed
minimal Schmidt rank. The implementation does not perform rank compression.

## Reproduce and use

```python
from native_relational_qc.stress_benchmark import brickwork
from native_relational_qc.factored import expectation, probability

circuit = brickwork(50, 8, 20261018)
answer = probability(circuit, {24: 0, 25: 0})
print(answer.value.to_dict())       # exact coefficients
print(answer.statistics)            # cost and factorization evidence
parity = expectation(circuit, {q: "Z" for q in range(50)})
```

From the repository root, with the optional reference dependencies installed:

```bash
python -m unittest discover -s tests -p 'test_native*.py' -v
python -m native_relational_qc.stress_benchmark \
  --protocol native_relational_qc/factored_protocol.json \
  --output /tmp/factored_rerun.json
```

The backend supports `CompactCircuit` named single-site gates and adjacent
`cx/cz/ch/cs/ct/swap`. Nonadjacent interactions require explicit routing;
unsupported gates fail, including when the query would hide them. Arbitrary
angle QAOA, dynamic measurement, noise, and arbitrary input states are not added
by this backend. Those require separate representations or existing engines.

API defaults are bond 256, one million inspected coefficients, ten million
counted scalar products, and 4,096 coefficient bits. Resource exhaustion raises
`ResourceLimit` with partial statistics and no answer. Count/bit checks occur
at inspection boundaries; scalar-product counters are implementation work
counters, not a complete CPU instruction count. API calls do not enforce a wall
clock or total RSS limit. Use the isolated benchmark controller for those.

## Measurement protocol

[Frozen protocol](factored_protocol.json), [raw results](factored_results.json),
[development pilot](factored_pilot_results.json), and
[verification manifest](factored_verification.json) are retained separately.
The final protocol was frozen after the four-row pilot; it is not a preregistered
blind experiment. All 57 final rows, including failures and ablations, remain.

The circuit generator, seeds, queries, and operation hashes match the original
[stress experiment](STRESS_BENCHMARK.md). These are one-dimensional random
Clifford+T brickwork circuits with `3r+3` unoptimized layers. Local queries use
only their exact causal region (18 sites in the 50-qubit, 8-round case); global
parity uses all 50 sites. They are selected answers, not all output amplitudes.

Each row uses a fresh, single-thread child process, run sequentially. Execution
time excludes imports/circuit construction and includes cold suffix-table
construction and readout. Total process peak RSS includes imports and setup;
the lower startup footprint of the native package contributes to its lower RSS.
Memory measurements alone do not establish a better asymptotic memory cost.

Final limits: 20 seconds execution, 15 seconds startup, 1,280 MiB process RSS,
bond 256, one million inspected coefficients, 100 million counted scalar
products, and 4,096 coefficient bits. A killed run has no answer; its RSS is a
sampled lower bound and its counters are only the last checkpoint. Reported
kill times include termination latency. Each row is one measurement, not a
statistical timing estimate.

Aer uses floating-point MPS with zero requested truncation threshold and no
maximum bond, or a feasible dense statevector. Floating-point/SVD error still
exists. Algebraic exactness of completed native results follows from the
representation and operations; reference comparisons are implementation checks,
not independent physical measurements or a formal proof of the Python program.

The host is an 8 GiB Linux environment, not a measured laptop. Dense complex128
amplitude payloads alone would require 16 TiB at 40 qubits and 16 PiB at 50.
Those dense runs were not attempted and have no measured time. Dense references
were actually run at 8, 12, 20, and 24 qubits.


## Final measured results

All 57 rows finished through the controller: **19 exact native completions, 10 native timeouts, 16 MPS completions, 7 MPS timeouts, and 5 dense completions**. Every completed comparison agrees within the measured absolute differences recorded below.

The earlier expanded observer needed **29.485 s / 180.9 MiB** for the same 50-qubit, 4-round local answer. It returned no answer for 8-round local (60 s timeout), or 4-round parity (262,145 terms at the cap crossing, 35.499 s). These are historical measurements from the pinned baseline commit, not reruns in the final protocol.

| Qubits | Rounds | Cone sites | Factored | Factored s / MiB | Allocated bond* | MPS | MPS s / MiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 4 | 8 | exact | 0.011 / 31.7 | 4 | complete | 0.010 / 101.3 |
| 40 | 8 | 16 | exact | 0.329 / 32.4 | 16 | complete | 0.021 / 102.8 |
| 40 | 12 | 24 | exact | 19.893 / 41.6 | 64 | complete | 0.291 / 110.9 |
| 40 | 16 | 32 | timeout | 20.425 / 117.0 | 256 | complete | 19.715 / 218.9 |
| 40 | 20 | 40 | timeout | 20.482 / 149.3 | 256 | timeout | 20.498 / 194.2 |
| 40 | 24 | 40 | timeout | 20.511 / 117.4 | 128 | timeout | 20.558 / 195.5 |
| 50 | 4 | 10 | exact | 0.014 / 32.0 | 4 | complete | 0.010 / 101.3 |
| 50 | 8 | 18 | exact | 0.432 / 32.5 | 16 | complete | 0.022 / 104.1 |
| 50 | 12 | 26 | timeout | 20.427 / 42.7 | 64 | complete | 0.334 / 113.5 |
| 50 | 16 | 34 | timeout | 20.455 / 150.3 | 256 | timeout | 20.456 / 200.3 |
| 50 | 20 | 42 | timeout | 20.614 / 124.0 | 128 | timeout | 20.565 / 201.1 |
| 50 | 24 | 50 | timeout | 20.736 / 103.3 | 128 | timeout | 20.680 / 201.9 |

Global all-site parity, 50 qubits:

| Rounds | Factored | Factored s / MiB | Allocated bond* | Stored coefficients* | MPS | MPS s / MiB |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | exact | 0.123 / 32.1 | 4 | 588 | complete | 0.009 / 102.4 |
| 8 | exact | 2.411 / 34.0 | 16 | 9264 | complete | 0.022 / 103.0 |
| 12 | timeout | 20.356 / 61.3 | 64 | 147648 | complete | 0.346 / 110.7 |
| 16 | timeout | 20.492 / 87.8 | 64 | 327936 | timeout | 20.465 / 202.8 |

*For timeouts, these are last-checkpoint peaks, not completed-run values. Different deeper circuits can time out earlier in execution with smaller recorded bonds. No final run reached its RSS or internal resource guard before the wall-clock limit.

A recovered exact local answer at 50 qubits, 8 rounds is:

\[P(00)=\frac{35102818810449}{140737488355328}-\frac{54100655}{34359738368}\sqrt{2}\approx 0.247193798527893.\]

Exact global parity coefficients are retained in the raw JSON; their decimal displays are approximately **1.003552279407049e-9** (4 rounds) and **-1.492080310507497e-8** (8 rounds). These are nonzero expectations, not output-bit guesses. The raw algebraic coefficients, not rounded displays, define the answers.

Small dense reference comparisons, actually executed:

| Qubits | Rounds | Query | Factored s / MiB | MPS s / MiB | Dense s / MiB |
| --- | --- | --- | --- | --- | --- |
| 8 | 4 | local00 | 0.009 / 32.6 | 0.003 / 101.0 | 0.003 / 100.8 |
| 8 | 4 | parity | 0.020 / 32.2 | 0.003 / 101.0 | 0.004 / 100.8 |
| 12 | 8 | local00 | 0.263 / 32.1 | 0.005 / 100.9 | 0.007 / 100.9 |
| 20 | 8 | local00 | 0.273 / 33.1 | 0.008 / 102.0 | 0.512 / 117.3 |
| 24 | 8 | local00 | 0.278 / 33.2 | 0.012 / 101.8 | 9.767 / 356.7 |

Second seed 20261019: 50-qubit, 8-round local completed exactly in 0.421 / 33.2 (s / MiB), versus 0.022 / 103.0 for MPS. Both 16-round cases timed out.

## Ablations and the actual source of improvement

All six ablations returned exactly equal algebraic coefficients to their corresponding main runs.

| 50-qubit query | Settings | Seconds | Stored coefficients |
| --- | --- | --- | --- |
| 4 rounds parity | suffix off; cone on | 0.218 | 1552 |
| 4 rounds parity | suffix off; cone off | 0.168 | 1552 |
| 8 rounds local00 | suffix off; cone on | 0.331 | 2554 |
| 8 rounds local00 | suffix off; cone off | 5.459 | 24640 |
| 8 rounds parity | suffix off; cone on | 6.512 | 24640 |
| 8 rounds parity | suffix off; cone off | 6.403 | 24640 |

The full 50-site MPS calculation also succeeds with both optimizations disabled. Avoiding the globally expanded Pauli representation is therefore the main recovery mechanism. The product suffix improves 8-round parity here (6.512 s without it versus 2.411 s with it). For the local query, causal pruning substantially reduces work (5.459 s with both disabled versus 0.331 s with only the suffix disabled). Its two-gate suffix does not show a timing benefit (0.432 s with it); one-run timing variation is not a speedup claim. The parity ablations with cone enabled/disabled are mathematically identical because every site is observed.

## Remaining failure boundary and verification

The 50-qubit local and global queries still time out at 12 rounds under this budget. For the local query, forward evolution completed and readout reached 14 of 26 causal sites at the last checkpoint; global readout reached 5 of 50. The 40-qubit, 12-round local case completed narrowly at 19.893 s. At greater depth, uncompressed bonds, stored coefficients and boundary contractions grow rapidly. There is no polynomial scaling guarantee and no automatic exact rank compression. A timeout is a resource result, not a proof that the circuit cannot be solved.

The next substantive optimization would need to reduce exact bond or contraction cost while preserving phase and correlations. Renaming coefficients or using prime residues alone would not remove those indices. Approximate truncation would require a separate error contract and must not be reported as an exact answer.

**104 native test methods passed, with no failures, errors or skips**, including 11 new methods covering dyadic arithmetic, product-prefix counts, Bell YY/order controls, control direction, complex readouts, adjacent SWAP, exact expanded-observer equality, ablations and explicit resource failures. The new independent Qiskit tests include 16 seeded small circuits.

- Maximum observed factored vs mps absolute difference: **1.016e-11**, across 13 completed matched pairs.
- Maximum observed factored vs statevector absolute difference: **5.662e-15**, across 5 completed matched pairs.
- Maximum observed mps vs statevector absolute difference: **1.016e-11**, across 5 completed matched pairs.

These differences are observed numerical comparisons, not worst-case error bounds. Tiny parity expectations should not be judged from absolute error alone. There are no IBM Runtime jobs or physical-qubit measurements in this experiment. Historical protocols/results/manifests remain unchanged; their older source hashes are historical snapshots, and the new manifest lists changes relative to them.
