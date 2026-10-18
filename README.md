# Quantum-Classical Recognition Validation

## Native relational calculation engine

The [quantum-circuit calculator](native_relational_qc/CALCULATOR.md) accepts custom
circuit/query JSON and returns exact answers, certified decimal enclosures and
cost diagnostics through `python -m native_relational_qc calculate INPUT.json`.

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

