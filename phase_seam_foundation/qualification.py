"""Reproducible examples and an external Hilbert-recovery compatibility check."""
from fractions import Fraction as F
from itertools import product

from .model import Atom, Cell, Config, Operation as Op, Preparation, Readout as R, verify_history


def transpose_guard():
    """Conditional guard: universal conjugation is not a local quantum channel.

    This matrix diagnostic is NOT used by the native phase-cell interpreter.
    The input is a two-qubit Bell density matrix. Transpose its first subsystem
    and evaluate the antisymmetric vector (0,1,-1,0), normalized via its norm^2.
    """
    rho = [[F(int(i in (0, 3) and j in (0, 3)), 2) for j in range(4)] for i in range(4)]
    pt = [[F(0) for _ in range(4)] for _ in range(4)]
    for a, b, c, d in product(range(2), repeat=4):
        pt[2*c+b][2*a+d] = rho[2*a+b][2*c+d]
    v = (0, 1, -1, 0)
    witness = sum(v[i] * pt[i][j] * v[j] for i, j in product(range(4), repeat=2)) / F(2)
    return dict(assumption="cut identified with universal conjugation of unknown quantum amplitudes",
                partial_transpose=[[str(x) for x in row] for row in pt],
                normalized_negative_expectation=str(witness),
                conclusion="not completely positive under this identification",
                scope="does not prohibit classical phase reflection or a restricted-state encoding")


def report():
    x = Cell.start((2, 0, 0, 0), config=Config(grid=8))
    a, b = Op("cut", (0, 0)), Op("cut", (0, 1))
    ab, ba = x.apply(a).apply(b), x.apply(b).apply(a)
    closed = Cell.start((2, 1, 0, -3), config=Config(grid=8, sector=1))
    moved = closed.apply(Op("pair_cut", (0, 1, 0))).apply(Op("pair_cut", (0, 1, 1)))
    reset = Cell.start((70, 2, 3, 4)).apply(Op("reset", (0, 2)))
    loop = Cell.start().apply(Op("shift", (0, 64)))
    lo, hi = Cell.start(), Cell.start((32, 0, 0, 0))
    joint = Preparation((Atom(F(1, 2), (lo, lo)), Atom(F(1, 2), (hi, hi))))
    correlations, s = joint.chsh((R(0, 0), R(0, 0)), (R(1, 0), R(1, 0)))
    return dict(
        schema="phase-seam-foundation-v0.1",
        status="finite classical operational proposal; quantum recovery and hardware realization open",
        default_cell=dict(modes=4,phase_bins=64,phase_step_degrees="45/8",
                          cut_axis_step_degrees="45/16",max_events=1024,max_lift=2**31-1,
                          rational_bits=4096,closure_sector="unrestricted unless explicitly selected"),
        cut_order=dict(initial=list(x.state.lifts),order_a_b=list(ab.state.lifts),
                       order_b_a=list(ba.state.lifts),same_cost=str(ab.state.cost),
                       charged_cuts=ab.state.charged_cuts,history_verified=verify_history(ab) and verify_history(ba)),
        closure_preserving_pair=dict(initial=list(closed.state.lifts),final=list(moved.state.lifts),
                                     initial_sum=sum(closed.state.lifts),final_sum=sum(moved.state.lifts),
                                     closure_sign=moved.closure,history_verified=verify_history(moved)),
        winding=dict(wrapped=list(loop.phases),lifts=list(loop.state.lifts),
                     algebraic_winding=list(loop.winding_lifts),physical_path_inferred=False),
        reset=dict(outcome=reset.events[-1].outcome,before=list(reset.events[-1].before.lifts),
                   after=list(reset.state.lifts),history_verified=verify_history(reset)),
        joint_readout=dict(probabilities={','.join(map(str,k)):str(v) for k,v in joint.distribution((R(0,0),R(1,0))).items()},
                           total="1",correlations=list(map(str,correlations)),CHSH=str(s),
                           general_local_bound="2",bound_assumptions="positive setting-independent preparation and local response, no postselection"),
        hilbert_recovery_guard=transpose_guard(),
        not_established=["Born rule from winding", "nonlocal quantum joint composition",
                         "time-tensor closure/uniqueness", "physical cut/coupling/readout laws",
                         "energy units or fixed-point attraction", "quantum advantage or physical qubit count"])
