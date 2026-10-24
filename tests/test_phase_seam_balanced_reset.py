"""Explicit reservoir reset: source lift law, sector code and coherent records."""
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import random
import unittest

from native_relational_qc.dynamic import DynamicCircuit, probability, expectation
from native_relational_qc.phase_backend import Phase64Circuit, prepare
from phase_seam_foundation.model import Cell, Config, Operation as O, ResourceLimit, closure_sign, verify_history
from phase_seam_foundation.controller import compile_controller, bind_controller, verify_controller, verify_controller_transition
from phase_seam_foundation.register import compile_register, closure_codec
from test_phase_seam_controller import basis_run, reduced_density


def image(x,j,reservoir,a,grid):
    # Independent direct formula, no Cell or compiler call.
    y=list(x);r=(x[j]-a)%grid
    y[j]=a%grid;y[reservoir]=(x[reservoir]+r)%grid
    return tuple(y),r


class BalancedResetSourceTests(unittest.TestCase):
    def test_integer_sum_gamma_and_cost_history_are_retained(self):
        for grid in (4,12,64):
            for sign,twist in product((-1,0,1),range(4)):
                cfg=Config(grid=grid,sector=sign,twist=twist)
                s=((grid//2 if sign==-1 else 0)-grid//4*twist)%grid
                cell=Cell.start((grid+1,-1,s,0),config=cfg,gamma=F(3,7))
                cell=cell.apply(O("pair_cut",(0,1,3)))
                out=cell.apply(O("pair_reset",(0,2,-5)))
                self.assertEqual(sum(out.state.lifts),sum(cell.state.lifts))
                self.assertEqual(out.state.lifts,( -5,cell.state.lifts[1],cell.state.lifts[2]+cell.state.lifts[0]+5,0))
                self.assertEqual(out.events[-1].outcome,(cell.state.lifts[0]+5)%grid)
                self.assertEqual(out.gamma,cell.gamma)
                self.assertEqual((out.state.cost,out.state.next_cut_cost,out.state.charged_cuts),
                                 (cell.state.cost,cell.state.next_cut_cost,cell.state.charged_cuts))
                self.assertFalse(out.events[-1].charged)
                self.assertTrue(verify_history(out))
                if sign:self.assertEqual(out.closure,sign)

    def test_reference_rebase_and_no_data_only_inverse(self):
        cell=Cell.start((65,-3,7,12));op=O("pair_reset",(0,2,-5))
        for delta in (-13,0,9):
            shifted=Cell.start(tuple(v+delta for v in cell.state.lifts))
            out=shifted.apply(op.rebase(delta))
            self.assertEqual(out.state.lifts,tuple(v+delta for v in cell.apply(op).state.lifts))
            self.assertEqual(out.events[-1].outcome,cell.apply(op).events[-1].outcome)
        with self.assertRaises(ValueError):op.inverse()
        a=Cell.start((1,0,3,0)).apply(O("pair_reset",(0,2,0)))
        b=Cell.start((2,0,2,0)).apply(O("pair_reset",(0,2,0)))
        self.assertEqual(a.state,b.state)
        self.assertNotEqual(a.events[-1].outcome,b.events[-1].outcome)

    def test_lift_overflow_and_invalid_source_are_atomic(self):
        cfg=Config(grid=4,max_lift=4)
        cell=Cell.start((4,0,4,0),config=cfg)
        for args in ((0,0,0),(0,4,0),(-1,2,0),(0,2,5),(0,2,0)):
            with self.assertRaises(ValueError):cell.apply(O("pair_reset",args))
        self.assertEqual(cell.state.lifts,(4,0,4,0));self.assertEqual(cell.events,())
        with self.assertRaises(TypeError):O("pair_reset",(0,True,0))
        with self.assertRaises(ValueError):O("pair_reset",(0,1))
        out=cell.apply(O("pair_reset",(0,2,4)))
        self.assertTrue(verify_history(out))
        self.assertFalse(verify_history(replace(out,events=(replace(out.events[0],outcome=1),))))


class BalancedResetBasisTests(unittest.TestCase):
    def test_all_grid4_full_inputs_pairs_and_references(self):
        cfg=Config(grid=4)
        for j,s,a in product(range(4),range(4),range(4)):
            if j==s:continue
            p=compile_controller((O("pair_reset",(j,s,a)),),config=cfg)
            for x in product(range(4),repeat=4):
                initial=p.pack(x);out=basis_run(p.gates,initial)
                y,r=image(x,j,s,a,4)
                self.assertEqual(p.unpack(out),(y,(r,)))
                self.assertEqual((sum(y)-sum(x))%4,0)
                self.assertEqual(basis_run(tuple(reversed(p.gates)),out),initial)

    def test_all_grid4_sector_labels_signs_twists_pairs_references_and_omissions(self):
        for sign,twist,omitted in product((-1,1),range(4),range(4)):
            cfg=Config(grid=4,sector=sign,twist=twist)
            for j,s,a in product(range(4),range(4),range(4)):
                if j==s:continue
                p=compile_controller((O("pair_reset",(j,s,a)),),config=cfg,omit_mode=omitted)
                for label in range(4**3):
                    x=p.layout.unpack(label);y,r=image(x,j,s,a,4)
                    out=basis_run(p.gates,label)
                    self.assertEqual(p.unpack(out),(y,(r,)))
                    self.assertEqual(closure_sign(y,4,twist),sign)
                    self.assertEqual(basis_run(tuple(reversed(p.gates)),out),label)

    def test_grid64_all_target_values_references_every_layout(self):
        cfg=Config(sector=-1,twist=3);target=48
        for omitted in (None,0,1,2,3):
            for a in range(64):
                p=compile_controller((O("pair_reset",(0,2,a)),),config=cfg,omit_mode=omitted)
                for value in range(64):
                    x=(value,11,(target-value-11-29)%64,29)
                    y,r=image(x,0,2,a,64)
                    self.assertEqual(p.unpack(basis_run(p.gates,p.pack(x))),(y,(r,)))

    def test_all_widths_and_composed_native_history(self):
        rng=random.Random(20261024)
        word=(O("read",(3,-1)),O("pair_reset",(0,2,-5)),O("pair_cut",(1,3,7)),
              O("pair_reset",(2,0,9)),O("pair_reset",(2,1,9)),O("swap",(0,3)))
        for width,omitted in product(range(2,13),(None,0,1,2,3)):
            cfg=Config(grid=1<<width,sector=-1,twist=1)
            p=compile_controller(word,config=cfg,omit_mode=omitted)
            for _ in range(3):
                x=[rng.randrange(cfg.grid) for _ in range(3)]
                x.append((cfg.grid//4-sum(x))%cfg.grid);x=tuple(x)
                t=bind_controller(Cell.start(x,config=cfg,gamma=F(2,3)),p)
                out=basis_run(p.gates,p.pack(x))
                self.assertEqual(p.unpack(out),(t.after.phases,t.outcomes))
                self.assertEqual(t.outcomes[-1],0)
                self.assertEqual(basis_run(tuple(reversed(p.gates)),out),p.pack(x))
                self.assertTrue(verify_controller_transition(t))
            self.assertEqual(tuple(r.step for r in p.records),(0,1,3,4))
            self.assertEqual(tuple(r.reservoir for r in p.records),(None,2,0,1))

    def test_dirty_record_extension_preserves_sum_but_is_not_a_reset(self):
        cfg=Config(grid=4,sector=1)
        for omitted in (None,0,1,2,3):
            p=compile_controller((O("pair_reset",(0,2,1)),),config=cfg,omit_mode=omitted)
            for j,s,memory in product(range(4),repeat=3):
                x=(j,1,s,(-j-s-1)%4)
                r=(memory+j-1)%4 if omitted==0 else ((memory^j)-1)%4
                y=((j-r)%4,1,(s+r)%4,x[3])
                initial=p.pack(x)|(memory << p.records[0].wires[0]);out=basis_run(p.gates,initial)
                self.assertEqual(p.unpack(out),(y,(r,)))
                self.assertEqual(closure_sign(y,4,0),1)
                self.assertEqual(basis_run(tuple(reversed(p.gates)),out),initial)

    def test_dirty_workspace_has_no_clean_arithmetic_promise(self):
        p=compile_controller((O("pair_reset",(0,2,0)),),config=Config(sector=1))
        changed=False
        for j in range(64):
            x=(j,0,(-j)%64,0);initial=p.pack(x)|(1 << p.layout.scratch[0])
            out=basis_run(p.gates,initial)
            y,r=image(x,0,2,0,64)
            ideal=p.pack(y)|(r << p.records[0].wires[0])|(1 << p.layout.scratch[0])
            changed |= out!=ideal
            self.assertEqual(basis_run(tuple(reversed(p.gates)),out),initial)
        self.assertTrue(changed)


class BalancedResetCoherenceTests(unittest.TestCase):
    def test_full_and_compressed_coherent_maps_agree_through_codec(self):
        cfg=Config(sector=-1,twist=1)
        word=(O("pair_reset",(0,2,7)),O("pair_cut",(1,3,3)),O("pair_reset",(2,0,-5)))
        full=compile_controller(word,config=cfg)
        for omitted in range(4):
            small=compile_controller(word,config=cfg,omit_mode=omitted)
            ref=full.n_qubits;c=Phase64Circuit(ref+1)
            kept=[j for j in range(4) if j!=omitted]
            for j in kept:c.add("h",full.layout.registers[j][0]).add("p64",full.layout.registers[j][0])
            c.add("cx",full.layout.registers[kept[0]][0],ref)
            codec=closure_codec(cfg,omitted)
            for name,qs in reversed(codec.operations):c.add(name,*qs)
            initial=prepare(c).amplitudes
            direct=Phase64Circuit(ref+1)
            for name,qs in c.operations+full.gates:direct.add(name,*qs)
            expected=prepare(direct).amplitudes
            for name,qs in codec.operations:c.add(name,*qs)
            mapping={a:b for j in kept for a,b in zip(small.layout.registers[j],full.layout.registers[j])}
            mapping.update(zip(small.layout.scratch,full.layout.scratch))
            for a,b in zip(small.records,full.records):mapping.update(zip(a.wires,b.wires))
            for name,qs in small.gates:c.add(name,*(mapping[q] for q in qs))
            for name,qs in reversed(codec.operations):c.add(name,*qs)
            self.assertEqual(prepare(c).amplitudes,expected)
            self.assertEqual(reduced_density(expected,(ref,)),reduced_density(initial,(ref,)))
            for name,qs in full.to_circuit(inverse=True).operations:c.add(name,*qs)
            self.assertEqual(prepare(c).amplitudes,initial)

    def test_branch_channel_partial_trace_and_untouched_reference(self):
        # Arbitrary coherent target/reservoir correlation plus external reference.
        p=compile_controller((O("pair_reset",(0,2,1)),),config=Config(grid=4))
        ref=p.n_qubits;c=Phase64Circuit(ref+1)
        c.add("h",0).add("p64",0).add("h",4).add("p64",4).add("cx",0,ref)
        before=prepare(c).amplitudes;expected={};branches={}
        for label,amp in before.items():
            y,r=image(p.layout.unpack(label&((1<<ref)-1)),0,2,1,4)
            data=p.pack(y)|(label&(1<<ref))
            expected[data|(r << p.records[0].wires[0])]=amp
            branches.setdefault(r,{})[data]=amp
        for name,qs in p.gates:c.add(name,*qs)
        after=prepare(c).amplitudes
        self.assertEqual(after,expected)
        keep=(*range(p.layout.phase_bits),ref)
        channel={}
        for branch in branches.values():
            for key,value in reduced_density(branch,keep).items():channel[key]=channel.get(key,c.field(0))+value
        channel={k:v for k,v in channel.items() if v}
        self.assertEqual(reduced_density(after,keep),channel)
        self.assertEqual(reduced_density(after,p.layout.registers[0]),{(1,1):c.field(1)})
        remote=(*p.layout.registers[1],*p.layout.registers[3],ref)
        self.assertEqual(reduced_density(after,remote),reduced_density(before,remote))
        self.assertEqual(sum((v for (a,b),v in channel.items() if a==b),c.field(0)),c.field(1))

    def test_fixed_sector_record_carries_phase_after_data_collapses(self):
        cfg=Config(sector=1)
        p=compile_controller((O("pair_reset",(0,2,0)),),config=cfg,omit_mode=2)
        c=Phase64Circuit(p.n_qubits).add("h",0).add("p64",0)
        initial=prepare(c).amplitudes
        for name,qs in p.gates:c.add(name,*qs)
        after=prepare(c).amplitudes
        self.assertEqual(reduced_density(after,range(p.layout.phase_bits)),{(0,0):c.field(1)})
        self.assertTrue(any(a!=b for a,b in reduced_density(after,p.records[0].wires)))
        self.assertEqual({p.unpack(k)[1][0] for k in after},{0,1})
        for name,qs in p.to_circuit(inverse=True).operations:c.add(name,*qs)
        self.assertEqual(prepare(c).amplitudes,initial)
        c.add("p64dg",0).add("h",0)
        self.assertEqual(prepare(c).amplitudes,{0:c.field(1)})

    def test_dynamic_matches_measure_reset_and_conditional_reservoir_shift(self):
        cfg=Config(grid=4);p=compile_controller((O("pair_reset",(0,2,0)),),config=cfg)
        prep=(("h",(0,)),("t",(0,)),("h",(1,)),("h",(4,)),("t",(4,)))
        actual=p.to_dynamic(prep);reference=DynamicCircuit(p.n_qubits,2)
        for name,qs in prep:reference.add(name,*qs)
        reference.measure(0,0).measure(1,1).reset(0).reset(1)
        for r in range(1,4):
            gates=compile_register((O("shift",(2,r)),),config=cfg).gates
            for name,qs in gates:reference.add(name,*qs,condition={0:r&1,1:r>>1})
        for r,reservoir in product(range(4),repeat=2):
            q={0:0,1:0,4:reservoir&1,5:reservoir>>1};bits={0:r&1,1:r>>1}
            self.assertEqual(probability(actual,quantum=q,classical=bits).value,
                             probability(reference,quantum=q,classical=bits).value)
        for axis in "XYZ":
            self.assertEqual(expectation(actual,{4:axis}).value,expectation(reference,{4:axis}).value)


class BalancedResetGuardTests(unittest.TestCase):
    def test_pair_reset_requires_record_and_keeps_single_reset_boundary(self):
        op=O("pair_reset",(0,2,0))
        with self.assertRaises(ValueError):compile_register((op,))
        for omitted in (None,0,1,2,3):
            cfg=Config(sector=1)
            self.assertTrue(verify_controller(compile_controller((op,),config=cfg,omit_mode=omitted)))
            with self.assertRaises(ValueError):compile_controller((O("reset",(0,0)),),config=cfg,omit_mode=omitted)
        for args in ((0,0,0),(0,4,0),(-1,2,0)):
            with self.assertRaises(ValueError):compile_controller((O("pair_reset",args),))
        with self.assertRaises(ResourceLimit):compile_controller((op,),max_records=0)
        with self.assertRaises(ResourceLimit):compile_controller((op,),max_gates=0)
        with self.assertRaises(ResourceLimit):compile_controller((op,)*39,max_records=64)

    def test_reservoir_source_record_and_gate_tampering_are_rejected(self):
        p=compile_controller((O("pair_reset",(0,2,0)),));r=p.records[0]
        for reservoir in (None,True,0,1,4):
            self.assertFalse(verify_controller(replace(p,records=(replace(r,reservoir=reservoir),))))
        self.assertFalse(verify_controller(replace(p,operations=(O("pair_reset",(0,1,0)),))))
        self.assertFalse(verify_controller(replace(p,gates=p.gates[:-1])))
        read=compile_controller((O("read",(0,0)),))
        self.assertFalse(verify_controller(replace(read,records=(replace(read.records[0],reservoir=2),))))

    def test_grid64_resources_and_original_interfaces(self):
        cfg=Config(sector=1)
        for omitted,wires in ((None,34),(0,28),(1,28),(2,28),(3,28)):
            p=compile_controller((O("pair_reset",(0,2,0)),),config=cfg,omit_mode=omitted)
            self.assertEqual(p.n_qubits,wires);self.assertEqual(p.record_bits,6)
            self.assertEqual(p.resources()["classical_output_bits_if_measured"],6)
            self.assertTrue(verify_controller(p))
        self.assertEqual(len(compile_controller((O("read",(0,0)),)).gates),6)
        self.assertEqual(len(compile_controller((O("reset",(0,0)),)).gates),18)


if __name__=="__main__":unittest.main()
