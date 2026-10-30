> Integration update: the photonic route and calculator now share the canonical
> flat arithmetic. These checks compare independent circuit/readout constructions,
> not independent arithmetic engines. The committed cluster record from 28e8650
> is retained as historical evidence; current regression tests exercise the
> migrated route. `nrqc certify` also supports the [four-number ledger command](README.md#ledger-certification).

# Ledger certification through the calculator (`nrqc certify`)

The phase-seam programme proves its cluster-state claims with a small private
engine over Q(zeta_64) in `phase_seam_foundation/cluster_compile.py`, because
the calculator had no mid-circuit measurement with pi/32 phases. The audit
note of phase seam v0.29 recorded that gap. `nrqc certify cluster` closes it:
the same claim is re-derived on the calculator's flat `cyclotomic_pow2`
backend through a static-circuit construction separate from the measurement
pattern engine. In this integration both use the same flat arithmetic kernel.

## Claim certified

Phase seam v0.29, the trained four-qubit parity classifier as a measurement
pattern on a 13-node tree cluster: on every corrected outcome path of the nine
flow-measured nodes, the readout probability P(readout = 1) equals the exact
circuit probability of `classifier_circuit`, and every path has probability
exactly 2^-9. Cases: the generic angles of `cluster_noise.GENERIC`,
features (5, 11) and parameters (3, 7, 13, 21, 29), and the pinned XOR
checkpoint (32, 0, 0, 32, 0) on its four inputs.

## Static reduction

The one-way-model byproduct identity: applying X^x Z^z to a node and then
measuring it in the X-Y plane at angle a with outcome s has the same
probability as measuring the uncorrected node at angle (-1)^x a with outcome
s XOR z. Proof: with |s_a> = (|0> + (-1)^s e^{ia}|1>)/sqrt(2),
Z|s_a> = |(s+1)_a> and X|s_a> = (-1)^s e^{ia} |s_{-a}>, so
<s_a| X^x Z^z |psi> has the modulus of <(s+z)_{(-1)^x a} | psi>.
`measurement_identity()` checks this through the calculator itself on five
exact one-qubit states, nine angles, all four byproducts and both outcomes
(400 exact equalities), so the reduction is not taken from the derivation
alone.

In the classifier pattern the flow is injective, so the X parity of a node is
the outcome of its unique predecessor, and the Z parity of a node is a fixed
XOR of earlier outcomes. The 512 corrected paths of one case therefore fall
into 64 static circuits, one per sign assignment of the six measured nodes
that have a predecessor (5, 6, 9, 10, 11, 12). Each circuit is the cluster
(H on 13 wires, 12 CZ edges) followed by one basis rotation per measured
node, `diag(1, zeta_64^-a') H`, with a' the sign-adapted angle, realised
through the calculator's own gate names (`p64 p32 p16 t s z` bits). One
distribution query over the ten measured wires (1024 outcomes) then gives,
for the eight paths of that assignment, the raw-outcome probabilities from
which P(path) and P(path, readout = 1) are read exactly.

## Values

Calculator values are elements of Q(zeta_64) in the flat power basis
(values computed in a smaller order are lifted by zeta_M = zeta_64^(64/M)).
Historical pattern values can be embedded from the nested tower by
Cyclotomic64 = lo + hi u, Cyclotomic32 = lo + hi w, Cyclotomic = lo + hi z,
with u = zeta_64, w = zeta_64^2, z = zeta_64^4, and the EMK field
Q(sqrt(2), i) constructed directly in the flat field. Equality is equality of
canonical stored forms; no decimal comparison is made.

For the generic case the circuit probability is

    (32 + (u + u^-1) + (u^7 + u^-7) + 8 (u^8 + u^-8) - (u^9 + u^-9)
         - 2 (u^11 + u^-11) - 8 (u^14 + u^-14) + (u^15 + u^-15)) / 64
    = 0.6370361636225...,   u = zeta_64,

and every one of the 512 corrected paths returns exactly this element. The
negative control reads the same 512 paths from the cluster measured at the
nominal angles with the byproducts ignored; there the conditional readouts
take several distinct values and most differ from the circuit probability, so
the corrections are doing work. (Comparing only the all-zero and all-one
paths is not a valid control at Clifford angles, where those two can agree;
the XOR cases show this.)

## Grades

| Grade | Meaning |
| --- | --- |
| `CERTIFIED` | identity holds, all 64 assignments of every case checked, every path weight 2^-9, every conditional readout equals the circuit probability, the pattern engine agrees, the uncorrected control differs on some paths |
| `MISMATCH` | an exact value disagrees between the two engines, the identity fails, or the control finds no path that the corrections change |
| `INCOMPLETE` | the identity check was skipped or fewer than 64 assignments of a case were run, with no disagreement found |

`TRAINED_ON_CHIP`, `QUANTUM_ADVANTAGE` and `ROOM_TEMPERATURE_CLASSIFIER` are
never granted. The certificate concerns an ideal lossless cluster; loss,
multi-pair emission and detector noise are outside it, and it records the
agreement of two exact engines on one mathematical object, not an observation.

## Run

```bash
nrqc certify cluster --workers 4 --out native_relational_qc/certify_records/cluster_certificate.json
nrqc certify cluster --cases generic --assignments 2      # a short partial run, graded INCOMPLETE
```

One assignment (13 qubits, 8192 amplitudes, 1024-outcome distribution) takes
about 27 s on one core in the flat engine; a full certificate is 320
assignments. The committed record is
[certify_records/cluster_certificate.json](certify_records/cluster_certificate.json);
`tests/test_native_certify.py` re-runs the identity, one assignment and the
control, and checks the committed record's grade and completeness.

## What this does and does not add

It adds a separate circuit/readout derivation of the v0.29 witness inside
the calculator's audited engine, and a reusable reduction (adaptive pattern to
static circuits with a distribution query) for later cluster claims. It does
not model loss or source noise (those are v0.33 to v0.36), does not touch the
bosonic fusion engine, and does not change any phase-seam module.
