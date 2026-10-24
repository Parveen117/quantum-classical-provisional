# Local-control obstruction and an exact bus-mediated EMK gate — v0.15

**Author: Monty. Status: conditional operator construction, with exact code
checks.** The existing two-site entangler is now connected to four explicit
data–bus interaction targets. Its ideal action returns the bus for every
initial bus state. A doubled sequence cancels specified local phase drift.
An exact fault map shows why these properties do not imply immunity to noise
during the gate. This is not a claim of a new law, fabricated interaction,
fault-tolerant computer or demonstrated quantum advantage.

## 1. Existing work and the missing resource

The repository already has the two-site EMK interaction

\[
U_{\rm EMK}(\chi)=\cos\chi\,I-\sin\chi\,R_A L_B
\]

in [JOINT_READOUT.md](JOINT_READOUT.md), together with positive preparations,
readout and exact Bell predictions. That interaction is an assumed joint
operation, not something produced by a local material susceptibility.
This revision supplies an alternative conditional decomposition of it.

The upstream [PH2 strain-cycle note](https://github.com/Parveen117/extra-ideas/blob/4aad5a0ec0fbdac727894ad0c315ed822cc0350e/physics/ph2/PH2_STRAIN_CYCLE_ROTATION.md)
describes rotations obtained by closed cycles of positive strain. A local
optical realization using positive filters must retain its attenuation and
success probability. A loop's nonzero rotation or curvature does not itself
establish a joint quantum interaction. No PH2 source is changed here.

**Local-control obstruction.** Suppose A and B start separable and every
resolved operation branch is a product `M_A tensor N_B`. This includes local
PH2 cycles, local filtering, shared classical control and communication with
retained outcomes. Every branch maps a product vector to another product
vector. For a separable mixed state, the unnormalized output is a positive
sum of product operators; conditioning on a nonzero-probability collection
of such branches preserves separability. Thus these resources cannot
prepare entanglement from separable inputs. A joint projection, quantum bus
coupling or initially shared entangled resource changes the assumptions.

In the particular product-metric model `H=H_A tensor H_B`, the proposed
connection also separates:

\[
\tfrac12 H^{-1}dH
=\tfrac12 H_A^{-1}dH_A\otimes I
+I\otimes\tfrac12 H_B^{-1}dH_B.
\]

Its transport factors into local transports along the path. This statement
does not exclude the existing abstract joint interaction or the register's
joint permutations: those explicitly supply nonlocal operations already.

The 16 paths in [PHOTONIC_EXCHANGE.md](PHOTONIC_EXCHANGE.md) encode labels of
**one photon**. Repartitioning those labels is not a realization of two
independently preparable data carriers. The current SiN layout does not
provide the new conditional bus interactions below.

## 2. Explicit conditional interaction contract

Take two independent two-level data carriers A,B, with `Z=K`, and a coherent
d-level bus C. This retains the existing algebraic quantum completion and
its finite Hilbert-space representation; it does not remove that structure.
Let

\[
X|k\rangle=|k+1\bmod d\rangle,\quad
Z_C|k\rangle=\omega^k|k\rangle,\quad
\omega=e^{2\pi i/d},\quad Z_CX=\omega XZ_C.
\]

The **added physical resources** are reversible coherent controlled kicks

\[
X_A(a)=\sum_{s=\pm1}\Pi^A_s\otimes X^{as},\qquad
Z_B(b)=\sum_{t=\pm1}\Pi^B_t\otimes Z_C^{bt},
\]

with integer a,b, their inverses, coherent local preparation and local gates.
Both data systems must actually couple to the same quantum bus; neither
measuring a control bit nor a classically programmed phase substitutes for
these operators. Their physical implementation and rates are not inferred
from the TVSP response coefficients. Compilation into existing CNOT gates
would already assume an entangling resource, so is not used as that argument.

In **execution order**, apply

1. `X_A(a)`;
2. `Z_B(b)`;
3. `X_A(-a)`;
4. `Z_B(-b)`.

For eigenvalues s,t and every bus basis state k, the two phase kicks give
`omega**(bt*(k+as)) * omega**(-bt*k) = omega**(abst)`.
The complete operator identity is therefore

\[
W(a,b)=Z_B(-b)X_A(-a)Z_B(b)X_A(a)
=e^{i\theta Z_AZ_B}\otimes I_C,\qquad \theta=2\pi ab/d.
\]

Consequences are operator-level, not dependent on a chosen bus preparation:
the bus returns for arbitrary pure or mixed states, including correlations
with an external reference. On an input product `rho_AB tensor rho_CR`, the
output is `U rho_AB U* tensor rho_CR`. The identity also holds on initially
correlated ABC states, but it does not erase pre-existing correlations.

For d=64, a=2,b=4, theta=pi/4. On `|++>` the data reduced states are I/2,
so the output is maximally entangled. In general its concurrence is
`|sin(2 theta)|`, and the diagonal nonlocal phase is `4 theta mod 2 pi`.
In the convention `R(phi)=diag(1,exp(i phi))`,

\[
U=e^{i\theta}[R_A(-2\theta)\otimes R_B(-2\theta)]\,CR(4\theta).
\]

This gives CZ up to local phases at theta=pi/4. With appropriate independent
single-qubit gates it is a universal gate-set ingredient, not a scalability
or execution-time result.

## 3. Exact reuse of the native EMK interaction

Use the existing relations `K^2=L^2=I`, `R^2=-I`, `L=RK`, and `iR=Y`.
Set

\[
C_A=(I+iL_A)/\sqrt2,\qquad C_B=(I+R_B)/\sqrt2,\qquad C=C_AC_B.
\]

Direct native multiplication gives `C_A K_A C_A*=iR_A` and
`C_B K_B C_B*=L_B`, hence

\[
C e^{i\theta K_AK_B} C^*
=\cos\theta\,I-\sin\theta\,R_A L_B.
\]

The `native_interaction_bridge()` function verifies the theta=pi/4 identity
using unchanged `joint.Element`, `local` and `interaction`. The old native
reference preparation and Bell functional are reused; this is not another
Bell model. The local complex gate C_A is a stated control requirement, not
claimed to follow from a real two-dimensional strain rotation alone.

## 4. What the echo cancels

Let `F=X_A X_B` on the data and let each half implement

\[
V_j=E_j U(\theta/2),\qquad
E_j=e^{i(\delta_{Aj}Z_A+\delta_{Bj}Z_B)}.
\]

Execute `V_1, F, V_2, F`. The kicks are diagonal in the data Z axes, so local
Z errors commute through them. For equal integrated local drifts in the two
halves and ideal instantaneous flips,

\[
F V_2 F V_1=E_2^{-1}E_1 U(\theta)=U(\theta).
\]

This equality holds for arbitrary real delta, not merely the exact test
grid. Time-independent local Z detuning with matched half durations is one
sufficient model. Unequal drift leaves
`exp(i[(delta_A1-delta_A2) Z_A + (delta_B1-delta_B2) Z_B])`.
An unwanted ZZ phase commutes with F and **adds** across the halves. Bus
noise, pulse-area error, imperfect flips, leakage and attenuation are not
removed by this identity. A finite-duration implementation requires its
own control/noise Hamiltonian; no such performance is assumed here.

At d=64 use a=1,b=4 in each half. The echoed target has eight conditional
bus kicks and four single-qubit flips, excluding preparation/basis changes.

## 5. Exact bus-fault propagation and an obstruction

Insert a bus Weyl error `E=X^r Z_C^s` after j of the four ideal kicks. Its
normal bus order is X then Z (so the injected execution order is Z then X).
For the bare rectangle the output factors as
`[D_j U(theta)] tensor E`, where

| Fault seam j | Data error D_j |
| --- | --- |
| 0, before the loop | I |
| 1, after X_A(a) | omega**(a s Z_A) |
| 2, after Z_B(b) | omega**(a s Z_A - b r Z_B) |
| 3, after X_A(-a) | omega**(-b r Z_B) |
| 4, after the loop | I |

The table follows by commuting E through the remaining kicks, or by direct
basis action. Each resolved Weyl fault yields local data rotations, with no
extra ZZ rotation. A mixture of faults can still cause **correlated** local
dephasing. Arbitrary coherent bus errors are sums of these terms and are not
claimed to preserve a product output. Photon loss or leakage need not even
stay in this finite bus algebra.

For a=2,b=4,d=64, one unit of both faults at seam 2 leaves relative phases
`(-pi/8,+pi/4)` on the data-one states, despite perfect final bus separation.
Even the echoed loop fails to cancel a lone unit clock fault after its first
kick. Initial-state independence is therefore weaker than in-gate noise
immunity.

**Within this signed rectangle family**, requiring no data error (up to a
global phase) for every Weyl fault at every seam forces

\[
2a=0\pmod d,\qquad 2b=0\pmod d.
\]

Proof: take s=1 at seam 1 and r=1 at seam 3. The two eigenvalues of each
resulting local rotation must agree. These conditions are also sufficient
by the table. But then `X^a=X^-a` and `Z_C^b=Z_C^-b`: both supposed controls
are bus-only. In particular `4ab=0 mod d`, so the gate is nonentangling.
This rules out a fully bus-fault-immune entangler **of this form**. It is not
a no-go theorem for error correction, other encodings or other architectures.

## 6. Dimension and phase limits

The 64-level choice matches the calculator's existing `Q(zeta_64)`; it is
not a physical minimum. A signed rectangle is locally equivalent to CZ
exactly when `8ab=(2m+1)d`. Thus d must be divisible by 8 and d=8,a=b=1
suffices. For the two identical half loops of the stated echo,
`16ab=(2m+1)d`, so d=16,a=b=1 suffices and is minimal in that family.
These are **not** lower bounds for all bus gates: projector-controlled
qubit-bus gates can use a two-level bus.

There is a second finite-dimensional constraint. If invertible d by d
operators obey `ABA^-1B^-1=lambda I`, taking determinants gives
`lambda**d=1`. An arbitrary continuous scalar commutator phase is therefore
unavailable at fixed finite d. This does not constrain arbitrary data gates
or gates allowed to depend on a selected bus state. Nor is it a finite-matrix
realization of the impossible exact relation `[q,p]=iI`, whose traces disagree.

## 7. Software scope and reproducibility

`weyl_bus.py` adds a bounded word checker, not an amplitude simulator. It
retains all four data branches as `zeta_64**p X**x Z_C**z`, with local flips
and phases explicit. Branch order is 00,10,01,11 (A is the low bit).
Coincidence of all bus X/Z labels is necessary and sufficient for universal
data/bus factorization in this monomial language. Identity labels additionally
certify bus return. A missing last kick can pass on bus `|0>` while failing
this universal check, so checking one initialized bus is insufficient.

Admitted dimensions are 2,4,8,16,32,64; words contain at most 512 instructions;
integer strengths lie in [-4096,4096]. Bool, float and fractional kick inputs
are rejected. Roots of unity are supplied by the existing exact field. No
continuous calibration value is rounded into an exact identity. Linear word
cost here follows from two data qubits and this restricted language; it is
not efficient simulation of arbitrary quantum circuits or 2056 qubits.

```python
from phase_seam_foundation.weyl_bus import (
    rectangle, echoed_rectangle, certificate, fault_certificate,
)

gate = certificate(rectangle())
assert gate["bus_returned"] and gate["nonlocal_phase_steps"] == 32
echo = certificate(echoed_rectangle(drift=(7, -11)))
assert echo["nonlocal_phase_steps"] == 32
fault = fault_certificate(rectangle(), after=2, x=1, z=1)
assert not fault["data_unchanged_up_to_global_phase"]
```

Run `python benchmarks/weyl_bus_audit.py`. The manifest records exact model
examples, source hashes, bounded test counts and retained previous-source
hashes. The new tests cover 5,460 rectangles, every basis column for selected
64-level words, 20,480 Weyl-fault/seam cases, an external reference, local
filtering, echo drift, failed closure and the existing native interaction.
The unchanged joint-algebra suite is also run. The previous CAD, full native,
constitutive/observer and Shor suites are not rerun by this audit.

## 8. Prior art and remaining theoretical work

Finite-dimensional bus-mediated controlled phase gates are established work:
Proctor, Dooley and Kendon, *Quantum computation mediated by ancillary qudits
and spin coherent states*, [arXiv:1402.6674](https://arxiv.org/abs/1402.6674),
Phys. Rev. A **91**, 012308 (2015). Their Sections II–III describe controlled
displacements, closed-loop phases and the difference between arbitrary-state
and selected-state bus operation. This construction belongs to that family;
neither geometric entangling gates nor bus-state independence is claimed as
a new discovery. Gate dissipation also has established analyses, e.g.
Louis et al., [arXiv:0804.3240](https://arxiv.org/abs/0804.3240).

The contribution here is a source-connected EMK realization contract,
bounded exact checker, specified echo, dimension accounting and explicit
fault boundary for this project. Literature novelty of the fault statement
or its combination is not established. The next theoretical gate is to
derive the conditional bus couplings from an explicit material Hamiltonian
and quantify control, leakage, loss and total-resource cost against an
existing implementation. PH2/TVSP may constrain those controls and responses;
the present source results do not already derive them. No new experimental
run or hardware submission is required to inspect this mathematical result.
