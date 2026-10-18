"""Offline Qiskit exchange for declared dynamic-circuit semantics.

Export supports nested bit-equality conditions and rational Pauli noise (through
Aer floating channel probabilities). Import is deliberately strict: named exact
gates, measurement, reset and if-only blocks. No loops, else blocks, expressions,
conditional instruments or arbitrary noise instructions are guessed.
"""
from contextlib import ExitStack

from .compact import CompactCircuit
from .compact_qiskit import to_qiskit as static_export, from_qiskit as static_import
from .dynamic import DynamicCircuit


def to_qiskit(circuit):
    from qiskit import QuantumCircuit
    if not isinstance(circuit, DynamicCircuit):
        raise TypeError('expected DynamicCircuit')
    qc = QuantumCircuit(circuit.n_qubits, circuit.n_clbits)
    for op in circuit.operations:
        if op.kind == 'measure':
            qc.measure(op.qargs[0], op.cbit)
        elif op.kind == 'reset':
            qc.reset(op.qargs[0])
        elif op.kind == 'pauli':
            from qiskit_aer.noise import pauli_error
            channel = pauli_error([(label, float(weight)) for label, weight in op.weights])
            qc.append(channel.to_instruction(), op.qargs)
        else:
            gate = static_export(CompactCircuit(len(op.qargs)).add(op.name, *range(len(op.qargs))))
            with ExitStack() as conditions:
                for bit, value in op.condition:
                    conditions.enter_context(qc.if_test((qc.clbits[bit], value)))
                qc.append(gate.data[0].operation, op.qargs)
    return qc


def from_qiskit(qc):
    from qiskit import QuantumCircuit
    from qiskit.circuit import Barrier, Measure, Reset, Clbit, ClassicalRegister, IfElseOp
    if not isinstance(qc, QuantumCircuit):
        raise TypeError('expected QuantumCircuit')
    out = DynamicCircuit(qc.num_qubits, qc.num_clbits)

    def visit(block, qmap, cmap, condition):
        if (block.parameters or block.global_phase != 0 or getattr(block, 'num_vars', 0)
                or getattr(block, 'num_stretches', 0)):
            raise ValueError('exact dynamic import requires bound, phase-zero circuits without variables')
        for item in block.data:
            op = item.operation
            qs = tuple(qmap[block.find_bit(q).index] for q in item.qubits)
            cs = tuple(cmap[block.find_bit(c).index] for c in item.clbits)
            if isinstance(op, Barrier):
                continue
            if isinstance(op, IfElseOp):
                if len(op.blocks) != 1:
                    raise ValueError('else blocks require an explicit supported rewrite')
                if not isinstance(op.condition, tuple) or len(op.condition) != 2:
                    raise ValueError('only bit/register equality predicates are imported')
                target, value = op.condition
                if isinstance(target, Clbit):
                    bits = [target]
                elif isinstance(target, ClassicalRegister):
                    bits = list(target)
                else:
                    raise ValueError('unsupported classical predicate')
                if not isinstance(value, int) or not 0 <= value < 2**len(bits):
                    raise ValueError('classical equality value is outside register range')
                combined = dict(condition)
                for index, bit in enumerate(bits):
                    global_bit = cmap[block.find_bit(bit).index]
                    outcome = (value >> index) & 1
                    if global_bit in combined and combined[global_bit] != outcome:
                        raise ValueError('contradictory nested predicates require explicit simplification')
                    combined[global_bit] = outcome
                visit(op.blocks[0], qs, cs, combined)
            elif isinstance(op, (Measure, Reset)):
                if condition:
                    raise ValueError('conditional measurement/reset are outside this importer')
                if isinstance(op, Measure):
                    out.measure(qs[0], cs[0])
                else:
                    out.reset(qs[0])
            else:
                # Existing exact adapter checks actual declared gate classes,
                # bound parameters and closed controls, rather than gate names.
                if cs:
                    raise ValueError('unsupported classical instruction')
                single = QuantumCircuit(len(qs))
                single.append(op, range(len(qs)))
                imported = static_import(single)
                for name, local in imported.operations:
                    out.add(name, *(qs[q] for q in local), condition=condition)

    visit(qc, tuple(range(qc.num_qubits)), tuple(range(qc.num_clbits)), {})
    return out
