# Repeated retained-event campaigns

Monty · 12 November 2026

Freeze the entire set of loss plans before acquisition. A request contains
`name`, `minimum_repetitions` and `plans`: 1..64 complete loss experiment plans.
Each run needs its own run ID and acquisition identity. Cohorts pool only an
identical prediction, device/calibration binding, detector policy, instrument
reference and set of thresholds. Every cohort must contain the declared minimum
repetitions. The matching and failed-job checks reuse the original campaign path.

The supplied three-run example is synthetic:

```sh
nrqc loss-campaign-plan native_relational_qc/experiments/loss_campaign_request.json \
  --out loss-campaign.json
for i in 0 1 2; do
  nrqc import-loss-events native_relational_qc/experiments/loss_run_${i}_plan.json \
    native_relational_qc/experiments/loss_run_${i}_controller_events.json --out loss-run-${i}.json
  nrqc record-observation loss-run-${i}.json --ledger repeated-loss.jsonl
done
nrqc loss-campaign-report loss-campaign.json --ledger repeated-loss.jsonl \
  --require-qualified --out repeated-loss-report.json
nrqc verify-loss-campaign-report repeated-loss-report.json
```

Use a fresh ledger for the example. It stores full source-bound observations;
provider authentication remains outside the offline software. Individual report
files can replace `--ledger`, and `--failures failures.json` uses the same
explicit failure objects as [EXPERIMENT_CAMPAIGN.md](EXPERIMENT_CAMPAIGN.md).

## Per-run qualification

All planned runs must individually pass the frozen yield, accepted-count,
unclassified-event, joint-error and conditional-error gates from
[LOSS_ACQUISITION.md](LOSS_ACQUISITION.md). Pooled yield, accepted probability and
mean error are descriptive. They cannot replace any individual gate. The report
retains each run's decision, the lowest observed yield, maximum conditional error
and all exclusive rejection counts.

For example, yields `1/2, 1/2, 3/10` pool to `13/30`, above a `2/5` yield minimum.
The third run still fails its minimum and the campaign remains unqualified.
Likewise a small average conditional error cannot hide one unacceptable run.

Campaign `status: complete` refers to run-slot accounting: each planned slot has
an observation or an explicit failure. A failed acquisition prevents
qualification. Missing slots keep accounting incomplete. A zero-accepted run
can finish its attempt accounting while conditional readout remains undefined;
its plan appears in `conditional_incomplete_plans` and it prevents qualification.

Each cohort reports `conditional_results_available`. Its mean and maximum use
only defined conditional errors. Undefined readouts receive no invented zero
error. `planned_attempts` and `attempts_observed` are separate: a timeout's actual
attempt count is not inferred from the planned budget or silently filled in.
Archive its partial source file under the explicit failure artifact reference.

`--require-qualified` returns 3 for valid but incomplete/unqualified campaigns.
Invalid input returns 2. Report replay verifies its computations and returns the
qualification boolean. All gates are declared engineering thresholds.

The [finite campaign audit](../benchmarks/records/loss_campaign_20261112.json)
freezes two input contexts with three repetitions each before creating synthetic
events. Its controls retain one missing run, a timeout, low yield, a conditional
outlier and a zero-accepted run. The complete healthy report is exactly replayed.
No hardware submission, instrument tomography or measured fidelity is claimed.

```sh
python3.12 -m unittest tests.test_loss_campaign tests.test_experiment_campaign -q
python3.12 benchmarks/loss_campaign_audit.py --out benchmarks/records/loss_campaign_20261112.json
```
