# Four phases and a seam: a checked tomographic bridge — v0.3

Author: Monty. Status: exact finite encoding, restricted transport
correspondence, and a proved obstruction for one native cut.

This revision connects the four-mode phase/seam data to the two-site operator
algebra. All four wrapped phases and the positive seam ratio are recoverable
from nine exact expectation values. Initial conditions and the operation tape
remain classical; together with the code they recover the full v0.1 cell.
Specific balanced transports and a paired mode swap have exact unitary
implementations. The general balanced cut fails a deterministic-channel test.

This is a **tomographic encoding**, not full operational equivalence between
the v0.1 classical cell and a two-qubit device. An injective map of states does
not automatically preserve every measurement or every allowed transformation.
The earlier v0.2 quantum readout postulates remain explicit assumptions.

## 1. The nine-reading map

Use the existing EMK definitions X=L=RK, Y=iR and Z=K, with sites A and B.
Choose the following signed observable pairs:

| Source phase | P reading | Q reading |
| --- | --- | --- |
| theta_0 | X_A | Y_A |
| theta_1 | X_B | Y_B |
| theta_2 | X_A Z_B | -Y_A Z_B |
| theta_3 | Z_A X_B | -Z_A Y_B |

The seam observable is T=Z_A Z_B. All nine are distinct, traceless Hermitian
Pauli words, orthonormal under the normalized trace tau. Each pair P_j,Q_j
anticommutes and squares to I.

For Gamma>0 choose its Cayley coordinate

\[
t=\frac{\Gamma-1}{\Gamma+1}\in(-1,1),\qquad
\Gamma=\frac{1+t}{1-t}.
\]

This reuses the pinned native Cayley identity. Identifying its positive
coordinate with the seam ratio is a **new calibration choice**, not a
derived physical relation. It preserves the positive-line domain without
identifying log(Gamma) with a circle. Gamma -> 1/Gamma gives t -> -t.

Put A_j=cos(theta_j) P_j+sin(theta_j) Q_j and propose

\[
D(\theta,\Gamma)=I+\frac15\left(\sum_{j=0}^{3}A_j+tT\right),
\qquad \omega_D(O)=\tau(DO).
\]

D is the normalized-trace density element; in the derived four-dimensional
matrix representation the ordinary trace-one density matrix is rho=D/4.
The signs, reading bank and equal weight 1/5 are deliberate design choices.
They are not uniquely forced by the source manuscripts.

The implementation uses the existing Q(zeta_64) field, with zeta_64=exp(2pi i/64),
and the same EMK basis multiplication as v0.2. It supports source grids
4,8,16,32,64 without rounding; other grids fail explicitly. It has 16
operator coefficients, each with 32 rational field coordinates. Coefficient
numerator/denominator sizes are bounded at 4096 bits; source event/lift bounds
still apply. No calculator circuit-state or probability engine is imported.

## 2. Positivity, normalization and exact inverse

Each A_j is a Hermitian involution, so (I+A_j)/2 is a projector. The following
is an explicit positive decomposition:

\[
D=\frac15\sum_{j=0}^{3}(I+A_j)+\frac15(I+tT).
\]

The last term has positive eigenvalues because |t|<1. In particular

\[
D\geq\frac{1-|t|}{5}I>0,\qquad \tau(D)=1.
\]

The executable positive-square witness uses six factors: four projectors
(I+A_j)/2 of weight 2/5, and the two projectors (I+T)/2, (I-T)/2 of weights
(1+t)/5 and (1-t)/5. Their weighted S S* sum is exactly D, with normalization
one. This is the existing positive-functional prescription, extended only
in its coefficient field.

Orthogonality gives the inverse readings:

\[
5\omega_D(P_j)=\cos\theta_j,\quad
5\omega_D(Q_j)=\sin\theta_j,\quad
5\omega_D(T)=t.
\]

Combining each pair gives exp(i theta_j). The exact decoder matches that
element against the declared root-of-unity grid, recovers Gamma through the
Cayley inverse, and reconstructs the entire D to reject extra moments or
wrong weights. Thus equal encoded states imply the same four wrapped phases
and the same Gamma. A common shift of all four phases remains distinguishable
in this construction; these phases are moment coordinates, not the discarded
global phase of a wavefunction.

This inverse assumes **exact expectation values**. It is not a finite-shot
tomography algorithm. Sampling error, confidence regions and calibration
uncertainty are not implemented. Recovering Gamma is especially sensitive
as t approaches +1, since dGamma/dt=2/(1-t)^2.

## 3. Which information is retained where

| Information | In the quantum code alone? | Recovery in this implementation |
| --- | --- | --- |
| Four wrapped phases | Yes, through expectation values | Exact tomographic decoder |
| Positive Gamma and its dual | Yes, through t | Exact rational Cayley inverse |
| Phase closure sign | Computable from phases plus the declared twist | Source configuration supplies twist/sector |
| Integer lift/winding convention | No | Replayed initial lifts and operation tape |
| Event order, cut count and cost | No | Replayed classical tape under the original cost policy |
| Read/reset outcomes and lost preimages | No | Reconstructed deterministic before/after records |

`Bridge` stores D, the source configuration, initial lifts and an immutable
operation tape. Gamma is decoded from D; replay reconstructs the source cell,
and its final phases must agree with the code. `verify_bridge` checks that
re-encoding the reconstructed cell reproduces the bridge. This verifies
internal consistency, not cryptographic authenticity of a claimed experiment.

A full +L turn and a full -L turn give the same code, but different tapes.
Two inverse cuts may restore the code while retaining a different cost.
The initial conditions/tape already contain extensive classical information;
retaining them is **not quantum memory compression**.

## 4. Exact compiled transports

For a source `pair_shift(0,2,d)` put phi=2pi d/L and

\[
V_A(\phi)=\frac{I+Z_A}{2}
          +e^{i\phi}\frac{I-Z_A}{2}.
\]

Conjugation rotates X_A,Y_A in the usual orientation. The minus sign in Q_2
reverses that orientation, giving

\[
(\theta_0,\theta_2)\mapsto(\theta_0+\phi,\theta_2-\phi).
\]

All other encoded readings, including the seam T, are unchanged. Therefore

\[
D(\operatorname{pair\_shift}_{0,2,d}(x))
=V_A(\phi)D(x)V_A(\phi)^*.
\]

The analogous V_B implements the pair (1,3). Reversing a pair reverses phi.
The source phase sum is preserved, so these operations respect its fixed
closure sector whenever the source's finite resource checks pass.

The product of source swaps (0,1) and (2,3) exchanges the two sites. Its
unitary is

\[
W=\frac12(I+X_AX_B+Y_AY_B+Z_AZ_B).
\]

The two source swaps can be listed in either order. They preserve the phase
sum and Gamma. The compiler checks unitarity and the exact identity
D_after=U D_before U*. A separate verifier checks source/tape consistency,
the selected compilation rule, and operator equality.

Using V_A=diag(1,exp(i phi)) avoids needing a 128th root for half-angle
coefficients when the source uses 64 bins. The discarded global unitary
phase has no effect on this conjugation identity.

Only these declared words are compiled. Cuts, resets, shears, arbitrary
pairings and single swaps have no implicit fallback. `ledger_update` is a
different interface: it applies a command to **known classical data** and
re-encodes the result. It does not assert a channel acting on an unknown
quantum codeword.

## 5. A balanced cut that cannot be a channel on this encoding

Take Gamma=1, grid L=64, fixed + closure sector, and source lifts

\[
x=(0,0,0,0),\qquad y=(16,-16,0,0).
\]

Both phase sums are zero. Apply the same source balanced cut (j=0,s=2,h=0):

\[
x'=x,\qquad y'=(-16,-16,32,0).
\]

The sums remain zero, so the example uses valid states and operations even
inside the constrained source sector.

Before the cut,

\[
\rho_x-\rho_y=\frac{X_A-Y_A+X_B+Y_B}{20}.
\]

The commuting involutions A=(X_A-Y_A)/sqrt(2) and
B=(X_B+Y_B)/sqrt(2) each have eigenvalues +/-1. Their four joint projectors
have rank one. Consequently the difference has eigenvalues
+sqrt(2)/10, 0, 0, -sqrt(2)/10 and the trace distance is

\[
\frac12\|\rho_x-\rho_y\|_1=\frac{\sqrt2}{10}.
\]

After the cut, the P_2=X_A Z_B expectations are +1/5 and -1/5. That single
binary measurement has outcome-distribution distance 1/5. Hence the output
trace distance is at least 1/5, strictly greater than sqrt(2)/10.

A deterministic completely positive trace-preserving channel cannot increase
trace distance. For a channel Phi, any output measurement pulls back through
Phi* to a valid input measurement, so its distinguishability cannot exceed
the optimal input distinguishability. Standard reference:
[Quantum Catalytic Space, contractivity statement](https://drops.dagstuhl.de/storage/00lipics/lipics-vol350-tqc2025/html/LIPIcs.TQC.2025.11/LIPIcs.TQC.2025.11.html).

Thus **no single deterministic quantum channel on this code alone implements
that native balanced cut for the whole encoded family**. The exact spectral
resolution and output witness are tested. This is an obstruction to this
particular encoding/operation combination, not a no-go theorem for every
native framework or every possible encoding.

If a controller also receives the classical state/tape, it can select a new
preparation using that extra information. Such a larger process has a
different input resource and is not ruled out by this example. That is why
the software keeps re-encoding separate from channel compilation.

## 6. Readout and resource boundaries

The original phase-point model returns an exact phase label deterministically.
Here, at theta_0=0 a P_0 measurement gives +1 with probability 3/5 and -1 with
probability 2/5. It does not return phase label zero. The inverse is a statement
about a bank of expectation values.

Every codeword is full rank, so two distinct codewords cannot be perfectly
distinguished in one copy. More generally, a quantum encoding preserving all
four deterministic grid-64 labels in a joint one-copy readout needs at least
64^4=2^24 mutually orthogonal states. With one fixed closure sign and twist,
there are still 64^3=2^18 phase labels. Gamma/history are held fixed in these
counts. These are storage/readout dimension lower bounds—24 or 18 qubits for
an orthogonal register—not a claim of quantum computational capacity or a
requirement for the present expectation-value encoding.

The positive mixture also has a strict image boundary:

\[
\operatorname{Tr}(\rho^2)
=\frac14\left(1+\frac{4+t^2}{25}\right)<\frac3{10}.
\]

The v0.2 pure Bell functional has purity one and is outside this image.
Unitary operations preserve purity, so merely applying its entangling unitary
to this mixed code cannot prepare that pure functional.

A stronger bound applies to nontrivial binary qubit settings. Their CHSH
operator S is traceless and tau(S squared)=4. Cauchy–Schwarz for the trace
pairing gives, after **any** global unitary conjugation of D,

\[
|\omega_D(S)|^2\leq
\tau((D-I)^2)\tau(S^2)
=\frac{4(4+t^2)}{25}<\frac45.
\]

The equality of the right-hand invariant under unitary conjugation proves
that this five-component code is far too mixed to yield a Bell violation
through unitaries alone. This does not change the v0.2 result for its different
pure preparation. Trivial identity-valued binary settings do not supply a
Bell violation either, but are outside the displayed traceless calculation.

The five components are also initially separable: the first two are local
equatorial states times a maximally mixed partner; the next two are local
equatorial states conditioned on the partner's Z value; I+t Z_A Z_B is a
positive diagonal mixture of product Z states. No entangled resource has
been silently supplied by this phase/seam encoding.

## 7. Reproduce and next design decision

```bash
python -m phase_seam_foundation.encoding_qualification
python benchmarks/phase_seam_encoding_audit.py
```

[encoding_qualification.json](encoding_qualification.json) retains the exact
code, nine readings, decoded values, history checks, unitary witness,
channel obstruction, image bounds and code/source hashes.
[encoding_test_results.txt](encoding_test_results.txt) retains the combined
targeted test run. [encoding_source_manifest.json](encoding_source_manifest.json)
separates inherited relations from the new chart and mixture choices.

The saved audit passes **87 tests in 46.594 seconds**, with no failures,
errors or skips: 23 new encoding tests plus the 64 existing targeted checks.
New coverage includes all 256 phase/mode round trips at grid 64, all 64
transport angles for a declared closed-sector example, both opposed pair
orientations across five grids, exact positive-square reconstruction, a
paired swap against an independent matrix permutation, extended-field
products against independent matrices, preserved/reset history, tampered
bridges/certificates, invalid grids and resource failures. The obstruction
has an independent exact spectral-resolution test. This is not an exhaustive
enumeration of all 64^4 phase tuples; the written identities establish the
general statements.

Closed: injective finite tomography for all four phases and positive Gamma;
full source-cell recovery using retained classical provenance; exact opposed
pair transports and paired swap; a concrete obstruction for the balanced cut.

Open: full source-measurement/channel equivalence; finite-shot decoding and
physical calibration; preparation of a nonclassical resource from native
physical primitives; material hardware, energy/time laws and scalable computing.

The [v0.4 register compiler](REGISTER.md) explores the change-of-encoding
option: orthogonal phase labels permit coherent native cut permutations at
the cost of 24 phase + 4 clean workspace wires on grid 64. It does not
convert this two-site mixed code into exact labels, invalidate this
obstruction, or encode Gamma and path history in those wires. Physical
preparation and controller/environment accounting remain open.
