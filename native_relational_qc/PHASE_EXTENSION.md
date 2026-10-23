# Exact sixteenth-root phase extension

Author: Monty. The calculator now accepts an explicit `cyclotomic` backend with
exact 22.5-degree phase gates, retained complex amplitudes and one prepared state
per request. Shor's builder supports four phase bits on this backend. The older
frame engines retain their original field and gate alphabet.

## What the uploaded material contributes

The uploaded operator/prime drafts separate phase, scale and winding and discuss
return/closure operators. These are useful design motivations for preserving
phase information. This implementation uses a separately derived standard
cyclotomic field; it does not execute the drafts' proposed UGD multiplication,
prime-successor operator, PDE, or claimed prime spectrum. Their independently
identified typing and construction gaps are not treated as certified premises.
Source file identities and the distinction between inspiration and implemented
mathematics are recorded in [phase_verification.json](phase_verification.json).

## Exact representation and embedding

Let F = Q(sqrt(2),i), omega = exp(i*pi/4), and z = exp(i*pi/8). Store

\[
v=A+Bz,\qquad A,B\in F,\qquad z^2=\omega.
\]

Multiplication and conjugation are

\[
(A+Bz)(C+Dz)=(AC+BD\omega)+(AD+BC)z,
\qquad \overline{A+Bz}=\bar A+\bar B\bar\omega z.
\]

For nonzero v, its inverse is `(A-B*z)/(A*A-B*B*omega)`. The denominator is in
F and nonzero: omega has no square root in F. Equivalently, z is a primitive
sixteenth root with minimal polynomial `x^8+1`, while F has degree four over Q.
This gives an eight-dimensional rational representation. The embedding of an
old exact value is `(A,0)`; the original arithmetic module is unchanged.

Serialization declares eight rational coefficients and their basis:
`1, sqrt(2), i, i*sqrt(2), z, z*sqrt(2), i*z, i*z*sqrt(2)`.
No angle, amplitude or coefficient is inferred by rounding a float.

The new named gates are `p16`, `p16dg`, `cp16`, `cp16dg`. Here
`p16 = diag(1,z)` and `cp16 = diag(1,1,1,z)`. These are phase gates, with their
stated global phase; they are not substituted with RZ gates. Existing named
gates embed exactly. Qiskit export supplies the corresponding explicit angles
for independent floating reference tests. Import still rejects guessed float
angles, and existing backends reject the new gates explicitly.

Real comparisons and decimal displays use rational bounds on
`sqrt(2)`, `sqrt(2+sqrt(2))/2` and `sqrt(2-sqrt(2))/2`, constructed with integer
square roots. Sign comparison refines until zero is excluded, or rejects if its
precision guard is reached. Exact zero is recognized algebraically. Display
uses outward rounding and reports its maximum absolute error; this is display
error, not simulation approximation or hardware uncertainty.

## Execution and resource contract

`cyclotomic` stores a dictionary from computational basis labels to exact
amplitudes. Gates retain every branch and interference cancellation. State
normalization is checked exactly after preparation. A marginal distribution is
computed in one traversal of that state, and subsequent queries reuse it.

- Register input: 1–256 qubits. This is a bounded sparse execution interface,
  not a claim that general 256-qubit states fit in memory.
- Default retained/transient support cap: 4096 amplitudes; maximum requested
  cap: 65536. A uniform superposition beyond the cap fails explicitly.
- Default work cap: 10,000,000 counted units; coefficient cap: 4096 bits.
  Units count visits and fixed-field additions/products, not CPU instructions.
- Limits apply to **the whole batch**, including preparation and all readouts.
  Reports use `limits_per_batch` and one authoritative `statistics` object.
  Earlier frame reports retain their per-scalar limit contract.
- A resource failure discards the complete batch, including completed query
  prefixes. A wall timeout likewise returns no answers. There is no hard RSS cap.
- Supported queries: probability, Pauli expectation and marginal distribution.
  Geometry and exact circuit reduction are explicitly unavailable on this backend.
  Their implementations remain available on the existing backends.
- The existing maximum 256 scalar outputs per request and 20-second default
  whole-batch worker timeout remain. Decimal rendering is covered by the child wall time, not represented as
  field-work units. Parent input parsing and validation precede that timer and
  remain bounded by the existing input-size caps.

This is a different state representation from `clifford_frame` and `jya_frame`.
Its speed on a small sparse circuit does not imply a general advantage for the
larger number field or for wide entangled circuits.

## Four-bit Shor result

The three-bit builder produces its original lowered circuits. At four bits it
adds one controlled inverse 22.5-degree phase, using `PhaseCircuit`; the existing
controlled T-dagger lowering still requires clean scratch. The fourth bit must
be requested with `backend='cyclotomic'`. Five bits fail explicitly.

N=15, a=2 uses a nine-qubit circuit with the special full-register cyclic
multiplier. N=21, a=2 uses an eleven-qubit, 1177-gate truth-table circuit. The
latter oracle is still exponential synthesis. No factor or order is supplied to
either builder. Full complex-state checks verify restored scratch and phases.

| Fixed-base circuit | CF-only ideal success | CF denominators plus doubles |
| --- | ---: | ---: |
| N=15, a=2, three or four phase bits | 1/2 | 3/4 |
| N=21, a=2, three phase bits | 0 | 1/4 |
| N=21, a=2, four phase bits | 0 | 3/16 + 5*sqrt(2)/64, about 0.297985 |

Four phase bits improve the declared doubled-denominator policy for this N=21
case by about 4.80 percentage points. **The strict continued-fraction policy
still fails on every readout.** Wider precision is still needed for the usual
general Shor success guarantee; this result does not replace it. Every candidate
is verified by modular exponentiation before gcd extraction. The extra candidate
policy remains explicit and is not an exhaustive search for the true order.

The H–P16–H interference control has
`P(0) = (1+cos(pi/8))/2`. Its exact value lies outside the original coefficient
field, demonstrating an observation made possible by the field extension.

## Qualification

The [frozen protocol](phase_protocol.json) compares the same three-bit circuits
on all three backends, then runs four-bit circuits and an independent phase
control. It uses three fresh processes per case/backend and a 20-second wall cap.
Unit tests and a retained [N=21 pilot](phase_pilot.json) preceded the freeze;
this is not blind preregistration. The pilot preceded final readout-normalization
work accounting and is excluded from all timing summaries.

All **36 of 36 timed calculations completed** and matched their independent
exact reference. All four deliberate resource guards returned no answers.
The full native suite passed **256 test methods in 63.755 seconds**, with no
failures, errors or skips; 13 methods are new.

| Circuit | Backend | Median wall seconds | Maximum worker MiB |
| --- | --- | ---: | ---: |
| N=15 rotation / 3 bits | `clifford_frame` | 0.532 | 23.43 |
| N=15 rotation / 3 bits | `cyclotomic` | 0.228 | 23.45 |
| N=15 rotation / 3 bits | `jya_frame` | 1.223 | 23.54 |
| N=21 table / 3 bits | `clifford_frame` | 4.083 | 23.66 |
| N=21 table / 3 bits | `cyclotomic` | 0.524 | 23.65 |
| N=21 table / 3 bits | `jya_frame` | 12.378 | 23.95 |
| N=15 rotation / 4 bits | `cyclotomic` | 0.335 | 23.48 |
| N=15 table / 4 bits | `cyclotomic` | 0.279 | 23.47 |
| N=21 table / 4 bits | `cyclotomic` | 1.982 | 24.20 |
| N=15 bad base / 4 bits | `cyclotomic` | 0.170 | 23.42 |
| N=21 no QFT / 4 bits | `cyclotomic` | 1.828 | 24.08 |
| H–P16–H | `cyclotomic` | 0.092 | 23.19 |

Times are medians of three fresh processes including startup. The new backend
is about 2.34× faster than the original frame for the selected three-bit N=15
circuit and 7.80× for N=21. This comparison combines sparse representation,
whole-distribution preparation reuse and the field extension; it does not
isolate the field's cost or establish a general speedup. RSS is similar at this
scale; these measurements establish no memory advantage. All cyclotomic runs
prepared their state exactly once.

[Every run and assessment](phase_results.json) ·
[Full test log](phase_test_results.txt) ·
[Source and artifact verification](phase_verification.json)

The new tests include all 64 basis products against an independent polynomial
representation, inverses/conjugation, the full 256-entry four-bit inverse-QFT
matrix, exact primitive phase actions, signed decimal enclosures with severe
cancellation, 12 random complete-state Qiskit comparisons and five four-bit
Shor full-state comparisons against both Qiskit and a direct Fourier formula.
No global-phase alignment is used. The complete output distributions also match
an independent exact finite Fourier sum. Bad-base, no-QFT, support, coefficient,
work and wall-time controls are retained. Tests verify batch reuse and that a
late failure cannot expose a completed answer prefix.

## Usage and next step

```bash
python -m native_relational_qc.shor --modulus 21 --base 2 \
  --oracle table --precision 4 --backend cyclotomic --out /tmp/shor21-4.json
python -m native_relational_qc calculate \
  native_relational_qc/calculator_examples/phase16_interference.json \
  --out /tmp/phase16.json
python -m unittest discover -s tests -p 'test_native*.py' -v
python -m native_relational_qc.phase_qualification --run --out /tmp/phase-rerun.json
```

Saved Shor inputs: [15 / four bits](calculator_examples/shor15_4bit.json) and
[21 / four bits](calculator_examples/shor21_4bit.json). Replay the frozen
protocol at this revision; it rejects source drift. To qualify edited sources,
create a separate protocol with `--prepare --out /tmp/new-protocol.json` and run
with `--protocol /tmp/new-protocol.json`, preserving historical evidence.

The phase extension and calculator integration are complete at this declared
scope. General reversible modular multiplication, further precision, and scalable
state compression remain open. No new physical assumption is introduced. These
tests establish no hardware processor, prime-generator theorem, quantum
advantage, or general 2056-qubit Shor execution.
