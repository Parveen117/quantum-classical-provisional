# Phase–seam foundation prototype

**New: [the trained classifier as a measurement pattern on a fusion-built cluster](CLUSTER_COMPILE.md).**
The v0.29 packet compiles the self-learning branch's four-qubit, five-angle,
three-CNOT classifier into the only form the dual-rail route can execute: a
13-photon tree cluster (12 edges, 7 heralded fusions) read by ten single-photon
measurements whose five trained angles are heater trims on the native π/32
grid. Lemmas G1–G3 are exact at all 64 angles; the pattern's readout
probability equals the circuit's exactly in Q(ζ₆₄) for the XOR checkpoint and
generic angles, every branch checked, with negative controls. Training stays
on the PC; no speedup, advantage or on-chip learning is claimed; the optical
build (1/128 one-shot, ≈ 0.55 with four spare leaves) and storage are open.
[Audit](cluster/qualification.json).

**Previous:** [age-aware memory and coherent fresh-node transfer](LOSS_REFRESH.md) (v0.28: ideal-circuit recovery through all 13 correctable six-photon erasures, age-aware memory budget, v0.26/v0.27 walks reinterpreted as ideal-renewal references), [building the encoded site, Theorem B1](TREE_BUILD.md) (initial-resource estimates, with v0.28 interpretation correction), [loss-tolerant tree code, exact](TREE_CODE.md) (single-round recovery polynomials over every loss pattern), [memory loss in the chain, Theorem M1, and the joint design point](CHAIN_MEMORY.md) (sequential growth suppressed as m^(3J + J(J−1)); x = 1/40 with number-resolving readout for large registers), [ledger violations, Theorems V1 and V2](LEDGER_VIOLATIONS.md) (multi-pair under threshold readout and the dark-to-efficiency ratio gate the register size; dual-rail sweep verdict), [loss as a retained ledger, Theorem L2](LOSS_LEDGER.md) (false heralds are readout-visible, loss is rate not fidelity, square-sourced channel on the native grid), [fusion network with Theorems N1 and N2](FUSION_NETWORK.md) (Bell pairs are a null walk at success 1/2, 3-site resources grow with drift 1/2, limit 3 − √5), [loss budget with Theorem L1](LOSS_BUDGET_810.md) (false-herald fraction (1-η)/(2-η), engine-checked), [810 nm heralded source spec](SOURCE_SPEC_810.md) (exact pair statistics, g2 = 2x, purity law, fail-closed source grade) and [810 nm re-target of the SiN core](CORE_RETARGET_810.md) (scaled nominal, fail-closed readiness grade).

**[Dual-rail route for room-temperature operation](DUAL_RAIL.md).**
The v0.18 module adds an exact few-photon boson engine in the calculator's
field, proves single-site universality from the existing four-heater unit,
evaluates type-I fusion of two Bell pairs exactly (success 1/2, heralded
phases, GHZ merge), shows distinguishable photons keep the success rate but
lose all coherence, and derives the witness-equals-visibility law. The plan
declares 810 nm and silicon detectors for any register size.

**New: [temperature-sweep evidence contract](TEMPERATURE_SWEEP.md).**
The v0.17 module separates room-temperature operation, temperature-independent
logical transfer and temperature-independent physics. It proves exact
common-mode invariance of all 24 observables, the kernel-or-correctable
dichotomy for phase-only drift, a declared thermo-optic scale and the
two-photon coincidence at one unit, and supplies an unrun sweep protocol with
a fail-closed verdict. The present SNSPD route grades as cryogenic; no
temperature claim follows without a recorded log.

**New: [effective Hamiltonian and microscopic error bridge](BUS_HAMILTONIAN.md).**
The v0.16 design compiles both bus kicks from a conditional level-shift
interaction and bus Fourier transforms. Centering needs finer exact phases,
supplied by the unchanged collaboration arithmetic module. Analytic area
sensitivities retain finite-level boundary projectors, and a JC comparison
retains bare-state dressing, nonlinear shifts and outside-code transitions.
All physical controls and additional error budgets remain declared inputs.

**New: [local-control obstruction and bus-mediated EMK gate](WEYL_BUS.md).**
The v0.15 exact word checker connects the existing two-site interaction to a
conditional bus loop. It proves arbitrary-state bus return, specified local
drift cancellation and dimension requirements for this signed-control family.
An explicit fault table shows which errors reach the data and why full Weyl
fault immunity would remove this rectangle's entangling action. The physical
bus couplings remain added assumptions; the geometric gate has known prior art.

**New: [TVSP constitutive response and finite-patch bounds](CONSTITUTIVE_RESPONSE.md).**
The v0.14 cubic-energy adapter supplies six constrained responses, first
layers and selected EMK curvature, then generates the material phase/control
map. Rational patch bounds supply state and optical nonlinear-remainder
bounds to the existing observer contract. Harmonic covariance retains common
noise cancellation. All model coefficients remain declared, not measured.

**New: [target-specific observer and uncertainty adapter](PHOTONIC_OBSERVER.md).**
The v0.13 adapter applies the earlier observer theorem to an explicit angle
or relative-phase target, with declared coordinate scales and nuisance
responses. An optional byte-pinned adapter reuses the existing device engine
without vendoring its private code. Missing bounds, target blindness and
numerically unreliable decoding cannot pass the conditional model gate.
No result accepts a physical calibration or submits hardware work.

**New: [coupled response and optical observer](PHOTONIC_RESPONSE.md).**
The v0.12 local audit differentiates the actual four-phase component word in
the existing exact field. At the ideal quadrature target, basis powers read
one phase combination; coherent local probes read three; interference with
a bypass reads four relative combinations. Reference drift is explicit.
The unrun acquisition plan binds the GDS and reserves all 28 heater responses
per unit, with all 31 assembled controls recorded. No material coefficients,
thermal/Maxwell solve or drive voltages are supplied by this ideal audit.

**New: [heated-core GDS and physical calibration](PHOTONIC_LAYOUT.md).**
The generated core subassembly places six exchange units, four bypasses and
an isolated guard. Its 28 heaters and 56 pads have a mapped physical
interface. Independent KLayout checks cover selected feature rules and
optical/electrical connectivity, including deliberately damaged layouts.
The explicit physical calibration profile requires 31 recorded channels
and binds both the layout specification and GDS byte hash. It contains no
measured values. Optical coupling, packaging and full foundry review remain
open; the drawing is not a fabricated or experimentally validated device.
The v0.11 register audit passes **199 tests in 123.801 seconds**; the separate
CAD audit passes **9 tests**. Both report zero failures, errors and skips.

**Previous: [optical I/O and calibration binding](PHOTONIC_IO.md).**
All 106 preparation/core/guard/analyzer routes now compile to the existing
exact calculator. The candidate process is pinned to CORNERSTONE SiN300
software, with two-input MMI interfaces explicitly selected. The offline
calibration adapter requires a complete recorded voltage vector and matching
device, assembly, phase-trim, temperature and validity context. No measured
calibration or fabricated layout is supplied by the empty template.
The v0.10 combined audit passes **193 tests in 121.041 seconds**, with no
failures, errors or skips.

**Previous: [first photonic carrier design](PHOTONIC_EXCHANGE.md).**
The grid-4 fixed-pair balanced exchange maps exactly to six disjoint
interferometers and four bypasses on 16 single-photon code paths, with one
isolated guard. A logical netlist, 106-setting unrun characterization plan
and complete herald-window accounting are generated by the existing audit.
The selected component classes are SiN paths, nominal 1550 nm, an external
heralded source and SNSPD readout.

This is a restricted encoded interaction prototype; the paths are not
independent qubits, and its guard does not independently measure four-mode
closure. Source/detector calibration, process geometry, physical fabrication
and nondestructive pointer readout remain open. The v0.9 audit passes
**181 tests in 111.008 seconds**, with no failures, errors or skips.

**Previous: [continuous control inside the closure sector](SECTOR_CONTROL.md).**
The balanced reset now has an explicit involutive data/record exchange.
Its proposed generator `H(t)=hbar*g(t)*(I-P)/2` preserves the modular
phase-sum sector at every real pulse angle. The proof uses the native
involution and sector projectors; a physical realization of that generator
is an added engineering assumption.

The adapter reuses the existing compiler, controlled arithmetic and exact
phase engine. It covers balanced cuts, shifts, swaps, reads and balanced
reset in full and compressed layouts. Exact fractional verification checks
coherent intermediate states, flag cleanup and zero ideal leakage. A
single-mode negative control leaks probability 1/2 at a half pulse.
Its binary verification gates are not a physical continuously constrained
implementation. No new simulator or material-device claim is introduced.

The v0.8 combined audit passes **170 tests in 110.823 seconds**, with no
failures, errors or skips. Material coupling, locality, pointer preparation,
calibrated rates and physical leakage remain open.

**Previous: [balanced reset with retained records](CONTROLLER.md#61-explicit-balanced-reset-source-law).**
The explicit `pair_reset(j,reservoir,a)` sets one mode to its reference,
adds the old phase difference to another mode, and retains that difference
in a fresh coherent record. The integer lift sum is preserved. The same
controller supports full and compressed fixed sectors, including an omitted
reset mode. At grid 64, pair_reset(0,2,0) uses **34 logical wires / 193 gates**
in full form and **28 wires / 132 gates** when reservoir 2 is omitted.
These include the 6 retained record bits; full/compressed conversion is extra.
Old operations keep their meanings, and single-mode fixed-sector reset
remains rejected. This is a new declared transfer rule, not fabricated hardware.

The v0.7 audit passes **156 tests in 97.389 seconds**, with no failures,
errors or skips: 16 balanced-reset tests plus the prior 140, with exact
coherent full/compressed comparisons, untouched-reference marginals, dirty
record behavior, all supported widths and existing measurement/feedback checks.
See the current [qualification](register_qualification.json) for results.

**Previous: [native read/reset with retained controller records](CONTROLLER.md).**
Each read/reset has a fresh record of its wrapped relative phase, using the
existing compiler, arithmetic and dynamic measurement engine. Coherent reset
transfers information into the record; joint inverse recovery requires
coherent records to remain available. At grid 64, a full stored-phase read
at reference zero uses 6 gates and reset uses 18, each with 6 retained record
wires in addition to the 28-wire full layout. The compressed layout supports
read, including its derived omitted phase; single-mode fixed-sector reset
is rejected. Gamma, lifts and path/cost history remain classical.

The v0.6 combined audit passes **140 tests in 52.509 seconds**, with no
failures, errors or skips: 16 controller tests, the prior 117 targeted tests,
and seven relevant existing dynamic-engine checks. Fresh pointer records and
their measurement are explicit model choices; no physical device is inferred.

**Previous: [fixed-closure compression in the phase-register compiler](REGISTER.md).**
The optional `omit_mode` layout derives one phase from the other three and
the known closure sum. At grid 64 it uses **18 phase + 4 workspace = 22
logical wires**, down from 28. The example pair_cut(0,2,0) uses 24 rather than
59 gates when mode 2 is omitted. Other omission choices can increase gate
cost. Reversible conversion retains any off-sector residual; its 28-wire
peak and conversion gates are counted separately. Full/compressed execution
agrees in exact amplitudes, including a coherent external reference.

The v0.5 combined audit passes **117 tests in 53.016 seconds**, with no
failures, errors or skips. The known-sector constraint and earlier quantum
circuit assumptions remain explicit; no new physical postulate is added.
Gamma, winding and event/cost history remain in the original classical Cell.

**Previous: [native cuts on an orthogonal phase register](REGISTER.md).**
An adapter to the existing reversible arithmetic compiles cuts, balanced cuts,
shifts, swaps and shears, with whole-sector closure checks. At grid 64 the
layout uses 24 phase wires + 4 clean workspace wires. Gamma, lifts, cost and
history stay in the original Cell. This is a new larger encoding, with
coherent circuit semantics explicitly assumed; the old code's obstruction
remains valid. The combined v0.4 audit passes **103 tests** in 47.541 seconds,
with no failures, errors or skips.

Run `python benchmarks/phase_seam_register_audit.py` for the current combined audit.
[Qualification](register_qualification.json) · [Tests](register_test_results.txt) ·
[Reuse/branch audit](register_source_manifest.json).

**Previous: [tomographic phase/seam bridge](ENCODING.md).**
All four phases and Gamma are recoverable from nine exact operator readings
on supported grids through 64 bins. Classical provenance retains winding and
event order. Opposed pair shifts and a paired swap have checked unitary
translations; a balanced-cut counterexample excludes a full deterministic
channel correspondence for this encoding. The mixed code does not contain
the v0.2 pure Bell resource.

The v0.3 combined audit passes **87 tests**: 23 encoding tests, 26 joint tests,
26 v0.1 tests and 12 calculator checks, with no failures, errors or skips.

**New: [two-site algebraic quantum completion](JOINT_READOUT.md).**
EMK multiplication plus explicitly added positive-state, composition and
measurement postulates gives exact CHSH=2 sqrt(2), non-signaling marginals,
sequential instruments and a recovered four-dimensional GNS representation.
This is a conditional quantum-compatible completion, not a physical device
or a derivation of the probability postulates from phase points.

The combined v0.2 audit passes **64 tests**: 26 joint-algebra/readout tests,
26 v0.1 foundation tests, and 12 existing calculator tests, with no failures,
errors or skips.

The original v0.1 is an executable finite proposal based on Monty's four supplied LaTeX
manuscripts. The cell uses phases, oriented cuts, a seam label and retained
history. It has no primitive amplitude vector or inner product. Its declared
probability/composition law is currently classical; Hilbert/Born recovery and
physical quantum hardware remain open.

- [Foundation, derivations, assumptions and unresolved claims](FOUNDATION.md)
- [Four-mode hardware interface and acceptance tests](HARDWARE_CONTRACT.md)
- [Reviewed source hashes](source_manifest.json)
- [Qualification and compatibility diagnostics](qualification.json)
- [Targeted test results](test_results.txt)

Validation: **38 tests passed** (26 foundation checks and 12 existing calculator
checks), with no failures, errors or skips. The saved report binds the checked
code and test hashes. This is targeted verification, not a rerun of the earlier
full native suite or certification of the complete manuscripts.

```bash
python -m phase_seam_foundation
python benchmarks/phase_seam_audit.py
```

For the new completion:

```bash
python -m phase_seam_foundation.joint_qualification
python benchmarks/phase_seam_joint_audit.py
```

[Joint qualification](joint_qualification.json) ·
[Joint source/assumption manifest](joint_source_manifest.json) ·
[Combined targeted tests](joint_test_results.txt)

For the encoding:

```bash
python -m phase_seam_foundation.encoding_qualification
python benchmarks/phase_seam_encoding_audit.py
```

[Encoding qualification](encoding_qualification.json) ·
[Encoding test results](encoding_test_results.txt)

Two different oriented cuts generate transport. The new balanced pair cut
preserves the finite phase-closure sum. Exact histories distinguish paths
with equal phase or cost. The readout law is explicitly normalized, and its
local Bell/CHSH bound is proved and checked. A separate conditional diagnostic
prevents misidentifying the cut with universal quantum conjugation.

This package keeps the original foundation interpreter separate from the
six-bit Shor calculator. The v0.4 adapter now imports its existing arithmetic
and gate IR, and uses its coherent engine in explicitly quantum tests. It
does not change the original classical law or inherit 2056-site
structured-simulation claims. Four modes are not four qubits.
