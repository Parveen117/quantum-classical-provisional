# A record-controlled moving observer that reduces tracking error

Author: Monty. Retained experiment: 2026-10-31.

The calculator now includes a usable moving-observer policy. With the same six
fresh probes and four available measurement axes, it reduces the declared
mean phase-prediction error from **0.113869 to 0.097070**, about **14.75%**, against
the searched nonadaptive rotating schedule. This is a finite task-specific
gain from choosing later measurements using earlier records. It does not
establish a faster quantum simulator, new universal physics or measured
hardware performance.

## Use the controller

After installing the repository with `python -m pip install -e .`, start with
no records. The controller reports the first analyzer axis. Prepare a fresh
probe from the source at each round, measure at the reported axis, append its
binary outcome, and request the next axis:

```bash
nrqc observer-track
nrqc observer-track --records 0
nrqc observer-track --records 01
nrqc observer-track --records 0101
nrqc observer-track --records 010101
```

These strings illustrate separate recorded prefixes, not measured lab data.
For the shipped policy, the first axis is 0 degrees; after either first bit it
is 90 degrees. The next axis after `00` is 135 degrees, while after `01` it is
45 degrees. Prefix `0101` requests 45 degrees with two probes remaining. After
six bits the command returns its predicted source phase at time index 6.

The command accepts only past binary records, a frozen policy, and an optional
common coordinate-origin shift. It never accepts the true source phase or
velocity. It returns the preceding measurement settings so that a caller can
check how the records were acquired. Outcomes obtained with different axes
are not interchangeable with these records. `--out FILE.json` saves the
response; `--policy FILE.json` selects another policy satisfying the bounded
schema. The shipped [policy](calculator_examples/moving_observer_policy.json)
is fingerprinted and malformed, modified or over-budget inputs are rejected.

`--frame-step k` relabels source/observer phase coordinates together in units
of 2*pi/32. It is not a command to rotate only the physical analyzer while
pretending the source moved too. The default is the laboratory origin, k=0.

## Exactly what is being predicted

A fresh equatorial probe at time t carries the source phase

\[
|\psi_t\rangle=(|0\rangle+e^{i\phi_t}|1\rangle)/\sqrt2,
\qquad p(b_t=0\mid a_t)=\frac{1+\cos(\phi_t-a_t)}2.
\]

The declared planning model has initial phase in 16 evenly spaced bins and
velocity in {-1,0,+1} phase steps per interval, all 48 pairs equally weighted.
One step is 2*pi/32 = 11.25 degrees. The source evolves as
phi_t=phi_0+t*velocity modulo 32. Measurements occur at t=0,...,5 and the
target is phase at t=6. Each consumes a fresh prepared probe; the model does
not repeatedly inspect one unknown state without disturbance or clone it.
The four analyzer settings are 0,45,90,135 degrees. Six-bit records therefore
have 64 possible outcomes. Terminal estimates use the 16-bin phase grid.

The observer updates its belief from the actual bit:

\[
w_{t+1}(h)\propto w_t(h)\,p(b_t\mid h,a_t),
\qquad
a_t=\pi_t(b_0,\ldots,b_{t-1}).
\]

Its objective is the expected circular error

\[
L=\frac{1-\cos(\phi_6-\widehat\phi_6)}2.
\]

Zero means a correct phase and one the opposite phase. **L is not a failure
probability, and 1-L is not classification accuracy.** A separate probability
of lying within 45 degrees is retained with its own limitations below.

Full finite-horizon Bayesian planning chooses the next axis for every possible
record prefix. Its selected tree has 63 measurement nodes and 64 terminal
estimates. The runtime controller follows one branch by table lookup; it does
not rerun that search after every bit. This is standard Bayesian decision
planning implemented with the calculator's phase model, not a claim to have
invented adaptive estimation.

The source in this benchmark has autonomous prescribed drift. Feedback acts
on the analyzer; a source controller, continuous detector backaction, detector
dead time and the material realization of the earlier coupled phase-memory
equations are not simulated here. The [earlier moving-observer experiment](MOVING_OBSERVER.md)
separately exercises record-controlled operations on both source and analyzer.

## Fair comparison and frozen choices

The protocol, implementation and initial tests were committed at
[`af8d8e0`](https://github.com/Parveen117/quantum-classical-provisional/commit/af8d8e068796b7dabe2bb3e61c35f36a07f26f1e)
before running the evaluation. Every policy was frozen before scoring any
trajectory. The planner receives only the declared prior and likelihood law;
it has no evaluation-case argument.

Both main planners use the same available axes, six probes and terminal
Bayesian decoder. The nonadaptive comparison searches all 1,024 schedules
after fixing the first axis to zero. That first-axis restriction uses the
uniform prior's rotation symmetry and applies to the adaptive search too.
Both score 65,536 candidate terminal paths. Planning is performed with NumPy,
using a declared rounding/tie rule; the selected policies' expected risks are
then replayed exactly. Global exact optimality is not certified.

Equal probe and candidate-path budgets do not imply identical controller
costs. On this run adaptive planning took 0.392 seconds; the schedule search
took 0.067 seconds, excluding some policy serialization/construction work.
The adaptive tree needs more stored decisions than a six-angle schedule. Its
mean number of analyzer changes on the model family is 4.1417 versus 4.0.
Those are control counts, not measured joules or actuator latency.

The best searched fixed schedule is [0,90,45,135,135,45] degrees. Other
retained controls are a fixed X analyzer, alternating X/Y, and the adaptive
tree's all-zero-record angle sequence replayed regardless of the observed
bits. The last control disables angle feedback while its terminal decoder
still uses all the real records; it does not insert fabricated zero readings.

## Retained comparison

Smaller mean circular error is better. No policy was changed after seeing
these results.

| Source/readout family | Adaptive observer | Searched schedule | Relative error reduction |
| --- | ---: | ---: | ---: |
| Declared model grid | 0.097070 | 0.113869 | 14.75% |
| Shifted initial phases | 0.097070 | 0.113869 | 14.75% |
| Twice the modeled drift speed | 0.275281 | 0.294332 | 6.47% |
| Drift reverses halfway | 0.091949 | 0.106805 | 13.91% |
| Independent 5% readout flips | 0.122785 | 0.142483 | 13.83% |
| Completely randomized readout | exactly 1/2 | exactly 1/2 | 0% |

On the declared model grid the fixed X control has error 0.232048,
alternating X/Y has 0.117559, and feedback-disabled replay has 0.131091.
The predeclared primary criterion, at least 5% relative error reduction
against the searched schedule on model and shifted-phase families, passes.

The shifted-phase cases use odd phase steps absent from the planning prior.
Their average circular error equals the model-grid average exactly. This is
not independent statistical evidence of broad generalization: with six
Bernoulli phase probes and this loss, the risk as a function of initial phase
is a trigonometric polynomial of degree at most seven. Both equally spaced
16-point grids average out its nonconstant harmonics. The faster/reversing
drift and flip families are more informative mismatch checks, but still only
the finite cases specified here. The simulated flip rate is not a measured
device noise parameter and the controller is not recalibrated for it.

### Losses remain visible

Average gains do not hold on every source trajectory. Against the searched
schedule, adaptive tracking has larger circular error on 6 of 48 model-grid
cases, 6 of 48 shifted-phase cases, 12 of 32 faster-drift cases, 10 of 32
reversing cases and 4 of 48 flip-stress cases. The two policies tie on every
randomized-readout case.

The within-45-degree probability on shifted phases rises from 73.3020% to
77.1817%. Under faster drift it instead falls from 31.8747% to 31.3160%, even
though mean circular error improves. These metrics answer different questions;
the controller was planned for circular error. Threshold hit rates on even
and odd phase grids also have different boundary alignment and should not be
compared as if they were identical test distributions.

## Exact verification and reproduction

The calculator supplies all 32 single-probe likelihood distributions in its
existing cyclotomic field. Exact branch propagation enumerates all 64 records
for each of 256 declared trajectories and five controllers: 1,280 evaluations.
Every path family normalizes exactly. The all-random record control has exact
mean error 1/2 for every controller, so changing the analyzer cannot create
information when the record contains none.

Sixteen selected six-probe path circuits independently reproduce the composed
branch probabilities, including paths from the adaptive policy and the searched
schedule at model-grid and shifted phases. All 48 calculator requests pass
independent local Qiskit checks; maximum discrepancy is below 4.42e-13. The
audit completed in 20.732 local wall seconds. These are local observations,
not hardware throughput claims. Output includes exact field coefficients,
outward decimal enclosures and source/data hashes. The numerical enclosures
are arithmetic bounds, not empirical confidence intervals.

Tests cover causal records, phase covariance, all eight paths of a three-probe
fixture, independent sequential path probabilities, exact prior risk, a full
two-round contingent-policy enumeration, noise controls, invalid policies,
CLI use and fail-closed incomplete audits. The core requires NumPy; Qiskit
remains optional.

```bash
python benchmarks/moving_observer_tracking_audit.py \
  --out /tmp/observer-tracking-replay \
  --protocol-commit af8d8e068796b7dabe2bb3e61c35f36a07f26f1e \
  --compare-qiskit
```

Use a new output directory, and omit --compare-qiskit for the NumPy-only path.
The commit argument is provenance metadata; the runner additionally checks
the protocol and retains implementation hashes. Runtime fields may change
on replay while the declared mathematical experiment remains the same.

The [retained archive](../benchmarks/records/observer_tracking_20261031.tar.gz)
contains likelihood inputs/results, all schedule scores, frozen policies,
all per-trajectory comparisons and path witnesses. The
[index](../benchmarks/records/observer_tracking_20261031.summary.json) includes
archive identity and results. Implementation:
[observer_tracking.py](observer_tracking.py).

The next engineering requirement is a measured source/probe/analyzer interface
with timed records, phase calibration and a latency/noise model. The software
controller can now supply the requested next angle; interpreting that command
as achieved hardware behaviour requires those measurements.
