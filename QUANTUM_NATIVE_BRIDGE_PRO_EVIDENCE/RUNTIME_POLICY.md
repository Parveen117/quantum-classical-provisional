# Quantum Native Bridge Pro Runtime Policy

This note maps bridge classifications into simple runtime recommendations.

## Classes

`RECOGNITION`: certify and continue.

`BOUNDED_RESIDUE`: certify with monitoring and repeat the run when the workflow is sensitive.

`ACTIONABLE_RESIDUE`: pause use of the result until the job is repeated, the context is checked, or the backend is recalibrated.

## Signals

The bridge uses measurement gap, phase coherence, phase penalty, residue score, backend metadata, record hash, chain hash, and certificate hash.

## Actions

1. Repeat measurement shots.
2. Compare with an expected distribution.
3. Refresh phase or session binding.
4. Recalibrate the backend context.
5. Try another simulator or backend.
6. Append the record to the ledger.
7. Export a certificate.
8. Ask for controller review when residue is high.

## Drafting value

This turns classification into a technical action for a quantum-classical workflow. That matters because the bridge is a runtime control system, not only a mathematical score.
