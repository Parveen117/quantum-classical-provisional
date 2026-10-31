# Delta OGMT: frozen tuning and unseen pulse sequences

Author: Monty. Local run: 2026-10-31. Evidence class:
**DECLARED_IDEAL_CIRCUIT_MODEL**.

The full double triangle failed the declared topology-advantage criterion.
After equal-budget tuning its held-out expected balanced accuracy was
49.9617%, compared with 55.0197% for one ledger and 49.6593% for three parallel
ledgers. Arithmetic verification passed. Tuning on these observables did not
produce a useful held-out classifier for this task family.

## Frozen experiment

The [protocol](../benchmarks/protocols/delta_ogmt_learning_v1.json), implementation
and tests were committed at
[`eb9db4d`](https://github.com/Parveen117/quantum-classical-provisional/commit/eb9db4dd605408274322b3d9b01477da60ff45cc)
before the campaign was run. Every history has 12 events, six A and six B,
starts with A and ends with B. The binary task distinguishes at least seven
adjacent transitions from at most five. A clean conventional symbol counter
solves this declared task exactly; there is no claimed algorithmic advantage.

The 252 strings form balanced groups with their reverse-complement twins.
Groups stay together across train (32), validation (32), test (64) and reserve
(124) splits. The reserve remains unevaluated. Histories used by the proposal
search are retained, and checked against test/reserve exclusion. Labels enter
scoring only, never the physical circuit inputs or feedback.

M1, M2, M3 and E_CA each receive 9 coupling profiles x 8 drain projections x
16 observer angles = 1,152 configurations. Each configuration tests both
decision polarities and all count thresholds. The two shared coupling scales
change the outer edges and memory edges; the full model gets no extra search
coordinate. The best training readout from each dynamics profile is shortlisted;
validation selects among four profiles. Equal parameter-search budgets do not
imply equal circuit gate counts, physical area or energy.

The decision uses **64 independent ideal preparations/readouts**, predicts
from their count K, and reports exact-bounded expected correctness under the
resulting binomial law. It does not pretend an exact probability is a noiseless
single-shot measurement. Fast proposals use native NumPy algebra; every frozen
train/validation/test probability is replayed through the exact calculator.

All models and thresholds are frozen before any test prediction. The original
M3 dynamics/projection with the earlier 67.5-degree observer is a separate
reference, with only its count threshold/polarity fitted to training. Another
control removes CA from the selected full model without retuning anything.

## Retained results

These are expected balanced accuracies, not sampled or physical accuracies.

| Model | Training | Validation | Unseen test |
| --- | ---: | ---: | ---: |
| M1, one ledger | 64.8785% | 57.5512% | 55.0197% |
| M2, three parallel ledgers | 60.8418% | 60.5663% | 49.6593% |
| M3, full double triangle | 61.5597% | 60.1221% | 49.9617% |
| E_CA, separately tuned edge-cut model | 71.0861% | 64.8343% | 56.3634% |
| M3 original dynamics/readout | 50.8570% | 49.6655% | 52.7778% |
| M3 frozen parameters, CA removed | — | — | 46.3705% |

The predeclared success rule required M3 test accuracy at least 70%, a lead of
at least 5 percentage points over both M1 and M2, and positive lower endpoints
of paired grouped-bootstrap difference intervals. It did not pass.

The M3-M1 test difference is -5.0580 percentage points; M3-M2 is +0.3025
points. Exploratory 2,000-resample grouped-bootstrap 95% intervals are
[-15.1552, +5.1576] and [-0.0972, +0.7052] points respectively. Neither supports
a positive full-topology advantage. The fixed CA removal decreases M3 by
3.5912 points on these exact inputs, but its broad resampling interval spans
both signs. The separately retuned E_CA comparison answers a different question.

Arithmetic enclosures in the archive rigorously bound the binomial expected
scores propagated from each exact calculator probability. Their narrow widths
are numerical certainty **conditional on the model**. The bootstrap describes
input-group variability within this one family, not noise, drift, fabrication
variation or physical uncertainty. No post-test retuning or alternate winner
selection was performed.

## Verification and replay

712 exact requests completed in 150.427 local wall seconds with at most four
worker subprocesses. Each request had its own 60-second timeout. The 704 frozen
model requests passed Qiskit checks; maximum discrepancy was below 5.17e-13.
All proposal probabilities agreed within 5.01e-13. Eight additional exact
requests checked opposite-label representatives under boundary-only,
equal-input, commuting-update and disabled-projection controls; each pair was
identical as required. Those are representative circuit checks, not 64 trials
of a physical negative control.

The [archive](../benchmarks/records/delta_ogmt_learning_20261031.tar.gz) retains
all requests/results, candidate scores, frozen settings, per-input expected
correctness, protocol, summary and byte-hash manifest. The
[index](../benchmarks/records/delta_ogmt_learning_20261031.summary.json) records
archive identity and scores. The driver refuses to overwrite an earlier run.

```bash
python benchmarks/delta_ogmt_learning_audit.py \
  --out /tmp/ogmt-learning-replay \
  --protocol-commit eb9db4dd605408274322b3d9b01477da60ff45cc \
  --compare-qiskit --workers 4
```

The supplied commit is provenance metadata; a rerun also validates the checked-in
protocol against its implementation and retains source hashes. Omit
--compare-qiskit for the NumPy-only path. These results do not qualify the
separate full-register 12-bit N=141 runtime workload.

The next conceptual experiment concerns a [moving observer and record-dependent
source/reference dynamics](MOVING_OBSERVER.md). Its algebraic examples are a
different test, and do not repair or replace this negative learning result.
