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
| Retained loss/heralding intake | Implemented offline | Frozen detector policy, explicit conditional reference, exact attempt/yield/error accounting and ledger replay |
| Repeated loss-event campaigns | Implemented offline | Per-run yield/readout gates, undefined conditional outcomes, explicit failed/missing jobs and comparable-context pooling |
| Repository integration and release | Qualified review candidate | Python 3.12 checks and installed-wheel workflow recorded; review/merge and release tagging remain |
| Actual device execution | Hardware integration | Bind the measured device's encoding, gates, channels, calibration and readout to a driver |
| Experimental qualification | Measured evidence | Supply original controller files and calibration artifacts for the frozen campaign |

## Current runtime qualification

The [loss runtime qualification record](../benchmarks/records/loss_runtime_qualification_20261112.json)
pins runtime `dd4e241` and a full Python 3.12.14 repository run with **1,252
passes, zero skips and zero failures**. Qiskit 2.6.2, Aer 0.18.2, gdstk 1.0.2
and KLayout 0.30.13 are installed for this integrated run. All 29 new loss-intake
and loss-campaign tests are included.

The rebuilt wheel is also installed outside the checkout in a NumPy-core
environment without Qiskit. Its 23-command smoke covers loss-plan creation,
source-bound event import, exact artifact replay, idempotent ledger receipts and
qualified repeated campaigns. It preserves undefined zero-accepted outcomes,
blocks a low-yield repetition despite a favourable pooled yield, rejects a
conflicting result and detects changed/missing raw source data. Installed runtime
hashes match the qualified source files. No hardware submission occurs.

The retained finite audits cover:

- seven synthetic loss acquisitions and explicit conditional references,
  including biased heralding, zero acceptance and retained overlapping flags;
- two input contexts with three loss repetitions each, with missing, timeout,
  low-yield, conditional-outlier and zero-accepted controls;
- two finite lossless comparisons with the original unconditional interface,
  plus an exact declared scalar-survival probability of `1/3`;
- the earlier 64 sampled acquisitions, three exact tolerance controls and five
  rejected binding/result controls;
- source-byte and ledger-integrity controls, original repeated-run campaigns,
  and all 60 readout maps over two synthetic full-register histograms.

The [prior acquisition qualification](../benchmarks/records/acquisition_qualification_20261112.json)
and [earlier software qualification](../benchmarks/records/software_qualification_20261112.json)
retain their own runtime/source pins and original test accounting. The current
full integrated run above qualifies the expanded loss-aware software. Instrument
models and physical provenance remain explicitly declared, with artifact
integrity separate from provider authentication.

## Remaining completion packets

1. Review, merge and tag the bounded software release under its demonstrated
   capabilities.
2. Implement the actual device driver and encoding described in the
   [controller handoff](CONTROLLER_HANDOFF.md). Supply its supported native
   operations, channel/wire map, calibrated phase response and validity context.
3. Import the actual controller files with their original bytes preserved.
   Qualify repeated operation, failures, errors and achieved throughput under a
   frozen campaign. Provider provenance remains distinct from artifact hashing.
4. Bind retained loss-event campaigns and their declared instrument probabilities
   to measured detector/encoding evidence. The original raw binary contract
   keeps its unconditional-shot scope.

The checked-in photonic calibration file remains an unmeasured template. It can
be populated from the corresponding experimental route. Physical fidelity,
room-temperature performance and computational advantage require their measured
evidence; the current records qualify the offline software workflow.

Pāṇini source compilation continues in Recognition-Kernel-Framework. Importing
additional Sanskrit grammar machinery remains a separate integration packet
with its own demonstrated use. The bounded software capabilities above can be
reviewed and released within their stated scope.
