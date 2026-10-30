# Reversible modular arithmetic and five-bit exact Shor

Author: Monty. This revision adds a general constant modular-multiplication
circuit and an explicit `cyclotomic32` backend. Shor now supports five phase
bits with exact 11.25-degree gates. At N=21, a=2, strict continued-fraction
postprocessing succeeds on readouts 5 and 27 and returns factors 3 and 7.

The previous [four-bit phase extension](PHASE_EXTENSION.md) is retained as a
historical qualification. Its frozen protocol belongs to commit
`f31a06a550c5abdb700d00177c5ea568e2cece3d`; replay it there. This revision changes
the shared sparse executor and adds a separately pinned qualification below.

## Arithmetic construction and proof

Let N be an odd modulus, n its register width, and b a known constant coprime
to N. The requested controlled permutation is

\[
|c,x,0\rangle\longmapsto |c,F_{b,c}(x),0\rangle,
\qquad
F_{b,c}(x)=\begin{cases} bx\bmod N&c=1,\ x<N,\\x&\text{otherwise}.\end{cases}
\]

Every circuit operation is an explicit X, CX or CCX. There is no simulator
instruction that directly applies modular exponentiation, no truth table, and
no supplied factor or order. Registers use little-endian wire order.

**Constant addition.** Adding a set bit 2^i is an increment of the register
suffix starting at i. Toggle high targets first, conditioned on every lower
suffix bit being one, then toggle bit i. This reads the pre-increment carry
predicates. A multi-controlled X is decomposed into a clean Toffoli ladder and
its reverse. Compose these increments for the set bits of the constant.

**Modular addition.** Use an n+1-bit accumulator t, with its top bit initially
zero, and a zero flag f. For 0≤t<N and 0≤k<N:

1. Conditionally add k, then unconditionally subtract N modulo 2^(n+1).
2. Copy the high borrow bit into f. If f=1, add N back.
3. Undo the conditional addition of k. The high bit is now 1 exactly when
   the original active addition wrapped around N.
4. Toggle f on the complement of this high bit, then reapply the conditional k.

The result is `(t+k) mod N` when enabled, otherwise t. Both the flag and high
bit return to zero. To see step 3, the temporary value is t for a non-wrapping
addition and t−N for a wrapping one; an inactive addition also gives t.
All temporary signed values have magnitude less than 2^n, so their high bit
distinguishes the cases. Reversing the elementary gate list subtracts k modulo N.

**Multiplication and cleanup.** Compute a validity bit `[x<N]` using reversible
subtraction, borrow-copy and reversal. Combine it with the external control.
For every input bit x_i, add `(b*2^i) mod N` to a clean accumulator when both
the enable bit and x_i are one. This computes b*x modulo N. Swap the work and
accumulator registers under the same enable. Subtract the corresponding
products for b^(-1) modulo N, erasing the old x. Finally uncompute enable and
validity. Multiplication maps valid residues to valid residues; invalid labels
were fixed, so the validity bit can be erased from the final x.

The inverse constant is computed by modular inversion, which does not require
the unknown order or factors. Clean workspace is exactly **2n+4 qubits**. The
construction uses O(n^4) X/CX/CCX gates per controlled multiplication and
O(m*n^4) for m phase bits: O(n) constant increments, O(n^2) decomposed gates
per increment, and O(n) modular additions per multiplication. Construction
itself fails explicitly at its 100,000-gate ceiling. This is a polynomial
construction, not a claim of optimal gate count or easy classical simulation.

## Exact fifth phase bit

Store `A+B*w`, with A,B in Q(ζ16), `w=exp(i*pi/16)`, and `w*w=ζ16`.
Multiplication, conjugation and inversion follow the same quadratic-extension
identities as the previous field. The minimal polynomial is `w^16+1`, so the
sixteen rational coefficients are unique: after translating w to w+1,
Eisenstein's criterion at 2 proves irreducibility. Four- and eight-coefficient input
values embed exactly; serialized outputs explicitly declare their basis.

Named gates `p32/p32dg/cp32/cp32dg` apply phases ±π/16. The old `cyclotomic`
backend keeps Q(ζ16) and rejects these gates; five-bit Shor explicitly requires
`cyclotomic32`. Six phase bits are rejected. Decimal enclosures use rational
half-angle bounds and integer square roots, including severe cancellation.

The shared sparse executor now handles the declared phase-free X/CX/CCX/SWAP
permutations by moving unchanged exact amplitudes. This skips multiplication
by one but retains every primitive visit in the work counter. It is not a
shortcut for an entire arithmetic oracle. Other gates still perform exact
field arithmetic, and all query types reuse one preparation.

## Measured result

All **27 of 27 fresh-process runs completed** and matched the independent exact
reference. All four deliberate resource guards returned no answers.

| Case | Qubits | Gates | Median wall seconds | Max worker MiB | Strict CF success | CF + doubles |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 21 / table / 4 bits | 11 | 1177 | 1.780 | 24.25 | 0.0000% | 29.7985% |
| 21 / arithmetic / 4 bits | 23 | 6715 | 0.573 | 27.70 | 0.0000% | 29.7985% |
| 21 / table / 5 bits | 13 | 3319 | 13.169 | 25.62 | 22.9513% | 55.6917% |
| 21 / arithmetic / 5 bits | 24 | 8416 | 1.861 | 28.88 | 22.9513% | 55.6917% |
| 15, a=7 / arithmetic / 5 bits | 21 | 2593 | 0.442 | 25.13 | 50.0000% | 75.0000% |
| 35 / arithmetic / 5 bits | 27 | 17682 | 2.339 | 34.30 | 0.0000% | 11.7743% |
| 21, a=20 / arithmetic / 5 bits | 24 | 2360 | 0.366 | 24.97 | 0.0000% | 0.0000% |
| 21 / no QFT / 5 bits | 24 | 8293 | 0.574 | 28.45 | 6.2500% | 37.5000% |
| H–P32–H | 1 | 3 | 0.111 | 23.27 | — | — |

Times are medians of three fresh workers including startup, each capped at
20 seconds. Gate counts are logical operations: the arithmetic oracle retains
native CCX, while the historical table builder decomposes each CCX into
H/T/CX. The timing difference therefore includes gate representation and
primitive-permutation execution; **this is not an isolated arithmetic-algorithm
comparison**. The arithmetic circuit uses more workspace and higher measured
RSS. Every run prepares once; the N=21/five-bit arithmetic case peaks at 188
retained amplitudes. Success values are ideal single-readout probabilities for
the stated fixed base, with exact coefficients saved in the results.

The N=35 control still has zero strict-CF success at five bits. Increasing the
precision enough for N=21 does not close the general precision requirement.

The arithmetic and table oracles agree at each matched precision despite
their different circuits and workspace. The gain in N=21 strict CF success
comes from the fifth phase bit. The arithmetic construction closes a separate
oracle-synthesis gap. No timing comparison here isolates the larger field or
establishes a quantum speedup.

At five bits, readout 5/32 has a continued-fraction denominator 6. The candidate
passes `2^6 mod 21 = 1`; the gcd step gives 3 and 7. Readout 27 is also
successful. These are actual calculator readouts, with no replacement by a
known order. Bad-base and no-QFT controls are included; useful classical
candidate probabilities without QFT are not evidence of quantum interference.

## Verification and reproducibility

**268 native test methods passed in 117.076 seconds**, with no failures,
errors or skips. The original four- and eight-coefficient arithmetic modules
and the frame/logic engines remain byte-identical to the previous commit;
the shared sparse phase executor is intentionally updated.

The 12 new methods check all 256 products of field basis elements against
independent Q[w]/(w^16+1) polynomial multiplication, inverses and strict
serialization, 60-place outward decimal bounds, all 1024 entries of the
five-bit inverse-QFT matrix, small modular additions and inverses, and **5712
complete-label controlled multiplier actions** including invalid labels and
clean scratch. Complete arithmetic Shor states for N=15, 21 and 35, plus a
no-QFT control, match a direct function/Fourier formula without phase alignment.
Twelve random complete states and a five-bit table Shor state are also checked
with Qiskit. Qiskit is optional for reference tests, not native execution.

Tests reject unsupported fields, widths, non-coprime multipliers, overlapping
wires and synthesis overflow. Work, support, coefficient and wall failures
return no answer; a late failure discards previously completed query prefixes.

[Frozen protocol](modular_protocol.json) · [All runs](modular_results.json) ·
[Source and artifact hashes](modular_verification.json) ·
[Test log](modular_test_results.txt) · [Disclosed pilot](modular_pilot.json).
The pilot and unit tests preceded the protocol freeze; this is not blind
preregistration. Timings retain every declared run, including failures.

```bash
python -m native_relational_qc.shor --modulus 21 --base 2 \
  --oracle arithmetic --precision 5 --backend cyclotomic32 \
  --out /tmp/shor21-arithmetic5.json
python -m native_relational_qc calculate \
  native_relational_qc/calculator_examples/shor21_arithmetic5.json \
  --timeout 20 --out /tmp/shor21-calculator.json
python -m unittest discover -s tests -p 'test_native*.py' -v
python -m native_relational_qc.modular_qualification --run --out /tmp/modular-rerun.json
```

Replay the frozen protocol at this revision. To qualify changed code, prepare
a new protocol with `--prepare --out /tmp/new-protocol.json`, then pass it to
`--run --protocol /tmp/new-protocol.json`, preserving the historical evidence.

## Closed and remaining work

Closed at this scope: full-register constant modular multiplication with clean
workspace, explicit fifth-bit phase arithmetic, and nonzero strict CF success
for N=21. The implementation adds no new physical assumption. Its mathematical
preconditions are a coprime multiplier, valid modular-adder inputs, and zeroed
scratch; the multiplier handles out-of-range work labels explicitly.

Still open: higher phase precision, better adders and lower gate counts,
hardware routing/error correction, and compression for harder quantum states.
The Shor interface still bounds N to 255 and phase precision to five bits.
Both sparse phase backends admit 1–256 register qubits, default support 4096,
10M whole-batch work units and a 20-second worker wall cap. There is no hard
RSS cap. Geometry and exact reduction remain unavailable on these two backends.
The 24-qubit N=21 circuit has small retained support; it does not demonstrate
arbitrary 24-qubit state capacity or general 2056-qubit Shor execution.
