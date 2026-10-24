# Flat power-of-two cyclotomic backend (`cyclotomic_pow2`)

The phase backends `cyclotomic`, `cyclotomic32` and `cyclotomic64` build
Q(zeta_16), Q(zeta_32) and Q(zeta_64) as a tower of quadratic extensions over
Q(sqrt(2), i). Each new phase bit needed a new module, and the Shor builder
stopped at six phase bits. This backend replaces the tower with one flat field
for every order M = 2^k, 8 <= M <= 4096.

## Field

An element is stored as

    (1/den) * sum_e c_e zeta^e,   0 <= e < M/2,   zeta = exp(2*pi*i/M),

with integer c_e, one positive common denominator, and only nonzero terms
kept. Because Phi_M(x) = x^(M/2) + 1 for M a power of two, the powers
1, zeta, ..., zeta^(M/2-1) are a Q-basis. Multiplication is negacyclic
convolution: zeta^(M/2) = -1. Conjugation sends zeta^e to -zeta^(M/2-e). After
gcd normalization the stored form is canonical, so equality is exact
comparison of coefficients. The EMK field Q(sqrt(2), i) embeds as
i = zeta^(M/4) and sqrt(2) = zeta^(M/8) + zeta^(-M/8). Fields of different
order are never mixed implicitly.

Real values carry certified decimal enclosures. pi is bracketed from Machin's
formula using alternating partial sums, rounded outward at scale 2^b. Each
cos(2*pi*e/M) is folded into [0, pi/2] and bounded by two consecutive Taylor
partial sums. These bracket the value because the terms decrease from the
second one on. Every term is again rounded outward. `real_sign` doubles the
precision until the enclosure excludes zero. Like the nested fields, it has a
bounded precision cap and fails with `ResourceLimit` rather than guessing.

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
- **Exact output.** Exact values use the sparse form
  `{"basis": ..., "sparse_coefficients": [[e, "p/q"], ...]}`.
- **Shared batch.** As on the other phase backends, one preparation is shared
  by the whole batch. `max_work`, `max_coefficient_bits` and `max_branches`
  apply to the whole batch, and any failure discards it.
- **Readout widths.** This backend alone accepts distributions over up to 12
  sites, with up to 4096 scalar outputs per request, so that a 12-bit phase
  register can be read in one batch. Every other backend keeps 8 sites and 256
  outputs.
- **Not supported.** Geometry queries and `simplify: "exact"` are rejected.

## Shor builder

`build(..., field='flat')` builds the circuit for `cyclotomic_pow2` with
precision 1..12. Each QFT distance d is one native controlled phase,
`cp(2^(d+1))dg`. No clean ancilla or seven-T controlled-T construction is
needed. `field='nested'` keeps the earlier 1..6-bit circuits unchanged.

`exact_phase_law(..., field='flat')` gives the independent reference law. It
groups x by the value f(x) = a^x mod N:

    P(y) = sum_v |sum_{f(x)=v} zeta^(y*x)|^2 / 2^(2m)

This is algebraically the same equal-value double sum used for the nested
fields. `assess` checks every calculator probability against it before
decoding. `decode` accepts up to 12 phase bits.

## Measured on this machine

Run `PYTHONPATH=. python benchmarks/shor_pow2_audit.py`. All rows use base 2,
the arithmetic oracle with the Panini rewrite, and one in-process batch.
Results are written to [pow2_shor_audit.json](pow2_shor_audit.json).

| N | bits | circuit | backend | gates | calc s | peak support | success, CF+doubles | success, CF only |
| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 141 | 6 | nested | cyclotomic64 | 21,080 | 30.73 | 2,908 | 4.8490366% | 0 |
| 141 | 6 | nested | cyclotomic_pow2 | 21,080 | 2.53 | 2,908 | 4.8490366% | 0 |
| 141 | 6 | flat | cyclotomic_pow2 | 20,940 | 1.76 | 2,908 | 4.8490366% | 0 |
| 141 | 8 | flat | cyclotomic_pow2 | 28,896 | 8.62 | 11,724 | 31.5572172% | 4.3549653% |
| 143 | 8 | flat | cyclotomic_pow2 | 31,065 | 7.76 | 14,832 | 6.4962126% | 0 |
| 187 | 8 | flat | cyclotomic_pow2 | 35,152 | 7.45 | 10,048 | 11.6736362% | 0 |
| 21 | 10 | flat | cyclotomic_pow2 | 8,681 | 39.28 | 6,140 | 66.4119591% | 33.0843218% |

Every row passed `assess`, so each probability equals the independent Fourier
law exactly. The second row runs the unchanged 21,080-gate circuit and is
about twelve times faster than the first. N=143 and N=187, which were zero at
six bits, now have nonzero ideal success at eight bits. Process peak RSS for
the whole audit was 149 MiB. A 12-bit run is accepted but was too slow to
include: for N=21 it was still running after about 28 minutes and was stopped.

## Limits that remain

- **Gate cap.** The modular synthesis gate cap (100,000 declared operations)
  is unchanged. For N near 255, it is reached before ten phase bits. Wider
  precision is therefore available only for smaller moduli in this
  calculator.
- **Scaling.** Support still grows with 2^m times the work-register orbit. No
  general Shor scaling, hardware result or shot statistics are claimed.
- **Arithmetic.** Multiplication is O(s1*s2) over nonzero terms in Python
  integers. It is not an FFT, and dense elements at M = 4096 are slow.
- **Division.** Only division by a nonzero rational is implemented. General
  field inversion is not provided.
