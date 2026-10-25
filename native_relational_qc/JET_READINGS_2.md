# Readings to jets, part 2: the Hessian metric, enclosure readings, and a second layer

**Author: Monty. Status: exact modules with proved statements, exact
witnesses and negative controls; no hardware, no probabilistic noise model,
no seam-calculus identity claimed.** Continues `JET_READINGS.md` (part 1).

Modules `native_relational_qc/hessian_metric.py`, `enclosure_learner.py`,
`layer_queries.py`; tests `tests/test_native_jet_readings2.py`; witnesses
`benchmarks/jet_readings2_audit.py` writing `native_relational_qc/jet_readings/qualification2.json`.

## 0. What part 2 settles

1. **What the selected curvature is.** The constitutive adapter's selected
   connection `A_i = H^-1 H_i / 2` is the Levi-Civita connection of the
   Riemannian metric `g = nabla^2 U`, and `kappa` is its Gaussian curvature
   (Theorem J5). This explains part 1's Theorem J2: a Hessian metric is an
   affine-invariant structure, so `kappa` is invariant under affine observer
   changes (J2) and not invariant under nonlinear charts in general (J6).
   Under a nonlinear chart change `kappa` changes in general, can change
   sign, and the transported jet needs one extra datum, the gradient at the
   base (Theorem J6, with exact counterexamples). This is the observer rule
   for nonlinear frames: Hessian jet plus gradient transfer, with the chart's
   Taylor polynomial to degree `d+2` as the correction known in advance; for
   `kappa` (order `d = 1`) that is the chart's second and third derivatives,
   and a chart with zero Hessian at the base can still flip the sign through
   its third derivatives (J6(d')).
2. **Learning from readings that carry a declared width.** When each reading
   is an exact interval containing the truth, the learner's design choice
   has an exact consequence: coefficient width equals a design factor times
   reading width (Theorem E1), and for three-point designs the factors are
   `2 Dv/|det D|` and `2 Ds/|det D|` with a lower bound `1/R` inside a box of
   half-side `R`, attained by corner designs; a larger `|det D|` alone does
   not mean a smaller width, and a higher jet order cannot help (Proposition
   E2). `kappa` receives a valid enclosure whose numerator range is taken
   over the admissible readings themselves, which is exact (Proposition E3);
   its sign is certified only when zero is excluded, and the learner reports
   what would help when it is not. The exact supremum half-width at which the
   sign is still certified is computed, not bracketed: `1/13` for the 64-case
   grid on the learner's design, attained by an admissible reading set whose
   interpolant is the Hessian jet of a cubic with `kappa = 0`, so no sound
   certifier of any kind can do better there (Theorem E4). All of this is
   worst-case arithmetic on declared inputs, not statistics.
3. **A second layer by shifted queries.** On the unchanged flat engine, `2n+1`
   uses of a quadratic phase oracle over `Z_M^n`, `M = 2^b`, identify the
   oracle's function class exactly (Theorem Q3). The identification class is
   itself a theorem (`x^2 = x mod 2` makes the quadratic part defined only
   mod `M/2`). The counting lower bound for deterministic classical readers
   is `ceil(n(n+1)(b-1)/(2b) + n)`, but the exact deterministic classical
   complexity is `n(n+3)/2` for every `M >= 4` (Theorem Q3(v), proved by
   duality and Nakayama's lemma, attained by a nonadaptive reader), so the
   quantum count, counted on the executed circuits, is below the classical
   one from `n = 3` on (`7` against `9`), ties at `n = 2` and loses at `n =
   1`; fewer than `n` shifts cannot read the quadratic part (Q3(vi)).

## 1. Theorem J5 (selected connection = Levi-Civita; kappa = Gaussian curvature)

Let `U` be a declared energy and `g_ij = partial_i partial_j U = H_ij` positive
definite at the point. Then in the coordinate frame

(a) `Gamma^k_ij = (H^-1 H_i / 2)^k_j = (A_i)^k_j`;

(b) `R(d_s, d_v) = d_s A_v - d_v A_s + [A_s, A_v] = -(1/4)[X_s, X_v] = F_sv` with
`X_i = H^-1 H_i`;

(c) `K = g(R(d_s,d_v) d_v, d_s) / det g = (H F_sv)_12 / det H = kappa`.

*Proof.* (a) `Gamma^k_ij = g^{kl}(d_i g_jl + d_j g_il - d_l g_ij)/2 =
g^{kl}(U_ijl + U_jil - U_lij)/2 = g^{kl} U_ijl / 2 = (H^-1 H_i)^k_j / 2`, by total
symmetry of third derivatives. (b) With `(A_i)^k_l = Gamma^k_il`, the
curvature endomorphism is `R(d_i,d_j) = d_i A_j - d_j A_i + [A_i, A_j]`.
Using `d_s(H^-1) = -H^-1 H_s H^-1` and `H_sv = H_vs`,
`d_s A_v - d_v A_s = (-X_s X_v + X_v X_s)/2 = -[X_s,X_v]/2`, while
`[A_s,A_v] = [X_s,X_v]/4`. The sum is `-[X_s,X_v]/4 = F_sv`. (c) In two
dimensions `K = R_1212 / det g` with `R_1212 = g(R(d_1,d_2) d_2, d_1) = g_1k
R^k_2 = (H F_sv)_12`. ∎

**Closed form.** Writing `(E,F,G) = (U_ss, U_sv, U_vv)` and the cubic form
`T = (U_sss, U_ssv, U_svv, U_vvv)`, the second-derivative terms of Brioschi's
formula cancel for a Hessian metric (`E_vv = F_sv = G_ss = U_ssvv`) and

`kappa = K = [G(U_ssv^2 - U_sss U_svv) + E(U_svv^2 - U_ssv U_vvv) + F(U_sss U_vvv - U_ssv U_svv)] / (4 (EG - F^2)^2)`.

So `K` depends on the order-one Hessian jet only, which is why the adapter's
one-layer reading suffices; for `cubic(u,v)` this is `F u v / (4 * 81) = uv/324`.
(`cubic_form_numerator` in `enclosure_learner.py` is this expression.)

The module computes `K` twice more, independently of the adapter's algebra:
through Christoffel symbols and the Riemann tensor (`gaussian_curvature_riemann`,
derivatives of `Gamma` taken exactly by the quotient rule on the polynomial
metric) and through the Brioschi formula (`gaussian_curvature_brioschi`). All
three agree exactly on 120 random polynomial energies of degree 3 to 7 at
random rational points and on the 64 cubic test-grid cases, where all equal
`uv/324`. The sign convention is the standard one (a round sphere has
`K > 0`), fixed by the agreement with Brioschi.

So the label the existing classifier learns is the sign of the Gaussian
curvature of the energy's Hessian metric. That is a geometric invariant of the
affine structure in which `U` is declared, nothing more and nothing less.

## 2. Theorem J6 (nonlinear observer change)

Let `phi` be a polynomial chart with `phi(p') = p` and invertible Jacobian
`J` at `p'`, and `U'(q') = U(phi(q'))`. Then

(a) `H'(q') = J(q')^T H(phi(q')) J(q') + sum_k (d_k U)(phi(q')) Hess(phi^k)(q')`.

(b) The order-`d` Hessian jet of `U'` at `p'` is determined by the order-`d`
Hessian jet of `U` at `p`, the gradient `nabla U(p)`, and the Taylor polynomial
of `phi` at `p'` to degree `d+2`; and it is not determined without the gradient.

(c) `kappa` is not invariant: for `cubic(3,-5)` at the origin and
`phi(s',v') = (s' + v'^2/2, v')`, `kappa = -5/108` becomes `-22/841`; with the
same chart and the linear terms of `U` removed (zero gradient at the base) it
becomes `-7/81`; for `cubic(1,1)` and `phi(s',v') = (s', v' - v'^2/4)`,
`kappa = 1/324 > 0` becomes `-1/1444 < 0`.

*Proof.* (a) is the chain rule applied twice. (b) The degree-`(d+2)` Taylor
polynomial of `U'` at `p'` is the degree-`(d+2)` truncation of the composition
of the degree-`(d+2)` Taylor polynomial of `U` at `p` with `phi(p'+eps) - p`,
which has no constant term; truncated composition only needs `phi` to degree
`d+2`. The Taylor polynomial of `U` to degree `d+2` is its value, its gradient,
and the part of degree 2 to `d+2`; the last is determined by the Hessian jet
because second differentiation is injective on polynomials with no affine
part (`energy_from_jet` integrates `H11` for monomials of `s`-degree at least
two, `H22` and `H12` for the rest, and then checks the two remaining routes,
so a triple of coefficient tensors that is not a Hessian jet is refused). The
value drops out of every Hessian. For necessity of the gradient: `U` and
`U + l` with `l` linear have the same Hessian field, and `(U+l)' - U' = l o phi`
has Hessian `sum_k l_k Hess(phi^k)`, nonzero when `phi` is nonlinear. (c) is
an exact computation, reproduced by `transport_chart` and by direct
recomposition of the energy (40 random quadratic charts in the audit; the
transported jet equals the jet of the recomposed energy in every case, the
gradient changed the result in every case, `kappa` changed in 34 cases and
changed sign in 14; in the remaining 6 the transported Hessian was not positive
definite, so `kappa` was undefined there). ∎

(d) *Any sign at a critical base.* Let `nabla U(p) = 0`, `H = H(p)` positive
definite, and `phi(p' + delta') = p + delta' + Q(delta')` with `Q` quadratic,
`Q^k(delta') = Q^k_ab delta'^a delta'^b / 2`. Then `H'(p') = H`, and the cubic
form shifts by `T' = T + S(Q)`, `S(Q)_abc = sum_k (H_kc Q^k_ab + H_kb Q^k_ac +
H_ka Q^k_bc)`. The linear map `S` from the six-dimensional space of `Q` onto the
four-dimensional space of symmetric cubic forms is surjective (`Q^k_ab =
(H^-1)^kc D_abc / 3` gives `S(Q) = D`), so by the closed form of J5 every target
`T*` and hence every sign of `kappa'` is reachable by a quadratic chart; e.g.
`T* = (0,0,1,0)` gives `kappa' = E / (4 det H^2) > 0` and `T* = (t,0,1,0)` with
`t > E/G` gives `kappa' < 0`. Explicit exact instances: the zero-gradient
`cubic(3,-5)` with `phi = (s' + 2v'^2, v')` goes from `-5/108` to `+29/324`
with `H'(0) = (2,1,5)`; `cubic(3,-5)` with its gradient `(10,-10)` and `phi =
(s' - s'v'/5, v')` goes to `+421/8100` with `H'(0) = (2,-1,5)`; the flat energy
`(2s^2 + 2sv + 5v^2)/2` (`kappa = 0` everywhere) acquires `kappa'(0) = 8/81`
under `phi = (s' + v'^2, v')`. Along the one-parameter family `phi_c = (s' +
c v'^2, v')` applied to `cubic(3,-5)` with its gradient, `kappa'(c) = (-208c^2 -
42c - 15) / (4(9 + 40c)^2)` is negative for every admissible `c` (discriminant
`42^2 - 4*208*15 < 0`), so that family never flips the sign; the `s'v'` term
does. (The two-dimensional formulas `H'(p') = H + sum_k g_k Q^k` and `T' = T +
S(Q)` hold for `J(p') = I` and exactly quadratic `phi`; for general `phi` use
`transport_chart`.)

(d') *Third derivatives of the chart act on `kappa` through the gradient.*
`phi = (s' + t v'^3, v')` has `J = I` and `Hess(phi^k) = 0` at the base, so
`H'(0) = H` exactly and the order-0 correction of (a) vanishes; yet for
`cubic(3,-5)` with its gradient `(10,-10)` the first layer moves, `H'_v =
(0,0,-5+60t)`, and `kappa' = (-15 + 180t)/324`: `25/756 > 0` at `t = 1/7`
(sign flipped from `-5/108`), `0` at `t = 1/12`, `-25/108` at `t = -1/3`.
With zero gradient the same chart leaves the order-1 jet unchanged. So the
correction for `kappa` is not the chart's Hessian alone: it is
`sum_k (d_k U) d^3 phi^k` as well.

*Not every nonlinear chart moves `kappa`.* `S` has rank 4 on the six
coefficients of `Q`, so at a critical base a two-parameter family of genuinely
nonlinear quadratic charts leaves the whole order-1 jet, hence `kappa`,
unchanged: for `H = (2,1,5)` the nullspace is spanned by `phi = (s' - s'^2 -
5s'v', v' + 2s'^2 + s'v')` and `phi = (s' + s'^2 + (9/2)s'v' - (5/2)v'^2,
v' - 2s'^2 + (1/2)v'^2)`; the zero-gradient `cubic(3,-5)` keeps `kappa =
-5/108` under both (exact; with a nonzero gradient the same charts do act).
J6 is therefore "not invariant in general", not "changed by every nonlinear
chart".

*What `phi` must be known to.* The order-`d` Hessian jet in the new chart needs
`phi` to order `d+2` when the gradient is nonzero and to order `d+1` when it
vanishes (adding `t (v' - v'_0)^{d+2}` to `phi^1`, with `v'_0` the base's
second coordinate, shifts exactly `C'_(0,d)` by `(0,0,(d+2)(d+1) t g_s)` and
nothing else of order at most `d`; at the origin this is `t v'^{d+2}`, and
(d') is the case `d = 1`).

Why this does not contradict J5: `g' = Hess U'` is not the pullback `phi^* g`.
The Hessian of a function is a tensor only with respect to a flat affine
connection; a nonlinear chart changes that connection, so `g'` is a different
metric with, in general, a different curvature. The Hessian-metric structure
is affine-invariant, and J2 is exactly that invariance. For the relational
reading of the framework: an observer related by a nonlinear chart receives
the Hessian jet, the gradient and the chart's Taylor polynomial to degree
`d+2`. For `H'` itself (order 0) the "correction factor supplied in advance"
is `sum_k (d_k U) Hess(phi^k)` and nothing smaller suffices; for the order-1
layer, and so for `kappa`, the third derivatives `sum_k (d_k U) d^3 phi^k`
are needed as well (d').

## 3. Enclosure readings: E1 (tightness), E2 (design), E3 (certified sign), E4 (exact threshold)

A reading at `q` is now a triple of exact intervals `I_q = (I11, I12, I22)`
containing `H(q)`. With a unisolvent design `D` of `m = (d+1)(d+2)/2` points,
the exact Taylor coefficients are `c = D^-1 h`. "Admissible" means: every
reading `h_q` inside its interval; the admissible set is a box in the `3m`
readings.

*Theorem E1.* The set of values of `c_alpha` over all admissible readings
`h_q in I_q` is exactly the interval `sum_q (D^-1)_{alpha q} I_q`, of width
`sum_q |(D^-1)_{alpha q}| width(I_q)`.

*Proof.* `c_alpha` is a linear form in independent variables `h_q`, each
ranging over an interval; the range of a linear form over a box is the
interval sum of the scaled intervals, attained at the corner where each `h_q`
sits at its upper bound if the coefficient is nonnegative and its lower bound
otherwise, and every value in between is attained on the segment joining the
two corners. ∎ The joint set of all coefficients of one entry is the
parallelepiped `D^-1(box)`, a strict subset of the product of the
per-coefficient intervals whenever `m >= 2` and all widths are positive: its
volume is `|det D^-1| prod_q w_q`, which by Hadamard's inequality and `L2 <=
L1` is at most `prod_alpha sum_q |(D^-1)_{alpha q}| w_q`, the box volume, with
equality only for a monomial `D^-1`, impossible since the `(0,0)` column of `D`
is all ones. For the learner's design with uniform widths the ratio is `(4/9)
/ (1 * 4/3 * 4/3) = 1/4`. E3 turns on this. (`fit_jet_enclosure`
returns these intervals and keeps the design and readings; the audit checks
containment of 640 random admissible interpolants and the width formula on 64
energies times two widths; the test checks that the upper bound is attained
by the corner reading.)

The row sums `sum_q |(D^-1)_{alpha q}|` are the design's **width factors**
(`width_factors`); the **first-layer factor** is the sum of the `(1,0)` and
`(0,1)` row sums.

*Proposition E2 (design criterion for three-point designs).* Let `D` be the
order-one design matrix of three points with base `p`, `Ds`, `Dv` the
coordinate spreads (`max - min`) of the three points, and `|det D| = 2 Area`.

(a) Row `(0,0)` of `D^-1` is the barycentric coordinate vector of `p` in the
design triangle; its `|.|`-sum is `1` iff `p` lies in the closed triangle.

(b) `rowsum_(1,0) = 2 Dv / |det D|` and `rowsum_(0,1) = 2 Ds / |det D|`.

(c) *Lower bound.* For any finite set of reading points, any jet order, and any
linear read-out `g` of the `(1,0)` coefficient that is exact on affine fields
(`sum_q g_q = 0`, `sum_q g_q s_q = 1`), `sum_q |g_q| >= 2/Ds`; inside a
candidate box of half-side `R` around the base this is `>= 1/R`, so no design
of any order inside the box has a first-layer factor below `2/R`. The
order-one corner design attains it (`8/3` for the learner's default
candidates, `R = 3/4`; `2/r` for the symmetric design at radius `r`).

(d) *Maximal volume versus minimal width.* For three points inside an
axis-aligned box of half-side `R`, both first-layer row sums are minimal
(`= 1/R`) iff `|det D| = 4R^2` is maximal. This is special to that situation:
in general a larger `|det D|` does not give a smaller width. `A = {(0,0),
(2,0), (0,2)}` has `|det D| = 4` and row sums `(1, 1, 1)`; `B = {(0,0), (5,4),
(4,5)}` has `|det D| = 9` and row sums `(1, 10/9, 10/9)`. Inside the learner's
own candidate grid, `A3 = {(-3/4,0), (3/4,0), (0,1/4)}` has `|det D| = 3/8`
and `rowsum_(1,0) = 4/3`, while `B3 = {(-3/4,-3/4), (-1/4,-3/4), (0,3/4)}`
has `|det D| = 3/4` and `rowsum_(1,0) = 4` (three times wider).

*Proof.* Translate the base to the origin; `D` is unchanged. (a) Row `(0,0)`
of `D^-1`, call it `lambda`, satisfies `sum lambda_q = 1` and `sum lambda_q q
= p`: barycentric coordinates; `sum |lambda_q| = 1` iff all are nonnegative
iff `p` is in the closed triangle. (b) `(D^-1)_{(1,0),q}` is the cofactor of
the `s`-entry in row `q` over `det D`, which is `+-(v_q' - v_q'')` for the
other two rows; the three absolute differences of three reals sum to twice
their range, so the row sum is `2 Dv / |det D|`; symmetrically for `(0,1)`.
(c) With `s_bar = (s_max + s_min)/2`, `1 = sum g_q s_q = sum g_q (s_q - s_bar)
<= (Ds/2) sum |g_q|`. In a box of half-side `R`, `Ds <= 2R`. An order-`d`
interpolation functional for `C_(1,0)` reproduces the coefficient of every
field of degree at most `d`, in particular of every affine field, so the bound
applies to every order; the order-one corner design has `Ds = Dv = 2R` and
`|det D| = 4R^2`, giving `1/R` for both rows by (b). (d) The area of a
triangle with vertices in a rectangle is a convex function of each vertex
separately, so it is maximal with all vertices at corners, where it is `0` or
`Ds Dv / 2`: `|det D| <= Ds Dv <= 4R^2`. By (b), `rowsum_(1,0) = 2Dv/|det D|
>= 2/Ds >= 1/R` with equality throughout iff `|det D| = Ds Dv` and `Ds = 2R`,
and likewise for `(0,1)`; both are minimal iff `|det D| = Ds Dv = 4R^2`, the
maximal value, and conversely `|det D| = 4R^2` forces `Ds = Dv = 2R`. The
counterexamples are exact computations. ∎

Consequences recorded by the audit on the default candidate grid (`7 x 7`,
step `1/4`, radius `3/4`): all `C(49,3) = 18424` triples enumerated, `17600`
unisolvent, `824` collinear; (a), (b) and `|det D| <= Ds Dv` hold in every
case; the maximal `|det D| = 9/4` is attained by exactly `24` designs, which
are exactly the designs with both first-layer row sums `4/3`, the learner's
default design among them; among `20000` random pairs of designs,
`1371` have a larger `|det D|` together with a larger `(1,0)` row
sum. `choose_design` starts from the greedy maximal-volume design and lowers
the first-layer factor by exact single-point swaps; it reports `converged`
when no single swap lowers the objective (a local minimum over swaps) and
otherwise that the sweep cap was reached; it is not a global optimum claim.
On the default candidates the greedy start is already optimal (by (c)); on
the candidate set `{(-5/4,-2), (-3/4,0), (0,1/4), (1/4,1), (3/2,1/2),
(7/4,7/4), (2,-3/4)}` the descent acts, `224/135 -> 100/63`, and stops above
the global minimum `168/107` over all triples. A higher jet order on the same
candidates ties or loses: `choose_design` gives first-layer factors `8/3`,
`8/3`, `28/3` at orders `1, 2, 3`, and the greedy order-two design has
`(0,0)` row sum `51/10` against `1`, so the `H` enclosure is `5.1` times
wider.

*Proposition E3 (numerator ranges and the certified sign; scope: the declared
family).* Write `H = (a,b,c)`, `H_s = (p1,p2,p3)`, `H_v = (r1,r2,r3)` (packed
entries), `Delta = ac - b^2`.

(a) `kappa = -N / (4 Delta^2)` with `N = (H_s adj(H) H_v - H_v adj(H) H_s)_12
= det[[a,b,c],[p1,p2,p3],[r1,r2,r3]] = (a,b,c) . (p x r)`. `N` is affine in
each of the nine entries and bilinear in `(H_s, H_v)`; as a function of the
readings, `N = det(E Hmat)` with `E` the three first-layer rows of `D^-1` and
`Hmat` the `m x 3` matrix of readings, so `N` is affine in every single
reading; for `m = 3`, `N = det(Hmat) / det D`. For the cubic family at the
origin `N = -uv`, `Delta = 9`, `kappa = uv/324`.

(b) Three valid ranges of `N`, nested: the natural interval extension of the
closed form `>=` the hull of `N` over the `2^9` corners of the nine
coefficient intervals (the exact range over the coefficient box) `>=` the
hull of `N` over the `2^{3m}` corners of the reading box (the exact range
over the admissible set; `reading_corner_range`, `numerator_ranges`). The
middle one can contain values no admissible reading produces: for `cubic(1,1)`
at half-width `1/16` on the learner's design the coefficient-corner range is
`[-371/192, -3/16]` and the reading-corner range `[-3763/2304, -11/24]`; the
coefficient corner `(a, p1, r1) = (33/16, 13/12, 1/12)` has the unique
preimage `H11` readings `(19/16, 47/16, 21/16)` under `h = D c`, and `47/16`
lies outside its interval `[43/16, 45/16]`.

(c) Assume the Hessian field is a polynomial of total degree at most one, so
that the exact order-one jet lies in the fitted box (E1). Let the box have
`a_lo > 0` and `Delta_lo := a_lo c_lo - max(b_lo^2, b_hi^2) > 0`. Then every
admissible `H` is positive definite, the exact range of `Delta` is `[Delta_lo,
a_hi c_hi - min b^2]`, and `-[N] / (4 [Delta]^2)` contains `kappa` for every
energy of the family whose readings lie in the given intervals, for each of
the three ranges `[N]`; so does the intersection with route (ii), the closed
form of J5 evaluated by interval arithmetic over `(E,F,G)` and the four third
derivatives, each taken as the intersection of the two jet intervals that
estimate it (`(H_s)_12` with `(H_v)_11`, `(H_s)_22` with `(H_v)_12`). The
module returns that intersection, using the reading-corner range when the
enclosure carries its design (order one), the coefficient-corner hull
otherwise. Route (i) alone also contains the curvature of every admissible
interpolant, integrable or not. Even with `[N]` exact the `kappa` interval is
loose, because `N` and `Delta` share `a, b, c`; within route (i) the sign
decision depends on `[N]` alone and is unaffected by that looseness, and route
(ii) can exclude zero where (i) does not (asymmetric designs; the audit
records how often).

(d) *Sign rule.* Under the gate, `sign(kappa) = -sign(N)`, and the sign is
certified iff `[N]` excludes `0`. With the reading-corner range this is the
best decision any method that ignores integrability can make: if `0` is in
the range, an admissible interpolant with `N = 0` exists and is consistent
with the data. When that interpolant is moreover integrable (an energy of the
family with `kappa = 0`), no sound certifier of any kind can certify.

*Proof.* (a) `H F_sv = -(H_s H^-1 H_v - H_v H^-1 H_s)/4`, and `H^-1 = adj(H) /
Delta`; computing the `12` entries gives `c(p1 r2 - p2 r1) - b(p1 r3 - p3 r1)
+ a(p2 r3 - p3 r2)`, the cofactor expansion of the determinant along its first
row; `kappa = (H F_sv)_12 / Delta = -N/(4 Delta^2)`. A determinant is affine in
each row and every entry sits in one row; changing one reading changes one
column of `E Hmat` affinely. (b) A multi-affine function on a box attains its
extremes at vertices (fix all variables but one: it is affine in that one),
and its range is an interval; the coefficient box contains the joint set
`D^-1(box)` (E1), and the natural extension contains the range over the box by
inclusion isotonicity. The unattainable corner is an exact computation. (c)
`a_lo c_lo > b^2 >= 0` gives `c_lo > 0`; `ac` is increasing in `a` and `c` on
the positive box and `b^2` ranges over the square of the `b`-interval; the
quotient of two ranges contains the quotient at every common point; the true
first layer is a Hessian jet, so its third derivatives lie in both estimating
intervals, and interval arithmetic on a valid box is valid; the intersection
of two sets containing the truth contains the truth. (d) The reading-corner
range is attained: `0` in it means an admissible reading set with `N = 0`,
which has the same readings as some truth with `kappa = 0` as far as the
certifier can tell. ∎ If the two intervals estimating one third derivative are
disjoint, no order-one Hessian jet fits the readings at all: the order
hypothesis is falsified (`InconsistentEnclosure`), a different event from a
positivity failure, reported as such. Outside the family the fitted box need
not contain the true jet at all (part 1, Theorem J3), and then no enclosure
built from it says anything about the true curvature: the certificate below
is conditional on the order hypothesis, exactly as the exact learner's status
is.

(Audit: nesting of the three ranges and containment of the true `N` on the 64
grid energies at two widths, the reading-corner range strictly inside the
coefficient-corner range in all 128 cases; the reading-corner endpoints attained by explicit
admissible corner readings pushed through `fit_jet` for 16 cases; the
`cubic(1,1)` numbers above; on the learner's symmetric design with uniform
widths route (ii) strictly tightens neither range in any of the 128 cases
(recorded); on 100 random asymmetric designs with per-entry widths the
reading-corner range is strictly inside the coefficient-corner range in
`100` cases and route (ii) strictly tightens the reading-corner range
in `33`, with the true `kappa` inside every intersection; 24 random cubic
energies with all four third derivatives nonzero, where the `E` and `G` terms
of the closed form are active, have their jet in the box, their `kappa` in the
enclosure, and the `kappa` of every integrable reading-box corner inside as
well; a perturbation sampler that crosses the reading box (rejections
recorded) has every admissible member's `kappa` inside. Scope control: a ghost
energy of part 1 built on the learner's six reading points has identical
readings, receives the identical certificate `sign_certified` with the
identical interval, and has a positive true `kappa` at the base where the
cubic's is negative; the certificate is about the family, not about that
energy.)

**Decision rule.** `learn_jet_enclosure` returns `sign_certified` when the
enclosure excludes zero, `sign_not_certified` when it does not,
`positivity_not_certified` when `H` itself is not certified, and
`order_falsified` when a check reading misses the predicted intervals or the
integrability intersection is empty; every status carries the `hypothesis`
field naming the declared family it is conditional on. In the middle two
cases the remedy named is narrower readings or a wider candidate set, with the
floor `1/max|ds| + 1/max|dv|` over the supplied candidates stated (E2(c)):
for the default candidates no design of any order has a first-layer factor
below `8/3`, which the default design already has, so repeated calls with
the same candidates cannot help. A higher jet order does not help: `kappa` at
the base is a function of the order-one coefficients only, and by E2(c) no
order-`d` read-out of a first-layer coefficient has a smaller width factor
than the order-one corner design on the same candidates. Check readings must
intersect the predicted intervals; a non-intersecting check falsifies the
order (the quartic control is falsified at width `1/1000`).

*Theorem E4 (exact certification threshold).* Uniform half-width `w` on every
entry at every design point, the learner's default design `{(-3/4,-3/4),
(3/4,3/4), (-3/4,3/4)}`, the 64 cubic grid cases, route (i) with the
reading-corner range. The set of `w` at which every case's sign is certified
is `[0, 1/13)`. At `w = 1/13` the case `(u,v) = (-1,1)` (true `kappa =
-1/324`) admits the readings `(147/52, 12/13, 225/52)`, `(69/52, 12/13,
303/52)`, `(139/52, 14/13, 295/52)` at the three design points, whose
interpolant `H = (27/13, 12/13, 66/13)`, `H_s = (-35/39, -4/39, 4/39)`, `H_v =
(-4/39, 4/39, 35/39)` is positive, satisfies both integrability identities,
and has `kappa = 0`: it is the order-one Hessian jet of a cubic energy of the
declared family, so no sound certifier of any kind certifies at `w >= 1/13`,
and for `w > 1/13` the same sign pattern yields an admissible interpolant with
`kappa > 0`, the wrong sign. The supremum is attained by no `w`.

*Proof.* Every enclosure is inclusion-isotone in `w`, so the certified set is
downward closed and it suffices to locate its supremum. Each reading corner's
`N` is a polynomial of degree at most three in `w` (E3(a), entries affine in
`w`) with value `-uv != 0` at `w = 0`; the reading-corner range is the hull of
these `512` values, so `0` enters it exactly at the least positive root over
all corner polynomials of all cases, unless the positivity gate (`a_lo = 2 -
w > 0`, `Delta_lo = (2-w)(5-w) - (1+w)^2 = 9 - 9w > 0`, the same for all 64
cases) fails first at `w = 1`. For `(u,v) = (-1,1)` the exact readings are
`(11/4, 1, 17/4)`, `(5/4, 1, 23/4)`, `(11/4, 1, 23/4)`; with the sign pattern
`(+,-,+ | +,-,+ | -,+,-)` the perturbed determinant is `(11/4+w)(-27w/2) -
(1-w)(-69/8 + 15w/2) + (17/4+w)(-3/2 + 6w) = 9/4 - 117w/4 = (9/4)(1 - 13w)`,
so `N = 1 - 13w` vanishes at `w = 1/13` and is negative beyond; the
interpolant there is the one displayed (exact), integrable, with `kappa = 0`.
This is the upper bound by hand. The lower bound, that no corner polynomial of
any case has a root in `(0, 1/13)`, is an exact finite computation
(`certification_threshold`: Sturm root counts over all `64 x 512` corner
polynomials, exact rationals), not a hand proof; its result is that the least
positive root over all corners is exactly `1/13`. ∎

The per-case suprema are exact rationals for all 64 cases (for example
`(1,1): 1/8`, `(1,-1): 1/11`, `(-1,3): 3/23`, `(3,-5): 15/29`, `(7,7): 21/41`,
`(-7,-7): 7/8`), minimal at `(-1,1)` only; in `24` cases the first vanishing
corner's interpolant is integrable, so the threshold is intrinsic there; in
the other `40` it is route (i)'s threshold, and route (ii) certifies at that
threshold in `0` of them. The learner (both routes) certifies at the
per-case threshold plus `1/50` in `0` cases, always with the
right sign. The same design scaled to radius `3/2` (factor `4/3`) has supremum
exactly `1/7`, witness integrable. The earlier bisection brackets
(`80659/1048576 < 1/13 < 20165/262144` and `37449/262144 < 1/7 <
149797/1048576`) are consistent with and superseded by the exact values. The
threshold is a property of the declared cubic family, this grid, this design
and the uniform-width model only; the design is not `s <-> v` symmetric,
which is why `(1,-1)` and `(-1,1)` differ (`1/11` versus `1/13`). Nothing
here concerns any instrument.

## 4. Theorem Q3 (second layer by shifted queries)

Let `f(x) = sum_i A_ii x_i^2 + 2 sum_{i<j} A_ij x_i x_j + sum_i b_i x_i mod M`
on `Z_M^n`, `M = 2^b`, `O_f|x> = zeta_M^{f(x)}|x>`.

(i) *Identification class.* `(A,b)` and `(A',b')` define the same function iff
`A' = A mod M/2` entrywise and `b' = b + (M/2) e mod M`, where `e_i = 1` when
`A'_ii` and `A_ii` differ (necessarily by `M/2`) and `e_i = 0` otherwise. The
number of functions is `(M/2)^{n(n+1)/2} M^n`.

*Proof.* `x^2 = x mod 2`, so `(M/2) x_i^2 = (M/2) x_i mod M`: adding `M/2` to
`A_ii` and to `b_i` leaves `f` unchanged; `2 A_ij x_i x_j` depends only on `A_ij
mod M/2`. Conversely, `f` determines the finite differences `Delta_i f(x) =
f(x+e_i) - f(x) = 2(Ax)_i + A_ii + b_i`, hence `Delta_i f(x) - Delta_i f(0) =
2 (Ax)_i` for all `x`, hence `2A_ij mod M`, hence `A mod M/2`; subtracting the
quadratic part of the canonical representative leaves a linear function whose
coefficients `mod M` are determined. So the classes are in bijection with
(`A mod M/2` symmetric, `b mod M`), which gives the count. ∎ (Enumeration
confirms the count for `(M,n) = (4,1), (8,1), (4,2)`.)

(ii) *Shifted pass.* On `H^{(x) nb}|0>`, apply `O_f^-1`, the reversible
increment `x_i -> x_i + 1 mod M`, `O_f`, the decrement, and the inverse QFT on
every register. The outcome is `2A_i mod M` (the vector `(2A_i1, ..., 2A_in)`)
with probability exactly 1.

*Proof.* After the four middle steps the state is
`M^{-n/2} sum_x zeta^{f(x+e_i) - f(x)} |x> = zeta^{A_ii + b_i} M^{-n/2} sum_x
zeta^{(2A_i).x} |x>`, a global phase times the tensor product over registers
`j` of `QFT|2A_ij>`; the inverse QFT returns `|2A_ij>` on each register. ∎

(iii) *Remainder pass.* With `A_hat = A mod M/2` lifted to `[0, M/2)`, apply
`O_f` then the inverse of the quadratic oracle of `A_hat` (with `b = 0`) on the
uniform superposition and read by inverse QFT: the outcome is `b_hat = b +
(M/2) e` with probability 1, and `(A_hat, b_hat)` is the canonical
representative of `f`'s class. *Proof.* The leftover phase is `zeta^{(A - A_hat)
x x + b.x}`; the off-diagonal leftovers are multiples of `M` and vanish, the
diagonal leftovers are `(M/2) e_i x_i^2 = (M/2) e_i x_i`, so the phase is linear
with coefficient `b + (M/2)e`. ∎

(iv) *Counting bound.* `2n+1` oracle uses determine the class. A deterministic
classical reader obtains one residue mod `M` per reading, so it needs at least
`ceil(log_M((M/2)^{n(n+1)/2} M^n)) = ceil(n(n+1)(b-1)/(2b) + n)` readings;
adaptivity cannot beat a counting bound (the whole run is a function of the
answer sequence), and a zero-error randomized reader obeys it on every run.
This bound is not the classical complexity; (v) settles that.

(v) *Exact classical complexity.* For `M >= 4` and every `n`, the minimum
number of readings of a deterministic classical reader, adaptive or not, that
identifies the class of every `f` is exactly `n(n+3)/2`, independent of `b`;
the nonadaptive point set `P0 = {e_i, 2e_i (i <= n), e_i + e_j (i < j)}`
attains it, with the decoding `2A_ii = f(2e_i) - 2f(e_i)`, `b_hat_i = f(e_i) -
A_hat_ii`, `2A_ij = f(e_i+e_j) - f(e_i) - f(e_j)` (all mod `M`;
`classical_reader`, `classical_complexity`). For `M = 2` the value is `n`.
The counting bound of (iv) equals `n(n+3)/2` iff `n(n+1) < 2b`, so among the
sizes below it is attained only for `n = 1`. Consequently `2n+1 <
n(n+3)/2` iff `n >= 3`: the quantum recipe uses fewer queries than any
deterministic classical reader from `n = 3` on for every `M >= 4` (`7` against
`9`), ties at `n = 2` (`5` against `5`) and loses at `n = 1` (`3` against
`2`).

*Proof.* Write `m = n(n+3)/2`, `g = (A_ii; A_ij (i<j); b_i) in Z_M^m`, and for
a point `p` the row `r_p = (p_i^2; 2 p_i p_j; p_i)`, so `f_g(p) = <r_p, g>`.
Let `K` be the subgroup of `g` with `f_g = 0` (the class of `0`; by (i) its
order is `2^{n(n+1)/2}`), and for a point set `P` let `Phi_P(g) = (<r_p,
g>)_{p in P}`. (1) Any correct adaptive reader, on an input `g`, queries a set
`P_L` of points along its path to a leaf `L`; every `g'` with `Phi_{P_L}(g') =
Phi_{P_L}(g)` follows the same path and receives the same answer, so
correctness forces `ker Phi_{P_L}` into `K`; since `K` is in the kernel of
every `Phi_P`, `ker Phi_{P_L} = K`. Hence every leaf has depth at least `C :=
min{|P| : ker Phi_P = K}`, and a nonadaptive reader on a minimizing `P`
attains `C`. (2) Let `R_P` be the `Z_M`-span of the rows `r_p`, `p in P`, and
`R` the span of all rows. The pairing on `Z_M^m` is nondegenerate, so
annihilators satisfy `|S^perp| = M^m/|S|` and `(S^perp)^perp = S`; `ker Phi_P
= R_P^perp` and `K = R^perp`; thus `ker Phi_P = K` iff `R_P = R`, and `C` is
the least number of rows that generate `R`. (3) `Z_M` is a local ring with
residue field `F_2`; by Nakayama's lemma the least number of generators of
the finitely generated module `R` is `dim_{F_2}(R / 2R)`. (4) The map `R ->
Hom(Z_M^m / K, Z_M)`, `r -> (g -> <r,g>)`, is well defined and injective, and
`|R| = M^m / |K| = |Z_M^m / K|`, so it is a bijection: `R` is the dual group
of `G = Z_M^m / K`, hence isomorphic to `G` as an abelian group, and its
`Z_M`-module structure is the group structure. By (i), `G` is isomorphic to
`Z_{M/2}^{n(n+1)/2} x Z_M^n`, a 2-group with `n(n+3)/2` nontrivial cyclic
factors when `M >= 4` (and `n` when `M = 2`), so `dim_{F_2}(R/2R) = n(n+3)/2`.
(5) `|P0| = 2n + n(n-1)/2 = n(n+3)/2` and the displayed decoding recovers the
canonical representative (`f(e_i) = A_ii + b_i`, `f(2e_i) = 4A_ii + 2b_i`,
`f(e_i+e_j) = A_ii + A_jj + 2A_ij + b_i + b_j`), so `P0` attains `C`. (6) The
counting bound is `ceil(n(n+3)/2 - n(n+1)/(2b))`, equal to `n(n+3)/2` iff
`n(n+1)/(2b) < 1`. `2n+1 < n(n+3)/2` is `(n-2)(n+1) > 0`. ∎ (Audit:
`classical_reader` decodes every parameter vector at `(M,n) = (4,1), (8,1),
(4,2), (8,2)` and random vectors at `(4,3), (8,3), (8,4)`; at `(4,2)` all
`1820` four-point sets fail to separate the `128` classes while `P0` does,
with the explicit pair `x_2` and `x_2^2` agreeing on `e_1, e_2, e_1+e_2,
2e_1`; the test repeats the `(4,2)` enumeration.)

(vi) *`n` shifts are necessary for shift readings.* For `M >= 4` and `k <= n-1`
shift vectors `s_1, ..., s_k`, there are two different classes with identical
shift readings `2 A s_j mod M` for every `j`: take `v in {0,1}^n` nonzero with
`v . s_j` even for all `j` (a nonzero solution of `k < n` homogeneous equations
over `F_2`) and `N = (M/4) v v^T`; then `N != 0 mod M/2`, so `(0,0)` and `(N,0)`
differ by (i), while `2 N s_j = (M/2) v (v . s_j) = 0 mod M` is the reading of
`A = 0` (`shift_blind_pair`; the test runs both shifted passes on the engine
and gets the same point mass). So any protocol that uses only shift readings
needs at least `n` shifts; `e_1, ..., e_n` suffice by (ii), as does any set
whose matrix is invertible mod `2`.

(vii) *Degree and differences (stated; the cubic is not executed on the engine
here).* For a polynomial phase of total degree `d`, one shift lowers the degree
by one (`(x+s)^alpha = x^alpha + lower order`), so a degree-`d` phase needs
`d-1` differences and `2^{d-1}` oracle uses per pass, and reads its top
coefficient as `d! C(., u_1, ..., u_{d-1}) mod M`, i.e. modulo `M / gcd(d!, M)`.
A single difference of a cubic is quadratic, and the uniform superposition
with a phase `q` followed by the inverse QFT has an outcome of probability `1`
iff `q` is affine mod `M` (the overlap with `QFT|w>` is a mean of `M^n` unit
complex numbers, of modulus `1` iff all equal): so one difference does not
read a cubic, two do. The engine's two-qubit controlled phases suffice for
quadratic oracles; a cubic oracle on the bit expansion needs triply controlled
phases for `M >= 32`, which is why this packet stops at quadratics.

| `b` | `n` | quantum uses `2n+1` (counted) | counting bound (iv) | exact classical (v) | fewer than exact? |
| --- | --- | --- | --- | --- | --- |
| 2 | 1 | 3 | 2 | 2 | no |
| 3 | 1 | 3 | 2 | 2 | no |
| 2 | 2 | 5 | 4 | 5 | no (tie) |
| 3 | 2 | 5 | 4 | 5 | no (tie) |
| 2 | 3 | 7 | 6 | 9 | yes |
| 3 | 3 | 7 | 7 | 9 | yes |
| 3 | 4 | 9 | 11 | 14 | yes |
| 2 | 5 | 11 | 13 | 20 | yes |
| 3 | 5 | 11 | 15 | 20 | yes |

The module caps registers at `b <= 3` bits (the reversible increment is
written with `x, cx, ccx` only); the number of registers `n` is limited only
by the engine's branch budget (`n b <= 16` qubits under the default
`max_branches = 65536`; beyond that `prepare` fails closed with a resource
error, never silently). The audit exercises `n <= 4`, `b <= 3`: it reads every
class for `n = 1`, `M = 4, 8`, random classes for `(b,n) = (2,2), (3,2),
(2,3), (3,3), (3,4)`, and checks `same_function`, `canonical_match` and the
counted `oracle_uses` for each. The separation
claimed is between the counted quantum uses of this recipe and the exact
deterministic classical complexity, at the sizes listed, with ideal
operations; no quantum lower bound is proved, and bounded-error randomized
classical readers are not covered by (iv) or (v). The final decrement in the
shifted pass only changes a global phase and could be dropped; it is kept so
that the register is read in place.

*Reading this with the jet picture.* The shift realizes the finite difference
`f(x+e_i) - f(x)`, a discrete first derivative, on the whole superposition at
once; the first difference of a quadratic is linear, and the Fourier law reads
a linear layer in one shot (part 1, Theorem Q1). A cubic phase would need two
differences (vii). The linear case is Bernstein and Vazirani; the
finite-difference trick for a quadratic phase is, we believe, standard in the
quantum query literature, and no reference is verified or claimed here. What
this packet adds is the exact execution on the flat engine, the exact
classical complexity, and the honest count: the `2n+1` is counted on the
executed circuits (`circuit.oracle_uses`, two applications of the hidden
oracle per shifted pass and one in the remainder pass; the inverse oracle of
the known representative is not a query), not a formula.

## 5. Claims, non-claims, open

Proved: J5(a)(b)(c); J6(a)(b), J6(d) (the surjectivity of `S`), J6(d') (the
third-derivative action, by the exact instance and the `(d+2)(d+1) t g_s`
formula); E1; E2(a)-(d) (identities, the `L1` lower bound and its consequence
for higher orders, the maximal-volume equivalence for three points in an
axis-aligned box, the counterexamples); E3(a)-(d) within the stated family;
E4's upper bound (the hand-computed corner polynomial and the integrable
witness) and the structure of the certified set; Q3(i)-(vii) as stated,
(v) by duality and Nakayama's lemma.
Exact finite computations, not hand proofs: E4's lower bound (least positive
root over `64 x 512` corner polynomials by Sturm counts), the 64 per-case
thresholds, the scaled-design threshold `1/7`, the enumeration of all 18424
candidate triples. Checked exactly on instances: the agreement of three
curvature formulas on random cases and on the grid, the transport-versus-
recomposition agreement on 40 random charts, every J6(c)(d)(d') instance, the
nullspace charts, the one-parameter formula at six values of `c`, `T' = T +
S(Q)` with `H' = H` on 20 random quadratic charts, the order-`(d+2)` shift for
`d = 0,1,2`, the enclosure containments, nesting, attainment and tightening
counts, the swap-descent instance, the enumerations and readings in Q3, the
`(4,2)` four-point enumeration and the nonadaptive decoding.
Not claimed: any identity with Recognition Seam Calculus rules; any statement
about measured noise, devices or hardware; a quantum lower bound (the exact
quantum query complexity is open; `2n+1` is this recipe's count); bounds for
bounded-error randomized classical readers; a transport law for charts that
are not polynomial; the cubic reading on the engine; anything beyond `n = 4`,
`b = 3` on the engine; that the per-case thresholds are rational for other
designs; a global design optimum beyond E2's setting (three points in an
axis-aligned box). Open: a certified design optimum for general candidate
sets and higher orders (the swap descent is local); whether route (ii) can be
made exact (the reading-corner range is exact for `N` but ignores
integrability); enclosure readings for the nonlinear transport (the gradient
would need an enclosure too); whether the Hessian-metric reading of `kappa`
is the one the constitutive adapter intends for the nonlinear photonic
response, where the chart is fixed by the device and a nonlinear observer
change is a real possibility.
