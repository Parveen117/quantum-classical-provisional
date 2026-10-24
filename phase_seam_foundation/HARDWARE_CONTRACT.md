# Four-mode phase–seam cell: functional hardware contract

Author: Monty. Version 0.1. Status: testable interface proposal; no fabricated
device, component selection, measured tolerances, or quantum capacity claim.

The [v0.2 joint-readout note](JOINT_READOUT.md) now supplies a conditional
two-site algebraic quantum completion and the explicit coupling target
U(chi)=cos(chi)I-sin(chi)R_A L_B. The encoding from this four-phase cell to
those operator states remains open; the classical device does not acquire
quantum behavior through that separate probability postulate alone.

The [v0.3 tomographic bridge](ENCODING.md) identifies a working subset:
opposed phase transports map to local phase gates, and paired mode swaps map
to site exchange. Its balanced-cut channel obstruction and mixed-state image
bound prevent treating that subset as a complete physical hardware encoding.

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

We have **not** selected electronic oscillators, optical modes, spins or
another material as the quantum substrate. The manuscripts do not yet give
a physical interaction/readout law from which to choose one. Choosing a
carrier now as the definitive QPU would add an unsupported physical premise.
Neither cryogenic operation nor room-temperature quantum operation follows
from the phase/seam notation alone.

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
2. **Physical transfer laws — open.** Specify a candidate carrier, preparation,
   cut, coupled transfer and measurement instrument. Give the state-dependent
   dynamics and noise/cost units. Resolve how a lift/path is observed and how
   the positive Gamma ratio sets a seam axis.
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

Complete one **two-cell operational experiment on paper**: preparation,
allowed interaction, two independently chosen readout settings per cell,
joint probabilities, and state updates. Derive its table from the proposed
native law, retain every outcome, check normalization and no-signaling, and
state its difference from the v0.1 local baseline. Then map those same
operations to a carrier's physical variables and an experimentally measurable
transfer law. This is the missing link between the current algebra and a
defensible material hardware design.
