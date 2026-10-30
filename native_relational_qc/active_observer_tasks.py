"""Declared polynomial sensors and preassigned whole-function dataset splits.

The learner never receives this model or its coefficients. These generators
are an exact synthetic benchmark, not physical sensor validation. Quartic
and quintic energies include mixed derivatives and several observation points.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
import hashlib
from math import factorial
import random

from .active_observer import Contract, Interval, native_curvature, rational
from .self_learning import digest


@dataclass(frozen=True)
class PolynomialEnergy:
    # Taylor coefficients: terms (i,j,t) contribute t*s**i*v**j/(i!*j!).
    terms: tuple

    def __post_init__(self):
        if not isinstance(self.terms, tuple) or not 1 <= len(self.terms) <= 21:
            raise ValueError("bounded polynomial required")
        seen = set()
        for i, j, value in self.terms:
            if type(i) is not int or type(j) is not int or min(i, j) < 0 or i+j > 5 or (i, j) in seen:
                raise ValueError("unique monomials of total degree <=5 required")
            rational(value)
            seen.add((i, j))

    def derivative(self, point, orders):
        s, v = map(rational, point)
        a, b = orders
        return sum((Q(t)*s**(i-a)*v**(j-b)/factorial(i-a)/factorial(j-b)
                    for i, j, t in self.terms if i >= a and j >= b), Q())

    def hessian(self, point):
        return tuple(self.derivative(point, orders) for orders in ((2, 0), (1, 1), (0, 2)))

    def jets(self, point):
        return tuple(tuple(self.derivative(point, orders) for orders in row)
                     for row in (((3, 0), (2, 1), (1, 2)), ((2, 1), (1, 2), (0, 3))))

    def curvature(self, point):
        return native_curvature(self.hessian(point), *self.jets(point))

    def record(self):
        return [[i, j, str(t)] for i, j, t in self.terms]

    def positive_patch(self, radius=Q(1, 2)):
        """Conservative diagonal-dominance certificate on a whole square."""
        bounds = []
        origin = (Q(0), Q(0))
        for a, b in ((2, 0), (1, 1), (0, 2)):
            center = self.derivative(origin, (a, b))
            error = sum((abs(Q(t))*radius**(i+j-a-b)/factorial(i-a)/factorial(j-b)
                         for i, j, t in self.terms if i >= a and j >= b and i+j > a+b), Q())
            bounds.append(Interval(center-error, center+error))
        a, b, c = bounds
        lower = min(a.low, c.low)-max(abs(b.low), abs(b.high))
        if lower <= 0:
            raise ValueError("positive patch not established")
        return dict(radius=str(radius), lower_eigenvalue=str(lower))


@dataclass(frozen=True)
class Case:
    family: str
    energy: PolynomialEnergy
    point: tuple
    noise_seed: int

    def record(self):
        return dict(family=self.family, energy=self.energy.record(), point=[str(x) for x in self.point],
                    noise_seed=self.noise_seed, positive_patch=self.energy.positive_patch())


def sensor(case, noise):
    """Stateless bounded noise: repeat queries and policies see identical data."""
    noise = rational(noise)
    if noise < 0:
        raise ValueError("noise bound must be nonnegative")
    def read(point):
        if max(abs(x) for x in point) > Q(1, 2):
            raise ValueError("query left the declared positive patch")
        values = case.energy.hessian(point)
        out = []
        for j, value in enumerate(values):
            key = str(case.noise_seed)+":"+":".join(map(str, point))+":"+str(j)
            sample = int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big") % 21-10
            out.append(value+noise*Q(sample, 10))
        return tuple(out)
    return read


def make_splits():
    """Fixed before training: train 64/val 16/test 40 distinct energy functions.

    Every function contributes two positions, all in the same split. Train/val
    fifth-order supports omit (3,2),(2,3); test adds these mixed terms. No
    selection on curvature, learner success, or evaluation scores occurs.
    """
    result = {}
    for split, seed, count in (("train", 3101, 64), ("validation", 3102, 16), ("test", 3103, 40)):
        rng = random.Random(seed)
        cases = []
        for index in range(count):
            weak_axis = rng.randrange(2)
            weak = Q(rng.choice((-3, -2, -1, 1, 2, 3)), 64)
            strong = Q(rng.choice((-8, -6, 6, 8)), 4)
            u, v = (weak, strong) if weak_axis == 0 else (strong, weak)
            terms = [(2, 0, Q(4+rng.randrange(3))), (1, 1, Q(rng.choice((2, 3, 4)), 4)),
                     (0, 2, Q(5+rng.randrange(3))), (3, 0, u), (0, 3, v),
                     (2, 1, Q(rng.choice((-1, 0, 1)), 64)), (1, 2, Q(rng.choice((-1, 0, 1)), 64))]
            for i in range(5):
                terms.append((i, 4-i, Q(rng.choice((-2, -1, 0, 1, 2)), 4)))
            if index % 4 != 0:  # a declared quartic subset; otherwise quintic
                for i in range(6):
                    if split != "test" and i in (2, 3):
                        continue
                    scale = 6 if i in (0, 5) else 2
                    terms.append((i, 5-i, Q(rng.choice((-scale, scale)))))
            energy = PolynomialEnergy(tuple(sorted(terms)))
            energy.positive_patch()
            for position in range(2):
                point = (Q(rng.choice((-1, 0, 1)), 8), Q((-1, 1)[position], 8))
                cases.append(Case(f"{split}_{index:03}", energy, point, seed*1000+index))
        result[split] = tuple(cases)
    families = [{c.family for c in cases} for cases in result.values()]
    energy_sets = [{digest(c.energy.record()) for c in cases} for cases in result.values()]
    for groups in (families, energy_sets):
        if any(groups[i] & groups[j] for i in range(3) for j in range(i+1, 3)):
            raise AssertionError("whole-function split leakage")
    return result


def blind_pair():
    """Same five initial H readings, opposite true curvature at the origin.

    Delta H_ss = +/- s*(s*s-h*h); it vanishes at s=0,+/-h.
    Delta U = +/- (s**5/20-h*h*s**3/6). Third H derivative bound is 6.
    No policy on these five readings can identify both signs without acquiring
    more information, even with an unlimited training set.
    """
    h = Contract().step
    cases = []
    for sign in (-1, 1):
        terms = ((2, 0, Q(4)), (1, 1, Q(1)), (0, 2, Q(5)),
                 (0, 3, Q(1)), (3, 0, -sign*h*h), (5, 0, Q(6*sign)))
        cases.append(Case(f"blind_{sign}", PolynomialEnergy(terms), (Q(0), Q(0)), 0))
    return tuple(cases)
