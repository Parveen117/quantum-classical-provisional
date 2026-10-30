"""Exact Q(sqrt(2), i) arithmetic; floating point is display-only.

An element is a + b sqrt(2) + i(c + d sqrt(2)), with rational coefficients.
This is a standard number field, used here to retain phase and ratio memory.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import sqrt


@dataclass(frozen=True, slots=True)
class Exact:
    a: Fraction = Fraction(0)
    b: Fraction = Fraction(0)
    c: Fraction = Fraction(0)
    d: Fraction = Fraction(0)

    def __post_init__(self):
        for name in ("a", "b", "c", "d"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
                raise TypeError("exact coefficients require int or Fraction; floats are not inferred")
            object.__setattr__(self, name, Fraction(value))

    @staticmethod
    def coerce(value):
        return value if isinstance(value, Exact) else Exact(value)

    @property
    def coefficients(self):
        return self.a, self.b, self.c, self.d

    def __bool__(self):
        return any(self.coefficients)

    def __add__(self, other):
        other = Exact.coerce(other)
        return Exact(*(x + y for x, y in zip(self.coefficients, other.coefficients)))

    __radd__ = __add__

    def __neg__(self):
        return Exact(*(-x for x in self.coefficients))

    def __sub__(self, other):
        return self + (-Exact.coerce(other))

    def __rsub__(self, other):
        return Exact.coerce(other) - self

    def __mul__(self, other):
        other = Exact.coerce(other)
        if not self or not other:
            return ZERO
        if self == ONE:
            return other
        if other == ONE:
            return self
        a, b, c, d = self.coefficients
        e, f, g, h = other.coefficients
        return Exact(a*e + 2*b*f - c*g - 2*d*h,
                     a*f + b*e - c*h - d*g,
                     a*g + 2*b*h + c*e + 2*d*f,
                     a*h + b*g + c*f + d*e)

    __rmul__ = __mul__

    def conjugate(self):
        return Exact(self.a, self.b, -self.c, -self.d)

    def norm2(self):
        a, b, c, d = self.coefficients
        return Exact(a*a + 2*b*b + c*c + 2*d*d, 2*(a*b + c*d))

    def inverse(self):
        if not self:
            raise ZeroDivisionError("zero exact amplitude has no inverse")
        if self == ONE:
            return ONE
        norm = self.norm2()
        denominator = norm.a**2 - 2*norm.b**2
        return self.conjugate() * Exact(norm.a/denominator, -norm.b/denominator)

    def __truediv__(self, other):
        other = Exact.coerce(other)
        if not other:
            raise ZeroDivisionError("division by zero")
        if self == other:
            return ONE
        return self * other.inverse()

    def __rtruediv__(self, other):
        return Exact.coerce(other) / self

    def __pow__(self, exponent):
        if isinstance(exponent, bool) or not isinstance(exponent, int):
            raise TypeError("integer exponent required")
        base = self if exponent >= 0 else self.inverse()
        exponent = abs(exponent)
        out = ONE
        while exponent:
            if exponent & 1:
                out = out * base
            base = base * base
            exponent >>= 1
        return out

    def __complex__(self):
        return complex(float(self.a) + float(self.b)*sqrt(2),
                       float(self.c) + float(self.d)*sqrt(2))

    @property
    def max_bits(self):
        return max(max(abs(x.numerator).bit_length(), x.denominator.bit_length())
                   for x in self.coefficients)

    def to_dict(self):
        return {"basis": "1,sqrt(2),i,i*sqrt(2)",
                "coefficients": [str(x) for x in self.coefficients]}


ZERO, ONE, IMAG = Exact(), Exact(1), Exact(c=1)
HALF = Exact(Fraction(1, 2))
INV_SQRT2 = Exact(b=Fraction(1, 2))
OMEGA = Exact(b=Fraction(1, 2), d=Fraction(1, 2))


def exact_gate(name):
    """All matrices are explicit in the declared EMK complex representation."""
    gates = {
        "id": ((ONE, ZERO), (ZERO, ONE)),
        "x": ((ZERO, ONE), (ONE, ZERO)),
        "rk": ((ZERO, ONE), (ONE, ZERO)),
        "y": ((ZERO, -IMAG), (IMAG, ZERO)),
        "z": ((ONE, ZERO), (ZERO, -ONE)),
        "k": ((ONE, ZERO), (ZERO, -ONE)),
        "r": ((ZERO, -ONE), (ONE, ZERO)),
        "h": ((INV_SQRT2, INV_SQRT2), (INV_SQRT2, -INV_SQRT2)),
        "s": ((ONE, ZERO), (ZERO, IMAG)),
        "sdg": ((ONE, ZERO), (ZERO, -IMAG)),
        "t": ((ONE, ZERO), (ZERO, OMEGA)),
        "tdg": ((ONE, ZERO), (ZERO, OMEGA.conjugate())),
        "sx": (((ONE + IMAG)*HALF, (ONE - IMAG)*HALF),
               ((ONE - IMAG)*HALF, (ONE + IMAG)*HALF)),
        "sxdg": (((ONE - IMAG)*HALF, (ONE + IMAG)*HALF),
                 ((ONE + IMAG)*HALF, (ONE - IMAG)*HALF)),
    }
    try:
        return gates[name]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unsupported exact gate: {name}") from exc
