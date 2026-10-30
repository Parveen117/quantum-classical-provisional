"""Integer basis oracles, coherent amplitudes, closure and resource boundaries."""
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import random
import unittest

from native_relational_qc.exact import INV_SQRT2, IMAG
from native_relational_qc.phase_backend import Phase64Circuit, prepare
from phase_seam_foundation.model import Cell, Config, Operation as O, ResourceLimit, closure_sign
from phase_seam_foundation.register import (
    compile_register, verify_program, bind_cell, verify_transition)


def basis_run(gates, label):
    # Separate bit-array interpretation, no source transform or native engine.
    bits = [(label >> q) & 1 for q in range(64)]
    for name, qs in gates:
        if name == "x": bits[qs[0]] ^= 1
        elif name == "cx": bits[qs[1]] ^= bits[qs[0]]
        elif name == "ccx": bits[qs[2]] ^= bits[qs[0]] & bits[qs[1]]
        else: raise AssertionError("unexpected gate")
    return sum(bit << q for q, bit in enumerate(bits))


def expected(phases, word, grid):
    # Existing v0.1 Cell is the independent operational reference.
    cell = Cell.start(phases, config=Config(grid=grid))
    for op in word: cell = cell.apply(op)
    return cell.phases


class RegisterBasisTests(unittest.TestCase):
    def check_labels(self, program, labels):
        for phases in labels:
            before = program.pack(phases)
            after = basis_run(program.gates, before)
            target = expected(phases, program.operations, program.config.grid)
            self.assertEqual(program.unpack(after), target)  # also asserts scratch=0
            self.assertEqual(program.image(phases), target)
            self.assertEqual(basis_run(tuple(reversed(program.gates)), after), before)

    def test_every_grid4_phase_tuple_for_generators_and_composition(self):
        words = [(O("cut", (j, h)),) for j in range(4) for h in range(4)]
        words += [(O("pair_cut", (j, s, h)),) for j in range(4)
                  for s in range(4) if j != s for h in (0, 3)]
        words += [(O("shift", (3, -3)),), (O("pair_shift", (3, 1, 7)),),
                  (O("swap", (0, 3)),), (O("swap", (2, 2)),),
                  (O("shear", (3, 0, -3, 2)),),
                  (O("cut", (0, 1)), O("shear", (0, 3, 3, -1)),
                   O("pair_cut", (3, 1, 2)), O("swap", (0, 2)))]
        for word in words:
            self.check_labels(compile_register(word, config=Config(grid=4)), product(range(4), repeat=4))

    def test_all_grid64_active_pairs_for_balanced_cut_and_shear(self):
        for op in (O("pair_cut", (0, 2, 7)), O("shear", (0, 2, -3, 5))):
            p = compile_register((op,))
            self.check_labels(p, ((x, 9, y, 41) for x in range(64) for y in range(64)))

    def test_every_grid64_axis_and_phase_for_cut(self):
        for h in range(64):
            p = compile_register((O("cut", (0, h)),))
            self.check_labels(p, ((x, 3, 7, 11) for x in range(64)))

    def test_supported_widths_and_negative_large_parameters(self):
        rng = random.Random(20261024)
        word = (O("shift", (1, -10001)), O("pair_cut", (3, 1, -4097)),
                O("shear", (1, 2, 4099, -133)), O("swap", (0, 3)))
        for width in range(2, 13):
            grid = 1 << width
            p = compile_register(word, config=Config(grid=grid))
            self.assertTrue(verify_program(p))
            self.check_labels(p, [tuple(rng.randrange(grid) for _ in range(4)) for _ in range(12)])

    def test_source_inverse_composes_to_identity(self):
        word = (O("cut", (1, 13)), O("shear", (1, 2, -7, 9)),
                O("pair_shift", (3, 0, -8)), O("pair_cut", (0, 2, 19)))
        p = compile_register(word + tuple(op.inverse() for op in reversed(word)))
        self.assertEqual(p.matrix, tuple(tuple(int(i==j) for j in range(4)) for i in range(4)))
        self.assertEqual(p.offset, (0, 0, 0, 0))
        self.check_labels(p, ((x, 3*x % 64, 7*x % 64, 63-x) for x in range(64)))

    def test_dirty_scratch_changes_promise_but_inverse_still_restores(self):
        p = compile_register((O("shear", (0, 1, 1, 0)),))
        found = False
        for x, y in product(range(8), repeat=2):
            clean = p.pack((x, y, 0, 0)); dirty = clean | (1 << p.scratch[0])
            output = basis_run(p.gates, dirty)
            self.assertEqual(basis_run(tuple(reversed(p.gates)), output), dirty)
            ideal = p.pack(p.image((x, y, 0, 0))) | (1 << p.scratch[0])
            found |= output != ideal
        self.assertTrue(found)


class RegisterCoherentTests(unittest.TestCase):
    def test_complex_superposition_preserved_by_balanced_cut_and_inverse(self):
        p = compile_register((O("pair_cut", (0, 2, 0)),), config=Config(sector=1))
        # Closure-preserving pair of labels 0 and (1,0,63,0), with relative i.
        c = Phase64Circuit(p.n_qubits).add("h", 0).add("s", 0)
        for q in p.registers[2]: c.add("cx", 0, q)
        initial = prepare(c).amplitudes
        for name, qs in p.to_circuit().operations: c.add(name, *qs)
        actual = prepare(c).amplitudes
        field = c.field
        self.assertEqual(actual, {p.pack((0,0,0,0)):field(INV_SQRT2),
                                  p.pack((63,0,1,0)):field(IMAG*INV_SQRT2)})
        for name, qs in p.to_circuit(inverse=True).operations: c.add(name, *qs)
        self.assertEqual(prepare(c).amplitudes, initial)
        # Undo preparation: coherence gives deterministic all-zero, not a mixture.
        for q in reversed(p.registers[2]): c.add("cx", 0, q)
        c.add("sdg", 0).add("h", 0)
        self.assertEqual(prepare(c).amplitudes, {0:field(1)})

    def test_entangled_external_reference_and_full_phase_retention(self):
        p = compile_register((O("cut", (0, 5)), O("shear", (0, 1, 3, -1))))
        reference = p.n_qubits
        c = Phase64Circuit(reference+1).add("h", reference).add("p64", reference).add("cx", reference, 0)
        before = prepare(c).amplitudes
        for name, qs in p.gates: c.add(name, *qs)
        expected_state = {}
        for label, amplitude in before.items():
            phase_label = label & ((1 << (4*p.width))-1)
            out = p.pack(p.image(p.unpack(phase_label))) | (label & (1 << reference))
            expected_state[out] = amplitude
        self.assertEqual(prepare(c).amplitudes, expected_state)


class RegisterContractTests(unittest.TestCase):
    def test_all_grid4_closed_inputs_signs_twists_and_each_prefix(self):
        word = (O("pair_cut", (0, 3, 3)), O("pair_shift", (1, 2, -1)), O("swap", (0, 2)))
        for sign in (-1, 1):
            for twist in range(4):
                cfg = Config(grid=4, sector=sign, twist=twist)
                p = compile_register(word, config=cfg)
                states = [x for x in product(range(4), repeat=4) if closure_sign(x,4,twist)==sign]
                self.assertEqual(len(states), 64)
                for x in states:
                    transition = bind_cell(Cell.start(x, config=cfg), p)
                    self.assertTrue(verify_transition(transition))
                    self.assertEqual(transition.after.closure, sign)

    def test_state_specific_closure_is_not_whole_sector_contract(self):
        cfg = Config(sector=1)
        op = O("cut", (0, 0))
        self.assertEqual(Cell.start(config=cfg).apply(op).closure, 1)
        with self.assertRaisesRegex(ValueError, "whole required closure sector"):
            compile_register((op,), config=cfg)
        # Net identity is not enough: the first native boundary leaves the sector.
        with self.assertRaises(ValueError):
            compile_register((O("shift", (0, 1)), O("shift", (0, -1))), config=cfg)
        self.assertTrue(verify_program(compile_register((O("shift", (0,64)),), config=cfg)))

    def test_old_channel_counterexample_is_now_distinct_orthogonal_labels(self):
        cfg = Config(sector=1)
        p = compile_register((O("pair_cut", (0, 2, 0)),), config=cfg)
        a = Cell.start(config=cfg); b = Cell.start((16,-16,0,0), config=cfg)
        self.assertNotEqual(p.pack(a.phases), p.pack(b.phases))
        self.assertEqual(bind_cell(a,p).after.phases, (0,0,0,0))
        self.assertEqual(bind_cell(b,p).after.phases, (48,48,32,0))
        self.assertNotEqual(basis_run(p.gates,p.pack(a.phases)),basis_run(p.gates,p.pack(b.phases)))

    def test_cell_gamma_winding_cost_and_history_retained_without_new_codec(self):
        cell = Cell.start((65,0,-1,0), config=Config(sector=1), gamma=F(2,3))
        cell = cell.apply(O("read", (0, 2)))
        p = compile_register((O("pair_cut", (0,2,0)),)*2, config=cell.config)
        t = bind_cell(cell,p)
        self.assertEqual(t.after.state.lifts, cell.state.lifts)
        self.assertEqual(t.after.gamma, F(2,3))
        self.assertEqual(t.after.state.cost, F(3,2))
        self.assertEqual(len(t.after.events), 3)
        self.assertTrue(verify_transition(t))
        other = Cell.start((1,0,63,0), config=cell.config, gamma=cell.gamma)
        self.assertEqual(p.pack(other.phases), p.pack(cell.phases))
        self.assertNotEqual(other.winding_lifts, cell.winding_lifts)

    def test_cell_lift_event_and_rational_limits_still_apply(self):
        for cfg, word, phases in (
            (Config(max_lift=64), (O("shift",(0,1)),), (64,0,0,0)),
            (Config(max_events=1), (O("shift",(0,1)),), (0,0,0,0)),
            (Config(rational_bits=2), (O("cut",(0,1)),)*3, (0,0,0,0))):
            cell = Cell.start(phases, config=cfg)
            if cfg.max_events==1: cell=cell.apply(O("read",(0,0)))
            p=compile_register(word,config=cfg)
            with self.assertRaises(ResourceLimit): bind_cell(cell,p)
            self.assertEqual(cell.state.lifts, phases)

    def test_tampered_gates_affine_operations_and_transition_rejected(self):
        p = compile_register((O("pair_cut", (0,2,7)),))
        variants = [replace(p,gates=p.gates[:-1]), replace(p,offset=(1,0,0,0)),
                    replace(p,operations=(O("pair_cut",(0,2,8)),)),
                    replace(p,gates=(("x",(True,)),)),
                    replace(p,matrix=((True,0,0,0),)+p.matrix[1:]),
                    replace(p,gates=(("cx",(0,0)),))]
        for v in variants:
            self.assertFalse(verify_program(v))
            with self.assertRaises(ValueError): v.to_circuit()
        t = bind_cell(Cell.start(),p)
        self.assertFalse(verify_transition(replace(t,after=Cell.start())))
        self.assertFalse(verify_transition(replace(t,program=variants[0])))

    def test_strict_inputs_grid_caps_indices_and_no_reset_fallback(self):
        for word in ([], (1,), (O("cut",(4,0)),), (O("pair_cut",(0,0,0)),),
                     (O("read",(0,0)),), (O("reset",(0,0)),)):
            with self.assertRaises((TypeError,ValueError)): compile_register(word)
        with self.assertRaises(ValueError): compile_register((),config=Config(grid=12))
        with self.assertRaises(TypeError): compile_register((),max_gates=True)
        with self.assertRaises(ResourceLimit): compile_register((O("cut",(0,0)),),max_gates=0)
        with self.assertRaises(ResourceLimit):
            compile_register((O("shift",(0,65)),),config=Config(max_lift=64))
        with self.assertRaises(ResourceLimit):
            compile_register((O("shift",(0,1)),)*2,config=Config(max_events=1))
        p=compile_register(())
        for labels in ((True,0,0,0),(64,0,0,0),[0,0,0,0]):
            with self.assertRaises((TypeError,ValueError)): p.pack(labels)
        with self.assertRaises(ValueError): p.unpack(1 << (4*p.width))
        with self.assertRaises(TypeError): p.unpack(True)
        with self.assertRaises(ValueError): bind_cell(Cell.start(config=Config(grid=4)),p)

    def test_resource_accounting_and_fresh_circuit_isolation(self):
        p=compile_register((O("pair_cut",(0,2,0)),))
        r=p.resources()
        self.assertEqual((r["phase_bits"],r["clean_scratch_bits"],r["total_logical_wires"]),(24,4,28))
        self.assertEqual(r["fixed_sector_information_bits"],18)
        a=p.to_circuit(); b=p.to_circuit(); a.add("x",0)
        self.assertNotEqual(a.operations,b.operations)
        self.assertTrue(verify_program(p))


if __name__ == "__main__": unittest.main()
