# Local IBM Quantum Run Index — 20260714

## Repository placement

These experiments were acquired and retained in the quantum-classical
repository. Directories tagged `TRANSFER_TO_EMK_TENSOR_CELL_DEVICES`
may later be copied into the device repository without modifying their
original files or SHA-256 evidence hashes.

## Experiments

### 1. EMK double-triangle topology baseline

- IBM backend: `ibm_kingston`
- IBM Runtime job: `d9aruo66hjac73fesiog`
- Local evidence directory:
  `device_candidate_evidence/emk_double_triangle_20260714T044725Z`
- Result: mixed result
- Static topology advantage: not observed
- Perturbation sensitivity: observed
- Scientific boundary: topology-level analogue only

### 2. Compiled UGD star-delta benchmark

- IBM backend: `ibm_kingston`
- IBM Runtime job: `d9as3eug26ic73df5j20`
- Local evidence directory:
  `device_candidate_evidence/ugd_star_delta_20260714T045727Z`
- Classification: `NO_UGD_COMPILED_ADVANTAGE`
- Result: negative for the tested static residue-weighted RZZ surrogate
- Scientific boundary: not a test of the complete UGD RK/seam mechanism

### 3. UGD RK/KR operator-order and seam-memory benchmark

- IBM backend: `ibm_kingston`
- IBM Runtime job: `d9as7a66hjac73fet1q0`
- Local evidence directory:
  `device_candidate_evidence/ugd_rk_kr_seam_memory_20260714T050541Z`
- Classification: `UGD_RK_KR_SEAM_MEMORY_RECOGNITION`
- Anticommuting mean ancilla P(1): `0.973511`
- Commuting-control mean ancilla P(1): `0.025574`
- Order-erased mean ancilla P(1): `0.027771`
- Mean visible RK/KR TVD: `0.001160`
- Result: full pass for the predeclared operator-order/seam-memory benchmark
- Scientific boundary: faithful UGD operator representation using established
  quantum anticommutation; not proof of a new physical law

## Provenance rule

The evidence bundles, submitted circuits, analysis files, certificates,
calibration references, job identifiers, and SHA-256 hashes must remain
unchanged when transferred into another repository.
