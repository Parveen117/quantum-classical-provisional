"""Exact Q(zeta_16)=Q(sqrt(2),i)[z]/(z²-omega), z=exp(i*pi/8).

The original four-coefficient field embeds as the constant component. This is
standard cyclotomic arithmetic, not a prime-spectrum or speedup theorem.
"""
from dataclasses import dataclass
from fractions import Fraction
from math import cos,sin,pi,isqrt

from .exact import Exact,ZERO as E0,ONE as E1,OMEGA
from .compact import ResourceLimit,_integer

BASIS='1,sqrt(2),i,i*sqrt(2),z,z*sqrt(2),i*z,i*z*sqrt(2); z=exp(i*pi/8)'


@dataclass(frozen=True,slots=True)
class Cyclotomic:
    lo: Exact=E0
    hi: Exact=E0

    def __post_init__(self):
        object.__setattr__(self,'lo',Exact.coerce(self.lo))
        object.__setattr__(self,'hi',Exact.coerce(self.hi))

    @staticmethod
    def coerce(value):return value if isinstance(value,Cyclotomic) else Cyclotomic(value)

    @property
    def coefficients(self):return self.lo.coefficients+self.hi.coefficients

    @property
    def max_bits(self):return max(self.lo.max_bits,self.hi.max_bits)

    def __bool__(self):return bool(self.lo or self.hi)

    def __add__(self,other):
        other=self.coerce(other)
        return Cyclotomic(self.lo+other.lo,self.hi+other.hi)
    __radd__=__add__

    def __neg__(self):return Cyclotomic(-self.lo,-self.hi)
    def __sub__(self,other):return self+-self.coerce(other)
    def __rsub__(self,other):return self.coerce(other)+-self

    def __mul__(self,other):
        other=self.coerce(other)
        if not self or not other:return ZERO
        return Cyclotomic(self.lo*other.lo+self.hi*other.hi*OMEGA,
                          self.lo*other.hi+self.hi*other.lo)
    __rmul__=__mul__

    def conjugate(self):return Cyclotomic(self.lo.conjugate(),self.hi.conjugate()*OMEGA.conjugate())
    def norm2(self):return self*self.conjugate()

    def inverse(self):
        if not self:raise ZeroDivisionError('zero cyclotomic value has no inverse')
        denominator=self.lo*self.lo-self.hi*self.hi*OMEGA
        return Cyclotomic(self.lo/denominator,-self.hi/denominator)

    def __truediv__(self,other):return self*self.coerce(other).inverse()
    def __rtruediv__(self,other):return self.coerce(other)*self.inverse()

    def __pow__(self,n):
        if isinstance(n,bool) or not isinstance(n,int):raise TypeError('integer exponent required')
        base=self if n>=0 else self.inverse();n=abs(n);out=ONE
        while n:
            if n&1:out=out*base
            base=base*base;n>>=1
        return out

    def __complex__(self):return complex(self.lo)+complex(self.hi)*complex(cos(pi/8),sin(pi/8))

    def to_dict(self):return dict(basis=BASIS,coefficients=[str(v) for v in self.coefficients])

    @staticmethod
    def from_dict(value):
        if not isinstance(value,dict) or set(value)!={'basis','coefficients'}:
            raise ValueError('invalid exact coefficient object')
        coefficients=value['coefficients']
        if not isinstance(coefficients,list) or any(not isinstance(v,str) for v in coefficients):
            raise ValueError('exact coefficients must be rational strings')
        if value['basis']==E0.to_dict()['basis'] and len(coefficients)==4:
            return Cyclotomic(Exact(*(Fraction(v) for v in coefficients)))
        if value['basis']!=BASIS or len(coefficients)!=8:raise ValueError('unknown exact field basis')
        return Cyclotomic(Exact(*(Fraction(v) for v in coefficients[:4])),
                          Exact(*(Fraction(v) for v in coefficients[4:])))

    def real_bounds(self,precision=20):
        """Rational outward enclosure via nested integer-square-root bounds."""
        _integer(precision,'enclosure precision',1,200_000)
        if self!=self.conjugate():raise ValueError('a real cyclotomic value is required')
        scale=10**precision
        def sqrt_bounds(x):
            low=isqrt((x.numerator*scale*scale)//x.denominator)
            lower=Fraction(low,scale)
            return lower,lower if lower*lower==x else Fraction(low+1,scale)
        def mul(x,y):
            products=[a*b for a in x for b in y]
            return min(products),max(products)
        def add(x,y):return x[0]+y[0],x[1]+y[1]
        def affine(a,b,interval):return add((a,a),mul((b,b),interval))
        rt=sqrt_bounds(Fraction(2))
        cosine=(sqrt_bounds(2+rt[0])[0]/2,sqrt_bounds(2+rt[1])[1]/2)
        sine=(sqrt_bounds(2-rt[1])[0]/2,sqrt_bounds(2-rt[0])[1]/2)
        a,b,_,_,e,f,g,h=self.coefficients
        return add(affine(a,b,rt),add(mul(affine(e,f,rt),cosine),mul(affine(-g,-h,rt),sine)))

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
        return dict(exact=self.to_dict(),expression='rational coefficients in the declared zeta_16 basis',
            decimal=_fixed((low+high)*5,places+1),decimal_enclosure=dict(
                lower=_fixed(low,places),upper=_fixed(high,places),
                maximum_absolute_display_error=str(Fraction(high-low,2*scale)),
                method='nested integer-square-root bounds and outward rational rounding'))


ZERO,ONE,ZETA=Cyclotomic(),Cyclotomic(1),Cyclotomic(E0,E1)
