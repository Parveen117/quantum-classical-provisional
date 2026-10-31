# A moving observer for changing contrast and phase

Author: Monty. Retained experiment: 2026-10-31.

The calculator now predicts both transverse Bloch contrast and phase from six
fresh binary probe readings. On the declared source family, its joint error is
**0.095244**, versus **0.103224** for the best searched nonadaptive schedule:
**7.73% lower error**. Keeping the old phase tracker's measurement angles but
giving it the same joint decoder yields **0.096264**. The additional benefit
from the newly chosen angles is therefore **1.06%**, not the much larger gain
against a mismatched unit-radius model.

This is a finite estimation experiment with a specified quantum channel.
It does not qualify a transistor, improve the 12-bit factoring runtime, or
demonstrate 64-bit factoring, hardware speedup or a new physical force.

## Use the controller

```bash
nrqc observer-state
nrqc observer-state --records 0
nrqc observer-state --records 01
nrqc observer-state --records 0101
nrqc observer-state --records 010101
```

For the shipped policy, `0101` requests an analyzer at 45 degrees, with two
probes remaining. After `010101`, the prediction for time 6 is radius **1/2**
and phase **315 degrees**. These are illustrative record strings, not acquired
hardware data. Every bit must have been measured with this policy's preceding
reported angle and a fresh source probe. Its records cannot be substituted into
the old phase-only policy's record stream when their chosen axes differ.

The command takes only past records, a frozen policy and an optional common
frame relabeling. It does not take the true hidden source trajectory. `--out`
saves its response; `--policy` selects a bounded, fingerprinted policy. The
default [policy](calculator_examples/moving_observer_state_policy.json) has
fingerprint `6f20b55dd1b479bbd5273d0f00beb844c88bc9a758e88b184be37aa370bafa5c`.
`--frame-step k` adds k*11.25 degrees to the phase coordinates of both source
and analyzer. It is not a command to rotate only the detector.

Radius here means the transverse contrast of the predicted density matrix.
It is not spatial distance, a statevector's normalization or a confidence
percentage. A joint state estimate can shrink because its phase is uncertain;
this is not a separate unbiased amplitude measurement. At zero radius the
phase is undefined, so the command reports `null` for that phase.

## A source law that actually changes radius

Write an equatorial-plane qubit density matrix as

\[
\rho=\frac12\begin{pmatrix}1&z^*\\z&1\end{pmatrix},
\qquad z=r e^{i\phi},\quad 0\leq r\leq1.
\]

The chosen source channel is

\[
\rho_{t+1}=\lambda U_\omega\rho_t U_\omega^\dagger
 +(1-\lambda)\rho_d,
\qquad
z_{t+1}=\lambda e^{i\omega}z_t+(1-\lambda)e^{i\phi_d}.
\]

It mixes a rotated state with a declared equatorial preparation. This is a
completely positive, trace-preserving channel: one Kraus operator is
sqrt(lambda)*U, and two more are sqrt(1-lambda)*|psi_d><0| and
sqrt(1-lambda)*|psi_d><1|. Their adjoint products sum to the identity. The
prepared drive state is a source resource. This construction does not grant
the controller a universal displacement gate on unknown quantum amplitudes.

The source model starts pure, uses lambda=3/4, and has a fixed drive at
phi_d=phi_0 +/- pi/2 for each hidden source. Initial phases occupy 16 even
steps of the 32-step circle; angular velocity is -1, 0 or +1 step per interval.
The resulting 96 hypotheses have equal prior weight. Every time t=0,...,5
provides a fresh probe from rho_t; the target is rho_6. Measurements do not
repeatedly inspect one unknown qubit without backaction or clone it.

The drive creates a concrete radius/angle coupling:

\[
r_{t+1}^2=(\lambda r_t)^2+(1-\lambda)^2
 +2\lambda r_t(1-\lambda)\cos(\phi_t+\omega-\phi_d).
\]

The next phase is the argument of that same vector sum. Changing the relative
angle therefore changes the next radius, while the current radius changes
the next angle. This is the declared source-channel dynamics; merely changing
observer coordinates does not physically change r.

An analyzer at angle a records

\[
P(0\mid z,a)=\frac{1+\operatorname{Re}(ze^{-ia})}{2}.
\]

Four available axes are 0,45,90,135 degrees. The primary loss is

\[
L=\frac{|z_6-\widehat z_6|^2}{4}.
\]

It lies in [0,1], and reduces to the earlier circular phase error when both
radii are one. It is not a failure probability or classification accuracy.
Predictions use radii 0,1/4,1/2,3/4,1 and 16 phase bins, with only one zero-radius
guess: 65 distinct estimates. The finite Bayesian planner updates from the
real bits and chooses later analyzer angles. The source channel is prescribed;
this controller changes the analyzer, not the drive.

## Rotation, translation and the Coriolis check

For q_t=exp(-i*a_t)*z_t and delta_a=a_(t+1)-a_t, the full update is

\[
q_{t+1}=e^{-i\Delta a}\left[
\lambda e^{i\omega}q_t+(1-\lambda)e^{i(\phi_d-a_t)}\right].
\]

Both the carried state and the added displacement must enter the next frame.
Exact tests compare this rule with direct laboratory-state propagation under
a nonuniform observer schedule. A negative control rotates the old state but
leaves the displacement in the old axes; it disagrees. For z=1, displacement
+1 and a 90-degree observer turn, the correct result is -2i; the faulty result
is 1-i.

The separate continuous-coordinate identity, allowing a moving origin c, is

\[
q=e^{-ia}(z-c),\quad \Omega=\dot a,
\qquad
\ddot q=e^{-ia}(\ddot z-\ddot c)
 -2i\Omega\dot q-i\dot\Omega q+\Omega^2q.
\]

The Coriolis, Euler and centrifugal terms are all present. In the exact test
z(t)=1+(1+i)t and a(t)=t, one obtains q''(0)=1-2i and reconstructs zero lab
acceleration. Dropping Coriolis gives a false lab acceleration 2i. Tests also
cover angular acceleration and origin acceleration independently.

This second-derivative identity has a mechanical interpretation when z is a
physical position with a force law. In the qubit experiment z is dimensionless
coherence and the source law is the channel above. No extra mechanical
"Coriolis gate" is inserted into its probabilities. The discrete channel also
does not specify a unique continuous interpolation or a material device law.

## Frozen comparison, including losses

The protocol, implementation and initial tests were committed at
[`99c5dbb`](https://github.com/Parveen117/quantum-classical-provisional/commit/99c5dbb9c1af8a03687d18b3a0ac069bcdf4a75c)
before evaluation. All six policies were then frozen before any case was
scored. Adaptive and schedule search share the driven prior, six probes,
four axes and terminal decoder. The first axis is zero by rotational symmetry;
schedule search covers all 1,024 remaining schedules. Each method scores
65,536 candidate terminal paths. Planning uses numerical ranking, followed by
exact risk replay of the frozen policies; exact global optimality is not claimed.

| Source/readout family | Coupled adaptive | Searched schedule | Old axes, joint decoder | Constant-radius adaptive | Old phase policy | Ignore records |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Declared model grid | 0.095244 | 0.103224 | 0.096264 | 0.107457 | 0.160382 | 0.166370 |
| Shifted initial phases | 0.095244 | 0.103224 | 0.096264 | 0.107457 | 0.160382 | 0.166370 |
| Twice the modeled drift | 0.083410 | 0.088997 | 0.083792 | 0.093584 | 0.190763 | 0.121416 |
| Retention 7/8 instead of 3/4 | 0.073750 | 0.081061 | 0.074978 | 0.076872 | 0.147142 | 0.121037 |
| Independent 5% bit flips | 0.107870 | 0.113900 | 0.109088 | 0.116386 | 0.185562 | 0.166370 |
| Completely randomized bits | 0.230823 | 0.218127 | 0.233752 | 0.197620 | 0.416370 | 0.166370 |

The predeclared criterion passes: at least 5% lower mean loss than the
searched schedule and strictly lower loss than the old-axes/joint-decoder
control on both model and shifted-phase families. The former is 7.73%, the
latter 1.06%. Against the schedule the reduction is 6.28% at faster drift,
9.02% at changed retention, and 5.29% with 5% readout flips. Errors across
different source families are not interchangeable task-difficulty scores:
target contrast also changes, as the no-record baseline shows.

The unchanged old phase-only decoder predicts unit radius and is explicitly
mismatched to this source. Its larger loss must not be described as evidence
of a comparable improvement due solely to observer rotation. The old-axes
control gives that same measurement tree the new model and optimal terminal
joint decoder. The constant-radius control has 192 equally weighted phase,
velocity and unknown fixed-radius hypotheses; it uses the same joint loss.

Gains are not uniform. The new adaptive policy loses to the searched schedule
on **10/96** model-grid cases, **16/96** shifted-phase cases, **24/64** faster
cases, and **20/96** cases in each of the retention and 5% flip families.
With randomized bits it loses on all 96 cases and its mean loss is **5.82%
higher** than the schedule. Each record then has exact probability 1/64,
independent of the source. A decoder still assuming informative readings can
make harmful nonzero guesses. The calibrated uninformative decoder outputs
the prior mean zero; none of the evaluated policies beats that average risk.

The secondary squared-contrast loss, (|z_6|^2-r_hat^2)^2, also exposes a
tradeoff: the adaptive observer has **0.188549**, versus **0.183361** for the
old axes with joint decoder and **0.141864** for the unit-radius old policy.
It improves the chosen joint objective without improving every radial metric.
All secondary values and per-case losses are retained.

Equal readout counts do not mean equal control cost. Adaptive planning took
0.708 seconds, schedule search 0.111 seconds, and constant-radius planning
0.761 seconds in this run. The adaptive policy changes analyzer axes an
expected 4.640 times per model-grid decision, versus 3 for the selected fixed
schedule [0,0,45,135,135,45] degrees. Source preparation, switching energy,
detector latency and physical memory costs have not been measured.

The odd shifted-phase grid was not used in planning, but its averaged primary
loss equals the even grid's exactly. Six linear Bernoulli factors and this
loss give a trigonometric polynomial in initial phase of degree at most seven;
both evenly spaced 16-point grids remove its nonconstant harmonics. This is
an exact quadrature property, not independent evidence of broad generalization.

## Evidence and reproduction

The calculator supplies 32 exact pure-phase likelihood distributions. Every
mixed source is a positive rational mixture of at most seven such phase
preparations. Exact cyclotomic arithmetic then composes all 64 record paths
and their losses for 544 cases and six policies: **3,264 evaluations**.
Every path distribution normalizes exactly. This is certified composition
of calculator outputs, not one coherent six-qubit mixed-state calculator job.

Independent local Qiskit checks cover all 32 primitives and 60 complete
mixed-state policy/source evaluations, including 5% and randomized readout.
The latter propagate a density matrix through the Kraus channel and compare
all 64 branch probabilities and joint/radial losses. All 92 checks pass;
maximum discrepancy against the calculator's rounded displays is
**5.01e-13**. Total audit runtime was **79.52 seconds**. Enclosures certify
rounding under the declared model; they are not experimental error bars.
See the official [Kraus representation documentation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.quantum_info.Kraus)
for the independent simulator's channel convention.

```bash
OPENBLAS_NUM_THREADS=1 python benchmarks/observer_state_audit.py \
  --out native_relational_qc/delta_ogmt_records/state_reproduction \
  --protocol-commit 99c5dbb9c1af8a03687d18b3a0ac069bcdf4a75c \
  --compare-qiskit
python -m pytest -q tests/test_observer_state.py tests/test_observer_tracking.py \
  tests/test_moving_observer.py tests/test_native_check.py
```

Qiskit is optional; omit `--compare-qiskit` for NumPy-only execution. Output
directories cannot be overwritten, and any incomplete calculator request
leaves an incomplete status rather than a passing summary. The command-line
policies themselves need only the NumPy core and use frozen tree lookups.

The [compact result index](../benchmarks/records/observer_state_20261031.summary.json)
and [full retained archive](../benchmarks/records/observer_state_20261031.tar.gz)
contain the protocol, all calculator inputs/results, frozen policies, all
schedule scores, every case and exact coefficient vector, channel witnesses,
enclosures, controls and source hashes. The archive contains 78 JSON files,
with SHA-256
`948fb85758a8f8e4131f036dfdd81b8a56646c7b09fbd8a9514492f8912b9cb1`.

This establishes a working software model and measurable task-specific
estimation gain. A hardware implementation still needs a calibrated source,
analyzer, binary detector and controller, with physical preparation, noise,
energy and latency measured against the same controls. No rotating chassis
is required by these equations; the observer angle is a measurement setting.
