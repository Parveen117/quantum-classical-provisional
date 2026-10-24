# Target-specific photonic observer adapter — v0.13

**Author: Monty.** This step connects the existing photonic response to the
existing observer framework. It asks which declared target the readings can
recover, then applies a separate, conditional uncertainty-budget gate. It
supplies no measured heater coefficient, voltage, material fit or hardware
qualification.

## Theory and implementation lineage

Monty's earlier manuscript, *The observer–measurement problem: relational
information and cross-measurement prediction* (19 October 2026), Theorem 4.2,
already supplies the target-factorization criterion. Section 11 / Theorem
11.1 already treats calibrated channels recovering one device response. The
present adapter specializes those results; it is not a new general theory.

For readings `y = S x` and target `t = Pi x`, exact recovery requires
`ker(S) ⊆ ker(Pi)`. The existing calculator field/rank engine checks this as
`rank([S; Pi]) == rank(S)`. Their rank difference is the dimension of the
target image of the invisible state directions. No complete-state recovery
is required.

The optional device integration calls the **unchanged** `analyze_robustness`
implementation from `Parveen117/EMK-Tensor-Cell-Devices`, commit
`a116985f667e258696334be8a6b07f85879eb1c4`, using its rational exact core and
numerical Euclidean decoder. The two source blobs are pinned in
`photonic_observer.py` and verified before either file executes. Private
source is supplied separately by an authorized caller; it is not vendored,
downloaded or published by this adapter. The full upstream test suite is
not represented as having been rerun.

The nuisance treatment also follows the target-versus-nuisance distinction
reviewed in `RNKE-Applications` at commit
`440c795e1f9e8f9657a663d8f12fc4460996002e`. We append declared nuisance
columns to the sensor and zero columns to the target, then use the exact
kernel test. This uses the same mathematical criterion without copying the
application's pressure fitter, units, constants or private implementation.
Correlated history/noise whitening from that application is **not**
implemented here; a scalar noise norm is not an independence assumption.

## Declared targets and normalization

The state order is `(lower_arm, upper_arm, input_trim, output_trim, reference)`
in radians, followed by any explicitly named nuisance coordinates.

| Target | Native target map | Meaning |
| --- | --- | --- |
| `exchange_angle` | `-lower + upper` | Change of native theta, since theta = pi - lower + upper |
| `relative_phases` | `(lower-reference, upper-reference, input_trim, output_trim)` | Four relative phase coordinates |
| `absolute_reference` | `reference` | Deliberately blind negative control |

Full relative-coordinate recovery is stronger than a gate-specific tangent
target at singular parameterizations. It is not a measured gate fidelity.
The angle target is a control coordinate near the declared ideal component;
recovering it alone does not establish that trim phases realize the entire
desired gate.

Every packet requires positive rational state, reading and target scales:

`x_native = Dx z`, `y_native = Dy ybar`, `t_native = Dt tbar`;
`Sbar = Dy^-1 S Dx`, `Pibar = Dt^-1 Pi Dx`.

Each scale means native units per normalized coordinate. All uncertainty
norms below refer to these normalized coordinates. There are no implicit
unit choices in the API. A unity-scale example is an explicit choice, not
an experimentally calibrated noise model. The packet records the operating
point, reading labels, nuisance order, scales and current GDS/spec/I/O hashes.
Its hash checks content integrity, not authenticity or experimental validity.

At quadrature (`theta=16*pi/32`) the target-blind dimensions are:

| Target | Basis powers | Coherent local probes | With reference |
| --- | ---: | ---: | ---: |
| Exchange angle | 0 | 0 | 0 |
| Four relative phases | 3 | 1 | 0 |
| Absolute reference | 1 | 1 | 1 |

At theta=0 or pi, these rows become `(1,0,0)`, `(4,2,1)`, `(1,1,1)`.
These are local linear statements. They do not resolve a global periodic
inverse or physical preparation/analyzer calibration.

All supported phase points use the existing exact Q(zeta_64) arithmetic for
visibility. Only genuinely rational matrices export to the existing rational
device engine. Irrational entries produce `EXACT_FIELD_ONLY` and an explicit
unsupported uncertainty-export status; they are never rounded into a false
exact certificate.

## Conditional uncertainty gate

For the declared normalized model
`ybar = (Sbar + DeltaSbar) z + e + r`, with decoder
`D = Pibar Sbar^+`, the inherited finite-dimensional bound is

`target_error <= ||D||_2 (eta + epsilon B + rho)`.

The caller must explicitly provide all five inputs, including declared zeros:

- `sensor_noise_bound = eta`: measurement noise 2-norm bound;
- `calibration_drift_operator_bound = epsilon`: sensor-map perturbation operator norm;
- `state_norm_bound = B`: bound on the local state displacement;
- `nonlinear_remainder_bound = rho`: omitted response in measurement-space norm;
- `target_error_budget`: permitted normalized target error.

The added remainder slot prevents silently applying a tangent derivative to
a finite displacement. A nonzero value is a caller assumption unless
independently justified over that state region. It is not derived from the
photonic word here. Loss changes, splitter variation, preparation errors and
settling must either be included in a justified model/bound or remain open.

The inherited device gain is a floating-point SVD estimate, **not a certified
upper enclosure**. The wrapper therefore reports `MODEL_BUDGET_MET_NUMERICALLY`
or `MODEL_ERROR_BUDGET_EXCEEDED`, never hardware acceptance. Missing bounds,
exact target blindness, missing engine, unsupported irrational export and
numerical decoder failure are separate outcomes. It additionally rejects a
numerical rank inconsistent with the exact sensor rank, a failed decoder
consistency check, an excessive residual relative to the declared target
scale, or a non-finite gain/error. An upstream success label cannot
override these checks. Rejecting a lost but target-irrelevant sensor direction
is conservative and can be relaxed only with a separate verified decoder.

All bounds are labelled `CALLER_ASSUMPTIONS`; there is no source-bound
experimental certificate in this release. The numerical estimate is not a
statistical confidence interval. `calibration_accepted` and `hardware_submitted`
remain false on every path. The existing recorded-calibration/drive-plan API
is unchanged and does not automatically consume these results.

## Use and validation

```python
from phase_seam_foundation.photonic_observer import observer_packet, assess_uncertainty

packet = observer_packet(
    (16, 0, 48, 48), target="exchange_angle", measurements="basis",
    state_scales=[1]*5, reading_scales=[1]*4, target_scales=[1],
)
# No assumed or measured uncertainty is inserted automatically.
result = assess_uncertainty(packet, bounds={})
assert result["status"] == "INCOMPLETE_UNCERTAINTY_BOUNDS"
```

Run the public target/response/control tests and regenerate the empty request:

```bash
python benchmarks/photonic_observer_audit.py
```

For actual cross-repository integration, supply an authorized local directory
containing the two pinned device files and an environment with NumPy:

```bash
python benchmarks/photonic_observer_audit.py --device-source-dir /path/to/seam_antenna
```

The integration checks 27 target/family/endpoint combinations against the
unchanged device engine and nine explicitly synthetic uncertainty fixtures:
noise, drift, remainder, budget failure, weak reference and unit changes.
The public suite includes nuisance-confounding and source-pin rejection tests.
The committed `observer/qualification.json` and `observer/test_results.txt`
record the actual run and source hashes. Running without the private source
records `NOT_RUN_ENGINE_NOT_SUPPLIED`; it never invents an integration pass.

`observer/request_template.json` remains unmeasured with every bound unset.
Next physical work needs an actual device/context-bound response fit,
uncertainty evidence, nonlinear validity region and held-out measurements.
The SiN layout, prior response manifest and CAD artifacts are unchanged.
