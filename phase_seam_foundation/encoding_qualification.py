"""Reproducible tomography, retained-ledger and transport witnesses."""
from fractions import Fraction as F
from .model import Cell,Config,Operation
from .encoding import (
    C,I,PAIRS,SEAM,encode,recover,decode,verify_bridge,compile_transport,
    verify_transport,positive_factors,binary_readout,channel_obstruction)


def data(x):
    if type(x) is C:return x.to_dict()
    if type(x) is F:return str(x)
    if type(x) in (tuple,list):return [data(v) for v in x]
    if type(x) is dict:return {str(k):data(v) for k,v in x.items()}
    return x


def report():
    cell=Cell.start((1,8,19,-28),config=Config(sector=1),gamma=F(2,3))
    cell=cell.apply(Operation("read",(0,0)))
    bridge=encode(cell)
    transport=compile_transport(bridge,(Operation("pair_shift",(0,2,1)),))
    decoded,gamma=decode(bridge.code)
    t=(gamma-1)/(gamma+1)
    factors=positive_factors(cell.phases,gamma)
    rebuilt=I*0
    for w,s in factors:rebuilt=rebuilt+(s*s.dagger())*w
    loop_a=encode(Cell.start().apply(Operation("shift",(0,64))))
    loop_b=encode(Cell.start().apply(Operation("shift",(0,-64))))
    return dict(
        schema="phase-seam-encoding-v0.3",
        status="injective tomographic phase/seam encoding with retained classical history; partial operation correspondence",
        new_choices=["nine signed Pauli readings", "Cayley calibration t=(Gamma-1)/(Gamma+1)",
                     "equal mixture of five positive components", "classical provenance retained separately"],
        input=dict(lifts=list(cell.state.lifts),gamma=str(cell.gamma),grid=64,closure=cell.closure),
        code=bridge.code.to_dict(),
        readings=data([bridge.code.expect(p) for pair in PAIRS for p in pair]+[bridge.code.expect(SEAM)]),
        decoded=dict(phases=list(decoded),gamma=str(gamma),exact=True,
                     qualification="exact expectation oracle; no one-copy phase decoding claim"),
        positivity=dict(square_factors=6,reconstruction=rebuilt==bridge.code,
                        tau_normalization=data(bridge.code.tau()),
                        density_element_lower_bound=str((1-abs(t))/5)),
        history=dict(verified=verify_bridge(bridge),full_cell_recovered=recover(bridge)==cell,
                     opposite_windings_same_code=loop_a.code==loop_b.code,
                     different_tapes=loop_a.operations!=loop_b.operations,
                     classical_memory_compressed=False),
        transport=dict(kind="pair_shift",args=[0,2,1],verified=verify_transport(transport),
                       initial_lifts=list(cell.state.lifts),final_lifts=list(recover(transport.after).state.lifts),
                       unitary=transport.unitary.to_dict(),identity="D(after)=U D(before) U^*",
                       scope="opposed pairs (0,2), (1,3) and paired site swap only"),
        one_copy_readout_example=data(binary_readout(encode(Cell.start()).code,PAIRS[0][0])),
        balanced_cut_obstruction=data(channel_obstruction()),
        image_boundary=dict(purity=data((bridge.code*bridge.code).tau()/4),
                            general_purity="(1+(4+t^2)/25)/4 < 3/10",
                            bell_pure_state_in_image=False,
                            nontrivial_CHSH_after_any_unitary_bound_squared="4*(4+t^2)/25 < 4/5",
                            assumptions="two nontrivial binary qubit observables at each site; traceless local settings"),
        exact_single_copy_label_bound=dict(unrestricted_phase_labels=64**4,minimum_register_bits=24,
                                          fixed_closure_phase_labels=64**3,minimum_fixed_closure_bits=18,
                                          scope="faithful deterministic joint phase-label readout, Gamma and history fixed; not an algorithmic capacity claim"),
        open=["physical preparation/calibration and finite-shot decoder",
              "full native cut/channel correspondence",
              "native preparation of nonclassical joint resources",
              "history storage cost, time/energy law and physical hardware"])


if __name__=="__main__":
    import json
    print(json.dumps(report(),indent=2))
