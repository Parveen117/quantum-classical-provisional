# Six-bit exact Shor and proof-traced arithmetic rewrites

Author: Monty. This revision closes two separate implementation gaps: a sixth
exact phase bit and a bounded, independently checked reduction of lowered
modular-arithmetic gate words. It does not change the default calculator
backend or supply factors or periods to Shor's builder or decoder.

## Source and adapter boundary

The source is RKF's [Paninian operator compiler, PC1–PC4](https://github.com/Parveen117/Recognition-Kernel-Framework/blob/e8e3089745bf7dc0532d01c62a5f660f5658c6f0/operator_foundation/theory/PANINIAN_OPERATOR_COMPILER.md).
Its useful discipline is typed admissible relations, decreasing reductions,
and retained replayable proof records. Here the object is a fixed wire-labelled
register and every gate is an endomorphism of that same register.
Circuit API lists are chronological; the corresponding operator product acts
right to left. The adapter retains the source positions in that API order.

`modular_rewrite.py` is a small Python specialization of that discipline; it
does not execute the general JavaScript compiler, import its cut field, or
claim its diamond/confluence theorem for the bounded search. No linguistic
mantra derivation, RH premise or mock-theta factor oracle enters execution.
The old observer32/linear-bank interfaces keep Q(zeta_32); no implicit
sixth-bit support is added to them.

## Exact sixth phase bit

Write A+B*u with A,B in Q(zeta_32), u=exp(i*pi/32), and u*u=w=zeta_32.
Then

    (A+B*u)(C+D*u) = (A*C+B*D*w) + (A*D+B*C)*u
    conjugate(A+B*u) = conjugate(A) + conjugate(B)*conjugate(w)*u
    inverse(A+B*u) = (A-B*u)/(A*A-B*B*w).

The minimal polynomial u^32+1 is irreducible: translate u to u+1 and apply
Eisenstein at 2. Thus the 32 rational coefficients form an exact basis.
The older 4/8/16-coefficient fields embed as constant components. New phase
names `p64`, `p64dg`, `cp64`, `cp64dg` act by exp(±i*pi/32), on the one state
with all declared gate wires equal to one. Inverse QFT now supports six
control wires with a distinct zero ancilla, restored at the end.

Decimal output is accompanied by rational outward bounds obtained through
integer square roots and half-angle identities. Floating complex conversion
is only a reference/testing convenience, not the calculation or sign test.

## Gate-word equality theorem

For g in X/CX/CCX, let t(g) be its target and C(g) its control set. Its basis
action toggles t(g) by the Boolean product of C(g). These are phase-free
permutation matrices, and g*g=I on every basis input.

Two such gates g,h commute whenever

    t(g) not in C(h) and t(h) not in C(g).

If targets differ, neither gate changes the other's predicate. If they share
a target, both predicates exclude that target and their XOR updates commute.
Shared controls are allowed. This proves equality of the complete matrices,
including global phase, not only equality of measured probabilities.

Consequently, for a surviving word W whose gates all satisfy that predicate
with g, the rule g W g -> W is valid. Each successful reduction removes two
gates, so reduction terminates. The implementation searches at most 64
surviving predecessors by default and stops at every unproved dependency or
non-X/CX/CCX gate. This is a sound bounded reduction, not a unique normal form
or a shortest-circuit theorem. It needs no clean-workspace assumption; the
arithmetic circuit's existing clean-workspace precondition still applies.

Each cancellation records the two original source positions and all surviving
positions crossed. `verify_rewrite` binds both circuit hashes, replays only
those supplied deletions, checks each context dependency independently, and
compares the final surviving word with the supplied result. It never calls the
rewrite search. The Shor builder verifies the certificate before returning a
rewritten program. Failure of a search/proof budget returns no partial circuit.

## Why 141 exposed a precision boundary

At N=141, a=2, the first 32 values 2^x mod 141 are distinct. Tracing out work
therefore leaves the five-bit phase register maximally mixed: all 32 outcomes
have exact probability 1/32, even after inverse QFT. Neither existing decoder
finds a factor from any of these labels.

At six bits, the declared continued-fraction-plus-doubles policy accepts
labels 25 and 39. Its candidate 46 is verified by modular exponentiation;
2^23 mod 141 = 95, so gcd(94,141)=47 and gcd(96,141)=3. These values are
outputs/diagnostics, not builder inputs. The strict-CF policy remains a
separate measurement. The no-QFT control is necessary: a uniform readout can
occasionally produce a useful classically checked candidate too.

## Verification

**302 native test methods pass in 155.426 seconds**, with no failures, errors
or skips. The thirteen new methods include all 1024 products of field basis
elements checked in the independent polynomial ring Q[u]/(u^32+1); all 4096
six-bit inverse-QFT matrix entries with clean scratch; full six-bit arithmetic
Shor states against direct Fourier sums; and twelve random complex-state
Qiskit comparisons without phase alignment.

The rewrite rules are checked on all 1800 three-wire gate-pair/input
combinations, including dirty auxiliary bits. Negative controls exercise
target/control dependencies, phase barriers, tampered proof contexts and
bindings, and proof/search budgets. Phase execution tests include support,
coefficient, work and wall failures and a late failure discarding a completed
query prefix. Existing lower-precision Shor and frame tests remain included.

## Measured results

All **33 of 33** declared timing runs completed, matched the independent exact
Fourier law, and reproduced their request/proof hashes. All four resource guards
returned no answers. Every case used three serial fresh workers; case order
was reversed in the second repetition. The protocol followed unit tests and
gate-count inspection, so this is not blind preregistration.

The six-bit rows below all use base 2, 34 logical qubits, the same zero input,
the same scratch and the same exact sparse backend. Arrows mean unchanged
circuit -> verified Panini-style rewrite.

| N | Elementary gates | Median total wall s | Median compile + verify s | Batch work units |
| --- | ---: | ---: | ---: | ---: |
| 141 | 55,422 -> 21,080 | 25.1193 -> 24.1385 | 0.2791 -> 1.5294 | 3,951,715 -> 1,719,485 |
| 143 | 59,580 -> 23,176 | 27.6671 -> 27.0946 | 0.3236 -> 1.6490 | 4,267,765 -> 1,901,505 |
| 187 | 64,761 -> 25,601 | 19.8385 -> 18.4154 | 0.3605 -> 1.7903 | 4,458,790 -> 1,913,390 |

The rewrite removes 61.96%, 61.10% and 60.47% of the logical gates, respectively.
Total median time decreases by only 3.90%, 2.07% and 7.17%. Compilation/proof
checking is more expensive, and exact phase-field arithmetic remains costly.
The first 141 and 143 rewritten runs were slower than their paired originals;
all runs are retained. Three timings are descriptive measurements, not a
statistical guarantee of a speedup on another machine.

Retained amplitude support is **unchanged** at 2908, 3824 and 2368, respectively.
The compact certificates occupy 727,666, 770,067 and 829,697 bytes. Gate-word
reduction is not state compression and does not eliminate certificate cost.

The five-bit baselines used 33 logical qubits, 44,840 / 49,355 / 51,764 gates
and median wall times 5.6692 / 5.8820 / 6.0318 seconds. Both decoder policies
had zero factoring probability for all three fixed-base cases.

At six bits, N=141 has exact single-readout success

\[
P_{\mathrm{CF+doubles}}=\frac1{32}+\frac9{512}\cos(\pi/16)
\approx 4.8490366257\%.
\]

This is identical before and after rewriting. The strict-CF policy remains
zero, as do both policies for N=143 and N=187 at six bits. The N=141, a=5
bad-base control remains zero. Without inverse QFT, N=141, a=2 has **3.125%**
success from uniformly distributed candidate labels; the QFT contribution is
therefore the increase above this control, not the entire 4.849%. Probabilities
are exact ideal distributions, not hardware shots or sampled success rates.

[Frozen protocol](phase64_protocol.json) · [Every timing run](phase64_results.json) ·
[Independent result and memory audit](phase64_audit.json) ·
[Source/artifact manifest](phase64_verification.json) · [Tests](phase64_test_results.txt).

The raw timing report retains its original `ru_maxrss` memory values. A local
launch test showed that this counter can include the parent's high-water mark
across exec (134,479,872 bytes versus current-executable VmHWM 8,642,560 bytes).
Those raw values are excluded from isolated-worker memory claims. The separate
audit uses Linux `/proc/self/status` VmHWM and keeps its additional runs apart
from the timing medians above. It also reconstructs the summary directly from
the saved 33 rows and rechecks every reference and all four guards.

All six additional memory-audit workers completed and matched the same exact
references and proof digests. One fresh worker per condition gave:

| N | Unchanged peak MiB | Rewritten peak MiB |
| --- | ---: | ---: |
| 141 | 68.34 | 52.80 |
| 143 | 73.67 | 58.50 |
| 187 | 72.36 | 57.65 |

These peaks include compilation, retained rewrite certificates and execution.
They measure this executable on this Linux host, not the theoretical storage
minimum or a memory guarantee for arbitrary states.

## Commands

```bash
python -m native_relational_qc.shor --modulus 141 --base 2 \
  --oracle arithmetic --precision 6 --backend cyclotomic64 \
  --rewrite panini --timeout 60 --out /tmp/shor141-six.json
python -m unittest discover -s tests -p 'test_native*.py' -v
python -m native_relational_qc.phase64_qualification --run \
  --out /tmp/phase64-rerun.json
python -m benchmarks.phase64_audit --out /tmp/phase64-audit.json
```

The Shor CLI result includes the full rewrite certificate. Its normal
calculator request contains only the reduced elementary gate list; the sparse
executor does not shortcut whole modular operators. To replay a certificate,
rebuild the unreduced source with `rewrite='none'` and call `verify_rewrite`.
Historical protocols must be replayed at their pinned historical commits.
After source changes, prepare a new protocol with `--prepare`, preserving the
old measurement record rather than overwriting it.

## Closed, unresolved, and assumptions

Closed at this scope: explicit six-bit exact arithmetic/QFT, independently
verified gate-word reductions, and a matched comparison that separates phase
precision from rewriting. Retained amplitude support can still grow
exponentially. The modulus cap stays 255; precision stays at most six bits;
register width stays 1–256. Defaults are 4096 amplitudes, 4096 coefficient bits
and 10M whole-batch work units. Work counts field operations without pretending
that a 32-coefficient product costs the same CPU time as a 16-coefficient one.

The rewrite defaults to 64 predecessors and 1M search checks; verification
allows 1M crossed gates. Certificate storage and verification have a cost.
No hard RSS cap is imposed. The standard calculator wall cap remains 20s;
this qualification explicitly uses 60s including synthesis/proof work.

Unresolved: a general Shor precision guarantee, faster arithmetic synthesis,
general low-memory simulation, sixth-bit observer banks, and hardware
routing/noise/error correction. No new physical assumption is introduced.
The exact simulator still assumes ideal declared gates, all-zero input and
clean scratch for the arithmetic/QFT construction. This is a finite software
qualification, not a physical quantum processor or a quantum speedup claim.
