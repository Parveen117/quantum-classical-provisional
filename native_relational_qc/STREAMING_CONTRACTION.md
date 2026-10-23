# Exact streaming contraction and signed reuse

The calculator has an explicit `"contraction": "streaming"` mode. It constructs
one matrix-product-state (MPS) site, contracts it with the retained observation
boundary, and releases the site before constructing its neighbor. The native
coefficient field, circuit, all-zero input and requested observation are unchanged.
The existing packed-integer mode remains the default and an exact reference.

This is a scheduling and arithmetic upgrade. The allocated MPS bond dimension
still grows with circuit depth; there is no numerical rank cutoff, approximate
state merge or new generic quantum-complexity claim. MPS representations and
contraction are established methods; see [Schollwoeck's review](https://arxiv.org/abs/1008.3477).
The contribution here is the native implementation, the exact arithmetic
contracts below, and bounded, reproducible comparisons with the previous engine.

## Why a whole-state allocation is unnecessary

For a supported controlled gate,

\[
C(U)=P_0\otimes I+P_1\otimes U.
\]

Give each occurrence an internal binary history label. On each neighboring
site, retain that label and apply its local operator in the original gate order.
An adjacent SWAP uses the same three controlled-X expansion as the prior engine.
For a fixed history assignment, each site's factor is

\[
A_q^{s_q}[h_{q-1},h_q]
=\langle s_q|\prod_{t\;\mathrm{in\;local\;order}}L_{q,t}(h)|0\rangle.
\]

Expanding every controlled-gate sum gives the original circuit amplitude as
the contraction of these factors over shared histories. A factor on one site
can therefore be constructed independently of its neighbors. The local order
of noncommuting gates is never changed, and neighboring plans use identical
history-label order. This is the same uncompressed MPS as the previous forward
algorithm, constructed in a different schedule. Tests compare every site entry
with that algorithm, including reversed controls, phase gates and SWAP.

For a product observer, the retained boundary evolves by

\[
E_{q+1}=\sum_{a,b}(O_q)_{ab}(A_q^a)^\dagger E_q A_q^b.
\]

Once this update is complete, the site factor is unnecessary. Keeping the full
boundary retains the correlations needed for all later contractions. An exactly
zero boundary remains zero under every later linear update. The existing
causal-cone pruning and exact product-preserving observer suffix are retained.

The source of the memory saving is storing one site instead of a list of all
sites. Boundary matrices, integer numerator channels, grouping keys and temporary
arrays still consume memory. A coefficient count is not total process RAM.

## Exact signed reuse within a matrix product

The arithmetic kernel identifies only zero vectors or vectors whose **four
integer numerator channels agree up to the same real sign**. Equal magnitudes,
probabilities or norms do not qualify. A phase of i does not qualify either.

If rows of B are signed copies of representative rows, write B = S Bbar, where
S contains only 0, +1 and -1. Then

\[
AB=(AS)\overline B.
\]

Accumulating AS can create exact zero columns, which can be removed together
with their unused inner labels. The resulting product also computes each signed
equal outer row/column once and scatters it with its original sign. Every output
entry is restored. This is a finite algebraic identity for the current matrix
product, not a minimum-rank factorization of the quantum state.

## Binary64 instructions with exact integer results

The default `integer` kernel uses arbitrary-precision signed packing. The new
`reuse`/`streaming` kernel instead splits each integer numerator into signed
base-2 limbs, multiplies those small integer matrices using NumPy binary64, and
reconstructs the answer with arbitrary-precision Python integers. Quantum
amplitudes are never rounded to floating-point approximations.

For inner dimension k, choose

\[
w=\left\lfloor\frac{52-\lceil\log_2 k\rceil}{2}\right\rfloor,
\qquad |x_j|,|y_j|\le 2^w-1.
\]

Every integer product and every partial signed dot sum obeys

\[
\left|\sum_{j\in J}x_jy_j\right|
\le k(2^w-1)^2<2^{52}.
\]

All these integers are exactly representable in IEEE binary64. Ordinary
binary64 multiplication/addition, or fused multiply-add, consequently introduces
no rounding error, in any order of partial sums, even with cancellation. The
result converts exactly through int64 and then to Python integers; the bound is
also far below int64 overflow. Limb shifts, signs, and the relations i^2=-1 and
sqrt(2)^2=2 are applied in Python-integer arrays. Shared dyadic denominators add.

The implementation checks binary64 precision, the bound before multiplication,
and finite integral output within that bound. These output guards are diagnostic;
the exactness argument rests on the bound and the arithmetic model. The declared
backend assumption is a NumPy binary64 matrix product using ordinary binary64
dot-product arithmetic, without reduced-precision or unbounded algebraic
rewrites. The tested NumPy/BLAS environment is recorded in the verification file.
This is not a formal verification of Python, NumPy, BLAS or the processor.

Tests compare against both the existing packed kernel and independent Fraction
field arithmetic, including all field-basis products, 350-bit inputs, mixed
denominators, signed duplicates, exact cancellation and limb-boundary cases.

## Selecting and bounding the path

```python
from native_relational_qc.factored import probability
from native_relational_qc.stress_benchmark import brickwork

circuit = brickwork(50, 16, 20261018)
result = probability(circuit, {24: 0, 25: 0},
                     contraction='streaming', max_work=300_000_000)
print(result.value.to_dict())
print(result.statistics)
```

The in-process call has no wall/RSS cap. The saved calculator example uses a
fresh worker with a whole-batch wall cap:

```bash
python -m native_relational_qc calculate \
  native_relational_qc/calculator_examples/brickwork_50q_16r_streaming.json \
  --timeout 90 --out /tmp/streaming-answer.json
```

Supported `contraction` values for the factored backend are:

| Value | Site storage | Boundary multiplication |
| --- | --- | --- |
| `integer` (default) | All active sites | Existing exact packed Python integers |
| `sparse` | All active sites | Original exact sparse scalar arithmetic |
| `reuse` | All active sites | Signed reuse and bounded exact integer limbs |
| `streaming` | One site at a time | Signed reuse and bounded exact integer limbs |

`reuse` permits an ablation of streaming storage through the Python/JSON API.
The expanded observer backend rejects this option. No mode is selected silently
after a failure. Contraction selection changes the canonical request hash;
the declared circuit hash is unchanged. Omitted selection still means `integer`.

The default work allowance remains ten million per scalar query. The explicit
JSON upper bound is now one billion, matching the factored Python API. The saved
16-round request chooses 300 million. The whole-worker wall cap remains 20 s by
default, with an explicit maximum of 300 s. Raising an allowed maximum is not an
automatic resource increase for existing requests.

In this path, `scalar_products` counts executed dense ring-product slots after
signed reuse, plus local factor/suffix scalar products. It does not count every
limb instruction, grouping comparison or Python operation. Additional counters
record unreused slots and limb products. Work comparisons use these stated
definitions, together with measured wall time and peak RSS.

Stored-coefficient statistics concern one live site in streaming mode. Dense
allocation and temporary-coefficient guards remain. Raw site numerator/denominator
bit sizes give a safe bit bound; if that bound exceeds the requested cap, the
canonical dyadic values are inspected before rejecting. A shared denominator
alone cannot cause a false bit-budget rejection. The report explicitly identifies
this bit statistic. Bond caps, unsupported gates, failed queries and discarded
unfinished distributions retain the existing calculator behavior.

## Validation protocol and scope

All **177 native test methods passed**, with no failures, errors or skips.
The 17 added methods cover arithmetic exactness and negative controls, sitewise
agreement with the original history construction, phase-sensitive queries,
independent dense statevectors, memory-cap improvement on disjoint Bell pairs,
resource failures and the public calculator interface.

The [24-row protocol](streaming_protocol.json) was frozen after adaptive pilots.
All final outcomes are retained in [streaming_results.json](streaming_results.json).
The [pilot record](streaming_pilots.json) is explicitly exploratory: its source
versions and caps varied, and it is not used for final timing claims. Native
comparisons use fixed circuits and queries. Historical 12-round coefficients,
small exact/dense calculations, an adaptive old-kernel exact calculation,
and independent Aer MPS runs provide different reference checks. MPS reference
runs request no truncation but use floating-point quantum arithmetic.

The original 100-million-work/20-second 16-round boundary is measured separately
from the extended 300-million/60-second comparison. The latter gives **both**
kernels the same cap. The old-kernel 400-million/60-second row also timed out.
A separately labeled adaptive 400-million/180-second run completed and supplies
an exact-value reference, not a same-budget timing comparison. A second seed and global parity remain
in the matrix; failed rows are not interpreted as completed answers.

Closed: streaming contraction, exact signed reuse, bounded-limb arithmetic and
the finite tests/results below. Open: minimum-rank compression, arbitrary deep
circuits, the original 16-round budget boundary, and general superiority over
Aer. There is no new hardware, physical energy, noise or forecasting validation.
No physical assumption is added. The new numerical assumption is the bounded
binary64 arithmetic contract above; the previous circuit/input restrictions remain.

## Recorded final results

The 24 frozen rows produced 18 answers, four internal resource failures
and two wall timeouts. All outcomes are retained. The first four small reference
rows may overlap the tail of the test run and are used only for answer checks.
Primary timing rows started after the test suite completed.

| Fixed case | Previous integer path | Streaming path | Interpretation |
| --- | --- | --- | --- |
| 50 qubits, 12 rounds, global Z parity, 3 runs | median 16.769 s; 56.0 MiB peak RSS | median 13.126 s; 36.0 MiB peak RSS | Same exact answer; 21.7% less time and 35.7% less RSS on this case |
| 50 qubits, 12 rounds, local 00 | 2.002 s | 1.845 s | Same exact answer; one run per path |
| 50 qubits, 16 rounds, local 00, original 100M/20 s cap | work limit | work limit | Original boundary remains open |
| Same local case, 300M/60 s cap | 60 s timeout | median 30.814 s across 3 runs; median peak 184.1 MiB | Explicitly increased budget; same cap for both paths |
| Second seed, 16 rounds, local 00, 300M/60 s cap | not measured | 31.102 s | Independent Aer comparison also completed |
| 50 qubits, 16 rounds, global parity, 300M/60 s cap | coefficient limit | work limit | Neither completed |

For the selected 16-round local case, the answer is approximately
**0.24999345603205234**. All three exact answers agree coefficient for
coefficient. The adaptive old-kernel reference completed in 94.193 s and
agrees in all four rational coefficients. Aer MPS completed in 27.241 s;
its floating result differs by 2.99e-14. For the second seed, the Aer
difference is 4.62e-14. This does not establish superiority over Aer;
the benefit is a larger completed exact-native case and reduced memory.

The native exact reference is stored in
[streaming_exact_reference.json](streaming_exact_reference.json), with its
adaptive protocol embedded. [streaming_verification.json](streaming_verification.json)
binds the frozen sources, test evidence, comparison checks, environment and
saved calculator output. The saved CLI replay uses a separate 90 s whole-worker
cap; its timing is not part of the benchmark medians.
