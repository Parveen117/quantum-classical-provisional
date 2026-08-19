# QEC Error-Control Laboratory v1

This private experimental package is the first bounded quantum-error-control
cartridge for the quantum-classical programme.  It is intentionally separated
from the narrow public Multi-Ledger Operator-Memory release.

## Implemented now

- one logical qubit encoded as `alpha|000> + beta|111>`;
- exact `Z0Z1` and `Z1Z2` syndrome extraction for injected X-error patterns;
- table-driven recovery of any one X error on the three data qubits;
- repeated-syndrome voting that tolerates one faulty report in three;
- fail-closed `INCOMPLETE_SYNDROME` when no exact report has a strict majority;
- exhaustive no-error/single-error trials on four logical states;
- multi-error negative controls that are never promoted as correctable;
- deterministic, SHA-256-bound campaign certificate.

Pinned campaign body SHA-256:

```text
7c0dae4253374839fc5a3aa911d4b66d26200bcdc3c234f21c1ccc065c9d0ca9
```

## Run

From this directory:

```bash
python -m unittest -v test_qec_repetition.py
python run_campaign.py --output generated/qec_error_control_certificate.json
```

The campaign is dependency-free and deterministic.  The generated certificate
is intentionally ignored as a runtime artifact until a release/evidence intake
process explicitly promotes it.

## Scientific and engineering boundary

This package establishes simulator-level behavior for a three-qubit repetition
code under its declared error model.  It does **not** establish:

- correction of arbitrary Pauli errors;
- a fault-tolerant logical gate set;
- protection against correlated multi-qubit errors;
- a threshold theorem or scalable architecture;
- physical-device, quantum-sensor, or quantum-computer validation.

The next cartridge should add the phase-flip companion and then a code that can
correct an arbitrary single-qubit Pauli error, with circuit-level ancilla and
measurement-noise models kept separate from hardware evidence.
