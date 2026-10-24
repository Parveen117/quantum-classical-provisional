# TVSP constitutive response adapter — v0.14

**Author: Monty.** A declared energy now supplies constrained response,
the first response layer, selected native curvature and the material part
of the photonic control Jacobian. Exact rational bounds specify a finite
operating patch and bound nonlinear optical remainder. This advances the
model before device readings exist; it does not manufacture material data.

## Source and reuse contract

The six responses and selected connection are inherited from Publications
`papers/native-thermodynamic-curvature/THEOREM.md`, NT-1/3/4. The original
six-response definitions are pinned in the corrected thermo manuscript at
`f0f1c1650e914b7eaf3bf64ddb7df9f543c92a56`, sections
`01_foundations.tex` and `01a_response_summary.tex`.

The equal-value/different-layer family and first-layer convention are TLM-T5
in Publications `babb4fb1922bd91c2eadc82abd4b9538a19745d0`,
`papers/native-tvsp-lambda-matrices/THEOREM.md`. That repository already has
the general Paninian jet algebra and covariant response tower. They are not
copied or reimplemented here. This small adapter admits only an explicitly
specified two-coordinate cubic energy, using closed derivative formulas.

The calculator's existing `EMKBlock` performs the native ordered products for
curvature; the existing optical word supplies probabilities/Jacobians and
`compose_response` supplies the final chain rule. An optional comparison
executes the unchanged, byte-pinned TLM adapter and its two native engines
from a separate source directory. It compares six source parameters, all six
response values and their first derivatives, the Hessian and its first layer.
This comparison is not a replay of the complete publication certificate.

## Declared source and responses

In one normalized affine chart q=(s,v), declare

`U(q) = g0.q + q^T H0 q/2 + T[q,q,q]/6`,

where `H0=[[a,b],[b,c]]` and the symmetric cubic tensor is stored as
`(U000,U001,U011,U111)=(d,e,f,g)`. Thus

`H(q) = H0 + [[d,e],[e,f]] s + [[e,f],[f,g]] v`.

The coefficient list defines the entire polynomial. Zero cubic coefficients
declare a quadratic model; they are not inferred from missing derivative
measurements. All input coefficients, points and scales are exact rationals.
Bool/float inputs, nonpositive Hessians and oversized coefficients fail.

The thermodynamic adapter additionally declares positive affine S,V and
requires positive T=U_s at the requested point, with P=-U_v. For the local
entries a,b,c and Delta=ac-b² it returns

`Lambda = (-S Delta/c, -S a, -V c, -V Delta/a, P/c, P a/Delta)`

in order `(lambdaP,lambdaV,lambdaS,zT,zS,lambdaT)`, along with
`Cv=T/a, Cp=Tc/Delta, Ks=Vc, Kt=VDelta/a`.

The EM chart of the same algebraic energy Hessian returns
`epsilonB=1/a, epsilonH=c/Delta, muD=1/c, muE=a/Delta`.
It uses the conjugate-pair substitution `(T,S,-P,V) <-> (E,D,H,B)`.
These are typed constitutive formulas, not a derivation of Maxwell field
equations or evidence that an actual thermal and EM specimen have the same
numerical coefficients. Physical reference scales and constitutive matching
must be supplied before assigning temperature, pressure or electromagnetic
units. The old uniform entropy-scaled tetrad is not substituted for this
six-response convention.

The first response layer consists of ordinary partial derivatives in this
declared affine chart and flat response-component frame. Higher covariant
slots remain the existing TLM engine's responsibility. The selected connection
is `A_i=H^-1 partial_i H/2`, so

`F_sv = -[H^-1 H_s, H^-1 H_v]/4`, `kappa=(H F_sv)_12/Delta`.

Here H is an energy-response Hessian, not the quantum circuit Hamiltonian.
The selected connection is part of the source contract. An arbitrary physical
device does not acquire this transport law merely by having a Hessian.

For `H0=[[2,1],[1,5]]`, `T=(0,mu,0,0)`, `g0=(10,-10)`, S0=V0=1:

| mu | All six response values at q=0 | partial_v lambdaV | kappa |
| ---: | --- | ---: | ---: |
| 0 | (-9/5,-2,-5,-9/2,2,20/9) | 0 | 0 |
| 1 | same | -1 | 5/324 |
| 5 | same | -5 | 125/324 |
| -5 | same | 5 | 125/324 |

Point responses alone do not identify the surrounding model. Curvature alone
also loses the sign of mu, which the first response layer retains.

## Constrained material response to the existing optical observer

At a stable operating point, static conjugate-force perturbations obey
`delta q = chi delta f` to first order, with `chi=H^-1`. Holding q1 fixed
instead gives the embedded response `diag(1/a,0)`; holding q0 fixed gives
`diag(0,1/c)`. A held coordinate has the reaction force required by that
constraint. The free and held responses need not agree.

Declare a constant five-by-two map L from material displacement to phase,
including reference phase, and a two-by-m map A from controls to conjugate
force. The adapter generates

`B_phase,control = L chi A`, `J_reading,control = J_reading,phase B`.

These are normalized model coordinates. Heater power and voltage are not
automatically conjugate forces; an actual electrothermal actuator law must
establish the appropriate mapping. Neither damping/settling nor bath dynamics
are supplied by static U. The full two-dimensional finite-patch bound below
applies to the released equilibrium; a clamped finite-displacement problem
would need its corresponding restricted bound.

## Exact finite-patch and nonlinear bounds

All norms in this section are Euclidean, except explicitly marked 1-norms.
At q0 define rational quantities

`m0 = det H(q0)/trace H(q0)`,
`L_H = |d|+3|e|+3|f|+|g|`, `m = m0 - L_H R`.

Require R>0, m>0 and `0 <= B_f < m R`. The entire closed ball
`||q-q0||_2 <= R` then has H>=m I. The m0 lower bound follows from the two
positive eigenvalues; the sum of absolute tensor coefficients bounds the
Hessian variation by `L_H ||delta q||_2`.

For every `||delta f||_2 <= B_f`, the perturbed energy has exactly one
stationary point in this ball. To see existence, minimize the strongly convex
energy on the compact ball. At a boundary point its outward radial derivative
is at least `m R²-B_f R>0`, so a minimizer cannot be on the boundary.
Strong monotonicity gives uniqueness and

`r_q = ||delta q||_2 <= B_f/m`.

The exact cubic gradient identity then gives

`||delta q - H(q0)^-1 delta f||_2 <= L_H r_q²/(2m0) = r_inv`.

This is a sufficient conservative bound. Failing it means the requested patch
is not certified by this routine, not that every possible model is unstable.
It makes no global-confinement claim for a nonquadratic cubic potential.

Let `ell=sum_ij |L_ij|`; then `||delta phi||_1 <= ell r_q`. For every
probability in the existing ideal optical word,

`|D²p(phi)[v,v]| <= 4 ||v||_1²`.

Indeed, differentiating the unitary factors along v bounds amplitude
derivatives by `||v||_1` and `||v||_1²`. Differentiating squared amplitude
gives the factor four. The reference-interference amplitudes satisfy the
same conservative bound, retaining the reference column. Taylor's integral
remainder gives `|r_p| <= 2 ||delta phi||_1²` for any real phase displacement.

For n readings with positive normalizers dy_i, the exact rational bound used
for v0.13 is

`rho_optical = 2 ceil(sqrt(n)) (ell r_q)² / min(dy)`.

With positive phase normalizers dx_i the state-displacement bound is

`B_phase = r_q sum_ij |L_ij|/dx_i`.

`phase_observer_bounds` reconstructs and verifies the current optical packet,
its normalizers and its geometry binding. It returns these two quantities
as `state_norm_bound` and `nonlinear_remainder_bound`. No sensor-noise bound,
calibration-drift bound or target budget is inserted. The existing uncertainty
gate therefore still rejects an incomplete uncertainty request.
These two bounds are rational model bounds. Passing them to v0.13 retains
that engine's floating-point gain/decision boundary; it does not turn its
total error estimate into a certified numerical upper enclosure.

The separate force-to-reading tangent remainder additionally includes the
nonlinear inverse response:

`rho_composed = rho_optical + 2 ceil(sqrt(n)) ell r_inv/min(dy)`.

It is reported separately because the current observer's target is the
actual phase displacement. It must not silently become a claim about a
nonlinear phase target inferred by treating force as the observer state.
Even a quadratic material has nonzero optical remainder: its trigonometric
optical readout is not a linear function of phase.

## Target-specific harmonic noise

For a globally positive quadratic energy only, and an explicitly declared
classical full-space Gibbs model with positive normalized k_B T=tau,

`Cov(q)=tau H^-1`, `Cov(phi)=L Cov(q) L^T`.

The native exchange angle has delta theta=delta phi_upper-delta phi_lower,
so its variance is `C_uu+C_ll-2C_ul`. Reference covariances are also retained.
An ideal common-mode fixture has nonzero arm noise but zero angle variance;
independent arm fluctuations do not cancel. This says nothing about the
remaining gate-error sources or an actual device's noise level.

Nonquadratic models are rejected by this exact harmonic API. This is an
equal-time classical covariance, not quantum FDT, a Nyquist spectrum or a
finite-window confidence bound. Frequency-dependent baths and causal response
remain separate work.

## Reproduce and continue

```bash
python benchmarks/constitutive_response_audit.py
# Also compare with unchanged, pinned Publications/TLM source:
python benchmarks/constitutive_response_audit.py --tlm-source-dir /path/to/Publications
```

The optional source directory needs only the three files listed in the audit's
SOURCE_PINS, with their repository-relative paths. Without them the comparison
is explicitly NOT_RUN. Public tests cover source integrability, response
identities, first layers, native curvature, held/free response, finite optical
remainders, normalization, correlated noise and rejected invalid domains.

The report is `constitutive/qualification.json`; all example coefficients
are declared synthetic models. No actual material has been fitted and no
hardware operation is authorized. Earlier response/observer sources and CAD
artifacts remain unchanged. The next separate development is the PH2
cycle-to-optical-gate compiler, retaining attenuation and success probability.
