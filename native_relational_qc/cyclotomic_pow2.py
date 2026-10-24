"""Exact Q(zeta_M), M=2**k (8<=M<=4096), in the flat power basis.

An element is (1/den) * sum_e c_e zeta**e with integer c_e, 0<=e<M/2, and
zeta=exp(2*pi*i/M). Reduction uses the cyclotomic relation zeta**(M/2)=-1,
so the power basis is a Q-basis and the stored form is canonical. Only
nonzero coefficients are stored. Q(zeta_16/32/64) of the nested backends are
the subfields M=16/32/64; this module is an independent flat representation,
not a speedup or prime-spectrum theorem.
"""
from fractions import Fraction
from functools import lru_cache
from math import cos,sin,pi,gcd

from .compact import ResourceLimit,_integer

MIN_ORDER,MAX_ORDER=8,4096


def _basis(order):
    return f'Q(zeta_{order}) power basis zeta^0..zeta^{order//2-1}; zeta=exp(2*pi*i/{order}), zeta^{order//2}=-1'


class CyclotomicPow2:
    """Base class; use field_of_order(M) for a concrete field."""
    __slots__=('terms','den')
    ORDER=None

    def __init__(self,value=0):
        if isinstance(value,CyclotomicPow2):
            if value.ORDER!=self.ORDER:raise ValueError('cyclotomic orders differ; no implicit embedding')
            self.terms,self.den=value.terms,value.den;return
        from .exact import Exact
        if isinstance(value,bool):raise TypeError('boolean is not an exact coefficient')
        if isinstance(value,(int,Fraction)):
            value=Fraction(value)
            self.terms=((0,value.numerator),) if value else ();self.den=value.denominator if value else 1;return
        if isinstance(value,Exact):
            a,b,c,d=value.coefficients;F=type(self)
            out=F(a)+F(b)*F.sqrt2()+F.imag()*(F(c)+F(d)*F.sqrt2())
            self.terms,self.den=out.terms,out.den;return
        raise TypeError('unsupported exact value for Q(zeta_M)')

    @classmethod
    def _make(cls,coefficients,den):
        out=object.__new__(cls)
        items=[(e,c) for e,c in coefficients.items() if c]
        if not items:out.terms,out.den=(),1;return out
        g=den
        for _,c in items:
            g=gcd(g,c)
            if g==1:break
        if den<0:g=-g
        out.terms=tuple(sorted((e,c//g) for e,c in items));out.den=den//g
        return out

    @classmethod
    def coerce(cls,value):return value if type(value) is cls else cls(value)

    @classmethod
    def root(cls,power=1):
        """zeta**power for any integer power."""
        M=cls.ORDER;n=M//2;e=power%M
        return cls._make({e-n:-1} if e>=n else {e:1},1)

    @classmethod
    def sqrt2(cls):return cls.root(cls.ORDER//8)+cls.root(-cls.ORDER//8)

    @classmethod
    def imag(cls):return cls.root(cls.ORDER//4)

    @property
    def coefficients(self):
        n=self.ORDER//2;out=[Fraction(0)]*n
        for e,c in self.terms:out[e]=Fraction(c,self.den)
        return tuple(out)

    @property
    def max_bits(self):
        return max([self.den.bit_length()]+[abs(c).bit_length() for _,c in self.terms])

    def __bool__(self):return bool(self.terms)
    def __eq__(self,other):
        try:other=self.coerce(other)
        except (TypeError,ValueError):return NotImplemented
        return self.terms==other.terms and self.den==other.den
    def __hash__(self):return hash((self.ORDER,self.terms,self.den))
    def __repr__(self):return f'{type(self).__name__}({dict(self.terms)}/{self.den})'

    def __add__(self,other):
        other=self.coerce(other)
        if not other.terms:return self
        if not self.terms:return other
        d1,d2=self.den,other.den;g=gcd(d1,d2);m1,m2=d2//g,d1//g
        out={e:c*m1 for e,c in self.terms}
        for e,c in other.terms:out[e]=out.get(e,0)+c*m2
        return self._make(out,d1*m1)
    __radd__=__add__

    def __neg__(self):
        out=object.__new__(type(self));out.terms=tuple((e,-c) for e,c in self.terms);out.den=self.den
        return out
    def __sub__(self,other):return self+-self.coerce(other)
    def __rsub__(self,other):return self.coerce(other)+-self

    def __mul__(self,other):
        other=self.coerce(other)
        if not self.terms or not other.terms:return type(self)()
        n=self.ORDER//2;out={}
        for e1,c1 in self.terms:
            for e2,c2 in other.terms:
                e=e1+e2;c=c1*c2
                if e>=n:e-=n;c=-c
                out[e]=out.get(e,0)+c
        return self._make(out,self.den*other.den)
    __rmul__=__mul__

    def __truediv__(self,other):
        """Division by a nonzero rational only; general inversion is not needed here."""
        if isinstance(other,bool) or not isinstance(other,(int,Fraction)):
            raise TypeError('only rational divisors are supported')
        other=Fraction(other)
        if not other:raise ZeroDivisionError('division by zero')
        return self._make({e:c*other.denominator for e,c in self.terms},self.den*other.numerator)

    def conjugate(self):
        n=self.ORDER//2;out={}
        for e,c in self.terms:
            if e:out[n-e]=-c          # zeta**-e = zeta**(M-e) = -zeta**(n-e)
            else:out[0]=c
        return self._make(out,self.den)
    def norm2(self):return self*self.conjugate()

    def __complex__(self):
        M=self.ORDER
        return sum((c*complex(cos(2*pi*e/M),sin(2*pi*e/M)) for e,c in self.terms),0j)/self.den

    def to_dict(self):
        return dict(basis=_basis(self.ORDER),sparse_coefficients=[[e,str(Fraction(c,self.den))] for e,c in self.terms])

    @classmethod
    def from_dict(cls,value):
        if not isinstance(value,dict) or set(value)!={'basis','sparse_coefficients'}:
            raise ValueError('invalid exact coefficient object')
        if value['basis']!=_basis(cls.ORDER):raise ValueError('basis does not match this cyclotomic order')
        rows=value['sparse_coefficients'];n=cls.ORDER//2;out=cls()
        if not isinstance(rows,list):raise ValueError('sparse coefficients must be a list')
        seen=set()
        for row in rows:
            if (not isinstance(row,list) or len(row)!=2 or type(row[0]) is not int or
                not isinstance(row[1],str) or not 0<=row[0]<n or row[0] in seen):
                raise ValueError('invalid sparse coefficient row')
            seen.add(row[0]);out=out+cls(Fraction(row[1]))*cls.root(row[0])
        return out

    # Certified real enclosures. cos(2*pi*e/M) is bounded from a rational pi
    # enclosure and alternating Taylor partial sums, rounded outward.
    def real_bounds(self,precision=20):
        _integer(precision,'enclosure precision',1,200_000)
        if self!=self.conjugate():raise ValueError('a real cyclotomic value is required')
        bits=(precision*33219+9999)//10000+16;low=high=Fraction(0)
        for e,c in self.terms:
            lo,hi=_cos_bounds(self.ORDER,e,bits)
            if c>0:low+=c*lo;high+=c*hi
            else:low+=c*hi;high+=c*lo
        return low/self.den,high/self.den

    def real_sign(self):
        if self!=self.conjugate():raise ValueError('a real cyclotomic value is required')
        if not self:return 0
        precision=8;cap=min(200_000,16*(self.max_bits+len(self.terms).bit_length()+1)+64)
        while True:
            low,high=self.real_bounds(precision)
            if low>0:return 1
            if high<0:return -1
            if precision>=cap:raise ResourceLimit('cyclotomic sign enclosure budget exceeded')
            precision=min(cap,precision*2)

    def display(self,decimal_places=12):
        from .calculator import _fixed
        places=_integer(decimal_places,'decimal_places',0,60)
        if self!=self.conjugate():raise ValueError('only real observations can be displayed')
        scale=10**places
        bits=max([0]+[max(0,abs(c).bit_length()-self.den.bit_length()+1) for _,c in self.terms])
        precision=places+((bits+len(self.terms).bit_length())*30103+99999)//100000+8
        while True:
            lower,upper=self.real_bounds(precision)
            if upper-lower<=Fraction(1,100*scale):break
            if precision>=200_000:raise ResourceLimit('cyclotomic display enclosure budget exceeded')
            precision=min(200_000,precision*2)
        low=(lower*scale).__floor__();high=(upper*scale).__ceil__()
        return dict(exact=self.to_dict(),expression=f'rational coefficients in the declared zeta_{self.ORDER} power basis',
            decimal=_fixed((low+high)*5,places+1),decimal_enclosure=dict(
                lower=_fixed(low,places),upper=_fixed(high,places),
                maximum_absolute_display_error=str(Fraction(high-low,2*scale)),
                method='Machin pi enclosure, alternating Taylor cosine bounds and outward rational rounding'))


@lru_cache(maxsize=None)
def field_of_order(order):
    """The concrete class for Q(zeta_order); order is a power of two, 8..4096."""
    _integer(order,'cyclotomic order',MIN_ORDER,MAX_ORDER)
    if order&(order-1):raise ValueError('cyclotomic order must be a power of two')
    return type(f'Cyclotomic{order}Flat',(CyclotomicPow2,),dict(__slots__=(),ORDER=order))


def _atan_inverse_bounds(k,bits):
    """Integers L<=2**bits*atan(1/k)<=U from bracketing alternating partial sums."""
    scale=1<<bits;terms=[];j=0
    while True:
        q=(2*j+1)*k**(2*j+1);floor=scale//q;terms.append(floor)
        if floor==0 and j%2==1:break
        j+=1
    low=sum(t if i%2==0 else -(t+1) for i,t in enumerate(terms))           # ends on a subtracted term
    high=sum(t+1 if i%2==0 else -t for i,t in enumerate(terms[:-1]))       # ends on an added term
    return low,high


@lru_cache(maxsize=64)
def _pi_bounds(bits):
    a5=_atan_inverse_bounds(5,bits+8);a239=_atan_inverse_bounds(239,bits+8)
    low=16*a5[0]-4*a239[1];high=16*a5[1]-4*a239[0]
    return Fraction(low,1<<(bits+8)),Fraction(high,1<<(bits+8))


def _cos_series_bounds(x,bits):
    """Bounds of cos(x) for rational 0<=x<=2 with denominator dividing 2**bits.

    For j>=1 the Taylor terms x**(2j)/(2j)! decrease, so consecutive partial
    sums with at least two terms bracket cos(x). Each term is bounded by
    integer floor/ceiling at scale 2**bits and summed outward.
    """
    if x==0:return Fraction(1),Fraction(1)
    if not 0<x<=2 or (x*(1<<bits)).denominator!=1:raise ValueError('cosine argument outside the certified range')
    N=int(x*(1<<bits));scale=1<<bits
    low=high=scale;sums=[(low,high)];j=0;power=1;factorial=1
    while True:
        j+=1;power*=N*N;factorial*=(2*j-1)*(2*j)
        floor=power//((1<<(bits*(2*j-1)))*factorial);ceil=floor+1
        if j%2:low,high=low-ceil,high-floor
        else:low,high=low+floor,high+ceil
        sums.append((low,high))
        if j>=2 and floor==0:break
    (l1,h1),(l2,h2)=sums[-1],sums[-2]
    return Fraction(min(l1,l2),scale),Fraction(max(h1,h2),scale)


@lru_cache(maxsize=None)
def _cos_bounds(order,e,bits):
    """Rational L<=cos(2*pi*e/order)<=U. Exponents are folded into [0,order/4]."""
    e%=order;sign=1
    if e>order//2:e=order-e                     # cos is even
    if e>order//4:e=order//2-e;sign=-1          # cos(pi-x)=-cos(x)
    if e==0:return (Fraction(sign),)*2
    if 4*e==order:return Fraction(0),Fraction(0)
    pl,ph=_pi_bounds(bits);den=1<<bits
    xl=Fraction((2*pl*e/order*den).__floor__(),den);xh=Fraction((2*ph*e/order*den).__ceil__(),den)
    low=_cos_series_bounds(xh,bits)[0];high=_cos_series_bounds(xl,bits)[1]   # decreasing on [0,pi/2]
    rl=Fraction((low*den).__floor__(),den);rh=Fraction((high*den).__ceil__(),den)
    return (rl,rh) if sign>0 else (-rh,-rl)
