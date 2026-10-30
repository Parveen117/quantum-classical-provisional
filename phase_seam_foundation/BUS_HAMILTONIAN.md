# Centered bus Hamiltonian, finite-level sensitivity and dispersive bounds — v0.16

**Author: Monty.** The [v0.15 EMK bus gate](WEYL_BUS.md) now has an explicit
effective interaction schedule and a quantitative bridge from a microscopic
Jaynes–Cummings (JC) model. The calculation retains bare-state dressing error,
nonlinear energy shifts and the transition out of the highest bus code level.
It also proves why ideal bus return does not confer first-order immunity to
continuous pulse-area errors.

These are mathematical results under the declared Hamiltonians. No material
coupling, Fourier pulse, noise rate or device fidelity is supplied by this
calculation. The current single-photon SiN layout is not reclassified as a
two-carrier quantum processor.

## 1. Collaboration reuse

The collaboration branch `native-relational-qc-pow2-field-20261024` contains
the flat exact field in commit
[`f2b969769e5c9fc5c3009ce33ddf2dd9095cb0b4`](https://github.com/Parveen117/quantum-classical-provisional/commit/f2b969769e5c9fc5c3009ce33ddf2dd9095cb0b4).
This revision copies `native_relational_qc/cyclotomic_pow2.py` **unchanged**;
its Git blob is `43aa0a7918598364e69fe20def96e0be2bf3a978`.
It reuses exact products, conjugation, rational division, roots of unity and
the outward Machin enclosure of pi. No second field engine is written.

This matters even at d=64: centering the generator gives half-integer
eigenvalues, so individual ideal pulses need `Q(zeta_128)`, although the
closed loop is still exactly in the earlier `Q(zeta_64)`. The source branch's
calculator registration and wider Shor changes are not imported by this
adapter; its Shor timings are not claimed as locally reproduced results.
Matrix exports here stop at d=64 and do not inherit a 4096-level matrix claim.

## 2. One conditional interaction class supplies both kicks

Let `c=(d-1)/2` and define

\[
Q_0=\operatorname{diag}(0,1,\ldots,d-1)-cI,\qquad
F_{jk}=d^{-1/2}e^{-2\pi i jk/d},\qquad P_0=FQ_0F^*.
\]

The negative-exponent Fourier convention gives `X=F Z_C F*`. Both generators
are Hermitian with norm c. The midpoint c minimizes `||N-cI||` among scalar
centerings of the equally spaced spectrum. The proposed conditional drives
are

\[
H_Q^{(j)}(t)=-\hbar\kappa_j(t)Z_j\otimes Q_0,
\qquad H_P^{(A)}(t)=-\hbar\kappa_A(t)Z_A\otimes P_0.
\]

Only Q-type coupling is needed if uncontrolled bus Fourier gates are also
available. In execution order a P pulse is `F*, Q pulse, F`.
For integrated area `alpha=2 pi a/d`,

\[
e^{i\alpha Z_AP_0}=e^{-i\alpha cZ_A}X^{aZ_A},\qquad
e^{i\beta Z_BQ_0}=e^{-i\beta cZ_B}Z_C^{bZ_B}.
\]

The extra local phases cancel between each kick and its inverse, so the
four-kick sequence still implements exactly
`exp(i 2 pi ab/d Z_A Z_B) tensor I_bus`. The existing native EMK basis-change
identity remains unchanged. Local phases must be kept for individual pulses;
discarding them before a general sequence is not valid.

`BusDesign.schedule()` explicitly counts four conditional interactions and
four bus Fourier transforms per bare rectangle. The identical-half echo
has eight interactions, eight Fourier transforms and four data X flips.
All are operator targets. In particular, a Fourier transform of selected
oscillator Fock levels is not supplied by ordinary free oscillator evolution
or by a classical heater setting.

## 3. Continuous area-error obstruction at an ideal closed loop

Use the same inverse-matched strengths in the return legs and write

\[
W(\alpha,\beta)=e^{-i\beta Z_BQ_0}e^{-i\alpha Z_AP_0}
e^{i\beta Z_BQ_0}e^{i\alpha Z_AP_0}.
\]

At `alpha=2 pi a/d`, `beta=2 pi b/d`, each data branch is a scalar on the
bus. For data eigenvalues s,t in {+1,-1}, differentiating the actual word
gives the **right-relative** derivatives

\[
(\partial_\alpha W)W^*=iK_\alpha,
\quad K_\alpha=s(P_0-Z_C^{-bt}P_0Z_C^{bt}),
\]
\[
(\partial_\beta W)W^*=iK_\beta,
\quad K_\beta=t(X^{-as}Q_0X^{as}-Q_0).
\]

Their exact spectra are especially simple:

\[
K_\alpha(p)=s\,[p-(p-bt)_{\bmod d}],\qquad
K_\beta(k)=t\,[(k+as)_{\bmod d}-k].
\]

K_alpha is diagonal in the P basis and K_beta in Q; these are not a common
joint spectrum. Each has zero trace. For `0<a,b<d`, their operator norms
across all data branches are `max(b,d-b)` and `max(a,d-a)` respectively.
At the earlier d=64,a=2,b=4 target the norms are **60 and 62 per radian**;
at d=8,a=b=1 they are both **7 per radian**. These compare absolute area
errors, not an unspecified common relative calibration error.

For `a>0`, one branch of the Q response is explicitly

\[
K_\beta=t\left(aI-d\sum_{k=d-a}^{d-1}|k\rangle\langle k|\right)
\quad(s=+1).
\]

The boundary projector is essential: replacing the finite cyclic shift by
an unbounded canonical translation would delete it and give the wrong
sensitivity. It is a finite-clock boundary effect, not a newly identified
thermodynamic or spacetime curvature.

**Obstruction.** Universal first-order bus independence under alpha error
would require each branch's K_alpha to be scalar. Since its trace is zero,
that scalar must vanish. The displayed spectrum vanishes only for `b=0 mod d`.
The analogous beta condition forces `a=0 mod d`. Either condition removes
this rectangle's entangling phase. Thus a nontrivial entangling rectangle of
this family has bus-dependent first-order error in both continuous area
directions, even when the inverse pulses have matched errors. This does not
rule out composite sequences, other encodings or a specified bus state.

## 4. Conditional finite-error bound

For the implemented centered finite-generator schedule, let epsilon_l be an
absolute pulse-area error bound in radians, f_l the operator error of each
bus Fourier transform, x_l that of each data flip, and v a dimensionless
bound on the integrated norm of other Hamiltonian perturbations divided by
hbar. With no double-counting, telescoping unitary products and Duhamel's
formula give

\[
\|\widetilde U-U\|\leq
\min\!\left(2,\ c\sum_l\epsilon_l+\sum_l f_l+\sum_l x_l+v\right).
\]

The pure area estimate uses
`||exp(i epsilon Z G)-I|| <= |epsilon| ||G||`, which holds for finite real
epsilon; it is not a first-order approximation. The reduced-data trace
distance is bounded by the same raw expression capped at 1. With a fixed
bus initial state independent of the data input, this also bounds half the
diamond distance of the induced data channels. It does not define a data
channel for arbitrary input-dependent initial data–bus correlations.

`implementation_bound()` requires every per-operation bound, including
explicit zeros. Its output is conditional on these bounds and closed-system
unitary dynamics. Dissipation, photon loss, unbounded perturbations and
statistical confidence are not inferred. The v0.13 optical observer does
not already measure these new interaction errors.

## 5. Microscopic JC bridge with a retained remainder

Consider one ideal two-level data carrier coupled to an oscillator:

\[
H_{\rm JC}/\hbar=\omega_c N+\tfrac{\omega_q}{2}Z
+g(\sigma_+a+\sigma_-a^*),\qquad \Delta=\omega_q-\omega_c>0.
\]

This is a declared rotating-wave model. The input code uses oscillator
levels 0 through d-1. In excitation block m=1,...,d, the basis
`(|e,m-1>, |g,m>)` has a common free energy plus

\[
B_m=\begin{pmatrix}\Delta/2&g\sqrt m\\g\sqrt m&-\Delta/2\end{pmatrix},
\quad \operatorname{spec}(B_m)=\left\{\pm\tfrac12\sqrt{\Delta^2+4g^2m}\right\}.
\]

The m=d block is included: `|e,d-1>` couples to `|g,d>`, outside the nominal
bus code. No d-level truncation is used to hide that transition. The ground
vacuum is an additional uncoupled exact state.

The dispersive diagonal target is

\[
H_{\rm disp}/\hbar=\omega_cN+\tfrac{\omega_q+\chi}{2}Z
+\chi ZN+\tfrac\chi2 I,\qquad \chi=g^2/\Delta.
\]

Tracking/compensating its free, Lamb, global and local centering phases leaves
`+hbar chi Z Q0`. These compensation operations are required controls, not
automatically absent terms. A positive-chi pulse produces a negative angle
in the earlier `exp(i angle Z Q0)` convention. For a positive requested angle,
`jc_schedule()` uses data X, that negative-angle pulse, data X. In the literal
unoptimized schedule this adds **four sign-reversal X gates** per rectangle.
The bare JC schedule therefore has four interactions, four Fourier gates,
four sign-reversal X gates and four phase-compensation operations. The echo
has eight interactions, eight Fourier gates, twelve X gates total and eight
compensations. Possible control optimizations are not assumed in those counts.

We can bound the JC approximation without assuming dressed-state preparation.
Put `r=|g/Delta|` and `tau=Delta t`. The rotation diagonalizing B_m has angle
`eta_m=atan(2r sqrt(m))/2`, so `||D_m-I|| <= r sqrt(m)`. Taylor's remainder,
using the bounded second derivative of sqrt(1+x) for x>=0, gives

\[
0\leq\frac{\Delta}{2}+\frac{g^2m}{\Delta}
-\frac12\sqrt{\Delta^2+4g^2m}
\leq \frac{g^4m^2}{\Delta^3}.
\]

Conjugation by D_m and a unitary exponential difference then yield, on the
entire input code including its possible outside output,

\[
\|(U_{\rm JC}-U_{\rm disp})P_{\rm code}\|
\leq\min(2,\ 2r\sqrt d+\tau r^4d^2).
\]

The first term keeps the bare/dressed basis mismatch; the second keeps the
nonlinear spectral shift. For a kick of magnitude `|alpha|=2 pi |a|/d`,
`tau=|alpha|/r^2`, and the bound becomes

\[
\epsilon_{\rm JC}\leq\min(2,\ 2r\sqrt d+|\alpha|r^2d^2).
\]

The code makes this a rational upper enclosure using `ceil(sqrt(d))` and
the reused field module's outward enclosure of pi. It does not replace sqrt
or pi by an unchecked floating-point decimal. The inequality holds for all
r>0, although it is useful as a small-error bound only in an appropriate
dispersive regime. It is not a bound for multilevel transmons or the full
non-rotating-wave Rabi model.

For multiple pulses, use the telescoping expansion with an actual unitary
suffix and an ideal prefix. Every ideal prefix remains in the code; thus
the **input-code-restricted** bounds above suffice even though an actual
pulse may leak outside. Add the explicit Fourier, X, phase-compensation,
area and other Hamiltonian error bounds. `jc_gate_bound()` returns the
resulting input-code operator bound, reduced-data trace-distance bound and
code-escape probability bound `min(1,epsilon_total^2)`.

This supplies a conditional microscopic path to the assumed interaction.
It does not derive an oscillator Fock Fourier gate, guarantee isolation of
the unaddressed data qubit, or account for resonator loss and qubit relaxation.
Those are separate terms or control assumptions.

## 6. Explicit cost and accuracy trade-offs

With `||H_effective||/hbar <= G` for each centered conditional interaction,
its nominal minimum duration at that bound is `c |angle|/G`. The following
table exhausts integer strengths in this signed schedule and minimizes the
sum of their absolute values. Fourier/local gate durations are additional.

| Bus d | Bare CZ-equivalent (a,b) | Bare conditional time, in pi/G | Identical-half echo (a,b) | Echo conditional time, in pi/G |
| --- | --- | --- | --- | --- |
| 8 | (1,1) | 7/2 | unavailable | — |
| 16 | (1,2) | 45/8 | (1,1) | 15/2 |
| 32 | (2,2) | 31/4 | (1,2) | 93/8 |
| 64 | (2,4) | 189/16 | (2,2) | 63/4 |

This favors d=8 for the bare primitive and d=16 for the specified echo under
this effective-generator budget. It is not an architecture-independent
quantum speed limit, measured device speed or comparison at fixed raw chi.
The d=64 echo's (2,2) choice improves on v0.15's valid (1,4) example within
this cost convention, without changing its intended entangling phase.

A separate declared JC example illustrates the cost of improving the
approximation. For the bare d=8,a=b=1 gate, with all additional control
bounds set explicitly to zero:

| r=g/Delta | Conservative total operator/trace bound (approx.) | Conditional Delta*T, excluding local/Fourier gates |
| --- | --- | --- |
| 1/100 | 0.260107 | 10,000 pi |
| 1/1000 | 0.024202 | 1,000,000 pi |
| 1/2000 | 0.012051 | 4,000,000 pi |

Displayed error decimals are rounded upward; the manifest stores rational
bounds. They are upper bounds, **not predicted infidelities or measurements**.
Halving r multiplies normalized duration Delta*T by four. At fixed Delta
that also multiplies time by four; changing Delta at fixed g has a different
time scaling. Dissipative errors can grow during a longer gate and are not
included in this example.

## 7. Verification, lineage and open assumptions

Run `python benchmarks/bus_hamiltonian_audit.py`. Exact checks cover Fourier
unitarity, generator conjugation, the finer phase field, all 256 d=64 nominal
basis columns against v0.15, and every column of the d=8 bare and d=16 echo
schedules, including literal JC sign reversals. Independent continuous
complex Hamiltonians check the analytic derivatives and finite-error bound.
High-precision square roots and exact JC excitation blocks check the
microscopic remainder, including m=d. Numerical reference checks are model
checks; the bound itself follows from the stated inequalities.

The audit also reruns the v0.15 bus and existing joint-algebra tests, records
the unchanged collaboration source blob, and verifies earlier source hashes.
It does not rerun the collaborator's complete flat-field/calculator/Shor suite
or the old CAD/observer suites. The calculator's registered backends and all
previous implementation files remain unchanged.

The conditional-spin Hamiltonian/Fourier construction has known precedent:
Proctor, Dooley and Kendon, [arXiv:1402.6674](https://arxiv.org/abs/1402.6674),
Section III.3, Eqs. (30)–(33). The JC and dispersive models are established
quantum-optics physics; see Blais et al., [*Circuit Quantum Electrodynamics*](https://arxiv.org/abs/2005.12667),
Rev. Mod. Phys. **93**, 025005 (2021). No priority claim is made for those
models or the generic norm-bound techniques.

Closed here: exact effective Hamiltonian-to-gate mapping, continuous
finite-level sensitivity, literal control accounting, and a bare-input JC
approximation bound composed through the gate. New assumptions: the JC/RWA
microscopic model, controlled coupling intervals, phase compensation, isolation
of the other data carrier, and finite-code Fourier/local operations with
declared errors. Still open: their material implementation, dissipative
budgets, scalable architecture and evidence of an advantage over existing
hardware. PH2/TVSP response structure is not silently promoted into any of
these interaction or control assumptions.
