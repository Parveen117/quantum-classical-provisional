"""Idempotent saved-model observations in the existing recognition bridge ledger."""
import argparse
from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path

from quantum_native_bridge_pro import BridgeRecord, QuantumNativeBridge, VerificationError
from quantum_native_bridge_pro.bridge import HASH_ALG, digest_payload, measurement_metrics

from .calculator import MAX_INPUT_BYTES, loads
from .compact import ResourceLimit
from .model_experiment import verify_observation


def _identity(report):
    acquired = report["acquisition"]
    return [acquired[k] for k in ("provider", "backend", "job_id")]


def _payload(report):
    payload = copy.deepcopy(report["bridge_payload"])
    payload["metadata"].update(nrqc_observation=copy.deepcopy(report),
                               nrqc_observation_fingerprint=report["fingerprint"],
                               nrqc_acquisition_identity=_identity(report),
                               nrqc_exact_classification=report["classification"])
    return payload


class _SnapshotBridge(QuantumNativeBridge):
    def __init__(self, path, records):
        self.path, self.records = path, records

    def read_records(self):
        return self.records


def _bridge(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("experiment ledger must be an existing regular file")
    with path.open("rb") as stream:
        data = stream.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("experiment ledger exceeds 64 MiB")
    # Legacy readers are permissive about duplicate JSON keys. The NRQC entry
    # point is strict before asking the existing bridge to parse the same bytes.
    records = []
    for line in data.decode("utf-8").splitlines():
        if line.strip():
            try:
                records.append(BridgeRecord.from_dict(loads(line)))
            except (ValueError, TypeError) as error:
                raise ValueError("invalid experiment ledger record") from error
    bridge = _SnapshotBridge(path, records)
    chain = bridge.verify_chain()
    if chain["records"] > 256:
        raise ValueError("experiment ledger exceeds the 256-record replay bound")
    return bridge, chain


@contextmanager
def _exclusive(path):
    """Single writer among this adapter's callers; never steals a stale lock."""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".nrqc-lock")
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise ValueError("experiment ledger is busy; its writer lock already exists") from error
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        yield path
    finally:
        os.close(descriptor)
        lock.unlink()


def record_observation(report, ledger):
    """Append once per frozen plan and provider/backend/job acquisition identity."""
    verify_observation(report)
    identity = _identity(report)
    with _exclusive(ledger) as path:
        if not path.exists():
            path.touch(mode=0o600)
        bridge, chain = _bridge(path)
        for record in bridge.read_records():
            previous = record.metadata.get("nrqc_observation")
            if previous is None:
                continue
            same_job = _identity(previous) == identity
            same_plan = previous["plan"]["fingerprint"] == report["plan"]["fingerprint"]
            if same_job or same_plan:
                if previous != report:
                    raise ValueError("acquisition identity or frozen plan already has a different result")
                _verify_record(record, report)
                return dict(status="already_recorded", observation_fingerprint=report["fingerprint"],
                            sequence=record.sequence, chain_hash=record.chain_hash,
                            ledger_head=chain["head_chain_hash"], appended=False)
        if chain["records"] >= 256:
            raise ValueError("experiment ledger has reached its 256-record bound")
        record = bridge.append(**_payload(report))
        _bridge(path)
        return dict(status="recorded", observation_fingerprint=report["fingerprint"],
                    sequence=record.sequence, chain_hash=record.chain_hash,
                    ledger_head=record.chain_hash, appended=True)


def _verify_record(record, report):
    payload = _payload(report)
    for key in ("root", "template", "phase"):
        if getattr(record, key + "_hash") != digest_payload(payload[key]):
            raise ValueError("ledger record differs from its observation's " + key + " binding")
    recognition = measurement_metrics(record.root_hash, record.template_hash, record.phase_hash,
                                      payload["observed"], expected_model=payload["expected_model"])
    if (record.hash_alg != HASH_ALG or record.backend != payload["backend"] or
            record.shots != payload["shots"] or record.metadata != payload["metadata"] or
            record.recognition != recognition or record.observed_hash != recognition["observed_hash"]):
        raise ValueError("ledger record differs from replayed observation metadata or metrics")


def verify_experiment_ledger(ledger):
    """Verify the hash chain and re-execute every embedded NRQC observation."""
    bridge, chain = _bridge(ledger)
    identities, plans, classifications, origins = set(), set(), {}, {}
    legacy = checked = 0
    for record in bridge.read_records():
        report = record.metadata.get("nrqc_observation")
        if report is None:
            if any(key.startswith("nrqc_") for key in record.metadata):
                raise ValueError("NRQC ledger metadata is missing its replayable observation")
            legacy += 1
            continue
        verify_observation(report)
        _verify_record(record, report)
        identity = tuple(_identity(report))
        plan = report["plan"]["fingerprint"]
        if identity in identities or plan in plans:
            raise ValueError("duplicate acquisition or frozen plan in experiment ledger")
        identities.add(identity)
        plans.add(plan)
        cls, origin = report["classification"], report["evidence_class"]
        classifications[cls] = classifications.get(cls, 0) + 1
        origins[origin] = origins.get(origin, 0) + 1
        checked += 1
    return dict(schema="nrqc-experiment-ledger-verification-v1", status="verified",
                chain=chain, observations_replayed=checked, legacy_records=legacy,
                exact_classifications=classifications, declared_origins=origins,
                source_authentication="not_performed", hardware_submissions=0)


def main(argv=None, *, replay=False):
    parser = argparse.ArgumentParser(description=__doc__)
    if not replay:
        parser.add_argument("input", type=Path)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        if replay:
            output = verify_experiment_ledger(args.ledger)
        else:
            with args.input.open("rb") as stream:
                report = loads(stream.read(MAX_INPUT_BYTES + 1).decode("utf-8"))
            output = record_observation(report, args.ledger)
        code = 0
    except (ValueError, TypeError, KeyError, OSError, VerificationError) as error:
        output, code = dict(status="invalid_request", error=str(error)), 2
    except ResourceLimit as error:
        output, code = dict(status="incomplete", error=str(error)), 1
    except ArithmeticError as error:
        output, code = dict(status="verification_failed", error=str(error)), 1
    rendered = json.dumps(output, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.out:
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return code
