"""Native outcomes, coherent information transfer and existing instruments."""
from dataclasses import replace
from fractions import Fraction as F
from itertools import product
import random
import unittest

from native_relational_qc.dynamic import DynamicCircuit, probability, expectation
from native_relational_qc.phase_backend import Phase64Circuit, prepare
from phase_seam_foundation.model import Cell, Config, Operation as O, ResourceLimit
from phase_seam_foundation.controller import compile_controller, bind_controller, verify_controller, verify_controller_transition


def basis_run(gates,label):
    for name,qs in gates:
        if name=="x":label ^= 1 << qs[0]
        elif name=="cx":label ^= ((label >> qs[0])&1) << qs[1]
        elif name=="ccx":label ^= (((label >> qs[0])&1)&((label >> qs[1])&1)) << qs[2]
        else:raise AssertionError("non-permutation primitive")
    return label


def reduced_density(amplitudes,keep):
    # Small independent verification oracle: exact partial trace, test-only.
    keep=tuple(keep);mask=sum(1 << q for q in keep);out={}
    for a,u in amplitudes.items():
        for b,v in amplitudes.items():
            if (a & ~mask)!=(b & ~mask):continue
            i=sum(((a >> q)&1) << k for k,q in enumerate(keep))
            j=sum(((b >> q)&1) << k for k,q in enumerate(keep))
            out[i,j]=out.get((i,j),u*0)+u*v.conjugate()
    return {k:v for k,v in out.items() if v}


class ControllerBasisTests(unittest.TestCase):
    def test_all_grid4_inputs_modes_and_references_match_original_cell(self):
        cfg=Config(grid=4)
        for kind,mode,ref in product(("read","reset"),range(4),range(4)):
            p=compile_controller((O(kind,(mode,ref)),),config=cfg)
            for x in product(range(4),repeat=4):
                cell=Cell.start(x,config=cfg).apply(p.operations[0])
                initial=p.pack(x);out=basis_run(p.gates,initial)
                self.assertEqual(p.unpack(out),(cell.phases,(cell.events[-1].outcome,)))
                self.assertEqual(basis_run(tuple(reversed(p.gates)),out),initial)

    def test_sequential_reads_resets_and_ordered_records(self):
        cfg=Config(grid=4)
        word=(O("read",(0,1)),O("pair_cut",(0,2,3)),O("reset",(0,2)),
              O("read",(2,3)),O("reset",(1,-1)),O("swap",(0,3)))
        p=compile_controller(word,config=cfg)
        self.assertEqual(tuple(r.step for r in p.records),(0,2,3,4))
        for x in product(range(4),repeat=4):
            t=bind_controller(Cell.start(x,config=cfg),p)
            self.assertEqual(p.unpack(basis_run(p.gates,p.pack(x))),(t.after.phases,t.outcomes))
            self.assertTrue(verify_controller_transition(t))
        self.assertEqual(bind_controller(Cell.start((0,0,0,0),config=cfg),p).outcomes[:2],(3,1))

    def test_all_grid64_values_and_references(self):
        for kind,ref in product(("read","reset"),range(64)):
            p=compile_controller((O(kind,(0,ref)),))
            for x in range(64):
                phases=(x,11,23,47)
                expected=phases if kind=="read" else (ref,11,23,47)
                self.assertEqual(p.unpack(basis_run(p.gates,p.pack(phases))),(expected,((x-ref)%64,)))

    def test_compressed_read_every_grid4_label_sign_twist_mode_and_omission(self):
        for sign,twist,omitted in product((-1,1),range(4),range(4)):
            cfg=Config(grid=4,sector=sign,twist=twist)
            word=tuple(O("read",(j,j-2)) for j in range(4))
            p=compile_controller(word,config=cfg,omit_mode=omitted)
            for label in range(4**3):
                x=p.layout.unpack(label)
                actual=p.unpack(basis_run(p.gates,label))
                self.assertEqual(actual,(x,tuple((x[j]-j+2)%4 for j in range(4))))

    def test_all_widths_and_negative_reference(self):
        rng=random.Random(20261024)
        for width in range(2,13):
            cfg=Config(grid=1 << width)
            p=compile_controller((O("read",(3,-9)),O("reset",(1,-5))),config=cfg)
            for _ in range(8):
                x=tuple(rng.randrange(cfg.grid) for _ in range(4))
                t=bind_controller(Cell.start(x,config=cfg),p)
                out=basis_run(p.gates,p.pack(x))
                self.assertEqual(p.unpack(out),(t.after.phases,t.outcomes))
                self.assertEqual(basis_run(tuple(reversed(p.gates)),out),p.pack(x))

    def test_dirty_records_are_not_silently_cleared(self):
        cfg=Config(grid=4)
        for kind in ("read","reset"):
            p=compile_controller((O(kind,(0,1)),),config=cfg)
            for x,y in product(range(4),repeat=2):
                initial=p.pack((x,0,0,0))|(y << p.records[0].wires[0])
                out=basis_run(p.gates,initial)
                expected=((x,0,0,0),(((y^x)-1)%4,)) if kind=="read" else (((y+1)%4,0,0,0),((x-1)%4,))
                self.assertEqual(p.unpack(out),expected)
                self.assertEqual(basis_run(tuple(reversed(p.gates)),out),initial)


class ControllerCoherenceTests(unittest.TestCase):
    def test_read_entangles_record_and_dephases_only_when_record_ignored(self):
        p=compile_controller((O("read",(0,0)),))
        c=Phase64Circuit(p.n_qubits).add("h",0).add("p64",0)
        before=prepare(c).amplitudes
        for name,qs in p.gates:c.add(name,*qs)
        after=prepare(c).amplitudes
        expected={k|((k&63) << p.records[0].wires[0]):v for k,v in before.items()}
        self.assertEqual(after,expected)
        rho=reduced_density(after,range(p.layout.phase_bits));field=c.field
        self.assertEqual(rho,{(0,0):field(F(1,2)),(1,1):field(F(1,2))})
        # Joint state still retains the relative phase, recoverable by undoing.
        for name,qs in p.to_circuit(inverse=True).operations:c.add(name,*qs)
        c.add("p64dg",0).add("h",0)
        self.assertEqual(prepare(c).amplitudes,{0:field(1)})

    def test_reset_moves_entanglement_to_record_without_changing_remote_state(self):
        p=compile_controller((O("reset",(0,5)),))
        ref=p.n_qubits;c=Phase64Circuit(ref+1).add("h",ref).add("p64",ref).add("cx",ref,0)
        before=prepare(c).amplitudes;remote=reduced_density(before,(ref,))
        for name,qs in p.gates:c.add(name,*qs)
        after=prepare(c).amplitudes
        expected={}
        for label,amp in before.items():
            x=label&63;r=(x-5)%64
            expected[5|(r << p.records[0].wires[0])|(label&(1 << ref))]=amp
        self.assertEqual(after,expected)
        self.assertEqual(reduced_density(after,p.layout.registers[0]),{(5,5):c.field(1)})
        self.assertEqual(reduced_density(after,(ref,)),remote)
        record_and_ref=reduced_density(after,(*p.records[0].wires,ref))
        self.assertTrue(any(a!=b for a,b in record_and_ref))
        for name,qs in p.to_circuit(inverse=True).operations:c.add(name,*qs)
        self.assertEqual(prepare(c).amplitudes,before)

    def test_repeated_read_records_correlated_not_independent_noise(self):
        p=compile_controller((O("read",(0,0)),)*2)
        c=Phase64Circuit(p.n_qubits).add("h",0)
        for name,qs in p.gates:c.add(name,*qs)
        for label in prepare(c).amplitudes:
            _,records=p.unpack(label)
            self.assertEqual(records[0],records[1])
        self.assertEqual(p.record_bits,12)  # explicit allocation, not an entropy lower bound

    def test_compressed_omitted_phase_read_preserves_exact_joint_amplitudes(self):
        p=compile_controller((O("read",(2,7)),),config=Config(sector=-1,twist=1),omit_mode=2)
        c=Phase64Circuit(p.n_qubits).add("h",0).add("p64",0)
        initial=prepare(c).amplitudes
        for name,qs in p.gates:c.add(name,*qs)
        expected={}
        for k,v in initial.items():
            x=p.layout.unpack(k);expected[k|(((x[2]-7)%64) << p.records[0].wires[0])]=v
        self.assertEqual(prepare(c).amplitudes,expected)

    def test_existing_dynamic_measurement_and_feedback_match_coherent_record(self):
        cfg=Config(grid=4)
        for kind in ("read","reset"):
            p=compile_controller((O(kind,(0,0)),),config=cfg)
            prep=(("h",(0,)),("t",(0,)))
            dynamic=p.to_dynamic(prep)
            reference=DynamicCircuit(p.n_qubits,p.record_bits).add("h",0).add("t",0)
            reference.measure(0,0).measure(1,1)
            if kind=="reset":reference.reset(0).reset(1)
            for bit,data in product((0,1),repeat=2):
                self.assertEqual(probability(dynamic,quantum={0:data},classical={0:bit,1:0}).value,
                                 probability(reference,quantum={0:data},classical={0:bit,1:0}).value)
            for axis in "XYZ":
                self.assertEqual(expectation(dynamic,{0:axis}).value,expectation(reference,{0:axis}).value)
            if kind=="read":
                dynamic.add("x",0,condition={0:1})
                self.assertEqual(probability(dynamic,quantum={0:0}).value.a,1)


class ControllerGuardTests(unittest.TestCase):
    def test_fixed_sector_reset_rejected_even_when_one_state_passes(self):
        cfg=Config(sector=1)
        self.assertEqual(Cell.start(config=cfg).apply(O("reset",(0,0))).closure,1)
        for omitted in (None,0,1,2,3):
            with self.assertRaisesRegex(ValueError,"whole fixed closure sector"):
                compile_controller((O("reset",(0,0)),),config=cfg,omit_mode=omitted)
        self.assertTrue(verify_controller(compile_controller((O("read",(0,0)),),config=cfg,omit_mode=2)))

    def test_memory_wire_gate_and_source_limits(self):
        read=O("read",(0,0))
        with self.assertRaises(ResourceLimit):compile_controller((read,)*17)
        with self.assertRaises(ResourceLimit):compile_controller((read,)*39,max_records=64)
        with self.assertRaises(ResourceLimit):compile_controller((read,),max_records=0)
        with self.assertRaises(ResourceLimit):compile_controller((read,),max_gates=0)
        with self.assertRaises(ResourceLimit):compile_controller((read,)*2,config=Config(max_events=1))
        p=compile_controller((read,),config=Config(max_events=1))
        cell=Cell.start(config=p.config).apply(read)
        with self.assertRaises(ResourceLimit):bind_controller(cell,p)
        self.assertEqual(len(cell.events),1)

    def test_tampering_records_gates_and_transition_rejected(self):
        p=compile_controller((O("read",(0,3)),O("reset",(0,5))))
        r=p.records[0]
        variants=(replace(p,records=(replace(r,reference=2),p.records[1])),
                  replace(p,records=(replace(r,step=True),p.records[1])),
                  replace(p,records=(replace(r,wires=(True,)),p.records[1])),
                  replace(p,gates=p.gates[:-1]),replace(p,omit_mode=True),
                  replace(p,gates=(("cx",(0,0)),)),replace(p,records=list(p.records)))
        for v in variants:
            self.assertFalse(verify_controller(v))
            with self.assertRaises(ValueError):v.to_circuit()
            with self.assertRaises(ValueError):v.to_dynamic()
        t=bind_controller(Cell.start(gamma=F(2,3)),p)
        self.assertTrue(verify_controller_transition(t))
        self.assertFalse(verify_controller_transition(replace(t,outcomes=(True,0))))
        self.assertFalse(verify_controller_transition(replace(t,after=t.before)))

    def test_input_guards_default_reversible_compiler_still_rejects_instruments(self):
        from phase_seam_foundation.register import compile_register
        for kind in ("read","reset"):
            with self.assertRaises(ValueError):compile_register((O(kind,(0,0)),))
        for kwargs in (dict(max_records=True),dict(max_gates=True),dict(omit_mode=True),dict(max_records=-1)):
            with self.assertRaises((ValueError,TypeError)):compile_controller((),**kwargs)
        with self.assertRaises(TypeError):compile_controller([])
        with self.assertRaises(ValueError):compile_controller((O("read",(4,0)),))
        p=compile_controller(())
        with self.assertRaises(TypeError):p.to_circuit(inverse=1)
        with self.assertRaises(TypeError):p.to_dynamic([])
        with self.assertRaises(ValueError):p.unpack(1 << p.n_qubits)
        with self.assertRaises(ValueError):p.unpack(1 << p.layout.scratch[0])
        with self.assertRaises(TypeError):p.unpack(True)

    def test_resource_accounting_and_external_history(self):
        p=compile_controller((O("read",(0,1)),O("reset",(0,2))))
        resources=p.resources()
        self.assertEqual((resources["phase_bits"],resources["clean_workspace_bits"],resources["retained_record_bits"],resources["total_logical_wires"]),(24,4,12,40))
        t=bind_controller(Cell.start((65,0,0,0),gamma=F(3,7)),p)
        self.assertEqual(t.outcomes,(0,63))
        self.assertEqual(t.after.state.lifts,(2,0,0,0))
        self.assertEqual(t.after.gamma,F(3,7))
        self.assertEqual(t.before.winding_lifts,(1,0,0,0))
        self.assertEqual(p.unpack(basis_run(p.gates,p.pack(t.before.phases))),(t.after.phases,t.outcomes))


if __name__=="__main__":unittest.main()
