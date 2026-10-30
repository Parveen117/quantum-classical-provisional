"""Reading a quadratic phase layer with shifted queries on the flat engine.

f(x) = x^T A x + b.x mod M on x in Z_M^n, M = 2^bits, A symmetric with
f(x) = sum_i A_ii x_i^2 + 2 sum_{i<j} A_ij x_i x_j + sum_i b_i x_i. The oracle
O_f|x> = zeta_M^{f(x)}|x> is a product of pK and cpK gates on the bit
expansion of x. A reversible increment of register i turns O_f^-1 followed by
O_f into the phase zeta_M^{f(x+e_i)-f(x)} = zeta_M^{2(Ax)_i + A_ii + b_i}: the
finite difference of a quadratic is linear, so one inverse QFT reads 2A_i
mod M, that is row i of A mod M/2. Over Z_{2^bits} the function determines A
only mod M/2 anyway (x^2 = x mod 2), so n shifted passes (2n oracle uses)
plus one pass for the linear remainder (1 use) determine the function class
exactly (Theorem Q3 in JET_READINGS_2.md). Everything is exact in Q(zeta_M).
The classical side is settled exactly too: a deterministic reader needs
n(n+3)/2 readings for M >= 4 (`classical_complexity`, attained by
`classical_reader`), so the quantum recipe uses fewer queries iff n >= 3,
ties at n = 2 and loses at n = 1; the counting bound `classical_lower_bound`
is weaker and not attained for n >= 2. The linear case is Bernstein and
Vazirani; the finite-difference trick is believed standard (no citation
verified here); the point here is the exact execution and the exact count.
"""
from itertools import product

from .compact import _integer
from .phase_backend import PowerPhaseCircuit,prepare
from .shor import append_inverse_qft

MAX_BITS=3   # the reversible increment below uses only x, cx, ccx (no larger controls)


def _layer(A,b,bits,n):
    M=1<<bits
    if not isinstance(A,(tuple,list)) or len(A)!=n or any(len(r)!=n for r in A):raise ValueError('A must be an n x n matrix')
    A=tuple(tuple(_integer(x,'quadratic entry',0,M-1) for x in r) for r in A)
    if any(A[i][j]!=A[j][i] for i in range(n) for j in range(n)):raise ValueError('A must be symmetric')
    b=tuple(_integer(x,'linear entry',0,M-1) for x in b)
    if len(b)!=n:raise ValueError('b must have n entries')
    return A,b,M


def evaluate(A,b,bits,x):
    n=len(b);A,b,M=_layer(A,b,bits,n)
    total=sum(A[i][i]*x[i]*x[i] for i in range(n))+2*sum(A[i][j]*x[i]*x[j] for i in range(n) for j in range(i+1,n))+sum(b[i]*x[i] for i in range(n))
    return total%M


def table(A,b,bits):
    n=len(b);M=1<<bits
    return tuple(evaluate(A,b,bits,x) for x in product(range(M),repeat=n))


def same_function(A1,b1,A2,b2,bits):return table(A1,b1,bits)==table(A2,b2,bits)


def canonical(A,b,bits):
    """Representative of the function class: A_ii, A_ij reduced mod M/2, b adjusted accordingly.

    (A_ii, b_i) -> (A_ii mod M/2, b_i + (M/2) floor(A_ii / (M/2)) mod M); A_ij -> A_ij mod M/2.
    Proposition Q3(i): this representative defines the same function.
    """
    n=len(b);A,b,M=_layer(A,b,bits,n);half=M//2
    Ac=[[A[i][j]%half for j in range(n)] for i in range(n)]
    bc=[(b[i]+half*(A[i][i]//half))%M for i in range(n)]
    return tuple(tuple(r) for r in Ac),tuple(bc)


def count_functions(bits,n):
    """Number of distinct functions and the matching formula (M/2)^(n(n+1)/2) * M^n."""
    M=1<<bits;seen=set()
    entries=n*(n+1)//2
    for upper in product(range(M),repeat=entries):
        A=[[0]*n for _ in range(n)];k=0
        for i in range(n):
            for j in range(i,n):A[i][j]=A[j][i]=upper[k];k+=1
        for b in product(range(M),repeat=n):seen.add(table(A,b,bits))
    formula=(M//2)**entries*M**n
    return len(seen),formula


def classical_lower_bound(bits,n):
    """Counting bound for deterministic readings of f, one residue mod M each: k >= ceil(log_M(#functions)).

    Not attained for n >= 2 at these sizes; the exact deterministic complexity
    is `classical_complexity` (Theorem Q3(v)).
    """
    M=1<<bits;entries=n*(n+1)//2;count=(M//2)**entries*M**n;k=0;reach=1
    while reach<count:reach*=M;k+=1
    return k


def classical_complexity(bits,n):
    """Exact deterministic (adaptive allowed) classical reading complexity of the class: n(n+3)/2 for M >= 4, n for M = 2.

    Theorem Q3(v) in JET_READINGS_2.md: every correct decision tree has depth
    at least dim_F2(R/2R) = n(n+3)/2 (Nakayama over the local ring Z_M), and
    the nonadaptive points `nonadaptive_points(n)` attain it.
    """
    return n if bits==1 else n*(n+3)//2


def nonadaptive_points(n):
    """P0 = {e_i, 2e_i (i < n), e_i + e_j (i < j)}: n(n+3)/2 reading points that identify the class for M >= 4."""
    e=lambda i:tuple(int(k==i) for k in range(n))
    points=[]
    for i in range(n):points.append(e(i));points.append(tuple(2*x for x in e(i)))
    for i in range(n):
        for j in range(i+1,n):points.append(tuple(x+y for x,y in zip(e(i),e(j))))
    return points


def classical_reader(A,b,bits):
    """Read f at the n(n+3)/2 points of P0 and decode the canonical representative exactly (no oracle, no circuit).

    f(2e_i) - 2 f(e_i) = 2 A_ii, f(e_i) = A_ii + b_i, f(e_i+e_j) - f(e_i) - f(e_j) = 2 A_ij, all mod M; each 2A entry
    determines A mod M/2, and b^_i = f(e_i) - A^_ii.
    """
    n=len(b);A,b,M=_layer(A,b,bits,n);half=M//2
    f={p:evaluate(A,b,bits,p) for p in nonadaptive_points(n)}
    e=lambda i:tuple(int(k==i) for k in range(n))
    Ahat=[[0]*n for _ in range(n)];bhat=[0]*n
    for i in range(n):
        doubled=(f[tuple(2*x for x in e(i))]-2*f[e(i)])%M
        if doubled%2:raise ArithmeticError('reading is not even')
        Ahat[i][i]=(doubled//2)%half;bhat[i]=(f[e(i)]-Ahat[i][i])%M
    for i in range(n):
        for j in range(i+1,n):
            doubled=(f[tuple(x+y for x,y in zip(e(i),e(j)))]-f[e(i)]-f[e(j)])%M
            if doubled%2:raise ArithmeticError('reading is not even')
            Ahat[i][j]=Ahat[j][i]=(doubled//2)%half
    return dict(A_hat=tuple(tuple(r) for r in Ahat),b_hat=tuple(bhat),readings=len(f),same_function=same_function(A,b,Ahat,bhat,bits),
                canonical_match=(tuple(tuple(r) for r in Ahat),tuple(bhat))==canonical(A,b,bits))


def shift_blind_pair(shifts,bits,n):
    """Proposition Q3(vi): shift vectors singular mod 2 leave two different classes with identical shift readings 2 A s mod M.

    Returns (N, v): N = (M/4) v v^T with v in {0,1}^n nonzero and v.s even for every shift, so 2 N s = 0 mod M for every
    shift (the reading of A = 0) while N is nonzero mod M/2. Requires M >= 4. Fewer than n shifts always leave such a v
    (k < n homogeneous equations over F_2 have a nonzero solution); n or more shifts leave one exactly when their matrix
    has rank < n over F_2. When the shifts span F_2^n the function raises ValueError: then (2 A s)_s determines A mod M/2
    (Q3(ii) with S invertible mod 2), so no blind pair exists.
    """
    M=1<<bits
    if M<4:raise ValueError('M >= 4 required')
    shifts=[tuple(_integer(x,'shift entry',0,M-1) for x in sh) for sh in shifts]
    if any(len(sh)!=n for sh in shifts):raise ValueError('shift vectors of length n required')
    for bitsv in range(1,1<<n):
        v=tuple((bitsv>>k)&1 for k in range(n))
        if all(sum(vi*si for vi,si in zip(v,sh))%2==0 for sh in shifts):
            N=tuple(tuple((M//4)*v[i]*v[j] for j in range(n)) for i in range(n))
            return N,v
    if len(shifts)<n:raise ArithmeticError('no blind vector found')   # impossible: k < n homogeneous equations over F_2 have a nonzero solution
    raise ValueError('the shifts span F_2^n: the shift readings determine A mod M/2, no blind pair exists')


# Circuits -----------------------------------------------------------------------------

def _wire(i,j,bits):return i*bits+j


def quadratic_oracle(circuit,A,b,bits,*,inverse=False,hidden=True):
    """Append O_f (or O_f^-1) as pK/cpK gates on n registers of `bits` qubits, LSB first.

    hidden=True counts the application on the circuit (`circuit.oracle_uses`):
    the reading's query count is the number of applications of the hidden
    oracle actually appended, not a formula. The remainder pass appends the
    inverse oracle of a representative it already knows with hidden=False.
    """
    n=len(b);A,b,M=_layer(A,b,bits,n);suffix='dg' if inverse else ''
    if hidden:circuit.oracle_uses=getattr(circuit,'oracle_uses',0)+1
    def phase(exponent,*wires):
        exponent%=M
        for t in range(bits):
            if exponent>>t&1:circuit.add(('c' if len(wires)==2 else '')+f'p{M>>t}'+suffix,*wires)
    for i in range(n):
        for j in range(bits):phase(A[i][i]*(1<<(2*j))+b[i]*(1<<j),_wire(i,j,bits))        # x_j^2 = x_j
        for j in range(bits):
            for k in range(j+1,bits):phase(2*A[i][i]*(1<<(j+k)),_wire(i,j,bits),_wire(i,k,bits))
    for i in range(n):
        for l in range(i+1,n):
            for j in range(bits):
                for k in range(bits):phase(2*A[i][l]*(1<<(j+k)),_wire(i,j,bits),_wire(l,k,bits))
    return circuit


def increment(circuit,wires,*,inverse=False):
    """x -> x+1 mod 2^len(wires) on LSB-first wires with x, cx, ccx only (1..3 wires)."""
    wires=tuple(wires)
    if not 1<=len(wires)<=MAX_BITS:raise ValueError('increment supports 1..3 wires')
    steps=[]
    if len(wires)==3:steps.append(('ccx',wires[0],wires[1],wires[2]))
    if len(wires)>=2:steps.append(('cx',wires[0],wires[1]))
    steps.append(('x',wires[0]))
    for name,*qs in (reversed(steps) if inverse else steps):circuit.add(name,*qs)
    return circuit


def shifted_row_circuit(A,b,bits,i):
    """H, O_f^-1, increment register i, O_f, decrement, inverse QFT on every register."""
    n=len(b);A,b,M=_layer(A,b,bits,n);_integer(i,'shift register',0,n-1);_integer(bits,'register bits',1,MAX_BITS)
    c=PowerPhaseCircuit(n*bits,max(8,M))
    for q in range(n*bits):c.add('h',q)
    quadratic_oracle(c,A,b,bits,inverse=True)
    increment(c,[_wire(i,j,bits) for j in range(bits)])
    quadratic_oracle(c,A,b,bits)
    increment(c,[_wire(i,j,bits) for j in range(bits)],inverse=True)
    for r in range(n):append_inverse_qft(c,[_wire(r,j,bits) for j in range(bits)])
    return c


def remainder_circuit(A,b,bits,representative):
    """H, O_f, inverse oracle of the quadratic part of the representative (b=0), inverse QFT: reads the linear remainder."""
    n=len(b);A,b,M=_layer(A,b,bits,n);rep,_,_=_layer(representative,(0,)*n,bits,n)
    c=PowerPhaseCircuit(n*bits,max(8,M))
    for q in range(n*bits):c.add('h',q)
    quadratic_oracle(c,A,b,bits)
    quadratic_oracle(c,rep,(0,)*n,bits,inverse=True,hidden=False)        # known representative, not a query
    for r in range(n):append_inverse_qft(c,[_wire(r,j,bits) for j in range(bits)])
    return c


def _registers(state,n,bits):
    M=1<<bits;out={}
    for ket,p in state.norms.items():
        key=tuple((ket>>(r*bits))&(M-1) for r in range(n));out[key]=out.get(key,state.field())+p
    return out


def read_quadratic_layer(A,b,bits,**limits):
    """2n+1 oracle uses: n shifted passes read A mod M/2 row by row; one pass reads the matching b.

    Returns the recovered (A_hat, b_hat), the exact distributions (each a
    point mass, Theorem Q3), the query count as counted on the executed
    circuits (2 per shifted pass, 1 for the remainder pass) and whether the
    recovered pair defines the same function as (A,b) on all of Z_M^n.
    """
    n=len(b);A,b,M=_layer(A,b,bits,n);half=M//2
    limits=dict(dict(max_work=100_000_000,max_branches=65_536),**limits)
    rows=[];distributions=[];stats=[];uses=0
    for i in range(n):
        circuit=shifted_row_circuit(A,b,bits,i);uses+=circuit.oracle_uses
        state=prepare(circuit,**limits);dist=_registers(state,n,bits)
        support=[k for k,v in dist.items() if v]
        if len(support)!=1 or dist[support[0]]!=state.field(1):raise ArithmeticError('shifted reading is not a point mass')
        doubled=support[0]
        if any(x%2 for x in doubled):raise ArithmeticError('shifted reading is not an even vector')
        rows.append(tuple(x//2 for x in doubled));distributions.append(dist);stats.append(state.budget.stats)
    A_hat=tuple(tuple(rows[i][j]%half for j in range(n)) for i in range(n))      # rows read mod M/2
    if any(A_hat[i][j]!=A_hat[j][i] for i in range(n) for j in range(n)):raise ArithmeticError('recovered rows are not symmetric')
    circuit=remainder_circuit(A,b,bits,A_hat);uses+=circuit.oracle_uses
    state=prepare(circuit,**limits);dist=_registers(state,n,bits)
    support=[k for k,v in dist.items() if v]
    if len(support)!=1 or dist[support[0]]!=state.field(1):raise ArithmeticError('remainder reading is not a point mass')
    b_hat=support[0];distributions.append(dist);stats.append(state.budget.stats)
    return dict(A_hat=A_hat,b_hat=b_hat,oracle_uses=uses,same_function=same_function(A,b,A_hat,b_hat,bits),
                canonical_match=(A_hat,b_hat)==canonical(A,b,bits),distributions=distributions,
                peak_branches=max(s['peak_branches'] for s in stats),work=sum(s['work_used'] for s in stats),
                classical_lower_bound=classical_lower_bound(bits,n),classical_complexity=classical_complexity(bits,n))
