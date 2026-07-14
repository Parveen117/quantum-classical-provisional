# Multi-Ledger Operator-Memory Replication Protocol

## Purpose

The first IBM hardware result established a successful implementation of the
declared multi-ledger operator-order memory benchmark on one backend. This
protocol separates a successful single run from same-backend replication and
cross-backend replication.

The replication layer does not alter the original benchmark circuit, operator
definition, projection weights, pass gates, or analysis metrics.

## Files

```text
run_multi_ledger_replication_job.py
evaluate_multi_ledger_replication.py
```

The replication runner:

1. reads completed local evidence bundles;
2. excludes backends already represented by a completed job;
3. selects the least-busy eligible operational backend with at least seven qubits;
4. submits exactly one unchanged benchmark job;
5. invokes the offline replication evaluator.

The evaluator never submits a quantum job. It verifies manifests and hashes,
rejects duplicated job identifiers or raw-result hashes, reapplies declared
per-run gates, evaluates cross-run metric stability, and writes a replication
certificate.

## Commands

Local software tests:

```bash
python evaluate_multi_ledger_replication.py --self-test
python run_multi_ledger_replication_job.py --self-test
```

Evaluate the currently available evidence:

```bash
python evaluate_multi_ledger_replication.py
```

Submit one job on an unused backend and evaluate the campaign:

```bash
python run_multi_ledger_replication_job.py
```

Request a particular backend:

```bash
python run_multi_ledger_replication_job.py --backend BACKEND_NAME
```

Allow a new job on a backend already represented locally:

```bash
python run_multi_ledger_replication_job.py --allow-used-backend
```

The runner deliberately submits only one job per invocation.

## Evidence classifications

```text
NO_HARDWARE_EVIDENCE
NO_REPRODUCIBLE_MULTI_LEDGER_MEMORY
SINGLE_HARDWARE_RUN_ONLY
SAME_BACKEND_REPLICATION
CROSS_BACKEND_REPLICATION
MIXED_REPLICATION_RESULT
REPLICATION_UNSTABLE
EVIDENCE_DUPLICATION_DETECTED
```

`CROSS_BACKEND_REPLICATION` requires:

- at least two valid completed jobs;
- at least two distinct IBM backends;
- unique IBM job identifiers;
- unique raw-result hashes;
- all declared benchmark pass gates;
- all conservative per-run metric gates;
- all cross-run stability gates.

A failed or invalid attempted repeat produces a mixed result rather than being
discarded.

## Conservative per-run gates

```text
minimum full ledger P(1)              0.90
maximum control ledger ceiling        0.05
minimum full readout P(1)             0.90
maximum projection-erased readout     0.05
minimum reset-signature spread        0.03
maximum visible RK/KR TVD             0.03
maximum full multi-ledger model MAE   0.08
```

The full multi-ledger model must also outperform every reduced model included
in the certificate.

## Cross-run stability gates

```text
maximum full-readout range                  0.08
maximum projection-erased readout range     0.05
maximum control-ceiling range               0.05
maximum visible RK/KR TVD                    0.03
minimum reset-signature spread               0.03
maximum full multi-ledger model MAE          0.08
```

## Outputs

Replication evidence is written to:

```text
multi_ledger_operator_memory_v1/
  replication/
    <UTC_TIMESTAMP>/
      replication_certificate.json
      replication_summary.md
      replication_manifest.json
```

## Promotion rule

A single successful run may be labelled:

```text
SINGLE_BACKEND_QUANTUM_REPRESENTATION_EVIDENCE
```

Same-backend replication may be labelled:

```text
REPEATED_SAME_BACKEND_QUANTUM_REPRESENTATION
```

Only `CROSS_BACKEND_REPLICATION` may be promoted to:

```text
REPLICATED_CROSS_BACKEND_MULTI_LEDGER_OPERATOR_MEMORY_REPRESENTATION
```

Even the cross-backend classification remains a quantum representation result.
It does not establish a fabricated transistor, material memory, quantum
computational advantage, thermodynamic entropy production, or a new physical
law.
