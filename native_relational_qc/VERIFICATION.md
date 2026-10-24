# NRQC v0.1 verification record

Evidence class: **LOCAL_IDEAL_SOFTWARE_VERIFICATION**.
Date: 2026-10-18. Python 3.12.14; NumPy 2.5.4; Qiskit 2.6.0.

The implementation is an independent NumPy evaluator of the explicitly declared
EMK complex quantum representation. Qiskit supplies independent ideal references
and offline target compilation. No IBM job was submitted by this work.

| Check | Recorded result |
|---|---|
| Local unit-test methods | 36 passed; 0 failures, errors or skips |
| Seeded mixed-circuit cases within those tests | 60, spanning 1–6 qubits, 24 gates per case |
| Analytic program comparisons recorded separately | 9 passed |
| Pinned legacy 7-qubit star/delta circuit variants | 32 passed |
| Legacy maximum full complex amplitude error | 1.6653472423834764e-15 |
| Legacy maximum total variation distance | 1.8563243729175817e-15 |
| Predeclared comparison tolerance | 1e-10 |
| Offline synthetic Target compilation | CX, CZ and ECR bases; GHZ and asymmetric circuits |
| Hardware submissions | 0 |

These counts overlap: the 60 seeded cases and offline compilation cases are
subcases in the 36 test methods, not additional independent experiments.

The legacy circuit builder is pinned to repository commit
`2a9eaf3e54e56236f1a92caf0a799f2e953ec125`, file
`run_ugd_seam_ledger_test.py`, Git blob
`d1248943ca5347e3f153c4a5c3fb3aaf7c7818e1`.
Only the inspected pure `build_circuit` function is loaded. The hardware runner,
Runtime imports, account lookup, environment configuration and main function are
not executed. Both topologies, four modes and four perturbation values are covered.
This checks the existing circuit definitions; it does not reanalyse their measured
hardware counts or establish their previously proposed experimental advantage.

The tests include negative controls for nonunitary EMK transport, phase erasure,
operator-order erasure, invalid indices/measurement wiring, unsupported reset and
feed-forward, non-final measurement, unresolved parameters, label spoofing and
JSON/hash consistency. The first regression run found a signed-zero serialization
mismatch; canonicalizing exact zero components fixed it, and replay passed.

## Replay

Use Python 3.12 in an isolated environment, then from the repository root:

```bash
python -m pip install numpy==2.5.4 qiskit==2.6.0
python -m native_relational_qc.verify --out native_relational_qc/verification.json
python -m native_relational_qc bv --compare-qiskit
```

The machine-readable [verification.json](verification.json) records comparison
metrics, versions, circuit hashes and SHA-256 hashes of the implementation, tests
and relevant existing bridge/source files. A missing Qiskit dependency, changed
legacy source pin, failed test or skipped test cannot yield the full replay pass.
The circuit hash binds a concrete serialized input; it is not a formal proof or
a canonical identifier of all mathematically equivalent circuits.

Only this new package's regression suite and pinned circuit compatibility were
run. The repository's entire historical experiment/test collection was not run.
Existing GitHub workflow files were left unchanged; the delivery commit uses
`[skip ci]`, and no workflow was manually dispatched.

## Established scope and remaining work

The stated finite tests support static ideal-circuit compatibility, including
entangled states, relative phases, observer-basis changes and terminal classical
wiring. NRQC-1 gives the mathematical equivalence argument under its explicit
representation assumptions; the tests are not exhaustive certification of the code.

Dynamic circuits, hardware noise/shot statistics, repeated-syndrome recovery,
large-scale resource equivalence, and a separate native physical processor remain
open milestones. Dense state storage is exponential. These results do not imply
quantum advantage on this host or establish the gravitational interpretation of
the broader research framework.
