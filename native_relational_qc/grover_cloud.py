"""Four-item Grover search with an ideal reference and an IBM Sampler job."""
import argparse
import json

from .examples import grover_search

TARGETS = ("00", "01", "10", "11")
PROTOCOL = "nrqc-four-target-grover-v1"
PARITY_PROTOCOL = "nrqc-two-bit-parity-decode-v1"
SEED = 117


def protocol_name(parity):
    return PARITY_PROTOCOL if parity else PROTOCOL


def metadata(target, shots, parity=False):
    return {"protocol": protocol_name(parity), "target": target, "shots": shots,
            "native_sha256": grover_search(target, parity=parity).digest()}


def ideal(parity=False):
    return {"evidence_class": "LOCAL_IDEAL_CALCULATION", "protocol": protocol_name(parity),
            "hardware_job_id": None,
            "probabilities": {t: grover_search(t, parity=parity).probabilities() for t in TARGETS}}


def prepare(backend, shots, parity=False):
    from .qiskit_adapter import compile_for_target

    circuits = []
    for target in TARGETS:
        circuit = grover_search(target, parity=parity)
        isa = compile_for_target(circuit, backend.target, seed_transpiler=SEED)
        isa.metadata = metadata(target, shots, parity)
        circuits.append(isa)
    return circuits


def submit(backend_name, shots, parity=False):
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

    service = QiskitRuntimeService()
    matches = service.backends(name=backend_name, operational=True, simulator=False)
    if not matches:
        raise ValueError(f"No accessible operational QPU named {backend_name!r}")
    backend = matches[0]
    circuits = prepare(backend, shots, parity)
    job = SamplerV2(mode=backend).run(circuits, shots=shots)
    return {"evidence_class": "IBM_JOB_SUBMITTED", "protocol": protocol_name(parity),
            "backend": backend.name, "hardware_job_id": job.job_id(),
            "shots_per_target": shots, "total_shots": len(TARGETS) * shots}


def summarize(pubs, parity=False):
    if len(pubs) != len(TARGETS):
        raise ValueError("Expected four search results")
    rows = {}
    expected_shots = None
    for target, pub in zip(TARGETS, pubs):
        meta = pub.metadata.get("circuit_metadata", {})
        shots = meta.get("shots")
        if (type(shots) is not int or not 1 <= shots <= 4096
                or meta != metadata(target, shots, parity)
                or expected_shots not in (None, shots)):
            raise ValueError("Inconsistent search circuit, target order, or shot metadata")
        expected_shots = shots
        counts = pub.data.c.get_counts()
        if (set(counts) - set(TARGETS) or sum(counts.values()) != shots
                or any(type(n) is not int or n < 0 for n in counts.values())):
            raise ValueError("Invalid two-bit counts or shot total")
        # Independent classical inverse, used only to score the measurements.
        high, low = map(int, target)
        solution = f"{high ^ low}{low}" if parity else target
        hits = counts.get(solution, 0)
        rows[target] = {"solution": solution, "counts": counts, "shots": shots,
                        "target_frequency": hits / shots,
                        "unique_mode_is_target": all(hits > counts.get(t, 0)
                                                     for t in TARGETS if t != solution)}
    return rows


def collect(job_id):
    from qiskit_ibm_runtime import QiskitRuntimeService

    job = QiskitRuntimeService().job(job_id)
    backend = job.backend()
    if backend.configuration().simulator:
        raise ValueError("Hardware results require a physical backend")
    pubs = job.result()
    if not len(pubs):
        raise ValueError("Empty job result")
    parity = pubs[0].metadata.get("circuit_metadata", {}).get("protocol") == PARITY_PROTOCOL
    return {"evidence_class": "IBM_QPU_COUNTS", "protocol": protocol_name(parity),
            "backend": backend.name, "hardware_job_id": job.job_id(),
            "cases": summarize(pubs, parity)}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="nrqc grover-cloud", description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    ideal_parser = actions.add_parser("ideal", help="solve all four cases locally")
    submit_parser = actions.add_parser("submit", help="submit one physical QPU job")
    for action in (ideal_parser, submit_parser):
        action.add_argument("--parity", action="store_true",
                            help="decode (x1 XOR x0, x0) instead of matching a bitstring")
    submit_parser.add_argument("--backend", required=True)
    submit_parser.add_argument("--shots", type=int, default=256, help="shots per target")
    actions.add_parser("collect", help="retrieve an existing job").add_argument("job_id")
    args = parser.parse_args(argv)
    if args.action == "ideal":
        report = ideal(args.parity)
    elif args.action == "submit":
        if not 1 <= args.shots <= 4096:
            parser.error("shots per target must be in 1..4096")
        report = submit(args.backend, args.shots, args.parity)
    else:
        report = collect(args.job_id)
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0
