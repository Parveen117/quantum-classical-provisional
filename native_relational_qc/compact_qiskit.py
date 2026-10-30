"""Strict named-gate bridge for the exact compact engine.

Dyadic phase gates use a documented canonical-float convention without tolerances.
RZ imports retain their scalar phase through exact named-gate decompositions.
Unknown gates, unbound parameters and measurements are rejected.
The existing dense adapter remains available for arbitrary finite unitary matrices.
"""
from .compact import CompactCircuit


def to_qiskit(circuit):
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import UnitaryGate
    import numpy as np
    qc = QuantumCircuit(circuit.n_qubits)
    for name, qargs in circuit.operations:
        from .phase_interop import phase_name
        phase_spec=phase_name(name)
        if phase_spec is not None:
            from math import pi
            from qiskit.circuit.library import PhaseGate
            turns,controlled=phase_spec
            gate=PhaseGate(2*pi*turns.numerator/turns.denominator)
            qc.append(gate.control() if controlled else gate,qargs)
        elif name == "r":
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
        CHGate, CSGate, CCXGate, SwapGate, PhaseGate, CPhaseGate, RZGate, U1Gate)
    if not isinstance(qc, QuantumCircuit):
        raise TypeError("expected QuantumCircuit")
    if qc.parameters or qc.global_phase != 0 or qc.num_clbits or getattr(qc, "num_vars", 0):
        raise ValueError("exact import requires a bound, phase-zero, unmeasured named-gate circuit")
    known = dict(zip((IGate, XGate, YGate, ZGate, HGate, SGate, SdgGate, TGate, TdgGate,
                     SXGate, SXdgGate, CXGate, CZGate, CHGate, CSGate, CCXGate, SwapGate, PhaseGate, CPhaseGate, RZGate, U1Gate),
                    ("id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx", "sxdg",
                     "cx", "cz", "ch", "cs", "ccx", "swap")))
    from .phase_interop import canonical_float_turns, phase_operations, rotation_operations
    from .phase_backend import PowerPhaseCircuit, required_order
    operations = []
    for item in qc.data:
        op = item.operation
        if isinstance(op, Barrier):
            continue
        base = getattr(op, "base_class", type(op))
        if base in (PhaseGate,CPhaseGate,RZGate,U1Gate):
            if getattr(op,"condition",None) is not None or (hasattr(op,"ctrl_state") and op.ctrl_state!=1):
                raise ValueError('conditional phases and open controls require explicit decomposition')
            turns=canonical_float_turns(op.params[0])
            qs=tuple(qc.find_bit(q).index for q in item.qubits)
            operations.extend((rotation_operations if isinstance(op,RZGate) else phase_operations)(turns,qs))
            continue
        if base not in known or op.params or getattr(op, "condition", None) is not None:
            raise ValueError(f"no declared exact import for {op.name}; use an explicit supported decomposition")
        if hasattr(op, "ctrl_state") and op.ctrl_state != 2**op.num_ctrl_qubits - 1:
            raise ValueError("open controls require an explicit exact decomposition")
        operations.append((known[base],tuple(qc.find_bit(q).index for q in item.qubits)))
    from .phase_interop import phase_name
    out=(PowerPhaseCircuit(qc.num_qubits,required_order(operations))
         if any(phase_name(n) is not None for n,_ in operations) else CompactCircuit(qc.num_qubits))
    for name,qs in operations:out.add(name,*qs)
    return out
