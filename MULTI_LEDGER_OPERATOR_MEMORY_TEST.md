# Multi-Ledger Operator-Memory Benchmark v1

## Purpose

This benchmark advances the successful RK/KR operator-order witness by adding the device repository's strongest validation ideas:

- three separately measurable memory ledgers;
- selective reset of each ledger;
- full ledger erasure;
- a projection-erased control;
- commuting and order-erased controls;
- visible RK/KR equality;
- comparison of no-memory, single-ledger, pair-ledger, and full multi-ledger projection models.

The benchmark is a quantum representation test. It is not physical transistor or material validation.

## Operator core

The declared operators are:

```text
R = X
K = Z
RK = -KR
```

Each ledger interferometer places RK on one branch and KR on the other. The target state is the same up to global phase, while the relative sign is written into the ledger qubit.

## Qubit map

```text
q0 q1 q2 = visible target registers
q3 q4 q5 = memory ledgers M1 M2 M3
q6       = projection/readout register
```

## Test modes

```text
full_memory
erase_m1
erase_m2
erase_m3
erase_all
projection_erased
single_m1
single_m2
single_m3
commuting_control
order_erased_control
visible_rk
visible_kr
```

## Projection

The readout weights are declared before execution and sum to pi. They are chosen to create distinguishable selective-reset signatures. They are not asserted to be physical constants.

## Pass gates

A full classification requires:

1. all three ledgers distinguish anticommuting order from controls;
2. resetting one ledger removes that ledger while preserving the other two;
3. erasing the projection leaves hidden ledger memory but suppresses readout;
4. selective resets produce distinguishable readout changes;
5. the full multi-ledger projection model outperforms no-memory and single-ledger models;
6. visible RK and KR target distributions remain close.

## Classifications

```text
MULTI_LEDGER_OPERATOR_MEMORY_DECOMPOSITION
HIDDEN_MULTI_LEDGER_MEMORY_WITHOUT_RELIABLE_PROJECTION
NO_REPRODUCIBLE_MULTI_LEDGER_MEMORY
```

A scientifically negative classification still means the hardware run completed successfully. Runtime or software failures return a nonzero process code.

## Run

```bash
python run_multi_ledger_operator_memory_test.py --self-test
python run_multi_ledger_operator_memory_test.py
```

Evidence is written to:

```text
multi_ledger_operator_memory_v1/runs/<UTC_TIMESTAMP>/
```

Files:

```text
results.json
certificate.json
summary.md
manifest.json
```

## Scientific boundary

This benchmark can establish whether IBM hardware reproduces a decomposable quantum operator-order memory representation with causal selective erasure and declared readout projection. It cannot by itself establish a fabricated transistor, a material memory mechanism, quantum advantage, or a new physical law.
