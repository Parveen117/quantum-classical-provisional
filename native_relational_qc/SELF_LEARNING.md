# Native self-learning branch: exact variational training and observer blindness

**Author: Monty. Status: bounded classical training of a quantum-circuit
model on declared synthetic tasks.** This branch adds a four-qubit, five-phase
classifier, saved model checkpoints and a reproducible learning protocol.
The real research task is the existing TVSP/EMK distinction between identical
point responses and different first response layers/native curvature.

The optimizer runs on the PC and evaluates ideal circuits through the exact
calculator engine. No photonic device is trained, no heater voltage is issued,
and no quantum speed or energy advantage is established. The branch is separate
from the hardware-development draft so this experiment can be reviewed alone.

## 1. Reuse and meaning of self-learning

The previously imported flat arithmetic module is retained unchanged. This
branch also reuses `phase_backend.py` byte-for-byte from collaboration commit
[`f2b969769e5c9fc5c3009ce33ddf2dd9095cb0b4`](https://github.com/Parveen117/quantum-classical-provisional/commit/f2b969769e5c9fc5c3009ce33ddf2dd9095cb0b4),
Git blob `74932a5d1a79ed5970c05850db4a52127a947498`. Its `PowerPhaseCircuit`
uses the same sparse executor, not a second simulator. The generic calculator
JSON registration and the collaborator's wider Shor integration are not
imported here; the learning API calls the circuit executor directly.

Here, self-learning means: choose phase parameters from a declared family,
compute loss against supplied training labels, accept improving updates,
retain the fitted parameters, and apply that frozen model to other inputs.
This is hybrid variational quantum-machine-learning software with a classical
optimizer. It is not autonomous theorem proving or a self-modifying foundation.

`self_learning.py` contains the generic bounded trainer/checkpoint API;
`learning_tasks.py` contains the specific source-derived data and baseline.
The model has two encoded inputs, four qubits and five trainable angles.
Starting from |0000>, apply:

1. RY feature rotations on qubits 0 and 1.
2. One trainable RY on each of the four qubits.
3. CNOT(0,2), CNOT(1,2), CNOT(2,3).
4. A fifth trainable RY on qubit 3, then read its probability of one.

All angles are integer multiples of pi/32. The RY compiler uses
`S H P(theta) H S*`, whose global phase is retained by the exact executor.
The fixed connectivity already has a parity structure. The experiment trains
phase alignment/readout; it does not discover parity connectivity from scratch.
The input preparation, all four qubits and readout are counted.

## 2. Exact feedback and bounded optimization

The objective is mean Brier loss, `mean((p_one-y)^2)`, with binary labels.
Coordinate search tests eight angles per coordinate, `0,8,...,56` in pi/32
units, accepting only strictly lower loss. All objective comparisons use the
exact field's bounded real-order test, not rounded floating-point scores.
The fixed experiment uses seeds **17,41,73**, at most three sweeps per restart,
and selects the minimum **training** loss. A coordinate plateau or sweep cap
is a stopping condition, not a global-optimum certificate.

One Evaluator budget covers the whole fit and subsequent evaluation, with
default caps of 16,000 circuit executions and 100 million executor work units.
An exact prediction cache is explicit; hits and actual executions are counted
separately. Each execution has at most 16 basis amplitudes. Executor work does
not include all Python/optimizer overhead, so measured wall time is also saved.
Exhaustion raises ResourceLimit and does not return a completed fitted model.

Checkpoints include architecture, feature view, phase units, training-data
hash and a content fingerprint. Loading rejects altered/mismatched metadata.
The fingerprint binds content; it is not a signature authenticating scientific
claims. `initial_parameters` supports a declared warm start on a new labelled
training batch. The fit API has no validation/test-data argument.

## 3. XOR is only a sanity check

The four binary inputs are encoded as RY angles 0 or pi, with the XOR bit as
label. All four cases are used in training. The report calls this a training
truth-table check; there is no unseen XOR test set and no generalization claim
from these four cases. Factoring is not obtained by extending this truth table.

## 4. Research task from the existing TVSP/EMK response model

In the existing normalized S,V chart, use the cubic-energy family

\[
U_{u,v}(s,w)=10s-10w+\tfrac12(2s^2+2sw+5w^2)
+\tfrac16(us^3+vw^3),
\]

where the coordinate w denotes V displacement and the parameter v is its
cubic coefficient. At the origin,

\[
H=\begin{pmatrix}2&1\\1&5\end{pmatrix},\quad
H_s=\begin{pmatrix}u&0\\0&0\end{pmatrix},\quad
H_w=\begin{pmatrix}0&0\\0&v\end{pmatrix}.
\]

The unchanged `CubicEnergy`/`response_record` implementation supplies the six
point responses, derivatives and selected native curvature using its EMK
commutator. Directly multiplying those matrices gives

\[
\mathcal F_{sw}=-\tfrac14[H^{-1}H_s,H^{-1}H_w],\qquad
\kappa=\frac{(H\mathcal F_{sw})_{12}}{\det H}=\frac{uv}{324}.
\]

The task is label 1 for kappa<0 and label 0 for kappa>0, in this **fixed
declared chart**. This is the selected native response curvature, not a new
Riemann-curvature, RH or Yang–Mills label. u=0 or v=0 is excluded from this
binary task. The source constructs every label; the independent uv/324 identity
checks the generator. The learner never receives kappa as an input feature.

Every model has the same H and same six point responses. With |u|,|v|<=7,
the source's sufficient bound also supplies a positive-Hessian patch of
radius 1/20: `m >= 9/7-(|u|+|v|)/20 > 0`.

Two observation choices are compared with the same learning architecture:

- **First layer:** encode the observed values `(H_s)11=u`, `(H_w)22=v` as
  phase steps `16+2u`, `16+2v`. The output label is not used in encoding.
- **Point only:** encode lambdaV and lambdaS from the six point responses
  by the same affine step rule. Both are constant across this family;
  in fact all six point responses are identical.

This specifically tests whether the required response layer is available.
No physical derivative measurement or noise distribution is fabricated.

## 5. Predeclared split, frozen model and classical controls

| Split | Allowed absolute u and v | Cases | Use |
| --- | --- | ---: | --- |
| Training | 2,6 | 16 | Parameter fitting and restart selection |
| Validation | 4 | 4 | Report only, after model freezing |
| Test | 1,3,5,7 | 64 | Report only, after model freezing |

Each split contains every sign combination and Cartesian pair of its listed
values. Both feature magnitudes in each test case are absent from training.
The model is selected by training loss and frozen before validation/test calls;
there are no score-dependent retries. This is an internal, known synthetic
family, not an externally hidden challenge set or evidence of generalization
to arbitrary physics. The architecture and features use known problem structure.

Two classical learners use the same observed u,v and the same training split:

- Linear least-squares regression of `1-2y` on `(1,u,v)` gives zero coefficients
  on this balanced design and predicts the majority/tie class. This particular
  baseline has 50% test accuracy; it is not a universal bound on all linear
  decision rules.
- A one-coefficient product regression fits `c*u*v` to `1-2y`, obtaining
  `c=1/25`. Its sign gives **100%** on the stated held-out grid. It provides a
  strong inexpensive comparator, so successful circuit learning here cannot
  establish a quantum advantage. The analytical curvature identity is also
  already known and remains the exact reference.

The circuit output probability is a measurement probability, not an externally
calibrated probability that the mathematical statement is true. Accuracy,
Brier loss, runtime and execution counts are reported separately.

## 6. Information ceiling: a useful negative result

For any finite labelled dataset, group examples by identical observed input x.
If a group has n_0(x) and n_1(x) labels, any predictor using only x has empirical
expected accuracy at most

\[
\frac{\sum_x\max(n_0(x),n_1(x))}{N}.
\]

Randomizing the prediction, including using a quantum output distribution,
cannot exceed that maximum. For the point-only view there is one input and
equal positive/negative curvature labels, so the ceiling is **1/2**. Its
minimum Brier loss is **1/4**. More epochs or qubits cannot recover information
absent from those records. Supplying the first response layer changes the
information available to the learner. This specializes the project's observer
blindness principle; it is not a new universal learning theorem.

## 7. Reproduce, inspect and resume

```bash
python benchmarks/self_learning_audit.py
```

The fixed run saves `learning/qualification.json`, `datasets.json`, three
model JSON files and `test_results.txt`. It records exact losses/predictions,
accepted-update traces, dataset hashes, cache/execution counts, wall times,
source provenance and classical baseline results. Training updates are replayed
against their recorded loss before held-out evaluation. Results are ideal
simulator calculations; no shots or hardware jobs are submitted.

```python
import json
from native_relational_qc.self_learning import fit, load_packet, assess
from native_relational_qc.learning_tasks import curvature_splits

model = json.load(open("native_relational_qc/learning/first_layer_model.json"))
splits, _ = curvature_splits()
prediction = assess(model, splits["test"])
# A later, explicitly supplied training batch can reuse these starting weights:
# updated = fit(new_training_examples, view="first_layer",
#               initial_parameters=load_packet(model))
```

The historical v0.12 source manifest pins the older execution kernel. This
branch intentionally advances that dependency and records its old/new hashes;
it does not edit the historical report to imply an unchanged source. The new
audit reruns the photonic-response and calculator regression tests alongside
the new learning tests, including exact old/new field-state comparisons.
The complete collaborator/Shor, CAD and older hardware suites are not rerun.
Use this branch's learning audit for its current qualification; the parent
hardware branch retains its earlier source pins.

## 8. Claims and future research scope

Photonic quantum learning predates this work; for example Maring et al.,
[*A versatile single-photon-based quantum computing platform*](https://www.nature.com/articles/s41566-024-01403-4),
Nature Photonics **18**, 603–609 (2024), reports a trained photonic classifier.
This branch makes no world's-first, 100x speed or lower-energy claim.

The proposed CHSH value is a quantum-correlation bound, not a quantum-chemistry
law or a guarantee against overfitting. Balanced exchange can constrain an
appropriate physical ansatz, but is not silently imposed by this generic
CNOT classifier. Unitary gate semantics and exact probabilities are checked;
generalization still needs separate evaluation.

For RH or Yang–Mills, this learning interface could rank finite candidates,
choose parameters or approximate a certified finite observable after a precise
task and independent labels are provided. Its output cannot certify all zeta
zeros, a continuum mass gap, or an infinite-volume statement. Any proposed
mathematical result must go through its independent proof/certificate workflow.
The task completed here is source-derived curvature classification with a
controlled information-loss comparison and retained model checkpoints.
