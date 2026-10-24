"""Repeatable phase-register compiler and coherent-interference witnesses."""
from fractions import Fraction as F
from native_relational_qc.phase_backend import Phase64Circuit, prepare
from .model import Cell, Config, Operation as O
from .register import compile_register, closure_codec, bind_cell, verify_program, verify_transition


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
        schema="phase-seam-register-v0.5",author="Monty",
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
        limits=dict(power_of_two_grids=[1<<w for w in range(2,13)],max_gates=100000,
                    source_guards="Config parameter/event limits; bound Cell replay also checks lift and rational-cost limits",
                    closure="whole fixed sector preserved after each source operation; elementary gates may leave it",
                    excluded=["read/reset instruments","Gamma quantum storage","quantum winding/history/cost register","unknown-sector compression"]),
        open=["native physical preparation of coherent phase-label superpositions",
              "physical gate/readout/control calibration and noise",
              "controller/environment accounting for read/reset and path-dependent records",
              "native probability and time/energy laws independent of circuit assumptions"])


if __name__ == "__main__":
    import json
    print(json.dumps(report(),indent=2))
