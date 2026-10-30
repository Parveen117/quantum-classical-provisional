"""Exact dyadic phase syntax, shared by the Qiskit and OpenQASM bridges."""
import ast
from fractions import Fraction
from math import isfinite, pi
import re

MAX_ORDER = 4096
PHASE_NAME = re.compile(r'(c?)p([1-9][0-9]*)(dg)?\Z')


def phase_name(name):
    match=PHASE_NAME.fullmatch(name)
    if match is None:return None
    controlled,den,inverse=match.groups();den=int(den)
    if den<2 or den>MAX_ORDER or den&(den-1):raise ValueError('unsupported dyadic phase order')
    return Fraction(-1 if inverse else 1,den),bool(controlled)


def phase_operations(turns, qubits):
    """Binary expansion of an exact rational number of turns, with no rounding."""
    turns=Fraction(turns)
    if turns.denominator>MAX_ORDER or turns.denominator&(turns.denominator-1):
        raise ValueError('phase angle must be an exact fraction of 2*pi with power-of-two denominator <=4096')
    sign='dg' if turns<0 else '';n=abs(turns.numerator)%turns.denominator
    den=turns.denominator;out=[]
    while n:
        if n&1:out.append((('cp' if len(qubits)==2 else 'p')+str(den)+sign,tuple(qubits)))
        n>>=1;den>>=1
    return out


def rotation_operations(turns, qubits):
    if len(qubits)!=1:raise ValueError('rz requires one qubit')
    # Rz(theta) = P(theta/2) X P(-theta/2) X. The scalar phase is retained.
    half=Fraction(turns)/2
    return [('x',tuple(qubits))]+phase_operations(-half,qubits)+[('x',tuple(qubits))]+phase_operations(half,qubits)


def canonical_float_turns(angle):
    """Recognize only an exactly equal canonical binary64 dyadic-pi spelling.

    A Qiskit float carries no symbolic proof of an irrational angle. This
    explicitly declared import convention uses equality, never a tolerance or
    limit_denominator. Use OpenQASM symbolic expressions for an exact source.
    """
    if isinstance(angle,bool):raise ValueError('boolean angle')
    value=float(angle)
    if not isfinite(value) or abs(value)>4*pi:raise ValueError('phase outside canonical import range [-4*pi,4*pi]')
    for bits in range(13):
        den=1<<bits;n=round(value/(2*pi)*den)
        if value==2*pi*n/den:
            return Fraction(n,den)
    raise ValueError('angle is not a canonical exact dyadic fraction of 2*pi; approximate rounding is disabled')


def symbolic_turns(expression):
    """Parse rational arithmetic and pi, preserving a rational coefficient of pi."""
    if len(expression)>256:raise ValueError('angle expression too long')
    def visit(node):
        if isinstance(node,ast.Constant) and type(node.value) is int:return Fraction(node.value),Fraction(0)
        if isinstance(node,ast.Name) and node.id=='pi':return Fraction(0),Fraction(1)
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            a,b=visit(node.operand);return (a,b) if isinstance(node.op,ast.UAdd) else (-a,-b)
        if isinstance(node,ast.BinOp):
            a,b=visit(node.left);c,d=visit(node.right)
            if isinstance(node.op,ast.Add):return a+c,b+d
            if isinstance(node.op,ast.Sub):return a-c,b-d
            if isinstance(node.op,ast.Mult) and not b*d:return a*c,a*d+b*c
            if isinstance(node.op,ast.Div) and not d and c:return a/c,b/c
        raise ValueError('angle must use exact rational arithmetic with pi')
    try:a,b=visit(ast.parse(expression.strip(),mode='eval').body)
    except (SyntaxError,RecursionError,ZeroDivisionError) as error:raise ValueError('invalid exact angle expression') from error
    if a:raise ValueError('angle must be an exact multiple of pi')
    turns=b/2
    # Validate even when zero gates would result.
    phase_operations(turns,(0,))
    return turns
