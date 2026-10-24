"""A declared complex EMK representation, independent of Qiskit.

Qargs use little-endian local indexing: qargs[0] is local bit zero.
Global phases of OPERATORS are retained, including under coherent control.
"""
from __future__ import annotations

import math
import numpy as np

MAX_QUBITS = 20
MAX_GATE_QUBITS = 5
ATOL = 1e-12


def checked_int(value: int, name: str, lower: int, upper: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{name} must be an integer")
    value = int(value)
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be in [{lower}, {upper}]")
    return value


def unitary(matrix, *, max_qubits=MAX_GATE_QUBITS) -> np.ndarray:
    raw = np.asarray(matrix)
    if raw.ndim != 2 or raw.shape[0] != raw.shape[1]:
        raise ValueError("gate must be square")
    size = raw.shape[0]
    if size < 2 or size & (size - 1) or size > 2**max_qubits:
        raise ValueError(f"gate size must be a power of two, at most {max_qubits} qubits")
    out = np.array(raw, dtype=complex, copy=True)
    if not np.isfinite(out).all():
        raise ValueError("gate entries must be finite")
    if not np.allclose(out.conj().T @ out, np.eye(size), atol=ATOL, rtol=0):
        raise ValueError("nonunitary transport requires an explicit channel or postselection")
    out.setflags(write=False)
    return out


I = np.eye(2, dtype=complex)
K = np.diag([1, -1]).astype(complex)
R = np.array([[0, -1], [1, 0]], dtype=complex)
RK = R @ K
X, Y, Z = RK, 1j * R, K
for _matrix in (I, K, R, RK, Y):
    _matrix.setflags(write=False)


def emk(a=0, b=0, c=0, d=0) -> np.ndarray:
    """Return a I + b K + c R + d RK, ONLY when unitary.

    This gate sector does not silently normalize general EMK/hyperbolic maps.
    """
    return unitary(a * I + b * K + c * R + d * RK)


def gate(name: str, theta: float | None = None) -> np.ndarray:
    fixed = {
        "id": I, "k": K, "r": R, "rk": RK,
        "x": X, "y": Y, "z": Z, "h": (K + RK) / math.sqrt(2),
        "s": np.diag([1, 1j]), "sdg": np.diag([1, -1j]),
        "t": np.diag([1, np.exp(1j * math.pi / 4)]),
        "tdg": np.diag([1, np.exp(-1j * math.pi / 4)]),
        "sx": ((1 + 1j) * I + (1 - 1j) * X) / 2,
        "swap": np.array([[1, 0, 0, 0], [0, 0, 1, 0],
                          [0, 1, 0, 0], [0, 0, 0, 1]]),
    }
    if name in fixed and theta is None:
        return unitary(fixed[name])
    if name not in {"rx", "ry", "rz", "rzz", "p"} or theta is None:
        raise ValueError(f"unknown gate or wrong parameters: {name}")
    theta = float(theta)
    if not math.isfinite(theta):
        raise ValueError("angle must be finite")
    if name == "p":
        return unitary(np.diag([1, np.exp(1j * theta)]))
    axis = {"rx": X, "ry": Y, "rz": Z, "rzz": np.kron(Z, Z)}[name]
    return unitary(math.cos(theta / 2) * np.eye(len(axis))
                   - 1j * math.sin(theta / 2) * axis)


def controlled(matrix, control_value=1) -> np.ndarray:
    """Controlled U with control as local bit 0, preserving U's phase."""
    control_value = checked_int(control_value, "control value", 0, 1)
    matrix = unitary(matrix, max_qubits=MAX_GATE_QUBITS - 1)
    out = np.eye(2 * len(matrix), dtype=complex)
    out[control_value::2, control_value::2] = matrix
    return unitary(out)


def apply_local(amplitudes: np.ndarray, matrix: np.ndarray, qargs: tuple[int, ...]):
    """Tensor contraction without forming a full-register gate matrix."""
    n = len(amplitudes).bit_length() - 1
    selected = [n - 1 - q for q in reversed(qargs)]
    axes = selected + [axis for axis in range(n) if axis not in selected]
    arranged = amplitudes.reshape((2,) * n).transpose(axes)
    evolved = matrix @ arranged.reshape(len(matrix), -1)
    return evolved.reshape((2,) * n).transpose(np.argsort(axes)).reshape(-1)
