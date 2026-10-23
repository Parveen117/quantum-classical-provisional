"""Exact dyadic matrix products using signed Kronecker substitution.

Each matrix has one power-of-two denominator and four Python-integer numerator
arrays. A bounded dot product is packed into base B, multiplied with NumPy's
object-integer matmul, and decoded *before* reducing sqrt(2)^2=2 and i^2=-1.
No floating-point arithmetic, fixed-width overflow, rank decision or truncation
enters this path. This is an arithmetic optimization, not bond compression.
"""
from dataclasses import dataclass

import numpy as np

from .dyadic import Dyadic


@dataclass
class IntegerMatrix:
    parts: tuple
    shift: int

    @property
    def shape(self):
        return self.parts[0].shape

    @classmethod
    def from_sparse(cls, entries, shape):
        shift = max((v.shift for v in entries.values()), default=0)
        parts = tuple(np.zeros(shape, dtype=object) for _ in range(4))
        for index, v in entries.items():
            for part, coefficient in zip(parts, (v.a, v.b, v.c, v.d)):
                part[index] = coefficient << (shift-v.shift)
        return cls(parts, shift)

    def entries(self):
        return {index: v for index in np.ndindex(self.shape)
                if (v := Dyadic(*(part[index] for part in self.parts), self.shift))}

    def adjoint(self):
        a, b, c, d = self.parts
        return IntegerMatrix((a.T, b.T, -c.T, -d.T), self.shift)

    def add(self, other):
        if self.shape != other.shape:
            raise ValueError('matrix addition shape mismatch')
        shift = max(self.shift, other.shift)
        return IntegerMatrix(tuple(x * (1 << (shift-self.shift)) +
                                   y * (1 << (shift-other.shift))
                                   for x, y in zip(self.parts, other.parts)), shift)

    def scale(self, value):
        if not isinstance(value, Dyadic):
            raise TypeError('dyadic matrix scale required')
        a, b, c, d = self.parts
        e, f, g, h = value.a, value.b, value.c, value.d
        return IntegerMatrix((a*e+2*b*f-c*g-2*d*h, a*f+b*e-c*h-d*g,
                              a*g+2*b*h+c*e+2*d*f, a*h+b*g+c*f+d*e),
                             self.shift+value.shift)

    def inspect(self, budget):
        # Check canonical entries, so shared denominators do not inflate the
        # user-facing coefficient-bit measurement. Guards are also applied
        # before dense allocation/multiplication in matmul.
        entries = self.entries()
        budget.inspect(list(entries.values()), temporary=True)
        return entries

    def matmul(self, other, budget):
        m, k = self.shape
        k2, n = other.shape
        if k != k2:
            raise ValueError('matrix product shape mismatch')
        # Count all dense ring-product slots, including zero entries. This is
        # conservative relative to the sparse evaluator's nonzero work count.
        budget.tick(m*k*n)
        slots = max(m*k, k*n, m*n)
        if slots > budget.max_coefficients:
            budget.fail('exact integer matrix allocation exceeds coefficient-count budget')
        xbits = max((abs(v).bit_length() for p in self.parts for v in p.flat), default=0)
        ybits = max((abs(v).bit_length() for p in other.parts for v in p.flat), default=0)
        # A convolution digit sums at most 4*k products, each strictly less
        # than 2**(xbits+ybits) in magnitude. B > 2*4*k*2**(xbits+ybits)
        # makes balanced decoding unique even for negative coefficients.
        width = max(2, xbits+ybits+(4*k).bit_length()+1)
        budget.stats['peak_packing_digit_bits'] = max(
            budget.stats.get('peak_packing_digit_bits', 0), width)
        budget.stats['integer_matrix_products'] = budget.stats.get('integer_matrix_products', 0)+1
        base = 1 << width
        powers = (1, base, base**3, base**4)

        def pack(matrix):
            a, b, c, d = matrix.parts
            return a + b*powers[1] + c*powers[2] + d*powers[3]

        packed = pack(self) @ pack(other)
        out = tuple(np.zeros((m, n), dtype=object) for _ in range(4))
        mask, half = base-1, base//2
        for index in np.ndindex((m, n)):
            value = packed[index]
            digits = []
            for _ in range(9):
                digit = value & mask
                if digit >= half:
                    digit -= base
                digits.append(digit)
                value = (value-digit) >> width
            if value:
                raise ArithmeticError('integer matrix packing bound violated')
            a, b, c, d, e, f, g, h, i = digits
            out[0][index], out[1][index] = a+2*c-g-2*i, b-h
            out[2][index], out[3][index] = d+2*f, e
        result = IntegerMatrix(out, self.shift+other.shift)
        result.inspect(budget)
        return result
