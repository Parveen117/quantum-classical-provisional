# Flat power-of-two cyclotomic backend (`cyclotomic_pow2`)

The phase backends `cyclotomic`, `cyclotomic32` and `cyclotomic64` build
Q(zeta_16), Q(zeta_32) and Q(zeta_64) as a tower of quadratic extensions over
Q(sqrt(2), i). Each new phase bit needed a new module, and the Shor builder
stopped at six phase bits. This backend replaces the tower with one flat field
for every order M = 2^k, 8 <= M <= 4096.

## Field

An element is

    (1/den) * sum_e c_e zeta^e,   0 <= e < n = M/2,   zeta = exp(2*pi*i/M),

with integer c_e and one positive common denominator. Because
Phi_M(x) = x^(M/2) + 1 for M a power of two, the powers 1, zeta, ...,
zeta^(n-1) are a Q-basis. Multiplication is negacyclic convolution:
zeta^n = -1. Conjugation sends zeta^e to -zeta^(n-e). After gcd normalization
the stored form is canonical, so equality is exact comparison of the stored
bytes. The EMK field Q(sqrt(2), i) embeds as i = zeta^(M/4) and
sqrt(2) = zeta^(M/8) + zeta^(-M/8). Fields of different order are never mixed
implicitly.

**Storage.** The n numerators are stored densely as little-endian signed
bytes of the smallest width (1, 2, 4 or 8 bytes) that holds them. A dense
amplitude at M = 4096 with numerators below 2^15 takes 4 KiB; the earlier
sparse tuple form took about 240 KiB for the same value. Numerators beyond
62 bits are stored as a tuple of Python integers.

**Arithmetic.** Addition, negation, conjugation, rational division and
multiplication by an element with at most four terms (every gate matrix entry
and every phase) are NumPy int64 vector operations, each guarded by an
explicit magnitude bound derived from the storage width. A general product
(amplitude times its conjugate at readout) is one exact int64 convolution
followed by the negacyclic fold, admitted only when
2 * terms * max|a| * max|b| < 2^63. Whenever a bound fails, the operation is
redone over Python integers: a Kronecker-substitution product (one
big-integer multiplication, outward-offset unpacking) or plain integer lists.
No floating point enters any exact value.

**Enclosures.** Real values carry certified decimal enclosures. pi is
bracketed from Machin's formula using alternating partial sums, rounded
outward at scale 2^b. Each cos(2*pi*e/M) is folded into [0, pi/2] and bounded
by two consecutive Taylor partial sums, which bracket the value because the
terms decrease from the second one on; every term is again rounded outward.
The bounds for one order and precision are tabulated once as integers; an
enclosure is then two exact integer dot products with the numerators.
`real_sign` first tries an int64 table whose width is chosen so that the dot
product cannot overflow, and otherwise doubles the precision until the
rational enclosure excludes zero. Like the nested fields, it has a bounded
precision cap and fails with `ResourceLimit` rather than guessing.

## Calculator

```json
{"schema": "nrqc-calculator-v1", "backend": "cyclotomic_pow2", "n_qubits": 1,
 "operations": [["h",[0]], ["p4096",[0]], ["h",[0]]],
 "queries": [{"id": "law", "kind": "distribution", "qubits": [0]}]}
```

- **Gates.** For every power of two 2 <= K <= 4096, `pK`, `pKdg`, `cpK` and
  `cpKdg` mean diag(1, exp(±2*pi*i/K)) and its controlled form. `p16`, `p32`
  and `p64` keep their earlier meanings. The rest of the compact alphabet,
  including nonadjacent controls and `ccx`, is accepted as on `cyclotomic64`.
- **Field order.** The order is the largest K in the request, and at least 8.
  It is reported in `statistics.representation`.
- **Exact output.** Every displayed value is real, and a real element
  satisfies c_(n-e) = -c_e, so it is reported as
  `{"basis": ..., "denominator": "d", "real_numerators": [c_0, ..., c_(n/2-1)]}`
  with trailing zeros removed. Non-real values (only reachable through the
  Python API) keep the sparse form `{"basis": ..., "sparse_coefficients":
  [[e, "p/q"], ...]}`. `from_dict` reads both.
- **Permutation gates.** For circuits of at most 62 wires, each maximal run of
  `id/x/rk/cx/ccx/swap` gates moves all basis labels at once as int64 bit
  operations; the amplitudes are not touched. The work accounting is the same
  as the per-ket loop: one gate visit per gate and one permutation visit per
  ket per gate, failing at the same unit.
- **Readout.** |amplitude|^2 is computed once for the exact normalization
  check and reused by probability and distribution queries.
- **Shared batch.** As on the other phase backends, one preparation is shared
  by the whole batch. `max_work`, `max_coefficient_bits` and `max_branches`
  apply to the whole batch, and any failure discards it.
- **Widths.** This backend alone accepts up to 1,000,000 declared operations,
  distributions over up to 12 sites and up to 4096 scalar outputs per request,
  so that a 12-bit phase register can be read in one batch. Every other
  backend keeps 100,000 operations, 8 sites and 256 outputs.
- **Not supported.** Geometry queries and `simplify: "exact"` are rejected.

## Shor builder

`build(..., field='flat')` builds the circuit for `cyclotomic_pow2` with
precision 1..12. Each QFT distance d is one native controlled phase,
`cp(2^(d+1))dg`. No clean ancilla or seven-T controlled-T construction is
needed. The modular synthesis cap and the Panini rewrite budgets follow the
backend's 1,000,000-operation limit for flat circuits. `field='nested'` keeps
the earlier 1..6-bit circuits unchanged.

`exact_phase_law(..., field='flat')` gives the independent reference law. It
groups x by the value f(x) = a^x mod N, counts for every difference d the
pairs (u, v) with f(u) = f(v) and v - u = d mod 2^m, and forms

    P(y) = sum_d pairs(d) zeta^(y*d) / 2^(2m).

This is algebraically the same equal-value double sum used for the nested
fields, evaluated in O(4^m) integer operations instead of O(4^m) field
products. `assess` checks every calculator probability against it before
decoding. `decode` accepts up to 12 phase bits.

## Measured on this machine

Run `PYTHONPATH=. python benchmarks/shor_pow2_audit.py`. All rows use base 2,
the arithmetic oracle with the Panini rewrite, and one in-process batch with
`max_branches` 65,536. Results are written to
[pow2_shor_audit.json](pow2_shor_audit.json). "calc s" is the calculator
batch: preparation, normalization and the full phase-register readout.

| N | bits | circuit | backend | gates | calc s | peak support | success, CF+doubles | success, CF only |
| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 141 | 6 | nested | cyclotomic64 | 21,080 | 27.26 | 2,908 | 4.8490366% | 0 |
| 141 | 6 | nested | cyclotomic_pow2 | 21,080 | 4.75 | 2,908 | 4.8490366% | 0 |
| 141 | 6 | flat | cyclotomic_pow2 | 20,940 | 1.08 | 2,908 | 4.8490366% | 0 |
| 141 | 8 | flat | cyclotomic_pow2 | 28,896 | 4.83 | 11,724 | 31.5572172% | 4.3549653% |
| 143 | 8 | flat | cyclotomic_pow2 | 31,065 | 4.83 | 14,832 | 6.4962126% | 0 |
| 187 | 8 | flat | cyclotomic_pow2 | 35,152 | 3.11 | 10,048 | 11.6736362% | 0 |
| 141 | 10 | flat | cyclotomic_pow2 | 36,799 | 36.96 | 47,036 | 67.6593021% | 23.8002623% |
| 143 | 10 | flat | cyclotomic_pow2 | 39,544 | 36.14 | 61,424 | 24.9773482% | 12.8593492% |
| 187 | 10 | flat | cyclotomic_pow2 | 44,847 | 20.66 | 40,768 | 43.0547653% | 24.5117931% |
| 21 | 12 | flat | cyclotomic_pow2 | 10,413 | 90.75 | 24,572 | 66.6022223% | 33.2703202% |

Every row passed `assess`, so each probability equals the independent Fourier
law exactly. Compared with the first version of this backend (sparse tuples,
Python-integer products, 100,000-gate cap): the same N = 141 eight-bit circuit
went from 8.6 s to 4.8 s; the ten-bit circuits for N = 141, 143 and 187 could
not be built before and now complete in 21 to 37 s each; the twelve-bit N = 21
run, stopped unfinished after 28 minutes before, completes in 91 s. The
ten-bit N = 143 state holds 61,424 basis labels with 512-slot amplitudes. Peak
process RSS for the whole audit was 405 MiB, most of it the twelve-bit report,
whose 4096 exact probabilities carry 1024 numerators each.

## Limits that remain

- **Support.** The number of basis labels after the inverse QFT is
  2^m times the orbit size of the base, and the calculator admits at most
  65,536 branches. At twelve bits this excludes N = 141 (order 46), N = 143
  (order 60) and N = 187 (order 40); at ten bits all three fit.
- **Scaling.** No general Shor scaling, hardware result or shot statistics
  are claimed. All times are single-process wall-clock readings here.
- **Arithmetic.** A dense product is O(n^2) in C, not an FFT. Values whose
  numerators pass 62 bits run on Python integers and are much slower.
- **Division.** Only division by a nonzero rational is implemented. General
  field inversion is not provided.
