# Historical calculator integration notes

Earlier scoped results; refer to the current calculator README for capabilities.

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

Install and run the exact calculator from the repository root with
`python -m pip install -e ".[test]"` (NumPy-only core; add `qiskit` to the extras
for the optional adapters), then `nrqc check INPUT.json` to see which backends
accept a request and `nrqc calculate INPUT.json` for exact answers. The package
[README](native_relational_qc/README.md) has the install steps and a capability
table of all eleven backends; CI runs the suite on Python 3.11 and 3.12, with and
without Qiskit.

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

