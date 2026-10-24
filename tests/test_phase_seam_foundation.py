"""Operational checks for a proposal, not certification of the manuscripts."""
from dataclasses import FrozenInstanceError, replace
from fractions import Fraction as F
from itertools import product
import unittest

from phase_seam_foundation import (Atom, Cell, Config, Operation as Op,
                                   Preparation, Readout as R, ResourceLimit,
                                   verify_history)


class PhaseSeamTests(unittest.TestCase):
    def test_cut_square_and_two_cut_translation_exhaustive(self):
        cfg = Config(grid=8)
        for r, a, b in product(range(8), repeat=3):
            x = Cell.start((r, 0, 0, 0), config=cfg)
            ca, cb = Op("cut", (0, a)), Op("cut", (0, b))
            self.assertEqual(x.apply(ca).apply(ca).state.lifts, x.state.lifts)
            out = x.apply(ca).apply(cb)
            self.assertEqual(out.state.lifts, (r + b - a, 0, 0, 0))
            self.assertEqual(out.phases[0], (r + b - a) % 8)

    def test_original_cut_and_half_grid_axes(self):
        for grid in (4, 8, 64):
            cfg = Config(grid=grid)
            # J(z)=i conjugate(z): theta' = pi/2 - theta.
            for r in range(grid):
                x = Cell.start((r, 0, 0, 0), config=cfg)
                self.assertEqual(x.apply(Op("cut", (0, grid // 4))).phases[0],
                                 (grid // 4 - r) % grid)
                # Adjacent axis indices yield a single phase-bin translation.
                y = x.apply(Op("cut", (0, 0))).apply(Op("cut", (0, 1)))
                self.assertEqual(y.phases[0], (r + 1) % grid)

    def test_seam_fixed_phase_has_zero_declared_cut_cost(self):
        for r, h in product(range(8), repeat=2):
            x = Cell.start((r, 0, 0, 0), config=Config(grid=8))
            y = x.apply(Op("cut", (0, h)))
            fixed = (2 * r - h) % 8 == 0
            self.assertEqual(y.events[-1].charged, not fixed)
            self.assertEqual(y.state.cost, F(0 if fixed else 1))
        # Same phase on the opposite seam ray can have a different lift.
        x = Cell.start((6, 0, 0, 0), config=Config(grid=8))
        y = x.apply(Op("cut", (0, 4)))
        self.assertEqual(x.phases, y.phases)
        self.assertNotEqual(x.state.lifts, y.state.lifts)

    def test_four_mode_permutations_exhaustive(self):
        cfg = Config(grid=8)
        images = set()
        shear = Op("shear", (0, 2, 3, 1))
        for phases in product(range(8), repeat=4):
            x = Cell.start(phases, config=cfg)
            y = x.apply(shear)
            expected = list(phases)
            expected[2] = (expected[2] + 3 * (expected[0] - 1)) % 8
            self.assertEqual(y.phases, tuple(expected))
            images.add(y.phases)
            self.assertEqual(y.apply(shear.inverse()).state.lifts, phases)
        self.assertEqual(len(images), 8**4)

    def test_reversible_operations_restore_lifts_not_erase_records(self):
        x = Cell.start((-9, 7, 3, 1))
        for op in (Op("cut", (1, 4)), Op("shift", (0, -7)),
                   Op("swap", (0, 3)), Op("shear", (2, 1, -5, 3)),
                   Op("pair_cut", (0, 3, 7)), Op("pair_shift", (1, 2, -9))):
            y = x.apply(op).apply(op.inverse())
            self.assertEqual(y.state.lifts, x.state.lifts)
            self.assertEqual(len(y.events), 2)
            self.assertTrue(verify_history(y))

    def test_cut_order_same_cost_different_state(self):
        x = Cell.start((2, 0, 0, 0), config=Config(grid=8))
        a, b = Op("cut", (0, 0)), Op("cut", (0, 1))
        ab, ba = x.apply(a).apply(b), x.apply(b).apply(a)
        self.assertEqual(ab.state.cost, F(3, 2))
        self.assertEqual(ab.state.cost, ba.state.cost)
        self.assertNotEqual(ab.phases, ba.phases)
        self.assertNotEqual(ab.events, ba.events)

    def test_geometric_cost_exact_and_limited_to_chargeable_cuts(self):
        cfg = Config(first_cut_cost=F(3, 7), decay=F(2, 3))
        x = Cell.start((1, 0, 0, 0), config=cfg)
        for n in range(1, 51):
            x = x.apply(Op("cut", (0, 0)))
            self.assertEqual(x.state.cost, cfg.first_cut_cost * (1-cfg.decay**n)/(1-cfg.decay))
            self.assertEqual(x.state.next_cut_cost, cfg.first_cut_cost * cfg.decay**n)
            self.assertEqual(x.state.charged_cuts, n)
        y = x.apply(Op("read", (0, 0))).apply(Op("shift", (1, 1)))
        self.assertEqual(y.state.cost, x.state.cost)
        self.assertEqual(len(y.events), 52)
        self.assertTrue(verify_history(y))

    def test_zero_cost_and_zero_decay_boundary(self):
        for c, q in ((0, F(1, 2)), (1, 0)):
            x = Cell.start((1, 0, 0, 0), config=Config(first_cut_cost=c, decay=q))
            for _ in range(3):
                x = x.apply(Op("cut", (0, 0)))
            self.assertEqual(x.state.cost, F(c))
            self.assertEqual(x.state.charged_cuts, 3)

    def test_winding_lift_is_retained_at_equal_wrapped_phase(self):
        x = Cell.start()
        plus = x.apply(Op("shift", (0, 64)))
        minus = x.apply(Op("shift", (0, -64)))
        self.assertEqual(plus.phases, minus.phases)
        self.assertEqual(plus.winding_lifts[0], 1)
        self.assertEqual(minus.winding_lifts[0], -1)
        self.assertNotEqual(plus.events, minus.events)

    def test_reference_covariance_in_unrestricted_kinematics(self):
        x = Cell.start((3, -7, 1, 12), gamma=F(2, 3))
        delta = 5
        y = Cell.start(tuple(v + delta for v in x.state.lifts), gamma=x.gamma)
        ops = (Op("cut", (0, 7)), Op("shift", (2, -9)),
               Op("shear", (0, 1, 3, 2)), Op("swap", (1, 3)),
               Op("pair_cut", (0, 1, 6)), Op("pair_shift", (2, 3, 8)),
               Op("read", (2, 4)), Op("reset", (0, 1)))
        for op in ops:
            x, y = x.apply(op), y.apply(op.rebase(delta))
            self.assertEqual(y.state.lifts, tuple(v + delta for v in x.state.lifts))
            self.assertEqual(x.events[-1].outcome, y.events[-1].outcome)
            self.assertEqual(x.state.cost, y.state.cost)
            self.assertEqual(x.gamma * x.dual_gamma, 1)

    def test_read_reset_and_lost_preimage(self):
        x = Cell.start((70, 2, 3, 4))
        y = x.apply(Op("read", (0, 2)))
        self.assertEqual(y.state.lifts, x.state.lifts)
        self.assertEqual(y.events[-1].outcome, 4)
        z = y.apply(Op("reset", (0, 2)))
        self.assertEqual(z.state.lifts, (2, 2, 3, 4))
        self.assertEqual(z.events[-1].outcome, 4)
        self.assertEqual(z.events[-1].before.lifts[0], 70)
        other = Cell.start((6, 2, 3, 4)).apply(Op("reset", (0, 2)))
        self.assertEqual(z.state, other.state)
        self.assertNotEqual(z.events[-1].before, other.events[-1].before)
        self.assertTrue(verify_history(z))
        for kind in ("read", "reset"):
            with self.assertRaises(ValueError):
                Op(kind, (0, 0)).inverse()

    def test_closure_sectors_and_phase_identity(self):
        for twist, r in product(range(-4, 5), range(8)):
            x = Cell.start((r, 0, 0, 0), config=Config(grid=8, twist=twist))
            quarter_turns = F(4 * r, 8) + twist
            expected = None
            if quarter_turns.denominator == 1 and quarter_turns.numerator % 2 == 0:
                expected = 1 if quarter_turns.numerator % 4 == 0 else -1
            self.assertEqual(x.closure, expected)
        self.assertEqual(Cell.start((32, 0, 0, 0), config=Config(sector=-1)).closure, -1)
        with self.assertRaises(ValueError):
            Cell.start((1, 0, 0, 0), config=Config(sector=1))

    def test_closed_pair_cut_compensation_exhaustive(self):
        cfg = Config(grid=8, sector=1)
        for a, b, h in product(range(8), repeat=3):
            lifts = (a, b, 0, -a-b)
            x = Cell.start(lifts, config=cfg)
            op = Op("pair_cut", (0, 1, h))
            y = x.apply(op)
            self.assertEqual(sum(y.state.lifts), sum(lifts))
            self.assertEqual(y.closure, 1)
            self.assertEqual(y.apply(op).state.lifts, lifts)
            z = x.apply(op).apply(Op("pair_cut", (0, 1, h+1)))
            self.assertEqual(z.state.lifts, (a+1, b-1, 0, -a-b))
            self.assertEqual(z.state.lifts, x.apply(Op("pair_shift", (0, 1, 1))).state.lifts)

    def test_closure_violation_rejected_without_successor(self):
        x = Cell.start(config=Config(sector=1))
        for op in (Op("shift", (0, 1)), Op("cut", (0, 1)), Op("reset", (0, 1))):
            with self.assertRaisesRegex(ValueError, "closure sector"):
                x.apply(op)
            self.assertEqual(x.events, ())
        self.assertEqual(x.apply(Op("pair_shift", (0, 1, 1))).closure, 1)

    def test_memory_lift_parameter_and_rational_bounds_are_atomic(self):
        x = Cell.start((1, 0, 0, 0), config=Config(max_events=1))
        y = x.apply(Op("cut", (0, 0)))
        with self.assertRaises(ResourceLimit):
            y.apply(Op("read", (0, 0)))
        self.assertEqual(len(y.events), 1)
        x = Cell.start((8, 0, 0, 0), config=Config(grid=8, max_lift=8))
        for op in (Op("shift", (0, 1)), Op("shift", (0, 9)), Op("shear", (0, 1, 2, 0))):
            with self.assertRaises(ResourceLimit):
                x.apply(op)
        x = Cell.start((1, 0, 0, 0), config=Config(rational_bits=3, decay=F(1, 2)))
        y = x.apply(Op("cut", (0, 0))).apply(Op("cut", (0, 0)))
        with self.assertRaises(ResourceLimit):
            y.apply(Op("cut", (0, 0)))
        self.assertEqual(y.state.charged_cuts, 2)
        self.assertTrue(verify_history(y))

    def test_immutable_state_and_tamper_replay(self):
        x = Cell.start((1, 0, 0, 0)).apply(Op("cut", (0, 0))).apply(Op("reset", (0, 2)))
        with self.assertRaises(FrozenInstanceError):
            x.gamma = F(2)
        e = x.events[-1]
        for bad in (replace(e, outcome=12), replace(e, charged=True),
                    replace(e, before=x.initial),
                    replace(e, operation=Op("reset", (0, 3)))):
            self.assertFalse(verify_history(replace(x, events=x.events[:-1] + (bad,))))
        self.assertFalse(verify_history(replace(x, events=x.events[::-1])))
        self.assertFalse(verify_history(replace(x, state=x.initial)))
        self.assertFalse(verify_history(replace(x, initial=replace(x.initial, cost=F(1)))))

    def test_strict_types_and_invalid_inputs(self):
        for kwargs in (dict(grid=True), dict(grid=6), dict(decay=1), dict(decay=-1),
                       dict(first_cut_cost=0.2), dict(first_cut_cost=-1), dict(sector=True)):
            with self.assertRaises((ValueError, TypeError)):
                Config(**kwargs)
        for lifts in ((True, 0, 0, 0), (0.5, 0, 0, 0), (0, 0), [0]*4):
            with self.assertRaises((ValueError, TypeError)):
                Cell.start(lifts)
        for gamma in (0, -1, True, 0.5):
            with self.assertRaises((ValueError, TypeError)):
                Cell.start(gamma=gamma)
        for kind, args in (("born", (0, 1)), ("cut", [0, 1]), ("cut", (0,)), ("cut", (0, True))):
            with self.assertRaises((ValueError, TypeError)):
                Op(kind, args)
        for op in (Op("cut", (-1, 0)), Op("swap", (0, 4)), Op("shear", (0, 0, 2, 0)), Op("pair_cut", (1, 1, 0))):
            with self.assertRaises(ValueError):
                Cell.start().apply(op)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.a = Cell.start()
        self.b = Cell.start((32, 0, 0, 0))
        self.coin = Preparation((Atom(F(1, 3), (self.a,)), Atom(F(2, 3), (self.b,))))

    def test_exact_normalization_and_joint_independent_composition(self):
        d = self.coin.distribution((R(0, 0),))
        self.assertEqual(d, {(0,): F(1, 3), (32,): F(2, 3)})
        joint = self.coin.independent(self.coin)
        self.assertEqual(joint.distribution((R(0, 0), R(1, 0))),
                         {(0, 0): F(1, 9), (0, 32): F(2, 9),
                          (32, 0): F(2, 9), (32, 32): F(4, 9)})
        for prep in (self.coin, self.coin.act(0, Op("cut", (0, 8))), joint):
            self.assertEqual(sum(prep.distribution((R(0, 0),)).values()), 1)

    def test_correlated_preparation_not_assumed_product(self):
        p = Preparation((Atom(F(1, 2), (self.a, self.a)), Atom(F(1, 2), (self.b, self.b))))
        self.assertEqual(p.distribution((R(0, 0), R(1, 0))), {(0, 0): F(1, 2), (32, 32): F(1, 2)})
        self.assertEqual(p.chsh((R(0, 0), R(0, 0)), (R(1, 0), R(1, 0))), ((F(1),)*4, F(2)))

    def test_local_operations_and_settings_do_not_signal(self):
        p = Preparation((Atom(F(1, 2), (self.a, self.a)), Atom(F(1, 2), (self.b, self.b))))
        marginal = p.distribution((R(0, 0),))
        for op in (Op("cut", (0, 8)), Op("reset", (0, 9)), Op("shear", (1, 0, 2, 1))):
            self.assertEqual(p.act(1, op).distribution((R(0, 0),)), marginal)
        for setting in (0, 1, 32, 63):
            d = p.distribution((R(0, 0), R(1, 0, setting)))
            recovered = {}
            for (a, _), w in d.items():
                recovered[(a,)] = recovered.get((a,), F(0)) + w
            self.assertEqual(recovered, marginal)

    def test_all_16_binary_local_assignments_chsh_bound(self):
        values = set()
        for a0, a1, b0, b1 in product((-1, 1), repeat=4):
            s = a0*b0 + a0*b1 + a1*b0 - a1*b1
            self.assertEqual(abs(s), 2)
            values.add(s)
        self.assertEqual(values, {-2, 2})

    def test_chsh_all_4096_setting_quadruples_at_grid8(self):
        cfg = Config(grid=8)
        atoms = tuple(Atom(F(1, 8), (Cell.start((r, 0, 0, 0), config=cfg),
                                    Cell.start((r, 0, 0, 0), config=cfg))) for r in range(8))
        p = Preparation(atoms)
        observed = set()
        for a, ap, b, bp in product(range(8), repeat=4):
            _, s = p.chsh((R(0, 0, a), R(0, 0, ap)), (R(1, 0, b), R(1, 0, bp)))
            self.assertLessEqual(abs(s), 2)
            observed.add(s)
        self.assertEqual(max(observed), 2)
        self.assertEqual(min(observed), -2)

    def test_no_silent_normalization_or_invalid_preparations(self):
        for weights in ((F(1, 3), F(1, 3)), (F(-1), F(2)), (0, 1), (0.5, 0.5)):
            with self.assertRaises((TypeError, ValueError)):
                Preparation(tuple(Atom(w, (self.a,)) for w in weights))
        with self.assertRaises(ValueError):
            Preparation((Atom(F(1, 2), (self.a,)), Atom(F(1, 2), (Cell.start(config=Config(grid=8)),))))
        forged = replace(self.b, state=self.a.state)
        with self.assertRaises(ValueError):
            Preparation((Atom(F(1), (forged,)),))

    def test_joint_bounds_and_failed_branch_do_not_postselect(self):
        atom = Atom(F(1, 65), (self.a,))
        p = Preparation((atom,) * 65)
        with self.assertRaises(ResourceLimit):
            p.independent(p)
        p = Preparation((Atom(F(1), (self.a,) * 16),))
        with self.assertRaises(ResourceLimit):
            p.independent(self.coin)
        cfg = Config(grid=8, max_lift=8)
        p = Preparation((Atom(F(1, 2), (Cell.start(config=cfg),)),
                         Atom(F(1, 2), (Cell.start((8, 0, 0, 0), config=cfg),))))
        before = p.distribution((R(0, 0),))
        with self.assertRaises(ResourceLimit):
            p.act(0, Op("shift", (0, 1)))
        self.assertEqual(p.distribution((R(0, 0),)), before)

    def test_measurement_validation(self):
        for reads in ((R(-1, 0),), (R(1, 0),), (), (R(0, 0),)*65):
            with self.assertRaises(ValueError):
                self.coin.distribution(reads)
        with self.assertRaises(ValueError):
            self.coin.chsh((R(0, 0), R(0, 1)), (R(0, 0), R(0, 1)))

    def test_external_universal_conjugation_guard(self):
        from phase_seam_foundation.qualification import transpose_guard
        guard = transpose_guard()
        matrix = [[F(x) for x in row] for row in guard['partial_transpose']]
        # Partial transpose of |Phi+><Phi+| is one half of the swap matrix.
        for i, j in product(range(4), repeat=2):
            swapped = (i % 2) * 2 + i // 2
            self.assertEqual(matrix[i][j], F(int(j == swapped), 2))
        self.assertEqual(sum(matrix[i][i] for i in range(4)), 1)
        self.assertEqual(F(guard['normalized_negative_expectation']), F(-1, 2))


if __name__ == "__main__":
    unittest.main()
