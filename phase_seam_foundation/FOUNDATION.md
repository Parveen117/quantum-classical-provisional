# Phase–seam foundation v0.1

Author: Monty. Status: finite operational proposal and source audit.

The four supplied manuscripts motivate a phase/seam primitive, with an inner
product to be recovered rather than assumed. This implementation makes a
limited part of that program executable: oriented cuts, transport, a closure
sector, retained history, and an explicitly normalized readout. It uses integer
lifts and rational arithmetic, with no Hilbert space in the cell interpreter.
It does **not** derive these numbers from a pre-numeric cut, prove Hilbert
recoverability, or establish a physical quantum computer.

The original manuscripts are unchanged and are not copied into this repository.
[source_manifest.json](source_manifest.json) identifies the four reviewed byte
streams. Hashes identify sources; they are not certificates of their theorems.

## What is inherited, proved here, or proposed

| Ingredient | Source / status | Executable treatment |
| --- | --- | --- |
| Four phase modes with seam label | DE geometry manuscript | Four cyclic coordinates plus a positive rational Gamma |
| J(z) = i conjugate(z), J squared = identity | Time-tensor manuscript; valid algebra | Exact reflection, at axis index L/4 |
| Oriented family J_alpha | New extension of that cut | C_h(r) = h-r |
| Two cuts generate transport | Proved below from the new family | All one-bin translations are reachable |
| Gamma times its dual = 1 | DE invariant | Dual defined as 1/Gamma; preserved by construction |
| Finite phase closure | Stabilized identity manuscript | Exact predicate and optional enforced sign sector |
| Closure-preserving pair cut | New coupling proposal | Reflection plus a compensating reservoir-mode update |
| Geometric cost | Cost and time manuscripts | Exact schedule for explicitly chargeable cuts |
| Memory and winding | Source motivation; physical law unresolved | Ordered event records and algebraic lift quotients |
| Normalized probabilities | Missing finite rule in sources | New positive finite preparation and pushforward readout |
| Joint preparation/composition | New baseline assumption | Correlated classical preparations and independent products |
| Born rule / Hilbert recovery | Source axiom or claim, not supplied construction | Open; not inserted into the interpreter |
| Time-tensor equation / unique Eye | Unresolved source claims | Not used as an execution law |

## 1. Finite carrier and orientation

Let L be a multiple of four, 4 <= L <= 4096; the default is 64. A cell has

\[
\ell=(\ell_T,\ell_V,\ell_S,\ell_P)\in\mathbb Z^4,
\quad r_j=\ell_j\bmod L,\quad
\theta_j=2\pi r_j/L,\quad \Gamma\in\mathbb Q_{>0}.
\]

Gamma is a passive invariant label in v0.1. Its dual is defined as 1/Gamma.
No law identifying log(Gamma) with a periodic angle is assumed. A physical
calibration from Gamma to a readout axis remains missing. T/V/S/P are mode
labels here; no thermodynamic material realization is implied.

The bounded cell also retains a finite event ledger, a chargeable-cut count,
cost, and the next scheduled cost. The whole implemented state space is
finite under its integer, rational-bit, and event limits. This is a finite
discretization proposal, not a proof that a continuous or infinite tower can
be truncated without changing all its invariants.

For an oriented cut, propose

\[
J_\alpha(z)=e^{2i\alpha}\bar z,
\qquad \alpha=\pi h/L,
\qquad C_{j,h}(\ell)_j=h-\ell_j.
\]

The circle states have spacing 2pi/L, while cut **axes have spacing pi/L**.
At L=64 these are 5.625 degrees and 2.8125 degrees respectively. Ignoring this
half-grid axis requirement would restrict which translations are generated.
Axis h=L/4 recovers J(z)=i conjugate(z). The physical reflection axis is
defined modulo pi; h and h+L give the same wrapped map but different lift
conventions. Hardware must specify which path/lift it actually implements.

Direct substitution proves

\[
C_{j,h}^{,2}=I,\qquad C_{j,b}C_{j,a}=T_{j,b-a},
\qquad J_\beta J_\alpha z=e^{2i(\beta-\alpha)}z.
\]

Operator products act right to left; the API lists events chronologically.
These equalities concern carrier coordinates, **not erasure of the event tape
or refund of physical energy**. Different axes usually do not commute. For
L=8, initial phase 2, cuts 0 then 1 give phase 3; reverse order gives phase 1.
Both histories have two chargeable cuts and cost 3/2 with default scheduling.
Cost alone cannot identify their order or their output.

## 2. Closure and admissible coupling

For a fixed integer twist kappa, define the finite closure diagnostic

\[
u=\left(\sum_j\ell_j+\frac L4\kappa\right)\bmod L.
\]

The product of phase factors with the quarter-turn twist is +1 exactly when
u=0, and -1 exactly when u=L/2. Otherwise it is outside those two closure
values. This is a scalar identity test, not a derivation of dynamics,
curvature, a probability law, or quantization of physical holonomy.

`Config(sector=1)` or `sector=-1` enforces the chosen sign on initial and
successor states. The default `sector=0` exposes unrestricted kinematics.
Single-mode cuts, shifts, and resets can leave a closure sector and then fail
without a successor. A twist is a supplied fixed label here, not inferred
from the four lift quotients.

To make a closure-preserving primitive, introduce a reservoir mode s != j:

\[
B_{j,s,h}:\quad
\ell'_j=h-\ell_j,\qquad
\ell'_s=\ell_s+2\ell_j-h.
\]

Other coordinates stay fixed. The old value of ell_j is used in both updates.
Their sum is unchanged. Applying B twice returns both coordinates exactly.
Therefore B is an involution preserving either closure sign. Moreover,

\[
B_{j,s,b}B_{j,s,a}:\quad
(\ell_j,\ell_s)\mapsto(\ell_j+b-a,\ell_s-(b-a)).
\]

Thus two balanced cuts generate equal and opposite transport. This is the
new `pair_cut` / `pair_shift` coupling proposal, not a coupling law already
proved by the manuscripts and not evidence of entanglement.

The interpreter also supplies swaps and the explicitly proposed shear
ell_t -> ell_t + k(ell_c-a), c != t. Its inverse uses -k. A shear need not
preserve closure and is accepted in a constrained sector only if its actual
successor passes the sector check. All these maps are integer bijections on
the unbounded carrier; resource bounds make them partial operations.

In unrestricted kinematics, shifting every lift by delta, every readout and
shear reference by delta, and every cut index by 2delta preserves relative
outcomes. The absolute closure convention fixes an external phase origin:
an arbitrary common shift changes its phase sum by 4delta. We do not claim
that such a shift is a gauge symmetry of a fixed closure sector. A quotient
by global phase requires an additional specification.

## 3. Cost, memory, and finite execution

Write q in [0,1), c0 >= 0, both rational. After n chargeable cuts,

\[
D_n=c_0\frac{1-q^n}{1-q},\qquad
D_{n+1}-D_n=c_0q^n.
\]

For the source expression R/lambda times (1-exp(-lambda*n)), the corresponding
parameters are q=exp(-lambda) and c0=R(1-q)/lambda. The exact first increment
is **not R** in general. Rational q is a chosen exact parametrization; no
floating exponential is used in execution. q=0 is an allowed finite model
boundary, not the image of a finite positive lambda.

The sources also say a cut on its fixed seam costs nothing. Applying a
positive schedule to every attempted cut would contradict that statement.
Our **new accounting convention** counts only cuts that change the reflected
mode's wrapped phase: 2r_j != h modulo L. A `pair_cut` charges its primary
reflection under the same rule. The integer n therefore counts chargeable
cuts, not all events. This is an explicit modification, not an unnoticed
derivation from the source's raw cut count.

Read, reset, shift, shear and compensation costs are **not physically
budgeted** by this schedule. A zero ledger increment does not assert they
consume zero energy. D is dimensionless bookkeeping; no joule calibration,
Landauer comparison or physical energy saving follows. The code does not
identify D, its integral, the event ledger, and a time tensor.

Every successful event retains the operation, before/after snapshots, charge
flag and readout outcome. `verify_history` replays the supplied tape and
checks these values; it is a consistency verifier sharing the transition
implementation, not an independent theorem prover or cryptographic signature.
Tests compare the key algebra against direct formulas and exhaust finite
domains. Directly constructed certificate values need verification before use.

The lifts retain a quotient floor(ell_j/L) and a wrapped remainder. Going from
0 to L has unchanged phase and quotient +1. This is an **algebraic path
convention**. Endpoint phase readings alone cannot determine real winding;
hardware needs a path model and crossing observations. Reflections with the
same wrapped action can have different lift histories.

Default limits: |lift| and |operation parameter| <= 2^31-1; 1024 events per
cell; 4096 bits per rational numerator/denominator. Preparations allow 4096
atoms and 16 cells, with at most 64 readouts per query. These are configurable
reference bounds, not measured hardware capacities. Lift, cost, history,
closure, and ensemble failures return no successor/distribution. Immutable
inputs stay intact. A failing branch is never discarded to renormalize the
remaining population. Copying and replaying full histories is intentionally
simple and can take quadratic total work in tape length.

## 4. Measurement and composition: an explicit baseline

A preparation is a finite list of states with declared positive rational
weights summing **exactly** to one. A deterministic seam-reference readout is

\[
f_{j,a}(\ell)=(\ell_j-a)\bmod L,\qquad
P(y)=\sum_{\lambda:f(\lambda)=y}w_\lambda.
\]

This pushforward is nonnegative and sums to one because the readout fibers
partition the preparation. Joint readouts use the tuple of outcomes before
summing weights. Correlated preparations are allowed; independently prepared
systems compose by Cartesian product and product weights. These are added
classical probability assumptions, **not a derivation of the Born rule from
winding**, and not a claim that the complete source framework is classical.

`read` records the current phase without changing its carrier. `reset`
records that same outcome and replaces the selected lift by the reference.
Different input lifts then give the same reduced state; the tape retains the
lost preimage. This implements a declared classical instrument. It does not
establish nondisturbing access to an unknown quantum state or a physical
measurement backaction law. Conditioning on a recorded outcome could be
defined by ordinary Bayesian restriction, but no selective instrument or
postselection API is included in this version.

Local operations/readout on one cell leave the other cell's unconditioned
distribution unchanged. For any setting-independent shared preparation and
binary local responses A0,A1,B0,B1 in {+1,-1},

\[
s_\lambda=A_0(B_0+B_1)+A_1(B_0-B_1)\in\{-2,2\}.
\]

Consequently |sum(w_lambda*s_lambda)| <= 2. Local stochastic responses can
also be included in a larger shared variable, giving the same bound. Retained
local histories do not evade it when those assumptions remain true. The
provided half-circle binning is just one local response.

This proves a boundary of **this chosen operational completion**: it cannot
reproduce Bell-violating quantum correlations under the stated conditions.
The 16 binary assignments and all 4096 setting quadruples for a grid-8
correlated example are checked. The general proof is above, not inferred
from that example. Bell violation alone would not establish a universal
quantum computer; it is a relevant joint-state compatibility target. An
experimental reference is [Hensen et al., 2015](https://arxiv.org/abs/1508.05949).
No desired Bell table or quantum probability is hard-coded into the cell.

## 5. A conditional hardware obstruction for the cut

The phase reflection is a valid map on the declared classical coordinates.
It must not silently be promoted to universal conjugation of unknown quantum
amplitudes. If that identification is made in a proposed Hilbert recovery,
J_alpha induces transposition of the density matrix (up to a unitary).
Transposition on one half of a Bell state produces half the swap matrix, with
expectation -1/2 on the normalized antisymmetric vector. Thus it is not a
completely positive deterministic local quantum channel on arbitrary inputs.

`qualification.transpose_guard` checks this negative witness using exact
rationals, separately from the native interpreter. This does not prohibit a
restricted-state encoding or classical phase reflection. It identifies a
condition any recovery map and physical cut implementation must resolve.
The related antiunitary-operation boundary is discussed by
[Buzek, Hillery and Werner](https://arxiv.org/abs/quant-ph/9901053).

## 6. Source claims that still need repair

| Claim / gap | Reason it is not used as a proved execution rule |
| --- | --- |
| Nonzero commutator of cut/join built from one fixed G | Both are sums of exp(+G/2) and exp(-G/2), so they commute wherever the products are defined. At G=0 the commutator is zero, contradicting the asserted nonzero RHS. Oriented cuts here are a different, explicitly introduced family. |
| Saturating cost implies a unique Eye attractor | Finite D(infinity) leaves exp(-D(t)) exp(i omega t) with nonzero limiting magnitude and continuing rotation for nonzero omega. Additional dissipative dynamics and a stability proof are needed. |
| kappa=0 implies Theta=0 while closure RHS is +/-R/lambda | Substitution gives zero on the left and nonzero on the right for positive R,lambda. Types, boundary terms or the asserted implication must change. |
| Probability from absolute winding derivative | A base measure, total mass, preparation dependence and joint/instrument laws are missing. Uniform winding alone does not specify arbitrary Born probabilities. |
| Gamma=exp(gamma) makes the seam a circle | exp maps real gamma to positive Gamma; a circle requires a quotient plus retained lift or another specified map. |
| Holonomy quantization and tensor uniqueness | Need coordinate domains, allowed loops/defects, typed equations, boundary/gauge conditions and actual proofs. The extra phi/Sigma coordinates in the one-form are not specified by the original four phases alone. |
| Infinite shift has a unique all-zero fixed point | Every constant sequence is fixed by a plain shift. Extra constraints or a different evolution are required. |

The stabilized finite phase identity remains useful as a checked constraint;
it does not supply the missing interaction, state preparation or measurement
theorems. Event order in this prototype is not a proof of emergent physical
time. There is no 2056-qubit capacity implication from having cyclic modes.

## 7. Reproduce and next mathematical target

From the repository root:

```bash
python -m phase_seam_foundation
python benchmarks/phase_seam_audit.py
```

The second command runs the dedicated foundation tests and existing calculator
smoke suite, then saves [qualification.json](qualification.json) and
[test_results.txt](test_results.txt), including code/test/source-manifest hashes.
It does not rerun the previous full 302-test native suite or Shor timing audit.
No quantum calculator backend was replaced or relabeled by this proposal.

The next mathematical target is a **native joint-state and measurement law**:
define preparations, admissible interactions, outcomes and sequential state
updates; prove normalization and composition consistency; specify how an
inner product/Born rule is recovered or give a quantitative alternative;
check Bell correlations and absence of observable signaling under the stated
experimental assumptions. That law must also explain how each physical cut
acts on a subsystem and its correlations. A PC emulation can test the resulting
predictions, but cannot supply the missing physical postulate by itself.
