"""Bounded cubic energy adapter for NT/TLM response data and photonic control.

Exact normalized coefficients describe a declared model, not a fitted material.
The shared EMK product and optical response engine are reused. This is not a
second jet algebra, a Hamiltonian identification, or a dynamic thermal solver.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from math import isqrt
import re

from native_relational_qc.emk_tensor import EMKBlock
from .photonic_io import fingerprint
from .photonic_response import PHASE_ORDER, compose_response, optical_response
from .photonic_observer import _read_packet, observer_packet


def _q(value):
    if type(value) not in (int, Q):
        raise TypeError("exact int/Fraction coefficients required")
    value = Q(value)
    if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > 4096:
        raise ValueError("constitutive coefficient bit limit")
    return value


def _vector(values, size):
    if not isinstance(values, (tuple, list)) or len(values) != size:
        raise ValueError(f"exact vector of length {size} required")
    return tuple(_q(v) for v in values)


def _matrix(rows, height, width=None):
    if not isinstance(rows, (tuple, list)) or len(rows) != height:
        raise ValueError(f"matrix needs {height} rows")
    if not isinstance(rows[0], (tuple, list)):
        raise ValueError("matrix rows required")
    width = len(rows[0]) if width is None else width
    if not 1 <= width <= 32:
        raise ValueError("matrix needs 1..32 columns")
    return tuple(_vector(row, width) for row in rows)


def _mul(a, b):
    if len(a[0]) != len(b):
        raise ValueError("matrix dimensions do not compose")
    return tuple(tuple(_q(sum(x*y for x,y in zip(row,col))) for col in zip(*b)) for row in a)


def _l1(rows):
    return _q(sum(abs(v) for row in rows for v in row))


def _block(h):
    return EMKBlock((h[0][0]+h[1][1])/2, (h[0][0]-h[1][1])/2, 0, h[0][1])


def _radial(value):
    if value.b or value.c or value.d:
        raise ArithmeticError("rational response left its declared carrier")
    return _q(value.a)


@dataclass(frozen=True)
class CubicEnergy:
    """U(q)=g.q + q.H0.q/2 + T[q,q,q]/6 in one normalized affine chart.

    hessian=(a,b,c), third=(U000,U001,U011,U111). Symmetry/integrability
    follow from this declared polynomial. origin=(S0,V0) is used only by the
    thermodynamic response adapter. The generic material chart is q=(s,v).
    """
    hessian: tuple
    third: tuple = (0, 0, 0, 0)
    gradient: tuple = (0, 0)
    origin: tuple = (1, 1)

    def __post_init__(self):
        for key, size in (("hessian",3),("third",4),("gradient",2),("origin",2)):
            object.__setattr__(self,key,_vector(getattr(self,key),size))

    def energy(self, point):
        s,v = _vector(point,2); a,b,c = self.hessian; d,e,f,g = self.third
        return _q(self.gradient[0]*s+self.gradient[1]*v+(a*s*s+2*b*s*v+c*v*v)/2
                  +(d*s**3+3*e*s*s*v+3*f*s*v*v+g*v**3)/6)

    def force(self, point):
        s,v = _vector(point,2); a,b,c = self.hessian; d,e,f,g = self.third
        return (_q(self.gradient[0]+a*s+b*v+(d*s*s+2*e*s*v+f*v*v)/2),
                _q(self.gradient[1]+b*s+c*v+(e*s*s+2*f*s*v+g*v*v)/2))

    def at(self, point):
        s,v = _vector(point,2); a,b,c = self.hessian; d,e,f,g = self.third
        a,b,c = _q(a+d*s+e*v),_q(b+e*s+f*v),_q(c+f*s+g*v)
        delta = _q(a*c-b*b)
        if a <= 0 or delta <= 0:
            raise ValueError("positive energy Hessian required at the operating point")
        h = ((a,b),(b,c))
        inverse = ((c/delta,-b/delta),(-b/delta,a/delta))
        return h,_matrix(inverse,2,2),delta

    def specification(self):
        return dict(kind="NORMALIZED_CUBIC_ENERGY_2D", evidence_class="DECLARED_MODEL",
                    **{k:[str(v) for v in getattr(self,k)]
                       for k in ("hessian","third","gradient","origin")})


def response_record(model, point=(0,0)):
    """NT six responses, ordinary first derivatives and selected EMK curvature.

    First derivatives are the first response layer in the declared flat
    six-component frame. Higher covariant slots are not regenerated here.
    """
    s,v = _vector(point,2); h,inv,delta = model.at((s,v))
    a,b,c = h[0][0],h[0][1],h[1][1]
    S,V = model.origin[0]+s,model.origin[1]+v
    T,minusP = model.force((s,v)); P = -minusP
    if min(S,V,T) <= 0:
        raise ValueError("thermodynamic response requires positive S,V,T")
    values = dict(lambdaP=-S*delta/c, lambdaV=-S*a, lambdaS=-V*c,
                  zT=-V*delta/a, zS=P/c, lambdaT=P*a/delta)
    d,e,f,g = model.third; dh = (((d,e),(e,f)),((e,f),(f,g)))
    derivatives = {name:[] for name in values}
    for j in range(2):
        da,db,dc = dh[j][0][0],dh[j][0][1],dh[j][1][1]
        dd = da*c+a*dc-2*b*db; ds,dv = int(j==0),int(j==1); dp = -h[1][j]
        terms = (-ds*delta/c-S*dd/c+S*delta*dc/c**2,
                 -ds*a-S*da, -dv*c-V*dc,
                 -dv*delta/a-V*dd/a+V*delta*da/a**2,
                 dp/c-P*dc/c**2, (dp*a+P*da)/delta-P*a*dd/delta**2)
        for name,value in zip(values,terms): derivatives[name].append(_q(value))
    # NT-3: F_sv = -[H^-1 H_s, H^-1 H_v]/4, using the EXISTING EMK product.
    inverse_block = _block(inv)
    x,y = (inverse_block*_block(jet) for jet in dh)
    xy,yx = x*y,y*x
    curvature = EMKBlock(*((right-left)/4 for left,right in zip(xy.coefficients,yx.coefficients)))
    kappa = _radial((_block(h)*curvature).matrix()[0][1])/delta
    return dict(hessian=h, inverse=inv, hessian_first=dh, determinant=delta,
                responses={k:_q(v) for k,v in values.items()},
                response_first={k:tuple(v) for k,v in derivatives.items()},
                thermal=dict(Cv=T/a,Cp=T*c/delta,Ks=V*c,Kt=V*delta/a),
                em=dict(epsilon_B=1/a,epsilon_H=c/delta,mu_D=1/c,mu_E=a/delta),
                curvature_emk=tuple(_radial(v) for v in curvature.coefficients),
                selected_response_curvature=_q(kappa))


def phase_control_response(model, point, phase_per_state, force_per_control, *, held_coordinate=None):
    """B = L H^-1 A; optionally hold one material coordinate fixed.

    L has all five phase rows, including reference; A maps normalized controls
    to conjugate forces. The two-channel energy response is not a Hamiltonian.
    """
    h,chi,_ = model.at(point)
    phase = _matrix(phase_per_state,5,2); drive = _matrix(force_per_control,2)
    if held_coordinate is not None:
        if type(held_coordinate) is not int or held_coordinate not in (0,1):
            raise ValueError("held coordinate must be 0, 1 or None")
        free = 1-held_coordinate
        chi = tuple(tuple(Q(1)/h[free][free] if i==j==free else Q(0)
                          for j in range(2)) for i in range(2))
    return _mul(_mul(phase,chi),drive)


def coupled_optical_response(model, point, phase_steps, phase_per_state, force_per_control,
                             *, measurements="reference", reference_steps=0, held_coordinate=None):
    b = phase_control_response(model,point,phase_per_state,force_per_control,held_coordinate=held_coordinate)
    response = optical_response(phase_steps,measurements=measurements,reference_steps=reference_steps)
    return dict(phase_per_control=b,measurement_per_control=compose_response(response["jacobian"],b),
                measurement_labels=response["labels"],evidence_class="DECLARED_MODEL")


def patch_bound(model, point, *, patch_radius, force_radius):
    """Rational strong-convexity and inverse-response remainder bound on a ball.

    Force radius bounds ||delta f||_2, not voltage or dissipated heater power.
    Existence/uniqueness is inside this declared ball, not global for a cubic.
    """
    point = _vector(point,2); R,B = _q(patch_radius),_q(force_radius)
    if R <= 0 or B < 0: raise ValueError("positive patch radius and nonnegative force radius required")
    h,_,delta = model.at(point)
    m0 = _q(delta/(h[0][0]+h[1][1]))
    d,e,f,g = model.third
    lipschitz = _q(abs(d)+3*abs(e)+3*abs(f)+abs(g))
    m = _q(m0-lipschitz*R)
    if m <= 0: raise ValueError("patch positivity not established by this sufficient bound")
    if B >= m*R: raise ValueError("force ball must fit strictly inside the certified patch")
    displacement = _q(B/m)
    remainder = _q(lipschitz*displacement**2/(2*m0))
    return dict(patch_radius=R,force_radius=B,point_lower_eigenvalue=m0,
                hessian_lipschitz=lipschitz,patch_lower_eigenvalue=m,
                state_displacement_bound=displacement,inverse_linearization_remainder=remainder)


def phase_observer_bounds(model, point, phase_per_state, packet, *, patch_radius, force_radius):
    """Generate two v0.13 bounds for the actual phase-state target packet.

    Does not fill sensor noise, calibration drift or target budget. The
    optical bound includes trigonometric nonlinearity even for quadratic U.
    The composed force-to-reading remainder is reported separately: it must
    not be substituted for a bound on an actual nonlinear phase target.
    """
    _read_packet(packet)
    if packet["state_order"] != list(PHASE_ORDER):
        raise ValueError("five phase coordinates without extra nuisance columns required")
    response = optical_response(tuple(packet["phase_steps"]),measurements=packet["measurement_family"],
                                reference_steps=packet["reference_steps"])
    if list(response["labels"]) != packet["measurement_labels"]:
        raise ValueError("measurement labels differ from the optical contract")
    phase = _matrix(phase_per_state,5,2)
    def scales(name):
        values = packet["scales"][name]
        if not isinstance(values,list) or not 1 <= len(values) <= 128:
            raise ValueError("bounded scale list required")
        if any(not isinstance(x,str) or len(x)>2500 or
               re.fullmatch(r"[1-9][0-9]*(?:/[1-9][0-9]*)?",x) is None for x in values):
            raise ValueError("positive rational scale strings required")
        return tuple(_q(Q(x)) for x in values)
    dx,dy,dt = scales("state"),scales("reading"),scales("target")
    if len(dx)!=5 or len(dy)!=len(response["labels"]) or min(*dx,*dy)<=0:
        raise ValueError("positive matching normalization required")
    if packet["unit"] not in tuple(f"exchange_{i}" for i in range(6)):
        raise ValueError("unknown exchange unit")
    expected = observer_packet(tuple(packet["phase_steps"]),target=packet["target_name"],
                               measurements=packet["measurement_family"],reference_steps=packet["reference_steps"],
                               state_scales=dx,reading_scales=dy,target_scales=dt,unit_index=int(packet["unit"][-1]))
    if expected["packet_sha256"] != packet["packet_sha256"]:
        raise ValueError("packet does not match the current exact optical and normalization contract")
    bound = patch_bound(model,point,patch_radius=patch_radius,force_radius=force_radius)
    qmax = bound["state_displacement_bound"]
    ell = _l1(phase)
    phase_l1 = _q(ell*qmax)
    state_bound = _q(sum(abs(v)/dx[i] for i,row in enumerate(phase) for v in row)*qmax)
    count = len(dy); root_count = isqrt(count)+(isqrt(count)**2 < count)
    optical_remainder = _q(2*root_count*phase_l1**2/min(dy))
    # Each ideal optical probability has |d p / d phi_i| <= 2 globally.
    composed_remainder = _q(optical_remainder+2*root_count*ell*
                            bound["inverse_linearization_remainder"]/min(dy))
    specification = dict(model=model.specification(),point=[str(v) for v in _vector(point,2)],
                         phase_per_state=[[str(v) for v in row] for row in phase],
                         patch_radius=str(bound["patch_radius"]),force_radius=str(bound["force_radius"]),
                         observer_packet_sha256=packet["packet_sha256"])
    return dict(schema="native-constitutive-observer-bound-v1",evidence_class="DECLARED_MODEL_BOUND",
                specification=specification,specification_sha256=fingerprint(specification),
                patch=bound,phase_displacement_l1_bound=phase_l1,
                observer_bounds=dict(state_norm_bound=state_bound,nonlinear_remainder_bound=optical_remainder),
                composed_force_to_reading_remainder=composed_remainder,
                assumptions=["normalized affine energy chart", "static conjugate-force equilibrium in the certified ball",
                             "constant declared material-state to phase map", "existing ideal lossless optical word"],
                measured_records=0,calibration_accepted=False,hardware_submitted=False)


def harmonic_phase_noise(model, phase_per_state, *, thermal_scale):
    """Classical full-space quadratic Gibbs covariance, projected to phases.

    thermal_scale is the declared normalized k_B T. No bath dynamics, noise
    spectrum, quantum FDT or nonlinear Gibbs law is inferred from this API.
    """
    if any(model.third): raise ValueError("exact harmonic covariance requires a quadratic energy")
    scale = _q(thermal_scale)
    if scale <= 0: raise ValueError("positive normalized thermal scale required")
    _,chi,_ = model.at((0,0)); phase = _matrix(phase_per_state,5,2)
    state_cov = tuple(tuple(_q(scale*v) for v in row) for row in chi)
    covariance = _mul(_mul(phase,state_cov),tuple(zip(*phase)))
    variance = _q(covariance[0][0]+covariance[1][1]-2*covariance[0][1])
    return dict(state_covariance=state_cov,phase_covariance=covariance,exchange_angle_variance=variance,
                evidence_class="DECLARED_CLASSICAL_HARMONIC_MODEL")
