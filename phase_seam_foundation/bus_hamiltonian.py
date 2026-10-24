"""Centered finite-bus Hamiltonian targets and conditional unitary error bounds.

Reuses the collaborator's unchanged flat cyclotomic field. No new amplitude
backend, material fit or measured coupling is supplied. See BUS_HAMILTONIAN.md.
"""
from dataclasses import dataclass
from fractions import Fraction as Q
from math import isqrt

from native_relational_qc.cyclotomic_pow2 import field_of_order, _pi_bounds
from .model import ResourceLimit

DIMENSIONS = (2, 4, 8, 16, 32, 64)


def _int(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low},{high}]")
    return value


def _dimension(d):
    if type(d) is not int or d not in DIMENSIONS:
        raise ValueError("Hamiltonian matrix dimension must be 2,4,8,16,32,64")
    return d


def _bound(value):
    if type(value) not in (int, Q):
        raise ValueError("bounds must be explicit nonnegative rationals")
    value = Q(value)
    if value < 0:
        raise ValueError("negative error bound")
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > 4096:
        raise ResourceLimit("error-bound coefficient cap")
    return value


def _field(d):
    _dimension(d)
    return field_of_order(max(8, 2*d))


def centered_spectrum(d):
    _dimension(d)
    return tuple(Q(2*k-d+1,2) for k in range(d))


def fourier_matrix(d):
    """F[j,k]=exp(-2*pi*i*j*k/d)/sqrt(d); X=F Z F*."""
    field = _field(d); n = d.bit_length()-1
    scale = field.ORDER//d
    norm = (field(Q(1,2**(n//2))) if n%2 == 0
            else field.sqrt2()/2**((n+1)//2))
    return tuple(tuple(norm*field.root(-scale*j*k) for k in range(d)) for j in range(d))


def _spectral_matrix(values, axis):
    """Export a specified diagonal spectrum in the Q or Fourier/P basis."""
    d=len(values); field=_field(d)
    if axis == "q":
        return tuple(tuple(field(values[j]) if j==k else field() for k in range(d)) for j in range(d))
    if axis != "p":
        raise ValueError("generator axis must be q or p")
    scale=field.ORDER//d
    row=tuple(sum((field(value)*field.root(scale*h*k) for k,value in enumerate(values)),field())/d
              for h in range(d))
    return tuple(tuple(row[(k-j)%d] for k in range(d)) for j in range(d))


def generator_matrix(d, axis):
    """Q0=diag(k-(d-1)/2), P0=F Q0 F*: dimensionless Hermitian targets."""
    return _spectral_matrix(centered_spectrum(d), axis)


def centered_kick_matrix(d, axis, steps, *, sign=1):
    """Nominal exp(i*2*pi*steps/d*sign*G_axis), including its local phase.

    The centered half-integer spectrum may require Q(zeta_(2d)). The complete
    closed rectangle returns to the earlier uncentered gate exactly.
    """
    field=_field(d); _int(steps,"kick strength",-4096,4096)
    if type(sign) is not int or sign not in (-1,1):
        raise ValueError("data eigenvalue must be +1 or -1")
    scale=field.ORDER//(2*d)
    if axis == "q":
        return tuple(tuple(field.root(scale*steps*sign*(2*j-d+1)) if j==k else field()
                           for k in range(d)) for j in range(d))
    if axis != "p":
        raise ValueError("generator axis must be q or p")
    phase=field.root(-scale*steps*sign*(d-1))
    return tuple(tuple(phase if j==(k+sign*steps)%d else field() for k in range(d)) for j in range(d))


@dataclass(frozen=True)
class BusDesign:
    dimension: int = 8
    a: int = 1
    b: int = 1
    echo: bool = False

    def __post_init__(self):
        d=_dimension(self.dimension)
        _int(self.a,"signed x strength",-d//2,d//2)
        _int(self.b,"signed z strength",-d//2,d//2)
        if type(self.echo) is not bool:
            raise ValueError("echo must be boolean")

    def schedule(self):
        """Execution-order dispersive/Fourier targets; no drive voltages."""
        half=[]
        for site,n,axis in ((0,self.a,"p"),(1,self.b,"q"),(0,-self.a,"p"),(1,-self.b,"q")):
            if axis=="p": half.append(dict(kind="fourier_inverse"))
            half.append(dict(kind="dispersive",data_site=site,area_pi=Q(2*n,self.dimension)))
            if axis=="p": half.append(dict(kind="fourier"))
        flips=[dict(kind="data_x",data_site=0),dict(kind="data_x",data_site=1)]
        return half+flips+half+flips if self.echo else half

    def resources(self):
        d=self.dimension; repeats=2 if self.echo else 1
        invariant=(4*self.a*self.b*repeats)%d
        return dict(dimension=d,field_order=max(8,2*d),
                    generator_norm=Q(d-1,2),
                    conditional_interactions=4*repeats,bus_fourier_transforms=4*repeats,
                    local_echo_flips=4 if self.echo else 0,
                    theta_pi=Q(2*self.a*self.b*repeats,d),
                    nonlocal_phase_modulus_d=invariant,
                    cz_equivalent=invariant==d//2,
                    conditional_time_at_unit_norm_rate_in_pi=Q(2*repeats*(abs(self.a)+abs(self.b))*(d-1),d),
                    cost_scope="sequential conditional interactions at norm(H)/hbar<=G; time coefficient times pi/G; Fourier/local gates excluded",
                    physical_couplings_assumed=True,physical_device_built=False)


def matched_area_sensitivity(design):
    """Exact first derivatives for a BARE loop with matched inverse errors.

    W(alpha+e,beta+f) W(alpha,beta)* = I + i e K_alpha + i f K_beta + O(e,f)^2.
    Alpha is the integrated P angle, beta the Q angle, both in radians.
    K_alpha is diagonal in the P basis; K_beta in Q. They are not jointly
    diagonal and their eigenvalues must not be added as a joint spectrum.
    """
    if type(design) is not BusDesign or design.echo:
        raise ValueError("matched derivative certificate requires a bare BusDesign")
    d=design.dimension; a,b=design.a,design.b; blocks=[]
    for data in range(4):
        s,t=1-2*(data&1),1-2*(data>>1)
        ka=tuple(s*(p-((p-b*t)%d)) for p in range(d))
        kb=tuple(t*(((k+a*s)%d)-k) for k in range(d))
        blocks.append(dict(data=data,k_alpha_p_basis=ka,k_beta_q_basis=kb,
                           alpha_trace=sum(ka),beta_trace=sum(kb)))
    return dict(branches=blocks,
                alpha_operator_norm=max(abs(v) for x in blocks for v in x["k_alpha_p_basis"]),
                beta_operator_norm=max(abs(v) for x in blocks for v in x["k_beta_q_basis"]),
                first_order_bus_independent_alpha=all(len(set(x["k_alpha_p_basis"]))==1 for x in blocks),
                first_order_bus_independent_beta=all(len(set(x["k_beta_q_basis"]))==1 for x in blocks))


def sensitivity_matrix(design, data, axis):
    _int(data,"data branch",0,3)
    response=matched_area_sensitivity(design)["branches"][data]
    if axis=="alpha":return _spectral_matrix(response["k_alpha_p_basis"],"p")
    if axis=="beta":return _spectral_matrix(response["k_beta_q_basis"],"q")
    raise ValueError("sensitivity axis must be alpha or beta")


def implementation_bound(design, *, area_bounds, fourier_bounds, flip_bounds,
                         residual_action_bound):
    """Conservative all-state closed-system bound; every input is an assumption.

    area_bounds: absolute integrated-angle errors, radians, per interaction.
    fourier/flip_bounds: operator-norm unitary implementation error per gate.
    residual_action_bound: integral norm(delta H)/hbar dt for other bounded
    Hamiltonian errors, without double-counting the specified gate errors.
    No loss, Lindblad rates, stochastic confidence or fitted data inferred.
    """
    if type(design) is not BusDesign:
        raise ValueError("validated BusDesign required")
    r=design.resources()
    def bounds(values,n):
        if not isinstance(values,(tuple,list)) or len(values)!=n:
            raise ValueError("one explicit bound per scheduled operation required")
        return tuple(_bound(x) for x in values)
    areas=bounds(area_bounds,r["conditional_interactions"])
    transforms=bounds(fourier_bounds,r["bus_fourier_transforms"])
    flips=bounds(flip_bounds,r["local_echo_flips"])
    residual=_bound(residual_action_bound)
    area=r["generator_norm"]*sum(areas)
    total=area+sum(transforms)+sum(flips)+residual
    return dict(status="CONDITIONAL_CLOSED_SYSTEM_BOUND",pulse_area_contribution=area,
                raw_operator_bound=total,unitary_operator_error_bound=min(Q(2),total),
                reduced_data_trace_distance_bound=min(Q(1),total),
                half_diamond_distance_bound=min(Q(1),total),
                channel_bound_requires_fixed_bus_state_independent_of_data_input=True,
                inputs_are_declared_bounds=True,calibration_accepted=False,
                loss_or_dissipative_noise_covered=False,hardware_submitted=False)


def least_area_cz_design(d, *, echo=False):
    """Exhaustive integer strength choice in this schedule, no architecture optimum."""
    _dimension(d)
    if type(echo) is not bool:raise ValueError("echo must be boolean")
    candidates=(BusDesign(d,a,b,echo) for a in range(1,d//2+1) for b in range(1,d//2+1))
    admitted=[x for x in candidates if x.resources()["cz_equivalent"]]
    if not admitted:return None
    return min(admitted,key=lambda x:(abs(x.a)+abs(x.b),max(abs(x.a),abs(x.b)),x.a,x.b))


def jc_schedule(design):
    """Literal fixed-positive-chi implementation with counted sign-reversal Xs.

    A compensated positive-chi JC pulse gives exp(-i*|angle| Z Q0).
    Positive requested angles use X_data, negative pulse, X_data. Each pulse
    also needs an explicit ideal free/Lamb/centering phase compensation.
    These are control targets, not a claim that Fock Fourier gates are native.
    """
    if type(design) is not BusDesign:raise ValueError("validated BusDesign required")
    out=[]
    for item in design.schedule():
        if item["kind"]!="dispersive":
            out.append(dict(item)); continue
        site=item["data_site"]; angle=item["area_pi"]
        flip=dict(kind="data_x",data_site=site,purpose="coupling_sign")
        if angle>0:out.append(dict(flip))
        out.append(dict(kind="jc_pulse",data_site=site,area_pi=-abs(angle)))
        out.append(dict(kind="phase_compensation",data_site=site,
                        target="remove ideal free/Lamb/global phases and center N to Q0"))
        if angle>0:out.append(dict(flip))
    return out


def jc_pulse_bound(d, steps, ratio):
    """All-input norm bound against dispersive evolution on bus levels 0..d-1.

    JC has g/|Delta|=ratio, chi=g^2/Delta. The pulse duration is set by
    |chi|*t=2*pi*|steps|/d. This compares bare states, retaining the dressing
    mismatch and the m=d block reaching the outside state |g,d>.
    Bounds use rational ceil(sqrt(d)) and an outward Machin enclosure of pi.
    """
    _dimension(d); _int(steps,"JC kick strength",-d//2,d//2)
    r=_bound(ratio)
    if r==0:raise ValueError("nonzero coupling/detuning ratio required")
    pi_low,pi_high=_pi_bounds(128)
    root=isqrt(d); root+=root*root<d
    area_pi=Q(2*abs(steps),d)
    mixing=2*r*root if steps else Q(0)
    spectral=area_pi*pi_high*r*r*d*d
    total=mixing+spectral
    return dict(status="CONDITIONAL_JAYNES_CUMMINGS_MODEL_BOUND",ratio=r,
                maximum_excitation_block=d,includes_bare_dressing_mismatch=True,
                includes_top_code_to_outside_transition=True,
                dressing_contribution=mixing,spectral_remainder_contribution=spectral,
                raw_operator_bound=total,operator_error_bound=min(Q(2),total),
                detuning_time_pi=area_pi/(r*r),
                pi_enclosure=[pi_low,pi_high],
                losses_multilevel_qubit_and_counterrotating_terms_covered=False)


def jc_gate_bound(design, *, ratio, area_bounds, fourier_bounds, flip_bounds,
                  compensation_bounds, other_action_bound):
    """Compose a microscopic JC remainder with explicit implementation budgets.

    All per-operation bounds are required, including sign-reversal X pulses.
    Telescoping uses error norms restricted to the IDEAL input code, so top
    boundary leakage is retained rather than deleting an oscillator level.
    """
    schedule=jc_schedule(design); d=design.dimension; r=_bound(ratio)
    if not r:raise ValueError("nonzero coupling/detuning ratio required")
    counts={kind:sum(x["kind"]==kind for x in schedule)
            for kind in ("jc_pulse","fourier","fourier_inverse","data_x","phase_compensation")}
    def total(values,n):
        if not isinstance(values,(tuple,list)) or len(values)!=n:
            raise ValueError("one explicit bound per actual JC schedule operation required")
        return sum((_bound(v) for v in values),Q(0))
    area=Q(d-1,2)*total(area_bounds,counts["jc_pulse"])
    control=(total(fourier_bounds,counts["fourier"]+counts["fourier_inverse"])
             +total(flip_bounds,counts["data_x"])
             +total(compensation_bounds,counts["phase_compensation"])
             +_bound(other_action_bound))
    pulses=[]
    for item in schedule:
        if item["kind"]=="jc_pulse":
            n=item["area_pi"]*d/2
            if n.denominator!=1:raise ArithmeticError("nonintegral compiled JC kick")
            pulses.append(jc_pulse_bound(d,int(n),r))
    microscopic=sum((p["raw_operator_bound"] for p in pulses),Q(0))
    error=microscopic+area+control
    return dict(status="CONDITIONAL_JC_GATE_BOUND",operation_counts=counts,
                microscopic_contribution=microscopic,area_contribution=area,
                other_control_contribution=control,raw_operator_bound=error,
                input_code_operator_error_bound=min(Q(2),error),
                reduced_data_trace_distance_bound=min(Q(1),error),
                code_escape_probability_bound=min(Q(1),error*error),
                total_detuning_time_pi=sum((p["detuning_time_pi"] for p in pulses),Q(0)),
                excludes_fourier_and_local_gate_durations=True,
                calibration_accepted=False,hardware_submitted=False,
                loss_or_dissipative_noise_covered=False)
