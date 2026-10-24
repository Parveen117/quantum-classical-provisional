"""Explicit retained records for native phase read/reset operations.

Reuses the phase-register compiler, constant adder and existing dynamic
measurement engine. Records are fresh coherent registers until measured;
they are never silently cleared or counted as reusable clean workspace.
"""
from collections import Counter
from dataclasses import dataclass

from native_relational_qc.compact import CompactCircuit
from native_relational_qc.dynamic import DynamicCircuit
from native_relational_qc.modular_arithmetic import _add
from .model import Cell, Config, ResourceLimit, integer, index, verify_history
from .register import MAX_GATES, _word, _sector_target, compile_register


@dataclass(frozen=True)
class Record:
    step: int
    kind: str
    mode: int
    reference: int
    wires: tuple


@dataclass(frozen=True)
class ControllerProgram:
    config: Config
    operations: tuple
    omit_mode: object
    records: tuple
    gates: tuple

    @property
    def layout(self):
        return compile_register((),config=self.config,omit_mode=self.omit_mode)

    @property
    def n_qubits(self): return self.layout.n_qubits + len(self.records)*self.layout.width

    @property
    def record_bits(self): return len(self.records)*self.layout.width

    def pack(self, phases):
        """Basis input with clean workspace and all record registers zero."""
        return self.layout.pack(phases)

    def unpack(self, label):
        """Decode a basis output; require clean workspace, retain all records."""
        integer(label,"basis label")
        if not 0 <= label < 1 << self.n_qubits: raise ValueError("basis label out of range")
        layout=self.layout
        if any(label & (1 << q) for q in layout.scratch):
            raise ValueError("controller workspace is not clean")
        phases=layout.unpack(label & ((1 << layout.phase_bits)-1))
        records=tuple(sum(((label >> q)&1) << i for i,q in enumerate(r.wires)) for r in self.records)
        return phases,records

    def to_circuit(self, *, inverse=False):
        if type(inverse) is not bool: raise TypeError("inverse must be bool")
        if not verify_controller(self): raise ValueError("invalid controller program")
        c=CompactCircuit(self.n_qubits)
        for name,qs in reversed(self.gates) if inverse else self.gates: c.add(name,*qs)
        return c

    def to_dynamic(self, preparation=()):
        """Existing dynamic engine: terminal record measurement into fresh cbits.

        Future controller gates never touch an earlier record, so record
        measurement may be deferred. Caller owns clean-register/sector input
        preconditions. Classical feedback can be appended through DynamicCircuit.
        Its existing exact gate alphabet applies to preparation.
        """
        if not verify_controller(self): raise ValueError("invalid controller program")
        if type(preparation) is not tuple: raise TypeError("preparation must be an immutable gate tuple")
        c=DynamicCircuit(self.n_qubits,self.record_bits)
        for item in preparation:
            if type(item) is not tuple or len(item)!=2 or type(item[1]) is not tuple:
                raise TypeError("invalid preparation gate")
            c.add(item[0],*item[1])
        for name,qs in self.gates: c.add(name,*qs)
        for bit,q in enumerate(q for r in self.records for q in r.wires): c.measure(q,bit)
        return c

    def resources(self):
        layout=self.layout
        return dict(phase_bits=layout.phase_bits,clean_workspace_bits=len(layout.scratch),
                    retained_record_bits=self.record_bits,retained_records=len(self.records),
                    total_logical_wires=self.n_qubits,source_operations=len(self.operations),
                    elementary_gates=len(self.gates),gate_counts=dict(Counter(n for n,_ in self.gates)),
                    classical_output_bits_if_measured=self.record_bits,
                    record_policy="one fresh width-bit register per read/reset; no overwrite or recycling",
                    record_storage_minimality_claim=False,
                    external="Gamma, unwrapped lifts, operation tape, charged-cut cost",
                    physical_qubits_built=0)


def _instrument_gates(op, layout, record):
    grid=layout.config.grid; mode,ref=op.args
    scratch=layout.scratch; registers=layout.registers
    out=[]

    def add(wires, constant, controls=()):
        out.extend(_add(wires,constant % grid,controls,scratch))

    def accumulate(source, target, coefficient):
        for i,q in enumerate(source): add(target,coefficient*(1 << i),(q,))

    if op.kind=="read":
        if mode==layout.omit_mode:
            add(record,_sector_target(layout.config)-ref)
            for wires in registers:
                if wires: accumulate(wires,record,-1)
        else:
            # On fresh zero memory this copies the basis label, not an
            # unknown quantum state; superpositions become correlated.
            out.extend(("cx",(x,y)) for x,y in zip(registers[mode],record))
            add(record,-ref)
    else:
        # |x,y> -> |a+y,x-a>; clean y=0 gives reset with retained old outcome.
        wires=registers[mode]
        add(wires,-ref)
        for x,y in zip(wires,record):
            out.extend((("cx",(x,y)),("cx",(y,x)),("cx",(x,y))))
        add(wires,ref)
    return tuple(out)


def compile_controller(operations, *, config=None, omit_mode=None, max_records=16, max_gates=MAX_GATES):
    config=Config() if config is None else config
    layout=compile_register((),config=config,omit_mode=omit_mode)
    _word(operations,config,allow_instruments=True)
    integer(max_records,"record cap"); integer(max_gates,"gate cap")
    if not 0 <= max_records <= 64 or not 0 <= max_gates <= MAX_GATES:
        raise ValueError("controller cap out of range")
    count=sum(op.kind in ("read","reset") for op in operations)
    if count > max_records: raise ResourceLimit("retained record budget exceeded")
    if layout.n_qubits+count*layout.width > 256:
        raise ResourceLimit("controller exceeds existing 256-wire IR limit")
    if config.sector and any(op.kind=="reset" for op in operations):
        raise ValueError("single-mode reset does not preserve the whole fixed closure sector")
    records=[];gates=[]
    for step,op in enumerate(operations):
        if op.kind in ("read","reset"):
            start=layout.n_qubits+len(records)*layout.width
            wires=tuple(range(start,start+layout.width))
            block=_instrument_gates(op,layout,wires)
            records.append(Record(step,op.kind,*op.args,wires))
        else:
            block=compile_register((op,),config=config,omit_mode=omit_mode,max_gates=max_gates).gates
        if len(gates)+len(block)>max_gates:
            raise ResourceLimit("controller gate budget exceeded; no circuit returned")
        gates.extend(block)
    return ControllerProgram(config,operations,omit_mode,tuple(records),tuple(gates))


def verify_controller(program):
    """Source/gate/record consistency; shares compiler, not a formal prover."""
    try:
        if type(program) is not ControllerProgram: return False
        if type(program.records) is not tuple or len(program.records)>64: return False
        for r in program.records:
            if type(r) is not Record or type(r.kind) is not str or r.kind not in ("read","reset"): return False
            integer(r.step,"record step"); index(r.mode,4,"record mode"); integer(r.reference,"record reference")
            if type(r.wires) is not tuple: return False
            for q in r.wires: index(q,program.n_qubits,"record wire")
        if type(program.gates) is not tuple or len(program.gates)>MAX_GATES: return False
        for g in program.gates:
            if type(g) is not tuple or len(g)!=2: return False
            name,qs=g
            if type(name) is not str or name not in ("x","cx","ccx"): return False
            if type(qs) is not tuple or len(qs)!={"x":1,"cx":2,"ccx":3}[name] or len(set(qs))!=len(qs): return False
            for q in qs: index(q,program.n_qubits,"gate wire")
        return compile_controller(program.operations,config=program.config,omit_mode=program.omit_mode,
                                  max_records=64)==program
    except (ValueError,TypeError,AttributeError,IndexError): return False


@dataclass(frozen=True)
class ControllerTransition:
    before: Cell
    after: Cell
    program: ControllerProgram
    outcomes: tuple


def bind_controller(cell, program):
    if not verify_history(cell) or not verify_controller(program):
        raise ValueError("invalid source history or controller program")
    if cell.config!=program.config: raise ValueError("cell/controller configuration mismatch")
    after=cell;outcomes=[]
    for op in program.operations:
        after=after.apply(op)
        if op.kind in ("read","reset"): outcomes.append(after.events[-1].outcome)
    return ControllerTransition(cell,after,program,tuple(outcomes))


def verify_controller_transition(transition):
    try:
        if type(transition) is not ControllerTransition or type(transition.outcomes) is not tuple: return False
        for value in transition.outcomes: index(value,transition.program.config.grid,"record outcome")
        return (verify_history(transition.after) and
                bind_controller(transition.before,transition.program)==transition)
    except (ValueError,TypeError,AttributeError,IndexError): return False
