"""Exact Q(zeta_64)=Q(zeta_32)[u]/(u²-zeta_32), u=exp(i*pi/32).

The original sixteen-coefficient field embeds as the constant component. This is
standard cyclotomic arithmetic, not a prime-spectrum or speedup theorem.
"""
from dataclasses import dataclass
from fractions import Fraction
from math import cos,sin,pi,isqrt

from .cyclotomic32 import Cyclotomic32 as Exact,ZERO as E0,ONE as E1,ZETA as OMEGA,BASIS as BASE_BASIS
from .exact import IMAG
from .compact import ResourceLimit,_integer

BASIS='Q(zeta_64): (1,u) times ['+BASE_BASIS+']; u=exp(i*pi/32), u^2=w'


@dataclass(frozen=True,slots=True)
class Cyclotomic64:
    lo: Exact=E0
    hi: Exact=E0

    def __post_init__(self):
        object.__setattr__(self,'lo',Exact.coerce(self.lo))
        object.__setattr__(self,'hi',Exact.coerce(self.hi))

    @staticmethod
    def coerce(value):return value if isinstance(value,Cyclotomic64) else Cyclotomic64(value)

    @property
    def coefficients(self):return self.lo.coefficients+self.hi.coefficients

    @property
    def max_bits(self):return max(self.lo.max_bits,self.hi.max_bits)

    def __bool__(self):return bool(self.lo or self.hi)

    def __add__(self,other):
        other=self.coerce(other)
        return Cyclotomic64(self.lo+other.lo,self.hi+other.hi)
    __radd__=__add__

    def __neg__(self):return Cyclotomic64(-self.lo,-self.hi)
    def __sub__(self,other):return self+-self.coerce(other)
    def __rsub__(self,other):return self.coerce(other)+-self

    def __mul__(self,other):
        other=self.coerce(other)
        if not self or not other:return ZERO
        if not self.hi and not other.hi:return Cyclotomic64(self.lo*other.lo)
        return Cyclotomic64(self.lo*other.lo+self.hi*other.hi*OMEGA,
                          self.lo*other.hi+self.hi*other.lo)
    __rmul__=__mul__

    def conjugate(self):return Cyclotomic64(self.lo.conjugate(),self.hi.conjugate()*OMEGA.conjugate())
    def norm2(self):return self*self.conjugate()

    def inverse(self):
        if not self:raise ZeroDivisionError('zero cyclotomic value has no inverse')
        denominator=self.lo*self.lo-self.hi*self.hi*OMEGA
        return Cyclotomic64(self.lo/denominator,-self.hi/denominator)

    def __truediv__(self,other):return self*self.coerce(other).inverse()
    def __rtruediv__(self,other):return self.coerce(other)*self.inverse()

    def __pow__(self,n):
        if isinstance(n,bool) or not isinstance(n,int):raise TypeError('integer exponent required')
        base=self if n>=0 else self.inverse();n=abs(n);out=ONE
        while n:
            if n&1:out=out*base
            base=base*base;n>>=1
        return out

    def __complex__(self):return complex(self.lo)+complex(self.hi)*complex(cos(pi/32),sin(pi/32))

    def to_dict(self):return dict(basis=BASIS,coefficients=[str(v) for v in self.coefficients])

    @staticmethod
    def from_dict(value):
        if not isinstance(value,dict) or set(value)!={'basis','coefficients'}:
            raise ValueError('invalid exact coefficient object')
        coefficients=value['coefficients']
        if not isinstance(coefficients,list) or any(not isinstance(v,str) for v in coefficients):
            raise ValueError('exact coefficients must be rational strings')
        if value['basis']!=BASIS:return Cyclotomic64(Exact.from_dict(value))
        if len(coefficients)!=32:raise ValueError('wrong coefficient count for zeta_64')
        return Cyclotomic64(Exact.from_dict(dict(basis=BASE_BASIS,coefficients=coefficients[:16])),
                            Exact.from_dict(dict(basis=BASE_BASIS,coefficients=coefficients[16:])))

    def real_bounds(self,precision=20):
        """Rational outward enclosure via nested integer-square-root bounds."""
        _integer(precision,'enclosure precision',1,200_000)
        if self!=self.conjugate():raise ValueError('a real cyclotomic value is required')
        if not self.hi:return self.lo.real_bounds(precision)
        scale=10**precision
        def sqrt_bounds(x):
            low=isqrt((x.numerator*scale*scale)//x.denominator)
            lower=Fraction(low,scale)
            return lower,lower if lower*lower==x else Fraction(low+1,scale)
        def mul(x,y):
            products=[a*b for a in x for b in y]
            return min(products),max(products)
        def add(x,y):return x[0]+y[0],x[1]+y[1]
        def real_part(v):return (v+v.conjugate())*Fraction(1,2)
        def imag_part(v):return (v-v.conjugate())*Exact(-IMAG)*Fraction(1,2)
        cosine32=real_part(OMEGA).real_bounds(precision)
        cosine=(sqrt_bounds((1+cosine32[0])/2)[0],sqrt_bounds((1+cosine32[1])/2)[1])
        sine=(sqrt_bounds((1-cosine32[1])/2)[0],sqrt_bounds((1-cosine32[0])/2)[1])
        return add(real_part(self.lo).real_bounds(precision),
                   add(mul(real_part(self.hi).real_bounds(precision),cosine),
                       mul((-imag_part(self.hi)).real_bounds(precision),sine)))

    def real_sign(self):
        if self!=self.conjugate():raise ValueError('a real cyclotomic value is required')
        if not self:return 0
        precision=8;cap=min(200_000,16*(self.max_bits+1)+64)
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
        # Bound coefficient magnitudes, then refine if interval cancellation needs it.
        bits=max(max(0,abs(v.numerator).bit_length()-v.denominator.bit_length()+1) for v in self.coefficients)
        precision=places+(bits*30103+99999)//100000+8
        while True:
            lower,upper=self.real_bounds(precision)
            if upper-lower<=Fraction(1,100*scale):break
            if precision>=200_000:raise ResourceLimit('cyclotomic display enclosure budget exceeded')
            precision=min(200_000,precision*2)
        low=(lower*scale).__floor__();high=(upper*scale).__ceil__()
        return dict(exact=self.to_dict(),expression='rational coefficients in the declared zeta_64 basis',
            decimal=_fixed((low+high)*5,places+1),decimal_enclosure=dict(
                lower=_fixed(low,places),upper=_fixed(high,places),
                maximum_absolute_display_error=str(Fraction(high-low,2*scale)),
                method='nested integer-square-root bounds and outward rational rounding'))


ZERO,ONE,ZETA=Cyclotomic64(),Cyclotomic64(1),Cyclotomic64(E0,E1)
