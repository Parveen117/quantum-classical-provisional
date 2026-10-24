"""Exact, bounded two-site Weyl-bus word certificates, not a device simulator.

The bus interactions are ADDITIONAL physical assumptions. This adapter
reuses Q(zeta_64) and the existing joint EMK algebra; it adds no state backend.
See WEYL_BUS.md for local-PH2 obstruction, fault boundaries and prior art.
"""
from dataclasses import dataclass

from native_relational_qc.cyclotomic64 import ZETA
from .model import ResourceLimit

DIMENSIONS = (2, 4, 8, 16, 32, 64)
MAX_WORD = 512
MAX_STEP = 4096


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low},{high}]")
    return value


def _dimension(value):
    if type(value) is not int or value not in DIMENSIONS:
        raise ValueError("bus dimension must be one of 2,4,8,16,32,64")
    return value


@dataclass(frozen=True)
class Pulse:
    """Execution-order instruction. Bus controls use sign (-1)**data_bit.

    phase_a/b = exp(i*steps*pi/32*Z_a/b), flips are ideal local X.
    An uncontrolled bus pulse has control=None. No continuous-angle rounding.
    """
    kind: str
    steps: int = 1
    control: object = None

    def __post_init__(self):
        if self.kind not in ("bus_x", "bus_z", "phase_a", "phase_b", "flip_a", "flip_b"):
            raise ValueError("unknown bus-word pulse")
        _integer(self.steps, "pulse steps", -MAX_STEP, MAX_STEP)
        if self.kind.startswith("bus_"):
            if self.control is not None:
                _integer(self.control, "data control", 0, 1)
        elif self.control is not None:
            raise ValueError("local pulses have no bus control")
        if self.kind.startswith("flip_") and self.steps != 1:
            raise ValueError("local flip has exactly one application")


def _word(word):
    if not isinstance(word, (tuple, list)):
        raise ValueError("word must be a finite list or tuple")
    if len(word) > MAX_WORD:
        raise ResourceLimit("Weyl word exceeds 512 pulses; no certificate returned")
    if any(type(p) is not Pulse for p in word):
        raise ValueError("word requires validated Pulse objects")
    return tuple(word)


@dataclass(frozen=True)
class Branch:
    """|data,k> -> zeta_64**(phase + (64/d)*clock*k)|data_out,k+shift>."""
    data_out: int
    shift: int
    clock: int
    phase: int


def normal_form(word, *, dimension=64):
    """Four exact monomial blocks; linear cost in word length, no amplitudes.

    Branch order is 00,10,01,11 (A is the low bit). The normal bus order is
    X**shift Z**clock. This covers this restricted word language only.
    """
    d = _dimension(dimension); word = _word(word); scale = 64 // d
    result = []
    for initial in range(4):
        data, x, z, phase = initial, 0, 0, 0
        for pulse in word:
            n = pulse.steps
            if pulse.kind.startswith("bus_"):
                if pulse.control is not None:
                    n *= 1 - 2 * ((data >> pulse.control) & 1)
                if pulse.kind == "bus_x":
                    x = (x + n) % d
                else:
                    phase = (phase + scale * n * x) % 64
                    z = (z + n) % d
            elif pulse.kind.startswith("flip_"):
                data ^= 1 if pulse.kind == "flip_a" else 2
            else:
                site = 0 if pulse.kind == "phase_a" else 1
                phase = (phase + n * (1 - 2 * ((data >> site) & 1))) % 64
        result.append(Branch(data, x, z, phase))
    return tuple(result)


def certificate(word, *, dimension=64):
    """Check all-bus-state factorization and diagonal nonlocal phase exactly.

    Common bus transport is allowed in factorization; 'bus_returned' is
    stronger and requires identity transport. A local output flip is retained.
    """
    d = _dimension(dimension); word = _word(word)
    blocks = normal_form(word, dimension=d)
    common = len({(b.shift, b.clock) for b in blocks}) == 1
    flip = {i ^ b.data_out for i, b in enumerate(blocks)}
    if len(flip) != 1:
        raise ArithmeticError("word language violated its local-flip invariant")
    phases = tuple(b.phase for b in blocks)
    nonlocal_phase = (phases[0] - phases[1] - phases[2] + phases[3]) % 64 if common else None
    concurrence2 = ((2 - ZETA**nonlocal_phase - ZETA**(-nonlocal_phase)) / 4
                    if common else None)
    return dict(schema="native-weyl-bus-word-v1", status="CONDITIONAL_OPERATOR_IDENTITY",
                dimension=d, word_length=len(word),
                controlled_bus_pulses=sum(p.kind.startswith("bus_") and p.control is not None for p in word),
                local_flip_pulses=sum(p.kind.startswith("flip_") for p in word),
                branches=[dict(data_out=b.data_out, shift=b.shift, clock=b.clock, phase_steps=b.phase) for b in blocks],
                data_bus_factorized=common,
                bus_returned=common and blocks[0].shift == blocks[0].clock == 0,
                common_bus_word=[blocks[0].shift, blocks[0].clock] if common else None,
                local_output_flip_mask=next(iter(flip)),
                nonlocal_phase_steps=nonlocal_phase,
                entangling=(nonlocal_phase != 0) if common else None,
                plus_input_concurrence_squared=concurrence2.to_dict() if common else None,
                physical_interactions_assumed=True, physical_device_built=False,
                universal_simulation_claim=False)


def rectangle(a=2, b=4):
    """Apply X^(a ZA), Z^(b ZB), X^(-a ZA), Z^(-b ZB), in this order."""
    _integer(a, "x strength", -MAX_STEP, MAX_STEP)
    _integer(b, "z strength", -MAX_STEP, MAX_STEP)
    return (Pulse("bus_x", a, 0), Pulse("bus_z", b, 1),
            Pulse("bus_x", -a, 0), Pulse("bus_z", -b, 1))


def echoed_rectangle(a=1, b=4, *, drift=(0, 0), second_drift=None):
    """Two identical loops separated/followed by ideal X_A X_B.

    drift is local integrated Z phase in pi/32 units per half. Equal values
    cancel; arbitrary real equal values cancel by the documented theorem.
    Drifts are inserted at half boundaries, equivalent to commuting local Z
    errors during diagonal-controlled kicks with instantaneous perfect flips.
    """
    def half(errors):
        if not isinstance(errors, (tuple, list)) or len(errors) != 2:
            raise ValueError("one local drift per data site required")
        return rectangle(a, b) + (Pulse("phase_a", errors[0]), Pulse("phase_b", errors[1]))
    flips = (Pulse("flip_a"), Pulse("flip_b"))
    return half(drift) + flips + half(drift if second_drift is None else second_drift) + flips


def fault_certificate(word, *, after, x=0, z=0, dimension=64):
    """Insert bus-only E=X**x Z**z at a pulse seam of a closed word.

    Reports residual data phase and common bus fault. A zero nonlocal error
    does not mean an error-free data gate: local rotations still matter.
    """
    word = _word(word); _dimension(dimension)
    _integer(after, "fault seam", 0, len(word))
    _integer(x, "fault shift", -MAX_STEP, MAX_STEP)
    _integer(z, "fault clock", -MAX_STEP, MAX_STEP)
    ideal = certificate(word, dimension=dimension)
    if not ideal["bus_returned"] or ideal["local_output_flip_mask"]:
        raise ValueError("fault comparison requires a closed data-diagonal ideal word")
    faulty = word[:after] + (Pulse("bus_z", z), Pulse("bus_x", x)) + word[after:]
    actual = certificate(faulty, dimension=dimension)
    if not actual["data_bus_factorized"] or actual["local_output_flip_mask"]:
        raise ArithmeticError("Weyl fault did not retain expected factorization")
    residual = [(f["phase_steps"] - i["phase_steps"]) % 64
                for f, i in zip(actual["branches"], ideal["branches"])]
    invariant = (residual[0] - residual[1] - residual[2] + residual[3]) % 64
    return dict(after=after, fault=[x, z], common_bus_word=actual["common_bus_word"],
                data_error_steps=residual, nonlocal_error_steps=invariant,
                local_one_phase_steps=[(residual[1]-residual[0]) % 64, (residual[2]-residual[0]) % 64],
                data_unchanged_up_to_global_phase=len(set(residual)) == 1)


def native_interaction_bridge():
    """Reuse joint.py: conjugate the pi/4 ZZ bus target into its existing U.

    K=Z, L=X, iR=Y. No new entangled state or quantum postulates are introduced.
    """
    from .joint import Element, local, IMAG, INV_SQRT2 as h, interaction
    identity = Element.basis(2)
    ka, kb = local(2, 0, "K"), local(2, 1, "K")
    la, rb = local(2, 0, "L"), local(2, 1, "R")
    zz_gate = (identity + (ka * kb) * IMAG) * h
    basis_change = ((identity + la * IMAG) * h) * ((identity + rb) * h)
    native_gate = basis_change * zz_gate * basis_change.dagger()
    target = interaction()
    if native_gate != target:
        raise ArithmeticError("bus/local-basis bridge failed native EMK identity")
    return dict(zz_gate=zz_gate, basis_change=basis_change, native_gate=native_gate, target=target)
