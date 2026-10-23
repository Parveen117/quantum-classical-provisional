# Executable 2056-qubit selected observations

Author: Monty. 23 October 2026.

Historical milestone recorded at commit
`d0b87fca3d7d1667c26ac4e1ed7e5bb7f6c62820`. The subsequent
[Clifford-frame upgrade](CLIFFORD_FRAME.md) adds a third explicit large-register
backend for wide T-phase probabilities. Measurements and the 204-test record
below describe this earlier milestone, not the later revision. Its frozen
runner must be replayed from that commit because source hashes intentionally
reject later changes.

The calculator now accepts up to **2056 ideal circuit qubits** through two
explicit backends: `stabilizer` and `clifford_t`. This implements the first
executable part of [the 2056-site design](DESIGN_2056.md). It performs classical
simulation of the specified observations; it does not manufacture qubits or
establish general efficient simulation of arbitrary 2056-qubit circuits.

Actual 2056-site runs below include global phase-sensitive correlations,
full-assignment Clifford probabilities, a finite-cut EMK tensor, six active T
gates, and a 14,392-gate seeded Clifford circuit checked against an independent
Qiskit tableau. All 39 measured runs met their declared expected outcome,
including 18 deliberate resource/time failures. **204 native tests passed,
with no failures, errors or skips.**

## Implemented interface

| Explicit backend | Register | Gates | Requested observations |
| --- | --- | --- | --- |
| `stabilizer` | 1–2056 | `id/x/y/z/h/s/sdg/sx/sxdg/r/k/rk/cx/cz/swap` | Pauli products; joint Z probabilities via generator elimination; bounded distributions and geometry |
| `clifford_t` | 1–2056 | The same gates plus `t/tdg` | Exact bounded Pauli expansion; marginal projector expansion; bounded distributions and geometry |
| Existing `factored` / `observer` | 1–256 | Existing gate sets and restrictions | Existing exact engines, unchanged width cap |

`LargeCircuit` is an iterative circuit description, not a state allocation.
Its `.state()` method rejects requests: callers must select an observation
backend. Logical nonadjacent CX/CZ/SWAP are admitted in the two new backends;
this is not a hardware connectivity or routing guarantee. CH/CS/CT/CCX are
rejected before simplification. There is no automatic decomposition, backend
fallback, truncation, arbitrary-angle rounding, noise or dynamic measurement
in these new paths. The input state is all-zero.

The public JSON format and certified decimal display are unchanged. Select
`"backend": "stabilizer"` or `"backend": "clifford_t"`; see
[CALCULATOR.md](CALCULATOR.md). Existing `simplify: "exact"` preserves the large
register type and its separate global-phase ledger. The original request hash
and reduced execution hash remain distinct.

Generate and execute the actual phase-sensitive example:

```bash
python -m native_relational_qc.large_register_qualification \
  --example ghz_t --out /tmp/ghz2056-t.json
python -m native_relational_qc calculate /tmp/ghz2056-t.json \
  --timeout 20 --out /tmp/ghz2056-t-result.json
```

The example includes two global correlations, an endpoint probability and the
three-control EMK geometry. Default execution needs no Qiskit, Aer or IBM
Runtime import; a fresh-process import-blocker replay is recorded separately.

## Exact Clifford algorithm

Represent a Pauli row as

\[
P=i^p X^xZ^z,\qquad x,z\in\{0,1\}^n,\quad p\pmod 4.
\]

The masks are Python arbitrary-precision integers. Y is `iXZ`, so a canonical
Hermitian Pauli has `p = popcount(x & z) mod 4`. Products retain order:

\[
(x,z,p)(u,v,q)=(x\oplus u,z\oplus v,p+q+2z\cdot u)\pmod4.
\]

For an ordered circuit U, pull the requested Pauli back as U†PU by visiting
gates in reverse order. Clifford conjugation maps a Pauli to one signed Pauli.
The source expectation on |0…0⟩ is zero if x is nonzero, and otherwise the
retained diagonal sign. A global query therefore does not require a dense
statevector or a complete state tableau.

For k requested computational-basis outcomes b_j, pull back the commuting
signed generators `G_j = (-1)^b_j U† Z_j U`. The probability is

\[
p(b)=2^{-k}\sum_{S\subseteq\{1,\dots,k\}}
\langle0|\prod_{j\in S}G_j|0\rangle.
\]

Only products whose X mask vanishes contribute. Let r be the rank of the
generator X masks over GF(2). Their kernel has dimension k−r. Elimination on
the X columns retains full Z masks and phases in every row product. Its
diagonal residual rows generate that kernel. If any has negative sign, the
sign character on the kernel is nontrivial and its contributions cancel:
probability zero. Otherwise every kernel product contributes +1, yielding
`2^(k-r)/2^k = 2^-r`. This evaluates one full 2056-site outcome without listing
2^2056 outcomes. It does not return the entire distribution.

This is a **Pauli-pullback/stabilizer-generator algorithm**, not an
Aaronson–Gottesman reusable full-state tableau. Efficient stabilizer simulation
is established prior work; see [Aaronson and Gottesman,
quant-ph/0406196](https://arxiv.org/abs/quant-ph/0406196). The contribution here
is its exact integration with the calculator, large-register input, retained
native gates, geometry, guards and reproducible qualification. No new universal
simulation-complexity result is claimed.

## Bounded T-phase extension

Keep an exact dictionary of Hermitian Pauli words and real coefficients in
Q(√2), using the existing Q(√2,i) `Exact` representation. In reverse evolution:

\[
T^\dagger XT=(X-Y)/\sqrt2,\qquad
T^\dagger YT=(Y+X)/\sqrt2,\qquad T^\dagger ZT=Z.
\]

Tdg reverses the corresponding signs. Each affected term splits; identical
words combine with exact arithmetic, and only algebraically zero coefficients
are removed. The source expectation is taken after the complete ordered
pullback. No phase is discarded to meet a budget. A k-site probability starts
with the exact 2^k-term Z-projector expansion and rejects an excessive initial
width before allocation. It does not use the specialized Clifford probability
algorithm automatically, even for a Clifford-only input.

Worst-case term count grows exponentially with the relevant T gates, as well
as with requested projector width. A small T count is not by itself a universal
performance guarantee. The measured six-T product-state example reaches 64
terms; the twelve-T control deliberately fails at the 128-term cap. Raising
the register cap does not resolve the earlier hard random-circuit MPS boundary.

## EMK and phase contract

The engine uses the existing admitted representation `X=RK`, `Y=iR`, `Z=K`,
with `K²=I`, `R²=-I` and `KR=-RK`. Native R/K/RK gates are supported directly.
Conjugation is insensitive to a uniform global phase, but the original ordered
circuit retains it and the optional reducer records its explicit phase factor.
A conjugation record alone is not a phase-complete representation for a future
controlled-U construction; controlled native R is not silently introduced.

The existing finite-cut adapter evaluates
`Q_ab = <H_a H_b> - <H_a><H_b>` and retains both its real information metric and
imaginary curvature. On GHZ+T with controls X⊗2056, Y₀X₁…X₂₀₅₅ and Z₀, the
real tangent rank is 2 and the complex Gram rank is 1. Curvature entries
Ω_yz and Ω_zx equal 1/√2. The full tensor reconstructs exactly from its retained
real basis. This uses [the earlier EMK/CID source contract](EMK_GEOMETRY.md);
it does not derive Einstein equations or validate unrestricted UGD arithmetic
as a quantum coefficient field. The earlier UGD compatibility boundaries remain.

## Limits and measured cost

| Guard | Default / scope |
| --- | --- |
| Register | 2056 maximum, explicitly selected new backends |
| Operations | 100,000; public input also bounded at 2 MiB |
| Per-scalar work | 10,000,000 gate-term visits plus generator row products |
| Exact coefficient bits | 4,096; the full uniform outcome uses 2,057 denominator bits |
| Clifford+T terms | 100,000, at most 1,000,000 when explicitly raised |
| Stabilizer generators | 2,056 requested outcomes, optionally reduced |
| Batch | 32 queries, 256 scalar evaluations; distribution width at most 8 |
| Worker wall time | CLI default 20 s; explicitly adjustable up to 300 s |

Work units are algorithm counters, not machine instructions or constant-time
bit operations. A Clifford expectation uses m gate visits for m gates. A
k-site Clifford probability uses at most km gate visits and O(k²) row products,
each operating on n-bit masks. T expansion visits each retained term at each
gate. Python object, coefficient and temporary-map overhead also consume RAM.
The compiled plan and declared circuit are retained in addition to Pauli rows.
Repeated queries do not share a compiled full-state tableau or evolved state.

An internal resource failure returns no answer for that query. A wall timeout
returns no answers for the entire batch. There is **no hard total-RSS limit**
in this wrapper. `retained_generator_record_bytes` is a component-only snapshot
of pivot integer objects, excluding container and execution overhead; it is
not a memory benchmark. RAM below is the independent whole-worker Linux VmHWM,
including imports, parsing and setup. Parent-process RAM is not included.

Three fresh workers per case were run in fixed round-robin order, with source
and request hashes frozen before measured execution. Successful cases use the
default per-scalar budgets and an explicit **60-second whole-batch timeout**.
Times are medians of the three complete child wall measurements, including
startup and child validation but excluding parent-side validation and separate
reference preparation. RAM is the **maximum** worker peak across those runs.
These are local measurements, not an Aer/Qiskit speed comparison.

| Actual 2056-site batch | Exact qualification | Median wall s | Max peak worker MiB |
| --- | --- | ---: | ---: |
| GHZ global observations | X⊗n=1; Z⊗n=1; local Z=0; endpoint ZZ=1 | 0.119 | 25.8 |
| GHZ full assignment + mismatch | P(0…0)=1/2; unequal endpoints=0 | 2.155 | 25.7 |
| GHZ+T including EMK tensor | global X=1/√2; global Y₀X…=1/√2; ranks 2/1 | 0.552 | 26.7 |
| GHZ+Tdg phase control | same global X and Z probability; global Y₀X…=−1/√2 | 0.345 | 26.0 |
| H on every site, full zero assignment | P(0…0)=2^-2056; X-mask rank 2056 | 2.033 | 25.9 |
| Six T gates with all-site mixed observation | exact 1/8; 64 retained terms | 2.615 | 25.5 |
| Seeded 14,392-gate Clifford | dense 1569-site witness=1; globals=0; P(end 00)=1/4 | 2.466 | 36.7 |

GHZ is H₀ followed by the complete 2055-edge CX chain; every site participates
in entanglement. GHZ+T/Tdg adds the indicated phase on q0. The uniform and
six-T examples are product states, explicitly different from GHZ. For the
six-T case, H acts on all sites, followed by T then H on sites 0–5; the queried
word is Z on those six sites and X on every other site, giving (1/√2)^6=1/8.
The seeded circuit starts with GHZ, then four layers of seeded single-qubit
Cliffords and shuffled disjoint two-qubit Clifford gates. These are logical,
potentially nonadjacent interactions. Its dense witness and endpoint reference
were obtained from Qiskit's independent forward tableau, without calling the
native engine to produce expected values.

Every successful batch completed below 3 seconds in all three recorded runs.
The 60-second benchmark allowance is still reported as used, rather than
retroactively changed to the default. The source/runtime environment is Python
3.12.14, NumPy 2.3.5, with Qiskit 2.6.0 used for independent reference preparation
and tests. Native worker execution uses no quantum SDK.

Six deliberate controls were repeated three times each: term growth above
128; an oversized Clifford+T initial projector; a one-work-unit cap; an
eight-generator cap; a 2048-bit coefficient cap; and a 1 ns worker wall cap.
All returned the intended resource/time status without a fabricated value.
The last is a timeout-handling control, not a timing-resolution measurement.
These failures are retained in the result file, not omitted from the report.

## Evidence and reproduction

- [Frozen protocol, source hashes and independent reference](large_register_protocol.json)
- [All 39 runs, exact answers, failures, time and RSS](large_register_results.json)
- [Verification, SDK-blocked replay and CLI smoke](large_register_verification.json)
- [Complete 204-test output](large_register_test_results.txt)
- [Reproducible qualification runner](large_register_qualification.py)

```bash
# Replay the frozen protocol; no quantum SDK required by this command.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -m native_relational_qc.large_register_qualification \
  --run --out /tmp/large-register-results.json

# Regenerate independent references and a new protocol; requires Qiskit.
python -m native_relational_qc.large_register_qualification \
  --prepare --out /tmp/large-register-protocol.json

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python -m unittest discover -s tests -p 'test_native*.py' -v
```

The runner refuses source changes against its frozen protocol. If developing a
new revision, prepare and identify a new protocol rather than changing old
measurements. Reference setup is correctness evidence only; no performance
ranking against the SDK follows from it. Independent small-circuit comparisons
cover exact matrix gate images, all outcomes of seeded Clifford circuits,
multiple T phases and Qiskit statevectors. Resource, ordering, unsupported-gate,
phase-ledger, geometry and actual 2056-site checks are included.

The qualification profile uses all 2056 sites as data. It does not reserve an
extra eight workspace sites simultaneously. Hardware control, calibration,
noise modeling, error correction and a general deep non-Clifford execution
strategy remain separate development tasks. The earlier 50-qubit MPS and
streaming measurements remain valid records of a different algorithm regime.
