# QEC Error-Control Laboratory v1

This private experimental package is the first bounded quantum-error-control
cartridge for the quantum-classical programme.  It is intentionally separated
from the narrow public Multi-Ledger Operator-Memory release.

The laboratory now has two levels:

1. a three-qubit repetition-code cartridge for one X error;
2. a nine-qubit Shor-code cartridge for one arbitrary X, Y, or Z error.

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

Pinned Shor campaign body SHA-256:

```text
f66642a5d7a5c2246eab653b9a78b1e9d8905f927d485593a80bd79fb1e3bbc0
```

## Run

From this directory:

```bash
python -m unittest -v test_qec_repetition.py
python run_campaign.py --output generated/qec_error_control_certificate.json
python -m unittest -v test_qec_shor.py
python run_shor_campaign.py --output generated/shor_qec_certificate.json
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
model circuit-level ancilla extraction and noisy gates.  Hardware evidence must
remain separate from the exact statevector certificates in this folder.
