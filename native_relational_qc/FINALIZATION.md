# Finalization of the bounded circuit-design software

Monty · 12 November 2026

The current release scope combines bounded state preparation, the four-qubit
native-phase classifier and offline device-target compilation. Its scope is
fixed by the supported input schemas and resource limits. Further algorithm
families can be developed as additional capabilities.

| Work item | Current state | Completion evidence or remaining action |
| --- | --- | --- |
| Goal-to-circuit construction | Implemented | Bell signs and three/four-wire GHZ goals, exact acceptance and rewrite replay |
| Phase and structure training | Implemented | Five declared topologies, frozen model selection, exact held-out comparison |
| Saved-model inference | Implemented | Original and topology checkpoints, matching feature views, exact prediction |
| Device-target compiler | Implemented for the model family | Directed placement/routing, native gate caps, three/four-wire targets |
| Export and replay | Implemented | Exact OpenQASM round-trip and active-register basis checks |
| Qualification of these paths | Recorded | Source-pinned synthesis, learning and runtime audit records |
| Repository integration and release | Qualified review candidate | Python 3.12 checks and installed-wheel commands are recorded. Review/merge and release tagging remain |
| Actual device execution | Hardware work | Bind a measured device's gate set, wiring, phase controls and readout to a device adapter |
| Experimental qualification | Hardware work | Record device runs, compare declared observables with the exported reference and use the existing evidence bridge |

The software's offline work can be reviewed and released within these stated
capabilities. The measured-hardware milestone needs the actual controller,
calibration and results from the experimental route.

The [software qualification record](../benchmarks/records/software_qualification_20261112.json)
accounts for 1,183 collected repository tests. The full run had 1,125 passes,
57 skips and one failure in the shipped-example schema check. The fix adds
the new goal/device descriptors to their respective validators, while retaining
their rejection as calculator requests. All 11 schema tests then passed, and
the formerly failed test passed in its own last-failed rerun. Current accounting
is 1,126 passing cases and 57 skipped cases, from the full run plus that
targeted correction. A separate focused run had 55 passes and one optional
Qiskit skip. The NumPy-core wheel was built, installed outside the checkout,
and exercised through both installed model commands on Python 3.12.14.

The next development packets have concrete outputs.

1. Connect the lab controller to the exported circuit and physical readout map.
   Record the supported native operations, success/heralding conditions and
   measured calibration ranges for that specific device.
2. Feed actual counts into the existing expected-model/evidence bridge with the
   prediction record's model, input, program and device bindings preserved.
   Keep measured data and ideal reference data identifiable in the record.
3. Qualify repeated operation and its failure/retry behaviour on that device.
   Report the achieved workload, readout agreement, errors and throughput.
4. Publish the software release and experimental evidence under their respective
   demonstrated capabilities, with reproducible commands and source pins.

Pāṇini source compilation continues in Recognition-Kernel-Framework. The current
calculator uses the documented Pāṇini-inspired context and transformation
mechanisms. Importing additional Sanskrit grammar machinery is a separate
integration packet with its own demonstrated use.
