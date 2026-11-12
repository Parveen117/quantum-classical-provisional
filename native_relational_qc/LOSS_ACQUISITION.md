# Retained loss and heralding events

Monty · 12 November 2026

`loss_acquisition.py` implements a distinct offline acquisition contract for the
classifier's terminal Z readout. It retains every attempted event, accepted and
rejected, under a frozen detector policy and a declared instrument reference.
The original unconditional binary-count interface keeps its earlier scope.

## Run the supplied synthetic example

```sh
nrqc loss-plan native_relational_qc/experiments/loss_experiment.json \
  --policy native_relational_qc/experiments/loss_policy.json \
  --reference native_relational_qc/experiments/loss_reference.json \
  --thresholds native_relational_qc/experiments/loss_thresholds.json --out loss-plan.json
nrqc import-loss-events loss-plan.json \
  native_relational_qc/experiments/loss_controller_events.json --out loss-report.json
nrqc verify-loss-observation loss-report.json \
  --source-artifact native_relational_qc/experiments/loss_controller_events.json
nrqc record-observation loss-report.json --ledger loss.jsonl
nrqc verify-experiment-ledger --ledger loss.jsonl
```

These files are synthetic. No hardware is contacted. The importer hashes the
actual controller-artifact bytes. Replay without that artifact checks the stored
computations; supplying it also checks its original bytes and validated values.

## Frozen detector policy

A `nrqc-click-policy-v1` names 2..32 ordered detector channels, a zero/one detector
pair for each measured physical wire, disjoint herald and guard detectors, a
nanosecond window and the full controller-program digest. Pair order follows the
base experiment's physical-to-classical map. This is a declared two-level
dual-rail encoding. The controller supplies integer counts per detector in
`[0,16]`; its detector response and time-window enforcement remain declarations.

Unassigned channels are retained monitors. A click there is unclassified.
The raw histogram has 1..4096 distinct rows, each with all channel counts, a
positive integer multiplicity, and unique diagnostic flags from `timing_invalid`,
`counter_overflow`, `unclassified`. Multiplicities must sum to the full planned
attempt count. Counts are never rounded, renormalized or silently discarded.

Rejection uses the fixed precedence below, before accepted-bit decoding:

| First matching predicate | Exclusive event category |
| --- | --- |
| Diagnostic flag or unassigned monitored output clicks | `unclassified` |
| A required herald detector count differs | `no_herald` |
| A guard detector clicks | `guard_or_code_violation` |
| Any data pair has zero total clicks | `no_click` |
| Any data pair has more than one total click | `ambiguous_click` |
| All checks pass | Accepted measured bitstring |

The report also retains every matched predicate and diagnostic flag count.
Those diagnostic totals can overlap; the exclusive accepted/rejected partition
alone must sum to the attempts. No-click facts do not become inferred lost-photon
counts or truth labels for genuine/false fusion heralds.

## Explicit conditional reference

Every loss plan supplies a versioned reference with a model identity and source
hash. Two model families are supported:

| Family | Declared meaning |
| --- | --- |
| `scalar_survival` | Positive input-independent scalar survival multiplying the ideal channel, with explicit conditional rejection weights |
| `declared_joint` | Input-specific probabilities for accepted Z outcomes zero/one and each exclusive rejection category |

The scalar family is an explicit modelling assumption. The joint family permits
outcome-dependent selection; its accepted conditional probability can differ
from the original ideal unitary prediction. Neither family establishes a
physical instrument implementation. Probabilities are real exact values in
`Q(zeta_64)`, must lie in `[0,1]` and sum exactly to one, and require positive
reference acceptance. Reference and derived conditional coefficients are bounded
to 4096 bits. Scalar parameters and thresholds are exact bounded rationals.

The joint outcome alphabet is `accepted:0`, `accepted:1`, plus `rejected:` followed
by each category above. Accepted outcomes marginalize only the model's final
physical Z readout. Other accepted measurement bits remain in the raw histogram.
The full controller instrument hash is bound separately from the reference
unitary's measured OpenQASM digest.

## Yield and qualification

For N attempts and A accepted events, report yield `A/N`, all joint per-attempt
counts, and conditional accepted Z probability `count_one/A` when A is positive.
The empirical conditional probability and its error remain null when A is zero.
No uniform or zero replacement is introduced.

Qualification requires all five frozen engineering gates: minimum yield,
minimum accepted count, maximum unclassified fraction, maximum joint total
variation error, and maximum conditional probability error. A low-yield run can
fail while its conditional error is zero. A positive A below the minimum
accepted count retains an incomplete status. These thresholds assert no
statistical significance or computational advantage.

The existing ledger accepts the new report schema and retains the entire exact
report. Its floating bridge view is descriptive; qualification is the exact
report's decision. No measured phase angles are supplied to that legacy bridge,
so its default phase-coherence field is not a physical coherence measurement.

The [loss acquisition audit](../benchmarks/records/loss_acquisition_20261112.json)
replays seven synthetic cases, including zero acceptance, low yield, overlapping
flags and a biased-heralding reference. A scalar reference applied to that biased
case fails while its explicitly supplied joint reference qualifies. Source-byte
and missing-attempt controls are rejected. Independent NumPy probabilities check
the balanced ideal input used by the biased model.

The original source distinctions are retained in the repository's
[loss-accounting design](../LOSS_AWARE_ACQUISITION_DESIGN.md). A repeated-campaign
extension and measured detector/encoding/controller evidence complete the next
integration stages.
