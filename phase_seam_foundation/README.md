# Phase–seam foundation prototype

An executable finite proposal based on Monty's four supplied LaTeX
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

Two different oriented cuts generate transport. The new balanced pair cut
preserves the finite phase-closure sum. Exact histories distinguish paths
with equal phase or cost. The readout law is explicitly normalized, and its
local Bell/CHSH bound is proved and checked. A separate conditional diagnostic
prevents misidentifying the cut with universal quantum conjugation.

This package is separate from `native_relational_qc`: it does not replace the
existing six-bit Shor calculator, import its quantum probabilities, or inherit
its 2056-site structured-simulation claims. Four modes are not four qubits.
