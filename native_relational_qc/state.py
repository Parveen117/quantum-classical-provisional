"""Projective pure states with a complete joint amplitude representation."""
from __future__ import annotations

import numpy as np
from .algebra import MAX_QUBITS, checked_int


class RelationalState:
    """A nonzero complex ray; the canonical comparison metric is G = I.

    Normalization removes common scale but does not erase relative phases.
    Arrays returned by the public API are copies.
    """

    def __init__(self, amplitudes):
        raw = np.asarray(amplitudes)
        if raw.ndim != 1 or len(raw) < 2 or len(raw) & (len(raw) - 1):
            raise ValueError("state requires a one-dimensional 2**n array, n >= 1")
        n = len(raw).bit_length() - 1
        checked_int(n, "qubits", 1, MAX_QUBITS)
        values = np.array(raw, dtype=complex, copy=True)
        if not np.isfinite(values).all():
            raise ValueError("state entries must be finite")
        # Scale real/imaginary parts first to avoid overflow in abs(complex).
        scale = max(float(np.max(np.abs(values.real))), float(np.max(np.abs(values.imag))))
        if scale == 0:
            raise ValueError("the zero vector is not a relational state")
        values /= scale
        values /= np.linalg.norm(values)
        values.setflags(write=False)
        self._amplitudes = values
        self._n = n

    @classmethod
    def zero(cls, n: int):
        n = checked_int(n, "qubits", 1, MAX_QUBITS)
        values = np.zeros(2**n, dtype=complex)
        values[0] = 1
        return cls(values)

    @property
    def n_qubits(self):
        return self._n

    @property
    def amplitudes(self):
        return self._amplitudes.copy()

    def chart(self, pivot: int | None = None):
        """Ratios to a nonzero amplitude; automatic pivot avoids a singular chart."""
        if pivot is None:
            pivot = int(np.argmax(np.abs(self._amplitudes)))
        pivot = checked_int(pivot, "pivot", 0, len(self._amplitudes) - 1)
        if self._amplitudes[pivot] == 0:
            raise ValueError("zero pivot: choose a different relational chart")
        return pivot, self._amplitudes / self._amplitudes[pivot]

    def probabilities(self):
        return {format(i, f"0{self._n}b"): float(abs(a) ** 2)
                for i, a in enumerate(self._amplitudes)}

    def overlap(self, other: "RelationalState") -> float:
        if self._n != other._n:
            raise ValueError("overlap requires matching registers")
        return min(1.0, float(abs(np.vdot(self._amplitudes, other._amplitudes)) ** 2))

    def tensor(self, high: "RelationalState"):
        """self occupies low qubits; high occupies the higher qubits."""
        checked_int(self._n + high._n, "combined qubits", 1, MAX_QUBITS)
        return RelationalState(np.kron(high._amplitudes, self._amplitudes))
