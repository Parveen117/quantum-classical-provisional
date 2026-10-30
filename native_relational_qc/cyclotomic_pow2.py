"""Exact Q(zeta_M), M=2**k (8<=M<=4096), in the flat power basis.

An element is (1/den) * sum_e c_e zeta**e with integer c_e, 0<=e<M/2, and
zeta=exp(2*pi*i/M). Reduction uses the cyclotomic relation zeta**(M/2)=-1,
so the power basis is a Q-basis and the stored form is canonical: den>0,
gcd(den,c_0,...)=1. Q(zeta_16/32/64) of the nested backends are the
subfields M=16/32/64; this module is an independent flat representation,
not a speedup or prime-spectrum theorem.

Storage: the n=M/2 numerators are kept densely as little-endian signed bytes
of the smallest width (1, 2, 4 or 8 bytes) that holds them, or as a tuple of
Python integers beyond 62 bits. Arithmetic runs on NumPy int64 vectors behind
explicit overflow bounds; a general product is one exact int64 convolution
reduced negacyclically, and beyond int64 a Kronecker-substitution product of
two Python integers. Every bound failure falls back to Python integers, never
to floating point.
"""
from fractions import Fraction
from functools import lru_cache,reduce
from math import cos,sin,pi,gcd

import numpy as np

from .compact import ResourceLimit,_integer

MIN_ORDER,MAX_ORDER=8,4096
_DTYPES={1:np.dtype('<i1'),2:np.dtype('<i2'),4:np.dtype('<i4'),8:np.dtype('<i8')}
_LIMIT=1<<62        # int64 vector arithmetic is used only for magnitudes below this
_FEW=4              # operands with at most this many terms multiply by rotation


def _basis(order):
    return f'Q(zeta_{order}) power basis zeta^0..zeta^{order//2-1}; zeta=exp(2*pi*i/{order}), zeta^{order//2}=-1'


def _item_for(maxabs):
    return 1 if maxabs<1<<7 else 2 if maxabs<1<<15 else 4 if maxabs<1<<31 else 8


def _rotate(a,e):
    """int64 vector of zeta**e times the element with numerators a, 0<=e<n."""
    if e==0:return a.copy()
    n=len(a);out=np.empty_like(a);out[e:]=a[:n-e];out[:e]=-a[n-e:]
    return out


def _negacyclic(product,n):
    out=product[:n].copy();out[:n-1]-=product[n:]
    return out


def _mul_wide(a,b,n):
    """Exact negacyclic product of two integer lists by Kronecker substitution."""
    ma=max(map(abs,a));mb=max(map(abs,b))
    terms=min(sum(1 for c in a if c),sum(1 for c in b if c))
    width=((terms*ma*mb).bit_length()+2+7)//8*8;bytes_per=width//8;modulus=1<<width
    def pack(v):
        unsigned=int.from_bytes(b''.join((c%modulus).to_bytes(bytes_per,'little') for c in v),'little')
        mask=int.from_bytes(b''.join((b'\x01' if c<0 else b'\x00')+bytes(bytes_per-1) for c in v),'little')
        return unsigned-(mask<<width)
    length=2*n-1;half=1<<(width-1)
    offset=half*(((1<<(width*length))-1)//(modulus-1))
    buffer=(pack(a)*pack(b)+offset).to_bytes(bytes_per*length,'little')
    digits=[int.from_bytes(buffer[i*bytes_per:(i+1)*bytes_per],'little')-half for i in range(length)]
    return [digits[k]-(digits[k+n] if k+n<length else 0) for k in range(n)]


class CyclotomicPow2:
    """Base class; use field_of_order(M) for a concrete field."""
    __slots__=('data','item','den')
    ORDER=None;N=None;_ZERO=b''

    def __init__(self,value=0):
        if isinstance(value,CyclotomicPow2):
            if value.ORDER!=self.ORDER:raise ValueError('cyclotomic orders differ; no implicit embedding')
            self.data,self.item,self.den=value.data,value.item,value.den;return
        from .exact import Exact
        if isinstance(value,bool):raise TypeError('boolean is not an exact coefficient')
        if isinstance(value,(int,Fraction)):
            value=Fraction(value);out=self._from_sparse({0:value.numerator},value.denominator)
        elif isinstance(value,Exact):
            a,b,c,d=value.coefficients;F=type(self)
            out=F(a)+F(b)*F.sqrt2()+F.imag()*(F(c)+F(d)*F.sqrt2())
        else:raise TypeError('unsupported exact value for Q(zeta_M)')
        self.data,self.item,self.den=out.data,out.item,out.den

    # Construction -----------------------------------------------------------
    @classmethod
    def _build(cls,coeffs,den):
        """Canonical element from an int64 vector or a list of ints, over den!=0."""
        out=object.__new__(cls)
        if isinstance(coeffs,np.ndarray):
            if den<0:den,coeffs=-den,-coeffs
            if not coeffs.any():
                out.data,out.item,out.den=cls._ZERO,1,1;return out
            g=gcd(int(np.gcd.reduce(coeffs)),den)
            if g>1:coeffs=coeffs//g;den//=g
            item=_item_for(int(np.abs(coeffs).max()))
            out.data,out.item,out.den=coeffs.astype(_DTYPES[item]).tobytes(),item,den
            return out
        coeffs=list(coeffs)
        if den<0:den,coeffs=-den,[-c for c in coeffs]
        if not any(coeffs):
            out.data,out.item,out.den=cls._ZERO,1,1;return out
        g=reduce(gcd,coeffs,den)
        if g>1:coeffs=[c//g for c in coeffs];den//=g
        if max(map(abs,coeffs))<_LIMIT:return cls._build(np.array(coeffs,dtype=np.int64),den)
        out.data,out.item,out.den=tuple(coeffs),0,den
        return out

    @classmethod
    def _from_sparse(cls,coefficients,den):
        """Element from {exponent: integer numerator} over den."""
        if all(abs(c)<_LIMIT for c in coefficients.values()):
            arr=np.zeros(cls.N,dtype=np.int64)
            for e,c in coefficients.items():arr[e]=c
            return cls._build(arr,den)
        values=[0]*cls.N
        for e,c in coefficients.items():values[e]=c
        return cls._build(values,den)
    _make=_from_sparse

    @classmethod
    def coerce(cls,value):return value if type(value) is cls else cls(value)

    @classmethod
    def root(cls,power=1):
        """zeta**power for any integer power."""
        e=power%cls.ORDER
        return cls._from_sparse({e-cls.N:-1} if e>=cls.N else {e:1},1)

    @classmethod
    def sqrt2(cls):return cls.root(cls.ORDER//8)+cls.root(-cls.ORDER//8)

    @classmethod
    def imag(cls):return cls.root(cls.ORDER//4)

    # Views --------------------------------------------------------------------
    def _vec(self):
        """Numerators as an int64 vector (item>0) or a list of Python ints."""
        if self.item:return np.frombuffer(self.data,dtype=_DTYPES[self.item]).astype(np.int64)
        return list(self.data)

    def _list(self):return self._vec().tolist() if self.item else list(self.data)

    def _maxabs(self):
        v=self._vec()
        return int(np.abs(v).max()) if self.item else max(map(abs,v))

    @property
    def coefficients(self):return tuple(Fraction(c,self.den) for c in self._list())

    @property
    def max_bits(self):return max(self.den.bit_length(),self._maxabs().bit_length())

    def __bool__(self):return self.item!=1 or self.data!=self._ZERO
    def __eq__(self,other):
        try:other=self.coerce(other)
        except (TypeError,ValueError):return NotImplemented
        return self.den==other.den and self.item==other.item and self.data==other.data
    def __hash__(self):return hash((self.ORDER,self.den,self.item,self.data))
    def __repr__(self):return f'{type(self).__name__}({dict((e,c) for e,c in enumerate(self._list()) if c)}/{self.den})'

    # Ring operations ---------------------------------------------------------
    def __add__(self,other):
        other=self.coerce(other)
        if not other:return self
        if not self:return other
        d1,d2=self.den,other.den
        if d1==d2:s1=s2=1;den=d1
        else:g=gcd(d1,d2);s1=d2//g;s2=d1//g;den=d1*s1
        a,b=self._vec(),other._vec()
        if (self.item and other.item and 8*self.item-1+s1.bit_length()<62
                and 8*other.item-1+s2.bit_length()<62):
            return self._build(a*s1+b*s2,den)
        a=a.tolist() if self.item else a;b=b.tolist() if other.item else b
        return self._build([x*s1+y*s2 for x,y in zip(a,b)],den)
    __radd__=__add__

    def __neg__(self):
        v=self._vec()
        return self._build(-v if self.item else [-c for c in v],self.den)
    def __sub__(self,other):return self+-self.coerce(other)
    def __rsub__(self,other):return self.coerce(other)+-self

    def __mul__(self,other):
        other=self.coerce(other)
        if not self or not other:return type(self)()
        den=self.den*other.den
        if self.item and other.item:
            a,b=self._vec(),other._vec()
            na,nb=int(np.count_nonzero(a)),int(np.count_nonzero(b))
            if nb>na:a,b,na,nb=b,a,nb,na
            ma=int(np.abs(a).max())
            if nb<=_FEW:
                index=np.flatnonzero(b);cs=b[index].tolist()
                if ma*sum(map(abs,cs))<_LIMIT:
                    out=np.zeros(self.N,dtype=np.int64)
                    for e,c in zip(index.tolist(),cs):out+=c*_rotate(a,e)
                    return self._build(out,den)
            elif 2*nb*ma*int(np.abs(b).max())<1<<63:
                # Every product coefficient is a sum of at most nb terms below ma*mb,
                # so the int64 convolution and the negacyclic fold are exact.
                return self._build(_negacyclic(np.convolve(a,b),self.N),den)
        return self._build(_mul_wide(self._list(),other._list(),self.N),den)
    __rmul__=__mul__

    def __truediv__(self,other):
        """Division by a nonzero rational only; general inversion is not needed here."""
        if isinstance(other,bool) or not isinstance(other,(int,Fraction)):
            raise TypeError('only rational divisors are supported')
        other=Fraction(other)
        if not other:raise ZeroDivisionError('division by zero')
        v=self._vec()
        if self.item and 8*self.item-1+other.denominator.bit_length()<63:
            return self._build(v*other.denominator,self.den*other.numerator)
        v=v.tolist() if self.item else v
        return self._build([c*other.denominator for c in v],self.den*other.numerator)

    def conjugate(self):
        v=self._vec()
        if self.item:
            out=np.empty_like(v);out[0]=v[0];out[1:]=-v[:0:-1]
            return self._build(out,self.den)
        return self._build([v[0]]+[-c for c in v[:0:-1]],self.den)
    def norm2(self):return self*self.conjugate()

    def __complex__(self):
        angles=2*pi*np.arange(self.N)/self.ORDER
        v=self._vec()
        if self.item:return complex(np.dot(v.astype(float),np.cos(angles)+1j*np.sin(angles)))/self.den
        return sum((c*complex(cos(t),sin(t)) for c,t in zip(v,angles.tolist())),0j)/self.den

    # Serialization -------------------------------------------------------------
    def to_dict(self):
        """Real values: denominator plus numerators of zeta^0..zeta^(n/2-1), trailing
        zeros removed; the rest follow from c_(n-e)=-c_e. Others: sparse rationals."""
        values=self._list()
        if self==self.conjugate():
            half=values[:self.N//2]
            while half and half[-1]==0:half.pop()
            return dict(basis=_basis(self.ORDER),denominator=str(self.den),real_numerators=half)
        return dict(basis=_basis(self.ORDER),
                    sparse_coefficients=[[e,str(Fraction(c,self.den))] for e,c in enumerate(values) if c])

    @classmethod
    def from_dict(cls,value):
        if not isinstance(value,dict) or value.get('basis')!=_basis(cls.ORDER):
            raise ValueError('invalid exact coefficient object for this cyclotomic order')
        keys=set(value)
        if keys=={'basis','denominator','real_numerators'}:
            den,rows=value['denominator'],value['real_numerators']
            if not isinstance(den,str) or not den.isdigit() or int(den)<1:
                raise ValueError('denominator must be a positive integer string')
            if (not isinstance(rows,list) or len(rows)>cls.N//2 or
                    any(type(c) is not int for c in rows)):
                raise ValueError('real numerators must be at most n/2 integers')
            coeffs=[0]*cls.N
            for e,c in enumerate(rows):
                coeffs[e]=c
                if e:coeffs[cls.N-e]=-c
            return cls._build(coeffs,int(den))
        if keys=={'basis','sparse_coefficients'}:
            rows=value['sparse_coefficients']
            if not isinstance(rows,list):raise ValueError('sparse coefficients must be a list')
            seen={}
            for row in rows:
                if (not isinstance(row,list) or len(row)!=2 or type(row[0]) is not int or
                        not isinstance(row[1],str) or not 0<=row[0]<cls.N or row[0] in seen):
                    raise ValueError('invalid sparse coefficient row')
                seen[row[0]]=Fraction(row[1])
            den=reduce(lambda x,y:x*y//gcd(x,y),(f.denominator for f in seen.values()),1)
            return cls._from_sparse({e:f.numerator*(den//f.denominator) for e,f in seen.items()},den)
        raise ValueError('invalid exact coefficient object')

    # Certified real enclosures ------------------------------------------------
    def _integer_bounds(self,bits):
        """Python ints L<=H with L <= den*2**bits*value <= H, from cosine tables."""
        low_table,high_table=_cos_table(self.ORDER,bits)
        v=self._vec()
        c=v.astype(object) if self.item else np.array(v,dtype=object)
        positive=np.array(c>0,dtype=bool)
        return (int((c*np.where(positive,low_table,high_table)).sum()),
                int((c*np.where(positive,high_table,low_table)).sum()))

    def real_bounds(self,precision=20):
        """Rational outward enclosure of a real value; precision in decimal digits."""
        _integer(precision,'enclosure precision',1,200_000)
        if self!=self.conjugate():raise ValueError('a real cyclotomic value is required')
        bits=(precision*33219+9999)//10000+16
        low,high=self._integer_bounds(bits);scale=self.den<<bits
        return Fraction(low,scale),Fraction(high,scale)

    def real_sign(self):
        if self!=self.conjugate():raise ValueError('a real cyclotomic value is required')
        if not self:return 0
        if self.item:
            # Rigorous int64 attempt: |c|<2**(8*item-1), |table|<=2**fbits, n terms.
            fbits=61-(8*self.item-1)-self.N.bit_length()
            if fbits>=8:
                v=self._vec();low_table,high_table=_cos_table64(self.ORDER,fbits);positive=v>0
                if int(np.dot(v,np.where(positive,low_table,high_table)))>0:return 1
                if int(np.dot(v,np.where(positive,high_table,low_table)))<0:return -1
        precision=8;cap=min(200_000,16*(self.max_bits+self.N.bit_length()+1)+64)
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
        bits=max(0,self._maxabs().bit_length()-self.den.bit_length()+1)+self.N.bit_length()
        precision=places+(bits*30103+99999)//100000+8
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
    return type(f'Cyclotomic{order}Flat',(CyclotomicPow2,),
                dict(__slots__=(),ORDER=order,N=order//2,_ZERO=bytes(order//2)))


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


@lru_cache(maxsize=32)
def _cos_table(order,bits):
    """Object arrays of integers L_e<=2**bits*cos(2*pi*e/order)<=H_e, e<order/2."""
    n=order//2;scale=1<<bits
    low=np.empty(n,dtype=object);high=np.empty(n,dtype=object)
    for e in range(n):
        l,h=_cos_bounds(order,e,bits);low[e]=int(l*scale);high[e]=int(h*scale)
    return low,high


@lru_cache(maxsize=32)
def _cos_table64(order,bits):
    low,high=_cos_table(order,bits)
    return np.array(low.tolist(),dtype=np.int64),np.array(high.tolist(),dtype=np.int64)
