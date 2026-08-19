# Legacy demo ledger — schema drift note (2026-08-19)

`demo-bridge-ledger.jsonl` was produced by an earlier revision of
`quantum_native_bridge_pro`. The record payload has since changed, so the stored
`record_hash` values no longer reproduce under the current
`BridgeRecord.hash_payload()`, and `cli verify` fails on that file at sequence 1.

This is schema drift, not tampering, and it is deliberately **not** repaired by
rewriting the file: the ledger is authentic evidence of what the code emitted at
the time, and silently regenerating hashes would destroy exactly the property the
ledger exists to demonstrate.

Handling:

- the legacy file is kept unchanged;
- `tests/test_legacy_ledger_drift.py` asserts that it does *not* verify, so the
  drift is recorded rather than forgotten;
- `tools/regenerate_demo_ledger.py` produces `demo-bridge-ledger-current.jsonl`
  under the present schema, and that file is what CI verifies.

If a future change again alters the record payload, the same pattern applies:
keep the old evidence, regenerate a current demo, and leave a note here.
