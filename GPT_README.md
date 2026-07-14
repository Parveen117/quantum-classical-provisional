# GPT Repository Guide

## Repository identity

- GitHub: `Parveen117/quantum-classical-provisional`
- Local path: `C:\Users\abc\Desktop\New Folder (2)\New folder\PROVISNAL RELATED\Quantum classical`
- Updated: `2026-07-14T05:21:33.059712+00:00`

## Primary role

This repository is the canonical working location for:

- IBM Quantum Runtime acquisitions
- logical and transpiled quantum circuits
- physical-backend measurement results
- quantum control experiments
- quantum-native certificates and hashes
- calibration references
- negative and positive quantum validation results
- experiments that are not yet classified as device evidence

Do not place general device architecture documents here unless they are
required to reproduce a quantum experiment.

## Connected device repository

- GitHub: `Parveen117/EMK-Tensor-Cell-Devices`
- Local path: `C:\Users\abc\Desktop\New Folder (2)\New folder\PROVISNAL RELATED\Devices`

Device-related quantum results may be transferred to the device repository
only when they are explicitly tagged:

`TRANSFER_TO_EMK_TENSOR_CELL_DEVICES`

Every transfer must preserve:

- IBM Runtime job ID
- backend name
- calibration reference
- submitted circuit files
- raw result files
- analysis file
- certificate
- SHA-256 hashes
- scientific interpretation boundary

After a verified transfer, this repository should retain a compact receipt in:

`transferred_device_evidence/`

## IBM Quantum work completed on 2026-07-14

### 1. Double-triangle topology baseline

- Backend: `ibm_kingston`
- Job ID: `d9aruo66hjac73fesiog`
- Result: mixed
- Static topology advantage: not observed
- Perturbation sensitivity: observed
- Interpretation: topology analogue only

### 2. Compiled UGD star-delta benchmark

- Backend: `ibm_kingston`
- Job ID: `d9as3eug26ic73df5j20`
- Classification: `NO_UGD_COMPILED_ADVANTAGE`
- Result: negative
- Meaning: the static residue-weighted RZZ surrogate did not outperform
  fixed or shuffled controls
- Important boundary: this was not a faithful test of the full UGD RK/KR
  operator structure

### 3. UGD RK/KR operator-order and seam-memory benchmark

- Backend: `ibm_kingston`
- Job ID: `d9as7a66hjac73fet1q0`
- Classification: `UGD_RK_KR_SEAM_MEMORY_RECOGNITION`
- Overall result: pass
- Anticommuting RK/KR mean ancilla P(1): `0.973511`
- Commuting-control mean ancilla P(1): `0.025574`
- Order-erased control mean ancilla P(1): `0.027771`
- Mean visible RK/KR TVD: `0.001160`

Interpretation:

The hardware implementation preserved a strong operator-order record in an
ancilla while the visible RK and KR system distributions remained nearly
identical.

Scientific boundary:

This validates a faithful quantum representation of the UGD RK/KR
operator-order and seam-memory architecture. It does not prove UGD as a new
physical law, because the underlying anticommutation is established quantum
mechanics.

## UGD framework reminder

The vault defines a UGD state as:

`U = (phase, scale/support, seam charge or memory)`

The defining operator relations are:

`R^2 = -I`

`K^2 = I`

`RK = -KR`

Future experiments must not reduce UGD to arbitrary static gate-angle
modulation. A faithful test should explicitly represent:

- R circular phase transport
- K hyperbolic seam transport
- RK/KR order dependence
- a seam-memory or ledger register
- visible projection versus hidden seam state
- closure and negative controls

## Next intended quantum experiment

Embed the passing RK/KR seam-memory primitive into matched star and delta
device architectures.

The next benchmark should compare:

- ordinary star topology
- ordinary delta topology
- star with RK/KR seam ledger
- delta with RK/KR seam ledger
- commuting negative control
- order-erased negative control

Primary question:

Does the seam-memory primitive improve perturbation detection, routing,
closure, or recovery when embedded into a device topology?

## Commit discipline

Do not use `git add .`.

Stage only explicit experiment directories, manifests, receipts, or source
files intended for the commit.

Do not commit:

- `.venv-quantum/`
- notebook checkpoints
- accidental temporary files
- credentials
- IBM Quantum tokens
- SSH keys
- unreviewed bulk outputs

Unsigned commits may be created in Jupyter with:

`git -c commit.gpgsign=false commit ...`

This disables signing only for that individual commit.
