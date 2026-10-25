# Readings to jets: learning local expansions from point readings

**Author: Monty. Status: exact module with proved statements, exact
witnesses and negative controls; no hardware, no quantum advantage for the
curvature task, no seam-calculus identity claimed.**

Module `native_relational_qc/jet_readings.py`, tests
`tests/test_native_jet_readings.py`, witnesses
`benchmarks/jet_readings_audit.py` writing `native_relational_qc/jet_readings/`.

## 0. The gap this fills, and what it does not fill

The self-learning branch (`codex/native-self-learning-v1-20261024`, commit
`bd79ac4`) trains a four-qubit parity circuit to classify the sign of the
selected native curvature `kappa = uv/324` of the cubic family

`U_{u,v}(s,w) = 10 s - 10 w + (2 s^2 + 2 s w + 5 w^2)/2 + (u s^3 + v w^3)/6`.

Its features are the first Hessian layer `u = (H_s)_11`, `v = (H_w)_22`,
supplied as numbers. The learner never takes a reading; it is handed a
derivative. Three questions follow, and this packet answers each exactly:

1. Can the learner obtain the first layer, and higher layers, from point
   readings of `H` alone, deciding where to read and how many readings it
   needs? Yes, within a declared polynomial family (Theorem J1), and the
   learner's stopping rule is a falsifiable hypothesis, never a certificate
   (Theorem J3 and the ghost energies).
2. Which part of the learned local description is the observer's and which
   is the system's? Under a constant linear change of chart the Hessian and
   its layers transform covariantly and the trained features `u, v` change,
   while `kappa` is invariant (Theorem J2). The existing frozen model, fed
   the same system through a sheared chart, drops from 64/64 to 38/58
   (negative control); the invariant read from the same jet stays at 58/58.
3. Does the quantum calculator read a layer that a classical reader cannot
   read as cheaply? For a *linear* phase layer, yes: one oracle query reads
   all `n` entries exactly with probability one, where any deterministic
   classical reader needs `n` readings (Theorem Q1; this is the
   Bernstein-Vazirani construction over `Z_M`, run exactly on the unchanged
   flat engine, not a new algorithm). For a quadratic layer the same
   single-query readout is not concentrated (Proposition Q2, negative
   control). The curvature task itself gains nothing quantum here: once the
   jet is read, `kappa` is a rational computed from it, and the circuit
   classifier is redundant (Section 5).

The comparison rules between frames used below are the ordinary transformation
laws of a symmetric bilinear form and its derivatives under a constant linear
chart change. They are not shown to be the Recognition Seam Calculus
observer or transport rules; no such identity is claimed or needed.

## 1. Objects

All quantities are exact rationals (`fractions.Fraction`) or exact elements
of the flat field `Q(zeta_M)`; nothing is rounded.

* A **declared energy** is a bivariate polynomial `U(s,v) = sum c_ij s^i v^j`
  of total degree at most 24, given by its coefficients. `cubic(u,v)` is the
  existing family. The **Hessian field** is `H(q) = nabla^2 U(q)`, a
  symmetric 2x2 polynomial matrix stored packed as `(H_11, H_12, H_22)`.
* A **reading** is `H(q)` at one point `q` chosen by the learner. The
  `Reader` serves readings from a declared energy, counts distinct readings
  against a budget, and fails closed (`ResourceLimit`) without a jet.
* A **jet of order `d` at base `p`** is the truncated expansion
  `H(p+delta) = sum_{|alpha|<=d} C_alpha delta^alpha`, with symmetric matrix
  coefficients `C_alpha`. `alpha! C_alpha = partial^alpha H(p)`. The first
  layer is `(C_(1,0), C_(0,1)) = (H_s, H_v)` at `p`.
* The **selected curvature** at `p` is read from an order-one jet:
  `A_i = H^-1 H_i / 2`, `F_sv = -[A_s, A_v]`, `kappa = (H F_sv)_12 / det H`,
  with the same connection as the constitutive adapter (NT-3 convention). The
  module recomputes it independently with rational arithmetic; the check
  `kappa(cubic(u,v)) = uv/324` for all 196 nonzero `(u,v)` in `[-7,7]^2`
  agrees with the identity stated in `SELF_LEARNING.md`.

## 2. Theorem J1 (exact reconstruction within a declared degree)

Let `H` be a polynomial matrix field of total degree at most `d`, let `p` be
a base point, and let `P` be a set of `m = (d+1)(d+2)/2` points whose monomial
design matrix `[(q-p)^alpha]_{q in P, |alpha|<=d}` is nonsingular (a
unisolvent design). Then the order-`d` jet of `H` at `p` is the unique
polynomial of degree at most `d` interpolating the readings `{H(q) : q in P}`,
and `fit_jet` returns it exactly.

*Proof.* Each entry of `H(p+delta)` is a polynomial of degree at most `d` in
`delta`, so it lies in the span of the `m` monomials and its coefficient
vector solves the linear system `D c = h` with `D` the design matrix and `h`
the readings of that entry. `D` is nonsingular by hypothesis, so the solution
is unique and equals the Taylor coefficient vector. Gaussian elimination over
`Q` is exact. The module additionally re-evaluates the interpolant at every
design point and raises if any reading is not reproduced. ∎

Consequences recorded as checks: for the cubic family the Hessian is affine,
so `d = 1`, three readings fix the first layer, and the reconstructed first
layer encodes to exactly the steps `16+2u, 16+2v` that the existing task
supplies by hand (64/64 on the held-out test grid). For declared energies of
degree 4 to 10 the learner stops at order `degree-2` with the exact jet
(42 random cases, degrees 2 to 8 of `U` with a fixed positive quadratic part).

**Design choice.** `next_point` picks, among candidate points, the one whose
design row has the largest exact squared component orthogonal to the span of
the rows already chosen (greedy maximal volume). A positive value proves the
candidate increases the rank, so the design reaches unisolvence whenever the
candidate set spans; collinear candidate sets are refused. This is a
conditioning heuristic for *where to read*, not an optimality theorem.

## 3. Theorem J2 (what transfers between observers)

Let two observers use charts related by `q = A q'` with `A` a constant
invertible rational 2x2 matrix, and let `U'(q') = U(A q')`. Then at
corresponding points:

(a) `H' = A^T H A` and `H'_j = sum_i A_ij A^T H_i A` for the first layer; more
generally every coefficient tensor of the order-`d` jet transforms by the
substitution `delta = A delta'` followed by conjugation `A^T (.) A`
(`Jet.transport`). These are covariant, not invariant: the features `u, v`
of the existing task change with the chart.

(b) `kappa' = kappa`.

*Proof of (b).* Write `X_i = H^-1 H_i`. Then
`H F_sv = -(H X_s X_v - H X_v X_s)/4 = -(H_s H^-1 H_v - H_v H^-1 H_s)/4`,
whose transpose is its negative since `H, H_i` are symmetric; so
`H F_sv = c J` with `J = [[0,1],[-1,0]]` and `c = (H F_sv)_12`. In the primed
chart `X'_j = A^-1 (sum_i A_ij X_i) A`, hence
`[X'_s, X'_v] = A^-1 (sum_{i,k} A_i1 A_k2 [X_i, X_k]) A = det(A) A^-1 [X_s, X_v] A`.
Therefore `H' F' = A^T H A det(A) A^-1 F A = det(A) A^T (H F) A = det(A) c A^T J A
= det(A)^2 c J`, using `A^T J A = det(A) J`. Finally `det H' = det(A)^2 det H`,
so `kappa' = det(A)^2 c / (det(A)^2 det H) = kappa`. ∎

The module checks (a) by comparing the transported jet with the jet of the
recomposed energy `U'` at `A^-1 p` (exact equality, 40 random pairs), and (b)
by exact equality of `kappa` (40 pairs, plus the test suite). Scope: constant
linear chart changes only. A nonlinear chart change adds second-derivative
terms of the chart to `H_i`, and the module refuses it rather than
transporting a jet by a law that has not been written down here.

**Negative control (observer dependence of the existing model).** Transport
the 64 test-grid jets through the shear `A = [[1,1],[0,1]]` and feed the
transported first layer to the frozen checkpoint `[32,0,0,32,0]` (fingerprint
`e9335f96...3e394`, reproduced exactly on this engine, Section 5): 6 cases
leave the encoding range, and the model is right on 38 of the remaining 58.
The sign of `kappa` read from the same transported jets is right on 58 of 58.
The trained features were readings in one chart; the label was an invariant.

## 4. Theorem J3 (a consistent order is a hypothesis) and ghost energies

`learn_jet` fits order `d = 0, 1, ...`, then takes fresh check readings and
stops at the first order whose truncated jet reproduces them. The reported
`status` is `consistent_at_order_d`, with `certificate: False`.

*Theorem J3.* For any finite set of points `P` (design and checks together)
and any declared energy `U`, there is a declared energy `U_g != U` whose
Hessian agrees with that of `U` at every point of `P`, so the learner returns
the same jet with the same status for both, while `H_g` and `kappa_g` differ
from `H` and `kappa` at points outside `P`.

*Proof.* Let `l_k` be a nonzero linear form vanishing at the `k`-th point of
`P` and put `U_g = U + c prod_k l_k^3`. Each factor vanishes to third order at
its own point, so the Hessian of the product vanishes at every point of `P`,
and every reading there is unchanged. The product is a nonzero polynomial, so
its Hessian is not identically zero, and `H_g != H` somewhere. ∎ (`ghost_energy`
builds this with `c = 1/1000` and directions cycling through `(1,0), (0,1),
(1,1), (1,-1)`; the audit checks, for each of the 64 test energies, that all
readings used by the learner coincide, that the learned jets and statuses
coincide, and that the order-one jet and `kappa` differ at `(1/41, -1/43)`.)

This is the finite-polynomial form of the earlier jet result JED-T5 (identical
jets of all orders at a point do not fix curvature with finite transport, in
the smooth class). Here the stronger finite statement holds trivially: finitely
many readings never fix the field between them. What makes the learner useful
is the *declared* family: Theorem J1 says that within degree at most `d` the
jet is exact, and Theorem J3 says that the degree hypothesis itself is only
ever falsified by a check reading, never certified. The module says both.

## 5. The existing classifier on this engine, and why it is redundant here

`parity_classifier` rebuilds the self-learning branch's four-qubit circuit
(`RY` as `S H P(theta) H S^dagger`, `CNOT(0,2), CNOT(1,2), CNOT(2,3)`, read
`q3`) on `PowerPhaseCircuit(4,64)` of this branch's dense flat engine and
applies the frozen first-layer checkpoint. Fed the first layer read from
readings, it predicts the label on 64/64 held-out test cases, matching the
`test` accuracy of 1 recorded in that branch's `qualification.json`.
Probabilities are also checked against an independent real-amplitude
evaluation of the same rotations (enclosure test).

Once the jet is read, `kappa` is a rational function of it (Section 1), exact
and chart-invariant. For this task the circuit learns a sign that the jet
already contains; it establishes no quantum resource. Said once, plainly: the
upgrade that matters for this learning model is the reading-to-jet step and
the invariant read from the jet, both classical and exact. The quantum
engine's own contribution is the different one in Section 6.

## 6. Theorem Q1 (one quantum query reads a linear layer)

Let `M = 2^b`, `n` registers of `b` qubits, and a hidden linear layer
`a in Z_M^n`. The phase oracle `O_a |x> = zeta_M^{a.x} |x>` is realized on the
flat engine as single-qubit phase gates: bit `j` of register `i` carries
`zeta_M^{a_i 2^j}`, written in the engine's `pK` gates by the binary expansion
of the exponent. The circuit `QFT^{-1 (x) n} O_a H^{(x) nb} |0>` reads `a`.

*Theorem Q1.* The outcome distribution is the point mass at `a`:
`Pr[read a] = 1` exactly.

*Proof.* `H^{(x) nb}|0> = M^{-n/2} sum_x |x>`; the oracle gives
`M^{-n/2} sum_x zeta_M^{a.x} |x> = (x)_i ( M^{-1/2} sum_{x_i} zeta_M^{a_i x_i} |x_i> )
= (x)_i QFT|a_i>`, and the inverse QFT of the Shor module returns `|a_i>` on
each register. ∎ The audit enumerates every layer for `(b,n)` in
`(3,1), (3,2), (2,3), (4,1), (2,4), (3,3)` and checks the exact point mass
(1 in `Q(zeta_M)`), 920 layers in all.

*Classical comparison (counting, not a witness).* A deterministic reader that
queries `f_a(x) = a.x mod M` at `k` points distinguishes at most `M^k`
hypotheses, so identifying `a in Z_M^n` needs `k >= n` readings; the quantum
circuit above uses one. This is the standard Bernstein-Vazirani separation
extended to `Z_M`; the engine executes it exactly. It says nothing about
noise, hardware or asymptotics beyond the enumerated sizes.

*Proposition Q2 (second layer, negative control).* For one register and the
oracle `zeta_M^{a x^2 + b x}` with `a != 0, M/2`, the same single-query readout
has every outcome probability strictly below 1 (audit: all such `(a,b)` for
`M = 4, 8, 16`, largest probability 1/2). For `a = M/2` the phase is linear
(`x^2 = x mod 2`) and `a+b` is read exactly. So the one-query reading is a
first-layer reading; a second layer is not read by this circuit. Shifted
queries that reduce a quadratic layer to a linear one are known in the
literature and are not developed here.

## 7. What the learner now does, end to end

```python
from fractions import Fraction as Q
from native_relational_qc.jet_readings import PolynomialEnergy,Reader,learn_jet,classify_first_layer

reader=Reader(PolynomialEnergy.cubic(3,-5))     # readings only; no derivative is handed over
result=learn_jet(reader,(0,0),max_order=3)      # chooses points, fits, checks, stops at order 1
jet=result['jet']                                # 7 readings for this family
jet.first_layer(), jet.curvature()               # ((3,0,0),(0,0,-5)), -5/108 = 3*(-5)/324
jet.transport(((1,1),(0,1))).curvature()         # -5/108: same system, other observer
classify_first_layer(jet)                        # existing frozen circuit, same label
```

Reproduce the witnesses with `python benchmarks/jet_readings_audit.py`
(writes `native_relational_qc/jet_readings/qualification.json` and its
`EXPECTED.sha256` over the content without timing fields).

## 8. Claims, non-claims, open

Proved here: J1, J2(a)(b), J3, Q1, Q2 as stated, each with the scope written
into the statement. Checked exactly, not proved: the identity `uv/324` on the
grid, the test-grid and sheared-chart counts, the random-family runs. Not
claimed: any correspondence with Recognition Seam Calculus rules; any speedup
for curvature classification; anything about physical readings, noise, or
devices. Open and not attempted: a transport law for nonlinear chart changes;
a one-query quantum reading of a second layer; using the record-conditioned
phase estimation of this branch as the "next reading" rule of the learner
(its correction `zeta_M^{e_t}` already depends on retained readings only, so
it is the natural place to connect, but no theorem about that connection is
offered here).
