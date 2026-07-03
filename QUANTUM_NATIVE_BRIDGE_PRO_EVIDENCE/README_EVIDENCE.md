# Quantum Native Bridge Pro Evidence Package

This folder records a compact enablement package for the Quantum Native Bridge Pro implementation.

## Purpose

The package demonstrates a practical quantum-classical verification layer:

- Root circuit/job identity hashing.
- Template/gate/control-path hashing.
- Phase/backend/session/noise binding.
- Measurement-distribution gap scoring.
- Phase-coherence penalty.
- Recognition-residue classification.
- Append-only bridge ledger.
- Certificate export.

## Files

```text
QUANTUM_NATIVE_BRIDGE_PRO_EVIDENCE/
  demo-bridge-ledger.jsonl
  demo-bridge-certificate.json
  README_EVIDENCE.md
```

## Evidence anchors

- Head chain hash: `4b68418b727d8c0eb1384d047f9133604f6931fa602145e2c979913e759abcc0`
- Certificate hash: `e574fb67a72986fffc339b199fd5a974e6b7684235401ffce84271a3277ce0d2`
- Records: `2`
- Version: `0.4.0-qbridge-pro`

## Verification command

From repository root:

```bash
python -m quantum_native_bridge_pro.cli verify \
  --ledger QUANTUM_NATIVE_BRIDGE_PRO_EVIDENCE/demo-bridge-ledger.jsonl
```

## Provisional drafting support

This evidence package supports claim language for:

1. A quantum-classical job record formed from a root identity, template/gate/control path, phase/backend/session binding, and observed measurement output.
2. Measurement-distribution gap analysis against a lawful expected distribution.
3. Phase-coherence penalty applied to a bridge residue score.
4. Classification into recognition, bounded-residue, or actionable-residue states.
5. Append-only quantum-classical bridge ledgering.
6. Certificate generation with head chain hash, residue count, head record, version, and certificate hash.
7. Technical action on actionable residue, including repeat shots, reject output, recalibrate backend, reroute job, apply correction, or human review.

## Scientific note

The included deterministic expected distribution is an enablement-safe bridge signal. For hardware deployment, connect backend-specific expected distributions, calibration data, transpiler metadata, noise models, and measurement-correction matrices.
