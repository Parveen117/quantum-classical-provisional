# Three-round Shor hardware acquisition runbook

This extends the existing four-case `ibm_marrakesh` evidence without adding a
new scientific pillar. Each shot executes three complete syndrome-extraction
rounds. All eight ancillas are measured after every round and reset before the
next round. No conditional recovery is performed on hardware.

## Predeclared contract

- backend: `ibm_marrakesh`
- cases: `no_error`, `x_q0`, `z_q0`, `y_q4`
- shots: 4096 per case
- syndrome rounds: 3 per shot
- mid-circuit policy: measure eight ancillas; reset after rounds 0 and 1
- hardware recovery: none

The evidence gate requires the expected syndrome to remain the unique mode in
each individual round and in the exact-report majority ledger for all cases.
No minimum exact-rate threshold is introduced after observing the data.

## 1. Test and inspect the frozen specification

```powershell
Set-Location .\qec_error_control_lab
& ".\.venv-qec\Scripts\python.exe" -m unittest -v test_ibm_shor_3round_hardware.py
& ".\.venv-qec\Scripts\python.exe" .\ibm_shor_3round_hardware.py spec
```

## 2. Submit with the already saved IBM account

```powershell
& ".\.venv-qec\Scripts\python.exe" .\ibm_shor_3round_hardware.py submit
```

The command prints the new job ID and writes
`hardware_evidence/ibm_shor_3round_submission_<job_id>.json`. It never accepts
or prints an API token.

## 3. Collect the completed job

```powershell
& ".\.venv-qec\Scripts\python.exe" .\ibm_shor_3round_hardware.py collect <job_id>
```

If the job is not `DONE`, the command updates the receipt status and returns
code 2. When complete, it writes
`hardware_evidence/<job_id>_3round_hardware_certificate.json`.

## 4. Capture the historical calibration for the earlier single-round job

```powershell
& ".\.venv-qec\Scripts\python.exe" .\capture_ibm_calibration_snapshot.py
```

The script first recovers the physical ancilla mapping from the submitted ISA
circuit in `job.inputs`, then requests backend properties closest to but older
than the job creation time. It fails closed if the account channel cannot
retrieve historical properties; current calibration is never silently
substituted for the job epoch.

Expected output path:

`hardware_evidence/da2raps3jnrc73ae9n80_calibration_snapshot.json`

Claim boundary: repeated extraction and calibration metadata from one backend
epoch; no hardware recovery, threshold, or fault-tolerance claim.
