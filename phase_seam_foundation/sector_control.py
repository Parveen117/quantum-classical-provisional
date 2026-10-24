"""Native involutions and continuously sector-preserving control targets.

For a declared involution P, U(theta)=(I+P)/2+exp(-i theta)*(I-P)/2.
The binary verification circuit reuses existing arithmetic/phase execution;
its intermediate gates are NOT a sector-preserving physical implementation.
See SECTOR_CONTROL.md for the algebra, added control assumption and limits.
"""
from dataclasses import dataclass

from native_relational_qc.cyclotomic64 import ZETA, ONE
from native_relational_qc.modular_arithmetic import _add, _mcx
from native_relational_qc.phase_backend import Phase64Circuit
from .model import Config, Operation, ResourceLimit, integer, index
from .register import MAX_GATES, _sector_target, compile_register
from .controller import ControllerProgram, compile_controller, verify_controller

KINDS = ("pair_cut", "pair_shift", "swap", "read", "pair_reset")
MAX_PULSES = 2048


def pulse_coefficients(steps):
    """Exact alpha,beta at theta=steps*pi/32; analytic theorem is for real theta."""
    integer(steps,"pulse angle steps")
    if not -64 <= steps <= 64: raise ValueError("pulse angle steps must be in [-64,64]")
    z=ZETA**(-steps)
    return (ONE+z)/2,(ONE-z)/2


@dataclass(frozen=True)
class Pulse:
    source_step: int
    operation: Operation
    record_index: object
    gates: tuple  # endpoint verification only; not the physical continuous drive


def _endpoint(op,layout,record):
    if op.kind in ("pair_cut","swap"):
        return compile_register((op,),config=layout.config,omit_mode=layout.omit_mode).gates
    grid=layout.config.grid;regs=layout.registers;scratch=layout.scratch
    j,a=op.args[0],op.args[-1]

    def add(wires,k,controls=()):return tuple(_add(wires,k%grid,controls,scratch))
    def accumulate(source,target,k):
        return tuple(g for i,q in enumerate(source) for g in add(target,k*(1 << i),(q,)))

    if op.kind=="read":
        # Modular reflection m -> x_j-a-m, not the previous dirty-record read.
        out=tuple(("x",(q,)) for q in record)+add(record,1-a)
        if j==layout.omit_mode:
            out+=add(record,_sector_target(layout.config))
            for wires in regs:
                if wires:out+=accumulate(wires,record,-1)
        else:out+=accumulate(regs[j],record,1)
        return out

    # Balanced exchange: (x_j,x_b,m) -> (a+m,x_b+x_j-a-m,x_j-a).
    # Conjugated register swap A^-1 S A; the gate list is in execution order.
    b=op.args[1]
    if j==layout.omit_mode:
        wires=regs[b]
        before=compile_register((Operation("swap",(j,b)),),config=layout.config,omit_mode=j).gates
        before+=add(wires,-a)
    else:
        wires=regs[j];before=add(wires,-a)
        if b!=layout.omit_mode:before+=accumulate(wires,regs[b],1)
    swap=tuple(g for x,y in zip(wires,record) for g in (("cx",(x,y)),("cx",(y,x)),("cx",(x,y))))
    return before+swap+tuple(reversed(before))


@dataclass(frozen=True)
class SectorControl:
    controller: ControllerProgram
    pulses: tuple

    @property
    def n_qubits(self):return self.controller.n_qubits

    def image(self,pulse_index,label):
        """Independent native involution on clean-workspace basis labels.

        All record values are admitted. This is a symbolic label map, not an
        amplitude executor; full fixed-sector layouts also admit off-sector
        labels because these involutions preserve every modular sum.
        """
        index(pulse_index,len(self.pulses),"pulse index")
        x,records=self.controller.unpack(label);x=list(x);records=list(records)
        pulse=self.pulses[pulse_index];op=pulse.operation;grid=self.controller.config.grid
        j=op.args[0]
        if op.kind=="pair_cut":
            _,b,h=op.args;x[b]+=2*x[j]-h;x[j]=h-x[j]
        elif op.kind=="swap":
            b=op.args[1];x[j],x[b]=x[b],x[j]
        elif op.kind=="read":
            records[pulse.record_index]=x[j]-op.args[1]-records[pulse.record_index]
        elif op.kind=="pair_reset":
            _,b,a=op.args;m=records[pulse.record_index]
            records[pulse.record_index]=x[j]-a;x[b]+=x[j]-a-m;x[j]=a+m
        else:raise ValueError("not a declared involution")
        out=self.controller.pack(tuple(v%grid for v in x))
        for record,value in zip(self.controller.records,records):out|=(value%grid) << record.wires[0]
        return out

    def verification_circuit(self,phase_steps=None,*,max_gates=MAX_GATES):
        """Export exact pulse samples to the EXISTING Phase64Circuit engine.

        Two additional clean wires: eigenvalue flag and controlled-gate scratch.
        Caller prepares input in the declared sector with clean workspace.
        Sampling angle steps uses pi/32; default pi executes every involution.
        This binary gadget does not promise sector confinement during its gates.
        """
        if not verify_sector_control(self):raise ValueError("invalid sector control program")
        if phase_steps is None:phase_steps=(32,)*len(self.pulses)
        if type(phase_steps) is not tuple or len(phase_steps)!=len(self.pulses):
            raise ValueError("one angle step per native pulse required")
        for step in phase_steps:pulse_coefficients(step)
        integer(max_gates,"verification gate cap")
        if not 0 <= max_gates <= MAX_GATES:raise ValueError("verification gate cap out of range")
        if self.n_qubits+2>256:raise ResourceLimit("verification gadget exceeds 256-wire IR")
        flag,helper=self.n_qubits,self.n_qubits+1;out=[]
        def extend(gates):
            if len(out)+len(gates)>max_gates:raise ResourceLimit("verification gate cap; no circuit returned")
            out.extend(gates)
        for pulse,step in zip(self.pulses,phase_steps):
            step=(step+32)%64-32
            if not step:continue
            controlled=[]
            for name,qs in pulse.gates:
                block=_mcx((flag,*qs[:-1]),qs[-1],(helper,))
                if len(controlled)+len(block)>max_gates:raise ResourceLimit("controlled endpoint gate cap")
                controlled.extend(block)
            extend((("h",(flag,)),));extend(controlled);extend((("h",(flag,)),))
            extend(tuple(("p64dg" if step>0 else "p64",(flag,)) for _ in range(abs(step))))
            extend((("h",(flag,)),));extend(tuple(reversed(controlled)));extend((("h",(flag,)),))
        c=Phase64Circuit(self.n_qubits+2)
        for name,qs in out:c.add(name,*qs)
        return c

    def resources(self):
        base=self.controller.resources()
        return dict(native_involution_pulses=len(self.pulses),
                    phase_bits=base["phase_bits"],retained_record_bits=base["retained_record_bits"],
                    inherited_arithmetic_workspace_bits=base["clean_workspace_bits"],
                    allocated_endpoint_wires=self.n_qubits,
                    endpoint_verification_gates=sum(len(p.gates) for p in self.pulses),
                    previous_controller_gates=base["elementary_gates"],
                    fractional_verification_extra_clean_wires=2,
                    fractional_verification_wires=self.n_qubits+2,
                    native_drive="H(t)=hbar*g(t)*(I-P)/2; integrated area pi for each endpoint",
                    physical_pulse_count_claim=False,physical_qubits_built=0,
                    limits="native pulses are high-dimensional operator targets, not calibrated one/two-qubit gates")


def compile_sector_control(operations,*,config=None,omit_mode=None,max_records=16,
                           max_pulses=MAX_PULSES,max_gates=MAX_GATES):
    """Reuse controller admission/layout/provenance; add a declared native drive.

    Endpoint maps agree with the old controller on fresh records; read and
    pair_reset use different, explicitly involutive dirty-record extensions.
    """
    integer(max_pulses,"native pulse cap");integer(max_gates,"endpoint gate cap")
    if not 0 <= max_pulses <= MAX_PULSES or not 0 <= max_gates <= MAX_GATES:
        raise ValueError("sector control cap out of range")
    cfg=Config() if config is None else config
    controller=compile_controller(operations,config=cfg,omit_mode=omit_mode,max_records=max_records)
    if any(op.kind not in KINDS for op in operations):raise ValueError("unsupported continuously sector-preserving source operation")
    if sum(2 if op.kind=="pair_shift" else 1 for op in operations)>max_pulses:
        raise ResourceLimit("native pulse count cap")
    records={r.step:i for i,r in enumerate(controller.records)};pulses=[];count=0
    layout=controller.layout
    for step,op in enumerate(operations):
        sequence=(op,)
        if op.kind=="pair_shift":
            j,b,d=op.args
            sequence=(Operation("pair_cut",(j,b,0)),Operation("pair_cut",(j,b,d)))
        ri=records.get(step);wires=controller.records[ri].wires if ri is not None else ()
        for primitive in sequence:
            gates=_endpoint(primitive,layout,wires);count+=len(gates)
            if count>max_gates:raise ResourceLimit("native endpoint verification gate cap")
            pulses.append(Pulse(step,primitive,ri,gates))
    return SectorControl(controller,tuple(pulses))


def verify_sector_control(program):
    """Shared-code source/record/gate consistency check, not a formal prover."""
    try:
        if type(program) is not SectorControl or not verify_controller(program.controller):return False
        if type(program.pulses) is not tuple or len(program.pulses)>MAX_PULSES:return False
        for p in program.pulses:
            if type(p) is not Pulse or type(p.operation) is not Operation:return False
            index(p.source_step,len(program.controller.operations),"source step")
            if p.record_index is not None:index(p.record_index,len(program.controller.records),"record index")
            if type(p.gates) is not tuple:return False
            for gate in p.gates:
                if type(gate) is not tuple or len(gate)!=2:return False
                name,qs=gate
                if type(name) is not str or name not in ("x","cx","ccx"):return False
                if type(qs) is not tuple or len(qs)!={"x":1,"cx":2,"ccx":3}[name] or len(set(qs))!=len(qs):return False
                for q in qs:index(q,program.n_qubits,"endpoint wire")
        c=program.controller
        return compile_sector_control(c.operations,config=c.config,omit_mode=c.omit_mode,max_records=64)==program
    except (ValueError,TypeError,AttributeError,IndexError):return False
