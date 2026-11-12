# Handoff to a measured device controller

Monty · 12 November 2026

The saved-model workflow now emits a measured circuit and accepts a strict raw
controller artifact. This document fixes the remaining boundary for a lab driver.
The three-wire example profile is a declared software target. A measured device
must supply its own gate realization, wire identities and calibration evidence.

## Inputs and returned artifact

Give the controller the frozen experiment plan, its `measured_openqasm`, and the
binding's calibration source artifact. The plan includes the final physical
readout after routing. Driver-local wire labels `0..n-1` must map explicitly to
the actual device channels or physical qubit IDs. Preserve that map in the
calibration artifact identified by the binding's source hash.

| Contract | Driver's required realization |
| --- | --- |
| `h` | Hadamard on the declared two-level encoding |
| `s`, `sdg` | Relative phase of `+pi/2`, `-pi/2` on state one |
| `pD`, for admitted `D` | Relative phase of exactly `2*pi/D` in the ideal reference |
| `cx(a,b)` | Control at `a`, target at `b`, on a declared directed edge |
| Terminal measurement | Z readout of each planned physical wire into its specified classical bit |
| Shot count | All planned attempts accounted for by the unconditional binary histogram |

The phase-model reference retains scalar phases. A rewrite into a controller's
native basis needs an explicit convention and a separately verified translation.
The current software compiler verifies its own placement/routing and exact QASM
round-trip. It does not verify arbitrary pulse or voltage programs.

The raw file must follow `nrqc-controller-counts-v1`, illustrated by
[synthetic_controller_counts.json](experiments/synthetic_controller_counts.json).
Repeat the plan, binding and measured-program hashes, concrete provider/backend,
job identity, UTC start/end, shots and canonical binary counts. The importer
computes `source_sha256` from the exact returned bytes. Archive those bytes for
`verify-observation --source-artifact`; provider authentication remains a separate
property of the acquisition route.

## Source-specific physical work

The existing [phase-seam controller](../phase_seam_foundation/CONTROLLER.md)
models finite phase-grid read/reset and retained coherent records. It supplies
source operations and circuit translations that can be reused by an encoding
adapter. The lab's encoded H/CX/native-phase realization and instrument response
must still be supplied for this classifier's circuit family.

The checked-in [photonic calibration template](../phase_seam_foundation/photonic_calibration_template.json)
has status `UNMEASURED_TEMPLATE`, no device/calibration IDs and no settings. It
requests complete configurations across nine actuator channels, their limits,
context, validity interval and evidence hashes. Its row contract uses full
configuration lookup without interpolation. A lab snapshot for that route must
replace those absent values with the applicable measurements.

For a photonic route, loss, invalid detections and heralding require explicit
accounting. The current acquisition schema admits an unconditional binary
histogram. It rejects a histogram whose counts fall short of the planned shots.
A protocol with discarded events needs a separately frozen loss/heralding
contract before its conditional probabilities can be qualified. No-click events
cannot be relabelled as a computational zero without a declared instrument model.

## Completion evidence

The measured-device milestone has concrete outputs: an identified controller
adapter and encoding, the raw calibration artifact, returned controller-count
files bound to the frozen measured circuits, and a campaign report that accounts
for every planned acquisition and failure. Repeated-run qualification uses the
fixed per-run tolerance and preserves outliers. Throughput, fidelity and error
claims require the corresponding measured records and their declared scope.

The software's [finalization state](FINALIZATION.md),
[acquisition contract](MODEL_EXPERIMENT.md), and
[campaign protocol](EXPERIMENT_CAMPAIGN.md) provide the reproducible offline side
of this handoff.
