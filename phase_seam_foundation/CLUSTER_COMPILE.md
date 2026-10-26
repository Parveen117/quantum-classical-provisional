# The trained classifier as a measurement pattern on a fusion-built cluster — v0.29

**Author: Monty.** The self-learning branch (`codex/native-self-learning-v1-20261024`
at `cfa04da`, read-only here) trains a four-qubit circuit with five RY angles
and three CNOTs on the PC through the exact calculator; its angles are integer
multiples of π/32, the same ζ₆₄ grid every phase_seam packet uses. The question
was whether that architecture can *be* the hardware design. This note answers
exactly: the trainable part maps natively (every angle is a heater trim), the
three CNOTs do not (dual-rail linear optics has no deterministic CNOT; three
post-selected KLM gates at 1/9 give 1/729 per shot and no herald), and the one
honest form is a fixed photonic resource read by programmable single-photon
measurements. That form is derived here with every step exact.

[Code](cluster_compile.py) · [Tests](../tests/test_phase_seam_cluster_compile.py) ·
[Audit](../benchmarks/cluster_compile_audit.py) ·
[Reproducible results](cluster/qualification.json) · [Test log](cluster/test_results.txt).

## 1. Claims, exactly separated

**Exact (this packet).** Lemmas G1–G3 as operator identities in Q(ζ₆₄) at all 64
native angles; the circuit's J/CZ rewrite; a 13-photon tree cluster with 12
edges and 9 J-measurements plus one readout; an end-to-end witness that the
pattern's readout probability equals the circuit's, with every measurement
branch checked and two negative controls; the fusion resource law from v0.27;
a heater codebook; a fail-closed grader.

**Never claimed.** Learning on the chip, any speed or quantum advantage, a
room-temperature classifier. The pinned source itself reports a one-coefficient
classical rule at 100 % on its held-out task and calls XOR a sanity check. The
cluster form is standard one-way computation; what is native is the exact
trainer, the shared π/32 grid (checkpoint → heater codebook with no rounding)
and the fusion build chain of v0.22–v0.27.

**Open.** Building and storing the 13-photon tree optically (Theorem B1 sets
m ≳ 0.99 per 0.1 µs attempt); the hardware form of the corrections (angle
adaptation instead of active Pauli gates); loss, multi-pair and dark counts on
the ten measured nodes (LEDGER_VIOLATIONS.md); every measured number.

## 2. Lemmas

Write Rz(k) = diag(1, ζ^k), J(k) = H·Rz(k), and B(a) for the basis
{Rz(a)|+⟩, Rz(a)|−⟩}.

**G1 (gadget).** With |ψ⟩ on wire 1 and |+⟩ on wire 2, after CZ, measuring
wire 1 in B(a) with outcome s leaves X^s J(−a)|ψ⟩/√2 on wire 2. Hence J(k) is
the measurement at angle a = −k, and both outcomes have weight 1/2. Checked as
a 2×2 identity for all 64 k and both s.

**G2 (propagation).** CZ (X⊗I) CZ = X⊗Z. An X byproduct on a node whose edges
are already applied is X on that node and Z on each of its other neighbours;
Z byproducts commute. Checked as a 4×4 identity.

**G3 (RY).** The pinned RY(k) = S·H·Rz(k)·H·S† satisfies RY(k)|0⟩ = S·J(k)|+⟩
and RY(a)RY(b) = RY(a+b). Checked for all 64 k.

## 3. The rewrite and the pattern

Wire q carries a_q = f_q + p_q (features f₀, f₁ enter wires 0, 1; the fifth
parameter p₄ is the readout). CX(c,t) = H_t·CZ·H_t. The S of G3 is dropped on
wires 0 and 1 (it commutes with CZ and those wires are traced), absorbed as
J(16) = H·S on wires 2 and 3, and the final S† on wire 3 is dropped before the
Z readout. The circuit becomes, on |+⟩⁴:

| wire | J sequence | cross edges |
| --- | --- | --- |
| 0 | J(a₀) | CZ to wire 2 |
| 1 | J(a₁) | CZ to wire 2 |
| 2 | J(a₂), J(16), [CZ 0, CZ 1], J(0) | CZ to wire 3 |
| 3 | J(a₃), J(16), [CZ 2], J(0), J(48), then Z readout after J(p₄) | |

Each J consumes one measured node (G1); the readout "J(p₄) then Z" is the last
node measured at angle −p₄. Nodes 0–1 (wire 0), 2–3 (wire 1), 4–7 (wire 2),
8–12 (wire 3); edges along each wire plus (1,6), (3,6), (7,10). Thirteen
photons, twelve edges, a tree (five leaves: 0, 2, 4, 8, 12; hub 6 of degree
four). Nodes 1, 3, 7 are wire outputs that are never read. Measurement order
0, 2, 4, 5, 8, 9, 6, 10, 11, then readout 12; after node i with outcome 1,
apply X on its flow successor f(i) and Z on the other neighbours of f(i) (G2).

The engine allocates a node as |+⟩ with its edges to live nodes at the moment
it is touched; because every CZ commutes with every other CZ and with Z, and
every edge of a node is applied before any X or measurement on it, this is a
legal reordering of the graph-first state. At most eight nodes are live.

## 4. Exact witness

For declared (f, p), the circuit probability P(wire 3 = 1) comes from the
repo's Q(ζ₆₄) phase backend; the pattern probability from the engine above.
With corrections on, both outcome branches of every one of the nine J
measurements are compared *exactly after correction* and must coincide; one is
kept and renormalised by √2. Every branch has weight exactly 1/2.

| input | circuit | pattern | equal | controls |
| --- | --- | --- | --- | --- |
| XOR checkpoint (32,0,0,32,0), all four inputs | 0 or 1 | 0 or 1 | exact, labels match | X-only rule diverges at node 0 |
| (5,17), (3,41,22,9,50) | 0.141134545… | 0.141134545… | exact | uncorrected paths differ; X-only diverges |
| four LCG-drawn angle sets (audit) | 0.168…, 0.323…, 0.692…, 0.676… | same | exact | same |

The controls: following the all-zero and all-one outcome paths with no
corrections gives different readouts at generic angles (at Clifford angles the
uncorrected readout can coincide, which is why the XOR rows report the X-only
control); using X without the G2 Z-propagation breaks branch equality at the
first measurement.

## 5. What the cluster costs (v0.27 law)

Root the tree at hub 6. Leaves are star leaves; each of the seven edges
between internal nodes is one type-I fusion at 1/2, a child star's centre into
a spare leaf of its parent. Bell-pair counts are conditional on a successful
build, as in TREE_BUILD.md, and star growth uses the v0.22 walk.

| spare leaves per parent | P(all attachments succeed) | expected Bell pairs (conditional) |
| --- | --- | --- |
| 0 | 1/128 | 27.6 |
| 4 | 288021/524288 ≈ 0.549 | ≈ 202 |

A one-shot build at 1/128 is a cliff of the kind Theorem B1 describes; the
cluster must be built offline and multiplexed, which Theorem B1 prices at
m ≳ 0.99 per 0.1 µs attempt. Storage survival of this particular tree is not
computed here.

## 6. Heater codebook

A measurement in B(a) on a dual-rail site is the Theorem D1 four-heater unit
with the exchange at 16 steps (π/2), the output trim at the nominal 48, and the
input trim `before = (32 − a) mod 64`, found by exact search so that Rz(a)|+⟩
exits on rail 0 and Rz(a)|−⟩ on rail 1. Ten measured nodes and three discarded
ones give 26 detectors. Training changes exactly five trims (nodes 0, 2, 4, 8
and the readout 12); the cluster, the seven fusions and the five fixed angles
(16, 16, 0, 0, 48) do not change. Under claim B the trims are phase variables
and transfer after calibration; nothing here is a temperature statement.

## 7. Grader

`compile_grade` is fail-closed: COMPILED → CLUSTER_RECORDED (LAB_RECORDED
13-photon cluster with at least 12 stabiliser witnesses) → PATTERN_RECORDED
(LAB_RECORDED readout frequencies with feedforward on, within a declared
tolerance of the exact probability on every declared input, using rational
outward bounds of the Q(ζ₆₄) value). A record asserting TRAINED_ON_CHIP,
QUANTUM_ADVANTAGE or ROOM_TEMPERATURE_CLASSIFIER is rejected outright.

## 8. Reproduce

```bash
python benchmarks/cluster_compile_audit.py
```

writes `cluster/qualification.json` and `cluster/test_results.txt`.
