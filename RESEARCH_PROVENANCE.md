# Research provenance and citation

Canonical repository: **[Parveen117/quantum-classical-provisional](https://github.com/Parveen117/quantum-classical-provisional)**. Maintainer: **@Parveen117**.
For author and contributor credit, retain the repository's citation metadata and the credits in the specific work being cited.

## Dated content record

Recorded on **2026-10-26 (UTC)**, before this provenance update:

- Default branch: `master`.
- Exact baseline commit: [`284302e1a65b6dfcc8b63531833394976bd4f331`](https://github.com/Parveen117/quantum-classical-provisional/commit/284302e1a65b6dfcc8b63531833394976bd4f331).
- Git tree: `ba58fefded547a6b1e612869213e02236766e447`.
- Inventory: **136 tracked entries**, including SHA-256 hashes of every Git blob's bytes.
- [Machine-readable snapshot](provenance/2026-10-26/baseline.json) · [Snapshot checksum](provenance/2026-10-26/baseline.sha256).

This is a content snapshot taken today, not a backdated first-disclosure claim.
Git object IDs and SHA-256 file digests are recorded separately. Gitlinks, if present, identify submodule commits; their external contents are not included.

## Archived version

Verified record metadata: [10.5281/zenodo.23454293](https://zenodo.org/records/23454293), version `v1.0`, record created `2026-10-18T14:58:04.751920+00:00`.

Recorded release commit: `2a9eaf3e54e56236f1a92caf0a799f2e953ec125`. Archive byte verification: **verified** (details and archive SHA-256 in the snapshot).

The record DOI identifies this version. The concept DOI, `10.5281/zenodo.23454292`, groups versions and should not replace an exact-version citation.

The snapshot records the published GitHub releases observed during this audit. Existing root citation metadata can describe an older release: cite the exact artifact, tag, commit and version DOI used.
The live branch may contain work added after the archive. A prior DOI does not timestamp those additions.

## Verify without running research code

From a clone that contains the baseline commit:

```bash
python provenance/verify_snapshot.py --repo . --snapshot provenance/2026-10-26/baseline.json
```

If a shallow clone lacks the baseline, fetch that exact commit first. The verifier reads Git objects, checks the manifest checksum, tree identity, file inventory and each blob's SHA-256. It does not execute experiments or validate scientific claims.
The checksum file is an integrity check; independent anchoring requires a dated external archive or timestamp receipt.

## New result → new evidence record

1. State the exact result, assumptions, limitations, reproduction command and relevant file paths.
2. Record the commit and content hashes, preserve raw observations and record any independent review separately.
3. Check citation metadata, rights notices and release contents. Where both files exist, Zenodo uses `.zenodo.json` rather than `CITATION.cff` for archival metadata.
4. Create a new release at that commit after the repository's existing release gates pass. Do not move a published tag to new content.
5. Verify the Zenodo record, exact version DOI, creation time and archive bytes; record the receipt in a later additive commit.

See [governance](GOVERNANCE.md) for owner-controlled changes and the [public research index](https://github.com/Parveen117/Publications/blob/main/PUBLIC_RESEARCH_INDEX.md) for the cross-repository record.
