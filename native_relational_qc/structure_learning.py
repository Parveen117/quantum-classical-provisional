"""Train native phase parameters while searching a declared CX topology family."""
import argparse
from itertools import combinations
import json
from pathlib import Path
import sys
import time

from .compact import ResourceLimit
from .pauli_engine import _conjugate
from .self_learning import (
    DEFAULT_ENTANGLERS, FIELD, Evaluator, _examples, _int, _topology,
    circuit, digest, fit, load_packet, packet,
)


DEFAULT_COUPLINGS = DEFAULT_ENTANGLERS + ((0, 3), (1, 3))


def _readout_context(edges):
    observations = ((1 << 3, 0, 0), (0, 1 << 3, 0))
    trace = []
    invariant = False
    for control, target in reversed(edges):
        gate = ("cx", 1 << control, 1 << target)
        updated = tuple(_conjugate(*row, gate) for row in observations)
        invariant |= updated == observations
        trace.append(dict(edge=[control, target], before=observations, after=updated))
        observations = updated
    support = 0
    for x, z, _ in observations:
        support |= x | z
    return dict(input_support_mask=support, pullback_trace=trace, has_invariant_edge=invariant)


def canonical_readout_model(model):
    """Zero initial-layer rotations on wires absent from both readout pullbacks.

    X3 and Z3 span the observable before the last RY. A tensor factor with I
    is invariant under every initial-layer local rotation on that wire. The
    accepted transformation preserves the q3 probability for every feature.
    """
    parameters = load_packet(model)
    edges = _topology(model.get("entanglers", DEFAULT_ENTANGLERS))
    context = _readout_context(edges)
    unused = [q for q in range(4) if not context["input_support_mask"] & (1 << q)]
    changed = [q for q in unused if parameters[q]]
    normalized = tuple(0 if q in unused else value for q, value in enumerate(parameters))
    output = packet(normalized, training_digest=model["training_sha256"],
                    view=model["feature_view"], entanglers=edges)
    return output, dict(context, zeroed_phase_coordinates=changed,
                        source_model_fingerprint=model["fingerprint"],
                        result_model_fingerprint=output["fingerprint"],
                        scope="q3 readout probability for every feature input")


def topology_candidates(coupling_map=DEFAULT_COUPLINGS, *, max_entanglers=3,
                        max_candidates=32):
    """Ordered subwords whose output-observable pullback uses both inputs.

    Immediately before the last RY, a Z readout is in the span of X3 and Z3.
    The existing exact Pauli engine propagates both backwards through each
    candidate CX word. An invariant gate or missing input rejects that word.
    """
    edges = _topology(coupling_map)
    _int(max_entanglers, "entangler cap", 0, 6)
    _int(max_candidates, "topology budget", 1, 64)
    candidates = []
    for count in range(min(max_entanglers, len(edges)) + 1):
        for word in combinations(edges, count):
            context = _readout_context(word)
            if context["has_invariant_edge"] or context["input_support_mask"] & 3 != 3:
                continue
            if len(candidates) == max_candidates:
                raise ResourceLimit("topology family exceeds the declared candidate budget")
            candidates.append(dict(entanglers=[list(edge) for edge in word],
                                   **context))
    if not candidates:
        raise ValueError("no admitted topology carries both inputs to the readout")
    return candidates


def fit_structure(examples, *, view, coupling_map=DEFAULT_COUPLINGS,
                  max_entanglers=3, max_candidates=32, seeds=(17, 41, 73),
                  sweeps=3, max_circuits=60000, max_work=200_000_000,
                  progress=None):
    """Select on training loss, then CX count, then native training gate count.

    Every admitted topology uses the same phase grid, seeds and sweep cap.
    The API accepts only training examples. One remaining circuit/work budget
    spans all candidates; exhaustion raises without a completed selected model.
    """
    examples = _examples(examples)
    if progress is not None and not callable(progress):
        raise ValueError("progress must be a callable")
    _int(max_circuits, "whole-search circuit budget", 1, 100000)
    _int(max_work, "whole-search work budget", 1, 1_000_000_000)
    candidates = topology_candidates(coupling_map, max_entanglers=max_entanglers,
                                     max_candidates=max_candidates)
    started = time.perf_counter()
    resources = dict(circuit_executions=0, engine_work=0, objective_evaluations=0,
                     cache_hits=0, total_executed_gates=0, peak_support=0, hardware_jobs=0)
    selected = None
    best_loss = None
    best_cost = None
    baseline = None
    records = []
    for index, candidate in enumerate(candidates):
        remaining_circuits = max_circuits - resources["circuit_executions"]
        remaining_work = max_work - resources["engine_work"]
        if min(remaining_circuits, remaining_work) <= 0:
            raise ResourceLimit("whole topology-search budget exhausted")
        edges = _topology(candidate["entanglers"])
        evaluator = Evaluator(max_circuits=remaining_circuits, max_work=remaining_work,
                              entanglers=edges, compiler="fused")
        try:
            trained = fit(examples, view=view, evaluator=evaluator, seeds=seeds, sweeps=sweeps)
        finally:
            for key, value in evaluator.stats.items():
                resources[key] = max(resources[key], value) if key == "peak_support" else resources[key] + value
        model, canonicalization = canonical_readout_model(trained["model"])
        parameters = load_packet(model)
        gate_count = sum(len(circuit(e.features, parameters, entanglers=edges,
                                    compiler="fused").operations) for e in examples)
        cost = len(edges), gate_count
        loss = FIELD.from_dict(trained["loss"]["exact"])
        better = selected is None or (loss - best_loss).real_sign() < 0
        tied = selected is not None and loss == best_loss and cost < best_cost
        if better or tied:
            selected, best_loss, best_cost = index, loss, cost
        if edges == DEFAULT_ENTANGLERS:
            baseline = index
        records.append(dict(candidate=candidate, training=trained, model=model,
                            readout_canonicalization=canonicalization,
                            native_training_gate_total=gate_count, entanglers_per_prediction=len(edges)))
        if progress is not None:
            progress(dict(index=index, entanglers=[list(edge) for edge in edges],
                          training_loss=trained["loss"]["decimal"],
                          circuit_executions=evaluator.stats["circuit_executions"],
                          engine_work=evaluator.stats["engine_work"]))
    return dict(schema="nrqc-structure-learning-v1", model=records[selected]["model"],
                selected_candidate=selected, baseline_candidate=baseline, candidates=records,
                selected_by="training Brier loss, then CX count, then compiled training gate count",
                training_sha256=digest([e.record() for e in examples]),
                protocol=dict(seeds=list(seeds), sweeps=sweeps, compiler="fused",
                              coupling_map=[list(edge) for edge in _topology(coupling_map)],
                              max_entanglers=max_entanglers, max_candidates=max_candidates,
                              max_circuits=max_circuits, max_work=max_work),
                resources=resources, wall_seconds=time.perf_counter() - started,
                global_optimum_certified=False, evidence_class="LOCAL_IDEAL_CALCULATION")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("curvature", "xor"), default="curvature")
    parser.add_argument("--seeds", nargs="+", type=int, default=[17, 41, 73])
    parser.add_argument("--sweeps", type=int, default=3)
    parser.add_argument("--max-circuits", type=int, default=60000)
    parser.add_argument("--max-work", type=int, default=200_000_000)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    from .learning_tasks import curvature_splits, xor_examples
    try:
        if args.task == "xor":
            training, view = xor_examples(), "xor_bits"
        else:
            splits, _ = curvature_splits()
            training, view = splits["train"], "first_layer"
        result = fit_structure(training, view=view, seeds=args.seeds, sweeps=args.sweeps,
                               max_circuits=args.max_circuits, max_work=args.max_work)
        result["status"] = "completed"
    except (ValueError, TypeError) as error:
        result = dict(schema="nrqc-structure-learning-v1", status="invalid_request", error=str(error))
    except ResourceLimit as error:
        result = dict(schema="nrqc-structure-learning-v1", status="incomplete", error=str(error))
    rendered = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "completed" else (2 if result["status"] == "invalid_request" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
