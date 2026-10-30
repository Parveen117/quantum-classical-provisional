# Calculator integration validation

Tested source: `c1bb8e4355ebac90d3246b86117973bbce0afb3a` (tree
`7b637666e30f17bc250dd26da7a9c8f1c65c4573`). The later evidence commit changes
only documentation and retained logs. The complete requested source history,
including `fdd3904`, `2005048`, `8903365` and the collaborator update `28e8650`,
is retained. Current-master snapshot `1881e8f` is an ancestor too.

## Full suite

| CI matrix job | Passed | Skipped | Subtests passed | Seconds |
| --- | ---: | ---: | ---: | ---: |
| [Python 3.12.15 + Qiskit](ci-python312-qiskit.log) | 1,081 | 9 | 272 | 647.11 |
| [Python 3.12.15 core](ci-python312-core.log) | 1,039 | 51 | 272 | 780.15 |
| [Python 3.11.17 core](ci-python311-core.log) | 1,039 | 51 | 272 | 600.04 |

All matrix jobs also build the wheel, run installed-command smoke checks,
regenerate and verify the bridge ledger, and export its evidence certificate.
The core jobs explicitly check that Qiskit is absent. Tests requiring optional
extras are reported as skips. The retained logs are the complete GitHub job
logs with trailing whitespace normalized; the machine-readable summary records
the job URLs and log hashes.

## Targeted and installed-package checks

The final targeted run passes 25 tests, including all supported phase orders,
RZ scalar phases, invalid-angle rejection, whole-batch parallel-readout limits,
an actual 131,072-branch state, independent integer products, and the Weyl v1
coefficient encoding. Photonic certification must fail when the 14/5*w bound is
violated; the corresponding negative test passes.

The wheel was installed outside the source checkout. With Qiskit absent,
`nrqc check`, `nrqc calculate`, `nrqc certify`, OpenQASM round trip and the Weyl
v1 schema all pass. The package's sole unconditional dependency is NumPy.

The separately regenerated jet audit retains 61,220 exact checks and 3,337
negative controls in `native_relational_qc/jet_readings/integration_20261030/`.
Earlier qualification records are retained as historical evidence.

## Limits and retained failures

The first integration runs exposed stale jet-source evidence, the legacy
coefficient-budget coordinate mismatch and the Weyl serialization mismatch.
These were fixed without relaxing their assertions. Photonic certification
also now explicitly checks the fourth target as an inequality, rather than
only reporting its coefficient. Its retained source hashes match this revision.

Six identical-input comparisons with Aer MPS and Stim retain every supported
trial and the calculator's losses. See [the benchmark page](../../native_relational_qc/BENCHMARKS.md).
The full-register N=141, base 2, 12-bit run still reaches its 300-second wall
budget and returns no partial answer. That workload is not qualified as
completed; the branch ceiling and other performance mechanisms are implemented.

Certificates cover declared ideal models, not hardware qualification. The
14/5*w bound is checked at x=1/40 and eta=243/4000, not asserted universally.

[Machine-readable validation](validation.json) ·
[Photonic certificate](photonic_certification.json) ·
[Raw comparisons](results.json)
