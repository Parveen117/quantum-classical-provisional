# Four-mode phase–seam cell: functional hardware contract

Author: Monty. Version 0.11. Status: functional interface and first encoded
carrier design; no fabricated device or measured tolerances/capacity.

The [v0.2 joint-readout note](JOINT_READOUT.md) now supplies a conditional
two-site algebraic quantum completion and the explicit coupling target
U(chi)=cos(chi)I-sin(chi)R_A L_B. The encoding from this four-phase cell to
those operator states remains open; the classical device does not acquire
quantum behavior through that separate probability postulate alone.

The [v0.3 tomographic bridge](ENCODING.md) identifies a working subset:
opposed phase transports map to local phase gates, and paired mode swaps map
to site exchange. Its balanced-cut channel obstruction and mixed-state image
bound prevent treating that subset as a complete physical hardware encoding.

The [v0.4 register compiler](REGISTER.md) supplies a different orthogonal
wrapped-phase encoding. Native reversible operations now compile through the
existing X/CX/CCX arithmetic; grid 64 uses 24 phase + 4 clean workspace wires.
The balanced cut (0,2,0) needs 59 logical gates in this implementation.
This supplies an executable interface target, not a physical transfer law.
The larger code retains distinguishable labels; it is not obtained by a
channel that extracts exact labels from the v0.3 mixed code.
Gamma and unwrapped path/cost/history stay in the original classical Cell.
Closure holds at source-operation boundaries; elementary gate steps may
leave the sector. A strictly constrained carrier needs additional design.

The v0.5 fixed-sector layout reduces stored phase coordinates to three:
18 phase + 4 clean workspace wires at grid 64. For pair_cut(0,2,0), omitting
mode 2 reduces the count to 24 logical gates. A reversible full-register
codec zeros the omitted register exactly on the known sector and otherwise
retains the closure residual. Conversion still peaks at 28 wires; each
direction takes 183 logical gates for sign +1, twist 0. Direct compressed
preparation and physical gate costs remain separate engineering requirements.
Reconstructing a fourth phase from the constraint is not an independent
measurement confirming that constraint.

The [v0.6 controller](CONTROLLER.md) makes read/reset records explicit.
Every native read/reset allocates a fresh width-bit pointer; coherent reset
moves the old phase information and its correlations into that pointer.
Pointer measurement uses the existing dynamic engine. At grid 64, one
record adds 6 logical wires; full read(0,1) followed by reset(0,2) uses 40
wires and 99 logical gates. Fresh physical record initialization, memory
noise and record erasure/recycling remain unmeasured engineering requirements.
Single-mode reset on a fixed closure sector remains rejected. The explicit
v0.7 `pair_reset(j,b,a)` adds a compensating native-mode update:
`x_j'=a, x_b'=x_b+x_j-a`, with a retained record `r=x_j-a mod L`.
Its integer-lift version preserves the sum; its coherent circuit preserves
wrapped closure at source boundaries and supports every compressed layout.
At grid 64, sign +1, twist 0, pair_reset(0,2,0) uses 34 logical wires and
193 gates in the full layout, or 28 wires and 132 gates with reservoir 2
omitted. The reservoir is another phase mode, not a thermal environment.
This is a declared software transfer law; physical continuous confinement
to the sector, initialization and control remain unimplemented.

The [v0.8 sector-control construction](SECTOR_CONTROL.md) now specifies the
continuous interaction target. Its balanced exchange
`P:(x_j,x_b,m)->(a+m,x_b+x_j-a-m,x_j-a)` is an involution conserving the
data sum for every pointer value. The proposed drive
`H(t)=hbar*g(t)*(I-P)/2` gives
`U(theta)=(I+P)/2+exp(-i*theta)*(I-P)/2` and preserves the closure sector
for every real pulse area, completing reset at area pi with a fresh pointer.
The pointer is neutral under the logical data-closure operator; material
charge assignments must be specified separately.

This closes the operator-level interpolation requirement conditionally.
It does not supply a local material Hamiltonian, a calibrated pulse,
automatic noise protection or a derived clock. Existing binary arithmetic
verifies exact sampled operators; its intermediate gates still need not
preserve the sector. The unchanged hardware task is to realize the
declared native symmetric generator and measure its intermediate evolution.

The [v0.9 photonic prototype](PHOTONIC_EXCHANGE.md) selects a first encoded
realization: a single photon across 16 SiN code paths for a grid-4 fixed
pair sum and one pointer. Six disjoint MZIs and four bypass paths implement
the balanced exchange; an isolated guard path monitors optical code escape.
The nominal operating target is 1550 nm, with an external heralded SPDC
source and SNSPD readout. An exact netlist and 106-setting unrun protocol
are included. This represents a restricted native subspace, not four
independent physical phase channels. The path count is not a qubit count.
Fabrication geometry, phase-voltage maps and measured performance remain open.

The [v0.10 I/O adapter](PHOTONIC_IO.md) supplies the ordered preparation and
analysis stages, exact whole-setting verification and an offline interface
for joint calibration records. A CORNERSTONE SiN300 software candidate is
pinned; its default one-input MZI splitter must be replaced by a two-input
component. Heated geometry and actual driver calibration remain to be
supplied. Nine logical phase channels exclude extra port-trim/stabilization
actuators. The generated calibration template contains no measured values.

The [v0.11 core subassembly](PHOTONIC_LAYOUT.md) now supplies placed/routed
GDS geometry with 28 heaters, 56 pads and 34 open optical ports. The four
heaters in each exchange support arm, common-phase and input/output phase
control; four more trim the bypasses. Local KLayout checks and negative
controls cover selected geometric properties. The physical calibration
profile records all 31 chip/external phase channels and binds the GDS hash.
This is not a full foundry DRC pass, packaged chip or measured transfer.

The proposed hardware primitive stores **four controllable cyclic modes**, a
seam calibration and retained history. It is not specified as four qubits.
Its required actions follow the finite operational model in
[FOUNDATION.md](FOUNDATION.md); their material realization remains open.

## Cell interfaces and acceptance tests

| Block | Required action / exposed data | Acceptance check |
| --- | --- | --- |
| Four phase channels T,V,S,P | Prepare and hold independently addressable cyclic coordinates | Repeat preparations; measure phase drift and cross-talk for all four channels |
| Reference and seam calibration | Supply declared readout axis and cut orientation; separately calibrate positive Gamma and dual | Check measured ratio relation and reference reproducibility; do not infer an angle from log(Gamma) without a map |
| Oriented cut | Implement theta' = 2alpha-theta on the declared carrier domain | Double cut restores carrier coordinates; two axes produce twice their angle separation |
| Balanced coupling | Reflect mode j while mode s receives the compensating phase 2theta_j-2alpha | Pair-cut twice restores both modes; two pair cuts translate them equally and oppositely; phase-sum closure persists |
| Transport / swap | Controlled phase increments and mode exchange | Compare against independently measured output phases; report any reservoir participation |
| Lift/path observer | Record directed crossings or another declared continuous-path observable | Distinguish a full forward turn, full reverse turn and no turn although their endpoints agree |
| Event memory | Retain commands, references, outcomes, state estimates and rejection conditions | Replay records; preserve different histories at equal cumulative cost; detect incomplete logs |
| Readout instrument | Report outcomes with a calibrated probability and state-update law | Check normalization and repeated/conditional outcome statistics; quantify backaction |
| Reset | Prepare the reference state while recording relevant output/environment exchange | Show lost carrier information is not claimed recoverable without its record; measure heat/energy separately |
| Balanced reset | Reset mode j to a, transfer x_j-a into a distinct native reservoir, and retain the wrapped outcome | Check the data sum at source boundaries, record correlations and inverse recovery with coherent records; account for intermediate excursions |
| Continuous symmetric drive | Realize the declared native generator while preserving the data-closure charge | Sample intermediate pulse areas; measure leakage and coherent phase against the v0.8 target; compare a symmetry-breaking control |
| Admission/limits | Enforce declared closure sector, finite counters, memory and controls | Reject invalid commands as a whole; retain all rejected trials in experimental records |

The current shear is an optional algebraic comparison, not a required physical
interaction. The balanced cut is the more direct proposed primitive because
it preserves the specified closure sum. The model does not derive its
Hamiltonian, pulse shape, rate, locality, material coupling or dissipation.

Default software resolution is L=64: 5.625-degree phase bins and
2.8125-degree **axis** bins. These are quantization steps, not achieved
hardware precision. Any phase-error allowance, repetition rate, memory depth,
coherence requirement, bandwidth and energy budget needs a target workload,
noise model and measured transfer function before a numerical specification
can be justified.

## Minimal functional assembly

A first engineering emulator could use four controlled phase channels,
reference/phase detectors, a control processor, and event/crossing memory.
The control processor would execute the declared cut and compensating-mode
updates and expose the same interface as the Python model. Such a device would
test classical phase transfer, calibration and memory; it would not establish
quantum coherence or an unknown quantum-state measurement law.

The selected first **encoded demonstrator** uses optical paths, with a
derived MZI transfer matrix for the native exchange. This does not select
a definitive scalable QPU substrate or prove a material realization of
four independent native modes. Carrier choice is an engineering addition;
the selected SNSPD readout also requires detector cooling. Neither a
room-temperature apparatus nor a full quantum computer follows from the
phase/seam notation.

The executable minimum has these interfaces:

```python
from phase_seam_foundation import Cell, Config, Operation, Readout, Atom, Preparation
from fractions import Fraction

cell = Cell.start((2, 1, 0, -3), config=Config(grid=64, sector=1))
cell = cell.apply(Operation("pair_cut", (0, 1, 0)))
cell = cell.apply(Operation("pair_cut", (0, 1, 1)))
# Lifts are now (3, 0, 0, -3); the closure sum remains zero.
prepared = Preparation((Atom(Fraction(1), (cell,)),))
outcomes = prepared.distribution((Readout(0, 0), Readout(0, 1)))
# {(3, 0): Fraction(1, 1)} under the explicitly classical v0.1 law.
```

The ledger contains exact commanded values in software. A physical prototype
must distinguish those commands from actual measured states, including their
uncertainties; writing a target value into a log is not evidence it happened.

## Four readiness stages

1. **Finite consistency — implemented.** Exact cell transitions, closure
   checks, bounded records, explicit normalized classical preparation/readout,
   and local-composition limitations have tests and reproducible reports.
2. **Physical transfer laws — candidate specified, validation open.** The
   v0.9 encoded photonic route has an explicit coupled transfer, codebook,
   source/readout choice and characterization plan. Fabrication, calibrated
   state preparation, noise/cost units and measured transfer remain open.
   Independent lift/path observation and the physical Gamma/seam mapping
   are not supplied by that encoding.
3. **Quantum recovery or distinguishable new prediction — open.** Define the
   native joint-state law, recover the required quantum probabilities or give
   a falsifiable alternative. Current positive shared preparations plus local
   readouts have CHSH <= 2. Do not bypass this by setting-dependent samples,
   communication between separated readouts, or discarding failed outcomes.
   If the cut is identified with universal quantum conjugation, resolve the
   exact complete-positivity obstruction recorded in the qualification.
4. **Scalable computing — open.** Only after the preceding laws are supported,
   specify composable logical operations, state preparation, measurement,
   noise/error correction, resource accounting and workload scaling. A Bell
   violation alone would not prove universality or algorithmic speedup.

Changing mathematical representation can change how a device is described.
It does not on its own supply controllable physical interactions. Conversely,
a finite classical prototype is useful for eliminating inconsistent rules
before a physical realization is proposed. This contract supports that step
without treating its assumptions as established laws of nature.

## Concrete next deliverable

The v0.11 heated core now has explicit geometry and open interfaces. Next,
it needs optical coupling/packaging, probe/PCB integration and full foundry
rule review. The external preparation/analysis modules need measured port
phases and stable patch routing. Joint voltage-vector acquisition across
the complete actuator set, source/detector response and a loss budget are
required before physical comparison with the proposed intermediate-angle
transfer and cross-block phase targets.

The prototype's guard monitors optical code escape; closure is built into
its fixed-sum code and is not independently verified on four physical
phase channels. Terminal photon detection destroys the joint data/pointer
carrier, so nondestructive record measurement and recycling remain open.
Coherent unwrapped path/cost history and a scalable architecture also remain
separate requirements. No hardware experiment has been submitted.
