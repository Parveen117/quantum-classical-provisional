# NRQC-2056: theoretical register and execution design

Author: Monty. 23 October 2026.

Original status at commit `52c6aefd22d213da237da526ad0609682958126d`:
theoretical architecture and written finite-register derivations, with no
2056-qubit execution or new implementation evidence at that revision.

Implementation update: [LARGE_REGISTER.md](LARGE_REGISTER.md) now records
executable exact Clifford/stabilizer-generator pullback, bounded Clifford+T
observations and measured 2056-qubit qualification. The subsequent
[Clifford-frame route](CLIFFORD_FRAME.md) adds wide T-phase probabilities with
a bounded sparse residual and phase-sensitive pair evaluation. These three
explicit backends accept up to 2056 sites; the older backends retain 256.
The implementation uses observation pullback rather than a reusable full-state
tableau. Hardware construction, fault tolerance and general efficient deep-T
execution remain outside this milestone. Historical design choices below are
not all implemented by this update.

This document extends the declared quantum sector of
[THEOREM.md](THEOREM.md) and the finite-cut adapter in
[EMK_GEOMETRY.md](EMK_GEOMETRY.md).

## 1. Register allocation and connectivity

Choose exactly 2056 ideal circuit qubits. These are not a claim of 2056
error-corrected logical qubits or a count of manufactured physical devices.

| Allocation | Indices | Size | Function |
| --- | --- | --- | --- |
| Data banks D_b, b=0,...,63 | 32b,...,32b+31 | 64 × 32 = 2048 | Problem state and coherent computation |
| Reusable workspace A | 2048,...,2055 | 8 | Bounded arithmetic workspace and coherent readout helpers |
| Classical retained record | Outside the qubit register | Workload-dependent | Circuit order, phase, observation specification and proof witnesses |

The baseline graph is one open nearest-neighbor chain q0—...—q2055.
It has 2055 edges: 1984 within data banks, 63 between data banks, seven
within workspace, and one connecting data to workspace. Banks are scheduling
and addressing units. Their states are not assumed independent.

The chain matches the present factored engine's local interaction semantics.
Within each bank, disjoint even edges and odd edges form separate gate layers;
between-bank links are scheduled explicitly. Arbitrary remote interactions
require SWAP routing along the chain, with the logical-to-physical permutation
retained in the record. The eight workspace qubits sit at one end; they are
not assumed simultaneously accessible to every bank at zero cost.

The normal application profile reserves workspace. A separate whole-register
qualification profile temporarily uses all 2056 sites as data, including those
eight sites. It does not claim to have additional workspace at the same time.

## 2. EMK algebra and the joint state

At every site retain K²=I, R²=-I, KR=-RK, and X=RK, Y=iR, Z=K.
The local operator has coordinates aI+bK+cR+dRK. Operators at distinct
sites commute; operator order on the same site is retained.

The already admitted complex representation, tensor composition, positive
pairing and Born rule define the 2056-site sector:

\[
\mathcal H_{2056}=(\mathbb C^2)^{\otimes2056},\qquad
|\psi_f\rangle=U_m\cdots U_1|0\rangle^{\otimes2056}.
\]

Its dimension is 2^2056. This is a semantic definition, not an instruction
to allocate the vector. EMK's three multiplication relations alone do not
derive the extra composition and observation choices; those remain explicit.

Use the exact gate alphabet H, S, T and their inverses, X/Y/Z, R/K/RK,
nearest-neighbor CX/CZ, and SWAP. Their entries lie in Q(sqrt(2),i), so every
finite gate sequence and Pauli/probability observation stays in that field.
This does not imply every arbitrary continuous rotation is exactly expressible
by this finite alphabet. Approximate synthesis, if added, needs a separate
declared error budget.

**Register-extension statement.** Every finite ordered circuit over this
alphabet defines a unitary on all 2056 sites and a normalized final state.
For a computational-basis observation projector Pi, the exact probability is
<psi_f|Pi|psi_f>. Proof: each local unitary embedded with identities is unitary;
their product is unitary; orthogonal outcome projectors resolve the identity.
The argument has no special cutoff at 50 or 256. It proves well-defined
semantics, not efficient classical execution.

## 3. Observation and retained memory

Users request selected marginals, Pauli strings, correlations or the EMK/CID
tensor for a bounded list of controls. Enumerating all 2^2056 outcomes is
not a default operation. With P=|psi_f><psi_f|, B_a=-i H_a and X_a=[B_a,P],

\[
Q_{ab}=\operatorname{Tr}(PX_aX_bP)
       =\langle H_aH_b\rangle-\langle H_a\rangle\langle H_b\rangle
       =g_{ab}+i\Omega_{ab}.
\]

This existing finite-rank-one identity is independent of register width.
The initial interface can retain its current limit of eight signed Pauli
controls even when the register grows. Each control may have global support.

Keep both g and Omega. Exact real tangent dependencies may be represented by
Q=C^dagger Q_JJ C only after the full complex reconstruction is verified.
Such a dependency belongs to that requested final-cut tensor. It does not
license deletion of circuit history or reduction of an arbitrary state bond.

The classical record retains the original gate sequence, routing permutation,
complete operator phases, workspace preconditions, selected observer and any
exact reconstruction witnesses. It grows with the workload. Neither eight
ancillas nor a fixed-size hash contains the full quantum state or history.

Workspace is borrowed only under a declared |0> precondition and returned
coherently to |0> before reuse. Discarding an entangled workspace changes the
state. Intermediate measurement/reset needs the separate channel and branch
semantics already developed in the dynamic engine; it is not silently added
to this pure-state design.

Full UGD digit/carry arithmetic remains outside the coefficient-field contract
until the recorded associativity and phase-adapter boundaries are resolved.
The usable EMK operator algebra is not blocked by that separate obligation.

## 4. Execution architecture and conditional costs

The proposed planner retains one circuit meaning and admits several explicit
execution routes. Every route must declare its eligibility and resource limits.
No backend switch may erase phase, truncate coefficients or reclassify an
approximate answer as exact.

| Route | Eligibility | Scaling variable | Development status |
| --- | --- | --- | --- |
| Exact observer propagation | Requested observable expansion stays bounded | Retained Pauli terms, gate visits, coefficient bits | Existing route; 2056 implementation unqualified |
| Exact MPS contraction | Exact bond sizes and integer arithmetic stay bounded | Bond dimensions, depth, coefficient bits | Existing route; 2056 implementation unqualified |
| Stabilizer representation | Circuit and observations meet the Clifford contract | Tableau size and update cost | Proposed additional backend, not implemented here |
| Physical QPU execution | Device implements the compiled gates and calibrated observations | Connectivity, errors, depth, samples | Hardware-dependent downstream adapter |

For an open-chain MPS with bond dimensions chi_0=chi_N=1,

\[
\#\text{stored field coefficients}=\sum_{q=1}^{2056}2\chi_{q-1}\chi_q
\le4112\chi_{\max}^2.
\]

This is a bound on mathematical representation entries, not peak process RAM.
For orientation only, storing that upper bound as complex128 would cost:

| chi_max | Coefficient upper bound | complex128 payload |
| --- | --- | --- |
| 2 | 16,448 | 0.251 MiB |
| 32 | 4,210,688 | 64.25 MiB |
| 64 | 16,842,752 | 257 MiB |
| 256 | 269,484,032 | 4112 MiB |

The exact engine stores several arbitrary-precision integer channels, indices
and temporaries; these numbers are not exact-engine RAM forecasts. A product
observer contraction takes O(N chi^3) field operations for a dense bounded-bond
MPS, up to fixed local dimensions. Integer bit growth and plan construction
must also be counted. Streaming one site can reduce live storage but cannot
remove an exponentially growing boundary. Current history-built factors may
be much larger than the minimal Schmidt rank; an efficient exact factorization
algorithm remains an implementation obligation.

A proposed full stabilizer/destabilizer tableau has 2N rows of 2N binary
coordinates plus one sign each: 2N(2N+1)=16,912,656 bits at N=2056,
about 2.016 MiB if bit packed, before scratch and software overhead. This
applies to Clifford simulation, not arbitrary T-rich circuits. Large
entanglement alone does not make every circuit hard: stabilizer structure is
a separate useful condition.

Neither bounded bonds nor bounded observer expansions follow merely from
the qubit count or from choosing EMK coordinates. A generic exact state can
require exponentially many parameters. The design therefore specifies
admission conditions rather than a universal efficient-simulation claim.

## 5. Two exact whole-register qualification families

These are written symbolic predictions, not reported simulation results.

**Family A: 2056-site GHZ.** Apply H on q0, then CX(q_j,q_{j+1}) for
j=0,...,2054, in that order. The 2056 gates give

\[
|G\rangle=(|0^{2056}\rangle+|1^{2056}\rangle)/\sqrt2.
\]

Proof by induction: after each CX the coherent 0/1 branch extends by one site.
Every site participates. Across every nontrivial contiguous cut its Schmidt
rank is 2. Each single-site Z mean is zero; every distinct-pair ZZ mean is 1;
every two-site 00 marginal is 1/2; the all-site X expectation is 1.

**Family B: retained non-Clifford phase.** Append T on q0, giving 2057 gates:

\[
|G_T\rangle=(|0^{2056}\rangle+e^{i\pi/4}|1^{2056}\rangle)/\sqrt2.
\]

Now <X^tensor2056>=1/sqrt(2) and
<Y_0 X_1...X_2055>=1/sqrt(2). Z-basis marginals remain unchanged.
Replacing the phase by its magnitude would preserve those marginals but fail
both phase-sensitive answers. The Schmidt rank remains 2. This is an exact
non-Clifford test with global correlations, not a representative hard random
circuit or a quantum-advantage demonstration.

Future harder qualification must declare circuits and budgets before execution:
increase depth and cross-bank coupling, retain failures, compare small instances
with an independent reference, and report exact bond/term/bit growth. A smaller
successful exact query cannot certify an unexecuted 2056-qubit workload.

## 6. Hardware interpretation

This is a technology-neutral gate/control architecture. A hardware realization
must supply two-level carriers, the chain's entangling links, addressable local
control, preparation, readout and timing/error specifications. Neither the
EMK coordinates nor the abstract chain selects a fabrication technology.

If 2056 means useful error-corrected logical qubits, the physical carrier count
must be designed separately from a chosen code, measured error model, target
logical failure rate and workload duration. Eight workspace qubits are not an
error-correction budget for 2048 data qubits. If only 2056 physical carriers
are available, the number of protected logical qubits cannot be inferred here.

Physical runs produce sampled, noisy readings with statistical/error analysis;
they do not inherit the software's exact rational-answer certificate. A PC
controller stores circuits and witnesses and coordinates device execution.

## 7. Closed design decisions and next obligations

Closed in this document: exact register allocation; connected gate graph;
EMK composition and observation semantics; complete-phase/record requirements;
conditional representation costs; symbolic whole-register qualification answers.

Still open: scalable implementation beyond the 256-qubit guard; elimination of
recursive stack limits; bounded planning and validation; practical exact
factorization; stabilizer backend; measured 2056-qubit runtime/memory;
hardware technology, error correction and calibration.

New choices: 64 banks of 32 plus eight reusable ancillas, an open chain,
the specified workload profiles and backend-admission policy. The inherited
quantum-sector assumptions are retained. No new physical law is assumed.

Next implementation milestone: an explicit 2056-register mode with iterative
planning, unchanged exactness semantics, bounded failure reports and Family A/B
qualification. Raising a constant alone does not close that milestone.

## References and attribution

Native source and representation pins are in EMK_GEOMETRY.md. MPS and
stabilizer simulation are established methods, not new EMK discoveries:

- G. Vidal, [Efficient classical simulation of slightly entangled quantum computations](https://arxiv.org/abs/quant-ph/0301063), 2003.
- S. Aaronson and D. Gottesman, [Improved Simulation of Stabilizer Circuits](https://arxiv.org/abs/quant-ph/0406196), 2004.

The contribution here is the concrete 2056-site design and its contracts for
the existing native calculator. The symbolic proofs do not certify an
unwritten implementation or a physical device.
