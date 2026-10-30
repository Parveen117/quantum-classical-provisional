"""Native involution laws and exact fractional controls through the old engine."""
from dataclasses import replace
from itertools import product
from fractions import Fraction as F
import random
import unittest

from native_relational_qc.phase_backend import Phase64Circuit, prepare
from phase_seam_foundation.model import Config, Operation as O, ResourceLimit
from phase_seam_foundation.controller import compile_controller
from phase_seam_foundation.sector_control import compile_sector_control, pulse_coefficients, verify_sector_control
from test_phase_seam_controller import basis_run, reduced_density


def pack_records(controller,phases,values):
    return controller.pack(phases)|sum(v << r.wires[0] for r,v in zip(controller.records,values))


def direct_image(x,m,op,grid):
    y=list(x);j=op.args[0]
    if op.kind=="read":m=(x[j]-op.args[1]-m)%grid
    elif op.kind=="pair_reset":
        _,b,a=op.args;y[j]=a+m;y[b]=x[b]+x[j]-a-m;m=(x[j]-a)%grid
    elif op.kind=="pair_cut":
        _,b,h=op.args;y[j]=h-x[j];y[b]=x[b]+2*x[j]-h
    else:
        b=op.args[1];y[j],y[b]=x[b],x[j]
    return tuple(v%grid for v in y),m


def superposition_circuit(program,x0,x1):
    # Two basis inputs with relative zeta_64 phase and an external reference.
    controller=program.controller;ref=program.n_qubits+2
    c=Phase64Circuit(ref+1);a,b=controller.pack(x0),controller.pack(x1)
    differing=[q for q in range(program.n_qubits) if ((a^b)>>q)&1]
    pivot=differing[0];c.add("h",pivot).add("p64",pivot)
    for q in differing[1:]:c.add("cx",pivot,q)
    c.add("cx",pivot,ref)
    for q in range(program.n_qubits):
        if (a>>q)&1:c.add("x",q)
    return c,ref


class SectorControlBasisTests(unittest.TestCase):
    def test_grid4_full_involutions_all_labels_and_dirty_records(self):
        cfg=Config(grid=4)
        ops=[O("read",(j,a)) for j,a in product(range(4),repeat=2)]
        ops += [O(kind,(j,b,a)) for kind,j,b,a in product(("pair_cut","pair_reset"),range(4),range(4),range(4)) if j!=b]
        ops += [O("swap",(j,b)) for j,b in product(range(4),repeat=2)]
        for op in ops:
            p=compile_sector_control((op,),config=cfg);c=p.controller;gates=p.pulses[0].gates
            memories=range(4) if c.records else (0,)
            for x in product(range(4),repeat=4):
                for memory in memories:
                    initial=pack_records(c,x,(memory,) if c.records else ())
                    out=basis_run(gates,initial);y,m=direct_image(x,memory,op,4)
                    expected=pack_records(c,y,(m,) if c.records else ())
                    self.assertEqual(out,expected);self.assertEqual(p.image(0,initial),expected)
                    self.assertEqual(p.image(0,expected),initial)
                    self.assertEqual(basis_run(gates,out),initial)
                    self.assertEqual((sum(y)-sum(x))%4,0)

    def test_grid4_compressed_involutions_signs_twists_omissions_and_memory(self):
        for sign,twist,omitted,a in product((-1,1),range(4),range(4),range(4)):
            cfg=Config(grid=4,sector=sign,twist=twist)
            for op in (O("pair_reset",(0,2,a)),O("read",(0,a))):
                p=compile_sector_control((op,),config=cfg,omit_mode=omitted);c=p.controller
                for label,memory in product(range(64),range(4)):
                    x=c.layout.unpack(label);initial=pack_records(c,x,(memory,))
                    y,m=direct_image(x,memory,op,4);expected=pack_records(c,y,(m,))
                    self.assertEqual(basis_run(p.pulses[0].gates,initial),expected)
                    self.assertEqual(p.image(0,initial),expected)
                    self.assertEqual(p.image(0,expected),initial)

    def test_composed_clean_endpoints_match_existing_controller(self):
        cfg=Config(grid=4,sector=-1,twist=3)
        ops=(O("read",(0,1)),O("pair_cut",(0,2,3)),O("pair_shift",(1,3,-1)),
             O("swap",(0,2)),O("pair_reset",(2,0,1)),O("read",(2,3)))
        for omitted in (None,0,1,2,3):
            p=compile_sector_control(ops,config=cfg,omit_mode=omitted);c=p.controller
            self.assertEqual(len(p.pulses),7)
            for a,b,d in product(range(4),repeat=3):
                x=(a,b,d,(3-a-b-d)%4);initial=c.pack(x);actual=initial
                for i,pulse in enumerate(p.pulses):
                    actual=basis_run(pulse.gates,actual)
                self.assertEqual(actual,basis_run(c.gates,initial))
                semantic=initial
                for i in range(len(p.pulses)):semantic=p.image(i,semantic)
                self.assertEqual(semantic,actual)

    def test_every_supported_width_and_layout_for_balanced_exchange(self):
        rng=random.Random(2056)
        for width,omitted in product(range(2,13),(None,0,1,2,3)):
            cfg=Config(grid=1<<width,sector=-1,twist=1)
            p=compile_sector_control((O("pair_reset",(0,2,-7)),),config=cfg,omit_mode=omitted)
            c=p.controller
            for _ in range(5):
                x=[rng.randrange(cfg.grid) for _ in range(3)];x.append((cfg.grid//4-sum(x))%cfg.grid)
                memory=rng.randrange(cfg.grid);initial=pack_records(c,tuple(x),(memory,))
                expected=p.image(0,initial);actual=basis_run(p.pulses[0].gates,initial)
                self.assertEqual(actual,expected);self.assertEqual(basis_run(p.pulses[0].gates,actual),initial)

    def test_dirty_extensions_differ_from_old_controller_only_where_declared(self):
        for kind,args in (("read",(0,1)),("pair_reset",(0,2,1))):
            p=compile_sector_control((O(kind,args),),config=Config(grid=4));c=p.controller;different=False
            for x,m in product(range(4),repeat=2):
                initial=pack_records(c,(x,0,0,0),(m,))
                old=basis_run(c.gates,initial);new=basis_run(p.pulses[0].gates,initial)
                if m==0:self.assertEqual(new,old)
                else:different |= new!=old
            self.assertTrue(different)


class SectorControlFractionalTests(unittest.TestCase):
    def test_exact_coefficients_unitarity_group_and_endpoints(self):
        one=Phase64Circuit.field(1);zero=one*0
        self.assertEqual(pulse_coefficients(0),(one,zero))
        self.assertEqual(pulse_coefficients(32),(zero,one))
        for k in range(64):
            a,b=pulse_coefficients(k);u,v=pulse_coefficients(7)
            self.assertEqual(a*a.conjugate()+b*b.conjugate(),one)
            self.assertEqual(a*b.conjugate()+b*a.conjugate(),zero)
            self.assertEqual((a*u+b*v,a*v+b*u),pulse_coefficients((k+7)%64))
            self.assertEqual(pulse_coefficients(-k),(a.conjugate(),b.conjugate()))

    def test_fractional_gadgets_match_native_operator_and_restore_ancillas(self):
        cfg=Config(grid=4,sector=1)
        for op in (O("read",(0,1)),O("pair_reset",(0,2,1)),O("pair_cut",(0,2,1)),O("swap",(0,2))):
            p=compile_sector_control((op,),config=cfg)
            for step in (0,1,8,16,31,32,63):
                c,ref=superposition_circuit(p,(0,0,0,0),(1,0,3,0));initial=prepare(c).amplitudes
                for name,qs in p.verification_circuit((step,)).operations:c.add(name,*qs)
                actual=prepare(c).amplitudes;a,b=pulse_coefficients(step);expected={}
                for label,value in initial.items():
                    mapped=p.image(0,label&((1<<ref)-1))|(label&(1<<ref))
                    for out,coefficient in ((label,a),(mapped,b)):
                        expected[out]=expected.get(out,c.field(0))+coefficient*value
                expected={k:v for k,v in expected.items() if v}
                self.assertEqual(actual,expected)
                for label in actual:
                    self.assertEqual((label>>p.n_qubits)&3,0)
                    x,_=p.controller.unpack(label&((1<<p.n_qubits)-1))
                    self.assertEqual(sum(x)%4,0)
                if op.kind!="swap":
                    self.assertEqual(reduced_density(actual,(ref,)),reduced_density(initial,(ref,)))

    def test_full_compressed_fractional_equality_including_dirty_records(self):
        for grid in (4,64):
            cfg=Config(grid=grid,sector=-1,twist=1);s=grid//4
            for memory in (0,1):
                outputs=[]
                for omitted in (None,0,1,2,3):
                    p=compile_sector_control((O("pair_reset",(0,2,3)),),config=cfg,omit_mode=omitted)
                    c,ref=superposition_circuit(p,(0,0,s,0),(1,0,(s-1)%grid,0))
                    if memory:c.add("x",p.controller.records[0].wires[0])
                    for name,qs in p.verification_circuit((16,)).operations:c.add(name,*qs)
                    amplitudes=prepare(c).amplitudes;decoded={}
                    for label,value in amplitudes.items():
                        self.assertEqual((label>>p.n_qubits)&3,0)
                        x,m=p.controller.unpack(label&((1<<p.n_qubits)-1))
                        self.assertEqual(sum(x)%grid,s)
                        decoded[x,m,(label>>ref)&1]=value
                    outputs.append(decoded)
                self.assertTrue(all(x==outputs[0] for x in outputs))

    def test_two_half_pulses_equal_endpoint_and_negative_angle_undoes(self):
        p=compile_sector_control((O("pair_reset",(0,2,0)),),config=Config(grid=4,sector=1),omit_mode=2)
        c,ref=superposition_circuit(p,(0,0,0,0),(1,0,3,0));before=prepare(c).amplitudes
        for _ in range(2):
            for name,qs in p.verification_circuit((16,)).operations:c.add(name,*qs)
        expected={p.image(0,k&((1<<ref)-1))|(k&(1<<ref)):v for k,v in before.items()}
        self.assertEqual(prepare(c).amplitudes,expected)
        for name,qs in p.verification_circuit((-32,)).operations:c.add(name,*qs)
        self.assertEqual(prepare(c).amplitudes,before)

    def test_partial_reset_is_coherent_and_not_a_completed_reset(self):
        p=compile_sector_control((O("pair_reset",(0,2,0)),),config=Config(grid=4,sector=1),omit_mode=2)
        c=Phase64Circuit(p.n_qubits+2).add("x",0)
        for name,qs in p.verification_circuit((16,)).operations:c.add(name,*qs)
        state=prepare(c)
        self.assertEqual(state.probability({0:0,1:0}),c.field(F(1,2)))
        for label in state.amplitudes:
            self.assertEqual(sum(p.controller.unpack(label)[0])%4,0)


class SectorControlBoundaryTests(unittest.TestCase):
    def test_binary_endpoint_prefixes_are_not_continuous_closure_evidence(self):
        p=compile_sector_control((O("pair_reset",(0,2,0)),),config=Config(sector=1));c=p.controller
        initial=c.pack((1,0,63,0));mask=(1<<c.layout.phase_bits)-1
        for gates in (c.gates,p.pulses[0].gates):
            label=initial;leaked=False
            for gate in gates:
                label=basis_run((gate,),label)
                leaked |= sum(c.layout.unpack(label&mask))%64!=0
            self.assertTrue(leaked)
            self.assertEqual(sum(c.unpack(label)[0])%64,0)

    def test_symmetry_breaking_half_rotation_leaks_exactly_one_half(self):
        # Same eigenvalue-phase gadget for P=X on one data bit: wrong generator.
        c=Phase64Circuit(10);flag=8
        c.add("h",flag).add("cx",flag,0).add("h",flag)
        for _ in range(16):c.add("p64dg",flag)
        c.add("h",flag).add("cx",flag,0).add("h",flag)
        state=prepare(c)
        self.assertEqual(state.probability({0:1}),c.field(F(1,2)))
        self.assertEqual(state.probability({flag:0}),c.field(1))
        # Other phase registers stay zero, so bit 0=1 is outside sum=0 mod 4.

    def test_caps_unsupported_operations_and_tampering(self):
        op=O("pair_reset",(0,2,0));p=compile_sector_control((op,));pulse=p.pulses[0]
        for q in (replace(p,pulses=list(p.pulses)),replace(p,pulses=(replace(pulse,source_step=True),)),
                  replace(p,pulses=(replace(pulse,record_index=True),)),
                  replace(p,pulses=(replace(pulse,gates=pulse.gates[:-1]),))):
            self.assertFalse(verify_sector_control(q))
            with self.assertRaises(ValueError):q.verification_circuit()
        for op in (O("reset",(0,0)),O("cut",(0,0)),O("shift",(0,1)),O("shear",(0,2,1,0))):
            with self.assertRaises(ValueError):compile_sector_control((op,))
        for kw in (dict(max_pulses=0),dict(max_gates=0),dict(max_records=0)):
            with self.assertRaises(ResourceLimit):compile_sector_control((O("pair_reset",(0,2,0)),),**kw)
        with self.assertRaises(ResourceLimit):compile_sector_control((O("pair_shift",(0,2,1)),),max_pulses=1)
        for steps in ([16],(),(True,),(65,)):
            with self.assertRaises((TypeError,ValueError)):p.verification_circuit(steps)
        with self.assertRaises(ResourceLimit):p.verification_circuit(max_gates=0)
        with self.assertRaises(TypeError):compile_sector_control((),max_pulses=True)
        wide=compile_sector_control((O("read",(0,0)),)*38,max_records=64)
        self.assertEqual(wide.n_qubits,256)
        with self.assertRaises(ResourceLimit):wide.verification_circuit()

    def test_resource_accounting_and_native_pulse_count(self):
        for omitted,wires,endpoint in ((None,34,140),(2,28,18)):
            p=compile_sector_control((O("pair_reset",(0,2,0)),),config=Config(sector=1),omit_mode=omitted)
            r=p.resources();self.assertEqual(r["allocated_endpoint_wires"],wires)
            self.assertEqual(r["native_involution_pulses"],1)
            self.assertEqual(r["endpoint_verification_gates"],endpoint)
            self.assertEqual(p.verification_circuit((16,)).n_qubits,wires+2)
            self.assertFalse(r["physical_pulse_count_claim"])
            self.assertTrue(verify_sector_control(p))


if __name__=="__main__":unittest.main()
