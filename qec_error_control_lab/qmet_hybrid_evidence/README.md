# Qmet hybrid evidence bundle v1

This folder binds four independently scoped evidence components into a single
proof-carrying index for an IIT Bombay Qmet bounded POC review:

1. IBM Shor hardware-syndrome evidence;
2. the exact-statevector RNKE Shor control gate;
3. finite Recognition-Framework theorem binding on the IBM shot counts; and
4. the Q-Seam NV/ODMR raw-spectrum digital-twin campaign.

The bundle composes provenance, **not claim strength**. Hardware QEC evidence
cannot upgrade digital-twin sensor evidence into physical sensor validation.
Every component retains its evidence class and negative claim boundary.

## Run inside the repository checkout

```powershell
Set-Location .\qec_error_control_lab\qmet_hybrid_evidence
python -m unittest -v
python .\qmet_hybrid_bundle.py
```

The CLI replays the three local QEC anchors, binds the pinned remote Q-Seam
attestation, creates a four-receipt hash chain and writes:

`generated/qmet_hybrid_evidence_certificate.json`

Expected status: `PASS_BOUNDED_QMET_HYBRID_EVIDENCE_BUNDLE_V1` and
`READY_FOR_QMET_BOUNDED_POC_REVIEW`.

## What the status means

It means the four bounded components are present, hash-bound, internally
separated and ready to be reviewed together as a POC evidence package. It does
not mean fault tolerance, a QEC threshold, physical NV validation,
metrological traceability, K0 collapse or a result on the Riemann Hypothesis.

Physical promotion requires instrument-native ODMR data, signed instrument and
calibration identities, predeclared field/temperature controls and comparison
with a traceable reference magnetometer.
