# Delta OGMT order recognition on the exact calculator

Author: Monty. Local run: 2026-10-31. Evidence class:
**DECLARED_IDEAL_CIRCUIT_MODEL**.

The calculator resolves ABAB from AABB in the declared circuit. The full double
triangle does **not** beat the single-memory or parallel-memory comparators at
this parameter setting. Rotating the readout improves its separation by about
4.76 times, but the equally scanned single-memory comparator still wins. This
is an actionable result about this encoding/readout, not a verdict on every
possible double-triangle implementation.

## What was mapped and what remains unassigned

The circuit maps the roles in the
[device experiment packet](https://github.com/Parveen117/EMK-Tensor-Cell-Devices/tree/4fa17c10c19aea5447fdea6c83e070826c1742a6)
to six data wires and a drain-readout wire. Source code:
[delta_ogmt.py](delta_ogmt.py). It uses the repository's existing
`nrqc-calculator-v1` JSON format and `cyclotomic_pow2` backend in Q(zeta_16).
No calculator engine or resource limit was changed.

| Wire | Role in this circuit |
| --- | --- |
| 0, 1, 2 | Outer channel, gate and memory-return roles |
| 3, 4, 5 | Inner electrical-memory, thermal-role and retention-role ledgers |
| 6 | Binary drain projection |
| 7 onward, when needed | Fresh environment wires for selective reset |

These are coherent state variables, not calibrated carrier density, volts,
kelvins or RC decay. The earlier IBM transistor script uses different,
arbitrary-angle operators; this audit does not silently round those operators
and claim an exact replay. It instantiates an explicitly declared dyadic circuit
on the same architectural roles. The IBM job-submission scripts were not run.

One phase step is 2*pi/16. Input A uses 1 step and B uses 3 steps. Each event
applies the gate-input rotation, core updates, active ledger updates and then
controlled phase couplings. The outer AB/BC/CA weights are 2/1/2 steps; inner
12/23/31 weights are 1/2/1; A1/B2/C3 bridges are 2/1/1. The code/model record
declares the local ledger phase/mixing updates. Their differences are not fitted
thermal or retention time constants. Initial state is H on wire 0, all others 0.
The commuting negative control additionally prepares the other data wires in
superposition so that its diagonal updates act nontrivially.

ABAB and AABB contain the same event multiset and the same first/last events.
Both receive one common hold update and one read event R (2 steps). The hold
has zero input drive phase but continues internal updates. A fixed interferometric
projection couples wires 0 and 2 to wire 6 with 4 and 2 phase steps. There is no
class-label wire or label-dependent readout. Model parameters were not searched
for a favorable topology result.

M0 is explicitly a boundary-only preparation after discarding history. M1 has
one active ledger, M2 three ledgers without inner cross-edges, M3 the full graph,
and E_CA removes the declared outer memory-return coupling. The coherent core
can itself retain history in M1/M2/M3; calling M1 a complete physical single-RC
device or claiming a thermodynamic resource match would be incorrect.

## Retained nominal results

The score below is `abs(P(drain=1 | ABAB) - P(drain=1 | AABB))`, shown in
**percentage points**. It is a probability separation, not classification
accuracy. The fixed readout is the primary comparison. Every mode then receives
the same 16-angle diagnostic budget with couplings held unchanged.

| Circuit | Fixed readout gap (pp) | Best tested readout angle | Gap at that angle (pp) |
| --- | ---: | ---: | ---: |
| M0 boundary-only | 0 | 0 degrees | 0 |
| M1 one ledger | 0.341245 | 67.5 degrees | 0.968506 |
| M2 parallel ledgers | 0.165110 | 67.5 degrees | 0.783905 |
| M3 full double triangle | 0.143338 | 67.5 degrees | 0.682622 |
| E_CA designated edge removed | 0.688639 | 157.5 degrees | 0.754217 |

For M3 at the fixed readout, P(1) is approximately 0.2010004142335 for ABAB
and 0.2024337901685 for AABB. Exact field coefficients and outward decimal
enclosures are retained, not replaced by these rounded displays.

At the selected M3 angle, the optimal equal-prior decision based on **one binary
readout** has success `(1 + gap)/2`, approximately **50.3413%**. This is weak
single-shot discrimination. Repeated preparations can estimate probabilities,
but their cost must be counted. The angle is chosen on these two known histories;
it is not held-out prediction accuracy or evidence of general pattern learning.
Likewise, no measured voltage, switching energy, temperature, drift tolerance,
physical accuracy or quantum speed advantage follows from this table.

The phase scan in [delta_ogmt_observer.py](delta_ogmt_observer.py) uses exact
calculator values of drain Y and Z. After Rx(theta),

`P(1; theta) = (1 - <Z>*cos(theta) - <Y>*sin(theta))/2`.

All 16 grid angles (0 through 337.5 degrees in 22.5-degree increments) are
retained. Each selected angle is also recalculated through explicit appended
gates for both histories. Thus the angle improvement is checked independently
of the moment-reconstruction formula.

## Reset and negative controls

Selective resets swap the relevant ledger into a fresh |0> environment and
marginalize that environment. This implements trace-and-prepare without
postselection. The independent numerical reference uses Qiskit's actual
density-matrix reset operation instead of the SWAP construction.

| Intervention on M3 before common hold/read | Fixed drain gap (pp) |
| --- | ---: |
| No reset | 0.143338 |
| Reset C1 ledger | 0.097117 |
| Reset C2 ledger | 0.143338 |
| Reset C3 ledger | 0.146421 |
| Reset all three ledgers | 0.100333 |

At this insertion point, resetting C2 leaves the two drain probabilities exactly
unchanged, although a memory-distribution diagnostic changes. This readout does
not demonstrate a useful C2 contribution. Resetting all three ledgers does not
erase history already transferred into the core or prevent later updates from
writing memory again. It is not a full-device reset.

The boundary-only, equal-input, commuting-update and disabled-projection controls
all have exactly zero drain separation. Equal-input and commuting controls also
have exactly equal core and ledger computational-basis distributions. With the
projection disabled, internal distribution differences remain while the drain
signal vanishes. These controls test circuit semantics, not physical causality.

## Execution and validation

- 24 primary requests completed in 10.332 seconds including local numerical
  cross-checks. Typical requests use 7 wires; reset cases use up to 10. Peak exact
  support across the primary campaign was 1,024 branches, with no truncation.
- The observer diagnostic ran 10 moment requests plus 10 explicit rotated
  requests in 6.273 seconds. These times are local run observations.
- 34 local Qiskit comparisons passed, including density-matrix reset checks.
  Maximum discrepancy against displayed exact midpoints was below 5.0e-13.
- All 10 direct rotated probabilities equal their reconstructed values exactly.
- The dedicated suite checks pulse matching, edge removal, genuine reset,
  negative controls, all 16 observer angles and rejection of incomplete results.
  Qiskit is optional; the calculator and core tests retain the NumPy-only path.

Arithmetic verification passed. The proposed full-topology advantage did not
pass at this setting. These are different outcomes and remain separate in the
records. No physical experiment was performed.

## Reproduce or inspect

Two plain calculator examples are included:
[ABAB](calculator_examples/delta_ogmt_ABAB.json) and
[AABB](calculator_examples/delta_ogmt_AABB.json).

```bash
nrqc calculate native_relational_qc/calculator_examples/delta_ogmt_ABAB.json
nrqc calculate native_relational_qc/calculator_examples/delta_ogmt_AABB.json

python -m native_relational_qc.delta_ogmt --out /tmp/ogmt-order-replay
python -m native_relational_qc.delta_ogmt_observer --out /tmp/ogmt-angle-replay
```

Output directories must be new, preserving previous observations. For independent
numerical checks, install the optional `.[qiskit]` extra and add
`--compare-qiskit`. Neither command connects to a quantum service.

The [retained archive](../benchmarks/records/delta_ogmt_order_20261031.zip)
contains 94 JSON files: the model/plan, all 44 input requests and their results,
full summaries and per-run hash manifests. The
[compact index](../benchmarks/records/delta_ogmt_order_20261031.summary.json)
records the archive SHA-256 and headline results. Unzip into a new directory;
every file under an `inputs/` directory can be passed to `nrqc calculate`.
The manifests bind exact saved bytes; runtime fields naturally change on rerun.

## Design consequence

Keep the physical experiment proposed, but do not promote this circuit as an
optimized recognition cell. Readout rotation is useful here; additional coupling
is not automatically useful. The next numerical design study needs a declared
family of histories, calibration/held-out splits, equal tuning budgets for the
simpler controls, and a physical mapping of the evolution operators. Those
measurements and comparisons are the bridge from this exact circuit exercise
to a hardware claim.
