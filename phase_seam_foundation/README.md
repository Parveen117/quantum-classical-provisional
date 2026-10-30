# Phase–seam foundation and photonic model

Author: Monty. The current integration uses the calculator's canonical flat
cyclotomic field for the photonic route. All results here are conditional model
results. Material parameters, optical loss, source quality, detector performance
and calibration require independent evidence.

Run `nrqc certify` from an installed calculator to re-derive the four arithmetic
targets below, including enclosures, source hashes and negative controls.

| Model result | Exact target / scope | Derivation |
| --- | --- | --- |
| Type-I fusion | success 1/2 across both herald branches | [Dual rail](DUAL_RAIL.md) |
| Coherent source loss | Bell weights (3/4, 1/12, 1/12, 1/12) in the selected sector | [Source and purification](SOURCE_DISTILLATION.md) |
| Ideal ZX purification | fidelity 841/932 for two supplied independent pairs per round | [Cascade](PURIFICATION_CASCADE.md) |
| XOR readout error bound | (5/2)w + 1−(1−w/4)^12−12(w/4)(1−w/4)^11; about 2.8w at x=1/40, η=243/4000 | [Classifier noise](CLUSTER_NOISE.md) |

The source-sector selection does not supply certified Bell pairs, and the rounded
2.8 coefficient does not bound the full expression for every w. No command here grants a measured
witness, on-chip learning, fabrication qualification or quantum advantage.

## Research contracts

- [Foundation](FOUNDATION.md), [joint algebra/readout](JOINT_READOUT.md), [encoding](ENCODING.md)
- [Register](REGISTER.md), [controller](CONTROLLER.md), [sector controls](SECTOR_CONTROL.md)
- [Bus gate](WEYL_BUS.md) and [Hamiltonian assumptions](BUS_HAMILTONIAN.md)
- [Layout](PHOTONIC_LAYOUT.md), [I/O](PHOTONIC_IO.md), [optical response](PHOTONIC_RESPONSE.md)
- [Constitutive response](CONSTITUTIVE_RESPONSE.md) and [observer](PHOTONIC_OBSERVER.md)
- [Loss budget](LOSS_BUDGET_810.md), [retained ledger](LOSS_LEDGER.md), [cluster faults](CLUSTER_FAULTS.md)
- [Earlier versioned notes and evidence links](HISTORY.md)

Historical artifacts and source manifests remain dated snapshots. The current
source hashes are emitted by `nrqc certify`; historical manifests are not silently
rewritten to claim a rerun.
