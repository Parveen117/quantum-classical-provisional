"""Exact repeated-source-channel audit: source return, detector return and history.

Uses observer_state's declared convex source channel, not a free affine map.
This is a local model calculation; no measurement records or hardware run are
fabricated. See OBSERVER_CYCLE.md for the SP1 adapter and its claim boundary.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction as Q
import json
from pathlib import Path

from .certify import flat_field
from .compact import ResourceLimit, _integer
from .observer_state import GRID, source_affine


@dataclass
class _Budget:
    max_coeff_bits: int
    compositions: int = 0
    peak_coeff_bits: int = 0

    def check(self, *values):
        for value in values:
            bits = value.max_bits
            self.peak_coeff_bits = max(self.peak_coeff_bits, bits)
            if bits > self.max_coeff_bits:
                raise ResourceLimit("observer-cycle exact coefficient bit budget exceeded")

    def compose(self, later, earlier):
        """(H2,b2) after (H1,b1), including transport of the earlier b."""
        H2, b2 = later
        H1, b1 = earlier
        H, transported = H2 * H1, H2 * b1
        self.check(H, transported)
        b = b2 + transported
        self.check(b)
        self.compositions += 1
        return H, b

    def power(self, pair, count):
        F = flat_field()
        result = F(1), F()
        while count:
            if count & 1:
                result = self.compose(pair, result)
            count //= 2
            if count:
                pair = self.compose(pair, pair)
        return result


def _real(z):
    return (z + z.conjugate()) / 2


def probability_zero(z, axis):
    """Fresh equatorial analyzer probability for the admitted coherence z."""
    if type(axis) is not int:
        raise ValueError("integer phase-grid analyzer required")
    return (1 + _real(flat_field().root(-2 * (axis % GRID)) * z)) / 2


def _complex_record(z, budget):
    F = flat_field()
    real, imag = _real(z), _real(-F.imag() * z)
    budget.check(z, real, imag)
    return dict(real=real.display(), imag=imag.display())


def audit_cycles(*, start=0, velocity=8, offset=8, retention=Q(3, 4),
                 steps_per_cycle=4, cycles=3, axis=0, frame_step=0,
                 max_coeff_bits=4096):
    """Propagate a repeated, fixed source block and audit exact equalities.

    `start`, `velocity`, `offset`, `axis`, and `frame_step` use 2*pi/32 units.
    The drive stays at start+offset in lab coordinates across ALL repetitions.
    `frame_step` is an observer-coordinate advance per whole block.
    A cycle denotes a repeated protocol block; its source need not return.
    """
    steps_per_cycle = _integer(steps_per_cycle, "steps_per_cycle", 1, 32)
    cycles = _integer(cycles, "cycles", 0, 1_000_000)
    max_coeff_bits = _integer(max_coeff_bits, "max_coeff_bits", 128, 8192)
    if type(axis) is not int or type(frame_step) is not int:
        raise ValueError("integer phase-grid analyzer and frame step required")
    step = source_affine(start, velocity, offset, retention=retention)
    F = flat_field()
    budget = _Budget(max_coeff_bits)
    budget.check(*step)
    H, b = budget.power(step, steps_per_cycle)
    Hn, bn = budget.power((H, b), cycles)
    initial = F.root(2 * (start % GRID))
    once, final = H * initial + b, Hn * initial + bn
    budget.check(once, final)

    # For the admitted channel family H=1 forces every retention to be one
    # and hence b=0. Otherwise the field inverse supplies a fixed coherence.
    if H == 1:
        if b:
            raise ArithmeticError("the physical source family cannot translate with H=1")
        fixed = F()  # One witness; all admitted coherences are fixed.
        fixed_kind = "all_equatorial_plane_states"
    else:
        fixed = b / (1 - H)
        fixed_kind = "unique_equatorial_plane_state"
    budget.check(fixed)
    fixed_residual = H * fixed + b - fixed
    fixed_radius_squared = fixed * fixed.conjugate()
    final_radius_squared = final * final.conjugate()
    budget.check(fixed_residual, fixed_radius_squared, final_radius_squared)
    if fixed_residual or (1 - fixed_radius_squared).real_sign() < 0 or (1 - final_radius_squared).real_sign() < 0:
        raise ArithmeticError("source-channel fixed point or positivity check failed")

    p_initial, p_final = probability_zero(initial, axis), probability_zero(final, axis)
    p_once = probability_zero(once, axis)
    orth_initial = probability_zero(initial, axis + 8)
    orth_final = probability_zero(final, axis + 8)
    # Compare two states under the SAME future block. The known affine
    # offset cancels, leaving E*d and E*H*d (SP1 / MR-04).
    difference = final - initial
    future_difference = H * difference
    now_signal = _real(F.root(-2 * (axis % GRID)) * difference)
    next_signal = _real(F.root(-2 * (axis % GRID)) * future_difference)
    budget.check(p_initial, p_once, p_final, orth_initial, orth_final,
                 difference, future_difference, now_signal, next_signal)
    horizon = 0 if now_signal else (1 if next_signal else None)
    future_rank = 1 if H == H.conjugate() else 2

    frame_angle = (cycles * frame_step) % GRID
    relative = F.root(-2 * frame_angle) * final
    calibrated = F.root(2 * frame_angle) * relative
    moving_probability = probability_zero(relative, axis - frame_angle)
    budget.check(relative, calibrated, moving_probability)
    source_return = final == initial
    pair_return = p_final == p_initial and orth_final == orth_initial
    if pair_return != source_return or calibrated != final or moving_probability != p_final:
        raise ArithmeticError("observer reconstruction check failed")

    result = dict(
        schema="nrqc-observer-cycle-v1", status="complete",
        evidence_class="LOCAL_IDEAL_CALCULATION", hardware_job_id=None,
        model=dict(start=start % GRID, velocity=velocity % GRID, offset=offset % GRID,
                   retention=str(Q(retention)), phase_grid=GRID,
                   steps_per_cycle=steps_per_cycle, cycles=cycles,
                   drive_phase=(start + offset) % GRID,
                   source="observer_state.source_affine / source_mixtures",
                   state_domain="equatorial-plane density matrices; z=2*rho[1,0]"),
        cycle=dict(H=_complex_record(H, budget), b=_complex_record(b, budget),
                   rotation_closes=(velocity * steps_per_cycle) % GRID == 0,
                   channel_is_identity=H == 1 and not b,
                   initial_source_returns_after_one_cycle=once == initial),
        state=dict(initial=_complex_record(initial, budget),
                   final=_complex_record(final, budget),
                   final_radius_squared=final_radius_squared.display(),
                   returns_to_initial=source_return),
        reset=dict(obstruction_zero=True, fixed_point_kind=fixed_kind,
                   fixed_point=_complex_record(fixed, budget),
                   fixed_point_radius_squared=fixed_radius_squared.display(),
                   exact_fixed_point_verified=not bool(fixed_residual),
                   state_event_counter_from_nonzero_obstruction=False),
        observer=dict(axis=axis % GRID,
                      initial_probability_zero=p_initial.display(),
                      final_probability_zero=p_final.display(),
                      repeats_after_one_cycle=p_once == p_initial,
                      repeats_at_requested_cycles=p_final == p_initial,
                      orthogonal_axis=(axis + 8) % GRID,
                      orthogonal_initial_probability_zero=orth_initial.display(),
                      orthogonal_final_probability_zero=orth_final.display(),
                      two_axis_readout_returns=pair_return,
                      future_bank_rank=future_rank,
                      distinguishing_future_cycles=horizon,
                      future_comparison="final vs initial, propagated under identical future blocks"),
        frame=dict(step_per_cycle=frame_step % GRID, final_angle=frame_angle,
                   relative_final=_complex_record(relative, budget),
                   relative_state_returns=relative == initial,
                   calibration_retained=True, laboratory_reconstruction_verified=calibrated == final,
                   analyzer_transported_probability_verified=moving_probability == p_final),
        history=dict(modeled_cycles=cycles, modeled_channel_applications=steps_per_cycle * cycles,
                     retained_counter_returns=cycles == 0,
                     provenance="declared software protocol exponent, not inferred measurement data",
                     physical_duration=None),
    )
    result["work"] = dict(affine_compositions=budget.compositions,
                          peak_coeff_bits=budget.peak_coeff_bits,
                          max_coeff_bits=max_coeff_bits,
                          method="binary affine composition; coefficient bit cap enforced")
    return result


def _retention(text):
    try:
        return Q(text)
    except (ValueError, ZeroDivisionError) as error:
        raise argparse.ArgumentTypeError("retention must be an exact rational number") from error


def main(argv=None):
    parser = argparse.ArgumentParser(prog="nrqc observer-cycle", description=__doc__)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--velocity", type=int, default=8)
    parser.add_argument("--offset", type=int, default=8)
    parser.add_argument("--retention", type=_retention, default=Q(3, 4))
    parser.add_argument("--steps-per-cycle", type=int, default=4)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--axis", type=int, default=0)
    parser.add_argument("--frame-step", type=int, default=0)
    parser.add_argument("--max-coeff-bits", type=int, default=4096)
    parser.add_argument("--out", type=Path)
    args = vars(parser.parse_args(argv))
    output = args.pop("out")
    try:
        result = audit_cycles(**args)
    except ResourceLimit as error:
        result = dict(schema="nrqc-observer-cycle-v1", status="resource_limit",
                      reason=str(error), hardware_job_id=None)
    except (ValueError, TypeError) as error:
        parser.error(str(error))
    content = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if output:
        output.write_text(content, encoding="utf-8")
    print(content, end="")
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
