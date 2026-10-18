"""Strict named-gate bridge for the exact compact engine.

No approximate float-to-exact inference. Unknown gates, parameterized rotations,
global phases and measurement instructions must be handled explicitly elsewhere.
The existing dense adapter remains available for arbitrary finite unitary matrices.
"""
from .compact import CompactCircuit


def to_qiskit(circuit):
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import UnitaryGate
    import numpy as np
    qc = QuantumCircuit(circuit.n_qubits)
    for name, qargs in circuit.operations:
        if name == "r":
            qc.append(UnitaryGate(np.array([[0, -1], [1, 0]], dtype=complex), label="R"), qargs)
        elif name == "k":
            qc.z(*qargs)
        elif name == "rk":
            qc.x(*qargs)
        elif name == "ct":
            from qiskit.circuit.library import TGate
            qc.append(TGate().control(), qargs)
        else:
            getattr(qc, name)(*qargs)
    return qc


def from_qiskit(qc):
    from qiskit import QuantumCircuit
    from qiskit.circuit import Barrier
    from qiskit.circuit.library import (IGate, XGate, YGate, ZGate, HGate,
        SGate, SdgGate, TGate, TdgGate, SXGate, SXdgGate, CXGate, CZGate,
        CHGate, CSGate, CCXGate, SwapGate)
    if not isinstance(qc, QuantumCircuit):
        raise TypeError("expected QuantumCircuit")
    if qc.parameters or qc.global_phase != 0 or qc.num_clbits or getattr(qc, "num_vars", 0):
        raise ValueError("exact import requires a bound, phase-zero, unmeasured named-gate circuit")
    known = dict(zip((IGate, XGate, YGate, ZGate, HGate, SGate, SdgGate, TGate, TdgGate,
                     SXGate, SXdgGate, CXGate, CZGate, CHGate, CSGate, CCXGate, SwapGate),
                    ("id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx", "sxdg",
                     "cx", "cz", "ch", "cs", "ccx", "swap")))
    out = CompactCircuit(qc.num_qubits)
    for item in qc.data:
        op = item.operation
        if isinstance(op, Barrier):
            continue
        base = getattr(op, "base_class", type(op))
        if base not in known or op.params or getattr(op, "condition", None) is not None:
            raise ValueError(f"no declared exact import for {op.name}; use an explicit supported decomposition")
        if hasattr(op, "ctrl_state") and op.ctrl_state != 2**op.num_ctrl_qubits - 1:
            raise ValueError("open controls require an explicit exact decomposition")
        out.add(known[base], *(qc.find_bit(q).index for q in item.qubits))
    return out
