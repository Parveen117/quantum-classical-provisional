"""Exact finite phase-cell proposal. See FOUNDATION.md for the added assumptions.

There is no amplitude vector, inner product, Born rule or quantum hardware API.
Every retained state and probability in this prototype is classical data.
"""

from dataclasses import dataclass
from fractions import Fraction as F


class ResourceLimit(ValueError):
    """A declared finite bound would be exceeded; no successor is returned."""


def integer(value, label):
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer, not a bool or float")
    return value


def rational(value, label, bits):
    if type(value) not in (int, F):
        raise TypeError(f"{label} must be an int or Fraction")
    value = F(value)
    if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > bits:
        raise ResourceLimit(f"{label} exceeds rational bit limit")
    return value


def index(value, size, label):
    integer(value, label)
    if not 0 <= value < size:
        raise ValueError(f"{label} out of range")


@dataclass(frozen=True)
class Config:
    grid: int = 64
    max_lift: int = 2**31 - 1
    max_events: int = 1024
    rational_bits: int = 4096
    first_cut_cost: F = F(1)
    decay: F = F(1, 2)
    sector: int = 0  # 0: unrestricted kinematics; +/-1: enforce closure sign
    twist: int = 0   # fixed integer quarter-turn twist, not derived curvature

    def __post_init__(self):
        for name in ("grid", "max_lift", "max_events", "rational_bits", "sector", "twist"):
            integer(getattr(self, name), name)
        if not 4 <= self.grid <= 4096 or self.grid % 4:
            raise ValueError("grid must be a multiple of four in [4, 4096]")
        if not self.grid <= self.max_lift <= 2**63 - 1:
            raise ValueError("max_lift must lie between grid and 2**63-1")
        if not 1 <= self.max_events <= 65536:
            raise ValueError("max_events must lie in [1, 65536]")
        if not 2 <= self.rational_bits <= 65536:
            raise ValueError("rational_bits must lie in [2, 65536]")
        if self.sector not in (-1, 0, 1) or abs(self.twist) > self.max_lift:
            raise ValueError("invalid closure sector or twist")
        c = rational(self.first_cut_cost, "first_cut_cost", self.rational_bits)
        q = rational(self.decay, "decay", self.rational_bits)
        if c < 0 or not 0 <= q < 1:
            raise ValueError("require first_cut_cost >= 0 and 0 <= decay < 1")
        object.__setattr__(self, "first_cut_cost", c)
        object.__setattr__(self, "decay", q)


@dataclass(frozen=True)
class Operation:
    kind: str
    args: tuple

    def __post_init__(self):
        arities = {"cut": 2, "shift": 2, "swap": 2, "shear": 4,
                   "read": 2, "reset": 2, "pair_cut": 3, "pair_shift": 3}
        if type(self.kind) is not str or self.kind not in arities:
            raise ValueError("unknown operation")
        if type(self.args) is not tuple or len(self.args) != arities[self.kind]:
            raise ValueError("wrong operation arity; use an immutable tuple")
        for value in self.args:
            integer(value, "operation argument")

    def inverse(self):
        if self.kind in ("cut", "pair_cut", "swap"):
            return self
        if self.kind == "shift":
            j, d = self.args
            return Operation("shift", (j, -d))
        if self.kind == "shear":
            c, t, k, a = self.args
            return Operation("shear", (c, t, -k, a))
        if self.kind == "pair_shift":
            a, b, d = self.args
            return Operation("pair_shift", (a, b, -d))
        raise ValueError("read/reset instruments have no physical inverse here")

    def rebase(self, delta):
        """Coordinate change, not an extra physical operation."""
        integer(delta, "origin shift")
        a = list(self.args)
        if self.kind == "cut":
            a[1] += 2 * delta
        elif self.kind == "pair_cut":
            a[2] += 2 * delta
        elif self.kind == "shear":
            a[3] += delta
        elif self.kind in ("read", "reset"):
            a[1] += delta
        return Operation(self.kind, tuple(a))


@dataclass(frozen=True)
class Snapshot:
    lifts: tuple
    charged_cuts: int
    cost: F
    next_cut_cost: F

    def __post_init__(self):
        if type(self.lifts) is not tuple or len(self.lifts) != 4:
            raise ValueError("snapshot requires four lifts")
        for v in self.lifts:
            integer(v, "lift")
        integer(self.charged_cuts, "charged cuts")
        if self.charged_cuts < 0:
            raise ValueError("negative charged count")
        if type(self.cost) is not F or type(self.next_cut_cost) is not F:
            raise TypeError("snapshot costs must be Fractions")
        if min(self.cost, self.next_cut_cost) < 0:
            raise ValueError("negative cost")


@dataclass(frozen=True)
class Event:
    operation: Operation
    before: Snapshot
    after: Snapshot
    outcome: object
    charged: bool

    def __post_init__(self):
        if type(self.operation) is not Operation or type(self.before) is not Snapshot or type(self.after) is not Snapshot:
            raise TypeError("invalid event types")
        if self.outcome is not None:
            integer(self.outcome, "outcome")
        if type(self.charged) is not bool:
            raise TypeError("charged must be bool")


def closure_sign(lifts, grid, twist):
    """Finite phase-closure predicate, not a dynamical or Born-rule theorem."""
    residue = (sum(lifts) + (grid // 4) * twist) % grid
    return 1 if residue == 0 else -1 if residue == grid // 2 else None


@dataclass(frozen=True)
class Cell:
    config: Config
    gamma: F
    initial: Snapshot
    state: Snapshot
    events: tuple = ()

    @classmethod
    def start(cls, lifts=(0, 0, 0, 0), *, config=None, gamma=F(1)):
        config = Config() if config is None else config
        if type(config) is not Config:
            raise TypeError("config must be Config")
        if type(lifts) is not tuple or len(lifts) != 4:
            raise ValueError("a cell requires four integer lifts in a tuple")
        for value in lifts:
            integer(value, "lift")
            if abs(value) > config.max_lift:
                raise ResourceLimit("initial lift limit")
        gamma = rational(gamma, "gamma", config.rational_bits)
        if gamma <= 0:
            raise ValueError("gamma must be positive")
        state = Snapshot(lifts, 0, F(0), config.first_cut_cost)
        if config.sector and closure_sign(lifts, config.grid, config.twist) != config.sector:
            raise ValueError("initial state outside required closure sector")
        return cls(config, gamma, state, state)

    @property
    def phases(self):
        return tuple(v % self.config.grid for v in self.state.lifts)

    @property
    def winding_lifts(self):
        """Algebraic lift quotients, not inferred continuous physical paths."""
        return tuple(v // self.config.grid for v in self.state.lifts)

    @property
    def dual_gamma(self):
        return 1 / self.gamma

    @property
    def closure(self):
        return closure_sign(self.state.lifts, self.config.grid, self.config.twist)

    def phase(self, mode, reference=0):
        index(mode, 4, "mode")
        integer(reference, "reference")
        if abs(reference) > self.config.max_lift:
            raise ResourceLimit("reference limit")
        return (self.state.lifts[mode] - reference) % self.config.grid

    def apply(self, operation):
        """Return a successor only after all bounds pass; self is immutable.

        Cost charges only phase-changing cuts. Other event costs are unspecified
        physically, not asserted free. See the explicitly proposed cost policy.
        """
        if type(operation) is not Operation:
            raise TypeError("operation must be Operation")
        cfg = self.config
        if len(self.events) >= cfg.max_events:
            raise ResourceLimit("event memory limit")
        kind, args = operation.kind, operation.args
        for value in args:
            if abs(value) > cfg.max_lift:
                raise ResourceLimit("operation parameter limit")
        index(args[0], 4, "mode")
        if kind in ("swap", "shear", "pair_cut", "pair_shift"):
            index(args[1], 4, "second mode")
        if kind in ("shear", "pair_cut", "pair_shift") and args[0] == args[1]:
            raise ValueError("coupled modes must differ")
        values = list(self.state.lifts)
        outcome, charged = None, False
        if kind == "cut":
            j, h = args
            charged = (h - 2 * values[j]) % cfg.grid != 0
            values[j] = h - values[j]
        elif kind == "shift":
            j, d = args
            values[j] += d
        elif kind == "swap":
            a, b = args
            values[a], values[b] = values[b], values[a]
        elif kind == "shear":
            c, t, k, a = args
            values[t] += k * (values[c] - a)
        elif kind == "pair_cut":
            j, reservoir, h = args
            charged = (h - 2 * values[j]) % cfg.grid != 0
            values[reservoir] += 2 * values[j] - h
            values[j] = h - values[j]
        elif kind == "pair_shift":
            j, reservoir, d = args
            values[j] += d
            values[reservoir] -= d
        else:
            j, a = args
            outcome = self.phase(j, a)
            if kind == "reset":
                values[j] = a
        if any(abs(v) > cfg.max_lift for v in values):
            raise ResourceLimit("successor lift limit")
        if cfg.sector and closure_sign(values, cfg.grid, cfg.twist) != cfg.sector:
            raise ValueError("operation leaves required closure sector")
        n, cost, rate = (self.state.charged_cuts, self.state.cost,
                         self.state.next_cut_cost)
        if charged:
            n += 1
            cost = rational(cost + rate, "cost", cfg.rational_bits)
            rate = rational(rate * cfg.decay, "next cut cost", cfg.rational_bits)
        after = Snapshot(tuple(values), n, cost, rate)
        event = Event(operation, self.state, after, outcome, charged)
        return Cell(cfg, self.gamma, self.initial, after, self.events + (event,))


def verify_history(cell):
    """Replay provenance for a Cell value; not cryptographic authentication.

    Direct dataclass construction is intended for inspectable certificates.
    Untrusted constructed values must pass this verifier before they are used.
    """
    try:
        if type(cell) is not Cell or type(cell.events) is not tuple:
            return False
        if len(cell.events) > cell.config.max_events:
            return False
        replay = Cell.start(cell.initial.lifts, config=cell.config, gamma=cell.gamma)
        if replay.initial != cell.initial:
            return False
        for event in cell.events:
            if type(event) is not Event:
                return False
            replay = replay.apply(event.operation)
            if replay.events[-1] != event:
                return False
        return replay.state == cell.state
    except (ValueError, TypeError, AttributeError, IndexError):
        return False


@dataclass(frozen=True)
class Readout:
    cell: int
    mode: int
    reference: int = 0

    def __post_init__(self):
        integer(self.cell, "cell")
        index(self.mode, 4, "mode")
        integer(self.reference, "reference")


@dataclass(frozen=True)
class Atom:
    weight: F
    cells: tuple


@dataclass(frozen=True)
class Preparation:
    """Positive normalized finite preparation, including correlated cells.

    Shared preparation is independent of later measurement settings. Local
    readout consequently obeys CHSH <= 2; see the proof, not just an example.
    """
    atoms: tuple
    MAX_ATOMS = 4096
    MAX_CELLS = 16
    MAX_WEIGHT_BITS = 4096
    MAX_READOUTS = 64

    def __post_init__(self):
        if type(self.atoms) is not tuple or not self.atoms:
            raise ValueError("preparation needs a nonempty tuple of atoms")
        if len(self.atoms) > self.MAX_ATOMS:
            raise ResourceLimit("preparation atom limit")
        signature, total = None, F(0)
        for atom in self.atoms:
            if type(atom) is not Atom or type(atom.cells) is not tuple:
                raise TypeError("use Atom(weight, tuple_of_cells)")
            if not 1 <= len(atom.cells) <= self.MAX_CELLS:
                raise ResourceLimit("preparation cell limit")
            weight = rational(atom.weight, "weight", self.MAX_WEIGHT_BITS)
            if weight <= 0:
                raise ValueError("atom weights must be strictly positive")
            if not all(verify_history(c) for c in atom.cells):
                raise ValueError("invalid cell provenance")
            current = tuple((c.config, c.gamma) for c in atom.cells)
            if signature is None:
                signature = current
            elif signature != current:
                raise ValueError("preparation atoms must describe the same cell types")
            total = rational(total + weight, "total weight", self.MAX_WEIGHT_BITS)
        if total != 1:
            raise ValueError("weights must sum exactly to one; no silent normalization")

    @property
    def size(self):
        return len(self.atoms[0].cells)

    def distribution(self, readouts):
        if type(readouts) is not tuple or not 1 <= len(readouts) <= self.MAX_READOUTS:
            raise ValueError("use 1..64 Readouts in a tuple")
        for r in readouts:
            if type(r) is not Readout:
                raise TypeError("expected Readout")
            index(r.cell, self.size, "cell")
        result = {}
        for atom in self.atoms:
            outcome = tuple(atom.cells[r.cell].phase(r.mode, r.reference)
                            for r in readouts)
            result[outcome] = rational(result.get(outcome, F(0)) + atom.weight,
                                       "outcome weight", self.MAX_WEIGHT_BITS)
        return result

    def act(self, cell, operation):
        index(cell, self.size, "cell")
        successors = []
        for atom in self.atoms:
            cells = list(atom.cells)
            cells[cell] = cells[cell].apply(operation)
            successors.append(Atom(atom.weight, tuple(cells)))
        return Preparation(tuple(successors))

    def independent(self, other):
        if type(other) is not Preparation:
            raise TypeError("expected Preparation")
        if len(self.atoms) * len(other.atoms) > self.MAX_ATOMS:
            raise ResourceLimit("joint preparation atom limit")
        if self.size + other.size > self.MAX_CELLS:
            raise ResourceLimit("joint preparation cell limit")
        return Preparation(tuple(
            Atom(rational(a.weight * b.weight, "joint weight", self.MAX_WEIGHT_BITS),
                 a.cells + b.cells) for a in self.atoms for b in other.atoms))

    def chsh(self, alice, bob):
        """Two local half-circle +/-1 settings per distinct cell.

        No filtering, setting-dependent preparation or communication is used.
        This finite binning is a model choice, not a quantum measurement law.
        """
        if type(alice) is not tuple or type(bob) is not tuple or len(alice) != 2 or len(bob) != 2:
            raise ValueError("two settings per party required")
        settings = alice + bob
        if not all(type(s) is Readout for s in settings):
            raise TypeError("settings must be Readouts")
        if alice[0].cell != alice[1].cell or bob[0].cell != bob[1].cell or alice[0].cell == bob[0].cell:
            raise ValueError("each party must read its own distinct cell")
        for s in settings:
            index(s.cell, self.size, "cell")
        correlations = []
        for a, b in ((alice[0], bob[0]), (alice[0], bob[1]),
                     (alice[1], bob[0]), (alice[1], bob[1])):
            d = self.distribution((a, b))
            la = self.atoms[0].cells[a.cell].config.grid
            lb = self.atoms[0].cells[b.cell].config.grid
            correlations.append(sum((w * (1 if x < la // 2 else -1) *
                                     (1 if y < lb // 2 else -1)
                                     for (x, y), w in d.items()), F(0)))
        value = correlations[0] + correlations[1] + correlations[2] - correlations[3]
        return tuple(correlations), value
