# Quantum-Classical Recognition Validation

This experimental branch adds [four-qubit self-learning](native_relational_qc/SELF_LEARNING.md):
bounded phase training, saved checkpoints, XOR sanity checking and a native
TVSP/EMK curvature task with disjoint training/test magnitudes. Exact source
labels, a point-only blindness control and classical baselines distinguish
learning success from quantum advantage. It uses PC simulation and submits
no photonic controls or hardware jobs.

The recorded run passes **33 tests**. XOR is correct on all four training
cases; the curvature model is correct on **64/64 held-out synthetic cases**.
The point-only control scores **32/64**, and the classical product baseline
also scores **64/64**. See the [run report](native_relational_qc/learning/qualification.json)
and [trained checkpoint](native_relational_qc/learning/first_layer_model.json).

## Phase–seam foundation and hardware contract

The [v0.35 full-payload purification cascade](phase_seam_foundation/PURIFICATION_CASCADE.md)
connects two noisy optical rounds without discarding vacuum or excess-photon
outputs between them. With declared 99% input transmission and detector
efficiency at each level, a 75%-fidelity supplied source reaches 82.27%
full output fidelity (90.24% in the ideal model). The exact state includes
all sectors through eight output photons, and costs include false heralds.
Fixed unequal waiting losses are explicit; random preparation times,
certified sources and longer noisy cascades remain open.

The [v0.34 source and purification channel](phase_seam_foundation/SOURCE_DISTILLATION.md)
corrects a missing-coherence term in the v0.33 source model and derives a
Bell-pair purification device from two existing optical fusion units.
Ideal alternating rounds improve a declared 75%-fidelity input to 90.24%
(two rounds) or 98.56% (four), with failed-attempt costs stated. An exact
one-round channel separates true output quality from misleading detector
heralds under input loss, detector inefficiency and dark counts. Supplied
pairs and ideal multi-round storage are explicit assumptions; this is not
a fabricated device or a certified raw-source/encoded-factory pipeline.

The [v0.32 encoded Bell transfer](phase_seam_foundation/ENCODED_BELL.md)
operates directly on encoded blocks and infers loss from detector records.
For the six-photon code it raises ideal transfer success from 1/2 to 3/4
with conditional entanglement fidelity 1. It reuses the classifier's native
heater interface with an explicit coherent-phase adjustment and connects
the output frame to v0.31's heater-only terminal readout. A twelve-photon
Bell resource costs 192 expected ideal Bell pairs under the stated lossless
restart policy; larger-code success values assume supplied resources.
The loss budget separates the herald from fresh-payload survival.

The [v0.30 optical refresh](phase_seam_foundation/OPTICAL_REFRESH.md) lowers
coherent loss recovery to single-photon controls and a two-coupler Bell
analyser with exact success 1/2. A seven-photon encoded Bell resource has an
explicit fusion factory and a full-restart cost of 48 expected ideal Bell
pairs with zero storage loss. Detector, supply and latency budgets separate
a Bell herald from survival of the fresh payload. These are verified ideal
optical models; physical source and device performance remain unmeasured.

The [v0.16 Hamiltonian bridge](phase_seam_foundation/BUS_HAMILTONIAN.md)
reuses the collaboration branch's unchanged flat exact field for centered
bus generators. It derives a conditional interaction/Fourier schedule,
continuous area-error sensitivity and a bare-input Jaynes–Cummings error
bound that retains top-level leakage. Explicit control counts and normalized
time costs expose the accuracy/time trade-off; no material fit is assumed.

The [v0.15 bus/EMK gate](phase_seam_foundation/WEYL_BUS.md) proves the local-PH2
entanglement obstruction and connects the existing joint interaction to
conditional Weyl-bus kicks. Exact bus return holds for every initial bus
state; an echo cancels specified local phase drift. Explicit fault maps and
a restricted no-go result prevent treating this as immunity to in-gate noise.
The added couplings are physical assumptions, not supplied by the SiN layout.

The [v0.14 constitutive adapter](phase_seam_foundation/CONSTITUTIVE_RESPONSE.md)
now generates constrained responses and first response layers from a declared
cubic energy, reuses the existing EMK algebra and optical Jacobian, and derives
finite-patch nonlinear bounds. A quadratic harmonic model retains phase-noise
cross-covariance. These are model calculations with no fitted material data.

The [v0.13 target observer](phase_seam_foundation/PHOTONIC_OBSERVER.md) now
checks the requested photonic target with explicit scales and nuisance
directions, then reuses a separately supplied, pinned device uncertainty
engine. Its conditional numerical budget checks cannot accept hardware
calibration; the empty request still needs physical evidence.

The [four-mode foundation prototype](phase_seam_foundation/README.md) makes
oriented cuts, closure-preserving paired transport, retained history and an
explicit normalized readout executable without a primitive inner product.
Its v0.1 probability law is classical. The separate
[two-site operator completion](phase_seam_foundation/JOINT_READOUT.md) adds
explicit positive-state and measurement postulates, derives CHSH=2 sqrt(2)
and constructs a finite inner-product representation. Physical realization
and the full phase/seam-to-operator encoding remain open. Source identities,
added postulates and hardware requirements are distinguished throughout.

The [phase/seam encoding study](phase_seam_foundation/ENCODING.md) now preserves
four phases and Gamma in exact tomographic readings, retains history in a
classical tape, and checks a restricted transport compiler. It also gives an
exact balanced-cut counterexample to full channel equivalence for that map.

The [orthogonal phase-register compiler](phase_seam_foundation/REGISTER.md)
now lowers native cuts, balanced cuts, shifts, swaps and shears through the
existing reversible arithmetic. It uses a different, larger label encoding:
grid 64 uses 24 phase + 4 clean workspace wires by default. With known fixed
closure, the same compiler now omits one dependent mode: 18 phase + 4
workspace wires, 22 total. The example balanced cut drops from 59 to 24
logical gates when its reservoir is omitted; other layouts can cost more.
Reversible conversion retains off-sector residuals and has its own 28-wire
peak. The v0.5 audit passed 117 tests, including exact coherent
compression and phase retention. Gamma and
lift/history/cost data remain in the original classical Cell; this is a
logical circuit design, not fabricated quantum hardware.

The [native read/reset controller](phase_seam_foundation/CONTROLLER.md) now
retains each relative phase outcome in a fresh explicit record register and
exports its measurement to the existing dynamic engine. Coherent reset
transfers old information and reference entanglement into the record; it
does not erase them for free. At grid 64, one record adds 6 wires. Single-mode
reset is supported only on the unrestricted full layout because it does not
preserve the whole fixed closure sector. The v0.6 audit passed 140 tests.

The explicit [balanced reset](phase_seam_foundation/CONTROLLER.md#61-explicit-balanced-reset-source-law)
now fills that fixed-sector interface: `pair_reset(j,b,a)` sets mode j to a,
adds the old phase difference to reservoir b, and keeps a coherent record.
The integer lift sum is preserved and every compressed layout is supported.
At grid 64, pair_reset(0,2,0) uses 34 logical wires / 193 gates in full form,
or 28 wires / 132 gates with reservoir 2 omitted. This is a declared source
extension using existing arithmetic and measurement engines; original
single-mode reset restrictions remain. The v0.7 audit passes 156 tests in
97.389 seconds, with no failures, errors or skips.

The [continuous sector-control extension](phase_seam_foundation/SECTOR_CONTROL.md)
now derives an all-angle path from native involutions:
`U(theta)=(I+P)/2+exp(-i theta)*(I-P)/2`. The associated proposed generator
commutes with the closure projectors, preserving the sector throughout its
ideal evolution. Exact samples reuse the existing phase engine and include
full/compressed comparisons and a symmetry-breaking negative control.
The v0.8 audit passes 170 tests in 110.823 seconds. Realizing the declared
generator in a material device remains open; binary verification circuits
do not establish continuous physical confinement.

The [first carrier blueprint](phase_seam_foundation/PHOTONIC_EXCHANGE.md)
maps a grid-4 fixed-pair balanced exchange to 16 single-photon optical code
paths: six interferometers and four bypasses, plus an isolated guard.
It includes a logical netlist and 106-setting unrun characterization
protocol. The selected SiN/source/detector architecture still needs process
geometry and calibration. This is an encoded interaction demonstrator;
16 paths are not 16 independent qubits or a scalable 2056-qubit device.
The v0.9 combined audit passes 181 tests in 111.008 seconds.

The [optical I/O and calibration adapter](phase_seam_foundation/PHOTONIC_IO.md)
now compiles all 106 complete preparation/exchange/readout settings through
the existing calculator. A pinned CORNERSTONE SiN300 candidate binding fixes
the default MZI's one-input mismatch by specifying two-input splitters at
both ends. Offline drive plans require complete recorded voltage vectors;
the saved template contains no measured values. Heated mask layout and
physical calibration remain open.
The v0.10 combined audit passes 193 tests in 121.041 seconds.

The [heated-core layout](phase_seam_foundation/PHOTONIC_LAYOUT.md) now provides
a reproducible GDS subassembly using pinned PDK geometry: six exchange units,
four trimmed bypasses and an isolated guard, with 28 heaters and 56 pads.
Independent KLayout connectivity/feature checks and deliberate broken-layout
controls accompany it. A separate 31-channel physical calibration profile
binds the GDS bytes and all bias controls. Optical coupling, packaging,
full foundry review and measured calibration remain open.
Validation: 199 targeted calculator tests and 9 separate CAD tests pass.

The [v0.12 coupled-response audit](phase_seam_foundation/PHOTONIC_RESPONSE.md)
now identifies which phase changes those optical measurements can read.
At a quadrature target, basis powers have rank one, local coherent readings
rank three, and bypass-reference readings rank four. The reference can drift;
global phase remains invisible. An unmeasured plan binds all 28 chip heater
responses to the GDS. Exact component algebra and material calibration remain
separate: no thermal/Maxwell prediction or physical performance is inferred.

## Native relational calculation engine

The [linear-recognition upgrade](native_relational_qc/LINEAR_RECOGNITION.md)
constructs the minimum exact linear future-observation space for a declared
Pauli seed and gate alphabet, with explicit resource limits. A checkable
provenance/closure certificate and execution API accompany a measured
64-to-8 reduction in a seven-qubit reversible-gate example.

The [observer-recognition upgrade](native_relational_qc/OBSERVER_RECOGNITION.md)
extends exact selected measurements to p16/p32 phases without amplitude
preparation and adds a bounded future-closed Pauli bank compiler. A connected
50-qubit local observation needs two terms; reverse resource failures remain
explicit. Morphic, representation, spectral and analytic sources are pinned
with their distinct hypotheses and limits.

The [modular-arithmetic upgrade](native_relational_qc/MODULAR_SHOR.md) adds
polynomial reversible multiplier construction and an explicit `cyclotomic32`
backend with exact 11.25-degree phases. Five-bit Shor now gives nonzero strict
continued-fraction success for N=21; scratch cleanup, invalid register labels
and whole-state phases are independently checked.

The [exact phase extension](native_relational_qc/PHASE_EXTENSION.md) adds an
explicit `cyclotomic` calculator backend with 22.5-degree phases and one prepared
sparse state per batch. Four-bit inverse QFT and bounded Shor circuits now run
through the calculator, with certified decimal displays and retained precision
and resource failures.

The [small Shor factoring qualification](native_relational_qc/SHOR.md) adds exact
modular-oracle circuits, inverse QFT and verified period-to-factor processing.
Historical paired N=15 and N=21 tests expose the original three-bit phase-precision boundary
and compare the original frame with the Surya/jya route on identical circuits.

The [Surya/jya local-return upgrade](native_relational_qc/JYA_FRAME.md)
adds the explicit `jya_frame` backend. It folds repeated single-qubit words
through an exact two-channel recurrence, retains their global phase and
chronological order, and feeds the existing bounded Clifford-frame readout.
An independent linear-fusion ablation separates recurrence savings from fusion.

The [exact Clifford-frame upgrade](native_relational_qc/CLIFFORD_FRAME.md)
adds 2056-site joint probabilities with retained T phase, using a bounded sparse
residual state and generator elimination. It avoids the earlier mandatory
full-projector expansion and compares both execution choices on identical
circuits, including a control where the earlier route is faster.

The [register family](native_relational_qc/REGISTER_FAMILY.md) makes 2056 a
default declared bound rather than a limit: plans `N = banks*width + workspace`,
polynomial cost laws, and exact GHZ families run up to 32896 sites.
The [2056-qubit execution upgrade](native_relational_qc/LARGE_REGISTER.md)
adds an exact Clifford/stabilizer-generator backend and a bounded Clifford+T
backend. Actual whole-register global correlations, full-assignment Clifford
probabilities and EMK geometry are qualified with measured time/RAM. The
[original architecture](native_relational_qc/DESIGN_2056.md) reserves 2048 data
qubits plus eight workspace qubits; qualification uses all 2056 sites as data.
This is classical ideal-circuit simulation with explicit algorithm limits.

The [quantum-circuit calculator](native_relational_qc/CALCULATOR.md) accepts custom
circuit/query JSON and returns exact answers, certified decimal enclosures and
cost diagnostics through `python -m native_relational_qc calculate INPUT.json`.

The [EMK geometry query](native_relational_qc/EMK_GEOMETRY.md) connects the recent
finite-cut information/curvature tensor to exact circuit observations. It
executes native EMK multiplication and certifies real tangent dependencies
while retaining both tensor halves. Full UGD numeral substitution has separately
recorded algebra and phase-adapter boundaries.

The optional [streaming contraction](native_relational_qc/STREAMING_CONTRACTION.md)
builds one exact site factor at a time and reuses signed equal matrix rows/columns.
It includes a bounded 50-qubit, 16-round local calculation, with explicit larger
work/time allowances, exact references and the original failed budget retained.

The [reversible logic and arithmetic layer](native_relational_qc/REVERSIBLE_LOGIC.md)
compiles small Boolean functions into coherent quantum oracles, adds a clean
four-bit adder, and demonstrates an arithmetic search whose interference depends
on uncomputing temporary outputs. Exact threshold-model and transport checks
keep physical assumptions separate from verified circuit behavior.

The optional [exact circuit reducer](native_relational_qc/EXACT_REDUCTION.md)
removes provably redundant gates with a retained phase ledger. It includes a
50-qubit compute/undo example, full-operator tests and an explicit comparison
showing the remaining random-circuit resource boundary.

The [integer-contraction upgrade](native_relational_qc/INTEGER_CONTRACTION.md)
recovers selected 50-qubit, 12-round exact local and all-site parity answers
within the previous 20-second per-query budget, with retained baseline failures,
independent reference checks and explicit deeper limits.

[`native_relational_qc`](native_relational_qc/README.md) implements the first
native relational quantum-computing milestone: EMK unitary gates, joint complex
rays, entanglement, terminal observations, and offline Qiskit/IBM Target exchange.
The design target is the same circuit semantics and output probabilities across
native and IBM-compatible representations. See the explicit
[equivalence derivation](native_relational_qc/THEOREM.md) and
[verification record](native_relational_qc/VERIFICATION.md) for scope and results.

The [exact compact extension](native_relational_qc/COMPACT.md) adds native
observer-first calculation and shared conditional-state graphs. It computes
selected probabilities with exact phase/ratio memory, including a recorded
128-qubit structured query, and measures cost against dense and MPS references.

The [dynamic extension](native_relational_qc/DYNAMIC.md) adds exact measurement,
reset, classical feedback and rational Pauli channels. Its recorded checks cover
teleportation, all 27 single-Pauli Shor recovery cases, and repeated noisy
bit-flip recovery through 128 rounds with explicit resource limits.

The [original IBM workload replay](native_relational_qc/IBM_WORKLOADS.md) executes
the pinned 17-qubit Shor logical source on the native software engine, including
complete classical readout laws at one and three rounds. Its default execution
uses saved native inputs and imports no quantum SDK.

The [40–50 qubit random-brickwork stress test](native_relational_qc/STRESS_BENCHMARK.md)
measures exact observer expansion against Aer MPS and smaller dense references.
Failed runs and resource boundaries are retained; general computational
superiority is not demonstrated.

The [exact factored backend](native_relational_qc/FACTORED.md) recovers selected
50-qubit local and global-parity answers that exhausted the expanded observer.
It combines exact product-observer propagation with sparse MPS contraction,
with a retained 57-row comparison, ablations, and explicit deeper failures.

## Purpose

This repository is the quantum-classical reference implementation of the broader EMK / Recognition Calculus programme.

Its purpose is not to claim that thermodynamics has been proved by quantum experiments, nor that one computational result establishes a universal physical law. Its purpose is narrower and testable:

1. define a quantum-classical state space in the same recognition-seam language used by the thermodynamic framework;
2. translate expected quantum distributions, backend observations, stability tests, and certificates into explicit state, seam, residue, and closure objects;
3. test whether the structural claims of the thermodynamic paper remain coherent under a non-thermodynamic physical projection;
4. expose reproducible evidence that can support, constrain, or falsify the proposed universal recognition architecture.

The repository therefore serves as a **cross-domain validation layer** for the foundational thermodynamic geometry and the EMK Universal Recognition Machine.

---

## Scientific status

The repository distinguishes four levels of statement:

| Level | Meaning in this repository |
|---|---|
| Definition | A state, operator, residue, invariant, or certificate is explicitly introduced. |
| Derivation | A result follows from declared assumptions and equations. |
| Computational verification | Code or tests confirm a result for specified models, datasets, simulators, or backends. |
| Physical validation | Independent experimental observations agree with a prediction within stated uncertainty. |

A computational certificate is not automatically a proof of a universal physical law. It is evidence relative to the declared model, backend, state preparation, measurement map, and tolerance.

---

## 1. Quantum-classical recognition state

The full state is defined as

\[
N_Q=(x_Q,\lambda_Q,\gamma_Q,\ell_Q,m_Q).
\]

The components are:

- \(x_Q\): visible physical state;
- \(\lambda_Q\): active response or recognition coordinates;
- \(\gamma_Q\): preparation, evolution, measurement, and backend protocol;
- \(\ell_Q\): declared dynamical, statistical, noise, and calibration ledger;
- \(m_Q\): accumulated phase, cycle, history, or memory information.

A practical visible-state representation is

\[
x_Q=(\rho,H,\mathcal M,p_{\mathrm{obs}}),
\]

where:

- \(\rho\) is the prepared density operator or declared classical probability state;
- \(H\) is the Hamiltonian or effective evolution generator;
- \(\mathcal M=\{M_i\}\) is the measurement model;
- \(p_{\mathrm{obs}}\) is the observed outcome distribution.

The expected distribution is

\[
p_{\mathrm{exp}}(i)=\operatorname{Tr}(\rho M_i)
\]

for a quantum model, or the corresponding declared classical probability rule.

Two runs may have the same measured endpoint distribution while differing in backend, noise history, phase history, preparation protocol, or calibration ledger. Therefore equality of visible outcomes does not imply equality of the full recognition state.

---

## 2. What is recognized?

The recognized object is **lawful agreement between an observed quantum-classical response and the response permitted by a declared model**.

Let

\[
\Lambda_{\mathrm{ref}}(N_Q)
\]

denote the expected response supplied by the declared quantum, classical, or bridge model, and let

\[
\Lambda_{\mathrm{obs}}(N_Q)
\]

denote the measured or simulated response.

Define

\[
\delta\Lambda_Q=\Lambda_{\mathrm{obs}}-\Lambda_{\mathrm{ref}}.
\]

The recognition decomposition is

\[
\delta\Lambda_Q=P_+\delta\Lambda_Q+P_-\delta\Lambda_Q,
\]

where:

- \(P_+\delta\Lambda_Q\) is the part explained by the declared physical and uncertainty ledger;
- \(P_-\delta\Lambda_Q\) is the unresolved residue.

Thus the quantum recognition operator is

\[
R_Q=P_+.
\]

Recognition does not mean that every run exactly equals an ideal distribution. It means that the deviation is accounted for by the declared finite-sampling, noise, calibration, drift, decoherence, and model tolerances.

---

## 3. Quantum-classical seam

A seam is a typed comparison across a physical or representational transition.

Examples include:

- state preparation to measurement;
- ideal simulator to noisy simulator;
- simulator to physical backend;
- one backend to another backend;
- quantum model to classical approximation;
- pre-measurement state to post-measurement record;
- one calibration epoch to another;
- one phase or control cycle to the next.

Define seam data

\[
\Sigma_Q=(\mathcal N_-,\mathcal N_+,E_{\Sigma_Q},L_{\Sigma_Q},\varepsilon_{\Sigma_Q}),
\]

where:

- \(\mathcal N_-\) and \(\mathcal N_+\) are the admissible state spaces on the two sides;
- \(E_{\Sigma_Q}\) defines which states may be compared;
- \(L_{\Sigma_Q}\) is the lawful bridge, channel, or transport model;
- \(\varepsilon_{\Sigma_Q}\) is the declared tolerance and uncertainty model.

The seam operator is

\[
K^{Q}_{\Sigma}:\mathcal N_-\rightarrow\mathcal N_+.
\]

The open defect must be computed after subtracting the lawful bridge contribution:

\[
G_{\mathrm{open}}=G_{\mathrm{obs}}-L_{\Sigma_Q}.
\]

Without this subtraction, ordinary decoherence, finite-shot variation, basis conversion, or calibrated backend noise would be misclassified as new physics.

---

## 4. Residue vector

The quantum-classical recognition residue is

\[
G_Q=(G_{\mathrm{state}},G_{\mathrm{dist}},G_{\mathrm{dyn}},G_{\mathrm{bridge}},G_{\mathrm{phase}},G_{\mathrm{frame}},G_{\mathrm{mem}}).
\]

Its components are:

- \(G_{\mathrm{state}}\): mismatch in the prepared or reconstructed state;
- \(G_{\mathrm{dist}}\): mismatch between observed and expected distributions;
- \(G_{\mathrm{dyn}}\): mismatch in the declared evolution law;
- \(G_{\mathrm{bridge}}\): simulator-backend or quantum-classical mapping defect;
- \(G_{\mathrm{phase}}\): unexplained phase, interference, or cycle residue;
- \(G_{\mathrm{frame}}\): basis, representation, gauge, or coordinate dependence not removed by the ledger;
- \(G_{\mathrm{mem}}\): history dependence, drift, hysteresis, or backend memory.

A possible distribution residue is

\[
G_{\mathrm{dist}}=D(p_{\mathrm{obs}},p_{\mathrm{exp}})-D_{\mathrm{lawful}},
\]

where \(D\) may be total variation distance, Hellinger distance, Jensen-Shannon divergence, a likelihood statistic, or another declared metric.

The metric must be named in every certificate. Quietly changing metrics until a plot looks persuasive is not validation.

---

## 5. Closure condition

Recognition closure is declared only when all active residue sectors remain within the registered uncertainty budget:

\[
\|G_Q\|_W\leq\varepsilon_Q,
\]

where \(W\) is a declared weighting or covariance model.

This gives several levels of closure:

1. **distribution closure**: observed and expected distributions agree within tolerance;
2. **dynamical closure**: the evolution model explains the run;
3. **bridge closure**: simulator, backend, or classical approximation differences are accounted for;
4. **frame closure**: equivalent bases or representations give equivalent conclusions;
5. **memory closure**: repeated cycles show no unexplained history-dependent residue;
6. **full recognition closure**: all registered sectors close simultaneously.

A passing result is always conditional on the declared model and ledger. A failed result identifies an unresolved residue; it does not automatically identify its physical cause.

---

## 6. Relation to the thermodynamic paper

The thermodynamic paper proposes a completed response geometry in which equilibrium closure, non-equilibrium curvature, hysteresis, frame dependence, and memory are treated within a common state-and-residue architecture.

This repository tests a structural projection of that proposal:

| Thermodynamic object | Quantum-classical projection |
|---|---|
| thermodynamic state \((T,V,S,P)\) | density/probability state, generator, measurement, distribution |
| response coordinate \(\lambda\) | expected response, correlation, stability, or certificate coordinate |
| constitutive ledger | Hamiltonian, channel, noise, calibration, and sampling model |
| thermodynamic seam | preparation, evolution, measurement, backend, or model bridge |
| curvature/path residue | phase, cycle, drift, non-Markovian, or bridge residue |
| hysteresis/memory | repeated-run or control-history dependence |
| closure | all registered residues lie within uncertainty |

The repository can support the thermodynamic framework in three ways:

1. **structural support**: the same state-seam-residue-closure grammar remains mathematically usable in another physical domain;
2. **computational support**: expected models, bridge tests, Bell analyses, and stability certificates are reproducible;
3. **falsification pressure**: frame artefacts, circular projectors, unstable metrics, or unexplained residues expose weaknesses in the universal claim.

The repository does **not** by itself prove the thermodynamic paper. A successful projection supports the proposed common architecture. A rigorous proof would require explicit theorems showing that the projection preserves the relevant operators, invariants, and closure conditions.

---

## 7. Projection certificate

The quantum-classical projection is written

\[
\Pi_Q:\mathfrak X_{\mathrm{EMK}}\rightarrow\mathfrak X_Q.
\]

Its initial dictionary is

\[
\Pi_Q(R)=P_+,
\]

\[
\Pi_Q(K)=K^{Q}_{\Sigma},
\]

\[
\Pi_Q(\Delta_N)=G_Q,
\]

\[
\Pi_Q(\text{shadow})=P_-\delta\Lambda_Q,
\]

\[
\Pi_Q(\text{closure})=\|G_Q\|_W\leq\varepsilon_Q.
\]

A full projection certificate must record:

- state preparation;
- expected model;
- measurement map;
- backend or simulator identity;
- bridge model;
- noise and calibration ledger;
- sampling count;
- residue metric;
- tolerance or statistical decision rule;
- software version and commit hash;
- machine-readable output hash.

---

## 8. Existing evidence layers

The repository currently contains work associated with:

- expected-distribution models;
- Bell-model evaluation;
- Bell stability analysis;
- bridge integration tests;
- backend observation evidence;
- backend comparison tests and summaries;
- runtime stability analysis;
- certificate-bundle generation.

These artifacts should be read as layers of a validation pipeline rather than as isolated demonstrations:

\[
\text{model}
\rightarrow
\text{expected distribution}
\rightarrow
\text{simulated run}
\rightarrow
\text{backend observation}
\rightarrow
\text{bridge comparison}
\rightarrow
\text{residue}
\rightarrow
\text{certificate}.
\]

---

## 9. Reviewer checklist

A reviewer should be able to answer the following without inferring hidden assumptions:

1. What exact state was prepared?
2. What model generated the expected distribution?
3. Which measurement and basis were used?
4. Which backend, simulator, or classical approximation was used?
5. Which differences were declared lawful before the result was inspected?
6. Which residue metric and tolerance were registered?
7. Does the conclusion remain stable under equivalent frames and repeated runs?
8. Can every reported certificate be regenerated from repository code?
9. Which claim is a definition, derivation, computational verification, or physical validation?
10. What result would falsify the proposed projection?

---

## 10. Falsification conditions

The proposed quantum-classical projection is weakened or falsified if:

- the recognition projector is chosen after observing the result;
- the bridge ledger absorbs every discrepancy and makes failure impossible;
- conclusions change under physically equivalent bases or representations;
- certificate results cannot be reproduced from declared inputs;
- repeated runs reveal unexplained history dependence that the model labels as closure;
- a classical model performs equally well while the repository claims uniquely quantum support;
- the same residue is alternately described as noise, curvature, or new physics without a predeclared decision rule;
- no explicit mathematical map connects the quantum objects to the universal EMK operators.

---

## 11. Immediate development tasks

The next repository work is:

1. create a machine-readable `quantum_state_schema.json`;
2. define `quantum_projection_certificate.schema.json`;
3. map current Bell, backend, bridge, and stability outputs into the common residue vector;
4. add one reproducible command that regenerates a complete certificate bundle;
5. add negative controls using deliberately false expected models;
6. add frame-change tests;
7. publish a claim-evidence matrix linking each scientific statement to code, data, tests, and limitations.

---

## Citation and foundational manuscript

The thermodynamic and universal-recognition manuscripts should be cited by version, date, and archival identifier once deposited. Until then, this repository should link to immutable manuscript snapshots rather than silently changing documents.

---

## Summary

This repository asks a precise question:

> Can quantum and classical observations be represented by the same typed state, seam, lawful-ledger, residue, and closure architecture proposed in the foundational thermodynamic and recognition manuscripts?

The answer must come from reproducible mappings, negative controls, frame tests, and independently inspectable certificates. The repository is designed to make that answer clearer, not to hide uncertainty beneath universal vocabulary.

## Theorem binding on hardware shots (claude/rnke-qec-gate-v1)

`rnke_theorem_binding_hw.py` applies two certified finite theorems of the
Recognition framework to the IBM ancilla-extraction shots (exact ℚ):

- **T1 seam integer** (D03 / LEAN-2): k_Σ = n₊(B−I), B = diag(1−⟨S_i⟩).
  Result: k_Σ equals the declared injected-error weight in all four cases
  (0, 1, 1, 4) and the expectation-derived syndrome equals both the expected
  and the bitstring-modal syndrome — operator-level syndrome from expectations.
- **T2 square-sourced residue** (SOS-1 / cut-square positivity): second-moment
  Gram G is certified PSD with explicit weights; residue D = G − σσᵀ typed by
  exact inertia and magnitude. Renaming control (TAUT-1) included: the (7,0,1)
  inertia shape is generic (random shots reproduce it) and is **not** a finding;
  the content is the exact residue magnitude per case.
- **T3** (LEAN-3): |⟨S_i⟩| reported as per-stabilizer orientation confidence.

Pinned certificate SHA-256: see `EXPECTED_THEOREM_BINDING_HW.sha256`.
Boundary: finite-theorem consequences on one hardware round; not RH/K₀/threshold/FT.

