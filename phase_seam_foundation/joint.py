"""Finite algebraic quantum completion of the EMK cut relations.

Added assumptions: complex scalar extension, commuting local algebras,
positive preparation functionals, projector readout and sandwich updates.
This is not derived from the v0.1 point-phase preparation/readout law.
No amplitude vector or matrix representation is used in this interpreter.
"""
from dataclasses import dataclass, field
from fractions import Fraction as F

from native_relational_qc.exact import Exact as E, ZERO, ONE, IMAG, INV_SQRT2
from .model import ResourceLimit

MAX_BITS = 4096
MAX_FACTORS = 64


def scalar(value):
    if type(value) not in (int, F, E):
        raise TypeError("coefficients require int, Fraction or Exact")
    value = E.coerce(value)
    if value.max_bits > MAX_BITS:
        raise ResourceLimit("joint coefficient bit limit")
    return value


def sign(value):
    """Exact order in the chosen real embedding Q(sqrt(2))."""
    value = scalar(value)
    if value.c or value.d:
        raise ValueError("ordering requires a real coefficient")
    a, b = value.a, value.b
    if not b:
        return (a > 0) - (a < 0)
    if not a:
        return (b > 0) - (b < 0)
    if (a > 0) == (b > 0):
        return (a > 0) - (a < 0)
    difference = a*a - 2*b*b
    return ((a > 0) - (a < 0)) * ((difference > 0) - (difference < 0))


def _size(sites):
    if type(sites) is not int or sites not in (1, 2):
        raise ValueError("joint prototype supports exactly one or two sites")
    return 4**sites


def basis_product(i, j, sites):
    """R^r K^k per site; cross-site factors commute by explicit assumption."""
    out, phase, place = 0, 1, 1
    for _ in range(sites):
        r, k = divmod(i % 4, 2)
        s, t = divmod(j % 4, 2)
        out += (2*(r ^ s) + (k ^ t)) * place
        if (k*s + r*s) % 2:
            phase = -phase
        i, j, place = i // 4, j // 4, place * 4
    return out, phase


def dagger_sign(i, sites):
    result = 1
    for _ in range(sites):
        if i % 4 == 2:
            result = -result
        i //= 4
    return result


@dataclass(frozen=True)
class Element:
    """Ordered basis I,K,R,RK at site 0, then site 1 (site 0 varies fastest)."""
    sites: int
    coefficients: tuple

    def __post_init__(self):
        size = _size(self.sites)
        if type(self.coefficients) is not tuple or len(self.coefficients) != size:
            raise ValueError("wrong coefficient tuple size")
        object.__setattr__(self, "coefficients", tuple(scalar(x) for x in self.coefficients))

    @classmethod
    def basis(cls, sites, index=0):
        size = _size(sites)
        if type(index) is not int or not 0 <= index < size:
            raise ValueError("basis index out of range")
        return cls(sites, tuple(ONE if i == index else ZERO for i in range(size)))

    def _other(self, value):
        if type(value) is Element:
            if value.sites != self.sites:
                raise ValueError("algebra size mismatch")
            return value
        return Element.basis(self.sites) * scalar(value)

    def __add__(self, other):
        other = self._other(other)
        return Element(self.sites, tuple(scalar(x+y) for x,y in zip(self.coefficients,other.coefficients)))

    __radd__ = __add__

    def __neg__(self):
        return Element(self.sites, tuple(-x for x in self.coefficients))

    def __sub__(self, other):
        return self + (-self._other(other))

    def __rsub__(self, other):
        return self._other(other) - self

    def __mul__(self, other):
        if type(other) is not Element:
            value = scalar(other)
            return Element(self.sites, tuple(scalar(x*value) for x in self.coefficients))
        if self.sites != other.sites:
            raise ValueError("algebra size mismatch")
        result = [ZERO] * len(self.coefficients)
        for i, x in enumerate(self.coefficients):
            if not x:
                continue
            for j, y in enumerate(other.coefficients):
                if not y:
                    continue
                k, phase = basis_product(i, j, self.sites)
                result[k] = scalar(result[k] + scalar(x*y)*phase)
        return Element(self.sites, tuple(result))

    __rmul__ = __mul__

    def __truediv__(self, other):
        return self * scalar(scalar(other).inverse())

    def dagger(self):
        return Element(self.sites, tuple(x.conjugate()*dagger_sign(i,self.sites)
                                       for i,x in enumerate(self.coefficients)))

    def tau(self):
        """Identity coefficient: normalized trace, proved positive in the note."""
        return self.coefficients[0]

    def to_dict(self):
        return {"sites": self.sites,
                "coefficients": [x.to_dict() for x in self.coefficients]}


def local(sites, site, letter):
    _size(sites)
    if type(site) is not int or not 0 <= site < sites:
        raise ValueError("site out of range")
    if type(letter) is not str or letter not in ("I", "K", "R", "L"):
        raise ValueError("use I,K,R,L where L=RK")
    return Element.basis(sites, ("I", "K", "R", "L").index(letter) * 4**site)


def observable(sites, site, u, v):
    """u*K+v*RK with real u^2+v^2=1; u=cos(2alpha), v=sin(2alpha)."""
    u, v = scalar(u), scalar(v)
    if u.c or u.d or v.c or v.d or u*u + v*v != ONE:
        raise ValueError("require real coefficients on the exact unit circle")
    return local(sites,site,"K")*u + local(sites,site,"L")*v


def projector(observation, outcome):
    if type(observation) is not Element:
        raise TypeError("expected Element observable")
    if type(outcome) is not int or outcome not in (-1, 1):
        raise ValueError("outcome must be -1 or +1")
    identity = Element.basis(observation.sites)
    if observation.dagger() != observation or observation*observation != identity:
        raise ValueError("readout requires a self-adjoint involution")
    return (identity + observation*outcome) / 2


def _local_to(observation, site):
    for i,x in enumerate(observation.coefficients):
        if x and any((i // 4**j) % 4 for j in range(observation.sites) if j != site):
            return False
    return True


@dataclass(frozen=True)
class State:
    """Positive functional represented by weighted preparation operators.

    omega(A) = sum w*tau(S^* A S) / sum w*tau(S^* S).
    Retains these factors; no arbitrary moment table is admitted as a state.
    This is a quantum-compatible probability postulate, not a physical proof.
    """
    factors: tuple  # (positive real Exact weight, Element preparation) entries
    density: Element = field(init=False, repr=False)
    normalization: E = field(init=False)

    def __post_init__(self):
        if type(self.factors) is not tuple or not self.factors:
            raise ValueError("nonempty immutable factor tuple required")
        if len(self.factors) > MAX_FACTORS:
            raise ResourceLimit("preparation factor limit")
        clean, total, density = [], ZERO, None
        for item in self.factors:
            if type(item) is not tuple or len(item) != 2 or type(item[1]) is not Element:
                raise TypeError("factor must be (weight, Element)")
            weight, word = scalar(item[0]), item[1]
            if sign(weight) <= 0:
                raise ValueError("factor weight must be real and positive")
            if density is None:
                density = Element.basis(word.sites)*0
            elif word.sites != density.sites:
                raise ValueError("factor site mismatch")
            # tau(S^* S) = sum |coefficient|^2 without multiplying matrices.
            norm = ZERO
            for c in word.coefficients:
                norm = scalar(norm + scalar(c.conjugate()*c))
            total = scalar(total + scalar(weight*norm))
            density = density + (word*word.dagger())*weight
            clean.append((weight, word))
        if sign(total) <= 0:
            raise ValueError("zero preparation has no normalized state")
        object.__setattr__(self, "factors", tuple(clean))
        object.__setattr__(self, "normalization", total)
        object.__setattr__(self, "density", density / total)

    @property
    def sites(self):
        return self.density.sites

    def expect(self, element):
        if type(element) is not Element or element.sites != self.sites:
            raise ValueError("expectation algebra mismatch")
        out = ZERO
        # Only matching monomials can contribute to the identity coefficient.
        for i,(x,y) in enumerate(zip(self.density.coefficients,element.coefficients)):
            if x and y:
                out = scalar(out + scalar(x*y)*dagger_sign(i,self.sites))
        return out

    def unitary(self, operation):
        if type(operation) is not Element or operation.sites != self.sites:
            raise ValueError("unitary algebra mismatch")
        identity = Element.basis(self.sites)
        if operation.dagger()*operation != identity or operation*operation.dagger() != identity:
            raise ValueError("operation is not unitary")
        return State(tuple((w,operation*s) for w,s in self.factors))

    def channel(self, operators):
        """Complete nonselective channel, with sum K^*K=I checked exactly."""
        if type(operators) is not tuple or not operators:
            raise ValueError("nonempty tuple of channel operators required")
        if len(operators)*len(self.factors) > MAX_FACTORS:
            raise ResourceLimit("channel factor limit")
        if any(type(k) is not Element or k.sites != self.sites for k in operators):
            raise ValueError("channel algebra mismatch")
        total = sum((k.dagger()*k for k in operators), Element.basis(self.sites)*0)
        if total != Element.basis(self.sites):
            raise ValueError("channel is not complete; no silent postselection")
        return State(tuple((w,k*s) for k in operators for w,s in self.factors))

    def branch(self, effect):
        """Projector outcome; probability zero is retained as (0,None)."""
        if type(effect) is not Element or effect.sites != self.sites:
            raise ValueError("effect algebra mismatch")
        if effect.dagger() != effect or effect*effect != effect:
            raise ValueError("selective update requires a projector")
        p = self.expect(effect)
        if sign(p) < 0 or sign(ONE-p) < 0:
            raise ArithmeticError("invalid outcome probability")
        if not p:
            return ZERO, None
        return p, State(tuple((w,effect*s) for w,s in self.factors))

    def joint(self, alice, bob):
        if self.sites != 2 or type(alice) is not Element or type(bob) is not Element:
            raise ValueError("two local observables required")
        if alice.sites != 2 or bob.sites != 2 or not _local_to(alice,0) or not _local_to(bob,1):
            raise ValueError("Alice/Bob must read their own sites")
        effects_a = {a:projector(alice,a) for a in (-1,1)}
        effects_b = {b:projector(bob,b) for b in (-1,1)}
        out = {}
        for a,ea in effects_a.items():
            for b,eb in effects_b.items():
                p = self.expect(ea*eb)
                if sign(p) < 0 or sign(ONE-p) < 0:
                    raise ArithmeticError("invalid joint probability")
                out[a,b] = p
        if sum(out.values(),ZERO) != ONE:
            raise ArithmeticError("joint distribution not normalized")
        return out

    def gram(self):
        basis = tuple(Element.basis(self.sites,i) for i in range(4**self.sites))
        return tuple(tuple(self.expect(a.dagger()*b) for b in basis) for a in basis)


def gns(state):
    """Construct finite quotient coordinates and check their exact Gram factor.

    Inner product is induced by omega(A^*B); positivity comes from State's
    preparation factors. This is the finite GNS construction, not a novel axiom.
    """
    if type(state) is not State:
        raise TypeError("expected State")
    gram = state.gram()
    rows, pivots = [list(r) for r in gram], []
    size = len(rows)
    for col in range(size):
        pivot = next((i for i in range(len(pivots),size) if rows[i][col]),None)
        if pivot is None:
            continue
        r = len(pivots)
        rows[r], rows[pivot] = rows[pivot], rows[r]
        d = rows[r][col]
        rows[r] = [scalar(v/d) for v in rows[r]]
        for i in range(size):
            if i != r and rows[i][col]:
                scale = rows[i][col]
                rows[i] = [scalar(v-scalar(scale*w)) for v,w in zip(rows[i],rows[r])]
        pivots.append(col)
    coords = tuple(tuple(r) for r in rows[:len(pivots)])
    for i in range(size):
        for j in range(size):
            value = ZERO
            for a,p in enumerate(pivots):
                for b,q in enumerate(pivots):
                    value = scalar(value+scalar(coords[a][i].conjugate()*gram[p][q]*coords[b][j]))
            if value != gram[i][j]:
                raise ArithmeticError("GNS Gram reconstruction failed")
    return dict(rank=len(pivots),basis=tuple(pivots),coordinates=coords,gram=gram)


def represent(element, quotient):
    """Left multiplication; externally supplied quotients need verify_gns."""
    size = 4**element.sites
    coords, basis = quotient["coordinates"], quotient["basis"]
    if len(quotient["gram"]) != size:
        raise ValueError("GNS algebra mismatch")
    columns = []
    for index in basis:
        word = element*Element.basis(element.sites,index)
        columns.append(tuple(scalar(sum((scalar(c*x) for c,x in zip(row,word.coefficients)),ZERO))
                             for row in coords))
    return tuple(tuple(columns[j][i] for j in range(len(basis))) for i in range(len(basis)))


def verify_gns(state, quotient):
    """Check a proposed quotient against the state without rerunning gns()."""
    try:
        if type(state) is not State or type(quotient) is not dict:
            return False
        size = 4**state.sites
        rank, basis = quotient["rank"], quotient["basis"]
        coords, gram = quotient["coordinates"], quotient["gram"]
        if type(rank) is not int or not 1 <= rank <= size:
            return False
        if type(basis) is not tuple or len(basis) != rank or len(set(basis)) != rank:
            return False
        if any(type(i) is not int or not 0 <= i < size for i in basis):
            return False
        if type(coords) is not tuple or len(coords) != rank:
            return False
        if any(type(row) is not tuple or len(row) != size or
               any(type(x) is not E for x in row) for row in coords):
            return False
        if gram != state.gram():
            return False
        if any(coords[a][b] != (ONE if a == j else ZERO)
               for a in range(rank) for j,b in enumerate(basis)):
            return False
        # Independent invertibility check for the selected Gram submatrix.
        core = [[gram[i][j] for j in basis] for i in basis]
        for k in range(rank):
            pivot = next((j for j in range(k,rank) if core[j][k]),None)
            if pivot is None:
                return False
            core[k],core[pivot] = core[pivot],core[k]
            for j in range(k+1,rank):
                f = scalar(core[j][k]/core[k][k])
                for t in range(k,rank):
                    core[j][t] = scalar(core[j][t]-scalar(f*core[k][t]))
        for i in range(size):
            for j in range(size):
                value = ZERO
                for a,p in enumerate(basis):
                    for b,q in enumerate(basis):
                        value = scalar(value+scalar(coords[a][i].conjugate()*gram[p][q]*coords[b][j]))
                if value != gram[i][j]:
                    return False
        return True
    except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError):
        return False


def mixture(items):
    """Declared convex mixing; weights must sum to one with no renormalization."""
    if type(items) is not tuple or not items or len(items) > MAX_FACTORS:
        raise ValueError("bounded nonempty mixture tuple required")
    total, factors = ZERO, []
    for item in items:
        if type(item) is not tuple or len(item) != 2 or type(item[1]) is not State:
            raise TypeError("use (weight, State) mixture entries")
        weight, state = scalar(item[0]), item[1]
        if sign(weight) <= 0:
            raise ValueError("mixture weights must be positive")
        total = scalar(total+weight)
        if len(factors)+len(state.factors) > MAX_FACTORS:
            raise ResourceLimit("mixture factor limit")
        for w,s in state.factors:
            factors.append((scalar(weight*w/state.normalization),s))
    if total != ONE:
        raise ValueError("mixture weights must sum to one")
    return State(tuple(factors))


def product_reference():
    """Chosen preparation K_A=+1, K_B=-1, expressed as two commuting cuts."""
    q = projector(local(2,0,"K"),1)*projector(local(2,1,"K"),-1)
    return State(((ONE,q),))


def interaction(c=INV_SQRT2, s=INV_SQRT2):
    """Proposed joint interaction U=c I-s R_A L_B, c^2+s^2=1."""
    c, s = scalar(c), scalar(s)
    if c.c or c.d or s.c or s.d or c*c+s*s != ONE:
        raise ValueError("interaction requires a real exact unit-circle pair")
    return Element.basis(2)*c - (local(2,0,"R")*local(2,1,"L"))*s


def bell_preparation():
    return product_reference().unitary(interaction())


def bell_settings():
    a0, a1 = local(2,0,"K"), local(2,0,"L")
    b0 = observable(2,1,-INV_SQRT2,-INV_SQRT2)
    b1 = observable(2,1,-INV_SQRT2,INV_SQRT2)
    return a0,a1,b0,b1


def chsh(settings):
    if type(settings) is not tuple or len(settings) != 4:
        raise ValueError("four observables required")
    a0,a1,b0,b1 = settings
    for site, obs in ((0,a0),(0,a1),(1,b0),(1,b1)):
        if type(obs) is not Element or obs.sites != 2 or not _local_to(obs,site):
            raise ValueError("CHSH locality mismatch")
        projector(obs,1)
    return a0*(b0+b1) + a1*(b0-b1)


def tsirelson_sos(settings):
    """Positive squares prove 2sqrt(2)I-S, not just an observed maximum."""
    s = chsh(settings)
    a0,a1,b0,b1 = settings
    d0 = a0-(b0+b1)*INV_SQRT2
    d1 = a1-(b0-b1)*INV_SQRT2
    lhs = Element.basis(2)*E(b=2)-s
    rhs = (d0.dagger()*d0+d1.dagger()*d1)*INV_SQRT2
    if lhs != rhs:
        raise ArithmeticError("Tsirelson sum-of-squares identity failed")
    return d0,d1
