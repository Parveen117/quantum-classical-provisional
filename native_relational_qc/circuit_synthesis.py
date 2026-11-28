"""Bounded goal-directed circuit construction with exact stabilizer checks.

Pāṇini-inspired context restrictions select admissible gate words. Quantum
identities come from the existing modular rewrite adapter and exact executor.
The input is |0...0>; a complete commuting independent stabilizer set specifies
the target pure state. This search admits H, X, Z and directed CX on 1..4 wires.
"""
from collections import deque
import argparse
import json
import math
from pathlib import Path
import sys
import time

from .calculator import MAX_INPUT_BYTES, _digest, _object, _site_map, calculate, loads
from .compact import ResourceLimit, _integer
from .modular_rewrite import rewrite_circuit, verify_rewrite
from .phase_backend import PowerPhaseCircuit, prepare


INPUT_SCHEMA = "nrqc-circuit-goal-v1"
OUTPUT_SCHEMA = "nrqc-circuit-synthesis-v1"
GATES = ("h", "x", "z", "cx")
DEFAULT_LIMITS = dict(max_gates=6, max_candidates=20000, max_work=5_000_000,
                      max_seconds=30)


def _goal(document):
    _object(document, ("schema", "n_qubits", "stabilizers"),
            ("allowed_gates", "coupling_map", "limits"))
    if document["schema"] != INPUT_SCHEMA:
        raise ValueError("unsupported circuit-goal schema")
    n = _integer(document["n_qubits"], "qubits", 1, 4)
    stabilizers = document["stabilizers"]
    if not isinstance(stabilizers, list) or len(stabilizers) != n:
        raise ValueError("require n_qubits independent commuting stabilizers")
    masks = []
    normalized = []
    pivots = {}
    for item in stabilizers:
        _object(item, ("paulis", "eigenvalue"))
        paulis = _site_map(item["paulis"], n, paulis=True)
        sign = _integer(item["eigenvalue"], "eigenvalue", -1, 1)
        if sign == 0:
            raise ValueError("stabilizer eigenvalue must be -1 or +1")
        x = sum(1 << q for q, p in paulis.items() if p in ("X", "Y"))
        z = sum(1 << q for q, p in paulis.items() if p in ("Z", "Y"))
        if any(((x & b).bit_count() + (z & a).bit_count()) % 2
               for a, b in masks):
            raise ValueError("target stabilizers must commute")
        row = x | (z << n)
        while row:
            pivot = row.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = row
                break
            row ^= pivots[pivot]
        if not row:
            raise ValueError("target stabilizers must be independent and nonidentity")
        masks.append((x, z))
        normalized.append(dict(paulis={str(q): p for q, p in paulis.items()},
                               eigenvalue=sign))
    gates = document.get("allowed_gates", list(GATES))
    if (not isinstance(gates, list) or not gates or
            any(not isinstance(g, str) or g not in GATES for g in gates) or
            len(set(gates)) != len(gates)):
        raise ValueError("allowed_gates must be a nonempty unique subset of h/x/z/cx")
    edges = document.get("coupling_map", [[a, b] for a in range(n)
                                         for b in range(n) if a != b])
    if not isinstance(edges, list):
        raise ValueError("coupling_map must be a list of directed pairs")
    seen = set()
    for edge in edges:
        if not isinstance(edge, list) or len(edge) != 2:
            raise ValueError("coupling edge must contain two wire indices")
        a, b = (_integer(q, "coupling wire", 0, n - 1) for q in edge)
        if a == b or (a, b) in seen:
            raise ValueError("coupling edges must be distinct and join different wires")
        seen.add((a, b))
    supplied = document.get("limits", {})
    _object(supplied, (), DEFAULT_LIMITS)
    limits = dict(DEFAULT_LIMITS, **supplied)
    for name, high in (("max_gates", 8), ("max_candidates", 100000),
                       ("max_work", 1_000_000_000)):
        _integer(limits[name], name, 0 if name == "max_gates" else 1, high)
    seconds = limits["max_seconds"]
    if (type(seconds) not in (int, float) or not math.isfinite(seconds) or
            not 0 < seconds <= 300):
        raise ValueError("max_seconds must be finite and in (0,300]")
    return dict(schema=INPUT_SCHEMA, n_qubits=n, stabilizers=normalized,
                allowed_gates=gates, coupling_map=edges, limits=limits)


def _circuit(n, operations):
    out = PowerPhaseCircuit(n, 8)
    for name, wires in operations:
        out.add(name, *wires)
    return out


def _state_key(state):
    """Exact state-ray identity; stabilizer goals ignore only a global phase."""
    first = min(state.amplitudes)
    pivot = state.amplitudes[first]
    return tuple((q, value / pivot) for q, value in sorted(state.amplitudes.items()))


def synthesize(document):
    """Search declared gate words; return a circuit only after exact checking.

    State deduplication is valid for the all-zero state-preparation goal, with
    the same future gates available at each node. It does not equate unitaries
    on arbitrary inputs. Candidate and work exhaustion return no partial circuit.
    """
    goal = _goal(document)
    limits = goal["limits"]
    n = goal["n_qubits"]
    started = time.perf_counter()
    resources = dict(candidate_checks=0, evaluated_states=0, duplicate_states=0,
                     rewrite_pruned=0, exact_work=0, hardware_jobs=0)
    examples = []
    actions = []
    for name in goal["allowed_gates"]:
        wires = goal["coupling_map"] if name == "cx" else [[q] for q in range(n)]
        actions.extend((name, tuple(qs)) for qs in wires)
    frontier = deque([()])
    seen = set()
    depth_limited = False

    def remaining_work():
        remaining = limits["max_work"] - resources["exact_work"]
        if remaining <= 0:
            raise ResourceLimit("whole synthesis-run exact-work budget exhausted")
        return remaining

    def result(status, reason, **fields):
        return dict(schema=OUTPUT_SCHEMA, status=status, reason=reason,
                    evidence_class="LOCAL_IDEAL_CALCULATION",
                    input_state="all_zero", goal=goal, goal_sha256=_digest(goal),
                    resources=dict(resources), wall_seconds=time.perf_counter() - started,
                    rewrite_examples=examples, calculator_request=None,
                    optimality_certified=False, **fields)

    try:
        while frontier:
            if time.perf_counter() - started >= limits["max_seconds"]:
                return result("incomplete", "wall-time budget exhausted")
            if resources["candidate_checks"] >= limits["max_candidates"]:
                return result("incomplete", "candidate budget exhausted")
            operations = frontier.popleft()
            resources["candidate_checks"] += 1
            circuit = _circuit(n, operations)
            reduced = rewrite_circuit(circuit, lookback=8, max_checks=128)
            if reduced.statistics["removed_gates"]:
                proof = verify_rewrite(circuit, reduced.circuit, reduced.certificate)
                resources["rewrite_pruned"] += 1
                if len(examples) < 4:
                    examples.append(dict(source=[[g, list(q)] for g, q in operations],
                                         result=[[g, list(q)] for g, q in reduced.circuit.operations],
                                         certificate=reduced.certificate, verification=proof))
                continue
            state = None
            try:
                state = prepare(circuit, max_work=remaining_work(), max_branches=16)
                resources["evaluated_states"] += 1
                key = _state_key(state)
                if key in seen:
                    resources["duplicate_states"] += 1
                    continue
                seen.add(key)
                matched = all(state.expectation({int(q): p for q, p in s["paulis"].items()})
                              == state.field(s["eigenvalue"]) for s in goal["stabilizers"])
            finally:
                if state is not None:
                    resources["exact_work"] += state.budget.stats["work_used"]
            if matched:
                request = dict(schema="nrqc-calculator-v1", n_qubits=n,
                               backend="cyclotomic_pow2",
                               operations=[[g, list(q)] for g, q in operations],
                               queries=[dict(id=f"stabilizer_{i}", kind="expectation",
                                             paulis=s["paulis"])
                                        for i, s in enumerate(goal["stabilizers"])],
                               limits=dict(max_work=remaining_work(), max_branches=16))
                verification = calculate(request)
                resources["exact_work"] += verification.get("statistics", {}).get("work_used", 0)
                if verification["status"] != "completed":
                    return result("incomplete", "calculator verification exhausted its budget")
                if any(state.field.from_dict(a["value"]["exact"]) != state.field(s["eigenvalue"])
                       for a, s in zip(verification["answers"], goal["stabilizers"], strict=True)):
                    raise ArithmeticError("calculator rejected a synthesized target")
                if time.perf_counter() - started >= limits["max_seconds"]:
                    return result("incomplete", "wall-time budget exhausted during verification")
                out = result("verified", "all independent target stabilizers matched exactly",
                             verification=verification, rewrite_certificate=reduced.certificate,
                             rewrite_verification=verify_rewrite(circuit, circuit, reduced.certificate),
                             derivation=[dict(rule="append_directed_cx" if g == "cx" else "append_local_gate",
                                              operation=[g, list(q)], source_index=i)
                                         for i, (g, q) in enumerate(operations)])
                out["calculator_request"] = request
                return out
            if len(operations) == limits["max_gates"]:
                depth_limited = True
                continue
            frontier.extend(operations + (action,) for action in actions)
    except ResourceLimit as error:
        if state is None:
            resources["exact_work"] += getattr(error, "statistics", {}).get("work_used", 0)
        return result("incomplete", str(error))
    return result("depth_limit" if depth_limited else "search_exhausted",
                  "no matching circuit in the explored gate words")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON goal path, or - for stdin")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        with (sys.stdin.buffer if args.input == "-" else Path(args.input).open("rb")) as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        document = loads(raw.decode("utf-8"))
        result = synthesize(document)
    except (ValueError, TypeError, OSError, RecursionError) as error:
        result = dict(schema=OUTPUT_SCHEMA, status="invalid_request", error=str(error),
                      calculator_request=None)
    except (ArithmeticError, MemoryError) as error:
        result = dict(schema=OUTPUT_SCHEMA, status="calculation_error", error=str(error),
                      calculator_request=None)
    rendered = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "verified" else (2 if result["status"] == "invalid_request" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
