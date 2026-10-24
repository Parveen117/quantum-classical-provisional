# Phase–seam foundation prototype

**New: [native read/reset with retained controller records](CONTROLLER.md).**
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
