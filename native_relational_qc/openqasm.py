"""Strict static OpenQASM 2 subset with exact symbolic dyadic phases.

No Qiskit dependency. No measurements, opaque/custom gates, loops, includes
other than qelib1.inc, or decimal-to-rational guesses. Unsupported syntax fails.
"""
import re
from .phase_backend import PowerPhaseCircuit, required_order
from .phase_interop import phase_name, phase_operations, rotation_operations, symbolic_turns


def dumps(circuit):
    lines=['OPENQASM 2.0;', 'include "qelib1.inc";', f'qreg q[{circuit.n_qubits}];']
    for name,qs in circuit.operations:
        args=','.join(f'q[{q}]' for q in qs)
        phase=phase_name(name)
        if phase is not None:
            turns,controlled=phase
            name=('cu1' if controlled else 'u1')+f'({2*turns.numerator}*pi/{turns.denominator})'
        elif name=='ct':name='cu1(pi/4)'
        elif name=='cs':name='cu1(pi/2)'
        elif name=='r':
            lines.extend((f'z {args};',f'x {args};'));continue
        elif name in ('k','rk'):name={'k':'z','rk':'x'}[name]
        # Qelib1 includes rx, not sx/sxdg in every implementation: exact decompositions.
        elif name in ('sx','sxdg'):
            lines.extend((f'h {args};',f'{"s" if name=="sx" else "sdg"} {args};',f'h {args};'));continue
        lines.append(f'{name} {args};')
    return '\n'.join(lines)+'\n'


def loads(source):
    if not isinstance(source,str) or len(source.encode())>2*1024*1024:raise ValueError('OpenQASM input exceeds 2 MiB or is not text')
    source=re.sub(r'//[^\n]*','',source)
    statements=[s.strip() for s in source.split(';') if s.strip()]
    if not source.rstrip().endswith(';') or not statements or statements.pop(0)!='OPENQASM 2.0':
        raise ValueError('expected semicolon-terminated OPENQASM 2.0')
    registers={};width=0;operations=[];started=False
    for statement in statements:
        if statement=='include "qelib1.inc"' and not started:continue
        match=re.fullmatch(r'qreg\s+([a-zA-Z_]\w*)\[(\d+)\]',statement)
        if match and not started:
            name,n=match.group(1),int(match.group(2))
            if name in registers or n<1 or width+n>256:raise ValueError('invalid or duplicate qreg')
            registers[name]=(width,n);width+=n;continue
        started=True
        match=re.fullmatch(r'([a-z][a-z0-9]*)(?:\(([^;]+)\))?\s+(.+)',statement)
        if not match:raise ValueError('unsupported OpenQASM statement: '+statement[:80])
        name,angle,args=match.groups();qs=[]
        for arg in args.split(','):
            wire=re.fullmatch(r'\s*([a-zA-Z_]\w*)\[(\d+)\]\s*',arg)
            if not wire or wire.group(1) not in registers:raise ValueError('undeclared or malformed qubit')
            start,n=registers[wire.group(1)];index=int(wire.group(2))
            if index>=n:raise ValueError('qubit index out of range')
            qs.append(start+index)
        if len(set(qs))!=len(qs):raise ValueError('gate requires distinct qubits')
        if angle is not None:
            arity={'p':1,'u1':1,'cp':2,'cu1':2,'rz':1}.get(name)
            if arity!=len(qs):raise ValueError('unsupported parameterized gate or wrong arity')
            turns=symbolic_turns(angle)
            operations.extend((rotation_operations if name=='rz' else phase_operations)(turns,qs))
        else:operations.append((name,tuple(qs)))
        if len(operations)>1_000_000:raise ValueError('too many expanded gates')
    circuit=PowerPhaseCircuit(width,required_order(operations))
    for name,qs in operations:circuit.add(name,*qs)
    return circuit
