# Two-site cut algebra and quantum-compatible readout — v0.2

Author: Monty. Status: conditional mathematical completion with exact software
checks. No physical device, experimental Bell violation or new law of nature
is claimed.

The new result is a concrete two-site preparation, interaction, joint readout
and sequential update law built on the existing EMK multiplication. It gives
CHSH = 2 sqrt(2), normalized positive probabilities, non-signaling marginals,
and a constructively recovered four-dimensional inner-product representation.
The additional probability and composition postulates are stated below.

This is an **algebraic quantum completion**, equivalent in its admitted sector
to ordinary two-qubit quantum mechanics. It is not a derivation of those
postulates from the four phase coordinates alone. The previous v0.1 model
continues to obey its proved local CHSH bound of 2. We have changed the state
and measurement law, not found an exception to that theorem.

## 1. Dependency and assumption ledger

The pinned native source is [EMK-2 at Publications commit
35d63e4](https://github.com/Parveen117/Publications/blob/35d63e4ac0d8cf161c549654ce6b430d68afbde4/papers/emk-ugd-algebra/certificates/emk2_native_carrier.py).
Only its finite relations are admitted:

\[
K^2=I,\qquad R^2=-I,\qquad KR=-RK,\qquad L=RK.
\]

The local ordered basis is I,K,R,L. The product is derived by moving K past R:

\[
(R^rK^k)(R^sK^t)=(-1)^{ks+rs}
R^{r\oplus s}K^{k\oplus t}.
\]

This revision adds the following explicit operational assumptions.

| Assumption | What it supplies | Not obtained from the four manuscript phases |
| --- | --- | --- |
| Complex scalar extension and star: K*=K, L*=L, R*=-R | Adjoints and ordered positive squares | Why nature chooses this extension |
| Commuting products between distinct sites | Local compatibility and a joint 16-dimensional operator algebra | A unique physical composition law |
| Positive normalized preparation functional | Consistent probabilities for all admitted effects | A derivation of positivity/readout from winding |
| P(a given A) = omega((I+aA)/2) | Binary projector measurement | A proof that this is the only measurement postulate |
| Sandwich state update and complete channels | Sequential outcomes and nonselective dynamics | Physical detector backaction |
| Selected reference preparation and joint U | A specific entangled state and testable calculation | A material coupling or preparation device |

These are substantial assumptions, not auxiliary numerical conveniences.
Positive-functional states and induced inner-product representations are the
established algebraic quantum/GNS route; see [Arab](https://arxiv.org/abs/2110.00793).
The contribution here is a source-pinned, finite implementation and derivation
for the chosen native cut algebra, with explicit boundaries. It is not a new
GNS theorem or a discovery of the quantum Bell bound.

The interpreter uses only the existing exact Q(sqrt(2),i) arithmetic.
It imports no circuit-state, Born-probability, Qiskit or matrix engine.
One-site and two-site algebras have 4 and 16 coefficients respectively.
The supplied settings include an exact subset of the older phase grid; full
64-bin readout support is not implied by this smaller coefficient field.

## 2. Oriented cuts and the antiunitary distinction

Define an observable/cut

\[
C_\alpha=\cos(2\alpha)K+\sin(2\alpha)L.
\]

Anticommutation gives C_alpha*=C_alpha and C_alpha squared = I. Also

\[
C_\beta C_\alpha
=\cos(2(\beta-\alpha))I+\sin(2(\beta-\alpha))R.
\]

In the faithful real coordinate presentation

\[
K=\begin{pmatrix}1&0\\0&-1\end{pmatrix},\quad
R=\begin{pmatrix}0&-1\\1&0\end{pmatrix},\quad
L=\begin{pmatrix}0&1\\1&0\end{pmatrix},
\]

C_alpha reflects the real pair (x,y) exactly as
z -> exp(2i alpha) conjugate(z), with z=x+iy. The interpreter checks this
against all 64 phase/axis combinations on the v0.1 grid L=8.

**Complexifying this real two-coordinate carrier is a new step.** C_alpha
then acts complex-linearly on two complex coordinates. It does not conjugate
those quantum coefficients. In particular C_alpha(i v)=i C_alpha(v). The
v0.1 negative complete-positivity witness for *universal conjugation of unknown
quantum amplitudes* still holds. This proposal uses a different extension,
not a way to physically implement that forbidden identification.

The displayed matrices are a faithful representation and independent test
reference. The implementation multiplies native basis words. The original
EMK source uses a conjugate choice of K; the generator relations agree.

## 3. Positive preparation and normalized readout

Let tau select the identity coefficient. Basis multiplication proves

\[
\tau(X^*X)=\sum_\nu |x_\nu|^2,\qquad
\tau(XY)=\tau(YX).
\]

For preparation operators S_j and positive real weights w_j, propose

\[
Z=\sum_jw_j\tau(S_j^*S_j)>0,\qquad
\omega(A)=Z^{-1}\sum_jw_j\tau(S_j^*AS_j).
\]

Then omega(I)=1 and

\[
\omega(X^*X)=Z^{-1}\sum_jw_j\tau((XS_j)^*(XS_j))\geq0.
\]

The code retains the preparation factors and computes the derived algebra
element D=sum(w_j S_j S_j*)/Z for efficient evaluation tau(D A). No arbitrary
table of moments is accepted as a state. This construction includes positive
mixtures; it is a chosen positive cone and readout law.

For a self-adjoint involution A and outcome a in {-1,+1}, set
E_a=(I+aA)/2. The two E are orthogonal self-adjoint projectors summing to I.
For local A on site A and B on site B:

\[
p(a,b\mid A,B)=\omega(E_aF_b).
\]

Because the sites commute, E_a F_b is itself a projector and hence a positive
square. All joint probabilities are nonnegative and sum to one. Summing over
b gives omega(E_a), independent of B. This proves no-signaling of the
unconditioned marginals for every admitted state, not just the Bell example.

There is no simultaneous pre-existing assignment to all noncommuting local
observables in this model. Each measurement context has a positive outcome
distribution. Consequently the shared phase-point hidden-variable hypothesis
used in v0.1's CHSH proof does not apply to this new state/readout law.

## 4. A joint interaction and derived outcome table

Choose the reference preparation operator

\[
Q_0=\frac{I+K_A}{2}\frac{I-K_B}{2},\qquad
G=R_A L_B,\qquad U(\chi)=\cos\chi\,I-\sin\chi\,G.
\]

G*=-G and G squared = -I, so U is unitary. This coupling is proposed, not
identified with v0.1's balanced coordinate update. Set chi=pi/4 and use the
preparation factor S=U Q0. Multiplication and tau give

\[
\omega(K_AK_B)=-1,\quad
\omega(L_AL_B)=-1,\quad
\omega(R_AR_B)=+1,
\]

with zero local K,L,R readings and zero mixed-axis correlations. The complex
Hermitian axis iR has correlation -1 as well. For
A=uK_A+vL_A and B=xK_B+yL_B with real unit-circle coefficient pairs:

\[
\omega(AB)=-(ux+vy),\qquad
p(a,b\mid A,B)=\frac{1-ab(ux+vy)}4.
\]

The program obtains probabilities by multiplying projectors and evaluating
omega; it does not read this formula or a preloaded Bell table.

Take A0=K_A, A1=L_A and
B0=-(K_B+L_B)/sqrt(2), B1=(-K_B+L_B)/sqrt(2).

| Settings | Correlation | Each same-sign outcome | Each opposite-sign outcome |
| --- | --- | --- | --- |
| A0,B0 | +1/sqrt(2) | (2+sqrt(2))/8 | (2-sqrt(2))/8 |
| A0,B1 | +1/sqrt(2) | (2+sqrt(2))/8 | (2-sqrt(2))/8 |
| A1,B0 | +1/sqrt(2) | (2+sqrt(2))/8 | (2-sqrt(2))/8 |
| A1,B1 | -1/sqrt(2) | (2-sqrt(2))/8 | (2+sqrt(2))/8 |

Every single-site outcome has probability 1/2. The CHSH combination is
exactly 2 sqrt(2). This is a calculated prediction of the admitted algebraic
quantum completion, not measured hardware data.

The reference product preparation alone gives CHSH=sqrt(2) for these same
settings; the normalized trace state gives zero. Under the explicitly
declared mixture with white noise, omega_v=v omega+(1-v)tau, the same
combination is 2 sqrt(2) v and exceeds 2 precisely when v>1/sqrt(2).
That is a model-specific visibility threshold, not a measured device budget.

## 5. Why this completion stops at 2 sqrt(2)

For any allowed binary local settings, write

\[
\mathcal S=A_0(B_0+B_1)+A_1(B_0-B_1),\qquad
D_0=A_0-\frac{B_0+B_1}{\sqrt2},\quad
D_1=A_1-\frac{B_0-B_1}{\sqrt2}.
\]

Using only involutions and cross-site commutation:

\[
2\sqrt2\,I-\mathcal S
=\frac{D_0^*D_0+D_1^*D_1}{\sqrt2}.
\]

Positivity of omega gives the upper bound. Flipping both A settings gives
the lower bound, hence |omega(S)| <= 2 sqrt(2). The chosen preparation
saturates it because both positive-square expectations vanish. This is a
direct instance of the established Tsirelson bound; contextual reference:
[Choudhary et al.](https://arxiv.org/abs/quant-ph/0608100).

A negative control assigning correlations (1,1,1,-1) to K/L settings would
give CHSH=4. Evaluating D0*D0 with those moments gives 2-2 sqrt(2)<0.
Thus that table is not an admitted positive state. This exclusion follows
from our operator-positivity assumptions; no-signaling by itself does not
enforce this bound.

## 6. Sequential measurements and complete channels

For a projector E, the outcome has probability p=omega(E). If p>0 the
conditional preparation factors are E S_j, yielding

\[
\omega_E(A)=\frac{\omega(EAE)}{\omega(E)}.
\]

A zero-probability outcome remains explicitly (0,None); it is never
normalized into a fictitious state. Repeating the same projective reading
gives the same outcome with certainty. Reading a noncommuting observable
can change later probabilities. For the selected Bell preparation, measuring
K_A=+1 gives conditional K_B=-1; this is a conditional statistic.

A nonselective channel uses factors K_mu S_j and must satisfy
sum(K_mu* K_mu)=I. A local complete channel leaves remote expectations
unchanged because those observables commute with every K_mu. Incomplete
channels fail rather than silently discard outcomes. The tests separately
check selective correlations and nonselective local measurement/reset.

These sandwich instruments are explicit added dynamics. Neither their
physical backaction nor the existence of a material joint interaction has
been derived from the time-tensor manuscript.

## 7. Inner product recovered after the operational law

Define on operator words

\[
\langle A,B\rangle_\omega=\omega(A^*B),\qquad
\mathcal N_\omega=\{A:\omega(A^*A)=0\}.
\]

The explicit factor formula shows that a null A satisfies A S_j=0 for all
j. This is a left ideal: X A S_j=0 as well. Quotienting by these null
directions gives a positive-definite form. Left multiplication then defines
a star representation pi(X)[A]=[XA]. The class of I is a cyclic vector and

\[
\omega(P)=\|\pi(P)[I]\|_\omega^2
\]

for each projector P. Thus the Born **representation identity** is recovered
from the chosen positive-functional/readout postulates. It is not a derivation
of the probability postulate itself from cuts alone.

The implementation builds M_ij=omega(e_i* e_j), finds independent quotient
coordinates C, and checks M=C* M_basis C. A separate `verify_gns` checks
state binding, independent basis, coordinate normalization and reconstruction
without calling the quotient search. `represent` uses those coordinates for
left multiplication; imported certificates should first pass `verify_gns`.

For the chosen pure two-site preparation: 16 algebra coordinates, Gram rank
4, and 12 null directions. The exact quotient is first over Q(sqrt(2),i);
extending scalars to C gives a four-dimensional Hilbert space. For the
normalized trace state, the cyclic GNS dimension is 16. That larger dimension
represents a mixed functional; it is not additional physical qubits.

The algebra is faithfully representable as M4(C), so this completion
recovers a conventional two-qubit sector. The physical interpretation of
the four v0.1 phase coordinates, positive seam ratio and history as such a
state is still missing. Matching reflection actions on a real circle is
not a proof of a faithful map between the full operational models.

## 8. Hardware requirement now made concrete

The two-site model identifies a precise interaction target:

\[
U(\chi)=\cos\chi\,I-\sin\chi\,R_A L_B,\qquad \chi=\pi/4.
\]

If a physical realization uses the conventional representation
Y=iR and X=L, an engineering Hamiltonian producing it is
H_int=-hbar g Y_A X_B with integrated pulse area chi=integral(g dt).
This follows since -i H_int dt/hbar=-g dt R_A L_B. Introducing a laboratory
time coordinate here does not derive the proposed emergent time tensor.

| Required operation | Acceptance target | What remains to establish |
| --- | --- | --- |
| Reference preparation | K_A=+1, K_B=-1 | Preparation mechanism and fidelity |
| Coherent joint coupling | U(pi/4), including relative phase | Material interaction, calibration and noise |
| Four local reading axes | K_A, L_A, -(K_B+L_B)/sqrt(2), (-K_B+L_B)/sqrt(2) | Physical observable mapping and detector backaction |
| Local projective instrument | Repeatability and the derived conditional update | Detector model, loss and retained records |
| Complete local operations | Remote unconditioned marginals unchanged | Experimental isolation and accounting for every outcome |
| Framework encoding | Map phase/seam/memory data to admissible operator preparations | No faithful full encoding has yet been supplied |

A controller that samples these calculated probabilities does not create a
quantum interaction. Nor does a classical phase-channel emulator inherit
these correlations merely by using the same cut names. The present target
specifies two quantum-compatible operator sectors, not a built two-qubit
device or a demonstrated conversion of four classical phase channels.

## 9. Reproduce and interpret

```bash
python -m phase_seam_foundation.joint_qualification
python benchmarks/phase_seam_joint_audit.py
```

The audit runs the new joint tests, unchanged v0.1 foundation tests, and
existing calculator smoke suite serially. It saves
[joint_qualification.json](joint_qualification.json), including the full
exact GNS certificate and source hashes, and
[joint_test_results.txt](joint_test_results.txt).
The old Shor benchmark and full native suite are not rerun or relabeled.

The saved run passes **64 tests in 7.680 seconds**, with no failures, errors
or skips: 26 joint tests, 26 v0.1 tests and 12 calculator checks. These include
all 4096 two-site basis-associativity triples; all 272 one/two-site basis
products against independent dense matrices; all 64 grid-8 reflection inputs;
all 64 pairs of eight planar readout axes; independent dense preparation
probabilities; exact positive-square and PR-table controls; complex-state
quotient/adjoint checks; wrong-state/tampered quotient rejection; and resource,
normalization and incomplete-channel failures.

Closed conditionally: a positive two-site operational law, explicit entangling
preparation, exact Bell probabilities, sequential/no-signaling consistency,
the sum-of-squares bound, and finite GNS recovery.

New assumptions: the six entries in the assumption ledger. Original
manuscripts, the v0.1 classical interpreter, and calculator semantics are
unchanged.

Open: derive or motivate those physical postulates from the native primitives;
construct the full phase/seam/history-to-operator encoding; select and test a
material interaction; derive energy/time/noise laws; establish universal or
scalable computation. The immediate next research gate is the encoding and
its retained-observation equivalence, not an increase in claimed qubit count.
