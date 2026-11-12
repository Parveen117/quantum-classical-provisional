# Repeated acquisition campaigns

Monty · 12 November 2026

Freeze the entire set of run plans before acquisition. A campaign request has
three fields: `name`, `minimum_repetitions`, and `plans`, the list of complete
`nrqc-model-experiment-plan-v1` documents. Use distinct run IDs for repetitions.
The API is `experiment_campaign.campaign_plan(plans, name=...,
minimum_repetitions=...)`. Every group must contain at least that many plans.
The campaign is bounded to 64 planned acquisitions.

```sh
nrqc campaign-plan campaign-request.json --out campaign.json
```

After the controller has provided counts, use the acquisition intake and ledger
commands in [MODEL_EXPERIMENT.md](MODEL_EXPERIMENT.md). Keep one dedicated ledger
for a campaign, then report its full planned workload:

```sh
nrqc campaign-report campaign.json --ledger experiment.jsonl --out campaign-report.json
nrqc verify-campaign-report campaign-report.json
```

Individual observation files can be supplied instead of a ledger:

```sh
nrqc campaign-report campaign.json run1.json run2.json --out partial-report.json
nrqc campaign-report campaign.json --ledger experiment.jsonl \
  --require-qualified --out campaign-report.json
```

A valid report can remain incomplete. `--require-qualified` returns exit code 3
when the fixed qualification policy fails or results are still missing, while
preserving the report. Invalid requests return 2. Report replay verifies the
computation and returns the qualification boolean without changing its meaning.

Each planned slot is explicitly `observed`, `failed`, or `missing`. Missing slots
keep the campaign incomplete. A declared acquisition failure completes that
slot's accounting but prevents qualification. Failure files supplied with
`--failures failures.json` contain a JSON list of objects with these fields:

| Field | Required value |
| --- | --- |
| `plan_fingerprint` | One planned run's fingerprint |
| `kind` | `acquisition_failed`, `timeout`, `cancelled`, or `not_submitted` |
| `detail` | Bounded, nonempty explanation |
| `job_id` | Recorded job identity, or `null` when none exists |
| `source_sha256` | Declared failure-artifact hash, or `null` when unavailable |

Failed and successful acquisitions cannot reuse a provider/backend/job identity
or occupy the same planned slot. Unknown plans, duplicate observations and
changed plans are rejected. A retry with a new job needs a new frozen plan and
campaign scope rather than replacing a failed or unfavourable result.

Results are grouped only when the exact prediction, measurement map, acquisition
binding and tolerance agree. Different inputs or calibrations are kept in
different groups. Each group retains its per-run classifications, pooled raw
marginal, empirical probability range, exact mean absolute error and exact
maximum error. Pooling is descriptive. Qualification requires every planned
run to be present and within its own frozen tolerance, with no failures. A low
pooled error cannot conceal a high-error repetition.

The [synthetic campaign audit](../benchmarks/records/experiment_campaign_20261112.json)
freezes three input contexts with three repetitions each before generating
counts from independent NumPy probabilities. Its controls remove one result,
declare a timeout, and introduce a biased deterministic-readout repetition whose
pooled error stays within tolerance. The missing/failure/outlier cases all retain
their failed qualification state. Every healthy observation is exactly replayed
and the complete healthy report is independently replayed.

This is qualification of the orchestration and comparison software. Origins and
calibration windows remain declared; no provider authentication, significance
test, state tomography or hardware performance claim is added.

```sh
python3.12 -m unittest tests.test_experiment_campaign tests.test_experiment_ledger -q
python3.12 benchmarks/experiment_campaign_audit.py \
  --out benchmarks/records/experiment_campaign_20261112.json
```
