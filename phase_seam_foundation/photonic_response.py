"""Exact local optical response and an unrun coupled-physics acquisition plan.

This differentiates a two-port component word in the calculator's existing
field. It is not a Maxwell/heat solver, fitted device model or voltage driver.
All derivatives are per radian; phase steps specify the evaluation point only.
"""
from functools import lru_cache
from fractions import Fraction

from native_relational_qc.cyclotomic64 import Cyclotomic64 as F, ZERO, ONE, ZETA
from native_relational_qc.exact import IMAG, INV_SQRT2
from .model import ResourceLimit, integer
from .photonic_io import calibration_template
from .photonic_layout import layout_spec

I, H = F(IMAG), F(INV_SQRT2)
PHASE_ORDER = ("lower_arm", "upper_arm", "input_trim", "output_trim", "reference")
D = ((H, I*H), (I*H, H))
IDENTITY = ((ONE, ZERO), (ZERO, ONE))
STATES = ((ONE, ZERO), (ZERO, ONE), (H, H), (H, I*H))
STATE_NAMES = ("0", "1", "+", "+i")


def _multiply(a, b):
    return tuple(tuple(sum((x*y for x, y in zip(row, col)), ZERO)
                       for col in zip(*b)) for row in a)


def _product(factors):
    value = IDENTITY
    for factor in factors:
        value = _multiply(value, factor)
    return value


def _steps(values, size):
    if type(values) is not tuple or len(values) != size:
        raise ValueError(f"a tuple of {size} phase steps is required")
    for value in values:
        integer(value, "phase step")
        if not -64 <= value <= 64:
            raise ValueError("phase step outside [-64,64]")
    return values


def unit_jet(phase_steps):
    """Return U and four exact derivatives dU/dphi at a declared phase point.

    U = diag(1,exp(i*out)) D diag(exp(i*upper),exp(i*lower))
        D diag(1,exp(i*in)). No material transfer is inferred from this word.
    """
    return _unit_jet(_steps(phase_steps, 4))


@lru_cache(maxsize=64)
def _unit_jet(phase_steps):
    lower, upper, before, after = (ZETA**k for k in phase_steps)
    factors = (((ONE, ZERO), (ZERO, after)), D,
               ((upper, ZERO), (ZERO, lower)), D,
               ((ONE, ZERO), (ZERO, before)))
    replacements = ((2, ((ZERO, ZERO), (ZERO, I*lower))),
                    (2, ((I*upper, ZERO), (ZERO, ZERO))),
                    (4, ((ZERO, ZERO), (ZERO, I*before))),
                    (0, ((ZERO, ZERO), (ZERO, I*after))))
    derivatives = []
    for position, derivative in replacements:
        word = list(factors)
        word[position] = derivative
        derivatives.append(_product(word))
    return _product(factors), tuple(derivatives)


def _amplitude(matrix, source, detector):
    return sum((detector[r].conjugate()*matrix[r][s]*source[s]
                for r in range(2) for s in range(2)), ZERO)


def optical_response(phase_steps, *, measurements="reference", reference_steps=0):
    """Exact probabilities and local Jacobian, including reference phase.

    basis: four basis powers. local: 16 input/projection probabilities within
    the unit. reference: the local set plus eight interference probabilities
    against a bypass path. Preparation/analyzer phases must be calibrated.
    The reference can drift: its column is retained, never fixed silently.
    """
    if measurements not in ("basis", "local", "reference"):
        raise ValueError("unknown measurement family")
    _steps((reference_steps,), 1)
    u, derivatives = unit_jet(phase_steps)
    labels, probabilities, jacobian = [], [], []

    def append(label, amplitude, tangent):
        labels.append(label)
        probabilities.append(amplitude.norm2())
        jacobian.append(tuple(amplitude.conjugate()*v + v.conjugate()*amplitude
                              for v in tangent))

    count = 2 if measurements == "basis" else 4
    for s in range(count):
        for r in range(count):
            amplitude = _amplitude(u, STATES[s], STATES[r])
            tangent = tuple(_amplitude(v, STATES[s], STATES[r]) for v in derivatives)
            append(f"local:{STATE_NAMES[s]}->{STATE_NAMES[r]}", amplitude, (*tangent, ZERO))
    if measurements == "reference":
        for s in range(2):
            for r in range(2):
                for alpha in (0, 16):
                    reference = ZETA**(reference_steps-alpha)
                    append(f"reference:{s}->{r}:analyzer_{alpha}",
                           (u[r][s]+reference)/2,
                           (*(v[r][s]/2 for v in derivatives), I*reference/2))
    return dict(labels=tuple(labels), probabilities=tuple(probabilities),
                jacobian=tuple(jacobian), phase_order=PHASE_ORDER,
                derivative_unit="per radian", evidence_class="IDEAL_COMPONENT_ALGEBRA")


def _real_matrix(rows):
    if not isinstance(rows, (tuple, list)) or not rows or len(rows) > 128:
        raise ResourceLimit("matrix requires 1..128 rows")
    if any(not isinstance(row, (tuple, list)) for row in rows):
        raise ValueError("matrix rows must be sequences")
    width = len(rows[0])
    if not 1 <= width <= 32:
        raise ResourceLimit("matrix requires 1..32 columns")
    if any(len(row) != width for row in rows):
        raise ValueError("ragged response matrix")
    result = []
    for row in rows:
        converted = []
        for value in row:
            if type(value) not in (int, Fraction, F):
                raise TypeError("exact int/Fraction/Cyclotomic64 entries required")
            value = F.coerce(value)
            if value != value.conjugate():
                raise ValueError("response matrix must be real")
            if value.max_bits > 4096:
                raise ResourceLimit("response coefficient bit limit")
            converted.append(value)
        result.append(converted)
    return result


def exact_rank(rows):
    """Bounded exact rank of ideal coefficients, not statistical data rank.

    No tolerance/conditioning claim is made. Noisy measured Jacobians need
    scaled singular values and uncertainty analysis, separately from this API.
    """
    a = _real_matrix(rows)
    rank = 0
    for col in range(len(a[0])):
        pivot = next((r for r in range(rank, len(a)) if a[r][col]), None)
        if pivot is None:
            continue
        a[rank], a[pivot] = a[pivot], a[rank]
        divisor = a[rank][col]
        a[rank] = [v/divisor for v in a[rank]]
        for r in range(rank+1, len(a)):
            if a[r][col]:
                factor = a[r][col]
                a[r] = [v-factor*w for v, w in zip(a[r], a[rank])]
        if any(v.max_bits > 4096 for row in a for v in row):
            raise ResourceLimit("elimination coefficient bit limit")
        rank += 1
        if rank == len(a):
            break
    return rank


def compose_response(optical_jacobian, phase_per_control):
    """Chain rule J_y,control = J_y,phase B, retaining all supplied crosstalk.

    B must include the reference response, with the same five phase rows and
    an explicit caller-defined control order/unit. This does not validate B
    as measured evidence or turn its entries into an authorized drive plan.
    """
    a, b = _real_matrix(optical_jacobian), _real_matrix(phase_per_control)
    if len(a[0]) != 5 or len(b) != 5:
        raise ValueError("five phase columns/rows, including reference, required")
    result = _multiply(a, b)
    _real_matrix(result)
    return result


def response_plan():
    """Unmeasured acquisition contract bound to the existing physical layout."""
    template = calibration_template(physical_layout=True)
    spec = layout_spec()
    channels = [h["channel"] for h in spec["heaters"]]
    units = []
    for i in range(6):
        units.append(dict(unit=f"exchange_{i}", paths=spec["exchange_groups"][i]["labels"],
                          reference_path=0,
                          phase_channels=[f"core_{i}", f"core_{i}_common",
                                          f"core_{i}_input_trim", f"core_{i}_output_trim", "bypass_0"],
                          phase_per_power_rad_per_w=[[None]*28 for _ in PHASE_ORDER]))
    return dict(schema="native-photonic-response-plan-v1", author="Monty",
                status="UNMEASURED_PLAN", evidence_class=None,
                io_sha256=template["io_sha256"],
                layout_spec_sha256=template["layout_spec_sha256"],
                layout_gds_sha256=template["layout_gds_sha256"],
                device_id=None, context=template["context"],
                strategy="optical-observer audit, then coupled electrical/thermal/optical identification",
                phase_order=list(PHASE_ORDER), power_control_order=channels, units=units,
                all_recorded_actuators=list(template["actuator_map"]),
                diagnostic_angle_pi_over_32=16, phase_derivative_unit="per radian",
                measurement_families=dict(basis=4, local=16, reference=24),
                measurement_definition="PHOTONIC_RESPONSE.md; probabilities include incident normalization, not success postselection",
                acquisitions=[], raw_evidence_sha256=[], hardware_submitted=False,
                missing_inputs=["vertical material stack, dispersive refractive indices and mode profiles",
                                "heater resistance versus temperature and measured V/I/power limits",
                                "thermal conductivities, heat capacities, interfaces and package boundary conditions",
                                "wavelength/polarization dependent complex MMI and bend transfer",
                                "calibrated input/analyzer/reference path, absolute loss and uncertainty",
                                "joint-channel steady and transient response, drift and held-out configurations"],
                boundary="exact local ideal observability only; no material solve, fitted coefficients or drive voltages")
