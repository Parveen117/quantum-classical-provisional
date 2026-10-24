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


def _sector_target(config):
    if config.sector not in (-1, 1):
        raise ValueError("a fixed closure sign is required")
    grid = config.grid
    return ((0 if config.sector == 1 else grid//2) - grid//4*config.twist) % grid


def _layout(config, omit_mode):
    width = _config(config)
    if omit_mode is not None:
        index(omit_mode, 4, "omitted mode")
        _sector_target(config)
    registers = []; start = 0
    for mode in range(4):
        if mode == omit_mode: registers.append(())
        else:
            registers.append(tuple(range(start, start+width)))
            start += width
    return tuple(registers), tuple(range(start, start+width-2))


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
    target = _sector_target(config)
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


def _sector_word(op, omitted, config):
    """Eliminate x_omitted = target - sum(retained) before gate lowering.

    Called only after whole-sector admissibility has passed. The generated
    operations are arithmetic instructions, not extra native Cell events.
    """
    kind, args = op.kind, op.args
    if kind == "pair_shift":
        j, s, d = args
        if j == omitted: return (Operation("shift", (s, -d)),)
        if s == omitted: return (Operation("shift", (j, d)),)
    elif kind == "pair_cut":
        j, s, h = args
        if s == omitted: return (Operation("cut", (j, h)),)
        if j == omitted:
            other = tuple(m for m in range(4) if m not in (omitted, s))
            return (Operation("cut", (s, 2*_sector_target(config)-h)),) + tuple(
                Operation("shear", (m, s, -2, 0)) for m in other)
    elif kind == "swap":
        j, s = args
        if j == s: return ()
        if omitted in args:
            retained = s if j == omitted else j
            other = tuple(m for m in range(4) if m not in (omitted, retained))
            return (Operation("cut", (retained, _sector_target(config))),) + tuple(
                Operation("shear", (m, retained, -1, 0)) for m in other)
    elif kind == "shift" and args[1] % config.grid == 0:
        return ()
    elif kind == "shear" and args[2] % config.grid == 0:
        return ()
    if omitted in (args[:2] if kind in ("shear", "swap", "pair_cut", "pair_shift") else args[:1]):
        raise ValueError("no lowering for this operation on the omitted mode")
    return (op,)


@dataclass(frozen=True)
class RegisterProgram:
    config: Config
    operations: tuple
    gates: tuple
    matrix: tuple
    offset: tuple
    omit_mode: object = None

    @property
    def width(self): return _config(self.config)

    @property
    def registers(self):
        return _layout(self.config, self.omit_mode)[0]

    @property
    def scratch(self): return _layout(self.config, self.omit_mode)[1]

    @property
    def phase_bits(self): return (4 if self.omit_mode is None else 3)*self.width

    @property
    def n_qubits(self): return self.phase_bits + len(self.scratch)

    def pack(self, phases):
        if type(phases) is not tuple or len(phases) != 4:
            raise ValueError("four wrapped phase labels required")
        for x in phases: index(x, self.config.grid, "wrapped phase")
        registers = self.registers
        if self.omit_mode is not None and sum(phases) % self.config.grid != _sector_target(self.config):
            raise ValueError("phase labels are outside the encoded closure sector")
        return sum(x << wires[0] for x, wires in zip(phases, registers) if wires)

    def unpack(self, label):
        integer(label, "basis label")
        if not 0 <= label < 1 << self.phase_bits:
            raise ValueError("basis label includes nonzero workspace or is out of range")
        phases = [(label >> wires[0]) & (self.config.grid-1) if wires else 0 for wires in self.registers]
        if self.omit_mode is not None:
            phases[self.omit_mode] = (_sector_target(self.config) - sum(phases)) % self.config.grid
        return tuple(phases)

    def image(self, phases):
        self.pack(phases)
        return tuple((sum(a*x for a, x in zip(row, phases))+b) % self.config.grid
                     for row, b in zip(self.matrix, self.offset))

    def stored_affine(self):
        """Map on stored coordinates after exact closure substitution."""
        if self.omit_mode is None: return self.matrix, self.offset
        omitted = self.omit_mode; target = _sector_target(self.config)
        kept = tuple(j for j in range(4) if j != omitted); grid = self.config.grid
        rows = tuple(tuple((self.matrix[i][j]-self.matrix[i][omitted]) % grid for j in kept) for i in kept)
        offset = tuple((self.offset[i]+self.matrix[i][omitted]*target) % grid for i in kept)
        return rows, offset

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
                    phase_bits=self.phase_bits, clean_scratch_bits=len(self.scratch),
                    total_logical_wires=self.n_qubits, source_operations=len(self.operations),
                    elementary_gates=len(self.gates), gate_counts=dict(Counter(n for n, _ in self.gates)),
                    full_phase_dimension=self.config.grid**4,
                    encoded_phase_labels=1 << self.phase_bits,
                    omitted_mode=self.omit_mode,
                    fixed_sector_information_bits=3*self.width,
                    compressed_sector_layout_implemented=self.omit_mode is not None,
                    gamma_lifts_history="external original Cell; not included in wire count",
                    physical_qubits_built=0)


def compile_register(operations, *, config=None, max_gates=MAX_GATES, omit_mode=None):
    """Full layout by default; omit one mode only in a fixed closure sector."""
    config = Config() if config is None else config
    registers, scratch = _layout(config, omit_mode); _word(operations, config)
    integer(max_gates, "gate cap")
    if not 0 <= max_gates <= MAX_GATES: raise ValueError("gate cap out of range")
    rows = tuple(tuple(int(i == j) for j in range(4)) for i in range(4))
    offset = (0, 0, 0, 0)
    gates = []
    for op in operations:
        rows, offset = _affine_step(rows, offset, op, config.grid)
        if not _preserves_sector(rows, offset, config):
            raise ValueError("operation prefix does not preserve the whole required closure sector")
        lower = (op,) if omit_mode is None else _sector_word(op, omit_mode, config)
        for instruction in lower:
            block = _primitive_word(instruction, registers, scratch, config.grid)
            if len(gates) + len(block) > max_gates:
                raise ResourceLimit("register gate budget exceeded; no circuit returned")
            gates.extend(block)
    return RegisterProgram(config, operations, tuple(gates), rows, offset, omit_mode)


def closure_codec(config, omit_mode, *, inverse=False, max_gates=MAX_GATES):
    """Full-register unitary: x_omitted <- sum(x)-sector_target (mod grid).

    On the declared sector the omitted register becomes zero and may be
    detached. Outside that sector it retains a nonzero syndrome; no erasure
    or sector projection is performed. The inverse restores four labels from
    three plus zero omitted register. Conversion itself still uses full width.
    """
    _layout(config, omit_mode)
    if omit_mode is None: raise ValueError("codec requires an omitted mode")
    if type(inverse) is not bool: raise TypeError("inverse must be bool")
    integer(max_gates, "codec gate cap")
    if not 0 <= max_gates <= MAX_GATES: raise ValueError("codec gate cap out of range")
    target = _sector_target(config)
    registers, scratch = _layout(config, None)
    word = tuple(Operation("shear", (m, omit_mode, 1, 0)) for m in range(4) if m != omit_mode)
    word += (Operation("shift", (omit_mode, -target)),)
    gates = []
    for op in word:
        block = _primitive_word(op, registers, scratch, config.grid)
        if len(gates) + len(block) > max_gates:
            raise ResourceLimit("closure codec gate budget exceeded; no circuit returned")
        gates.extend(block)
    circuit = CompactCircuit(4*_config(config)+len(scratch))
    for name, qs in reversed(gates) if inverse else gates: circuit.add(name, *qs)
    return circuit


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
        return compile_register(program.operations, config=program.config, omit_mode=program.omit_mode) == program
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
