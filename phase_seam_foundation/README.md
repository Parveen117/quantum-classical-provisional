# Phase–seam foundation prototype

**New: [tomographic phase/seam bridge](ENCODING.md).**
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

This package is separate from `native_relational_qc`: it does not replace the
existing six-bit Shor calculator, import its quantum probabilities, or inherit
its 2056-site structured-simulation claims. Four modes are not four qubits.
