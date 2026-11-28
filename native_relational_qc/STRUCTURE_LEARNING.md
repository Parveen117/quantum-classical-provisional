# Native phase training with circuit-structure search

Monty · 12 November 2026

The existing four-qubit learner can now train its five native phase parameters
for each member of a declared CX topology family. The search selects a model
using training Brier loss, then CX count, then compiled gate count over the
training inputs. Its interface receives training examples only.

```bash
nrqc learn-structure --task curvature --out structure-fit.json
python3.12 benchmarks/structure_learning_audit.py --out structure-audit.json
```

The first command fits the built-in training split and exports a topology-bound
model. The second completes the fixed comparison protocol, freezes the chosen
model, and then evaluates validation and test splits. It records all candidates,
phase-training traces, exact losses, prediction resources and source hashes.

## Admitted topology rules

The fixed classifier uses `CX(0,2), CX(1,2), CX(2,3)` between its initial four
trainable rotations and its final readout rotation. The software experiment
admits those edges plus `CX(0,3), CX(1,3)`. It explores ordered subwords of this
five-edge list containing at most three entanglers. The listed edge order is
part of the search definition. Other user-supplied directed lists can be passed
to the Python API, with an upper bound of six edges.

Immediately before the last RY, the measured observable lies in the span of
`X3` and `Z3`. The existing exact Pauli engine propagates both observables
backwards through each proposed CX word. A word is admitted when both encoded
input wires occur in the resulting support and every selected edge changes at
least one of the two intermediate observables. The result retains these exact
pullback steps. The default family has five admitted words, including the
original topology and the direct two-CX topology.

If a wire is absent from both complete pullbacks, its initial trainable local
rotation commutes with both observed operators. The search canonicalizes that
phase coordinate to zero, with the source and resulting model fingerprints in
the record. This preserves the q3 output probability for every feature input.
The original fitted checkpoint and its optimizer trace remain in the candidate
record. In the two-CX layout this removes the unused rotation on wire 2. The
full-register state can change on that unobserved wire.

This is an application of the same contextual rule discipline used in the
[circuit builder](CIRCUIT_SYNTHESIS.md). Quantum admissibility here comes from
the existing gate and Pauli definitions. The topology family and its order are
explicit design choices in this finite software experiment.

## Phase compilation and preserved semantics

All original phase steps `0..63` remain supported in the exact field
`Q(zeta_64)`. The optimizer keeps its original eight-angle coordinate grid,
three restart seeds `17,41,73` and three-sweep cap in the comparison run. The
encoded curvature inputs also contain non-Clifford phase angles.

The optional `fused` compiler combines the feature rotation and first trainable
rotation on each encoded wire. For the existing emitted word

\[
U(k)=S H P_{64}^{k} H S^{\dagger},
\qquad
U(a)U(b)=U((a+b)\bmod64).
\]

The adjacent `S† S` and `H H` factors cancel. Phase powers add modulo 64.
Rotations on separate wires commute, so the two feature/parameter pairs can
be grouped before any entangler. This preserves the complete unitary and its
retained global phase. The optional mode leaves the five parameter meanings
unchanged. `circuit()` and `Evaluator()` continue to select `raw` by default.

Topology models carry a distinct schema and architecture, their ordered CX
edges, the original training fingerprint and a content fingerprint. Existing
v1 checkpoints retain their original format. Loading and assessment validate
the topology, and an explicitly supplied evaluator must match it. Each
evaluator's topology and compiler are fixed for its prediction cache.

## Comparison and resource accounting

The curvature protocol uses the existing 16 training, four validation and 64
test cases. Every candidate gets the same optimizer settings and training
inputs. Model selection finishes before validation or test inputs are read.
The comparison has three rows.

| Row | Topology | Phase parameters | Compiler |
| --- | --- | --- | --- |
| Fixed raw | Original three-CX word | Fitted original model | raw |
| Fixed fused | Original three-CX word | Same original model | fused |
| Searched fused | Selected admitted word | Model fitted on that word | fused |

Each inference row uses a fresh evaluator. The report gives exact Brier loss,
accuracy, emitted native gates, executor work and measured wall time. It also
checks exact equality of raw and fused output probabilities on all 64 held-out
inputs for both frozen models, and compares those probabilities with the
independent NumPy circuit implementation.

Whole-search circuit and exact-work budgets decrease across candidate fits.
Exhaustion raises `ResourceLimit` before a completed selected model is returned.
Search totals are reported separately from the cost of applying a frozen model.
Exact executor work counts its stated arithmetic operations; wall time includes
the surrounding Python work. Native gate counts use the declared software
couplings. The result describes this synthetic task and bounded family. The
existing one-coefficient classical product baseline is retained in the report.
Hardware routing, device measurements and universal topology optimization
remain outside this experiment's evidence.

## Published comparison

The [12 November record](../benchmarks/records/structure_learning_20261112.json)
used all five default candidates. All five attained the same exact training
Brier loss. Selection chose `CX(0,3), CX(1,3)` and the unused initial rotation
on wire 2 was zeroed through its readout-invariance condition. The original
baseline checkpoint agrees exactly with the previously archived first-layer
checkpoint.

| Frozen model on the 64 held-out cases | Correct | CX gates per prediction | Native gates over all 64 cases | Exact executor work |
| --- | ---: | ---: | ---: | ---: |
| Fixed raw | 64 | 3 | 1,664 | 16,096 |
| Fixed fused | 64 | 3 | 1,408 | 12,576 |
| Searched fused | 64 | 2 | 1,344 | 12,256 |

The selected model's 64 output probabilities agree exactly with the fixed
baseline. The reported held-out Brier loss is approximately 0.10723326275 in
all three rows. Relative to the original emitted words, native gate count
falls 19.23% and executor work falls 23.86%. Topology selection adds a 2.54%
work reduction beyond the fixed fused implementation. The individual measured
inference times were approximately 1.35, 1.02 and 1.10 seconds respectively.
The fixed fused implementation had the shortest wall time in this single
measurement.

The search used 14,128 circuit evaluations and 7,246,876 executor work units,
with about 372 seconds of measured search time. Those search costs precede
application of a frozen model. The independent NumPy probability comparison
had maximum absolute error about 3.33e-16. Exact controls checked 128 raw/fused
probability pairs and 84 before/after unused-phase pairs. The same-feature
classical product baseline also classified all 64 cases correctly.
