"""Orthogonal wrapped-phase register compiler using existing native arithmetic.

The new encoding is |x0,x1,x2,x3>, not the v0.3 two-site mixed state.
Only phase permutations are compiled. Gamma, lifts, cost and event records
remain in the original Cell; read/reset are not silently made reversible.
See REGISTER.md for proofs, clean-workspace requirements and physical limits.
"""
from collections import Counter
from dataclasses import dataclass

from native_relational_qc.compact import CompactCircuit
from native_relational_qc.modular_arithmetic import _add
from .model import Cell, Config, Operation, ResourceLimit, index, integer, verify_history

MAX_GATES = 100_000


def _config(config):
    if type(config) is not Config:
        raise TypeError("config must be Config")
    if config.grid & (config.grid - 1):
        raise ValueError("register compiler requires a power-of-two grid")
    return config.grid.bit_length() - 1


def _word(operations, config):
    if type(operations) is not tuple:
        raise TypeError("operations must be an immutable tuple")
    if len(operations) > config.max_events:
        raise ResourceLimit("register source-word event limit")
    for op in operations:
        if type(op) is not Operation:
            raise TypeError("source word requires Operation values")
        if op.kind in ("read", "reset"):
            raise ValueError("read/reset require instruments; not permutation compilation")
        for arg in op.args:
            if abs(arg) > config.max_lift:
                raise ResourceLimit("register source parameter limit")
        index(op.args[0], 4, "mode")
        if op.kind in ("swap", "shear", "pair_cut", "pair_shift"):
            index(op.args[1], 4, "second mode")
        if op.kind in ("shear", "pair_cut", "pair_shift") and op.args[0] == op.args[1]:
            raise ValueError("coupled modes must differ")


def _affine_step(rows, offset, op, grid):
    """Independent symbolic source semantics, not elementary-gate evaluation."""
    a, b = [list(row) for row in rows], list(offset)
    j = op.args[0]
    if op.kind == "cut":
        h = op.args[1]
        a[j] = [-v for v in a[j]]; b[j] = h - b[j]
    elif op.kind == "shift":
        b[j] += op.args[1]
    elif op.kind == "swap":
        s = op.args[1]
        a[j], a[s] = a[s], a[j]; b[j], b[s] = b[s], b[j]
    elif op.kind == "shear":
        c, t, k, ref = op.args
        a[t] = [x + k*y for x, y in zip(a[t], a[c])]
        b[t] += k*(b[c] - ref)
    elif op.kind == "pair_shift":
        j, s, d = op.args
        b[j] += d; b[s] -= d
    elif op.kind == "pair_cut":
        j, s, h = op.args
        a[s] = [x + 2*y for x, y in zip(a[s], a[j])]
        b[s] += 2*b[j] - h
        a[j] = [-v for v in a[j]]; b[j] = h - b[j]
    return tuple(tuple(v % grid for v in row) for row in a), tuple(v % grid for v in b)


def _preserves_sector(rows, offset, config):
    """Necessary and sufficient on the full affine sum sector over Z/grid."""
    if not config.sector:
        return True
    grid = config.grid
    target = ((0 if config.sector == 1 else grid//2) - grid//4*config.twist) % grid
    sums = tuple(sum(row[j] for row in rows) % grid for j in range(4))
    return len(set(sums)) == 1 and (sums[0]*target + sum(offset) - target) % grid == 0


def _primitive_word(op, registers, scratch, grid):
    """Lower source operations; reuse modular_arithmetic._add and its ladder."""
    out = []

    def add(mode, constant, controls=()):
        out.extend(_add(registers[mode], constant % grid, controls, scratch))

    def accumulate(control, target, multiplier):
        for bit, wire in enumerate(registers[control]):
            add(target, multiplier*(1 << bit), (wire,))

    def cut(mode, h):
        out.extend(("x", (wire,)) for wire in registers[mode])
        add(mode, h + 1)  # bitwise complement is -x-1 modulo grid

    kind, args = op.kind, op.args
    if kind == "cut": cut(*args)
    elif kind == "shift": add(*args)
    elif kind == "pair_shift":
        j, s, d = args; add(j, d); add(s, -d)
    elif kind == "pair_cut":
        j, s, h = args
        accumulate(j, s, 2); add(s, -h); cut(j, h)
    elif kind == "shear":
        c, t, k, ref = args
        accumulate(c, t, k); add(t, -k*ref)
    elif kind == "swap":
        j, s = args
        if j != s:
            for x, y in zip(registers[j], registers[s]):
                out.extend((("cx", (x, y)), ("cx", (y, x)), ("cx", (x, y))))
    return tuple(out)


@dataclass(frozen=True)
class RegisterProgram:
    config: Config
    operations: tuple
    gates: tuple
    matrix: tuple
    offset: tuple

    @property
    def width(self): return _config(self.config)

    @property
    def registers(self):
        w = self.width
        return tuple(tuple(range(j*w, (j+1)*w)) for j in range(4))

    @property
    def scratch(self): return tuple(range(4*self.width, 5*self.width-2))

    @property
    def n_qubits(self): return 4*self.width + len(self.scratch)

    def pack(self, phases):
        if type(phases) is not tuple or len(phases) != 4:
            raise ValueError("four wrapped phase labels required")
        for x in phases: index(x, self.config.grid, "wrapped phase")
        return sum(x << (j*self.width) for j, x in enumerate(phases))

    def unpack(self, label):
        integer(label, "basis label")
        if not 0 <= label < 1 << (4*self.width):
            raise ValueError("basis label includes nonzero workspace or is out of range")
        return tuple((label >> (j*self.width)) & (self.config.grid-1) for j in range(4))

    def image(self, phases):
        self.pack(phases)
        return tuple((sum(a*x for a, x in zip(row, phases))+b) % self.config.grid
                     for row, b in zip(self.matrix, self.offset))

    def to_circuit(self, *, inverse=False):
        """Fresh existing IR; validates witness before returning any circuit.

        Requires scratch=0 to realize the phase map; the complete gate word
        is unitary even with dirty scratch, but then has a different contract.
        """
        if type(inverse) is not bool: raise TypeError("inverse must be bool")
        if not verify_program(self): raise ValueError("invalid register program")
        circuit = CompactCircuit(self.n_qubits)
        for name, qs in reversed(self.gates) if inverse else self.gates:
            circuit.add(name, *qs)
        return circuit

    def resources(self):
        return dict(grid=self.config.grid, bits_per_mode=self.width,
                    phase_bits=4*self.width, clean_scratch_bits=len(self.scratch),
                    total_logical_wires=self.n_qubits, source_operations=len(self.operations),
                    elementary_gates=len(self.gates), gate_counts=dict(Counter(n for n, _ in self.gates)),
                    full_phase_dimension=self.config.grid**4,
                    fixed_sector_information_bits=3*self.width,
                    compressed_sector_layout_implemented=False,
                    gamma_lifts_history="external original Cell; not included in wire count",
                    physical_qubits_built=0)


def compile_register(operations, *, config=None, max_gates=MAX_GATES):
    config = Config() if config is None else config
    width = _config(config); _word(operations, config)
    integer(max_gates, "gate cap")
    if not 0 <= max_gates <= MAX_GATES: raise ValueError("gate cap out of range")
    rows = tuple(tuple(int(i == j) for j in range(4)) for i in range(4))
    offset = (0, 0, 0, 0)
    registers = tuple(tuple(range(j*width, (j+1)*width)) for j in range(4))
    scratch = tuple(range(4*width, 5*width-2))
    gates = []
    for op in operations:
        rows, offset = _affine_step(rows, offset, op, config.grid)
        if not _preserves_sector(rows, offset, config):
            raise ValueError("operation prefix does not preserve the whole required closure sector")
        block = _primitive_word(op, registers, scratch, config.grid)
        if len(gates) + len(block) > max_gates:
            raise ResourceLimit("register gate budget exceeded; no circuit returned")
        gates.extend(block)
    return RegisterProgram(config, operations, tuple(gates), rows, offset)


def verify_program(program):
    """Recompute source/gate binding; not an independent formal proof system.

    Independent basis/coherent checks and the arithmetic proof are in tests
    and REGISTER.md. A hash alone would not establish semantic correctness.
    """
    try:
        if type(program) is not RegisterProgram: return False
        if type(program.gates) is not tuple or len(program.gates) > MAX_GATES: return False
        for gate in program.gates:
            if type(gate) is not tuple or len(gate) != 2: return False
            name, qs = gate
            if type(name) is not str or name not in ("x", "cx", "ccx"): return False
            if type(qs) is not tuple or len(qs) != {"x":1, "cx":2, "ccx":3}[name]: return False
            if len(set(qs)) != len(qs): return False
            for q in qs: index(q, program.n_qubits, "gate wire")
        if type(program.matrix) is not tuple or len(program.matrix) != 4: return False
        for row in program.matrix:
            if type(row) is not tuple or len(row) != 4: return False
            for x in row: index(x, program.config.grid, "affine coefficient")
        if type(program.offset) is not tuple or len(program.offset) != 4: return False
        for x in program.offset: index(x, program.config.grid, "affine offset")
        return compile_register(program.operations, config=program.config) == program
    except (ValueError, TypeError, AttributeError, IndexError):
        return False


@dataclass(frozen=True)
class RegisterTransition:
    before: Cell
    after: Cell
    program: RegisterProgram


def bind_cell(cell, program):
    """Retain original lifted-state/resource semantics for a known classical Cell.

    No measurement or copy of an unknown coherent register is implied.
    """
    if not verify_history(cell) or not verify_program(program):
        raise ValueError("invalid source history or register program")
    if cell.config != program.config: raise ValueError("cell/program configuration mismatch")
    after = cell
    for op in program.operations: after = after.apply(op)
    if after.phases != program.image(cell.phases):
        raise ArithmeticError("source cell and compiled phase map disagree")
    return RegisterTransition(cell, after, program)


def verify_transition(transition):
    try:
        return (type(transition) is RegisterTransition and
                verify_history(transition.after) and
                bind_cell(transition.before, transition.program) == transition)
    except (ValueError, TypeError, AttributeError, IndexError):
        return False
