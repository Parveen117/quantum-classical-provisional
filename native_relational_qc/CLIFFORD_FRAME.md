# Exact Clifford frame: wide probabilities with retained T phase

Author: Monty. 23 October 2026.

The explicit `clifford_frame` backend evaluates selected observations on up to
2056 ideal qubits by retaining a Clifford circuit and a bounded sparse residual
state. It removes the previous Clifford+T route's mandatory 2^k initial
projector expansion for a k-site joint probability. It also avoids propagating
every expanded Pauli coefficient through every Clifford gate.

This is a new exact execution choice, not an increase in the register cap.
The existing `clifford_t` backend remains available and can be faster when a
requested observable avoids most of the non-Clifford activity. All earlier
benchmark records remain tied to their original revision.

## Use

Select `"backend": "clifford_frame"` in the existing calculator JSON format.
The admitted gates are the same as `clifford_t`:
`id/x/y/z/h/s/sdg/sx/sxdg/r/k/rk/cx/cz/swap/t/tdg`.
The original gate list is validated before any cancellation or trivial-query
shortcut. CH/CS/CT/CCX remain unsupported here. There is no implicit backend
fallback, continuous-angle approximation or hardware routing.

```bash
python -m native_relational_qc.frame_qualification \
  --example ghz_y_t_full --out /tmp/frame2056.json
python -m native_relational_qc calculate /tmp/frame2056.json \
  --timeout 20 --out /tmp/frame2056-result.json
```

This request measures one specified outcome on **all 2056 sites**, after a GHZ
preparation, a T phase, an Sdg readout rotation and Hadamards on every site.
The result is the exact algebraic number `(1+1/sqrt(2))/2^2056`. The decimal
display may enclose this extremely small number between zero and the display
grid spacing; the exact rational/radical coefficients remain available.

Python callers may use `clifford_frame.expectation(circuit, paulis)` and
`clifford_frame.probability(circuit, assignments)`. The fresh-worker calculator
API supplies the batch wall timeout; direct module calls supply internal
budgets only. Geometry, bounded distributions and optional exact simplification
use the existing calculator contracts.

## State factorization and phase

Maintain

\[
|\psi\rangle=C|v\rangle,
\qquad |v\rangle=\sum_{u\in S}c_u|u\rangle.
\]

C is the ordered Clifford skeleton, obtained by omitting T/Tdg gates from the
physical circuit. The finite dictionary S contains computational-basis labels
in this moving frame, with exact complex coefficients in Q(√2,i). It is a
sparse residual vector, not a list of classical alternatives. Its amplitudes
can interfere after the retained Clifford transformation.

For a Clifford gate D, replace C by DC. For a T gate on site q, use

\[
T=aI+bZ,\quad a=(1+\omega)/2,\quad b=(1-\omega)/2,
\quad \omega=(1+i)/\sqrt2.
\]

Then

\[
TC|v\rangle=C(aI+bQ)|v\rangle,
\qquad Q=C^\dagger Z_qC.
\]

Pull Q back through the Clifford prefix using the existing exact signed-Pauli
rules. If `Q = i^p X^x Z^z`, its action on a residual ket is

\[
Q|u\rangle=i^p(-1)^{z\cdot u}|u\oplus x\rangle.
\]

Update the two corresponding amplitudes, combine equal labels exactly, and
remove only exact zero coefficients. Tdg uses the complex conjugate of ω.
Induction over the original ordered gates proves `U|0…0⟩ = C|v⟩`.
The algorithm checks the exact invariant `sum_u |c_u|² = 1` after preparation.
No floating arithmetic is used for coefficients or quantum observations.

The construction respects the existing EMK representation X=RK, Y=iR, Z=K.
The Clifford circuit retains native R/K/RK operations. Global phase remains
part of the original circuit and optional simplification ledger; ordinary
expectations are phase invariant. The sparse record alone is not a substitute
for the complete controlled-unitary semantics of the retained circuit.

## Joint probabilities without projector enumeration

For requested Z outcomes b_j, form commuting signed generators

\[
G_j=(-1)^{b_j}C^\dagger Z_jC,
\qquad P'=\prod_j(I+G_j)/2.
\]

Eliminate only their X columns, retaining the complete Z masks and phases in
every row multiplication. This changes the generating basis without changing
the common +1 eigenspace or its projector. The result consists of r flip
generators B_i with independent X masks and k−r diagonal generators D_j:

\[
P'=2^{-r}\sum_{s\in\{0,1\}^r}B(s)\,P_D.
\]

First retain only residual kets satisfying every diagonal constraint. Unlike
the previous all-zero-source stabilizer calculation, a negative diagonal row
does **not** automatically make the probability zero: its eigenvalue on each
ket u is `i^p (-1)^(z·u)`. For example, H–T–H followed by outcome 1 selects a
nonzero residual ket and has probability `(1−1/sqrt(2))/2`.

For two accepted labels u and v, solve

\[
x(B(s))=u\oplus v.
\]

Independence of the flip masks gives at most one solution. If none exists, the
matrix element is zero. Otherwise retain the ordered product row
`B(s)=i^p X^x Z^z` and evaluate

\[
\langle v|P'|u\rangle=2^{-r}i^p(-1)^{z\cdot u}.
\]

The phase is evaluated on the **ket u**. It can be imaginary even though the
projector is Hermitian. The final probability is

\[
p=\sum_{u,v}\overline{c_v}c_u\langle v|P'|u\rangle.
\]

The implementation evaluates diagonal contributions and each unordered
off-diagonal pair once, adding twice its real part. This retains interference;
replacing the residual by a mixture of `|c_u|²` would be incorrect.
For a Pauli expectation, one pulled-back Pauli maps each residual ket to at
most one other label, so a dictionary lookup replaces the pair search.

## Complexity and guards

Let m be the Clifford gate count, t the T/Tdg count, B the maximum residual
support during preparation, k the number of specified outcomes, and A the
support remaining after diagonal filtering. Preparation scans O(m+t) gates,
uses up to O(tm) pullback gate visits and O(tB) branch updates, and checks O(B)
exact normalization terms.
A probability uses O(km) gate visits, O(k²) generator row products, O(kB)
constraint checks and at most A(A+1)/2 candidate pairs, each requiring up to
O(k) row reductions. A Pauli expectation uses O(m+B) observation work after
preparation. Bit operations act on n-bit masks and rational coefficient costs
grow with their bit sizes; these counts are not constant-time CPU estimates.

Residual support can still grow to 2^t, and pair evaluation can be quadratic
in that support. The method is exact within its declared resource caps, not a
general efficient solver for arbitrary deep 2056-qubit circuits. Many diagonal
T gates may remain one branch, whereas a small number of active T gates may
double the support repeatedly. A large number of independent non-Clifford
directions remains unresolved.

| Guard | Default | Explicit maximum |
| --- | ---: | ---: |
| Residual branches `max_branches` | 4096 | 65536 |
| Candidate pairs `max_pairs` | 1,000,000 | 10,000,000 |
| Measurement generators `max_generators` | 2056 | 2056 |
| Algorithm work `max_work` | 10,000,000 | 1,000,000,000 |
| Coefficient bits in calculator | 4096 | 8192 |
| Worker wall seconds | 20 | 300 |

The pair cap conservatively counts **all** upper-triangle candidates after
diagonal filtering, including pairs later found outside the flip span. Some
easy marginals can consequently hit this cap. Empty probability assignments
return the already-verified normalization without pair enumeration. The work
counter includes plan scans, gate visits, branch updates, normalization terms,
row products, constraint checks and pair visits. `work_used` is their total,
not an additional kind of work. Input validation and integer
bit complexity are not equated with those counters.

No total process-RSS cap is promised. Old and new amplitude maps may coexist
during a T update; Python objects, circuit storage and temporary arithmetic
also consume RAM. Reports explicitly distinguish
`dense_statevector_constructed: false` from
`sparse_residual_constructed: true`. Query-independent frame preparation is
currently repeated for each scalar call rather than cached across a batch.

## Qualification and comparison

The frozen protocol uses actual 2056-site inputs, the same circuit/query for
each paired comparison, and the same 20-second worker wall cap. Applicable
default work and representation limits are retained; their units and objects
differ by algorithm. No speed comparison against Qiskit or Aer is made.
All result values are checked against analytic exact references. Small-circuit
tests independently reconstruct the entire state C|v⟩ and compare it with
Qiskit, as well as comparing full and marginal probabilities with the prior
exact Pauli engine.

**219 native tests passed in 46.641 seconds, with no failures, errors or
skips.** The frozen comparison contains **66 fresh-worker runs**: 30 completed
calculations, 30 declared resource failures and six wall timeouts. Every
completed value and every failure status matched the protocol. Each row below
has three repetitions; times are median child wall seconds, including startup
and child parsing/validation but excluding parent validation. RAM is the
maximum whole-worker Linux VmHWM across the three runs, including imports/setup.
Parent RAM is excluded; timeout workers do not report VmHWM.

| Actual 2056-site scalar query | Prior `clifford_t` | New frame median s | New max peak MiB |
| --- | --- | ---: | ---: |
| GHZ+T, full zero assignment = 1/2 | Initial projector limit | 2.629 | 26.2 |
| GHZ+T, all-site X readout | Initial projector limit | 4.506 | 28.0 |
| GHZ+T, all-site Y/X readout | Initial projector limit | 4.510 | 28.0 |
| GHZ+Tdg, opposite Y/X phase | Initial projector limit | 4.343 | 28.0 |
| Six T gates, full zero assignment | Initial projector limit | 2.233 | 26.0 |
| Six T gates, global correlation = 1/8 | 2.591 s, exact | 0.642 | 25.3 |
| Twelve T gates, global correlation = 1/64 | All three runs hit 20 s wall cap | 1.332 | 27.5 |
| Twelve T gates, unrelated local Z = 0 | 0.705 s, exact | 1.107 | 27.0 |

The six-T global query is about 4.0 times faster by these paired end-to-end
medians. The new twelve-T global query retains 4096 residual branches and
finishes within the same 20-second cap; the old completion time is unknown.
The local control is slower on the frame route. This supports an additional
execution choice, not blanket superiority or an automatic routing rule.
Per-run timing ranges and old-route RSS are preserved in the result file.

All five wide probabilities use the default 10,000,000 work budget; the
phase-sensitive Y/X cases use 8,464,560 counted work units. Separate controls
lower the branch cap to 128, candidate-pair cap to 128, coefficient cap to 64
bits, work cap to eight units, generator cap to eight, or wall cap to 1 ns.
The nanosecond control checks timeout behavior, not timer accuracy. Failed
queries provide no value, and wall timeouts provide no partial batch.

The GHZ cases entangle all 2056 sites along the complete CX chain. Subsequent
all-site Hadamards read interference in a full-register outcome. Sdg before
readout converts the relative phase into a sine-sensitive probability; T and
Tdg then give `(1±1/sqrt(2))/2^2056`. The six- and twelve-T examples are product
states: H acts on all sites, then T–H acts on the indicated active sites.
Their all-site mixed X/Z correlations are `(1/sqrt(2))^6=1/8` and
`(1/sqrt(2))^12=1/64`. The six-T full-zero probability is
`(1+1/sqrt(2))^6/2^2056`.

The local-control query reads only Z on q2055, which is outside the active T
sites. It intentionally tests a case where observable pullback can avoid work
that frame preparation still performs. Failed runs remain in the evidence.
The pair-limit control intentionally exposes the conservative candidate cap,
even though its analytic probability is simple. Neither is hidden by an
automatic backend switch.

EMK geometry is still computed from exact means and ordered products, with
both information and curvature retained. Tests cover actual 2056-site T/Tdg
circuits, real/complex ranks 2/1 and the opposite signed curvature entry.
No extra physical assumption is introduced beyond the existing ideal
all-zero circuit, admitted gate algebra and Born observation contract.

## Evidence and reproduction

- [Frozen protocol and source hashes](frame_protocol.json)
- [Every paired run and resource control](frame_results.json)
- [Verification, SDK-blocked replay and CLI result](frame_verification.json)
- [Complete test output](frame_test_results.txt)
- [Qualification runner](frame_qualification.py)

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -m native_relational_qc.frame_qualification \
  --run --out /tmp/frame-results.json

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -m unittest discover -s tests -p 'test_native*.py' -v
```

The protocol is source-pinned and refuses a changed implementation. A new
revision requires a separately identified `--prepare` protocol. Historical
large-register qualification at commit
`d0b87fca3d7d1667c26ac4e1ed7e5bb7f6c62820` remains unchanged and must be replayed
from that revision; see [LARGE_REGISTER.md](LARGE_REGISTER.md).

This implementation uses an exact, potentially large common Clifford basis.
It is not a claim to implement the optimized stabilizer-rank algorithms or
their published complexity bounds. Relevant prior work includes
[Bravyi, Smith and Smolin (2016)](https://arxiv.org/abs/1506.01396) and
[Bravyi and Gosset (2016)](https://arxiv.org/abs/1601.07601). The proof above
states the narrower construction actually implemented here. Hardware,
fault-tolerant operation and efficient arbitrary non-Clifford simulation remain
separate goals; this milestone closes the initial-projector bottleneck for
the qualified bounded-frame families.
