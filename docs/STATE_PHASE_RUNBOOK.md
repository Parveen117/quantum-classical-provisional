# State, Dynamics, and Phase Certificate Runbook

Run after the unified evidence certificate has been generated.

```bash
python tools/build_state_phase_certificates.py --root .
python -m unittest tests.test_state_phase_certificates -v
```

Outputs:

- `generated_certificates/quantum_state_certificate.json`
- `generated_certificates/quantum_dynamics_certificate.json`
- `generated_certificates/quantum_phase_certificate.json`

Interpretation:

- `EVALUATED`: the required witness class was found.
- `PARTIAL`: some relevant evidence exists, but it does not uniquely close the sector.
- `UNEVALUATED`: the required witness class was not found.

For Bell-state evidence, computational-basis counts alone support distribution closure but not relative-phase closure. A phase certificate requires non-commuting-basis correlations, an explicit phase witness, tomography, or an equivalent registered test.

The builder never promotes a missing witness to zero residue. That omission would make the certificate prettier and the science worse.
