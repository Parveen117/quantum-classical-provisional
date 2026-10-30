"""Compatibility views for historical constructors and JSON bases.

All storage, products, inversion and enclosures use cyclotomic_pow2. These
views retain old coefficients/lo/hi/JSON for saved ledgers and Python callers;
they are not separate arithmetic engines.
"""
from fractions import Fraction
from functools import lru_cache
from .cyclotomic_pow2 import CyclotomicPow2, field_of_order, _basis
from .exact import Exact

BASES = {16: '1,sqrt(2),i,i*sqrt(2),z,z*sqrt(2),i*z,i*z*sqrt(2); z=exp(i*pi/8)'}
BASES[32] = 'Q(zeta_32): (1,w) times ['+BASES[16]+']; w=exp(i*pi/16), w^2=z'
BASES[64] = 'Q(zeta_64): (1,u) times ['+BASES[32]+']; u=exp(i*pi/32), u^2=w'


class LegacyView:
    __slots__ = ()

    def __init__(self, lo=0, hi=0):
        if isinstance(hi,bool) or not isinstance(hi,(int,Fraction,Exact,CyclotomicPow2)):
            raise TypeError('unsupported exact high component')
        super().__init__(lo)
        if hi:
            out=self+type(self)(hi)*type(self).root()
            self.data,self.item,self.den=out.data,out.item,out.den

    def _component(self, odd):
        values=self._list()[odd::2]
        if self.ORDER==16:
            a,b,c,d=(Fraction(v,self.den) for v in values)
            return Exact(a,(b-d)/2,c,(b+d)/2)
        return legacy_field_of_order(self.ORDER//2)._build(values,self.den)

    @property
    def lo(self):return self._component(0)

    @property
    def hi(self):return self._component(1)

    @property
    def coefficients(self):
        # Legacy basis order is bit-reversed over the tower offsets. Convert
        # directly from the stored vector without rebuilding a nested field.
        v=self._list();stride=self.ORDER//8;bits=stride.bit_length()-1;out=[]
        for k in range(stride):
            r=int(format(k,f'0{bits}b')[::-1],2)
            out.extend((Fraction(v[r],self.den),
                        Fraction(v[r+stride]-v[r+3*stride],2*self.den),
                        Fraction(v[r+2*stride],self.den),
                        Fraction(v[r+stride]+v[r+3*stride],2*self.den)))
        return tuple(out)

    @property
    def max_bits(self):
        # Historical backend budgets count historical coefficient coordinates.
        # The shared product representation must not silently relax that cap.
        return max(max(abs(c.numerator).bit_length(),c.denominator.bit_length())
                   for c in self.coefficients)

    def to_dict(self):
        return dict(basis=BASES[self.ORDER],coefficients=[str(c) for c in self.coefficients])

    @classmethod
    def from_dict(cls,value):
        if not isinstance(value,dict):raise ValueError('invalid exact coefficient object')
        basis=value.get('basis')
        if basis==_basis(cls.ORDER):return cls(field_of_order(cls.ORDER).from_dict(value))
        if set(value)!={'basis','coefficients'}:raise ValueError('invalid exact coefficient object')
        rows=value['coefficients']
        if not isinstance(rows,list) or any(type(c) is not str for c in rows):
            raise ValueError('exact coefficients must be rational strings')
        if basis==Exact().to_dict()['basis']:
            if len(rows)!=4:raise ValueError('wrong coefficient count for Q(zeta_8)')
            return cls(Exact(*(Fraction(c) for c in rows)))
        for order,known in BASES.items():
            if basis!=known:continue
            if order>cls.ORDER or len(rows)!=order//2:raise ValueError('wrong coefficient count or order')
            lower=Exact if order==16 else legacy_field_of_order(order//2)
            def part(coeffs):
                return Exact(*(Fraction(c) for c in coeffs)) if order==16 else lower.from_dict(dict(basis=BASES[order//2],coefficients=coeffs))
            n=order//4
            return cls(legacy_field_of_order(order)(part(rows[:n]),part(rows[n:])))
        raise ValueError('unknown exact field basis')


@lru_cache(maxsize=3)
def legacy_field_of_order(order):
    if order not in BASES:raise ValueError('legacy order must be 16, 32 or 64')
    return type('Cyclotomic' if order==16 else f'Cyclotomic{order}',
                (LegacyView,field_of_order(order)),{'__slots__':()})
