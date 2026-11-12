# Saved-model acquisition contracts

Monty · 12 November 2026

A saved-model prediction can now be turned into a frozen acquisition plan,
compared with recorded unconditional counts, and replayed. This is the software
boundary between the exact model runtime and an external laboratory controller.
It does not connect to a device or authenticate a provider's data.

The plan fixes the model/input/device prediction, directed physical placement,
terminal Z measurements, exact rational tolerance, planned shots and declared
provider/backend/calibration context. A SHA-256 digest binds each document. The
result must repeat the plan, program and binding fingerprints. Calibration
capture and expiry are supplied declarations with an explicit source-artifact
hash. Acquisitions outside that frozen validity interval are rejected.

The example files under `experiments/` are explicitly synthetic fixtures. Run
the complete intake and replay without a provider SDK:

```sh
nrqc observe-model native_relational_qc/experiments/synthetic_plan.json \
  native_relational_qc/experiments/synthetic_result.json --out observation.json
nrqc verify-observation observation.json
```

Create a new plan before acquiring the corresponding data:

```sh
nrqc predict native_relational_qc/learning/structure_model.json \
  --features 0 32 --view first_layer \
  --device native_relational_qc/calculator_examples/three_wire_line.json \
  --out prediction.json
nrqc experiment-plan prediction.json \
  --binding native_relational_qc/experiments/synthetic_binding.json \
  --run-id my-synthetic-run --shots 100 --tolerance 1/10 \
  --out plan.json --qasm-out measured.qasm
```

Use the schema in `synthetic_result.json` for an acquired result, replacing all
identities, dates, source hash and counts with the actual acquisition's values.
Repeat the newly generated plan fingerprint. `binding_fingerprint` is the
canonical JSON digest of the frozen binding, using `self_learning.digest`.
`program_sha256` hashes the measured OpenQASM UTF-8 bytes. A source hash records
an external artifact reference; this adapter does not fetch that artifact or
verify the provider's signature. Declaring `physical_backend` retains the label
`DECLARED_PHYSICAL_OBSERVATION` and does not promote it into authenticated data.

Measured physical wires are assigned in list order to `c[0]`, `c[1]`, and so on.
The default measures only the final physical model readout. With
`--measure-wires 2 0 1`, physical wire 1 is `c[2]`. Histogram strings have exactly
that width, with the most significant classical bit at the left. Spaced,
hexadecimal, variable-width and implicit endian conventions are rejected.
Counts must be nonnegative integers and sum to the planned unconditional shots.
The current contract admits no hidden filtering or postselection.

For the model's single Z readout, the total variation distance is exactly
`abs(count_one / shots - ideal_probability_one)`. The ideal probability remains
a cyclotomic value. The comparison to the rational tolerance uses exact signs,
including equality at the thresholds. The existing bridge vocabulary is retained:

| Raw marginal error | Engineering classification |
| --- | --- |
| At most tolerance | `RECOGNITION` |
| Above tolerance, at most twice tolerance | `BOUNDED_RESIDUE` |
| Above twice tolerance | `ACTIONABLE_RESIDUE` |

These are declared engineering thresholds. A report does not assert statistical
significance, tomography, corrected readout fidelity or computational advantage.
The raw histogram and exact marginal are retained. No mitigation is applied.

Each observation exposes `bridge_payload`, with the expected model, raw marginal,
model/input/program and calibration bindings for `QuantumNativeBridge.append`.
That legacy bridge uses a floating distribution view; the exact threshold
decision is the observation report's `classification`. Replay recomputes the
prediction, plan, validation, marginal and decision instead of accepting a
repaired checksum alone.

## Recorded observations and retries

```sh
nrqc record-observation observation.json --ledger experiment.jsonl
nrqc verify-experiment-ledger --ledger experiment.jsonl
```

The installed wheel includes the existing `quantum_native_bridge_pro` package.
Each appended bridge entry retains the complete replayable observation and its
exact classification in metadata. Repeating an identical report returns the
existing receipt without another append. A provider/backend/job identity or
frozen plan cannot acquire a different result. A genuinely new acquisition
requires a new run plan and job identity. There is no automatic submission or
retry on a physical backend.

The adapter checks the existing hash chain before writing. Its exclusive lock
coordinates callers of `record-observation`; direct legacy bridge writers must
be kept separate. A busy lock is reported instead of stolen, including a stale
lock after a crashed writer. Explicit verification reads one immutable file
snapshot, checks the chain and recomputes every embedded NRQC observation and
bridge metric. Repairing a hash chain alone cannot change those computations.
Legacy records without NRQC observations are counted separately. Replay is
bounded to 256 records and 64 MiB; start a new ledger for a larger campaign.

The [ledger audit](../benchmarks/records/experiment_ledger_20261112.json)
retains one synthetic healthy run and one deliberate residue, a byte-identical
idempotent retry, a conflicting-result rejection and a repaired-chain negative
control. Its [ledger](../benchmarks/records/experiment_ledger_20261112.jsonl)
can be checked by `nrqc verify-experiment-ledger`.

The [qualification record](../benchmarks/records/model_experiment_20261112.json)
uses independently computed NumPy state probabilities to sample synthetic
counts for the frozen model's 64 held-out inputs, plus exact threshold endpoints
and invalid-binding controls. Every report is replayed. This qualifies intake
and comparison software; physical acquisition remains the controller's task.

```sh
python3.12 -m unittest tests.test_model_experiment -q
python3.12 benchmarks/model_experiment_audit.py \
  --out benchmarks/records/model_experiment_20261112.json
```
