"""Exact Z[1/2,sqrt(2),i] arithmetic for division-free tensor contraction.

Store four integer numerators over a shared power of two. No floats enter the
calculation. The public Exact type remains the interchange/certificate format.
"""
from dataclasses import dataclass
from fractions import Fraction

from .exact import Exact


@dataclass(frozen=True, slots=True)
class Dyadic:
    a: int = 0
    b: int = 0
    c: int = 0
    d: int = 0
    shift: int = 0

    def __post_init__(self):
        if any(type(v) is not int for v in (self.a, self.b, self.c, self.d, self.shift)) or self.shift < 0:
            raise TypeError('dyadic coefficients require integer numerators and nonnegative shift')
        mask = abs(self.a) | abs(self.b) | abs(self.c) | abs(self.d)
        if not mask:
            object.__setattr__(self, 'shift', 0)
        elif self.shift:
            cancel = min(self.shift, (mask & -mask).bit_length() - 1)
            if cancel:
                for field in ('a', 'b', 'c', 'd'):
                    object.__setattr__(self, field, getattr(self, field) >> cancel)
                object.__setattr__(self, 'shift', self.shift - cancel)

    @classmethod
    def from_exact(cls, value):
        value = Exact.coerce(value)
        shifts = [x.denominator.bit_length() - 1 for x in value.coefficients]
        if any(x.denominator != 1 << s for x, s in zip(value.coefficients, shifts)):
            raise ValueError('coefficient is outside the dyadic gate ring')
        k = max(shifts)
        return cls(*(x.numerator << (k-s) for x, s in zip(value.coefficients, shifts)), k)

    def to_exact(self):
        return Exact(*(Fraction(v, 1 << self.shift) for v in (self.a, self.b, self.c, self.d)))

    def __bool__(self):
        return bool(self.a or self.b or self.c or self.d)

    def __neg__(self):
        return Dyadic(-self.a, -self.b, -self.c, -self.d, self.shift)

    def __add__(self, other):
        if not isinstance(other, Dyadic):
            return NotImplemented
        if not self:
            return other
        if not other:
            return self
        k = max(self.shift, other.shift)
        x, y = k-self.shift, k-other.shift
        return Dyadic((self.a << x)+(other.a << y), (self.b << x)+(other.b << y),
                      (self.c << x)+(other.c << y), (self.d << x)+(other.d << y), k)

    def __sub__(self, other):
        return self + (-other)

    def __mul__(self, other):
        if not isinstance(other, Dyadic):
            return NotImplemented
        if not self or not other:
            return DZERO
        if self == DONE:
            return other
        if other == DONE:
            return self
        a,b,c,d = self.a,self.b,self.c,self.d
        e,f,g,h = other.a,other.b,other.c,other.d
        return Dyadic(a*e+2*b*f-c*g-2*d*h, a*f+b*e-c*h-d*g,
                      a*g+2*b*h+c*e+2*d*f, a*h+b*g+c*f+d*e,
                      self.shift+other.shift)

    def conjugate(self):
        return Dyadic(self.a,self.b,-self.c,-self.d,self.shift)

    @property
    def max_bits(self):
        return max(self.shift+1, abs(self.a).bit_length(), abs(self.b).bit_length(),
                   abs(self.c).bit_length(), abs(self.d).bit_length())


DZERO = Dyadic()
DONE = Dyadic(1)
DIMAG = Dyadic(c=1)
