# Expected-Integrated Bridge Ledger Command

This command creates a fresh bridge ledger where the expected Bell model is integrated directly into the bridge append path.

```bash
python -m quantum_native_bridge_pro.cli append \
  --ledger trial-expected-integrated-ledger.jsonl \
  --root '{"circuit":"bell_state","qubits":2,"intent":"prepare_correlated_pair"}' \
  --template '{"expected_model":"bell_phi_plus","gates":["H q0","CX q0 q1"],"measurement_basis":"Z","tolerance":0.08}' \
  --phase '{"backend":"jupyter-trial","session":"expected-integrated-001","calibration_id":"cal-demo-001"}' \
  --observed '{"00":506,"01":11,"10":9,"11":498}' \
  --expected-model QUANTUM_NATIVE_BRIDGE_PRO_EVIDENCE/bell-expected-model.json \
  --phase-angles '[0.1,0.2,0.15]'
```

Verify:

```bash
python -m quantum_native_bridge_pro.cli verify --ledger trial-expected-integrated-ledger.jsonl
```

Expected result:

```json
{
  "recognized": 1,
  "actionable_residue": 0,
  "expected_model_counts": {
    "RECOGNITION": 1
  }
}
```

This resolves the earlier split where external expected-model evaluation recognized the Bell pattern while the bridge ledger still counted only the fallback hash-derived residue.
