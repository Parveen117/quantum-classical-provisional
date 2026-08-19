# RNKE-Q Certificate Specification v0.1

**Purpose.** A machine-readable, hash-chained verdict for any quantum job, QEC
round, or calibration epoch: *nothing becomes an accepted result merely because
the backend returned it.* Every certificate declares what was verified, against
which model, with which residue, and what it does NOT claim.

This spec generalises the certificates already emitted in this repository
(`rnke_qec_gate`, `rnke_theorem_binding_hw`, `qmet_hybrid_evidence`,
Multi-Ledger replication). New emitters MUST conform; existing ones are v0.1
instances.

## 1. Verdict grammar (typed, exhaustive, fail-closed)

| verdict | meaning | state advances? |
|---|---|---|
| `COMMITTED` | residue zero under the declared model | yes |
| `CORRECTED` | bounded residue; lawful correction applied **and re-audited to zero** | yes |
| `DEFERRED` | evidence incomplete / reports disagree; held, re-extraction requested | no |
| `CUT` | residue outside declared model, or fidelity not restored; rejected | no |

`ABSTAIN_*` is permitted only for *tests* (hypothesis runners), never for
state-advancing gates.

## 2. Required fields

```json
{
  "protocol": "<name>-v<major>",
  "emitter": {"module": "...", "git_commit": "<sha>"},
  "inputs": {
    "circuit_or_spec_sha256": "...",
    "backend": "ibm_marrakesh | simulator | <device>",
    "job_ids": ["..."],
    "calibration_epoch": "<iso8601 or 'none'>",
    "shots": 4096,
    "source_certificates": [{"path": "...", "sha256": "..."}]
  },
  "model": {"declared": "...", "error_model": "...", "thresholds": {...}},
  "residue": {"type": "...", "value": "...", "inertia_or_weight": "..."},
  "verdict": "COMMITTED|CORRECTED|DEFERRED|CUT",
  "controls": {"negative": [...], "renaming": [...]},
  "claim_boundary": "<one paragraph: what this does NOT establish>",
  "receipt": {"parent_receipt_hash": "<sha256|genesis>", "receipt_hash": "<sha256>"},
  "certificate_sha256": "<sha256 of canonical JSON without this field>"
}
```

Canonical JSON: sorted keys, separators `(",",":")`, ASCII. Exact arithmetic
(rationals as strings) wherever a verdict depends on a comparison.

## 3. Evidence classes (never silently upgraded)

`definition` < `derivation` < `computational_verification` < `hardware_observation`
< `replication` < `physical_validation`. A certificate carries exactly one class.
Composition (bundles) composes **provenance, not class**: a bundle's class is the
minimum of its members.

## 4. Mandatory controls

- **Negative control:** a planted failure the verdict must reject.
- **Renaming control (TAUT-1):** the same computation on random data of the same
  shape; if it reproduces the headline, the headline is an identity, not a finding,
  and MUST be labelled `IDENTITY_RESTATEMENT`.
- **Pin integrity:** every consumed certificate re-hashed at read time; mismatch ⇒ `CUT`.

## 5. Prohibited wording in any RNKE-Q certificate or summary

"quantum advantage", "fault tolerant", "threshold", "validated device",
"Qmet-validated", "proves RH/K₀", unless the evidence class is `physical_validation`
with an independent evaluator recorded.

## 6. Conformance

A conformant emitter ships: (a) `--self-test` requiring no credentials, (b) a
pinned `EXPECTED_*.sha256`, (c) tests including tamper detection and
determinism. CI runs (a)–(c).

## 7. Current instances (this repo)

| emitter | class | pin |
|---|---|---|
| `rnke_qec_gate` (Shor exact) | computational_verification | `EXPECTED_RNKE_GATE` |
| `rnke_theorem_binding_hw` (IBM shots) | hardware_observation | `EXPECTED_THEOREM_BINDING_HW` |
| `qmet_hybrid_evidence` | bundle (min class) | `EXPECTED_QMET_HYBRID_BUNDLE` |
| Multi-Ledger replication (public repo) | replication | release manifest |
| `coherence_lab` (planned) | hardware_observation | — |
