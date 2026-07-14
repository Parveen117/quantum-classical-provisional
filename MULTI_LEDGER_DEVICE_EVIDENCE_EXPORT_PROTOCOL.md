# Multi-Ledger Device Evidence Export Protocol

## Purpose

This protocol transfers replicated IBM Quantum evidence into the device repository without changing the original evidence files or weakening the scientific boundary.

The required quantum classification is:

```text
CROSS_BACKEND_REPLICATION
```

The resulting device evidence status is:

```text
REPLICATED_DEVICE_RELEVANT_QUANTUM_WITNESS
```

The physical status remains:

```text
PHYSICAL_DEVICE_NOT_VALIDATED
```

## Required source evidence

The export gate requires:

- at least two passing hardware runs;
- at least two distinct IBM backends;
- unique IBM job identifiers;
- unique raw-results hashes;
- all six multi-ledger benchmark gates passing;
- cross-run stability passing;
- valid run and replication manifests;
- all selected evidence files committed and unchanged in Git.

The exporter intentionally refuses untracked or modified evidence. This binds the transfer to an exact source commit rather than to an informal local folder state.

## Exported structure

```text
device_evidence_exports/
  multi_ledger_operator_memory/
    <UTC_TIMESTAMP>/
      runs/
        <RUN_TIMESTAMP>/
          results.json
          certificate.json
          summary.md
          manifest.json
      replication/
        <REPLICATION_TIMESTAMP>/
          replication_certificate.json
          replication_summary.md
          replication_manifest.json
      DEVICE_RELEVANT_QUANTUM_WITNESS.md
      transfer_certificate.json
      transfer_manifest.json
```

Only files declared by the original run and replication manifests are copied. The transfer manifest hashes every exported payload file.

## Optional device copy

When `--device-repo` is provided, the exporter copies the completed bundle to:

```text
quantum_hardware_evidence/<YYYY-MM-DD>/multi_ledger_cross_backend_<UTC_TIMESTAMP>/
```

The destination is written through a temporary directory, verified against `transfer_manifest.json`, and then moved into its final name. A separate `device_copy_receipt.json` records the verified copy.

## Commands

Self-test:

```bash
python export_multi_ledger_device_evidence.py --self-test
```

Export only:

```bash
python export_multi_ledger_device_evidence.py
```

Export and copy to the local device repository:

```bash
python export_multi_ledger_device_evidence.py \
  --device-repo "C:\Users\abc\Desktop\New Folder (2)\New folder\PROVISNAL RELATED\Devices"
```

## Device-side verification

After copying, run the device repository verifier:

```bash
python tools/verify_multi_ledger_quantum_evidence_import.py \
  --bundle "<COPIED_DEVICE_BUNDLE_PATH>"
```

The verifier writes device-local registration files only after all source hashes, run identities, controls, metric bounds, and claim boundaries pass.

## Supported interpretation

The replicated evidence supports these architecture concepts:

- decomposable hidden memory;
- selective reset of individual memory channels;
- causal memory-to-output projection;
- distinct reset signatures;
- stable multi-ledger reconstruction across independent IBM backends;
- hidden RK/KR operator-order information with nearly matched visible outputs.

## Scientific boundary

This transfer does not establish:

- a fabricated transistor;
- a breadboard or Arduino device;
- a phase-seam material;
- thermodynamic entropy production;
- quantum computational advantage;
- a new physical law.

The transferred evidence is a replicated quantum representation witness for the device architecture, not physical device validation.
