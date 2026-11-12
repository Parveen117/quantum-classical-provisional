# Finalization of the bounded circuit-design software

Monty · 12 November 2026

The current review candidate combines bounded state preparation, the four-qubit
native-phase classifier, offline device-target compilation and recorded-acquisition
qualification. Its capabilities are fixed by its schemas and resource bounds.

| Work item | Current state | Completion evidence or remaining action |
| --- | --- | --- |
| Goal-to-circuit construction | Implemented | Bell signs and three/four-wire GHZ goals, exact acceptance and rewrite replay |
| Phase and structure training | Implemented | Five declared topologies, frozen model selection, exact held-out comparison |
| Saved-model inference | Implemented | Original/topology checkpoints, matching feature views, exact prediction |
| Device-target compiler | Implemented for the model family | Directed placement/routing, native gate caps, three/four-wire targets |
| Export and replay | Implemented | Exact QASM round-trip and full active-register basis checks |
| Frozen acquisition plans | Implemented | Measured QASM, shots, raw-count convention, rational tolerance and calibration binding |
| Raw controller artifact intake | Implemented offline | Source-byte SHA-256, strict integer counts, exact Z-marginal comparison and artifact replay |
| Acquisition ledger | Implemented | Idempotent receipts, conflicting-job rejection, writer lock and embedded observation replay |
| Repeated-run campaigns | Implemented | Frozen repetitions, per-run errors, missing/failed acquisitions and outlier-preserving qualification |
| Repository integration and release | Qualified review candidate | Python 3.12 checks and installed-wheel workflow recorded; review/merge and release tagging remain |
| Actual device execution | Hardware integration | Bind the measured device's encoding, gates, channels, calibration and readout to a driver |
| Experimental qualification | Measured evidence | Supply original controller files and calibration artifacts for the frozen campaign |

## Qualification of the current runtime

The [acquisition qualification record](../benchmarks/records/acquisition_qualification_20261112.json)
records a full Python 3.12.14 repository run with **1,166 passes, 57 skips and
zero failures**. The previously skipped cases were then exercised in an isolated
environment with Qiskit 2.6.2, Aer 0.18.2, gdstk 1.0.2 and KLayout 0.30.13. All
57 have a passing targeted execution. This is one full NumPy-core run plus
targeted optional checks. The record identifies each batch and its cases.

The wheel is built and installed outside the checkout. Its smoke covers 20
console commands: prediction, measured plans, source-bound import, exact replay,
idempotent ledger recording and a qualified three-repetition campaign. Changed
artifact bytes and incomplete raw counts are rejected. The installed code hashes
match the qualified source files. No hardware submission occurs.

The retained finite audits cover:

- 64 synthetic sampled acquisitions from the frozen held-out inputs, three exact
  tolerance controls and five rejected binding/result controls;
- a synthetic healthy/residue ledger pair, a byte-identical retry and repaired
  hash-chain negative controls;
- three input contexts with three repetitions each, with missing, timeout and
  biased-outlier controls that retain failed qualification;
- actual source-byte binding and duplicate-key rejection for a synthetic
  controller artifact;
- all 60 ordered measurement maps containing the readout on the three/four-wire
  targets, including a nonidentity final routing layout. These project two
  synthetic full-register histograms.

The [earlier qualification record](../benchmarks/records/software_qualification_20261112.json)
preserves the prior full run and its shipped-example schema correction. The new
full run above is the qualification for the expanded acquisition runtime.

## Remaining completion packets

1. Review, merge and tag the bounded software release under its demonstrated
   capabilities.
2. Implement the actual device driver and encoding described in the
   [controller handoff](CONTROLLER_HANDOFF.md). Supply its supported native
   operations, channel/wire map, calibrated phase response and validity context.
3. Import the actual controller files with their original bytes preserved.
   Qualify repeated operation, failures, errors and achieved throughput under a
   frozen campaign. Provider provenance remains distinct from artifact hashing.
4. For a loss/heralding protocol, add an explicit instrument/event-accounting
   contract before qualifying conditional readout data. The current raw binary
   contract accounts for unconditional shots.

The checked-in photonic calibration file remains an unmeasured template. It can
be populated from the corresponding experimental route. Physical fidelity,
room-temperature performance and computational advantage require their measured
evidence; the current records qualify the offline software workflow.

Pāṇini source compilation continues in Recognition-Kernel-Framework. Importing
additional Sanskrit grammar machinery remains a separate integration packet
with its own demonstrated use. The bounded software capabilities above can be
reviewed and released within their stated scope.
