"""Tomographic phase/seam encoding, retained classical ledger, proved transports.

This adds a selected mixed-state embedding, not a full operational equivalence.
The original deterministic phase readout is not a one-copy quantum readout.
"""
from dataclasses import dataclass
from fractions import Fraction as F

from native_relational_qc.exact import Exact, IMAG
from native_relational_qc.cyclotomic64 import Cyclotomic64 as C, ZERO, ONE, ZETA
from .model import Cell, Config, Operation, ResourceLimit, verify_history
from .joint import Element, basis_product, dagger_sign

MAX_BITS = 4096
GRIDS = (4, 8, 16, 32, 64)


def scalar(value):
    if type(value) not in (int, F, Exact, C):
        raise TypeError("exact coefficient required")
    out = C.coerce(value)
    if out.max_bits > MAX_BITS:
        raise ResourceLimit("encoding coefficient bit limit")
    return out


@dataclass(frozen=True)
class Op64:
    """The same two-site EMK algebra, with the existing 64th-root field."""
    coefficients: tuple

    def __post_init__(self):
        if type(self.coefficients) is not tuple or len(self.coefficients) != 16:
            raise ValueError("two-site operator needs 16 coefficients")
        object.__setattr__(self,"coefficients",tuple(scalar(x) for x in self.coefficients))

    @classmethod
    def basis(cls,index=0):
        if type(index) is not int or not 0 <= index < 16:
            raise ValueError("basis index out of range")
        return cls(tuple(ONE if i==index else ZERO for i in range(16)))

    @classmethod
    def from_joint(cls,value):
        if type(value) is not Element or value.sites != 2:
            raise ValueError("two-site v0.2 element required")
        return cls(value.coefficients)

    def _other(self,x):
        return x if type(x) is Op64 else Op64.basis()*scalar(x)

    def __add__(self,x):
        x=self._other(x)
        return Op64(tuple(scalar(a+b) for a,b in zip(self.coefficients,x.coefficients)))

    __radd__=__add__

    def __neg__(self):
        return Op64(tuple(-x for x in self.coefficients))

    def __sub__(self,x):
        return self+-self._other(x)

    def __rsub__(self,x):
        return self._other(x)+-self

    def __mul__(self,x):
        if type(x) is not Op64:
            x=scalar(x)
            return Op64(tuple(scalar(a*x) for a in self.coefficients))
        out=[ZERO]*16
        for i,a in enumerate(self.coefficients):
            if not a: continue
            for j,b in enumerate(x.coefficients):
                if not b: continue
                k,s=basis_product(i,j,2)
                out[k]=scalar(out[k]+scalar(a*b)*s)
        return Op64(tuple(out))

    __rmul__=__mul__

    def __truediv__(self,x):
        return self*scalar(scalar(x).inverse())

    def dagger(self):
        return Op64(tuple(x.conjugate()*dagger_sign(i,2) for i,x in enumerate(self.coefficients)))

    def tau(self):
        return self.coefficients[0]

    def expect(self,observable):
        """Treat self as normalized density element D, omega(A)=tau(D A)."""
        if type(observable) is Element:
            observable=Op64.from_joint(observable)
        if type(observable) is not Op64:
            raise TypeError("operator observable required")
        out=ZERO
        for i,(x,y) in enumerate(zip(self.coefficients,observable.coefficients)):
            if x and y:
                out=scalar(out+scalar(x*y)*dagger_sign(i,2))
        return out

    def to_dict(self):
        return {"basis":"two-site I,K,R,RK; site 0 fastest",
                "coefficients":[x.to_dict() for x in self.coefficients]}


I=Op64.basis()
XA,YA,ZA=Op64.basis(3),Op64.basis(2)*IMAG,Op64.basis(1)
XB,YB,ZB=Op64.basis(12),Op64.basis(8)*IMAG,Op64.basis(4)
PAIRS=((XA,YA),(XB,YB),(XA*ZB,-YA*ZB),(ZA*XB,-ZA*YB))
SEAM=ZA*ZB
ROOTS=tuple(ZETA**k for k in range(64))


def _grid(grid):
    if type(grid) is not int or grid not in GRIDS:
        raise ValueError("encoding supports grids 4,8,16,32,64 exactly")


def _rational(value):
    value=scalar(value)
    if any(value.coefficients[1:]):
        raise ValueError("expected a rational field element")
    return value.coefficients[0]


def phase_pair(grid,r):
    _grid(grid)
    if type(r) is not int:
        raise TypeError("integer phase index required")
    z=ROOTS[(r*(64//grid))%64]
    return (z+z.conjugate())*F(1,2),(z-z.conjugate())*Exact(c=F(-1,2))


def density(phases,gamma,grid=64):
    """Chosen five-component mixture; injective in phases and positive gamma."""
    _grid(grid)
    if type(phases) is not tuple or len(phases)!=4 or any(type(r) is not int for r in phases):
        raise ValueError("four integer phase indices required")
    if type(gamma) not in (int,F):
        raise TypeError("rational gamma required")
    gamma=F(gamma)
    if gamma<=0:
        raise ValueError("gamma must be positive")
    scalar(gamma)
    t=(gamma-1)/(gamma+1)
    out=I+SEAM*F(t,5)
    for r,(p,q) in zip(phases,PAIRS):
        u,v=phase_pair(grid,r)
        out=out+(p*u+q*v)/5
    return out


def positive_factors(phases,gamma,grid=64):
    """Six positive-square factors whose normalization is exactly one."""
    # Validate the full admitted chart and coefficient bounds first.
    density(phases,gamma,grid)
    t=(F(gamma)-1)/(F(gamma)+1)
    factors=[]
    for r,(p,q) in zip(phases,PAIRS):
        u,v=phase_pair(grid,r)
        factors.append((F(2,5),(I+p*u+q*v)/2))
    factors.extend(((F(1+t,5),(I+SEAM)/2),(F(1-t,5),(I-SEAM)/2)))
    return tuple(factors)


def decode(code,grid=64):
    """Exact tomography oracle: not a physical one-shot decoding procedure."""
    _grid(grid)
    if type(code) is not Op64 or code.dagger()!=code or code.tau()!=ONE:
        raise ValueError("invalid encoded density element")
    t=_rational(code.expect(SEAM)*5)
    if not -1<t<1:
        raise ValueError("seam reading is outside positive-gamma chart")
    gamma=(1+t)/(1-t)
    phases=[]
    for p,q in PAIRS:
        z=scalar(code.expect(p)*5+code.expect(q)*Exact(c=5))
        exponent=next((i for i in range(grid) if ROOTS[i*(64//grid)]==z),None)
        if exponent is None:
            raise ValueError("readings are not on the declared phase grid")
        phases.append(exponent)
    phases=tuple(phases)
    # Reject extra moments or a wrong component weight, not just read nine slots.
    if density(phases,gamma,grid)!=code:
        raise ValueError("operator is outside the encoded family")
    return phases,gamma


def binary_readout(code,observable):
    """One binary projective measurement, distinct from the tomography oracle."""
    decode(code,64)  # all supported subgrids lie inside this admitted family
    if type(observable) is Element:
        observable=Op64.from_joint(observable)
    if type(observable) is not Op64 or observable.dagger()!=observable or observable*observable!=I:
        raise ValueError("self-adjoint involution required")
    mean=code.expect(observable)
    out={s:scalar((ONE+mean*s)/2) for s in (-1,1)}
    if any(p.real_sign()<0 for p in out.values()):
        raise ArithmeticError("invalid probability")
    return out


@dataclass(frozen=True)
class Bridge:
    """Quantum code plus classical provenance, with no memory-compression claim."""
    code: Op64
    config: Config
    initial_lifts: tuple
    operations: tuple


def encode(cell):
    if type(cell) is not Cell or not verify_history(cell):
        raise ValueError("valid source cell history required")
    _grid(cell.config.grid)
    return Bridge(density(cell.phases,cell.gamma,cell.config.grid),cell.config,
                  cell.initial.lifts,tuple(e.operation for e in cell.events))


def recover(bridge):
    """Reconstruct the deterministic cell using tomography plus retained tape."""
    if type(bridge) is not Bridge or type(bridge.config) is not Config:
        raise TypeError("Bridge required")
    if type(bridge.operations) is not tuple:
        raise ValueError("immutable operation tape required")
    if len(bridge.operations)>bridge.config.max_events:
        raise ResourceLimit("bridge event limit")
    phases,gamma=decode(bridge.code,bridge.config.grid)
    cell=Cell.start(bridge.initial_lifts,config=bridge.config,gamma=gamma)
    for op in bridge.operations:
        cell=cell.apply(op)
    if cell.phases!=phases:
        raise ValueError("code and retained tape disagree")
    return cell


def verify_bridge(bridge):
    try:
        return encode(recover(bridge))==bridge
    except (ValueError,TypeError,AttributeError):
        return False


def ledger_update(bridge,operations):
    """Classically replay known inputs and re-encode. This is NOT a quantum gate."""
    if type(operations) is not tuple:
        raise TypeError("immutable operation word required")
    cell=recover(bridge)
    for op in operations:
        cell=cell.apply(op)
    return encode(cell)


class UnsupportedTransport(ValueError):
    pass


def transport_unitary(operations,grid):
    """Only declared state-independent intertwiners; no reprepare fallback."""
    _grid(grid)
    if type(operations) is not tuple or not operations or any(type(o) is not Operation for o in operations):
        raise ValueError("nonempty immutable operation word required")
    if len(operations)==1 and operations[0].kind=="pair_shift":
        a,b,d=operations[0].args
        if (a,b) in ((0,2),(2,0)):
            z=ROOTS[((d if a==0 else -d)*(64//grid))%64]
            axis=ZA
        elif (a,b) in ((1,3),(3,1)):
            z=ROOTS[((d if a==1 else -d)*(64//grid))%64]
            axis=ZB
        else:
            raise UnsupportedTransport("unproved pair-shift pairing")
        # diag(1,exp(i phi)); avoids requiring a 128th root for half angles.
        return (I+axis)/2+((I-axis)/2)*z
    canonical=(Operation("swap",(0,1)),Operation("swap",(2,3)))
    if operations in (canonical,canonical[::-1]):
        return (I+XA*XB+YA*YB+ZA*ZB)/2
    raise UnsupportedTransport("no certified channel for this source operation word")


@dataclass(frozen=True)
class Transport:
    before: Bridge
    after: Bridge
    operations: tuple
    unitary: Op64


def compile_transport(bridge,operations):
    recover(bridge)  # validate source before selecting the compiled interface
    u=transport_unitary(operations,bridge.config.grid)
    after=ledger_update(bridge,operations)
    if u.dagger()*u!=I or u*u.dagger()!=I:
        raise ArithmeticError("transport is not unitary")
    if u*bridge.code*u.dagger()!=after.code:
        raise ArithmeticError("transport does not intertwine the encoding")
    return Transport(bridge,after,operations,u)


def verify_transport(certificate):
    try:
        if type(certificate) is not Transport:
            return False
        before,after=certificate.before,certificate.after
        if not verify_bridge(before) or not verify_bridge(after):
            return False
        u=transport_unitary(certificate.operations,before.config.grid)
        if u!=certificate.unitary or ledger_update(before,certificate.operations)!=after:
            return False
        return u.dagger()*u==I and u*before.code*u.dagger()==after.code
    except (ValueError,TypeError,AttributeError):
        return False


def channel_obstruction():
    """Exact distinguishability witness against compiling one balanced cut."""
    config=Config(grid=64,sector=1)
    a=Cell.start(config=config)
    b=Cell.start((16,-16,0,0),config=config)
    op=Operation("pair_cut",(0,2,0))
    da,db=encode(a).code,encode(b).code
    oa,ob=encode(a.apply(op)).code,encode(b.apply(op)).code
    # Before: rho_a-rho_b=(X_A-Y_A+X_B+Y_B)/20.
    delta=(da-db)/4
    expected=(XA-YA+XB+YB)/20
    if delta!=expected:
        raise ArithmeticError("obstruction source identity failed")
    before_distance=C(Exact(b=F(1,10)))  # sqrt(2)/10, proved in the note
    after_readout_tv=(oa.expect(PAIRS[2][0])-ob.expect(PAIRS[2][0]))/2
    if after_readout_tv!=C(F(1,5)) or (after_readout_tv-before_distance).real_sign()<=0:
        raise ArithmeticError("obstruction witness failed")
    return dict(initial_lifts=(a.state.lifts,b.state.lifts),
                final_lifts=(a.apply(op).state.lifts,b.apply(op).state.lifts),
                input_trace_distance=before_distance,
                output_binary_tv=after_readout_tv,
                scope="no single deterministic quantum channel implements this cut on this entire encoded family")
