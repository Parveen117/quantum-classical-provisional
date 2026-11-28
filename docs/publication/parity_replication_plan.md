# Prospective hardware replication of a two-bit parity decoder

This protocol specifies one future device run of the NRQC v1.2.0 parity decoder. It can accompany an Open-Ended Registration on OSF. The simulator predictions and circuit implementation are already public. The observations covered here begin with the first eligible hardware job submitted after public registration. This document contains no device measurements.

## Question and prediction

Can the device recover the two hidden bits for each of the four possible parity checks? Write the bits as `x1 x0`. The supplied check is `(x1 XOR x0, x0)`. In the released circuit the oracle computes the parity, marks the state consistent with the check, and uncomputes the parity. One Grover diffusion step yields a unique ideal answer. The inverse mapping below scores the returned counts.

| Supplied check | Predicted measured bits (q1 q0) |
| --- | --- |
| 00 | 00 |
| 01 | 11 |
| 10 | 10 |
| 11 | 01 |

## Run and stopping rule

1. Use the released `nrqc-two-bit-parity-decode-v1` circuit on a physical IBM Quantum backend available to the experimenter. Record the backend name before submission. Save the job ID, UTC submission time, package versions, and transpiled circuit layouts or sufficient compilation metadata to reproduce them. The release fixes the transpiler settings and target order.
2. Submit all four checks together, with 256 shots per check and 1,024 shots in total. Preserve the first submitted job ID. Use its original raw counts in the released bit order. Preserve any failure, cancellation, invalid metadata or incomplete output as an inconclusive run. Any later attempt receives a separate label and job ID.
3. Keep every valid shot. Report all four two-bit counts for every check, including zero counts. The release checks circuit metadata, target order, allowed bitstrings and the reported shot total. A rejected result is inconclusive.

## Analysis fixed in advance

The primary endpoint is whether the predicted bitstring is the unique most frequent output **for all four checks**. A tie or a different winner for any valid check fails that endpoint. Report the four target fractions (target count divided by 256) and the smallest of the four. An ideal circuit predicts 1 for each fraction. Uniform independent guessing predicts 1/4 in expectation. This rule is a descriptive device diagnostic; it assigns no statistical significance level. Mark any error-mitigated analysis or additional job as exploratory and keep its counts separate.

The classical inverse takes one XOR and one copy. The experiment measures decoding performance under device noise.

## Public implementation

[Release and wheel](https://github.com/Parveen117/quantum-classical-provisional/releases/tag/v1.2.0) · [Archived source](https://doi.org/10.5281/zenodo.24624377) · [Circuit and scoring code](https://github.com/Parveen117/quantum-classical-provisional/blob/67478206858dac407198bcd58cc3c3c5663dfd6a/native_relational_qc/grover_cloud.py)
