"""Native static-unitary circuit and terminal observation semantics."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import numpy as np

from .algebra import MAX_QUBITS, apply_local, checked_int, controlled, gate, unitary
from .state import RelationalState


@dataclass(frozen=True)
class Operation:
    name: str
    qargs: tuple[int, ...]
    matrix: np.ndarray


class Circuit:
    """Independent NumPy evaluator. No accounts, sampling, or hardware calls.

    Terminal measurements explicitly map quantum indices to classical indices.
    No measurements means probabilities of all qubits in the computational basis.
    """

    def __init__(self, n_qubits: int, n_clbits: int = 0):
        self.n_qubits = checked_int(n_qubits, "qubits", 1, MAX_QUBITS)
        self.n_clbits = checked_int(n_clbits, "classical bits", 0, MAX_QUBITS)
        self._ops: list[Operation] = []
        self._measurements: list[tuple[int, int]] = []
        self._global_phase = 0.0

    @property
    def operations(self):
        return tuple(Operation(op.name, op.qargs, op.matrix.copy()) for op in self._ops)

    @property
    def measurements(self):
        return tuple(self._measurements)

    @property
    def global_phase(self):
        return self._global_phase

    def phase(self, theta):
        theta = float(theta)
        if not math.isfinite(theta):
            raise ValueError("phase must be finite")
        new_phase = self._global_phase + theta
        if not math.isfinite(new_phase):
            raise ValueError("accumulated phase must be finite")
        self._global_phase = new_phase
        return self

    def _q(self, q):
        return checked_int(q, "qubit", 0, self.n_qubits - 1)

    def append(self, matrix, qargs, name="unitary"):
        if self._measurements:
            raise ValueError("operations after measurement require a dynamic-circuit engine")
        qargs = tuple(self._q(q) for q in qargs)
        if not qargs or len(set(qargs)) != len(qargs):
            raise ValueError("gate qubits must be nonempty and distinct")
        matrix = unitary(matrix)
        if len(matrix) != 2**len(qargs):
            raise ValueError("matrix size and qubit count disagree")
        if not isinstance(name, str) or not name:
            raise ValueError("operation name must be a nonempty string")
        self._ops.append(Operation(name, qargs, matrix))
        return self

    def add(self, name, *qargs, theta=None):
        if name in {"cx", "cz"}:
            if theta is not None:
                raise ValueError(f"{name} does not accept an angle")
            return self.append(controlled(gate(name[-1])), qargs, name)
        return self.append(gate(name, theta), qargs, name)

    def control(self, matrix, control, *targets, name="controlled-unitary"):
        return self.append(controlled(matrix), (control, *targets), name)

    def measure(self, qubit, clbit):
        qubit = self._q(qubit)
        clbit = checked_int(clbit, "classical bit", 0, self.n_clbits - 1)
        if any(q == qubit or c == clbit for q, c in self._measurements):
            raise ValueError("terminal measurement map must use unique qubits and classical bits")
        self._measurements.append((qubit, clbit))
        return self

    def measure_all(self):
        if self._measurements:
            raise ValueError("measurement map already exists")
        if self.n_clbits not in (0, self.n_qubits):
            raise ValueError("measure_all requires zero or n_qubits classical bits")
        self.n_clbits = self.n_qubits
        self._measurements = [(q, q) for q in range(self.n_qubits)]
        return self

    def state(self, initial: RelationalState | None = None):
        initial = initial if initial is not None else RelationalState.zero(self.n_qubits)
        if initial.n_qubits != self.n_qubits:
            raise ValueError("initial state register does not match circuit")
        values = initial.amplitudes
        for op in self._ops:
            values = apply_local(values, op.matrix, op.qargs)
        values *= np.exp(1j * self._global_phase)
        # Do not hide a broken operation behind state normalization.
        norm_squared = float(np.vdot(values, values).real)
        if not np.isfinite(norm_squared) or abs(norm_squared - 1) > 1e-9:
            raise ArithmeticError("unitary evolution failed norm conservation")
        return RelationalState(values)

    def probabilities(self, initial=None):
        state = self.state(initial)
        if not self._measurements:
            return state.probabilities()
        out = np.zeros(2**self.n_clbits)
        for index, amplitude in enumerate(state.amplitudes):
            classical = sum(((index >> q) & 1) << c for q, c in self._measurements)
            out[classical] += abs(amplitude) ** 2
        return {format(i, f"0{self.n_clbits}b"): float(p) for i, p in enumerate(out)}

    def to_dict(self):
        return {
            "schema": "native-relational-circuit-v1", "qubits": self.n_qubits,
            "classical_bits": self.n_clbits, "global_phase": self._global_phase,
            "bit_order": "q0-lsb; displayed bitstrings high-to-low",
            "operations": [{"name": op.name, "qargs": list(op.qargs),
                            "real": np.where(op.matrix.real == 0, 0.0, op.matrix.real).tolist(),
                            "imag": np.where(op.matrix.imag == 0, 0.0, op.matrix.imag).tolist()}
                           for op in self._ops],
            "measurements": [list(pair) for pair in self._measurements],
        }

    @classmethod
    def from_dict(cls, payload):
        required = {"schema", "qubits", "classical_bits", "global_phase", "bit_order",
                    "operations", "measurements"}
        if not isinstance(payload, dict) or set(payload) != required:
            raise ValueError("invalid circuit document fields")
        if payload["schema"] != "native-relational-circuit-v1":
            raise ValueError("unsupported circuit schema")
        if payload["bit_order"] != "q0-lsb; displayed bitstrings high-to-low":
            raise ValueError("unsupported bit ordering")
        out = cls(payload["qubits"], payload["classical_bits"]).phase(payload["global_phase"])
        for op in payload["operations"]:
            if not isinstance(op, dict) or set(op) != {"name", "qargs", "real", "imag"}:
                raise ValueError("invalid operation fields")
            real, imag = np.asarray(op["real"], dtype=float), np.asarray(op["imag"], dtype=float)
            if real.shape != imag.shape:
                raise ValueError("real and imaginary matrix shapes differ")
            out.append(real + 1j * imag, op["qargs"], op["name"])
        for q, c in payload["measurements"]:
            out.measure(q, c)
        return out

    def digest(self):
        data = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(data.encode()).hexdigest()
