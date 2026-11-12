"""Saved-model prediction with bounded device mapping and exact QASM replay."""
import argparse
import copy
from collections import deque
from itertools import permutations
import json
from pathlib import Path
import sys

from .calculator import MAX_INPUT_BYTES, _object, calculate, loads
from .compact import ResourceLimit, _integer
from .cyclotomic_pow2 import field_of_order
from . import openqasm
from .phase_backend import PowerPhaseCircuit, prepare, required_order
from .self_learning import DEFAULT_ENTANGLERS, FIELD, _steps, circuit, digest, load_packet


PROFILE_SCHEMA = "nrqc-device-profile-v1"
OUTPUT_SCHEMA = "nrqc-model-prediction-v1"
NATIVE_GATES = ("h", "s", "sdg", "cx", "p2", "p4", "p8", "p16", "p32", "p64")


def device_profile(profile=None):
    if profile is None:
        profile = dict(schema=PROFILE_SCHEMA, name="software-four-wire-all-to-all", n_qubits=4,
                       coupling_map=[[a, b] for a in range(4) for b in range(4) if a != b],
                       native_gates=list(NATIVE_GATES), max_gates=1024)
    _object(profile, ("schema", "name", "n_qubits", "coupling_map", "native_gates", "max_gates"))
    if profile["schema"] != PROFILE_SCHEMA:
        raise ValueError("unsupported device-profile schema")
    n = _integer(profile["n_qubits"], "physical wires", 1, 4)
    if not isinstance(profile["name"], str) or not 1 <= len(profile["name"]) <= 100:
        raise ValueError("device profile requires a short name")
    gates = profile["native_gates"]
    if (not isinstance(gates, list) or not gates or
            any(not isinstance(g, str) or g not in NATIVE_GATES for g in gates) or
            len(set(gates)) != len(gates)):
        raise ValueError("device native gates must be a unique supported subset")
    edges = profile["coupling_map"]
    if not isinstance(edges, list):
        raise ValueError("device coupling_map must contain directed pairs")
    seen = set()
    for edge in edges:
        if not isinstance(edge, list) or len(edge) != 2:
            raise ValueError("device edge needs two physical wires")
        a, b = (_integer(q, "physical wire", 0, n - 1) for q in edge)
        if a == b or (a, b) in seen:
            raise ValueError("device edges must be distinct and join different wires")
        seen.add((a, b))
    cap = _integer(profile["max_gates"], "native gate cap", 1, 4096)
    return dict(schema=PROFILE_SCHEMA, name=profile["name"], n_qubits=n,
                coupling_map=[list(e) for e in sorted(seen)], native_gates=gates.copy(), max_gates=cap)


def _path(start, end, profile):
    edges = {tuple(e) for e in profile["coupling_map"]}
    if (start, end) in edges or ("h" in profile["native_gates"] and (end, start) in edges):
        return [start, end]
    # A routing SWAP needs a CX in both directions. H permits reversal.
    frontier = deque([[start]])
    seen = {start}
    while frontier:
        path = frontier.popleft()
        for q in range(profile["n_qubits"]):
            a = path[-1]
            usable = ((a, q) in edges and (q, a) in edges) or (
                "h" in profile["native_gates"] and ((a, q) in edges or (q, a) in edges))
            if q in seen or not usable:
                continue
            extended = path + [q]
            if q == end:
                return extended
            seen.add(q)
            frontier.append(extended)
    return None


def compile_model_circuit(source, profile):
    """Place active logical wires, route CXs and retain final wire labels."""
    if not isinstance(source, PowerPhaseCircuit) or source.n_qubits != 4 or source.order > 64:
        raise ValueError("a four-wire native model circuit of order at most 64 is required")
    profile = device_profile(profile)
    active = sorted({0, 1, 3} | {q for _, qs in source.operations for q in qs})
    if len(active) > profile["n_qubits"]:
        raise ValueError("device has too few wires for the model's active register")
    if any(name not in profile["native_gates"] for name, _ in source.operations):
        raise ValueError("device native gates do not admit this model/feature circuit")
    best = None
    for placement in permutations(range(profile["n_qubits"]), len(active)):
        layout = dict(zip(active, placement))
        paths = [_path(layout[qs[0]], layout[qs[1]], profile)
                 for name, qs in source.operations if name == "cx"]
        if all(path is not None for path in paths):
            score = sum(3 * (len(path) - 2) + 1 for path in paths)
            if best is None or (score, placement) < best[:2]:
                best = score, placement, layout
    if best is None:
        raise ValueError("device connectivity cannot route the model")
    layout = best[2].copy()
    initial = layout.copy()
    physical = PowerPhaseCircuit(profile["n_qubits"], 64)
    edges = {tuple(e) for e in profile["coupling_map"]}
    trace = []

    def emit(name, *qs):
        if name not in profile["native_gates"]:
            raise ValueError("routing needs an unsupported native gate")
        if len(physical.operations) >= profile["max_gates"]:
            raise ResourceLimit("device native gate cap exhausted")
        physical.add(name, *qs)

    def cx(a, b):
        if (a, b) in edges:
            emit("cx", a, b)
        elif (b, a) in edges and "h" in profile["native_gates"]:
            emit("h", a)
            emit("h", b)
            emit("cx", b, a)
            emit("h", a)
            emit("h", b)
        else:
            raise ValueError("directed CX is unavailable")

    for index, (name, qs) in enumerate(source.operations):
        before = len(physical.operations)
        if name == "cx":
            path = _path(layout[qs[0]], layout[qs[1]], profile)
            if path is None:
                raise ValueError("routing lost connectivity after placement")
            for a, b in zip(path[:-2], path[1:-1]):
                cx(a, b)
                cx(b, a)
                cx(a, b)
                layout = {logical: b if q == a else a if q == b else q
                          for logical, q in layout.items()}
            cx(layout[qs[0]], layout[qs[1]])
        else:
            emit(name, layout[qs[0]])
        trace.append(dict(source_index=index, native_start=before,
                          native_stop=len(physical.operations)))
    return physical, dict(profile=profile, initial_layout={str(q): p for q, p in initial.items()},
                          final_layout={str(q): p for q, p in layout.items()},
                          omitted_logical_wires_initial_zero=sorted(set(range(4)) - set(active)),
                          native_trace=trace, placement_optimality_certified=False)


class _ExecutionBudget:
    def __init__(self, max_work):
        self.cap = _integer(max_work, "whole-run work budget", 1, 1_000_000_000)
        self.used = 0

    def remaining(self):
        if self.used >= self.cap:
            raise ResourceLimit("whole prediction/verification budget exhausted")
        return self.cap - self.used

    def run(self, program, outcomes=None):
        state = None
        failure = None
        try:
            state = prepare(program, max_work=self.remaining(), max_branches=16)
            value = state.probability(outcomes) if outcomes is not None else None
            return state.amplitudes, value
        except ResourceLimit as error:
            failure = error
            raise
        finally:
            stats = state.budget.stats if state is not None else getattr(failure, "statistics", {})
            self.used += stats.get("work_used", 0)


def _basis_program(program, occupied):
    out = PowerPhaseCircuit(program.n_qubits, 64)
    for q in occupied:
        out.add("x", q)
    for name, qs in program.operations:
        out.add(name, *qs)
    return out


def _logical_amplitudes(amplitudes, final_layout):
    result = {}
    live = sum(1 << q for q in final_layout.values())
    for ket, value in amplitudes.items():
        if ket & ~live:
            raise ArithmeticError("routing changed a spare wire's final zero state")
        logical = sum(((ket >> physical) & 1) << int(q) for q, physical in final_layout.items())
        result[logical] = value
    return result


def _model(document):
    if isinstance(document, dict) and document.get("schema") in (
            "native-learning-fit-v1", "nrqc-structure-learning-v1"):
        if document.get("status", "completed") != "completed":
            raise ValueError("a completed fit is required")
        document = document.get("model")
    load_packet(document)
    return copy.deepcopy(document)


def predict(document, features, *, view, profile=None, max_work=1_000_000):
    model = _model(document)
    if view != model["feature_view"]:
        raise ValueError("declared feature view does not match the saved model")
    features = _steps(features, 2)
    parameters = load_packet(model)
    source = circuit(features, parameters, entanglers=model.get("entanglers", DEFAULT_ENTANGLERS),
                     compiler="fused")
    physical, mapping = compile_model_circuit(source, device_profile(profile))
    budget = _ExecutionBudget(max_work)
    text = openqasm.dumps(physical)
    roundtrip = openqasm.loads(text)
    active = sorted(map(int, mapping["initial_layout"]))
    for label in range(1 << len(active)):
        occupied = [q for bit, q in enumerate(active) if label & (1 << bit)]
        expected, _ = budget.run(_basis_program(source, occupied))
        physical_input = [mapping["initial_layout"][str(q)] for q in occupied]
        actual, _ = budget.run(_basis_program(physical, physical_input))
        returned, _ = budget.run(_basis_program(roundtrip, physical_input))
        if returned != actual:
            raise ArithmeticError("OpenQASM changed the active-register unitary")
        if expected != _logical_amplitudes(actual, mapping["final_layout"]):
            raise ArithmeticError("mapped circuit failed active-register unitary verification")
    _, expected = budget.run(source, {3: 1})
    readout = mapping["final_layout"]["3"]
    request = dict(schema="nrqc-calculator-v1", backend="cyclotomic_pow2",
                   n_qubits=physical.n_qubits,
                   operations=[[name, list(qs)] for name, qs in physical.operations],
                   queries=[dict(id="probability_one", kind="probability", outcomes={str(readout): 1})],
                   limits=dict(max_work=budget.remaining(), max_branches=16))
    calculation = calculate(request)
    budget.used += calculation.get("statistics", {}).get("work_used", 0)
    if calculation["status"] != "completed":
        raise ResourceLimit("calculator execution exhausted its remaining budget")
    value = calculation["answers"][0]["value"]["exact"]
    actual = FIELD(field_of_order(required_order(physical.operations)).from_dict(value))
    if actual != expected:
        raise ArithmeticError("mapped calculator readout differs from the source model")
    payload = dict(schema=OUTPUT_SCHEMA, model=model, features=list(features), feature_view=view,
                   device=mapping["profile"], mapping=mapping, calculator_request=request,
                   openqasm=text, probability_one=actual.to_dict(),
                   predicted=int((actual - FIELD(1) / 2).real_sign() > 0),
                   verification=dict(status="verified", basis_inputs_checked=1 << len(active),
                                     scope="full active-register unitary, omitted wires initialized to zero",
                                     qasm_exact_active_unitary_roundtrip=True),
                   resources=dict(exact_work=budget.used, max_work=max_work,
                                  source_gates=len(source.operations), native_gates=len(physical.operations)),
                   evidence_class="LOCAL_IDEAL_CALCULATION", hardware_jobs=0)
    return dict(payload, fingerprint=digest(payload))


def verify_prediction(record):
    if not isinstance(record, dict) or record.get("schema") != OUTPUT_SCHEMA:
        raise ValueError("a prediction record is required")
    payload = {k: v for k, v in record.items() if k != "fingerprint"}
    if record.get("fingerprint") != digest(payload):
        raise ValueError("prediction record fingerprint mismatch")
    replay = predict(record["model"], record["features"], view=record["feature_view"],
                     profile=record["device"], max_work=record["resources"]["max_work"])
    if replay != record:
        raise ValueError("prediction record does not match exact replay")
    return dict(status="verified", fingerprint=record["fingerprint"],
                basis_inputs_checked=record["verification"]["basis_inputs_checked"])


def main(argv=None, *, replay=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    if not replay:
        parser.add_argument("--features", nargs=2, type=int, required=True)
        parser.add_argument("--view", choices=("xor_bits", "first_layer", "point_only"), required=True)
        parser.add_argument("--device", type=Path)
        parser.add_argument("--max-work", type=int, default=1_000_000)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        def read(path):
            with path.open("rb") as stream:
                return loads(stream.read(MAX_INPUT_BYTES + 1).decode("utf-8"))
        document = read(args.input)
        if replay:
            result = verify_prediction(document)
        else:
            result = predict(document, args.features, view=args.view,
                             profile=read(args.device) if args.device else None, max_work=args.max_work)
        status = "completed"
    except (ValueError, TypeError, OSError, KeyError) as error:
        result, status = dict(status="invalid_request", error=str(error)), "invalid_request"
    except ResourceLimit as error:
        result, status = dict(status="incomplete", error=str(error)), "incomplete"
    except ArithmeticError as error:
        result, status = dict(status="verification_failed", error=str(error)), "verification_failed"
    rendered = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if status == "completed" else (2 if status == "invalid_request" else 1)
