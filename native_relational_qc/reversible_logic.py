"""Exact Boolean oracles and clean-workspace quantum arithmetic.

Boolean values are basis labels, not amplitudes or independent probabilities.
Compile f as |x,y,0> -> |x,y XOR f(x),0> using X/CX/CCX only. The complete
input and phase information is retained. No thermal-energy claim is made.
"""
from collections import Counter
from dataclasses import dataclass

from .compact import CompactCircuit, ResourceLimit, _integer


@dataclass(frozen=True)
class BooleanMap:
    """Small exact truth table; row index and output word are little-endian."""
    input_bits: int
    output_bits: int
    table: tuple

    def __post_init__(self):
        _integer(self.input_bits, 'truth-table input bits', 0, 8)
        _integer(self.output_bits, 'truth-table output bits', 1, 8)
        if not isinstance(self.table, (tuple, list)) or len(self.table) != 1 << self.input_bits:
            raise ValueError('truth table needs exactly 2**input_bits rows')
        for value in self.table:
            _integer(value, 'truth-table output word', 0, (1 << self.output_bits)-1)
        object.__setattr__(self, 'table', tuple(self.table))

    def anf(self):
        """Unique multilinear polynomial over GF(2), as monomial bit masks."""
        outputs = []
        for bit in range(self.output_bits):
            coefficients = [(value >> bit) & 1 for value in self.table]
            for q in range(self.input_bits):
                for mask in range(1 << self.input_bits):
                    if mask & (1 << q):
                        coefficients[mask] ^= coefficients[mask ^ (1 << q)]
            outputs.append(tuple(mask for mask, value in enumerate(coefficients) if value))
        return tuple(outputs)


@dataclass(frozen=True)
class LogicProgram:
    circuit: CompactCircuit
    inputs: tuple
    outputs: tuple
    scratch: tuple
    registers: tuple
    function: str

    def append_to(self, circuit, mapping=None, *, inverse=False):
        """Append on distinct mapped wires; scratch must initially be zero.

        The caller owns that clean-workspace precondition. No measurement or
        reset is inserted to force it. The inverse is exact on the whole space.
        """
        if not isinstance(circuit, CompactCircuit):
            raise TypeError('destination must be CompactCircuit')
        if type(inverse) is not bool:
            raise ValueError('inverse must be boolean')
        mapping = tuple(range(self.circuit.n_qubits)) if mapping is None else tuple(mapping)
        if len(mapping) != self.circuit.n_qubits or len(set(mapping)) != len(mapping):
            raise ValueError('mapping must provide one distinct wire per program qubit')
        for q in mapping:
            _integer(q, 'mapped qubit', 0, circuit.n_qubits-1)
        operations = self.circuit.operations
        if any(name not in ('x','cx','ccx') for name, _ in operations):
            raise ValueError('logic program contains a gate outside its reversible alphabet')
        for name, qubits in reversed(operations) if inverse else operations:
            circuit.add(name, *(mapping[q] for q in qubits))
        return circuit

    def to_dict(self):
        return dict(schema='nrqc-reversible-logic-v1',function=self.function,
                    n_qubits=self.circuit.n_qubits,
                    inputs=list(self.inputs),outputs=list(self.outputs),scratch=list(self.scratch),
                    registers={name:list(wires) for name,wires in self.registers},
                    register_bit_order='little-endian',scratch_precondition='all zero',
                    scratch_postcondition='all zero',inputs_preserved=True,
                    operator_contract='|x,y,0> -> |x,y XOR f(x),0>',
                    phase_preserved=True,gate_counts=dict(Counter(name for name,_ in self.circuit.operations)),
                    gates=len(self.circuit.operations),
                    operations=[[name,list(qubits)] for name,qubits in self.circuit.operations])


def _monomial(controls, target, scratch):
    if not controls:
        return [('x',(target,))]
    if len(controls) == 1:
        return [('cx',(controls[0],target))]
    if len(controls) == 2:
        return [('ccx',(*controls,target))]
    compute = [('ccx',(controls[0],controls[1],scratch[0]))]
    for j in range(2,len(controls)-1):
        compute.append(('ccx',(scratch[j-2],controls[j],scratch[j-1])))
    return compute + [('ccx',(scratch[len(controls)-3],controls[-1],target))] + list(reversed(compute))


def compile_oracle(function, *, max_gates=100_000):
    """Synthesize a bounded truth table, preserving arbitrary output words.

    This exponential-size truth-table interface is deliberately capped at eight
    input bits. Large structured arithmetic uses ripple_adder instead.
    """
    if not isinstance(function, BooleanMap):
        raise TypeError('compile_oracle requires BooleanMap')
    cap = _integer(max_gates, 'oracle gate budget', 0, 1_000_000)
    polynomials = function.anf()
    degree = max((mask.bit_count() for terms in polynomials for mask in terms),default=0)
    cost = sum(max(1,2*mask.bit_count()-3) for terms in polynomials for mask in terms)
    if cost > cap:
        raise ResourceLimit('exact oracle gate budget exceeded; nothing was truncated')
    n,m = function.input_bits,function.output_bits
    inputs,outputs = tuple(range(n)),tuple(range(n,n+m))
    scratch = tuple(range(n+m,n+m+max(0,degree-2)))
    circuit = CompactCircuit(n+m+len(scratch))
    for target, terms in zip(outputs,polynomials):
        for mask in terms:
            controls = tuple(q for q in inputs if mask & (1 << q))
            for name,qubits in _monomial(controls,target,scratch):
                circuit.add(name,*qubits)
    return LogicProgram(circuit,inputs,outputs,scratch,
                        (('input',inputs),('output',outputs),('scratch',scratch)),'truth-table XOR oracle')


def gate_function(name):
    tables = {'not':(1,0),'and':(0,0,0,1),'or':(0,1,1,1),
              'nand':(1,1,1,0),'nor':(1,0,0,0),'xor':(0,1,1,0),'xnor':(1,0,0,1)}
    if not isinstance(name,str) or name not in tables:
        raise ValueError('logic gate must be not/and/or/nand/nor/xor/xnor')
    return BooleanMap(1 if name=='not' else 2,1,tables[name])


def _carry(a,b,cin,cout):
    # AB and (A XOR B)Cin are mutually exclusive on bits. XOR equals OR.
    # Temporarily change B to A XOR B, then restore it before returning.
    return [('ccx',(a,b,cout)),('cx',(a,b)),('ccx',(b,cin,cout)),('cx',(a,b))]


def ripple_adder(width):
    """Out-of-place coherent addition: outputs XOR (A+B+Cin), inputs intact.

    Registers: A[n], B[n], Cin, Sum[n], Cout, scratch[n-1]. Each is
    little-endian. All sum/carry output bits may start arbitrarily; scratch must
    start zero and is returned zero by reversing the internal carry calculation.
    Costs: 4n+1 qubits, 4n-2 CCX, 7n-2 CX; no global or relative phase change.
    """
    n = _integer(width, 'adder width', 1, 63)  # Native IR cap is 256 qubits.
    a,b = tuple(range(n)),tuple(range(n,2*n))
    cin = 2*n
    sums = tuple(range(2*n+1,3*n+1))
    cout = 3*n+1
    scratch = tuple(range(3*n+2,4*n+1))
    carries = (cin,*scratch,cout)
    operations,cleanup = [],[]
    for i in range(n):
        block = _carry(a[i],b[i],carries[i],carries[i+1])
        operations.extend(block)
        if i<n-1:
            cleanup.extend(block)
    for i in range(n):
        operations.extend(('cx',(q,sums[i])) for q in (a[i],b[i],carries[i]))
    operations.extend(reversed(cleanup))
    circuit = CompactCircuit(4*n+1)
    for name,qubits in operations:
        circuit.add(name,*qubits)
    return LogicProgram(circuit,(*a,*b,cin),(*sums,cout),scratch,
                        (('a',a),('b',b),('cin',(cin,)),('sum',sums),('cout',(cout,)),('scratch',scratch)),
                        f'{n}-bit addition with carry')
