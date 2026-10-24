"""Reduced closure coordinates checked against the original four-mode model."""
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import random
import unittest

from native_relational_qc.phase_backend import Phase64Circuit, prepare
from phase_seam_foundation.model import Cell, Config, Operation as O, ResourceLimit, closure_sign
from phase_seam_foundation.register import compile_register, closure_codec, verify_program, bind_cell, verify_transition


def basis_run(gates, label):
    # Independent bit interpretation, no compiler arithmetic or phase engine.
    for name, wires in gates:
        if name == "x": label ^= 1 << wires[0]
        elif name == "cx": label ^= ((label >> wires[0]) & 1) << wires[1]
        elif name == "ccx": label ^= (((label >> wires[0]) & 1) & ((label >> wires[1]) & 1)) << wires[2]
        else: raise AssertionError("unexpected gate")
    return label


def target(cfg):
    return ((cfg.grid//2 if cfg.sector == -1 else 0)-cfg.grid//4*cfg.twist) % cfg.grid


def phase_tuple(values, omitted, cfg):
    it = iter(values)
    out = [0 if j == omitted else next(it) for j in range(4)]
    out[omitted] = (target(cfg)-sum(out)) % cfg.grid
    return tuple(out)


def source_image(phases, operations, cfg):
    cell = Cell.start(phases, config=cfg)
    for op in operations: cell = cell.apply(op)
    return cell.phases


class SectorBasisTests(unittest.TestCase):
    def test_all_grid4_generators_on_all_sector_labels_each_omission(self):
        cfg = Config(grid=4,sector=1)
        words = [(O("pair_cut",(j,s,h)),) for j in range(4) for s in range(4) if j!=s for h in range(4)]
        words += [(O("pair_shift",(j,s,3)),) for j in range(4) for s in range(4) if j!=s]
        words += [(O("swap",(j,s)),) for j in range(4) for s in range(j,4)]
        words += [(O("shift",(j,-8)),) for j in range(4)]
        words += [(O("shear",(j,s,8,-2)),) for j in range(4) for s in range(4) if j!=s]
        self.assertEqual(len(words),86)
        for omitted in range(4):
            for word in words:
                p = compile_register(word,config=cfg,omit_mode=omitted)
                rows, offset = p.stored_affine()
                kept = tuple(m for m in range(4) if m != omitted)
                for values in product(range(4),repeat=3):
                    x = phase_tuple(values,omitted,cfg)
                    inp = p.pack(x); out = basis_run(p.gates,inp)
                    self.assertEqual(p.unpack(out),source_image(x,word,cfg))
                    self.assertEqual(p.image(x),p.unpack(out))
                    stored_image = tuple((sum(a*v for a,v in zip(row,values))+b)%4 for row,b in zip(rows,offset))
                    self.assertEqual(stored_image,tuple(p.unpack(out)[m] for m in kept))
                    self.assertEqual(basis_run(tuple(reversed(p.gates)),out),inp)

    def test_all_grid8_labels_signs_twists_and_composed_words(self):
        word = (O("pair_cut",(0,3,-5)), O("pair_shift",(1,2,3)),
                O("swap",(0,2)), O("pair_cut",(3,1,9)))
        for sign,twist,omitted in product((-1,1),range(4),range(4)):
            cfg = Config(grid=8,sector=sign,twist=twist)
            p = compile_register(word,config=cfg,omit_mode=omitted)
            for values in product(range(8),repeat=3):
                x = phase_tuple(values,omitted,cfg)
                self.assertEqual(p.unpack(p.pack(x)),x)
                y = p.unpack(basis_run(p.gates,p.pack(x)))
                self.assertEqual(y,source_image(x,word,cfg))
                self.assertEqual(closure_sign(y,8,twist),sign)

    def test_grid64_all_active_pairs_for_each_omission(self):
        cfg = Config(sector=-1,twist=3)
        word = (O("pair_cut",(0,2,7)),O("swap",(0,3)),O("pair_shift",(1,2,-9)))
        for omitted in range(4):
            p=compile_register(word,config=cfg,omit_mode=omitted)
            for a,b in product(range(64),repeat=2):
                x=phase_tuple((a,b,17),omitted,cfg)
                self.assertEqual(p.unpack(basis_run(p.gates,p.pack(x))),source_image(x,word,cfg))

    def test_all_supported_widths_and_source_inverses(self):
        rng = random.Random(2056)
        word = (O("pair_cut",(3,0,-101)),O("swap",(1,3)),O("pair_shift",(2,0,999)))
        inverse = tuple(o.inverse() for o in reversed(word))
        for width,omitted in product(range(2,13),range(4)):
            cfg=Config(grid=1<<width,sector=-1,twist=-7)
            p=compile_register(word,config=cfg,omit_mode=omitted)
            undo=compile_register(inverse,config=cfg,omit_mode=omitted)
            for _ in range(8):
                x=phase_tuple(tuple(rng.randrange(cfg.grid) for _ in range(3)),omitted,cfg)
                out=basis_run(p.gates,p.pack(x))
                self.assertEqual(p.unpack(out),source_image(x,word,cfg))
                self.assertEqual(basis_run(undo.gates,out),p.pack(x))

    def test_scratch_really_needed_and_never_silently_reset(self):
        cfg=Config(sector=1)
        p=compile_register((O("swap",(0,3)),),config=cfg,omit_mode=3)
        found=False
        for a,b in product(range(8),repeat=2):
            x=phase_tuple((a,b,5),3,cfg)
            dirty=p.pack(x)|(1<<p.scratch[0])
            out=basis_run(p.gates,dirty)
            self.assertEqual(basis_run(tuple(reversed(p.gates)),out),dirty)
            found |= out != (p.pack(p.image(x))|(1<<p.scratch[0]))
        self.assertTrue(found)


class ClosureCodecTests(unittest.TestCase):
    def test_all_grid4_full_inputs_syndrome_retention_and_inverse(self):
        # Also off-sector inputs: no hidden projection or discarding.
        for sign,twist,omitted in product((-1,1),range(4),range(4)):
            cfg=Config(grid=4,sector=sign,twist=twist)
            full=compile_register((),config=cfg)
            codec=closure_codec(cfg,omitted); inverse=closure_codec(cfg,omitted,inverse=True)
            for x in product(range(4),repeat=4):
                label=full.pack(x); out=basis_run(codec.operations,label)
                actual=full.unpack(out)
                expect=list(x); expect[omitted]=(sum(x)-target(cfg))%4
                self.assertEqual(actual,tuple(expect))
                self.assertEqual(basis_run(inverse.operations,out),label)
                self.assertEqual(actual[omitted]==0,closure_sign(x,4,twist)==sign)

    def test_grid64_codec_roundtrip_for_all_single_register_values(self):
        cfg=Config(sector=-1,twist=-2)
        full=compile_register((),config=cfg)
        for omitted in range(4):
            c=closure_codec(cfg,omitted)
            for mode,x in product(range(4),range(64)):
                values=[5,11,23,47];values[mode]=x
                label=full.pack(tuple(values));out=basis_run(c.operations,label)
                expected=list(values);expected[omitted]=(sum(values)-target(cfg))%64
                self.assertEqual(full.unpack(out),tuple(expected))
                self.assertEqual(basis_run(tuple(reversed(c.operations)),out),label)

    def test_coherent_full_compress_apply_expand_equals_full_operation(self):
        cfg=Config(sector=-1,twist=1)
        word=(O("pair_cut",(0,2,7)),O("swap",(0,3)),O("pair_shift",(3,1,-5)))
        full=compile_register(word,config=cfg)
        for omitted in range(4):
            reduced=compile_register(word,config=cfg,omit_mode=omitted)
            # Prepare three independent coherent bits, an external reference,
            # and the dependent fourth phase using inverse codec.
            ref=full.n_qubits
            c=Phase64Circuit(ref+1)
            kept=[m for m in range(4) if m!=omitted]
            for i,m in enumerate(kept):
                q=full.registers[m][0];c.add("h",q).add("p64",q)
                if i==0:c.add("cx",q,ref)
            for name,qs in closure_codec(cfg,omitted,inverse=True).operations:c.add(name,*qs)
            prepared=prepare(c).amplitudes
            # Direct full execution on the same initial state.
            direct=Phase64Circuit(ref+1)
            for name,qs in c.operations+full.gates:direct.add(name,*qs)
            expected=prepare(direct).amplitudes
            for name,qs in closure_codec(cfg,omitted).operations:c.add(name,*qs)
            compressed=prepare(c)
            self.assertEqual(compressed.probability({q:0 for q in full.registers[omitted]}),c.field(1))
            mapping={r:q for m in kept for r,q in zip(reduced.registers[m],full.registers[m])}
            mapping.update(zip(reduced.scratch,full.scratch))
            for name,qs in reduced.gates:c.add(name,*(mapping[q] for q in qs))
            for name,qs in closure_codec(cfg,omitted,inverse=True).operations:c.add(name,*qs)
            self.assertEqual(prepare(c).amplitudes,expected)
            for name,qs in full.to_circuit(inverse=True).operations:c.add(name,*qs)
            self.assertEqual(prepare(c).amplitudes,prepared)

    def test_codec_guards(self):
        for cfg,omitted in ((Config(),3),(Config(grid=12,sector=1),3),(Config(sector=1),None),
                            (Config(sector=1),True),(Config(sector=1),4)):
            with self.assertRaises((ValueError,TypeError)):closure_codec(cfg,omitted)
        with self.assertRaises(TypeError):closure_codec(Config(sector=1),3,inverse=1)
        with self.assertRaises(TypeError):closure_codec(Config(sector=1),3,max_gates=False)
        with self.assertRaises(ResourceLimit):closure_codec(Config(sector=1),3,max_gates=1)


class SectorContractTests(unittest.TestCase):
    def test_compressed_execution_retains_phase_and_interference(self):
        # Direct execution with only 22 wires, no hidden fourth register.
        cfg=Config(sector=1)
        p=compile_register((O("pair_cut",(0,2,0)),),config=cfg,omit_mode=2)
        c=Phase64Circuit(p.n_qubits).add("h",p.registers[0][0]).add("p64",p.registers[0][0])
        before=prepare(c).amplitudes
        for name,qs in p.gates:c.add(name,*qs)
        expected={p.pack(p.image(p.unpack(k))):v for k,v in before.items()}
        self.assertEqual(prepare(c).amplitudes,expected)
        for name,qs in p.to_circuit(inverse=True).operations:c.add(name,*qs)
        c.add("p64dg",p.registers[0][0]).add("h",p.registers[0][0])
        self.assertEqual(prepare(c).amplitudes,{0:c.field(1)})
        self.assertEqual(c.n_qubits,22)

    def test_source_cell_cost_winding_and_history_stay_external(self):
        cfg=Config(sector=1)
        cell=Cell.start((65,0,-1,0),config=cfg,gamma=F(3,7)).apply(O("read",(0,2)))
        word=(O("pair_cut",(0,2,0)),)*2
        for omitted in range(4):
            p=compile_register(word,config=cfg,omit_mode=omitted)
            t=bind_cell(cell,p)
            self.assertTrue(verify_transition(t))
            self.assertEqual(t.after.state.lifts,cell.state.lifts)
            self.assertEqual(t.after.gamma,F(3,7))
            self.assertEqual(t.after.state.cost,F(3,2))
            self.assertEqual(len(t.after.events),3)
            self.assertEqual(p.unpack(p.pack(t.after.phases)),t.after.phases)

    def test_reject_unfixed_sector_invalid_omission_and_cross_sector_labels(self):
        with self.assertRaises(ValueError):compile_register((),omit_mode=3)
        for omitted in (True,False,4,-1,1.0,"3"):
            with self.assertRaises((ValueError,TypeError)):compile_register((),config=Config(sector=1),omit_mode=omitted)
        p=compile_register((),config=Config(sector=1),omit_mode=3)
        with self.assertRaises(ValueError):p.pack((0,0,0,1))
        with self.assertRaises(ValueError):p.unpack(1<<18)
        with self.assertRaises(ValueError):compile_register((O("cut",(0,0)),),config=p.config,omit_mode=3)
        with self.assertRaises(ValueError):compile_register((O("shift",(0,1)),O("shift",(0,-1))),config=p.config,omit_mode=3)
        for kind in ("read","reset"):
            with self.assertRaises(ValueError):compile_register((O(kind,(0,0)),),config=p.config,omit_mode=3)

    def test_gate_cap_native_resource_failures_and_tampering(self):
        cfg=Config(sector=1)
        p=compile_register((O("pair_cut",(0,2,0)),),config=cfg,omit_mode=2)
        for cap in (0,len(p.gates)-1):
            with self.assertRaises(ResourceLimit):compile_register(p.operations,config=cfg,omit_mode=2,max_gates=cap)
        self.assertTrue(verify_program(compile_register(p.operations,config=cfg,omit_mode=2,max_gates=len(p.gates))))
        for v in (replace(p,omit_mode=0),replace(p,omit_mode=True),replace(p,omit_mode=None),
                  replace(p,gates=p.gates[:-1]),replace(p,offset=(1,0,0,0)),
                  replace(p,config=Config()),replace(p,gates=(("x",(22,)),))):
            self.assertFalse(verify_program(v))
            with self.assertRaises(ValueError):v.to_circuit()
        limited=Config(sector=1,max_lift=64)
        large=compile_register((O("pair_shift",(0,2,1)),),config=limited,omit_mode=2)
        with self.assertRaises(ResourceLimit):bind_cell(Cell.start((64,0,-64,0),config=limited),large)

    def test_wire_gate_counts_and_full_layout_compatibility(self):
        cfg=Config(sector=1);word=(O("pair_cut",(0,2,0)),)
        full=compile_register(word,config=cfg)
        reduced=compile_register(word,config=cfg,omit_mode=2)
        self.assertEqual(full.resources()["total_logical_wires"],28)
        self.assertEqual(len(full.gates),59)
        self.assertEqual((reduced.phase_bits,len(reduced.scratch),reduced.n_qubits),(18,4,22))
        self.assertEqual(len(reduced.gates),24)
        self.assertEqual(reduced.registers[2],())
        self.assertEqual(reduced.resources()["encoded_phase_labels"],64**3)
        self.assertTrue(reduced.resources()["compressed_sector_layout_implemented"])
        self.assertFalse(full.resources()["compressed_sector_layout_implemented"])


if __name__ == "__main__":unittest.main()
