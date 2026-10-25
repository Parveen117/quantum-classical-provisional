"""Readings to jets: exact local expansions learned from point readings.

The existing learning task is fed the first Hessian layer (u,v) as given
numbers. Here the learner receives only point readings of the Hessian at
observer-chosen points, reconstructs the Taylor jet of the Hessian field at a
base point by exact rational interpolation, transports that jet to another
affine chart, and reads the chart-invariant selected curvature from it. A
one-query quantum reader for a linear phase layer runs on the unchanged flat
phase engine. Every quantity is a rational or a flat-field element; nothing
is rounded. See JET_READINGS.md for the statements and their scope.

Nothing here is a seam-calculus identity, a hardware claim, a universal
learner or a quantum speedup for the curvature task.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib
import json
from math import factorial

from .compact import ResourceLimit,_integer
from .phase_backend import PowerPhaseCircuit,prepare
from .shor import append_inverse_qft

SCHEMA='nrqc-jet-readings-v1'
MAX_DEGREE=6            # jets are truncated at total order <= MAX_DEGREE
MAX_ENERGY_DEGREE=24    # declared polynomial energies have total degree <= MAX_ENERGY_DEGREE
MAX_READINGS=4096
COEFFICIENT_BITS=4096


# Exact rationals and 2x2 matrices -------------------------------------------

def _q(value,name='coefficient'):
    if type(value) not in (int,Q):raise TypeError(f'{name} must be an exact int or Fraction')
    value=Q(value)
    if max(abs(value.numerator).bit_length(),value.denominator.bit_length())>COEFFICIENT_BITS:
        raise ValueError(f'{name} exceeds the coefficient bit limit')
    return value


def _point(point):
    if not isinstance(point,(tuple,list)) or len(point)!=2:raise ValueError('a point is an exact pair')
    return (_q(point[0],'coordinate'),_q(point[1],'coordinate'))


def _sym(h):
    """A symmetric 2x2 matrix is stored as (a,b,c) = (H11,H12,H22)."""
    if not isinstance(h,(tuple,list)) or len(h)!=3:raise ValueError('symmetric 2x2 reading needs three entries')
    return tuple(_q(x,'reading') for x in h)


def _matrix(rows):
    if not isinstance(rows,(tuple,list)) or len(rows)!=2 or any(len(r)!=2 for r in rows):
        raise ValueError('2x2 matrix required')
    return tuple(tuple(_q(x,'matrix entry') for x in r) for r in rows)


def _mul(a,b):return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(2)) for j in range(2)) for i in range(2))
def _det(a):return a[0][0]*a[1][1]-a[0][1]*a[1][0]
def _tr(a):return ((a[0][0],a[1][0]),(a[0][1],a[1][1]))
def _inv(a):
    d=_det(a)
    if not d:raise ValueError('singular matrix')
    return ((a[1][1]/d,-a[0][1]/d),(-a[1][0]/d,a[0][0]/d))
def _full(h):return ((h[0],h[1]),(h[1],h[2]))
def _packed(m):
    if m[0][1]!=m[1][0]:raise ArithmeticError('matrix is not symmetric')
    return (m[0][0],m[0][1],m[1][1])


# Exact bivariate polynomials: {(i,j): coefficient of s**i v**j} -------------

def _poly(coefficients):
    out={}
    for key,value in coefficients.items():
        if not isinstance(key,tuple) or len(key)!=2 or any(type(k) is not int or k<0 for k in key):
            raise ValueError('monomial exponents must be a pair of nonnegative integers')
        value=_q(value)
        if value:out[key]=value
    return out


def poly_eval(p,point):
    s,v=_point(point)
    return sum((c*s**i*v**j for (i,j),c in p.items()),Q())


def poly_diff(p,variable):
    out={}
    for (i,j),c in p.items():
        if variable==0 and i:out[(i-1,j)]=out.get((i-1,j),Q())+c*i
        if variable==1 and j:out[(i,j-1)]=out.get((i,j-1),Q())+c*j
    return {k:v for k,v in out.items() if v}


def poly_add(p,r,scale=1):
    out=dict(p)
    for k,v in r.items():out[k]=out.get(k,Q())+scale*v
    return {k:v for k,v in out.items() if v}


def poly_mul(p,r):
    out={}
    for (i,j),c in p.items():
        for (k,l),e in r.items():out[(i+k,j+l)]=out.get((i+k,j+l),Q())+c*e
    return {k:v for k,v in out.items() if v}


def poly_power(p,n):
    out={(0,0):Q(1)}
    for _ in range(n):out=poly_mul(out,p)
    return out


def poly_degree(p):return max((i+j for (i,j) in p),default=-1)


def poly_substitute(p,s_image,v_image):
    """p(s,v) with s:=s_image(s',v'), v:=v_image(s',v'); images are polynomials."""
    out={}
    for (i,j),c in p.items():out=poly_add(out,poly_mul(poly_power(s_image,i),poly_power(v_image,j)),c)
    return out


# Declared polynomial energy and its exact Hessian field ------------------------

@dataclass(frozen=True)
class PolynomialEnergy:
    """U(s,v) = sum c_ij s**i v**j, a declared exact polynomial in one affine chart.

    The cubic family of the existing learning task is cubic(u,v). Nothing is
    fitted: the coefficients define the model; readings are taken from it.
    """
    coefficients: dict

    def __post_init__(self):
        p=_poly(self.coefficients)
        if poly_degree(p)>MAX_ENERGY_DEGREE:raise ValueError('declared energy degree exceeds the module limit')
        object.__setattr__(self,'coefficients',p)

    @staticmethod
    def cubic(u,v,*,hessian=(2,1,5),gradient=(10,-10)):
        """The existing task family: g.q + q.H0.q/2 + (u s**3 + v w**3)/6."""
        a,b,c=_sym(hessian);g0,g1=(_q(x) for x in gradient)
        return PolynomialEnergy({(1,0):g0,(0,1):g1,(2,0):a/2,(1,1):b,(0,2):c/2,(3,0):Q(_q(u),6),(0,3):Q(_q(v),6)})

    def hessian_polynomials(self):
        p=self.coefficients;ps,pv=poly_diff(p,0),poly_diff(p,1)
        return (poly_diff(ps,0),poly_diff(ps,1),poly_diff(pv,1))

    def hessian(self,point):
        """One point reading: (H11,H12,H22) at the point, exactly."""
        return tuple(poly_eval(h,point) for h in self.hessian_polynomials())

    def hessian_degree(self):return max(poly_degree(h) for h in self.hessian_polynomials())

    def hessian_jet(self,base,order):
        """Taylor coefficients of H(base+delta) in delta up to total order."""
        base=_point(base);_integer(order,'jet order',0,MAX_DEGREE)
        shifted=[poly_substitute(h,{(1,0):Q(1),(0,0):base[0]},{(0,1):Q(1),(0,0):base[1]}) for h in self.hessian_polynomials()]
        jet={}
        for i in range(order+1):
            for j in range(order+1-i):
                jet[(i,j)]=tuple(h.get((i,j),Q()) for h in shifted)
        return Jet(base,jet)

    def curvature(self,point):
        """Selected native curvature kappa=(H F_sv)_12/det H with A_i=H^-1 H_i/2, F=-[A_s,A_v]."""
        return self.hessian_jet(point,1).curvature()

    def compose_linear(self,chart):
        """U'(q') = U(A q'): the same energy read by an observer using q = A q'."""
        A=_matrix(chart)
        if not _det(A):raise ValueError('chart change must be invertible')
        s={(1,0):A[0][0],(0,1):A[0][1]};v={(1,0):A[1][0],(0,1):A[1][1]}
        return PolynomialEnergy(poly_substitute(self.coefficients,s,v))

    def specification(self):
        return dict(kind='EXACT_POLYNOMIAL_ENERGY_2D',evidence_class='DECLARED_MODEL',
                    coefficients={f'{i},{j}':str(c) for (i,j),c in sorted(self.coefficients.items())},
                    hessian_degree=self.hessian_degree())


# Jets of the Hessian field ----------------------------------------------------

def _monomials(order):return [(i,j) for n in range(order+1) for i in range(n,-1,-1) for j in (n-i,)]


@dataclass(frozen=True)
class Jet:
    """H(base+delta) = sum_{|alpha|<=order} C_alpha delta**alpha (+ remainder).

    C_alpha are symmetric matrices stored packed. order is the truncation
    order; the jet says nothing about terms beyond it.
    """
    base: tuple
    coefficients: dict

    def __post_init__(self):
        base=_point(self.base);coeffs={}
        orders=set()
        for key,value in self.coefficients.items():
            if not isinstance(key,tuple) or len(key)!=2 or any(type(k) is not int or k<0 for k in key):
                raise ValueError('jet multi-index must be a pair of nonnegative integers')
            coeffs[key]=_sym(value);orders.add(key[0]+key[1])
        order=max(orders,default=-1)
        if order<0 or set(_monomials(order))!=set(coeffs):raise ValueError('jet must carry every multi-index up to its order')
        object.__setattr__(self,'base',base);object.__setattr__(self,'coefficients',coeffs)

    @property
    def order(self):return max(i+j for (i,j) in self.coefficients)

    def value(self,point):
        """Truncated expansion evaluated at an absolute point."""
        s,v=_point(point);ds,dv=s-self.base[0],v-self.base[1]
        return tuple(sum((c[k]*ds**i*dv**j for (i,j),c in self.coefficients.items()),Q()) for k in range(3))

    def hessian(self):return self.coefficients[(0,0)]

    def first_layer(self):
        """(partial_s H, partial_v H) at the base: the existing task's u=(H_s)11, v=(H_v)22."""
        if self.order<1:raise ValueError('first layer needs a jet of order at least one')
        return self.coefficients[(1,0)],self.coefficients[(0,1)]

    def derivative(self,alpha):
        """partial^alpha H(base) = alpha! C_alpha."""
        i,j=alpha
        return tuple(c*factorial(i)*factorial(j) for c in self.coefficients[(i,j)])

    def curvature(self):
        H=_full(self.hessian());d=_det(H)
        if H[0][0]<=0 or d<=0:raise ValueError('positive Hessian required for the selected curvature')
        Hs,Hv=(_full(x) for x in self.first_layer());inv=_inv(H)
        X,Y=_mul(inv,Hs),_mul(inv,Hv);XY,YX=_mul(X,Y),_mul(Y,X)
        F=tuple(tuple(-(XY[i][j]-YX[i][j])/4 for j in range(2)) for i in range(2))
        HF=_mul(H,F)
        if HF[0][0] or HF[1][1] or HF[0][1]!=-HF[1][0]:raise ArithmeticError('H F_sv is not antisymmetric')
        return HF[0][1]/d

    def transport(self,chart):
        """The same jet read in the chart q = A q' (A constant, invertible).

        H'(delta') = A^T H(A delta') A, so every coefficient tensor is pushed
        through the substitution delta = A delta' and conjugated by A. The
        base point becomes A^-1 base.
        """
        A=_matrix(chart);d=_det(A)
        if not d:raise ValueError('chart change must be invertible')
        inv=_inv(A);new_base=(inv[0][0]*self.base[0]+inv[0][1]*self.base[1],inv[1][0]*self.base[0]+inv[1][1]*self.base[1])
        s={(1,0):A[0][0],(0,1):A[0][1]};v={(1,0):A[1][0],(0,1):A[1][1]}
        entries=[]
        for k in range(3):
            p={key:c[k] for key,c in self.coefficients.items() if c[k]}
            entries.append(poly_substitute(p,s,v))
        out={}
        for key in _monomials(self.order):
            H=_full(tuple(e.get(key,Q()) for e in entries))
            out[key]=_packed(_mul(_tr(A),_mul(H,A)))
        return Jet(new_base,out)

    def record(self):
        return dict(base=[str(x) for x in self.base],order=self.order,
                    coefficients={f'{i},{j}':[str(x) for x in c] for (i,j),c in sorted(self.coefficients.items())})


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


# Readings ------------------------------------------------------------------------

class Reader:
    """Point readings of a Hessian field at observer-chosen points, counted.

    The learner never receives a derivative; it receives H at the points it
    asked for. Repeated points are served from the record without a new reading.
    """
    def __init__(self,energy,*,max_readings=256):
        if type(energy) is not PolynomialEnergy:raise TypeError('declared polynomial energy required')
        self.energy=energy;self.max_readings=_integer(max_readings,'reading budget',1,MAX_READINGS)
        self.record={};self.requests=0

    def read(self,point):
        point=_point(point);self.requests+=1
        if point in self.record:return self.record[point]
        if len(self.record)>=self.max_readings:raise ResourceLimit('reading budget exhausted; no jet returned')
        value=self.energy.hessian(point);self.record[point]=value
        return value

    @property
    def readings(self):return len(self.record)


# Exact interpolation of a jet from readings ------------------------------------

def _solve(rows,rhs):
    """Exact Gaussian elimination over Q; returns the solution or None if singular."""
    n=len(rows);m=len(rows[0]);a=[list(r)+[b] for r,b in zip(rows,rhs)]
    if n!=m:raise ValueError('square system required')
    for col in range(n):
        pivot=next((r for r in range(col,n) if a[r][col]),None)
        if pivot is None:return None
        a[col],a[pivot]=a[pivot],a[col];p=a[col][col]
        a[col]=[x/p for x in a[col]]
        for r in range(n):
            if r!=col and a[r][col]:
                f=a[r][col];a[r]=[x-f*y for x,y in zip(a[r],a[col])]
    return [a[r][n] for r in range(n)]


def design_rows(base,points,order):
    base=_point(base);mono=_monomials(order);rows=[]
    for point in points:
        s,v=_point(point);ds,dv=s-base[0],v-base[1]
        rows.append([ds**i*dv**j for (i,j) in mono])
    return rows


def fit_jet(base,readings,order):
    """Exact jet of the given order from exactly (order+1)(order+2)/2 readings.

    readings: list of (point,(H11,H12,H22)). The design must be unisolvent
    (nonsingular monomial matrix); otherwise ValueError. The returned jet
    reproduces every supplied reading exactly; it is the unique polynomial of
    total degree <= order doing so. Whether the field agrees elsewhere is a
    separate check (see check_jet).
    """
    base=_point(base);_integer(order,'jet order',0,MAX_DEGREE);mono=_monomials(order)
    readings=[(_point(p),_sym(h)) for p,h in readings]
    if len(readings)!=len(mono):raise ValueError(f'order {order} needs exactly {len(mono)} readings')
    if len({p for p,_ in readings})!=len(readings):raise ValueError('readings must be at distinct points')
    rows=design_rows(base,[p for p,_ in readings],order)
    solved=[_solve(rows,[h[k] for _,h in readings]) for k in range(3)]
    if any(s is None for s in solved):raise ValueError('design is not unisolvent for this order')
    jet=Jet(base,{key:(solved[0][n],solved[1][n],solved[2][n]) for n,key in enumerate(mono)})
    for p,h in readings:
        if jet.value(p)!=h:raise ArithmeticError('interpolant does not reproduce a reading')
    return jet


def check_jet(jet,readings):
    """Exact residuals of the truncated jet at check readings; empty list = consistent."""
    if type(jet) is not Jet:raise TypeError('jet required')
    out=[]
    for p,h in readings:
        p=_point(p);h=_sym(h);predicted=jet.value(p)
        if predicted!=h:out.append(dict(point=[str(x) for x in p],reading=[str(x) for x in h],predicted=[str(x) for x in predicted]))
    return out


def next_point(base,chosen,candidates,order):
    """Greedy exact choice: the candidate whose design row has the largest squared
    component orthogonal to the span of the chosen rows. A positive value means
    the candidate adds rank. Returns (point, squared_distance); (None,0) if no
    candidate adds rank. Heuristic for conditioning, not an optimality claim.
    """
    base=_point(base);chosen=[_point(p) for p in chosen];cands=[_point(p) for p in candidates]
    basis=[]
    for row in design_rows(base,chosen,order):
        r=list(row)
        for b in basis:
            c=sum(x*y for x,y in zip(r,b))/sum(y*y for y in b);r=[x-c*y for x,y in zip(r,b)]
        if any(r):basis.append(r)
    best=None;best_value=Q()
    for point,row in zip(cands,design_rows(base,cands,order)):
        if point in chosen:continue
        r=list(row)
        for b in basis:
            c=sum(x*y for x,y in zip(r,b))/sum(y*y for y in b);r=[x-c*y for x,y in zip(r,b)]
        value=sum(x*x for x in r)
        if value>best_value:best,best_value=point,value
    return best,best_value


def default_candidates(base,*,radius=3,step=Q(1,4)):
    base=_point(base);step=_q(step);_integer(radius,'candidate radius',1,8)
    if step<=0:raise ValueError('positive step required')
    return [(base[0]+i*step,base[1]+j*step) for i in range(-radius,radius+1) for j in range(-radius,radius+1)]


def learn_jet(reader,base,*,max_order=3,checks=3,candidates=None):
    """Readings -> jet, choosing where to read and how many derivatives to keep.

    For order d=0,1,...: read at a greedily chosen unisolvent design of
    (d+1)(d+2)/2 points (earlier readings reused), fit the exact order-d jet,
    then read `checks` fresh points and compare. If every check matches, stop
    and report the jet as consistent at order d. A consistent order is a
    falsifiable hypothesis about the field between the readings, not a
    certificate: see ghost_energy. If no order up to max_order is consistent,
    the result says so and returns the last fitted jet.
    """
    if type(reader) is not Reader:raise TypeError('counted Reader required')
    base=_point(base);_integer(max_order,'maximum jet order',0,MAX_DEGREE);_integer(checks,'check readings',1,16)
    candidates=[_point(p) for p in candidates] if candidates is not None else default_candidates(base)
    chosen=[];history=[];jet=None;status='no_consistent_order_up_to_%d'%max_order
    for order in range(max_order+1):
        need=len(_monomials(order))
        while len(chosen)<need:
            point,gain=next_point(base,chosen,candidates,order)
            if point is None:raise ValueError('candidate set cannot complete a unisolvent design at order %d'%order)
            chosen.append(point)
        design=chosen[:need]
        jet=fit_jet(base,[(p,reader.read(p)) for p in design],order)
        # Check points: chosen for the NEXT design so a failed check is reused.
        extra=[]
        while len(extra)<checks:
            point,gain=next_point(base,chosen+extra,candidates,order+1 if order<MAX_DEGREE else order)
            if point is None:
                leftover=[p for p in candidates if p not in chosen and p not in extra]
                if not leftover:break
                point=leftover[0]
            extra.append(point)
        residuals=check_jet(jet,[(p,reader.read(p)) for p in extra])
        history.append(dict(order=order,design=[[str(x) for x in p] for p in design],checks=[[str(x) for x in p] for p in extra],
                            mismatches=len(residuals),residuals=residuals))
        if not residuals:
            status='consistent_at_order_%d'%order;break
        chosen=chosen+[p for p in extra if p not in chosen]
    return dict(schema=SCHEMA,status=status,order=jet.order,jet=jet,readings=reader.readings,requests=reader.requests,
                history=history,hypothesis='the Hessian field is a polynomial of total degree <= order between the readings',
                certificate=False)


def ghost_energy(energy,points,*,scale=1,directions=None):
    """energy + scale * prod_k l_k(q)**3 with l_k a linear form vanishing at point k.

    Its Hessian equals the original Hessian at every listed point (each factor
    vanishes to third order there), so every reading at those points is
    unchanged, while the field differs elsewhere. Finite polynomial analogue of
    the earlier jet result that identical jets do not fix curvature away from
    the point (JED-T5 in the jet-entry report); here identical readings at
    finitely many points do not fix the jet or curvature elsewhere.
    """
    if type(energy) is not PolynomialEnergy:raise TypeError('declared polynomial energy required')
    points=[_point(p) for p in points];scale=_q(scale)
    if not points or len(set(points))!=len(points):raise ValueError('distinct ghost points required')
    directions=directions or [((1,0),(0,1),(1,1),(1,-1))[k%4] for k in range(len(points))]
    ghost={(0,0):Q(1)}
    for (s0,v0),(n0,n1) in zip(points,directions):
        n0,n1=_q(n0),_q(n1)
        if not (n0 or n1):raise ValueError('nonzero direction required')
        l={(1,0):n0,(0,1):n1,(0,0):-(n0*s0+n1*v0)}
        ghost=poly_mul(ghost,poly_power(l,3))
    total=poly_add(energy.coefficients,ghost,scale)
    if poly_degree(total)>MAX_ENERGY_DEGREE:raise ValueError('ghost energy exceeds the declared degree limit')
    return PolynomialEnergy(total)


# The existing parity classifier, reproduced on the flat engine -----------------

EXISTING_FIRST_LAYER_MODEL=dict(architecture='four-qubit-parity-five-ry-v1',phase_steps=(32,0,0,32,0),phase_unit='pi/32',
    feature_view='first_layer',fingerprint='e9335f96e2a81f026f350ba983734e5e5251904c05000878169e47ce12f3e394',
    source='native_relational_qc/learning/first_layer_model.json at codex/native-self-learning-v1-20261024 bd79ac4')


def _ry(circuit,q,steps):
    """RY(steps*pi/32) up to a retained global phase: S H P(theta) H S^dagger."""
    _integer(steps,'phase step',0,63)
    if not steps:return
    circuit.add('sdg',q).add('h',q)
    for bit in range(6):
        if steps&(1<<bit):circuit.add(f'p{64>>bit}',q)
    circuit.add('h',q).add('s',q)


def parity_classifier(features,parameters=EXISTING_FIRST_LAYER_MODEL['phase_steps']):
    """Exact probability of reading one on qubit 3 for the existing architecture."""
    if len(features)!=2 or len(parameters)!=5:raise ValueError('two feature steps and five parameter steps required')
    c=PowerPhaseCircuit(4,64)
    for q,step in enumerate(features):_ry(c,q,step)
    for q,step in enumerate(parameters[:4]):_ry(c,q,step)
    for a,b in ((0,2),(1,2),(2,3)):c.add('cx',a,b)
    _ry(c,3,parameters[4])
    state=prepare(c,max_work=100000,max_branches=16)
    return state.probability({3:1})


def first_layer_steps(jet):
    """The existing encoding 16+2u, 16+2v of the first layer read from a jet."""
    Hs,Hv=jet.first_layer();u,v=Hs[0],Hv[2];steps=(16+2*u,16+2*v)
    if any(x.denominator!=1 or not 0<=x<=63 for x in steps):raise ValueError('first layer outside the existing encoding range')
    return tuple(int(x) for x in steps)


def classify_first_layer(jet):
    """Existing frozen model applied to first-layer features read from readings; exact tie -> 0."""
    p=parity_classifier(first_layer_steps(jet))
    return int((p-Q(1,2)).real_sign()>0),p


# One-query quantum reading of a linear phase layer -----------------------------

def linear_phase_circuit(layer,bits):
    """n registers of `bits` qubits, order M=2**bits, oracle |x> -> zeta_M**(a.x)|x>.

    Hadamards prepare the uniform superposition, the oracle is a product of
    single-qubit phase gates (bit j of register i carries zeta_M**(a_i 2**j)),
    the inverse QFT of the Shor module is applied to each register, and the
    registers are read. Register i occupies qubits i*bits..i*bits+bits-1, least
    significant first.
    """
    _integer(bits,'register bits',1,12);M=1<<bits
    if not isinstance(layer,(tuple,list)) or not 1<=len(layer)<=8:raise ValueError('1..8 layer entries required')
    layer=tuple(_integer(a,'layer entry',0,M-1) for a in layer)
    n=len(layer);c=PowerPhaseCircuit(n*bits,max(8,M))
    for q in range(n*bits):c.add('h',q)
    for i,a in enumerate(layer):
        for j in range(bits):
            e=(a<<j)%M                      # phase exponent of zeta_M carried by this qubit
            for t in range(bits):
                if e>>t&1:c.add(f'p{M>>t}',i*bits+j)   # zeta_M**(2**t) = exp(2 pi i / (M/2**t))
    for i in range(n):append_inverse_qft(c,range(i*bits,i*bits+bits))
    return c


def read_linear_layer(layer,bits,**limits):
    """Exact outcome distribution over register values after one oracle query."""
    c=linear_phase_circuit(layer,bits);n=len(layer);M=1<<bits
    limits=dict(dict(max_work=100_000_000,max_branches=65_536),**limits)
    state=prepare(c,**limits)
    out={}
    for ket,value in state.amplitudes.items():
        key=tuple((ket>>(i*bits))&(M-1) for i in range(n))
        p=state.norms[ket]
        out[key]=out.get(key,c.field())+p
    return out,state.budget.stats


def quadratic_phase_distribution(a,b,bits):
    """Negative control: one register, oracle zeta_M**(a x**2 + b x), same readout.

    Returned as the exact distribution over register values; for a!=0 it is
    not concentrated on one value, so this single-query readout does not read
    a second layer the way it reads a first layer.
    """
    _integer(bits,'register bits',1,8);M=1<<bits;_integer(a,'quadratic entry',0,M-1);_integer(b,'linear entry',0,M-1)
    c=PowerPhaseCircuit(bits,max(8,M))
    for q in range(bits):c.add('h',q)
    # Diagonal phase x -> zeta_M**(a x**2 + b x) built from its bit expansion:
    # x**2 = sum_j x_j 2**(2j) + 2 sum_{j<k} x_j x_k 2**(j+k).
    for j in range(bits):
        e=(a*(1<<(2*j))+b*(1<<j))%M
        for t in range(bits):
            if e>>t&1:c.add(f'p{M>>t}',j)
    for j in range(bits):
        for k in range(j+1,bits):
            e=(2*a*(1<<(j+k)))%M
            for t in range(bits):
                if e>>t&1:c.add(f'cp{M>>t}',j,k)
    append_inverse_qft(c,range(bits))
    state=prepare(c,max_work=10_000_000,max_branches=4096)
    out={}
    for ket,value in state.amplitudes.items():out[ket&(M-1)]=out.get(ket&(M-1),c.field())+state.norms[ket]
    return out
