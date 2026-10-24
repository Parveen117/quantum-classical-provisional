"""Reproducible two-site completion; probabilities are computed from operators."""
from fractions import Fraction as F
from .joint import (
    E, ZERO, ONE, INV_SQRT2 as H, Element, State, local, observable, projector,
    product_reference, interaction, bell_preparation, bell_settings, chsh,
    tsirelson_sos, gns, verify_gns, mixture)


def data(x):
    if type(x) is E:
        return x.to_dict()
    if type(x) in (list,tuple):
        return [data(v) for v in x]
    if type(x) is dict:
        return {str(k):data(v) for k,v in x.items()}
    return x


def report():
    state,settings=bell_preparation(),bell_settings()
    a0,a1,b0,b1=settings
    contexts=[]
    for i,a in enumerate((a0,a1)):
        for j,b in enumerate((b0,b1)):
            d=state.joint(a,b)
            contexts.append(dict(alice_setting=i,bob_setting=j,
                                 probabilities={f"{oa},{ob}":data(p) for (oa,ob),p in d.items()},
                                 correlation=data(state.expect(a*b)),
                                 alice_marginals=data([sum((d[a,k] for k in (-1,1)),ZERO) for a in (-1,1)]),
                                 bob_marginals=data([sum((d[k,b] for k in (-1,1)),ZERO) for b in (-1,1)])))
    q=gns(state)
    p,after=state.branch(projector(a0,1))
    white=State(((ONE,Element.basis(2)),))
    noise=[]
    for v in (E(F(1,2)),H,E(F(3,4))):
        out=mixture(((v,state),(ONE-v,white)))
        noise.append(dict(visibility=data(v),CHSH=data(out.expect(chsh(settings)))))
    # PR-style cross moments are a diagnostic negative control, not a State.
    pr_settings=(local(2,0,"K"),local(2,0,"L"),local(2,1,"K"),local(2,1,"L"))
    pr_moments={0:ONE,5:ONE,13:ONE,7:ONE,15:-ONE}
    d0,_=tsirelson_sos(pr_settings)
    pr_witness=sum((c*pr_moments.get(i,ZERO) for i,c in enumerate((d0.dagger()*d0).coefficients)),ZERO)
    return dict(
        schema="phase-seam-joint-v0.2",
        status="conditional finite algebraic quantum completion; no physical device or new-physics claim",
        assumptions=["complexified EMK algebra", "commuting algebras for separated sites",
                     "positive normalized preparation functional", "projector probabilities",
                     "sandwich instruments and complete channels", "chosen joint interaction"],
        inherited_v01="positive phase-point ensembles and local response still obey CHSH <= 2",
        basis="I,K,R,RK at site 0 then site 1, site 0 varies fastest",
        preparation=dict(reference_factors=[s.to_dict() for _,s in product_reference().factors],
                         interaction=interaction().to_dict(),final_factors=[s.to_dict() for _,s in state.factors]),
        contexts=contexts,
        CHSH=data(state.expect(chsh(settings))),CHSH_symbolic="2*sqrt(2)",
        general_upper_bound_proof="2*sqrt(2)*I-S=(D0^*D0+D1^*D1)/sqrt(2)",
        saturation_norms=data([state.expect(d.dagger()*d) for d in tsirelson_sos(settings)]),
        gns=dict(verified=verify_gns(state,q),rank=q["rank"],nullity=16-q["rank"],certificate=data(q),
                 scope="finite GNS quotient over the exact field, then complex scalar extension"),
        selective_measurement=dict(probability=data(p),repeat_probability=data(after.branch(projector(a0,1))[0]),
                                   opposite_probability=data(after.branch(projector(a0,-1))[0]),
                                   conditional_bob_K=data(after.expect(local(2,1,"K")))),
        noise_controls=noise,white_noise_boundary="visibility=1/sqrt(2), CHSH=2; declared depolarizing model only",
        product_control_CHSH=data(product_reference().expect(chsh(settings))),
        pr_negative_control=dict(CHSH="4",positive_square_value=data(pr_witness),
                                 conclusion="2-2*sqrt(2)<0; not an admitted positive state"),
        hardware_target="U(chi)=cos(chi)I-sin(chi)R_A L_B; chi=pi/4 for the chosen preparation",
        open=["derive probability/positivity assumptions from manuscript primitives",
              "faithful map from the v0.1 four phase coordinates and memory to this operator state",
              "material implementation and measured noise",
              "time-tensor law and energy calibration",
              "universal/scalable computing, physical qubit count or quantum speedup"])


if __name__=="__main__":
    import json
    print(json.dumps(report(),indent=2))
