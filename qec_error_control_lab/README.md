# QEC Error-Control Laboratory v1

This private experimental package is the first bounded quantum-error-control
cartridge for the quantum-classical programme.  It is intentionally separated
from the narrow public Multi-Ledger Operator-Memory release.

The laboratory now has two levels:

1. a three-qubit repetition-code cartridge for one X error;
2. a nine-qubit Shor-code cartridge for one arbitrary X, Y, or Z error.
3. a 17-qubit ancilla extraction circuit specification and optional Qiskit adapter;
4. a bounded encoded-vs-unencoded phenomenological noise comparison.

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

Pinned ancilla circuit specification SHA-256:

```text
5e1610cbf3a8ec4146001218381b57d8b791732901b8f7bf8956adaeec93e291
```

Pinned phenomenological noise certificate SHA-256:

```text
7a0df18786d664dc9d05fb4d0366e309c538ec5be2d01bba16740a5efe087f2e
```

## Run

From this directory:

```bash
python -m unittest -v test_qec_repetition.py
python run_campaign.py --output generated/qec_error_control_certificate.json
python -m unittest -v test_qec_shor.py
python run_shor_campaign.py --output generated/shor_qec_certificate.json
python -m unittest -v test_qec_circuit_and_noise.py
python run_noise_benchmark.py --output generated/noise_benchmark_certificate.json
```

The campaign is dependency-free and deterministic.  The generated certificate
is intentionally ignored as a runtime artifact until a release/evidence intake
process explicitly promotes it.

## Scientific and engineering boundary

This package establishes exact simulator-level behavior for the three-qubit
repetition code and the nine-qubit Shor code under their declared error models.
It includes an ancilla extraction prototype and a deliberately bounded analytic
noise comparison.  It does **not** establish:

- a fault-tolerant logical gate set;
- protection against correlated multi-qubit errors;
- a threshold theorem or scalable architecture;
- physical-device, quantum-sensor, or quantum-computer validation.

The optional Qiskit adapter materializes the declared circuit but never submits
a job by itself.  Hardware evidence must remain separate from the exact
statevector and phenomenological certificates in this folder.
