# Exact integer contraction: the 50-qubit, 12-round upgrade

The default factored calculator now evaluates the selected 50-qubit, 12-round
local probability and all-site parity that timed out in the original engine.
The circuit, input state, observables and exact coefficient field are unchanged.
This update reduces arithmetic and inspection overhead; it does not reduce bond
dimension or change the physical model. See the measured results below.

## What changed

The existing MPS tensors remain sparse dyadic coefficients in
`Z[1/2, sqrt(2), i]`. Previously, each scalar multiplication and accumulation in
the readout constructed and normalized another `Dyadic` object. Readout instead
uses four integer numerator matrices sharing a power-of-two denominator. NumPy
`dtype=object` matrix multiplication operates on arbitrary-precision **Python
integers**; it does not use floating-point BLAS or fixed-width integer arithmetic.

The boundary identity is unchanged:

\[
E' = \sum_{a,b} O_{ab} A_a^\dagger E A_b.
\]

The implementation first forms `C_a = sum_b O_ab A_b`, then sums
`A_a.adjoint() @ (E @ C_a)`. Each dot product is packed with a proven finite
coefficient bound and decoded exactly. The boundary is normalized once per
output entry. Every nonzero coefficient, complex phase and shared bond is kept.

Separately, a local gate updates the coefficient count and bit maximum only for
the sites it changed. Cached summaries of untouched sites are combined to enforce
the same whole-state stored-coefficient and coefficient-bit guards. This avoids
rescanning every site after every gate. The tests compare these cached summaries
with full storage scans.

## Exact packing argument

For numerator `a + b sqrt(2) + i(c + d sqrt(2))`, encode the polynomial

\[
p(B)=a+bB+cB^3+dB^4.
\]

In a matrix dot product of length `k`, every coefficient of the degree-eight
polynomial `sum_j p_j(B) q_j(B)` is a sum of at most `4k` integer products.
Let `x` and `y` be the maximum numerator bit lengths of the two input matrices.
The implementation chooses

\[
w=\max(2,x+y+\operatorname{bitlength}(4k)+1),\qquad B=2^w.
\]

Every convolution coefficient has magnitude strictly below `B/2`. Consequently
balanced base-`B` decoding recovers all nine signed coefficients without an
ambiguous carry, including negative products and severe cancellation. If those
coefficients are `d_0,...,d_8`, the reduced field coefficients are

\[
\begin{aligned}
a'&=d_0+2d_2-d_6-2d_8,& b'&=d_1-d_7,\\
c'&=d_3+2d_5,& d'&=d_4.
\end{aligned}
\]

The two denominator exponents add. Reduction uses only `sqrt(2)^2=2` and
`i^2=-1`. A nonzero remainder after nine digits raises an arithmetic error.
This is ordinary signed Kronecker substitution for a finite exact contraction,
not a claim of a new quantum-complexity theorem. Algebraic exactness is relative
to the declared circuit model; testing is not a formal verification of Python
or NumPy.

## Usage and reproducibility

Existing calculator requests use the improved exact contraction automatically.
The result statistics explicitly report `contraction: "integer"`; there is no
approximate backend fallback. The prior scalar path remains available through
the Python API:

```python
from native_relational_qc.factored import probability
from native_relational_qc.stress_benchmark import brickwork

circuit = brickwork(50, 12, 20261018)
result = probability(circuit, {24: 0, 25: 0})
print(result.value.to_dict())
print(result.statistics)
# For bounded comparisons: probability(circuit, query, contraction="sparse")
```

The 1,644-gate two-query example explicitly permits 100 million scalar-product
slots per query. Its command allows 40 seconds for the **entire batch**, including
worker startup. The comparison protocol independently retains the original
20-second **per-query** execution cap.

```bash
python -m native_relational_qc calculate \
  native_relational_qc/calculator_examples/brickwork_50q_12r.json \
  --timeout 40 --out /tmp/brickwork_50q_12r.result.json

python -m unittest discover -s tests -p 'test_native*.py' -v
python -m native_relational_qc.stress_benchmark \
  --protocol native_relational_qc/integer_protocol.json \
  --output /tmp/integer_results.json
```

Runtime requires Python and NumPy; Qiskit/Aer are optional comparison dependencies.
The source revision and installed versions for the recorded measurements are
bound in [integer_verification.json](integer_verification.json). Historical
verification files remain immutable snapshots of their original revisions.

## Resource contract

- Input support remains all-zero initial state, named exact single-site gates
  and adjacent supported two-site gates. This does not extend the factored
  backend to arbitrary angles, nonadjacent routing, noise or dynamic operations.
- Bond, stored-coefficient, temporary-coefficient, coefficient-bit and work
  budgets still fail without a guessed answer. The benchmark controller also
  enforces wall time and sampled process RSS. The in-process API has no wall
  clock or total RSS cap.
- Dense boundary allocations are checked against the coefficient-count limit
  before matrix multiplication. This can reject a case the sparse readout could
  fit; `contraction="sparse"` remains an explicit option.
- `scalar_products` now counts dense ring-product slots, including zero slots,
  for integer matrix multiplications, plus the existing forward/suffix work.
  It is conservative relative to the sparse path's nonzero counter and is not
  an instruction count. Local scaling, packing and decoding have additional
  cost. The calculator's default ten-million work cap is unchanged; the saved
  12-round parity example requests the larger explicit allowance.
- `peak_packing_digit_bits` measures one packing digit, not a field coefficient.
  Packed integers may use nine such digits during multiplication. Numerator
  matrices, packed matrices and temporary arrays consume additional memory;
  coefficient counts are not total RSS. `max_coefficient_bits` inspects
  canonical dyadic entries, and the final report separately measures process RSS.
- No rank truncation, statevector construction, quantum SDK execution, GPU or
  quantum hardware is used by the native path. Bonds still grow with depth.

## Measurement protocol

The [29-row protocol](integer_protocol.json) was frozen after development pilots.
It is a declared engineering benchmark, not a blind experiment. Each row runs
sequentially in a fresh process with one numerical thread. The primary 12-round
native queries each have three repetitions; other rows have one run. The
reference matrix includes exact expanded/sparse small-circuit calculations,
independent dense and Aer MPS calculations, a second seed, and 16-round failures.
Aer requests no MPS truncation but still uses floating-point arithmetic.

[integer_baseline.json](integer_baseline.json) contains a fresh same-host run of
the unmodified `8004981` engine made before any edits. Its source hashes and
circuit hashes are retained. Its four rows are single runs. The final comparison
does not reinterpret a timeout as an exact 20-second completion or a fixed
speedup factor. Runtime excludes imports and circuit generation; process peak
RSS includes them. All final outcomes are retained in
[integer_results.json](integer_results.json).

## Recorded results

The run used Python 3.12.14, NumPy 2.3.5, Qiskit 2.6.0 and Aer 0.17.2 on an
8 GiB Linux environment. These are measurements of that environment, not of
the user's PC. Both selected 12-round queries use the same 1,644-gate circuit
hash as the same-host baseline. The local query has a 26-site structural causal
region; parity involves all 50 sites.

| 50-qubit, 12-round query | Original engine, 20 s cap | Integer engine median (3 runs) | Run range | Maximum process peak RSS |
| --- | --- | --- | --- | --- |
| Local P(q24=0, q25=0) | Timeout; no answer | 1.962 s | 1.891–2.012 s | 38.5 MiB |
| All-site Z parity | Timeout; no answer | 17.001 s | 16.961–17.439 s | 57.8 MiB |

Exact coefficient tuples agree across all three repetitions. The second seed
also completes: local 1.980 s, parity 17.619 s. Both previously completed
8-round baseline answers are reproduced algebraically. The sparse/expanded
small-circuit answers also agree algebraically with the integer path.

For the primary 12-round circuit:

\[
P(00)=\frac{2475859145126021431308460617}{9903520314283042199192993792}
+\frac{46178737831515614491}{604462909807314587353088}\sqrt2
\approx0.25010592696462469245.
\]

Its global parity is approximately `-3.9244739402316730e-8`; the full exact
coefficients are retained in the results and calculator example. The two-query
CLI batch completes in **18.318 s calculation / 18.801 s child wall**, with
**55.8 MiB** worker peak RSS. This is one smoke run, distinct from the repeated
per-query measurements. Both certified decimal displays have maximum absolute
display error `5e-25`, with exact rational enclosure checks.

Independent Aer MPS is still faster on the primary 12-round cases: 0.342 s local
and 0.401 s parity, using approximately 103–106 MiB process peak RSS. The observed
absolute differences against the native exact answers are `4.52e-14` local and
`1.67e-17` parity; parity relative difference is `4.26e-10`. Across all eight
completed dense/MPS reference comparisons, the maximum observed absolute
difference is recorded in the verification data. These are numerical comparison
results, not certified bounds on Aer error or a claim of runtime superiority.

All **29 final rows** are retained: 15 completed factored, 2 completed expanded
observer, 2 completed dense, 6 completed MPS, 2 native resource-limit failures and
2 MPS timeouts. At 16 rounds, the native local query exceeds its 100-million
work allowance; global parity exceeds its one-million stored-coefficient
allowance during forward evolution. Neither returns an answer. Both corresponding
MPS rows time out under the same 20-second execution cap.

**128 native test methods passed, with zero failures, errors or skips.** Twelve
new methods cover signed packing, all field-basis products, rectangular products,
mixed denominators, 350-bit coefficients, cancellation, exact phase/control
orientation, cached resource accounting and failure without a guessed answer.
A fresh process also calculates the frozen 50-qubit/8-round answer with all
quantum-SDK imports blocked. The verification manifest binds source, tests,
protocol, raw results and calculator inputs/outputs by SHA-256.

## Closed gates, open gates and assumptions

Closed: the selected 50-qubit, 12-round local/parity computation boundary; exact
phase/sign and coefficient regression checks; explicit resource failure; a usable
calculator input/output example.

Open: deeper circuits under the same budgets, minimum-rank compression, arbitrary
circuit families and general performance superiority over Aer. This is a local
ideal-circuit calculator, with no new physical-qubit or forecasting validation.

No new physical assumptions are introduced. Existing circuit/input/gate
restrictions remain. The additional implementation dependency is exact Python
integer arithmetic through NumPy object arrays, validated against independent
arithmetic and circuit references within the tested scope.
