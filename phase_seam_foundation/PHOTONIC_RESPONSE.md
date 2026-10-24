# Coupled response through an explicit optical observer

Author: Monty. Version 0.12. Status: exact local component algebra and an
unrun acquisition contract. No Maxwell/heat solve, fitted material parameter,
measured response, fabrication or instrument job is reported.

[Code](photonic_response.py) · [Qualification](response/qualification.json) ·
[Acquisition plan](response/acquisition_plan.json) · [Tests](response/test_results.txt).

## 1. Development choice

Use one coupled electrical–thermal–optical response description, with the
optical observable defining the gate requirement. The existing heated
geometry needs both an optical transfer and a control-to-transfer map.
The immediate result is an observer audit: which changes can the chosen
measurements distinguish? It closes a gap that a temperature-only calculation
or a single nominal electromagnetic mode calculation would leave open.

The framework supplies a common language for transformations and readings.
An experimental identification supplies the material-dependent conversion
between volts, power, temperature and optical phase. Equality of measured
invariants establishes equivalence for those observables and conditions;
additional observers can distinguish systems that previously agreed.

For a declared operating point and a differentiable phase-only reduction,

\[
\delta y=J_{y,\phi}\,\Gamma_{\phi,P}\,\delta P,
\qquad
\delta P=J_{P,V}\,\delta V.
\]

Here y is a vector of incident-normalized optical probabilities, phi is in
radians, P is in watts, and V is in volts. `compose_response` multiplies
J and a supplied Gamma exactly, including every supplied off-diagonal term.
The first matrix is derived below. The physical Gamma and J(P,V) remain
unmeasured; the saved plan contains null entries, with no fitted substitutes.

For a thermal model one may further factor Gamma = K(phi,T) G(T,P).
Even a perfectly identified product does not uniquely identify its factors:
K A^-1 and A G give the same Gamma for any admissible invertible latent
coordinate change A. Thermal sensors, a specified material model or further
experiments are needed to resolve that ambiguity. Such algebraic freedom
does not make every factorization a physically admissible material.

Changing absorption, splitting ratio, polarization or wavelength needs extra
terms such as J(y,loss) delta(loss). This phase-only module does not model
those effects. They must be measured and included before device acceptance.

## 2. Exact component and observer definitions

The current layout has four heaters per exchange unit. Let l,u,b,a denote
lower-arm, upper-arm, input-trim and output-trim phases. With the same ideal
balanced coupler used in v0.11,

\[
D=\frac1{\sqrt2}\begin{pmatrix}1&i\\i&1\end{pmatrix},\quad
U=\operatorname{diag}(1,e^{ia})D
  \operatorname{diag}(e^{iu},e^{il})D\operatorname{diag}(1,e^{ib}).
\]

The native exchange target is l=pi-theta, u=0, b=a=-pi/2. Its matrix is
exactly H diag(1,exp(-i theta)) H. `unit_jet` differentiates the component
product analytically and evaluates it using the existing Q(zeta_64) field.
Evaluation angles are sampled in pi/32 units; **derivatives are per radian**.
This is small component-matrix calculus, not a new general amplitude backend.

For any prepared vector x and calibrated analyzer vector d,

\[
p=|d^\dagger Ux|^2,\qquad
\partial_jp=2\operatorname{Re}
[(d^\dagger Ux)^*(d^\dagger(\partial_j U)x)].
\]

Three nested observer families are explicit:

| Family | Scalar probabilities per operating point | Definition |
| --- | ---: | --- |
| Basis powers | 4 | Inputs and projections 0,1 |
| Local coherent observations | 16 | Inputs and projections 0,1,+,+i |
| Reference-assisted observations | 24 | The local 16 plus eight bypass-interference readings |

Here +=(0+1)/sqrt(2), +i=(0+i1)/sqrt(2). The counts are scalar observables,
not optimized numbers of physical acquisitions. The bypass reference is
path 0, outside all six paired units. For each unit input s and output r,
prepare (s+reference)/sqrt(2) and analyze (r+exp(i alpha) reference)/sqrt(2),
where alpha is 0 or pi/2. If the bypass phase is rho, the selected probability is

\[
p_{rs,\alpha}=\tfrac14|U_{rs}+e^{i(\rho-\alpha)}|^2.
\]

The fifth Jacobian column is rho. The reference is allowed to respond to
heating: omitting this column would falsely interpret reference drift as a
gate change. Reference amplitude is one only in this ideal lossless audit.
Actual transmission and calibrated preparation/analyzer transfer must be
included when fitting hardware data. Complementary outputs, total input
power, loss and backgrounds must be recorded; do not renormalize only the
selected successful detections.

## 3. Local identifiability theorem at the quadrature target

Under the ideal assumptions above, at theta=pi/2, with rho=0, four rows of
the Jacobian in column order (l,u,b,a,rho) are

\[
\begin{array}{c|rrrrr}
 &l&u&b&a&\rho\\\hline
p_{0\to0}&1/2&-1/2&0&0&0\\
p_{+\to0}&0&0&-1/2&0&0\\
p_{0\to+}&0&0&0&-1/2&0\\
p_{00,0}^{\rm reference}&3/8&-1/8&0&0&-1/4
\end{array}.
\]

The determinant of the first four columns is 1/32. Thus these observations
have rank four after fixing the reference gauge. All rows annihilate
(1,1,0,0,1): adding the same phase to both arms and the reference changes
no probability. The full five-variable Jacobian has rank exactly four,
and that common phase is its entire infinitesimal kernel at this point.
This proves local identifiability of four relative combinations, not a
unique global inverse over periodic phases or a noise tolerance.

Basis powers have rank one: input/output trims and the arm common phase
are invisible. Local coherent observations have rank three: the common
phase of the whole unit is still invisible. Reference interference makes
the unit's common phase visible relative to the bypass.

The exact audit checks all 64 theta samples:

| Target theta | Basis rank | Local coherent rank | Reference-assisted rank |
| --- | ---: | ---: | ---: |
| 0 or pi | 0 | 2 | 3 |
| Other 62 sampled angles | 1 | 3 | 4 |

At the identity/swap endpoints the current four-control parameterization
itself has a redundant tangent direction. More observations of that same
point cannot restore that direction. Use a calibrated interior diagnostic
point, then verify endpoint behavior separately. A zero derivative does
not imply no finite or higher-order response. This table concerns local
exact rank, not finite-resolution conditioning; near endpoints sensitivity
can be poor even where mathematical rank is full.

An explicit negative control composes a rank-two phase/control matrix with
the basis observer and obtains rank zero. The reference observer recovers
rank two. If the reference heats with the arm common phase, that composed
rank drops to one. A rich thermal response is therefore insufficient unless
the optical observer can read its relevant directions.

## 4. Coupled characterization contract

The saved plan binds the unchanged GDS, layout specification and existing
I/O identity. Each of six units has a five-by-28 phase/power matrix slot:
four internal phase coordinates and the reference phase, versus **all 28
chip heaters**. Cross-unit thermal effects are retained. All 31 assembled
actuator settings, including the three external phase controls, must be
recorded and their stability checked. These are local model coordinates,
not a promise that independent internal temperature/phase sensors exist.

The plan is not consumed by `compile_drive_plan`. It cannot manufacture a
RECORDED calibration profile or bypass the existing full-vector binding.
Only actual documented calibration records may populate that interface.

Acquisition order once appropriate device/model inputs exist:

1. Establish wavelength, polarization, detector/input normalization,
   complex coupler/bend transfer, loss, and the external reference/analyzers.
2. Locate an interior phase point by calibrated fringe measurements. The
   pi/2 target in the plan supplies no voltage for reaching it.
3. Record voltage and current, power, temperature context and optical
   observations. Perturb each heater around admissible biases, repeat at
   multiple amplitudes and in both sweep directions, and retain all others.
   Characterize the full cross-response, including the reference.
4. Reserve joint-heater configurations for validation rather than fitting.
   Quantify uncertainty, drift, nonlinear residuals and loss changes; use
   scaled singular values for noisy numerical identifiability. The exact
   `exact_rank` API must not be used as a noise-rank estimator.
5. Record step-response traces and settling behavior. A steady-state map
   cannot predict time constants, dynamic crosstalk or hysteresis. Qualify
   the complete existing optical protocol after calibration.

For predictive material models, acquire the verified vertical stack and
dispersive optical constants, heater electrical properties, thermal
conductivities/capacities, interfaces and package boundary conditions.
The GDS alone does not contain those inputs. Mode/MMI calculations should
establish complex optical transfer; the electrothermal calculation should
produce the spatial/transient temperature response; their coupling should
predict the same measured optical response and its uncertainty. Nominal
foundry dimensions already recorded in the process binding are useful
inputs, but do not supply all of these quantities.

Experimental precedent for optical calibration is Taballione et al.,
[20-Mode Universal Quantum Photonic Processor, Quantum 7, 1071 (2023)](https://quantum-journal.org/papers/q-2023-08-01-1071/),
[sections 2–3](https://arxiv.org/html/2203.01801v5). They characterize
phase–voltage response using coherent inputs and optical power readings,
and account for crosstalk. Their platform and measured performance are not
parameters or validation of our CORNERSTONE geometry. The calculations and
observer theorem here are independently stated for our declared component.

## 5. Reproduction and closure

Run `python benchmarks/photonic_response_audit.py` with the existing Python
3.12 calculator environment. No CAD package or additional dependency is
needed. It runs the new response tests plus the six existing physical-control
tests, saves source hashes and an empty acquisition plan. The report records
the exact test count and timing. Earlier full foundation/CAD results remain
historical; they are not silently counted as rerun here.

Validation covers all 64 angle ranks and native transfer identities, exact
parameter-shift checks of all five derivatives, eight independent reference
checks through the existing Phase64Circuit, global-phase invariance,
observer/crosstalk negative controls, input guards and layout binding.

Closed: the ideal observer sensitivity gap is identified, the relative
rank-four diagnostic is derived, reference response is explicit, and the
same Jacobian interface can connect coupled model or calibration inputs.

New assumptions: ideal lossless balanced couplers; coherent calibrated
preparation/analyzers; a differentiable phase-only local model. These are
design assumptions, not new measured properties or foundational postulates.

Open: actual complex transfer, electrical/thermal parameters, dynamics,
loss/error/uncertainty budgets, packaging and physical quantum qualification.
