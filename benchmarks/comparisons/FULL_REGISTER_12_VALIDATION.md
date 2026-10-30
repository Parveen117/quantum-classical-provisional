# Full-register 12-bit runtime qualification — 2026-10-31

Author: Monty.

Tested source: `b1a126deea34845a02d62825dc5456f7b0951b86` (tree
`0f481ccc75fb839ca19ddbab2bbbc2dd17bbc08c`). The later evidence commit changes
only documentation and retained validation logs.

The N=141, base 2, 12-bit full-register arithmetic-oracle workload completes in
two fresh calculator workers under the unchanged 300-second deadline. This closes
the runtime item left open by [the earlier integration](VALIDATION.md).

| Trial | Worker wall seconds | Calculation seconds | Preparation seconds | Child peak RSS (MiB) |
| --- | ---: | ---: | ---: | ---: |
| 1 | 160.102 | 155.853 | 141.202 | 1196.746 |
| 2 | 190.228 | 168.388 | 148.154 | 1196.688 |

Both use the same canonical input as the [original timeout](full_register_12.json):
40 wires, 45,132 gates after Panini rewriting, and a complete 4,096-bin phase
distribution. The branch cap is 1,048,576, the work cap is 1,000,000,000 and the
coefficient cap is 4096 bits. Actual peak support is 188,412 branches and logical
work is 195,338,092 units. No amplitude is truncated, no dense computational
statevector is constructed, and no factors or order are supplied.

Every exact bin matches the independent finite Fourier sum. Both timed trials
have the same distribution SHA-256:
`1949ebc4d2f32f416f5b99950282a5a3c9378f3a77af8b898ebacf1cd14e0d37`.
The retained input and full output are compressed losslessly; the output includes
exact coefficients and decimal enclosures. The replay verifier checks current
source hashes, both timed summaries, the complete answers and independent
reference. Its changed-probability and missing-bin controls are rejected.

## Full suite and regression evidence

| Run | Passed | Skipped | Subtests passed | Seconds |
| --- | ---: | ---: | ---: | ---: |
| [Local Python 3.12.14 + Qiskit](full_register_12_20261031_logs/local-python312-qiskit.log) | 1,088 | 9 | 272 | 773.46 |
| [CI Python 3.12.15 + Qiskit](full_register_12_20261031_logs/ci-python312-qiskit.log) | 1,088 | 9 | 272 | 784.69 |
| [CI Python 3.12.15 core](full_register_12_20261031_logs/ci-python312-core.log) | 1,046 | 51 | 272 | 543.49 |
| [CI Python 3.11.17 core](full_register_12_20261031_logs/ci-python311-core.log) | 1,046 | 51 | 272 | 780.77 |

All three CI variants also build the wheel, pass installed-command smoke checks,
regenerate and verify the bridge ledger, and export its evidence certificate.
Core jobs verify that Qiskit is absent. Optional-extra tests are reported as
skips. Full job logs are retained with trailing whitespace normalized.
The [machine-readable validation](full_register_12_validation_20261031.json)
records the tested commit, job URLs, counts and log hashes.

The [final targeted run](full_register_12_20261031_logs/targeted-regressions.log)
passes 23 tests. The seven new tests cover signed root
rotations, Hadamard normalization, all packed widths and wide integers, overflow
fallback, external-field embedding, coefficient/branch limits, and equality with
generic execution at every work cutoff. Existing integration, record-phase and
source-pin checks also pass. A separate
[field regression run](full_register_12_20261031_logs/field-products.log) passes 27 tests.

The regenerated jet audit passes 61,220 exact checks and 3,337 negative controls
under `native_relational_qc/jet_readings/performance_20261031/`. Its earlier
records remain unchanged. The [photonic certificate](photonic_certification_performance_20261031.json)
is regenerated against the optimized sources and passes all four claim checks.

## Measurement scope

Python 3.12.14 and NumPy 2.5.4 on a shared Linux x86_64 host; one BLAS/OpenMP
thread. Trial 2 overlaps the jet audit. Both runs use one readout worker for the
single distribution query. Worker wall time includes startup and result transfer;
calculation excludes those costs, and preparation is a subset of calculation.
Child peak RSS includes serialization. Circuit construction and independent
verification are outside the worker deadline. These two local runs do not give a
runtime guarantee for other hosts or workloads.

The older Aer MPS/Stim comparison measurements remain historical integration
results; they have not been replaced with estimates for the optimized kernel.
The record-conditioned path is a separate execution strategy and supplies none
of the timings above.

[Qualification manifest](full_register_12_qualification_20261031.json) ·
[Trial 1](full_register_12_optimized_20261031_run1.json) ·
[Trial 2](full_register_12_optimized_20261031_run2.json) ·
[Reproduction commands](../../native_relational_qc/BENCHMARKS.md#full-register-12-bit-runtime-qualification)
