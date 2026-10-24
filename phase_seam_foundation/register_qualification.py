"""Repeatable phase-register compiler and coherent-interference witnesses."""
from fractions import Fraction as F
from native_relational_qc.phase_backend import Phase64Circuit, prepare
from .model import Cell, Config, Operation as O
from .register import compile_register, closure_codec, bind_cell, verify_program, verify_transition
from .controller import compile_controller, bind_controller, verify_controller_transition
from .sector_control import compile_sector_control, pulse_coefficients, verify_sector_control
from .photonic_exchange import design_photonic_exchange, verify_photonic_exchange


def photonic_report():
    import hashlib,json
    layout=design_photonic_exchange()
    def digest(value):return hashlib.sha256((json.dumps(value,indent=2)+"\n").encode()).hexdigest()
    netlist=layout.netlist();protocol=layout.experiment_plan()
    return dict(status="DESIGN_ONLY",evidence_class="LOCAL_IDEAL_CALCULATION",hardware_job_id=None,
                candidate=netlist["engineering_choice"],resources=layout.resources(),
                native_domain="fixed pair sum q=0, reference a=0, two spectator modes fixed zero, one retained pointer",
                route_pairs=[list(p) for p in layout.pairs],fixed_ports=list(layout.fixed),guard=layout.guard,
                canonical_layout_verified=verify_photonic_exchange(layout),
                transfer="each two-cycle uses H diag(1,exp(-i*theta)) H; fixed paths are identity",
                artifacts=dict(netlist="photonic_exchange_netlist.json",netlist_sha256=digest(netlist),
                               protocol="photonic_exchange_protocol.json",protocol_sha256=digest(protocol)),
                proposed_settings=dict(total=protocol["settings_count"],basis=80,cross_block_coherence=24,guard_controls=2,
                                       herald_windows_per_setting=None,measurements=None),
                scale_comparison={str(grid):design_photonic_exchange(grid=grid).resources() for grid in (4,8,64)},
                boundaries=["one photon across many paths is not many independent qubits",
                            "four independent physical phase channels are not built or measured",
                            "guard tests optical code leakage, not an independent native closure charge",
                            "ordinary photon detection destroys the joint data/pointer carrier",
                            "bright-light calibration is not quantum-carrier qualification",
                            "all losses and herald-window categories must be retained",
                            "generic mesh endpoint equivalence does not prove its internal path stays in the code",
                            "fabrication geometry, phase-voltage maps, errors, rates and budget remain unmeasured"])


def sector_control_report():
    cfg=Config(sector=1)
    p=compile_sector_control((O("pair_reset",(0,2,0)),),config=cfg,omit_mode=2)
    samples=[];initial=p.controller.pack((1,0,63,0))
    for step in (0,1,8,16,24,32):
        c=Phase64Circuit(p.n_qubits+2).add("x",0)
        verification=p.verification_circuit((step,))
        for name,qs in verification.operations:c.add(name,*qs)
        state=prepare(c);alpha,beta=pulse_coefficients(step)
        expected={}
        for label,value in ((initial,alpha),(p.image(0,initial),beta)):
            if value:expected[label]=expected.get(label,c.field(0))+value
        leakage=sum((v.norm2() for label,v in state.amplitudes.items()
                     if sum(p.controller.unpack(label&((1<<p.n_qubits)-1))[0])%64),c.field(0))
        samples.append(dict(angle_pi_over_32_steps=step,exact_amplitude_match=state.amplitudes==expected,
                            closure_leakage_probability=leakage.to_dict(),
                            reset_probability=state.probability({q:0 for q in p.controller.layout.registers[0]}).to_dict(),
                            flags_zero_probability=state.probability({p.n_qubits:0,p.n_qubits+1:0}).to_dict(),
                            verification_gates=len(verification.operations)))
    wrong=Phase64Circuit(10).add("h",8).add("cx",8,0).add("h",8)
    for _ in range(16):wrong.add("p64dg",8)
    wrong.add("h",8).add("cx",8,0).add("h",8)
    negative=prepare(wrong).probability({0:1})
    cases={str(o):compile_sector_control((O("pair_reset",(0,2,0)),),config=cfg,omit_mode=o).resources()
           for o in (None,0,1,2,3)}
    for o,r in cases.items():
        program=compile_sector_control((O("pair_reset",(0,2,0)),),config=cfg,omit_mode=None if o=="None" else int(o))
        r["half_angle_verification_gates"]=len(program.verification_circuit((16,)).operations)
    return dict(status="conditional continuous control theorem plus existing-engine exact samples",
                algebra=dict(exchange="P: (x_j,x_b,m) -> (a+m,x_b+x_j-a-m,x_j-a) mod L",
                             involution="P^2=I, P*=P",closure="[P,Q_s]=0 for every modular-sum sector",
                             interpolation="U(theta)=(I+P)/2+exp(-i*theta)*(I-P)/2",
                             generator="H(t)=hbar*g(t)*(I-P)/2; theta=integral g(t) dt",
                             all_real_angle_theorem="[U(theta),Q_s]=0; U(0)=I; U(pi)=P",
                             clock="laboratory pulse area, not a derivation of native time"),
                source_consistency=verify_sector_control(p),exact_samples=samples,
                negative_control=dict(generator="single data-bit X, not a balanced exchange",angle="pi/2",
                                      outside_sum_zero_probability=negative.to_dict()),
                resources=cases,
                choice="new involutive dirty-record extension; agrees with v0.7 clean-record endpoints",
                verification_boundary="binary gadget is a mathematical verification circuit, not a sector-confined physical gate path",
                error_budget="for initial sector Q and H=H0+V with [H0,Q]=0, leakage <= min(1,(integral ||(I-Q)VQ||/hbar dt)^2)",
                new_assumption="device can realize the declared high-dimensional symmetric generator and initialized records",
                unresolved=["material carrier, locality and native coupling synthesis","calibrated pulse strengths, time and energy",
                            "noise coupling to forbidden sectors and protected continuous implementation",
                            "record recycling and coherent unwrapped lift/cost storage"],
                evidence_class="LOCAL_IDEAL_CALCULATION",hardware_job_id=None)


def controller_report():
    from native_relational_qc.dynamic import probability
    p=compile_controller((O("read",(0,1)),O("reset",(0,2))))
    source=Cell.start((65,0,0,0),gamma=F(3,7))
    transition=bind_controller(source,p)
    reset=compile_controller((O("reset",(0,5)),))
    ref=reset.n_qubits
    c=Phase64Circuit(ref+1).add("h",ref).add("p64",ref).add("cx",ref,0)
    initial=prepare(c).amplitudes
    for name,qs in reset.gates:c.add(name,*qs)
    state=prepare(c)
    expected={5|(((label&63)-5)%64 << reset.records[0].wires[0])|(label&(1<<ref)):amp for label,amp in initial.items()}
    records=[dict(data_and_record=list(reset.unpack(label&((1<<ref)-1))),reference=(label>>ref)&1,
                  amplitude=amp.to_dict()) for label,amp in sorted(state.amplitudes.items())]
    for name,qs in reset.to_circuit(inverse=True).operations:c.add(name,*qs)
    inverse_matches=prepare(c).amplitudes==initial
    dynamic=compile_controller((O("read",(0,0)),O("reset",(0,0))),config=Config(grid=4)).to_dynamic((("h",(0,)),("t",(0,))))
    cases={
        "full_read_reference0":compile_controller((O("read",(0,0)),)).resources(),
        "full_reset_reference0":compile_controller((O("reset",(0,0)),)).resources(),
        "read_reference1_then_reset_reference2":p.resources(),
        "compressed_omitted_read":compile_controller((O("read",(2,0)),),config=Config(sector=1),omit_mode=2).resources()}
    return dict(status="coherent native read/reset records with existing dynamic measurement export",
                equations=dict(read_clean_record="|x,0> -> |x,x_j-a mod L>",
                               read_retained_mode_dirty_record="|x,y> -> |x,(y XOR x_j)-a mod L>",
                               read_omitted_mode_dirty_record="|x,y> -> |x,y+x_j-a mod L>",
                               reset="|x_j,y> -> |a+y,x_j-a mod L>"),
                record_precondition="fresh zero product registers, separate from temporary clean workspace",
                known_cell=dict(input_lifts=list(source.state.lifts),output_lifts=list(transition.after.state.lifts),
                                outcomes=list(transition.outcomes),gamma=str(transition.after.gamma),
                                verified=verify_controller_transition(transition)),
                coherent_reset=dict(input="entangled data/reference with relative zeta_64 phase",output=records,
                                    exact_amplitude_transfer=state.amplitudes==expected,inverse_restores_input=inverse_matches,
                                    reset_data_probability=state.probability({q:(5>>i)&1 for i,q in enumerate(reset.layout.registers[0])}).to_dict(),
                                    scope="coherent retained record; inverse does not undo discarded or measured coherence"),
                existing_dynamic_engine=dict(reset_zero_probability=probability(dynamic,quantum={0:0,1:0}).value.to_dict(),
                                             two_records_both_one_probability=probability(dynamic,classical={0:1,1:0,2:1,3:0}).value.to_dict(),
                                             implementation="native_relational_qc.dynamic, unchanged"),
                resources=cases,
                limits=dict(default_max_records=16,max_records_option=64,max_total_wires=256,max_gates=100000,
                            reset="only unrestricted full layout; a single-mode reset is not whole-sector preserving"),
                open=["physical initialization, pointer measurement and noise",
                      "record recycling and environment/energy accounting","coherent unwrapped winding and path-cost storage"])


def balanced_reset_report():
    cfg=Config(sector=1)
    op=O("pair_reset",(0,2,0))
    p=compile_controller((op,),config=cfg,omit_mode=2)
    source=Cell.start((65,0,-1,0),config=cfg,gamma=F(3,7))
    transition=bind_controller(source,p)
    c=Phase64Circuit(p.n_qubits).add("h",0).add("p64",0)
    initial=prepare(c).amplitudes
    for name,qs in p.gates:c.add(name,*qs)
    amplitudes=prepare(c).amplitudes
    expected={((label&63) << p.records[0].wires[0]):value for label,value in initial.items()}
    output=[dict(phases=list(p.unpack(label)[0]),records=list(p.unpack(label)[1]),amplitude=value.to_dict())
            for label,value in sorted(amplitudes.items())]
    for name,qs in p.to_circuit(inverse=True).operations:c.add(name,*qs)
    inverse=prepare(c).amplitudes==initial
    cases={}
    for reference in (0,7):
        cases[str(reference)]={str(omitted):compile_controller((O("pair_reset",(0,2,reference)),),config=cfg,
                                                              omit_mode=omitted).resources()
                               for omitted in (None,0,1,2,3)}
    return dict(status="explicit pair_reset source law, compiled through existing retained-record controller",
                source=dict(operation="pair_reset(j,reservoir,a)",lift_update="ell_j'=a; ell_s'=ell_s+ell_j-a",
                            record="(ell_j-a) mod L",integer_sum_preserved=True,
                            added_choice="compensating reservoir transfer, not derived from the supplied manuscripts",
                            cost="does not charge the existing cut counter; physical energy unspecified"),
                clean_isometry="|x_j,x_s,0> -> |a,x_s+x_j-a,x_j-a> modulo L",
                lowering="existing read into fresh record r, then controlled shifts (-r,+r) on stored data modes",
                known_cell=dict(input_lifts=list(source.state.lifts),output_lifts=list(transition.after.state.lifts),
                                input_sum=sum(source.state.lifts),output_sum=sum(transition.after.state.lifts),
                                outcomes=list(transition.outcomes),gamma=str(transition.after.gamma),
                                history_verified=verify_controller_transition(transition)),
                coherent_sector_example=dict(input="(|0,0,0,0> + zeta_64 |1,0,63,0>)/sqrt(2)",
                                             omitted_reservoir=2,output=output,exact_amplitudes=amplitudes==expected,
                                             coherent_inverse_restores_input=inverse,
                                             evidence_class="LOCAL_IDEAL_CALCULATION"),
                resources_by_reference_and_omitted_mode=cases,
                boundaries=["single-mode reset remains rejected in fixed sectors",
                            "reservoir is another native phase mode, not a thermal bath or free memory",
                            "only untouched modes/reference have guaranteed unchanged unconditioned marginals",
                            "sum preserved at source boundaries; elementary gates may leave the sector",
                            "fresh zero records and clean workspace required for reset semantics",
                            "record coherence and availability required for inverse recovery",
                            "Gamma, unwrapped lift transfer and cost/history remain classical",
                            "logical gate counts are construction costs, not optimality or physical performance"])


def sector_report():
    cfg = Config(sector=1)
    word = (O("pair_cut",(0,2,0)),)
    p = compile_register(word,config=cfg,omit_mode=2)
    full = compile_register(word,config=cfg)
    c = Phase64Circuit(p.n_qubits).add("h",0).add("p64",0)
    before = prepare(c).amplitudes
    for name,qs in p.gates: c.add(name,*qs)
    state = prepare(c)
    expected = {p.pack(p.image(p.unpack(k))):v for k,v in before.items()}
    for name,qs in p.to_circuit(inverse=True).operations: c.add(name,*qs)
    c.add("p64dg",0).add("h",0)
    restored = prepare(c).amplitudes == {0:c.field(1)}
    matrix, offset = p.stored_affine()
    cases = {}
    for name, operations in (
        ("balanced_cut_axis_zero",word),
        ("paired_shift",(O("pair_shift",(0,2,1)),)),
        ("mode_swap",(O("swap",(0,2)),)),
        ("three_operation_closed_word",(O("pair_cut",(0,2,7)),O("pair_shift",(1,3,-5)),O("swap",(0,1))))):
        cases[name] = dict(full_gates=len(compile_register(operations,config=cfg).gates),
                           gates_by_omitted_mode={str(o):len(compile_register(operations,config=cfg,omit_mode=o).gates) for o in range(4)})
    codec = closure_codec(cfg,2)
    return dict(
        status="fixed-closure exact coordinate elimination inside the existing register compiler",
        closure=dict(sign=1,twist=0,sum_residue=0,omitted_mode=2,identity="x2 = -(x0+x1+x3) mod 64"),
        full_resources=full.resources(),compressed_resources=p.resources(),
        stored_affine_matrix=[list(row) for row in matrix],stored_affine_offset=list(offset),
        elementary_operations=[[n,list(qs)] for n,qs in p.gates],source_gate_binding_verified=verify_program(p),
        coherent_control=dict(actual_amplitudes=[dict(labels=list(p.unpack(k)),amplitude=v.to_dict()) for k,v in sorted(state.amplitudes.items())],
                              exact_amplitude_match=state.amplitudes==expected,inverse_interference_restores_zero=restored,
                              execution_logical_wires=c.n_qubits,evidence_class="LOCAL_IDEAL_CALCULATION"),
        codec=dict(peak_logical_wires=codec.n_qubits,compression_gates=len(codec.operations),
                   expansion_gates=len(codec.operations),on_sector="omitted register and workspace end zero",
                   off_sector="omitted register retains sum(x)-s, not discarded",
                   full_compress_apply_expand_gates=2*len(codec.operations)+len(p.gates),
                   comparison="conversion costs counted separately; direct compressed preparation uses 22 wires"),
        gate_tradeoffs=cases,
        no_new_physical_postulate=True,
        restrictions=["fixed sign and twist are known", "only operations preserving the whole sector at every source boundary",
                      "no cross-sector superposition compression", "Gamma, winding, event/cost data remain external",
                      "no new physical preparation or measurement law", "reconstructed omitted label is derived, not an independent closure measurement"])


def report():
    cfg = Config(sector=1)
    word = (O("pair_cut", (0,2,7)), O("pair_shift", (1,3,-5)), O("swap", (0,1)))
    p = compile_register(word, config=cfg)
    source = Cell.start((1,8,19,-28),config=cfg,gamma=F(2,3)).apply(O("read",(0,2)))
    transition = bind_cell(source,p)
    cut = compile_register((O("pair_cut",(0,2,0)),),config=cfg)
    c = Phase64Circuit(cut.n_qubits).add("h",0).add("s",0)
    for q in cut.registers[2]: c.add("cx",0,q)
    for name,qs in cut.to_circuit().operations: c.add(name,*qs)
    state = prepare(c)
    rows = [dict(phase_labels=list(cut.unpack(label)),amplitude=amp.to_dict())
            for label,amp in sorted(state.amplitudes.items())]
    for name,qs in cut.to_circuit(inverse=True).operations: c.add(name,*qs)
    for q in reversed(cut.registers[2]): c.add("cx",0,q)
    c.add("sdg",0).add("h",0)
    restored = prepare(c)
    obstruction_inputs = [Cell.start(config=cfg),Cell.start((16,-16,0,0),config=cfg)]
    resource_cases = {}
    for name, ops in (
        ("cut_axis_zero",(O("cut",(0,0)),)),
        ("balanced_cut_axis_zero",(O("pair_cut",(0,2,0)),)),
        ("shear_minus3_reference5",(O("shear",(0,2,-3,5)),)),
        ("three_operation_closed_word",word)):
        resource_cases[name] = compile_register(ops).resources()
    return dict(
        schema="phase-seam-register-v0.9",author="Monty",
        status="wrapped-phase permutation compiler reusing existing native arithmetic",
        assumptions=["orthogonal labels","clean workspace","standard coherent gate semantics if used as quantum circuit"],
        program=dict(source_operations=[dict(kind=o.kind,args=list(o.args)) for o in word],
                     affine_matrix=[list(r) for r in p.matrix],affine_offset=list(p.offset),
                     source_gate_binding_verified=verify_program(p),
                     elementary_operations=[[n,list(qs)] for n,qs in p.gates]),
        known_cell=dict(initial_lifts=list(source.state.lifts),final_lifts=list(transition.after.state.lifts),
                        initial_phases=list(source.phases),final_phases=list(transition.after.phases),
                        gamma=str(transition.after.gamma),cost=str(transition.after.state.cost),
                        events_retained=len(transition.after.events),verified=verify_transition(transition)),
        coherent_control=dict(input="(|0,0,0,0> + i |1,0,63,0>)/sqrt(2)",
                              balanced_cut_output=rows,
                              inverse_and_preparation_inverse_yield_zero=restored.amplitudes=={0:c.field(1)},
                              evidence_class="LOCAL_IDEAL_CALCULATION",hardware_job_id=None),
        prior_obstruction_pair=dict(
            inputs=[list(x.phases) for x in obstruction_inputs],
            outputs=[list(bind_cell(x,cut).after.phases) for x in obstruction_inputs],
            input_trace_distance=1,output_trace_distance=1,
            reason="distinct orthogonal labels; a different encoding, not a channel conversion of the old code",
            previous_two_site_obstruction_still_valid=True),
        resources=resource_cases,
        sector_compression=sector_report(),
        controller=controller_report(),
        balanced_reset=balanced_reset_report(),
        sector_control=sector_control_report(),
        photonic_exchange=photonic_report(),
        limits=dict(power_of_two_grids=[1<<w for w in range(2,13)],max_gates=100000,
                    source_guards="Config parameter/event limits; bound Cell replay also checks lift and rational-cost limits",
                    closure="whole fixed sector preserved after each source operation; elementary gates may leave it",
                    excluded=["single-mode reset in a fixed closure sector","Gamma quantum storage","quantum winding/history/cost register","unknown-sector compression"]),
        open=["native physical preparation of coherent phase-label superpositions",
              "physical gate/readout/control calibration and noise",
              "physical controller/environment and record recycling; coherent unwrapped path records",
              "native probability and time/energy laws independent of circuit assumptions"])


if __name__ == "__main__":
    import json
    print(json.dumps(report(),indent=2))
