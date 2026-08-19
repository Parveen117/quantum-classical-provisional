# coherence_lab — recognition-adaptive dynamical decoupling (RNKE-Q control-loop demo)

Measures effective coherence under DD on IBM hardware and tests whether an
RNKE-selected per-qubit schedule beats the best fixed schedule. Conforms to
`../RNKE_Q_CERTIFICATE_SPEC.md` (class: hardware_observation once run).

Arms per qubit: ramsey (T2*), hahn (T2), cpmg_{2,4,8,16}, xy4_{1,2,4}, **adaptive**
(select_schedule from calibration: δ_q = log 2T1/T2, readout error, optional
syndrome confidence), **random_ctrl** (renaming control). Delays 0–320 µs.
Predeclared fit: 0.5 + A·exp(−(τ/T)^β), bootstrap CI. Headline only if adaptive
beats best fixed with CI separation on ≥60 % of qubits; otherwise
`NO_ADAPTIVE_EFFECT_DD_EXTENSION_ONLY` (DD extension over Hahn is a standard
effect and is reported as such, never as a finding).

```bash
python adaptive_dd.py --self-test      # no credentials
python -m unittest -v test_adaptive_dd
```

## Hardware step (GPT)
1. Pin calibration snapshot for the chosen qubits (same schema as
   `hardware_evidence/<job>_calibration_snapshot.json`: T1_us, T2_us, readout_error).
2. `plan(cal)` → build circuits with `build_circuits(q, arms)` for each qubit,
   transpile with `scheduling_method="alap"`, submit (2000 shots/circuit) on ibm_marrakesh.
3. Write counts as `hardware_evidence/<job>_dd_counts.json`:
   `{qubit: {arm_label: {tau_us: {"0": n0, "1": n1}}}}` + job ids; commit.
4. `analyse(plan, counts)` → certificate; pin `EXPECTED_DD_*.sha256`.

Claim boundary: effective coherence under DD on measured qubits/epoch; not bare
device T2, not fault tolerance, not a vendor benchmark.
