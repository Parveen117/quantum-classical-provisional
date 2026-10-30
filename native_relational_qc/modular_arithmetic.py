"""Reversible constant modular arithmetic from X/CX/CCX, without truth tables.

All registers are little-endian. Workspace must start zero and is restored.
The multiplier fixes labels >= N, so its declared action is a permutation on
the complete input register, not just the orbit visited by order finding.
"""
from math import gcd
from .compact import _integer,ResourceLimit

MAX_GATES=100_000


def _extend(out,block):
    if len(out)+len(block)>MAX_GATES:
        raise ResourceLimit('modular synthesis gate budget exceeded; no circuit returned')
    out.extend(block)


def _mcx(controls,target,scratch):
    controls=tuple(controls)
    if not controls:return [('x',(target,))]
    if len(controls)==1:return [('cx',(*controls,target))]
    if len(controls)==2:return [('ccx',(*controls,target))]
    if len(scratch)<len(controls)-2:raise ValueError('insufficient clean ladder workspace')
    chain=[('ccx',(controls[0],controls[1],scratch[0]))]
    for j in range(2,len(controls)-1):chain.append(('ccx',(scratch[j-2],controls[j],scratch[j-1])))
    return chain+[('ccx',(scratch[len(controls)-3],controls[-1],target))]+list(reversed(chain))


def _add(register,constant,controls,scratch):
    """Add a constant modulo 2**len(register), conditional on every control.

    Each set constant bit is an increment of its suffix. High targets are
    toggled first so their carry predicates read the original lower bits.
    """
    out=[]
    for i in range(len(register)):
        if not (constant>>i)&1:continue
        for j in range(len(register)-1,i-1,-1):
            _extend(out,_mcx((*controls,*register[i:j]),register[j],scratch))
    return out


def _modadd(register,constant,modulus,controls,flag,scratch):
    """Controlled +constant mod N on 0<=register<N; top bit and flag clean.

    The extra top bit records a subtraction borrow. After conditional repair,
    subtracting the original addend reconstructs that borrow, clearing flag.
    Every primitive is self-inverse; reversing the list subtracts modulo N.
    """
    if constant==0:return []
    plus=_add(register,constant,controls,scratch)
    minus_n=list(reversed(_add(register,modulus,(),scratch)))
    repair=_add(register,modulus,(flag,),scratch)
    high=register[-1]
    out=[]
    for block in (plus,minus_n,[('cx',(high,flag))],repair,list(reversed(plus)),
                  [('x',(high,)),('cx',(high,flag)),('x',(high,))],plus):_extend(out,block)
    return out


def multiplier_workspace(width):
    return 2*_integer(width,'multiplier width',2,63)+4


def multiplier_operations(control,work,scratch,multiplier,modulus):
    """Controlled |x,0> -> |b*x mod N,0> for x<N, identity otherwise.

    Compute b*x into a clean accumulator by controlled modular additions,
    swap, then subtract b**(-1)*new_x to erase the old x. The modular inverse
    uses extended Euclid through pow(b,-1,N), not order finding or factoring.
    O(n) clean qubits and O(n**4) elementary gates per controlled multiplier.
    """
    work=tuple(work);scratch=tuple(scratch);n=len(work)
    _integer(n,'multiplier width',2,63)
    _integer(modulus,'modulus',3,(1<<n)-1)
    _integer(multiplier,'multiplier',1,modulus-1)
    if gcd(multiplier,modulus)!=1:raise ValueError('multiplier must be coprime to modulus')
    if len(scratch)!=multiplier_workspace(n):raise ValueError('wrong multiplier workspace size')
    wires=(control,*work,*scratch)
    if any(type(q) is not int or q<0 for q in wires) or len(set(wires))!=len(wires):
        raise ValueError('all arithmetic wires must be distinct nonnegative integers')
    if multiplier==1:return []
    accumulator=scratch[:n];high,flag,valid,enable=scratch[n:n+4];ladder=scratch[n+4:]
    register=(*accumulator,high)
    # Toggle valid iff x<N, restoring x and the shared high bit exactly.
    subtract=list(reversed(_add((*work,high),modulus,(),ladder)))
    compare=subtract+[('cx',(high,valid))]+list(reversed(subtract))
    out=compare+[('ccx',(control,valid,enable))]
    def accumulate(b):
        ops=[]
        for i,bit in enumerate(work):
            _extend(ops,_modadd(register,(b*(1<<i))%modulus,modulus,(enable,bit),flag,ladder))
        return ops
    _extend(out,accumulate(multiplier))
    for x,y in zip(work,accumulator):
        _extend(out,[('cx',(y,x)),('ccx',(enable,x,y)),('cx',(y,x))])
    _extend(out,list(reversed(accumulate(pow(multiplier,-1,modulus)))))
    out.append(('ccx',(control,valid,enable)))
    _extend(out,compare)
    return out


def append_multiplier(circuit,control,work,scratch,multiplier,modulus):
    operations=multiplier_operations(control,work,scratch,multiplier,modulus)
    if len(circuit.operations)+len(operations)>getattr(circuit,'max_gates',MAX_GATES):
        raise ResourceLimit('modular synthesis circuit budget exceeded')
    for name,qs in operations:circuit.add(name,*qs)
