# Small exact Shor factoring qualification

**Historical baseline:** the three-bit measurements below belong to commit
`cfabd608b6dc28b1640a507bba4716c7de30e6c0`. The subsequent
[exact phase extension](PHASE_EXTENSION.md) adds four-bit circuits through an
explicit `cyclotomic` backend. Earlier frame engines retain the boundary
described here. Replay this page's frozen protocol at its baseline revision.
The [modular-arithmetic upgrade](MODULAR_SHOR.md) supports five phase bits
and a polynomial multiplier construction on an explicit sparse phase backend.
The latest [six-bit extension and arithmetic rewrite](PHASE64_REWRITE.md)
adds `cyclotomic64` and an optional proof-traced circuit reduction.

Author: Monty. This upgrade adds a runnable order-finding circuit, exact
Clifford+T lowering and verified classical factor extraction to the calculator.
It tests **Shor factoring**; the repository's earlier Shor workloads implement
the separate nine-qubit error-correcting code.

The builder accepts the modulus N and a coprime base a. It receives neither the
order nor the factors. A uniform exponent register controls modular
exponentiation, an inverse QFT produces interference, and continued fractions
propose periods. Each candidate r must satisfy `pow(a,r,N) == 1` before the
even-period gcd step. Only proper divisors are reported.

## Circuit and exactness contract

Two oracle constructions make the compilation assumptions visible:

- `rotation15` implements controlled multiplication by 1, 2, 4 or 8 on the
  **entire four-qubit work register**, using controlled cyclic bit rotations.
  Labels 0 and 15 are fixed; labels 1 through 14 follow multiplication modulo
  15. Each multiplier is computed by repeated squaring from N and a. Work starts
  at 1. This is a special arithmetic identity for N=15, not general arithmetic.
- `table` synthesizes the reversible XOR oracle for `f(x) = pow(a,x,N)` with the
  existing Boolean compiler. It works coherently on all supplied exponents,
  starting its output at zero, and uncomputes its scratch. Its truth table has
  2^m entries, so this route is explicitly an **exponential demonstration**.

Toffoli uses an exact seven-T decomposition. Controlled swaps use that Toffoli;
inverse-QFT controlled S-dagger uses Clifford+T directly. Controlled T-dagger
computes the AND into a clean ancilla, phases it and uncomputes it. Dirty scratch
is not allowed. Full basis-action tests check phase, including a dirty-ancilla
counterexample, and the full inverse-QFT matrix is checked at widths 1, 2 and 3.

The current exact coefficient field is Q(sqrt(2),i). Consequently this builder
supports **1–3 exponent/phase bits**. A four-bit exact QFT needs a sixteenth root
of unity outside that field. Wider precision fails explicitly; there is no
silently rounded rotation. This is a limited-precision Shor demonstration,
without the success guarantee of the usual higher-precision construction.

Registers use least-significant-qubit-first arithmetic. The calculator's
distribution request lists control wires in reverse order, so the displayed
binary string parses directly as the integer y. Scratch starts and ends at zero.
All simulation starts from the all-zero state before the preparation gates.

## Exact outputs and factor extraction

All measured circuits below use three phase bits. Entries are exact ideal
single-readout success probabilities for the stated fixed base, not sampled
shot frequencies and not probabilities of successfully factoring arbitrary N.

| Case | Qubits | Lowered gates | CF denominators only | CF denominators and their doubles | Factors on a successful readout |
| --- | ---: | ---: | ---: | ---: | --- |
| N=15, a=2, rotation | 8 | 134 | 1/2 | 3/4 | 3, 5 |
| N=15, a=2, table | 8 | 113 | 1/2 | 3/4 | 3, 5 |
| N=15, a=7, table | 8 | 113 | 1/2 | 3/4 | 3, 5 |
| N=21, a=2, table | 9 | 355 | 0 | 1/4 | 3, 7 |
| N=15, a=14, trivial-gcd control | 8 | 53 | 0 | 0 | None |
| N=15, a=2, rotation without inverse QFT | 7 | 89 | 1/4 | 5/8 | 3, 5 |

For N=15, a=2 or 7, the phase distribution assigns 1/4 each to y=0,2,4,6
and zero elsewhere. The strict rule succeeds for y=2 or 6. The optional
double-denominator rule also recovers period 4 from y=4 after checking it.

For N=21, a=2, the distribution is `(3,2,1,2,3,2,1,2)/16` in y=0..7 order.
Three phase bits are insufficient for the strict rule here. At y=3 or 5, a CF
denominator of 3 can be doubled to 6; modular exponentiation verifies this
candidate, then the gcds give 3 and 7. Both policies are reported separately.
There is no search through all possible orders, supplied true order, or
substitution of an oracle answer into postprocessing.

The a=14 control has a verified even period but yields only trivial gcds. The
no-QFT control is uniform on all eight readings, demonstrating loss of the
intended phase distribution. Some of its readings still happen to yield valid
classical candidates: a nonzero factoring rate alone would not prove correct
quantum interference.

## Measurement and verification

The [frozen protocol](shor_protocol.json) compares identical ordinary calculator
requests on `clifford_frame` and `jya_frame`, three fresh processes per case and
backend. Backend order alternates. Each entire eight-outcome batch has a
20-second wall cap and unchanged default scalar resource limits. Peak worker
RSS includes setup and imports; no hard RSS cap is promised.

Correctness tests and one retained [N=15 jya pilot](shor_pilot.json) preceded the
freeze; this is not a claim of blind preregistration. The pilot predates the
assessment input-identity guard and is excluded from the paired summaries.
Every timed run, including any failure, is retained in [shor_results.json](shor_results.json).
Resource and wall-limit controls must return no factoring assessment.

The independent exact reference sums the Fourier phases over pairs u,v for
which `pow(a,u,N) == pow(a,v,N)`. It does not call the circuit simulator or use
the period. Seven full complex-state comparisons with Qiskit also check the
actual lowered circuit against a direct function/Fourier formula, without
global-phase alignment. Exact primitive and full-QFT tests supplement the
floating reference.

**36/36 timed calculations completed and matched the exact reference.** Two
work-limit and two deliberate wall-time controls rejected without factors.

| N / base, circuit | Clifford frame wall s | Jya frame wall s | Peak worker MiB, old / jya |
| --- | ---: | ---: | ---: |
| 15 / 2, rotation | 0.515 | 1.242 | 23.36 / 23.46 |
| 15 / 2, table | 0.446 | 1.808 | 23.36 / 23.46 |
| 15 / 7, table | 0.421 | 1.835 | 23.36 / 23.47 |
| 21 / 2, table | 4.039 | 12.245 | 23.58 / 23.87 |
| 15 / 14, trivial gcd | 0.128 | 0.210 | 23.30 / 23.37 |
| 15 / 2, no inverse QFT | 0.277 | 0.634 | 23.33 / 23.40 |

Times are three-run medians including process startup. The original frame is
faster on all six cases: the jya path takes about **2.41x** as long for the
N=15 rotation circuit and **3.03x** for N=21. All six circuits compile with
zero repeated local blocks and zero recurrence products, so they provide no
repeated-word opportunity for the jya recurrence. Short local fusion adds
overhead and can change residual support. This measurement does not isolate
each cause of that overhead. There is no demonstrated memory benefit.
The saved examples therefore explicitly select `clifford_frame`.

**243 native test methods passed in 56.383 seconds, with no failures, errors or skips.**
The 12 new methods cover primitive, matrix, circuit, postprocessing and resource
checks. See the [test log](shor_test_results.txt), [tests](../tests/test_native_shor.py)
and [verification manifest](shor_verification.json).

## Run it

From the repository root:

```bash
python -m native_relational_qc.shor --modulus 15 --base 2 \
  --oracle rotation15 --backend clifford_frame --out /tmp/shor15.json
python -m native_relational_qc.shor --modulus 21 --base 2 \
  --oracle table --backend jya_frame --out /tmp/shor21.json
```

The result contains the program metadata, original calculator report and both
postprocessing policies. `--example` writes an ordinary calculator request.
The saved [15 input](calculator_examples/shor15.json) and
[21 input](calculator_examples/shor21.json) use the old frame explicitly:

```bash
python -m native_relational_qc calculate \
  native_relational_qc/calculator_examples/shor15.json --out /tmp/phase15.json
python -m unittest discover -s tests -p 'test_native*.py' -v
python -m native_relational_qc.shor_qualification --run \
  --out /tmp/shor-rerun.json
```

Replay the frozen protocol at this upgrade's revision. It hashes all native
Python sources and the new test module and rejects source drift. On an edited
checkout, create a new protocol with `--prepare --out /tmp/shor-protocol.json`,
then run with `--protocol /tmp/shor-protocol.json`; keep previous evidence intact.

## Next development justified by this test

1. Reuse prepared state across the eight distribution outcomes. The calculator
   currently prepares the same circuit eight times; a prepared-query interface
   could remove that repeated work with explicit shared resource accounting.
2. Add higher phase precision through a wider exact cyclotomic representation,
   or a separately specified approximate-rotation path with certified error
   bounds. This requires phase handling and backend integration, not only a
   larger register-size setting.
3. Build reversible modular add/multiply/exponentiation for general N, retaining
   clean scratch and full operator tests, then qualify larger nontrivial cases.

The current 2056-site input capability concerns supported structured
observations. These Shor circuits use 7–9 simulated qubits and establish neither
2056-qubit general Shor execution nor polynomial-time classical factoring.
They do not construct a physical processor or establish quantum advantage.

Algorithm references: [IBM's Shor tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/shors-algorithm),
[IBM's order-finding and factoring course](https://quantum.cloud.ibm.com/learning/en/courses/fundamentals-of-quantum-algorithms/phase-estimation-and-factoring/shor-algorithm),
and [Shor's original paper](https://arxiv.org/abs/quant-ph/9508027). The bounded
precision, compiler choices and measured results above describe this repository.
