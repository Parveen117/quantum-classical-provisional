"""Learning a jet from certified enclosure readings: worst-case, exact, no probability.

A reading is now an exact rational interval per Hessian entry that contains
the true value. The learner propagates the intervals through the exact
inverse of the monomial design matrix, so every Taylor coefficient receives
an enclosure whose width is a declared function of the design (Theorem E1 in
JET_READINGS_2.md): width(c_alpha) = sum_q |(D^-1)_{alpha q}| w_q. Where to
read therefore matters here, unlike the exact case (Proposition E2: for a
three-point design the first-layer factors are 2 Dv/|det D| and 2 Ds/|det D|
with Ds, Dv the coordinate spreads, bounded below by 1/R inside a box of
half-side R; a larger |det D| alone does not mean a smaller width). The
selected curvature receives a valid (possibly loose) enclosure, and its sign
is certified only when that enclosure excludes zero; the numerator's range is
taken over the admissible readings themselves, which is exact (Proposition
E3), so the sign decision is the best any method ignoring integrability can
make, and `certification_threshold` computes the exact supremum half-width
at which it still works (Theorem E4). Validity is conditional on the declared
family: the Hessian field must have the fitted order, which check readings
can falsify but never certify (part 1, Theorem J3).

The interval widths are inputs declared by whoever supplies the readings;
they are not a noise model, not a statistic and not a device property.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import product

from .compact import ResourceLimit,_integer
from .jet_readings import (MAX_DEGREE,MAX_READINGS,PolynomialEnergy,_monomials,_point,_q,_sym,design_rows,next_point,
                           default_candidates)


@dataclass(frozen=True)
class Interval:
    lo: Q
    hi: Q

    def __post_init__(self):
        lo,hi=_q(self.lo,'interval bound'),_q(self.hi,'interval bound')
        if lo>hi:raise ValueError('interval bounds out of order')
        object.__setattr__(self,'lo',lo);object.__setattr__(self,'hi',hi)

    @staticmethod
    def point(value):value=_q(value);return Interval(value,value)

    @staticmethod
    def around(value,half_width):value=_q(value);w=_q(half_width,'half width');return Interval(value-abs(w),value+abs(w))

    @property
    def width(self):return self.hi-self.lo

    def __contains__(self,value):return self.lo<=_q(value)<=self.hi

    def __add__(self,other):
        other=other if isinstance(other,Interval) else Interval.point(other)
        return Interval(self.lo+other.lo,self.hi+other.hi)
    __radd__=__add__

    def __neg__(self):return Interval(-self.hi,-self.lo)

    def __sub__(self,other):return self+(-(other if isinstance(other,Interval) else Interval.point(other)))

    def __mul__(self,other):
        if not isinstance(other,Interval):
            k=_q(other);return Interval(self.lo*k,self.hi*k) if k>=0 else Interval(self.hi*k,self.lo*k)
        corners=(self.lo*other.lo,self.lo*other.hi,self.hi*other.lo,self.hi*other.hi)
        return Interval(min(corners),max(corners))
    __rmul__=__mul__

    def square(self):
        if self.lo>=0:return Interval(self.lo**2,self.hi**2)
        if self.hi<=0:return Interval(self.hi**2,self.lo**2)
        return Interval(Q(0),max(self.lo**2,self.hi**2))

    def reciprocal(self):
        if self.lo<=0<=self.hi:raise ZeroDivisionError('interval contains zero')
        return Interval(1/self.hi,1/self.lo)

    def sign(self):
        """+1, -1 or None (zero not excluded)."""
        return 1 if self.lo>0 else -1 if self.hi<0 else None

    def intersects(self,other):return self.lo<=other.hi and other.lo<=self.hi

    def record(self):return [str(self.lo),str(self.hi)]


def _reading(value):
    if not isinstance(value,(tuple,list)) or len(value)!=3 or any(type(v) is not Interval for v in value):
        raise ValueError('an enclosure reading is three Intervals (H11,H12,H22)')
    return tuple(value)


def _invert(rows):
    """Exact inverse of a square rational matrix, or None if singular."""
    n=len(rows);a=[list(r)+[Q(int(i==j)) for j in range(n)] for i,r in enumerate(rows)]
    for col in range(n):
        pivot=next((r for r in range(col,n) if a[r][col]),None)
        if pivot is None:return None
        a[col],a[pivot]=a[pivot],a[col];p=a[col][col];a[col]=[x/p for x in a[col]]
        for r in range(n):
            if r!=col and a[r][col]:
                f=a[r][col];a[r]=[x-f*y for x,y in zip(a[r],a[col])]
    return [row[n:] for row in a]


def design_inverse(base,points,order):
    base=_point(base);points=[_point(p) for p in points];mono=_monomials(order)
    if len(points)!=len(mono):raise ValueError(f'order {order} needs exactly {len(mono)} design points')
    inverse=_invert(design_rows(base,points,order))
    if inverse is None:raise ValueError('design is not unisolvent for this order')
    return mono,inverse


def width_factors(base,points,order):
    """Row sums of |D^-1| per multi-index: the exact factor from reading widths to coefficient widths."""
    mono,inverse=design_inverse(base,points,order)
    return {key:sum(abs(x) for x in row) for key,row in zip(mono,inverse)}


def first_layer_width_factor(base,points,order=1):
    f=width_factors(base,points,order);return f[(1,0)]+f[(0,1)]


@dataclass(frozen=True)
class JetEnclosure:
    """Interval Taylor coefficients of H(base+delta), one triple of Intervals per multi-index.

    When built by `fit_jet_enclosure` it also keeps the design points and the
    interval readings they came from, so that ranges can be taken over the
    admissible readings themselves (the exact admissible set) rather than over
    the product of coefficient intervals (a strictly larger box in general).
    """
    base: tuple
    coefficients: dict
    points: tuple=None
    readings: tuple=None

    def __post_init__(self):
        base=_point(self.base);coeffs={}
        for key,value in self.coefficients.items():coeffs[key]=_reading(value)
        order=max(i+j for (i,j) in coeffs)
        if set(_monomials(order))!=set(coeffs):raise ValueError('enclosure must carry every multi-index up to its order')
        object.__setattr__(self,'base',base);object.__setattr__(self,'coefficients',coeffs)
        if (self.points is None)!=(self.readings is None):raise ValueError('design points and readings come together')
        if self.points is not None:
            points=tuple(_point(p) for p in self.points);readings=tuple(_reading(h) for h in self.readings)
            if len(points)!=len(readings) or len(points)!=len(coeffs):raise ValueError('one reading per design point, one point per coefficient')
            object.__setattr__(self,'points',points);object.__setattr__(self,'readings',readings)

    @property
    def order(self):return max(i+j for (i,j) in self.coefficients)

    def contains(self,jet):
        """Does this enclosure contain an exact Jet (same base and order)?"""
        return jet.base==self.base and jet.order==self.order and all(
            jet.coefficients[k][e] in self.coefficients[k][e] for k in self.coefficients for e in range(3))

    def value(self,point):
        s,v=_point(point);ds,dv=s-self.base[0],v-self.base[1];out=[]
        for e in range(3):
            total=Interval.point(0)
            for (i,j),c in self.coefficients.items():total=total+c[e]*(ds**i*dv**j)
            out.append(total)
        return tuple(out)

    def widths(self):return {k:tuple(c.width for c in v) for k,v in self.coefficients.items()}

    def record(self):
        out=dict(base=[str(x) for x in self.base],order=self.order,
                 coefficients={f'{i},{j}':[c.record() for c in v] for (i,j),v in sorted(self.coefficients.items())})
        if self.points is not None:out['design']=[[str(x) for x in p] for p in self.points]
        return out


def fit_jet_enclosure(base,readings,order):
    """Exact interval coefficients from (point, (I11,I12,I22)) readings on a unisolvent design.

    c_alpha = sum_q (D^-1)_{alpha q} I_q as an interval linear combination.
    Theorem E1: this is the exact range of c_alpha over all admissible
    readings, with width sum_q |(D^-1)_{alpha q}| width(I_q).
    """
    base=_point(base);_integer(order,'jet order',0,MAX_DEGREE)
    readings=[(_point(p),_reading(h)) for p,h in readings]
    if len({p for p,_ in readings})!=len(readings):raise ValueError('readings must be at distinct points')
    mono,inverse=design_inverse(base,[p for p,_ in readings],order)
    out={}
    for key,row in zip(mono,inverse):
        triple=[]
        for e in range(3):
            total=Interval.point(0)
            for coefficient,(_,h) in zip(row,readings):
                if coefficient:total=total+h[e]*coefficient
            triple.append(total)
        out[key]=tuple(triple)
    return JetEnclosure(base,out,tuple(p for p,_ in readings),tuple(h for _,h in readings))


def check_enclosure(enclosure,readings):
    """Readings whose interval does not intersect the predicted interval: a falsification of the order."""
    out=[]
    for p,h in readings:
        p=_point(p);h=_reading(h);predicted=enclosure.value(p)
        if any(not predicted[e].intersects(h[e]) for e in range(3)):
            out.append(dict(point=[str(x) for x in p],reading=[x.record() for x in h],predicted=[x.record() for x in predicted]))
    return out


# Curvature from an enclosure --------------------------------------------------

def curvature_numerator(h,hs,hv):
    """N = (H_s adj(H) H_v - H_v adj(H) H_s)_12 with adj(H) = det(H) H^-1; kappa = -N / (4 det(H)^2).

    Multilinear in the nine entries (each term has one factor from each of
    H, H_s, H_v). Works for exact rationals and for Intervals alike.
    """
    a,b,c=h;adj=((c,-b),(-b,a));S=((hs[0],hs[1]),(hs[1],hs[2]));V=((hv[0],hv[1]),(hv[1],hv[2]))
    def mul(x,y):return tuple(tuple(x[i][0]*y[0][j]+x[i][1]*y[1][j] for j in range(2)) for i in range(2))
    SAV=mul(mul(S,adj),V);VAS=mul(mul(V,adj),S)
    return SAV[0][1]-VAS[0][1]


def numerator_determinant(h,hs,hv):
    """The same N as a 3 x 3 determinant: N = det[[a,b,c],[p1,p2,p3],[r1,r2,r3]] = (a,b,c).(p x r).

    Rows are the packed entries of H, H_s, H_v. Expanding `curvature_numerator`
    gives c(p1 r2 - p2 r1) - b(p1 r3 - p3 r1) + a(p2 r3 - p3 r2), the cofactor
    expansion of this determinant along its first row (Proposition E3(a)).
    Each entry sits in exactly one row, so N is affine in every entry.
    """
    (a,b,c),(p1,p2,p3),(r1,r2,r3)=h,hs,hv
    return a*(p2*r3-p3*r2)+b*(p3*r1-p1*r3)+c*(p1*r2-p2*r1)


def design_spreads(points):
    """(max s - min s, max v - min v) over the design points."""
    points=[_point(p) for p in points]
    return max(p[0] for p in points)-min(p[0] for p in points),max(p[1] for p in points)-min(p[1] for p in points)


def curvature_from_entries(h,hs,hv):
    a,b,c=h;det=a*c-b*b
    if a<=0 or det<=0:raise ValueError('positive Hessian required')
    return -curvature_numerator(h,hs,hv)/(4*det*det)


def cubic_form_numerator(h,T):
    """kappa = [G(b1^2 - b0 b2) + E(b2^2 - b1 b3) + F(b0 b3 - b1 b2)] / (4 det^2) with (E,F,G)=H and T=(U_sss,U_ssv,U_svv,U_vvv).

    This is the same kappa written through the integrability identities
    (H_s)_12 = (H_v)_11 = U_ssv and (H_s)_22 = (H_v)_12 = U_svv; the
    numerator here is quadratic in T, so interval arithmetic gives a valid,
    not exact, range. Works for rationals and Intervals alike.
    """
    E,F,G=h;b0,b1,b2,b3=T
    return G*(b1*b1-b0*b2)+E*(b2*b2-b1*b3)+F*(b0*b3-b1*b2)


class InconsistentEnclosure(ValueError):
    """The two jet intervals estimating one third derivative are disjoint.

    No order-one Hessian jet fits the readings: the integrability identities
    (H_s)_12 = (H_v)_11, (H_s)_22 = (H_v)_12 fail on the whole box. This
    falsifies the order hypothesis; it is not a positivity failure.
    """


def _intersect(x,y):
    lo,hi=max(x.lo,y.lo),min(x.hi,y.hi)
    if lo>hi:raise InconsistentEnclosure('enclosures are inconsistent: no admissible value remains')
    return Interval(lo,hi)


def integrability_defects(enclosure):
    """Pairs of jet intervals that should share a value but are disjoint (empty list = consistent)."""
    if type(enclosure) is not JetEnclosure or enclosure.order<1:raise ValueError('order>=1 jet enclosure required')
    S=enclosure.coefficients[(1,0)];V=enclosure.coefficients[(0,1)];out=[]
    for name,x,y in (('U_ssv',S[1],V[0]),('U_svv',S[2],V[1])):
        if not x.intersects(y):out.append(dict(derivative=name,from_H_s=x.record(),from_H_v=y.record()))
    return out


MAX_READING_CORNER_BITS=12   # the reading-corner range enumerates 2^(3m) corners; m = 3 (order one) gives 512


def _first_layer_rows(enclosure):
    """Rows (0,0), (1,0), (0,1) of D^-1 for the enclosure's design (None without a design)."""
    if enclosure.points is None:return None
    mono,inverse=design_inverse(enclosure.base,enclosure.points,enclosure.order)
    return [inverse[mono.index(key)] for key in ((0,0),(1,0),(0,1))]


def reading_corner_range(enclosure):
    """Exact range of N over all admissible readings (the admissible set itself, not the coefficient box).

    N = det(E Hmat) with E the three first-layer rows of D^-1 and Hmat the
    m x 3 matrix of readings, so N is affine in every single reading
    (Proposition E3(a)); a multi-affine function on a box takes its extremes
    at vertices, so the hull of the 2^(3m) reading corners is the exact range.
    Every value in it is attained by an admissible interpolant. Returns None
    when the enclosure carries no design or 3m exceeds MAX_READING_CORNER_BITS.
    """
    rows=_first_layer_rows(enclosure)
    if rows is None or 3*len(enclosure.points)>MAX_READING_CORNER_BITS:return None
    m=len(enclosure.points);values=[]
    for pick in product((0,1),repeat=3*m):
        h=[[(enclosure.readings[q][e].lo,enclosure.readings[q][e].hi)[pick[3*q+e]] for e in range(3)] for q in range(m)]
        C=[[sum(row[q]*h[q][e] for q in range(m)) for e in range(3)] for row in rows]
        values.append(numerator_determinant(*C))
    return Interval(min(values),max(values))


def numerator_ranges(enclosure):
    """Three valid ranges of N, nested natural >= coefficient_corners >= reading_corners (the last exact, or None).

    natural: interval arithmetic on the closed form over the nine coefficient
    intervals. coefficient_corners: hull of N at the 2^9 corners of the nine
    intervals, the exact range over the coefficient box; coefficients of one
    entry share readings, so the box is larger than the admissible set and
    this range can contain values no admissible reading produces.
    reading_corners: the exact range over the admissible readings.
    """
    if type(enclosure) is not JetEnclosure or enclosure.order<1:raise ValueError('order>=1 jet enclosure required')
    A,B,C=enclosure.coefficients[(0,0)];S=enclosure.coefficients[(1,0)];V=enclosure.coefficients[(0,1)]
    values=[]
    for pick in product((0,1),repeat=9):
        entries=[(x.lo,x.hi)[k] for x,k in zip((A,B,C,*S,*V),pick)]
        values.append(numerator_determinant(entries[:3],entries[3:6],entries[6:9]))
    return dict(natural=curvature_numerator((A,B,C),S,V),coefficient_corners=Interval(min(values),max(values)),
                reading_corners=reading_corner_range(enclosure))


def curvature_enclosure(enclosure,*,corners=True,intersect=True,readings=True):
    """Valid enclosure of kappa at the base from an order>=1 JetEnclosure.

    Positivity of H is certified on the whole box first (a>0 and ac-b^2>0
    for every admissible H), else ValueError. Two valid enclosures are
    intersected: (i) -[N]/(4 [det]^2) with [N] a range of the numerator N
    (Proposition E3): the exact range over the admissible readings when the
    enclosure carries its design and readings=True (2^(3m) reading corners),
    otherwise the hull over the 2^9 coefficient corners (corners=True) or the
    natural interval extension (corners=False); and (ii) the cubic-form
    expression in the four third derivatives, each taken as the intersection
    of the two jet intervals that estimate it (integrability), evaluated by
    interval arithmetic. Both contain kappa of every admissible Hessian field
    of the family (an integrable jet in the box); so does their intersection;
    (i) alone also contains the curvature of every admissible interpolant,
    even a non-integrable one. The result may be loose because numerator and
    denominator share a, b, c; within route (i) the sign decision depends on
    [N] alone, and route (ii) can exclude zero where (i) does not (asymmetric
    designs; the audit records how often). intersect=False returns (i) alone.

    Scope: "admissible" means a Hessian field of the declared family whose
    exact order-one jet is the fitted interpolant (for the order-one fit, a
    Hessian field of total degree at most one). Outside that hypothesis the
    fitted box need not contain the true jet (part 1, Theorem J3), and no
    enclosure built from it says anything about the true curvature.
    """
    if type(enclosure) is not JetEnclosure or enclosure.order<1:raise ValueError('order>=1 jet enclosure required')
    A,B,C=enclosure.coefficients[(0,0)];S=enclosure.coefficients[(1,0)];V=enclosure.coefficients[(0,1)]
    if A.lo<=0:raise ValueError('positivity of H11 not certified by the enclosure')
    b2=B.square()
    if C.lo<=0 or A.lo*C.lo-b2.hi<=0:raise ValueError('positivity of det H not certified by the enclosure')
    det=Interval(A.lo*C.lo-b2.hi,A.hi*C.hi-b2.lo)
    scale=(det*det).reciprocal()*Q(-1,4)
    N=reading_corner_range(enclosure) if readings else None
    if N is None:
        if corners:
            values=[]
            for pick in product((0,1),repeat=9):
                entries=[(x.lo,x.hi)[k] for x,k in zip((A,B,C,*S,*V),pick)]
                values.append(numerator_determinant(entries[:3],entries[3:6],entries[6:9]))
            N=Interval(min(values),max(values))
        else:
            N=curvature_numerator((A,B,C),S,V)
    nine=N*scale
    if not intersect:return nine
    T=(S[0],_intersect(S[1],V[0]),_intersect(S[2],V[1]),V[2])
    four=cubic_form_numerator((A,B,C),T)*((det*det).reciprocal()*Q(1,4))
    return _intersect(nine,four)


def certify_sign(enclosure):
    """(+1|-1|None, kappa interval): the sign is certified iff zero is excluded."""
    k=curvature_enclosure(enclosure);return k.sign(),k


# Readers and the learner ---------------------------------------------------------

class EnclosureReader:
    """Readings of a declared energy, widened to declared half-widths that contain the truth.

    half_width may be a rational (same for every entry and point) or a
    callable point -> (w11,w12,w22). The true value is centred; this is the
    declared enclosure model of this packet, not a claim about any device.
    """
    def __init__(self,energy,half_width,*,max_readings=256):
        if type(energy) is not PolynomialEnergy:raise TypeError('declared polynomial energy required')
        self.energy=energy;self.max_readings=_integer(max_readings,'reading budget',1,MAX_READINGS)
        self.half_width=half_width if callable(half_width) else (lambda point,w=_q(half_width,'half width'):(w,w,w))
        self.record={};self.requests=0

    def read(self,point):
        point=_point(point);self.requests+=1
        if point in self.record:return self.record[point]
        if len(self.record)>=self.max_readings:raise ResourceLimit('reading budget exhausted; no enclosure returned')
        truth=self.energy.hessian(point);widths=self.half_width(point)
        value=tuple(Interval.around(t,w) for t,w in zip(truth,widths));self.record[point]=value
        return value

    @property
    def readings(self):return len(self.record)


def choose_design(base,candidates,order,*,objective=first_layer_width_factor,sweeps=4):
    """Unisolvent design from greedy maximal volume, then exact single-point swaps that lower the objective.

    Returns (design, objective value, converged). The swap descent is exact;
    when `converged` is True it stopped because no single swap lowers the
    objective (a local minimum over swaps), otherwise because the `sweeps`
    cap was reached. Neither is a global optimum claim. (Proposition E2: on
    an axis-aligned candidate box of half-side R the first-layer factor of
    any design of any order is at least 2/R, and a three-point corner design
    attains it; the greedy maximal-volume start is first-layer optimal there
    only because, for three points in such a box, maximal |det D| and minimal
    first-layer row sums coincide; in general a larger |det D| does not give a
    smaller width.)
    """
    base=_point(base);candidates=[_point(p) for p in candidates];need=len(_monomials(order));design=[]
    while len(design)<need:
        point,gain=next_point(base,design,candidates,order)
        if point is None:raise ValueError('candidate set cannot complete a unisolvent design')
        design.append(point)
    best=objective(base,design,order);converged=False
    for _ in range(_integer(sweeps,'sweeps',0,16)):
        improved=False
        for slot in range(need):
            for candidate in candidates:
                if candidate in design:continue
                trial=design[:slot]+[candidate]+design[slot+1:]
                try:value=objective(base,trial,order)
                except ValueError:continue
                if value<best:best,design,improved=value,trial,True
        if not improved:converged=True;break
    return design,best,converged


def learn_jet_enclosure(reader,base,*,order=1,checks=3,candidates=None,sweeps=4):
    """Readings with declared widths -> jet enclosure, curvature enclosure and a sign certificate.

    The design is chosen to lower the first-layer width factor (exact swaps);
    check readings must intersect the predicted intervals, otherwise the order
    is falsified. The result's certificate is 'sign_certified' only when the
    curvature enclosure excludes zero; otherwise it names what would help:
    narrower readings or a smaller width factor. A higher jet order does not
    help: kappa at the base depends on the order-one coefficients only, and
    any interpolation functional for a first-layer coefficient that is exact
    on affine fields has width factor at least 1/max|ds| (resp. 1/max|dv|)
    over the candidate set, which the order-one corner design attains; a
    higher-order fit on the same candidates can only tie or lose
    (Proposition E2).
    """
    if type(reader) is not EnclosureReader:raise TypeError('EnclosureReader required')
    base=_point(base);_integer(order,'jet order',1,MAX_DEGREE);_integer(checks,'check readings',0,16)
    candidates=[_point(p) for p in candidates] if candidates is not None else default_candidates(base)
    design,factor,converged=choose_design(base,candidates,order,sweeps=sweeps)
    half_s=max(abs(p[0]-base[0]) for p in candidates);half_v=max(abs(p[1]-base[1]) for p in candidates)
    bound=(1/half_s if half_s else None,1/half_v if half_v else None)        # Proposition E2: first-layer factor >= 1/max|ds| + 1/max|dv|
    floor=None if None in bound else bound[0]+bound[1]
    enclosure=fit_jet_enclosure(base,[(p,reader.read(p)) for p in design],order)
    extra=[]
    while len(extra)<checks:
        point,gain=next_point(base,design+extra,candidates,order+1 if order<MAX_DEGREE else order)
        if point is None:
            leftover=[p for p in candidates if p not in design and p not in extra]
            if not leftover:break
            point=leftover[0]
        extra.append(point)
    falsified=check_enclosure(enclosure,[(p,reader.read(p)) for p in extra])
    for defect in integrability_defects(enclosure):falsified.append(dict(integrability=defect))
    try:sign,kappa=certify_sign(enclosure);positivity=True
    except InconsistentEnclosure:sign,kappa,positivity=None,None,True
    except ValueError:sign,kappa,positivity=None,None,False
    status=('order_falsified' if falsified else 'sign_certified' if sign is not None else
            'positivity_not_certified' if not positivity else 'sign_not_certified')
    if status=='order_falsified':sign,kappa=None,None     # nothing read from a falsified model is reported as a result
    remedy={'sign_certified':None,
            'order_falsified':'the order hypothesis is falsified by the readings; fit a higher order (or a different family)',
            'sign_not_certified':f'narrower readings, or a wider candidate set: over the supplied candidates no design of any order has a first-layer width factor below 1/max|ds| + 1/max|dv| = {floor} (Proposition E2), and this design has {factor}',
            'positivity_not_certified':f'narrower readings, or a wider candidate set (first-layer factor floor {floor} over the supplied candidates, this design {factor}); the Hessian box must certify a>0 and ac-b^2>0'}[status]
    return dict(status=status,design=[[str(x) for x in p] for p in design],first_layer_width_factor=str(factor),design_converged=converged,
                candidates=len(candidates),candidate_half_sides=[str(half_s),str(half_v)],first_layer_factor_floor=None if floor is None else str(floor),
                enclosure=enclosure,curvature=kappa,sign=sign,falsifications=falsified,readings=reader.readings,
                requests=reader.requests,remedy=remedy,
                hypothesis='the Hessian field is a polynomial of total degree <= order (declared family); the certificate is conditional on it and is falsified, never certified, by check readings (part 1, Theorem J3)',
                certificate='worst-case enclosure arithmetic within the declared family; the declared widths are inputs, not measured noise')


def tolerance_bracket(energy_cases,base,design,*,order=1,lo=Q(0),hi=Q(1),steps=24):
    """Largest common half-width certifying every case's curvature sign, bracketed by exact bisection.

    Returns (w_ok, w_fail): every case is certified at w_ok, at least one is
    not at w_fail; the true threshold lies in between. steps bisections.
    """
    base=_point(base);design=[_point(p) for p in design];lo,hi=_q(lo),_q(hi)
    def certified(w):
        for energy in energy_cases:
            reader=EnclosureReader(energy,w)
            enclosure=fit_jet_enclosure(base,[(p,reader.read(p)) for p in design],order)
            try:sign,_=certify_sign(enclosure)
            except ValueError:return False
            if sign is None or sign!=(1 if energy.curvature(base)>0 else -1):return False
        return True
    if not certified(lo):raise ValueError('the lower bracket is not certified')
    if certified(hi):return hi,None
    for _ in range(_integer(steps,'bisection steps',1,64)):
        mid=(lo+hi)/2
        if certified(mid):lo=mid
        else:hi=mid
    return lo,hi


# Exact certification threshold --------------------------------------------------
# Univariate polynomials in the half-width w: coefficient lists, low degree first, exact rationals.

def _pstrip(p):
    p=list(p)
    while p and p[-1]==0:p.pop()
    return p


def _padd(p,r,scale=Q(1)):
    out=[Q(0)]*max(len(p),len(r))
    for i,x in enumerate(p):out[i]+=x
    for i,x in enumerate(r):out[i]+=scale*x
    return _pstrip(out)


def _pmul(p,r):
    out=[Q(0)]*(len(p)+len(r)-1) if p and r else []
    for i,x in enumerate(p):
        for j,y in enumerate(r):out[i+j]+=x*y
    return _pstrip(out)


def _peval(p,x):
    total=Q(0)
    for c in reversed(p):total=total*x+c
    return total


def _pderiv(p):return _pstrip([i*c for i,c in enumerate(p)][1:])


def _prem(p,r):
    p=_pstrip(p);r=_pstrip(r)
    while p and len(p)>=len(r):
        k=p[-1]/r[-1];shift=len(p)-len(r)
        p=_pstrip([x-(k*r[i-shift] if i>=shift else 0) for i,x in enumerate(p)])
    return p


def sturm_sequence(p):
    seq=[_pstrip(p),_pderiv(p)]
    while seq[-1]:
        nxt=[-x for x in _prem(seq[-2],seq[-1])];seq.append(nxt)
    return seq[:-1]


def _variations(seq,x):
    signs=[s for s in ((v>0)-(v<0) for v in (_peval(q,x) for q in seq)) if s]
    return sum(1 for a,b in zip(signs,signs[1:]) if a!=b)


def count_roots(seq,a,b):
    """Number of distinct real roots of the polynomial of the Sturm sequence in (a, b], for p(a) != 0 (Sturm's theorem)."""
    if _peval(seq[0],a)==0:raise ValueError('left end must not be a root')
    return _variations(seq,a)-_variations(seq,b)


def smallest_positive_root(p,*,bits=60,denominator_bound=1<<20):
    """(root or None, (lo, hi)) for a nonzero polynomial with p(0) != 0: the least positive root, exactly when it is
    rational with denominator <= denominator_bound (found from the convergents of the isolating interval), else the
    isolating interval (lo, hi] of width <= 2^-bits with root=None. (None, None) when there is no positive root."""
    p=_pstrip(p)
    if not p or _peval(p,Q(0))==0:raise ValueError('nonzero polynomial with p(0) != 0 required')
    if len(p)==1:return None,None
    seq=sturm_sequence(p);bound=1+max(abs(c/p[-1]) for c in p[:-1])
    if count_roots(seq,Q(0),bound)==0:return None,None
    lo,hi=Q(0),bound
    while hi-lo>Q(1,1<<bits):
        mid=(lo+hi)/2
        if count_roots(seq,lo,mid)>=1:hi=mid
        else:lo=mid
    if _peval(p,hi)==0:return hi,(lo,hi)
    x=(lo+hi)/2;h0,h1,k0,k1=0,1,1,0          # convergents of the midpoint's continued fraction
    while k1<=denominator_bound:
        a=x.numerator//x.denominator;h0,h1=h1,a*h1+h0;k0,k1=k1,a*k1+k0
        candidate=Q(h1,k1)
        if lo<candidate<=hi and _peval(p,candidate)==0:return candidate,(lo,hi)
        frac=x-a
        if frac==0:break
        x=1/frac
    return None,(lo,hi)


def certification_threshold(energy_cases,base,design,*,bits=60,denominator_bound=1<<20):
    """Exact supremum of the uniform half-width w at which route (i) certifies every case's curvature sign.

    Model: every reading at every design point carries the same half-width w
    around the truth; the design is a three-point order-one design; route (i)
    is the exact reading-corner range of N (Proposition E3). The certified set
    of w is downward closed (every enclosure is inclusion-isotone in w), so
    it is [0, sup) or [0, sup]. Route (i) certifies at w iff the positivity
    gate holds and no reading corner has N = 0: at w = 0 every corner equals
    the true N = -4 det(H)^2 kappa != 0, each corner's N is a polynomial of
    degree <= 3 in w, so the sup is the least positive root over the 2^9 sign
    patterns of all cases, or the gate's first failure if that comes first.
    The witness at the sup is the admissible interpolant of the first corner
    to vanish; when it satisfies the integrability identities it is the
    order-one Hessian jet of an energy of the declared family with kappa = 0,
    and then no sound certifier of any kind can certify at w >= sup
    (Theorem E4). Returns a dict with sup (exact rational or None), bracket
    (lo, hi] when the root is irrational, the gate root, and the witness.
    """
    base=_point(base);design=[_point(p) for p in design]
    if len(design)!=3:raise ValueError('three-point order-one design required')
    mono,inverse=design_inverse(base,design,1);E=[inverse[mono.index(key)] for key in ((0,0),(1,0),(0,1))]
    rho=sum(abs(x) for x in E[0])
    best=None;bracket=None;witness=None;gate=None
    for index,energy in enumerate(energy_cases):
        if type(energy) is not PolynomialEnergy:raise TypeError('declared polynomial energies required')
        H0=[energy.hessian(p) for p in design]
        C0=[[sum(row[q]*H0[q][e] for q in range(3)) for e in range(3)] for row in E]
        a0,b0,c0=C0[0];N0=numerator_determinant(*C0)
        if a0<=0 or a0*c0-b0*b0<=0:raise ValueError('positive Hessian required at the base')
        if N0==0:return dict(sup=Q(0),exact=True,bracket=None,gate_root=None,witness=dict(case=index,note='kappa = 0 already at zero width'))
        # positivity gate: a0 - rho w > 0 and (a0 - rho w)(c0 - rho w) - (|b0| + rho w)^2 > 0
        delta=_padd(_pmul([a0,-rho],[c0,-rho]),_pmul([abs(b0),rho],[abs(b0),rho]),Q(-1))
        for poly in ([a0,-rho],delta):
            root,_=smallest_positive_root(poly,bits=bits,denominator_bound=denominator_bound)
            if root is not None and (gate is None or root<gate):gate=root
        for pattern in product((-1,1),repeat=9):
            # entries of C(w) = E (H0 + w S) are linear in w; N(w) = det C(w)
            C=[[[C0[r][e],sum(E[r][q]*pattern[3*q+e] for q in range(3))] for e in range(3)] for r in range(3)]
            (a,b,c),(p1,p2,p3),(r1,r2,r3)=C
            N=_padd(_padd(_pmul(a,_padd(_pmul(p2,r3),_pmul(p3,r2),Q(-1))),_pmul(b,_padd(_pmul(p3,r1),_pmul(p1,r3),Q(-1)))),
                    _pmul(c,_padd(_pmul(p1,r2),_pmul(p2,r1),Q(-1))))
            limit=best if bracket is None else bracket[1]
            if limit is not None and count_roots(sturm_sequence(N),Q(0),limit)==0:continue
            root,iso=smallest_positive_root(N,bits=bits,denominator_bound=denominator_bound)
            if iso is None:continue
            value=root if root is not None else iso[1]
            if limit is None or value<limit or (root is not None and value==limit):
                best,bracket=root,(None if root is not None else iso)
                readings=[tuple(H0[q][e]+(root if root is not None else iso[1])*pattern[3*q+e] for e in range(3)) for q in range(3)]
                witness=dict(case=index,pattern=pattern,readings=readings)
    sup=best if bracket is None else None
    if gate is not None and (sup is None or gate<=sup):
        sup,bracket,witness=gate,None,dict(note='positivity gate fails first')
    if witness is not None and 'readings' in witness and sup is not None:
        from .jet_readings import fit_jet
        jet=fit_jet(base,list(zip(design,witness['readings'])),1);S,V=jet.first_layer()
        integrable=S[1]==V[0] and S[2]==V[1]
        witness.update(half_width=sup,jet=jet,integrable=integrable,kappa=jet.curvature() if jet.hessian()[0]>0 else None)
    return dict(sup=sup,exact=sup is not None,bracket=None if bracket is None else (bracket[0],bracket[1]),gate_root=gate,witness=witness,
                model='uniform half-width on every entry at every design point; route (i) with the exact reading-corner range')
