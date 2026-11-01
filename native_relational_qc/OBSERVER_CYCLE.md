# Repeated source channels: return, observation and retained history

Author: Monty. 1 November 2026.

`nrqc observer-cycle` applies RKF SP1's affine composition and reset test to
the calculator's **existing** rotation-and-preparation source channel. It
predicts an arbitrary admitted number of repeated blocks exactly, finds a
physical fixed state, and checks whether a repeated detector probability
really means the source returned. This is a local ideal-model calculation.

```bash
nrqc observer-cycle
nrqc observer-cycle --retention 1 --cycles 1000000
nrqc observer-cycle --retention 1 --steps-per-cycle 1 --cycles 1 --axis 4 --frame-step 8
nrqc observer-cycle --cycles 1000 --max-coeff-bits 128
```

The last command deliberately returns `resource_limit` and exit code 2, with
no partial state or passing conclusion. `--out report.json` saves the result.
Angles use steps of 11.25 degrees. The first command uses start 0, velocity 8,
drive offset 8, retention 3/4, four source steps per block and three blocks.
Inputs describe a known model; this command does not infer hidden parameters
from measured bits. Use `observer-state` for its separate record controller.

## Source-derived H and b

The prior implementation is pinned at
[`observer_state.py`, 9093c2f](https://github.com/Parveen117/quantum-classical-provisional/blob/9093c2fad928050e834df9021e3955c4ec9c9420/native_relational_qc/observer_state.py).
Its `source_mixtures` enumerates convex equatorial preparations. The new
`source_affine` uses the same validated rotation, fixed drive and retention:

\[
z'=Az+c,\qquad A=\lambda e^{i\omega},\quad
c=(1-\lambda)e^{i\phi_d},\qquad \phi_d=\phi_0+\mathrm{offset}.
\]

The drive stays fixed in lab coordinates across every repetition. It is not
reinitialized from the current phase at a block boundary. For a k-step block,

\[
H=A^k,\qquad b=\sum_{j=0}^{k-1}A^j c,\qquad
z_n=H^n z_0+\sum_{j=0}^{n-1}H^j b.
\]

Composition is `(H2,b2) after (H1,b1) = (H2 H1,b2+H2 b1)`.
The implementation uses binary composition, without dividing by `1-H` to
propagate; identity, complete replacement and zero repetitions are admitted.
This reduces the number of affine compositions to O(log k + log n). Rational
coefficient lengths can still grow linearly with the exponent, so this is
not an O(log n) bit-runtime claim or a quantum speed advantage.

The coefficient field is the calculator's exact Q(zeta_64). For the real
two-coordinate observer argument, use its real subfield K+ and M=(K+)^2,
with multiplication by H represented by
`[[Re H,-Im H],[Im H,Re H]]`. This is a declared finite cut-field quantum
adapter; it does not derive Hilbert space from RKF's full lambda carrier or
replace SP1's native zero-specialization construction. Here lambda is the
source retention parameter, distinct from RKF's operator-family parameter.

A protocol block can repeat even if its state does not return. The output
therefore distinguishes the rotation schedule closing, the channel being
identity, the chosen initial state returning, and one analyzer probability
returning. Only a verified source return supplies that part of SP1's
closed-source premise; no arbitrary block is silently called a closed state.

## Why this source has zero reset obstruction

For `H != 1`, the witness is `z*=b/(1-H)`. For `H=1`, admissibility forces
retention 1 and b=0, so all states in this equatorial-plane domain are fixed;
the report chooses z*=0 as one witness. Thus SP1's class `[b]` in
`M/im(I-H)` is zero for this channel family, including when raw b is nonzero.

This fixed point is physical. If retention <1, the infinite convex series
`sum A^j c` has modulus at most
`(1-lambda) sum lambda^j = 1`. It is the same fixed point for the repeated
block. If retention=1, z=0 is fixed by every rotation. The density matrix
`rho=[[1,conj(z)],[z,1]]/2` is positive whenever |z|<=1. Code also checks the
computed fixed-point equation and squared contrast exactly. Existence of a
fixed point does **not** say that the user's chosen initial state returns.

The quantum channel is
`rho' = lambda U rho U† + (1-lambda) rho_drive`.
It has Kraus operators sqrt(lambda) U and
sqrt(1-lambda) |psi_drive><j|, j=0,1; their adjoint products sum to I.
See [the existing source derivation](OBSERVER_STATE.md) and
[IBM's Kraus representation](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.quantum_info.Kraus).
There is no unbounded translation of an unknown qubit amplitude here. A
nonzero SP1 drift counter is therefore not extracted from this bounded source.

For the default quarter-turn source, one four-step block gives

\[
H=81/256,\quad b=(-21+28i)/256,\quad
z_1=(15+7i)/64,\quad z_*=(-3+4i)/25.
\]

Rotation closes, yet the initially pure z0=1 does not return. Repeated
blocks approach the fixed state: the deviation is `H^n (z0-z*)`.

## Detector return, future access and moving frames

A fresh equatorial analyzer at a reads `P(0)=(1+Re(exp(-ia)z))/2`.
One analyzer can miss a state change. The same analyzer and an orthogonal
one, at a+pi/2, determine both coherence coordinates in this admitted domain.
Their **probabilities**, not two individual shot outcomes, distinguish states.
No tomography of an arbitrary three-coordinate qubit state is claimed.

For a difference d between the final and initial states, identical future
blocks give differences `H^j d`: affine offsets cancel. The two rows E and
EH have rank two iff Im H is nonzero. If H is real their span has rank one.
Consequently a differing state visible to this repeated analyzer is seen at
horizon 0 or 1; a null result means this same block/analyzer never separates
the pair. An orthogonal analyzer can still do so. This is SP1's application
of MR-04's future-row closure in a two-coordinate carrier.

For z0=1, one pure quarter-turn gives z1=i. An analyzer at pi/4 has identical
probabilities on the two states; its probability differs after one further
common quarter-turn. The orthogonal analyzer already separates them now.
The test retains this exact counterexample to "same reading means same state".

With frame advance alpha per block, q_n=exp(-in alpha)z_n. Its correct update is

\[
q_{n+1}=e^{-i\alpha}Hq_n+e^{-i(n+1)\alpha}b.
\]

The displacement must move too. A co-rotating frame can make the pure rotating
source look stationary. The report retains the final calibration and checks
laboratory reconstruction and the jointly transported analyzer probability.
No physical force is inferred from a coordinate change.

## What history means here

The reported cycle count is the **declared software protocol exponent**.
It is not inferred from the qubit or acquired from hardware. With retention 1
and a four-quarter-turn block, one million modeled blocks return the source,
while this explicit count differs from its initial zero. The ordinary
retained-register extension `(z,m)->(Hz+b,m+1)` has a nonzero count obstruction
over Q. It is a declared classical memory resource, not a new quantum clock.
The command stores a count, not every past outcome or full word history, and
assigns no physical duration. Finite counters and hardware timing need their
own storage, overflow and clock model.

Limits: 1..32 steps per block, 0..1,000,000 repetitions, retention an exact
rational in [0,1] with denominator <=16, and 128..8192 coefficient bits
(default 4096). Every stored affine coefficient and derived output is checked;
intermediate arithmetic on bounded operands and exact field inversion still
use ordinary working storage. The tool never falls back to floating output
as evidence of an exact return. Decimal renderings have certified enclosures.

## Attribution and verification

The philosophical prompt is credited to Spanda, Śiva's dance and
Pratyabhijñā in
[RKF SP1 sources](https://github.com/Parveen117/Recognition-Kernel-Framework/blob/main/research/spanda_recognition/SOURCES.md)
and its [Sanskrit passage register](https://github.com/Parveen117/Recognition-Kernel-Framework/blob/main/research/spanda_recognition/SANSKRIT_PASSAGES.md).
These texts motivate questions; they do not assert the channel or its proofs.
The mathematical contract is pinned to
[SP1 THEOREM.md at 7c49d86](https://github.com/Parveen117/Recognition-Kernel-Framework/blob/7c49d86d7552802c0f682245b847c5d977ea4903/research/spanda_recognition/THEOREM.md).
Its source register credits standard affine actions, cocycles and
observability. No historical anticipation of quantum mechanics, religious
validation of a model, or worldwide-first mathematical claim is made.

`tests/test_observer_cycle.py` compares exact block powers with the preexisting
convex preparation path and calculator gate probabilities; checks identity,
replacement, fractional retention, a nonzero b with zero obstruction, hidden
readings, future access, moving-frame covariance and resource failure; and
optionally compares an independently built Qiskit Kraus evolution and fixed
point. The existing observer-state tests protect its source/controller behavior.
CI runs the installed command and the suite on Python 3.11, Python 3.12, and
Python 3.12 with optional Qiskit/benchmark dependencies.
