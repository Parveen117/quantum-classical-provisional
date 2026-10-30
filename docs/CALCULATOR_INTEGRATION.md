# Calculator integration — 2026-10-30

Author: Monty. Integration branch: `calculator-integration-20261030`.

## Source inventory and integration

At handoff, the branch was `44cfe80`: flat field / record phase `2005048`,
jet learner `8903365`, Codex `fdd3904`, the photonic route through `82db457`,
and self-learning `cfa04da` were already combined. During integration the remote
advanced through `fbc51d7` and `28e8650`; their refreshed records and cluster
certificate were merged as well. `nrqc certify cluster` remains available;
`nrqc certify` / `nrqc certify ledger` derives the four numerical targets. Packaging and `nrqc check`
were present, but historical README counts and a stale jet-source pin remained.

The integration retains these commits rather than rewriting collaborator
history. The current master snapshot `1881e8f` had unrelated rewritten history;
a normal merge reconciles it, preserving governance, citation, provenance,
CODEOWNERS and the prior file removals. No force push is needed.

| Requested work | Implementation / evidence |
| --- | --- |
| Single integration branch | All requested source commits remain ancestors; this branch targets current master. |
| Packaging and CI | NumPy-only core, optional Qiskit/benchmark/CAD extras, installed `nrqc`, Python 3.12 matrix with and without Qiskit; wheel smoke check. |
| Backend check and table | `nrqc check` includes unsupported gates, validation errors and applicable caps; one generated capability table replaces README change history. |
| Ledger certification | Photonic modules import `cyclotomic_pow2`; `nrqc certify` re-derives the four named model targets with enclosures, source hashes and negative controls. |
| Exact phase transport | PhaseGate export/import under an explicit canonical-float convention; symbolic OpenQASM 2 round trip; RZ scalar phase retained and non-dyadic angles rejected. |
| Retired arithmetic engines | Three thin compatibility modules use the shared flat field. Old JSON bases, constructors and legacy coefficient-budget semantics remain. |
| Retained comparisons | Six identical JSON workloads, three trials each; all supported answers agree, with losses to Aer/Stim and the first adapter error retained. |
| Performance | Flat branch ceiling 1,048,576; opt-in shared-state parallel query readout; exact sparse/dense products. Actual 131,072-branch regression passes. Full-register N=141 at 12 bits still times out at 300 seconds. |

## Numerical interpretation

The source weights and purification fidelity are derived from Fock/channel
contractions, not copied expected answers. Expected targets are checked only
after those calculations. The readout expression is `(5/2)w + R`, where
`R = 1-(1-w/4)^12-12(w/4)(1-w/4)^11`; the coefficient is about 2.7981 at the
declared x=1/40, eta=243/4000 point. A counterexample concerns bounding this
expression by 2.8w, not a measured physical error.

Qiskit angles are binary64 at the API boundary. Exact equality to the declared
canonical dyadic spelling is an interoperability convention, not symbolic
recovery from arbitrary floats. The strict OpenQASM parser retains rational pi
syntax. RZ's half-angle must fit the 4096 field cap.

## Validation

The integration found and corrected the historical-coordinate bit-budget
regression rather than relaxing its tests. The stale jet evidence is regenerated
under `native_relational_qc/jet_readings/integration_20261030/`; the earlier
qualification and checksum remain unchanged.

Final full-suite logs, source-bound certification and summaries are retained
under `benchmarks/comparisons/`. See [benchmarks](../native_relational_qc/BENCHMARKS.md)
and [phase transport](../native_relational_qc/PHASE_INTEROP.md) for reproducible
commands and boundaries. The [final validation summary](../benchmarks/comparisons/VALIDATION.md) records
exact pass/skip counts, all three successful CI jobs and the tested revision.
