#!/usr/bin/env python3
"""Quantum Native Bridge Pro
=========================

A deployable, dependency-free quantum-classical verification bridge for hybrid
quantum jobs, simulator outputs, measurement-result streams, and control-loop
experiments.

This module is a runtime verification and recognition-residue layer around
quantum-classical workflows:

Root     = intended classical payload / circuit identity / Hamiltonian identity
Template = declared lawful circuit, gate, measurement, correction, or control path
Phase    = quantum phase/context/noise/timing/backend/session binding
Observed = measured bitstring distribution or reported classical result
Ledger   = seam memory of quantum-classical residue

Version 0.4.1 integrates expected-model recognition directly into bridge records.
That removes the old mismatch where the external expected-model evaluator could
recognize a Bell run while the bridge ledger still counted only hash-derived
residue. Machines, unlike committees, can be taught consistency.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import random
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .expected_models import ExpectedModel, evaluate_expected_model, load_model, model_from_template

VERSION = "0.4.1-qbridge-pro"
HASH_ALG = "sha256"
GENESIS_HASH = "0" * 64


class QuantumBridgeError(Exception):
    """Base exception for bridge failures."""


class VerificationError(QuantumBridgeError):
    """Raised when a bridge record or ledger fails verification."""


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def digest_payload(payload: Any) -> str:
    if isinstance(payload, bytes):
        return sha256_hex(payload)
    if isinstance(payload, str):
        return sha256_hex(payload)
    return sha256_hex(canonical_json(payload))


def bit_vector(hex_digest: str, dim: int = 256) -> List[int]:
    raw = bytes.fromhex(hex_digest)
    bits: List[int] = []
    for byte in raw:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits[:dim]


def hamming_distance(a: List[int], b: List[int]) -> int:
    if len(a) != len(b):
        raise ValueError("bit vectors must have equal length")
    return sum(1 for x, y in zip(a, b) if x != y)


def coherence_from_phases(phases: Iterable[float]) -> float:
    values = list(phases)
    if not values:
        return 1.0
    real = sum(math.cos(x) for x in values) / len(values)
    imag = sum(math.sin(x) for x in values) / len(values)
    return math.sqrt(real * real + imag * imag)


def normalize_counts(counts: Mapping[str, int | float]) -> Dict[str, float]:
    total = float(sum(float(v) for v in counts.values()))
    if total <= 0:
        raise QuantumBridgeError("count distribution must have positive total")
    return {str(k): float(v) / total for k, v in sorted(counts.items())}


def l1_distribution_gap(expected: Mapping[str, float], observed: Mapping[str, float]) -> float:
    keys = set(expected) | set(observed)
    return sum(abs(float(expected.get(k, 0.0)) - float(observed.get(k, 0.0))) for k in keys) / 2.0


def deterministic_expected_distribution(root_hash: str, template_hash: str, phase_hash: str) -> Dict[str, float]:
    """Generate a deterministic fallback distribution from hashes.

    This is only a fallback bridge signal. Production workflows should attach a
    circuit-specific expected model, backend model, or simulator-derived model.
    """
    seed = int(sha256_hex(root_hash + template_hash + phase_hash)[:16], 16)
    rng = random.Random(seed)
    raw = [0.05 + rng.random() for _ in range(4)]
    total = sum(raw)
    states = ["00", "01", "10", "11"]
    return {state: raw[i] / total for i, state in enumerate(states)}


def _expected_model_from_any(value: ExpectedModel | Mapping[str, Any] | str | Path | None) -> Optional[ExpectedModel]:
    if value is None:
        return None
    if isinstance(value, ExpectedModel):
        return value
    if isinstance(value, (str, Path)):
        return load_model(value)
    if isinstance(value, Mapping):
        if "distribution" in value and "model_id" in value:
            return ExpectedModel.from_dict(value)
        return model_from_template(value)
    raise TypeError(f"unsupported expected_model type: {type(value)!r}")


def combine_runtime_classification(bridge_class: str, expected_class: Optional[str], phase_coherence: float) -> str:
    """Combine hash/fallback bridge result with circuit expected-model result.

    Expected models are authoritative for known circuits, but phase coherence can
    still downgrade a record. This keeps the ledger scientifically sane instead
    of worshipping a hash fallback like it is a quantum oracle.
    """
    if expected_class is None:
        return bridge_class
    if phase_coherence < 0.80:
        return "ACTIONABLE_RESIDUE"
    if phase_coherence < 0.90 and expected_class == "RECOGNITION":
        return "BOUNDED_RESIDUE"
    return expected_class


def measurement_metrics(
    root_hash: str,
    template_hash: str,
    phase_hash: str,
    observed: Mapping[str, int | float] | str | None,
    phase_angles: Optional[Iterable[float]] = None,
    expected_model: ExpectedModel | Mapping[str, Any] | str | Path | None = None,
) -> Dict[str, Any]:
    root = bit_vector(root_hash)
    template = bit_vector(template_hash)
    phase = bit_vector(phase_hash)
    lawful = [r ^ t ^ p for r, t, p in zip(root, template, phase)]

    expected_dist = deterministic_expected_distribution(root_hash, template_hash, phase_hash)
    expected_model_obj = _expected_model_from_any(expected_model)
    expected_model_result: Optional[Dict[str, Any]] = None

    if isinstance(observed, Mapping):
        observed_dist = normalize_counts(observed)
        fallback_gap = l1_distribution_gap(expected_dist, observed_dist)
        observed_hash = digest_payload(observed_dist)
        if expected_model_obj is not None:
            expected_model_result = evaluate_expected_model(expected_model_obj, observed)
            gap = float(expected_model_result["distribution_gap"])
        else:
            gap = fallback_gap
    elif observed is None:
        observed_dist = expected_dist
        fallback_gap = 0.0
        gap = 0.0
        observed_hash = digest_payload(observed_dist)
    else:
        observed_hash = digest_payload(observed)
        observed_bits = bit_vector(observed_hash)
        fallback_gap = hamming_distance(lawful, observed_bits) / len(lawful)
        gap = fallback_gap
        observed_dist = {}

    coherence = coherence_from_phases(phase_angles or [])
    phase_penalty = max(0.0, 1.0 - coherence)
    bridge_residue_score = min(1.0, fallback_gap + 0.25 * phase_penalty)

    if bridge_residue_score <= 0.08:
        bridge_class = "RECOGNITION"
    elif bridge_residue_score <= 0.25:
        bridge_class = "BOUNDED_RESIDUE"
    else:
        bridge_class = "ACTIONABLE_RESIDUE"

    expected_class = expected_model_result.get("classification") if expected_model_result else None
    combined_class = combine_runtime_classification(bridge_class, expected_class, coherence)
    residue_score = min(1.0, gap + 0.25 * phase_penalty)

    result = {
        "observed_hash": observed_hash,
        "expected_distribution": expected_model_result.get("expected_distribution") if expected_model_result else expected_dist,
        "observed_distribution": expected_model_result.get("observed_distribution") if expected_model_result else observed_dist,
        "distribution_gap": gap,
        "fallback_distribution_gap": fallback_gap,
        "phase_coherence": coherence,
        "phase_penalty": phase_penalty,
        "residue_score": residue_score,
        "bridge_classification": bridge_class,
        "expected_model_classification": expected_class,
        "combined_runtime_classification": combined_class,
        "classification": combined_class,
        "recognized": combined_class == "RECOGNITION",
    }
    if expected_model_result is not None:
        result["expected_model"] = expected_model_result
    return result


@dataclass(frozen=True)
class BridgeRecord:
    record_id: str
    version: str
    timestamp_ns: int
    root_hash: str
    template_hash: str
    phase_hash: str
    observed_hash: str
    previous_hash: str
    sequence: int
    backend: str = "simulated-or-external"
    shots: int = 1024
    metadata: Dict[str, Any] = field(default_factory=dict)
    recognition: Dict[str, Any] = field(default_factory=dict)
    record_hash: str = ""
    chain_hash: str = ""
    hash_alg: str = HASH_ALG

    def hash_payload(self) -> Dict[str, Any]:
        data = dataclasses.asdict(self)
        for key in ("record_hash", "chain_hash"):
            data.pop(key, None)
        return data

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "BridgeRecord":
        return BridgeRecord(**dict(data))


class QuantumNativeBridge:
    """Append-only quantum-classical recognition bridge."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def read_records(self) -> List[BridgeRecord]:
        records: List[BridgeRecord] = []
        for line_no, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                records.append(BridgeRecord.from_dict(json.loads(line)))
            except Exception as exc:
                raise VerificationError(f"Invalid bridge ledger line {line_no}: {exc}") from exc
        return records

    def last_record(self) -> Optional[BridgeRecord]:
        records = self.read_records()
        return records[-1] if records else None

    def append(
        self,
        root: Any,
        template: Any,
        phase: Any,
        observed: Mapping[str, int | float] | str | None = None,
        phase_angles: Optional[Iterable[float]] = None,
        backend: str = "simulated-or-external",
        shots: int = 1024,
        metadata: Optional[Dict[str, Any]] = None,
        expected_model: ExpectedModel | Mapping[str, Any] | str | Path | None = None,
    ) -> BridgeRecord:
        previous = self.last_record()
        previous_hash = previous.chain_hash if previous else GENESIS_HASH
        sequence = previous.sequence + 1 if previous else 1
        root_hash = digest_payload(root)
        template_hash = digest_payload(template)
        phase_hash = digest_payload(phase)
        recognition = measurement_metrics(root_hash, template_hash, phase_hash, observed, phase_angles, expected_model)
        record = BridgeRecord(
            record_id=str(uuid.uuid4()),
            version=VERSION,
            timestamp_ns=time.time_ns(),
            root_hash=root_hash,
            template_hash=template_hash,
            phase_hash=phase_hash,
            observed_hash=recognition["observed_hash"],
            previous_hash=previous_hash,
            sequence=sequence,
            backend=backend,
            shots=shots,
            metadata=metadata or {},
            recognition=recognition,
        )
        record_hash = sha256_hex(canonical_json(record.hash_payload()))
        chain_hash = sha256_hex(canonical_json({"previous_hash": previous_hash, "record_hash": record_hash, "sequence": sequence}))
        final = dataclasses.replace(record, record_hash=record_hash, chain_hash=chain_hash)
        self._atomic_append(final)
        return final

    def _atomic_append(self, record: BridgeRecord) -> None:
        existing = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        new_content = existing + canonical_json(record.to_dict()) + "\n"
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(self.path.parent)) as tmp:
            tmp.write(new_content)
            tmp_path = Path(tmp.name)
        tmp_path.replace(self.path)

    def verify_record(self, record: BridgeRecord, expected_previous_hash: str, expected_sequence: int) -> Tuple[bool, str]:
        if record.previous_hash != expected_previous_hash:
            return False, f"previous_hash mismatch at sequence {record.sequence}"
        if record.sequence != expected_sequence:
            return False, f"sequence mismatch: expected {expected_sequence}, got {record.sequence}"
        record_hash = sha256_hex(canonical_json(record.hash_payload()))
        if record_hash != record.record_hash:
            return False, f"record_hash mismatch at sequence {record.sequence}"
        chain_hash = sha256_hex(canonical_json({"previous_hash": record.previous_hash, "record_hash": record.record_hash, "sequence": record.sequence}))
        if chain_hash != record.chain_hash:
            return False, f"chain_hash mismatch at sequence {record.sequence}"
        return True, "ok"

    def verify_chain(self) -> Dict[str, Any]:
        records = self.read_records()
        previous = GENESIS_HASH
        expected_sequence = 1
        counts = {"RECOGNITION": 0, "BOUNDED_RESIDUE": 0, "ACTIONABLE_RESIDUE": 0}
        bridge_counts = {"RECOGNITION": 0, "BOUNDED_RESIDUE": 0, "ACTIONABLE_RESIDUE": 0}
        expected_counts = {"RECOGNITION": 0, "BOUNDED_RESIDUE": 0, "ACTIONABLE_RESIDUE": 0, "NONE": 0}
        for record in records:
            ok, msg = self.verify_record(record, previous, expected_sequence)
            if not ok:
                raise VerificationError(msg)
            combined = record.recognition.get("combined_runtime_classification", record.recognition.get("classification", "ACTIONABLE_RESIDUE"))
            bridge_cls = record.recognition.get("bridge_classification", record.recognition.get("classification", "ACTIONABLE_RESIDUE"))
            expected_cls = record.recognition.get("expected_model_classification") or "NONE"
            counts[combined] = counts.get(combined, 0) + 1
            bridge_counts[bridge_cls] = bridge_counts.get(bridge_cls, 0) + 1
            expected_counts[expected_cls] = expected_counts.get(expected_cls, 0) + 1
            previous = record.chain_hash
            expected_sequence += 1
        return {
            "valid": True,
            "records": len(records),
            "recognized": counts.get("RECOGNITION", 0),
            "bounded_residue": counts.get("BOUNDED_RESIDUE", 0),
            "actionable_residue": counts.get("ACTIONABLE_RESIDUE", 0),
            "bridge_counts": bridge_counts,
            "expected_model_counts": expected_counts,
            "head_chain_hash": previous,
            "version": VERSION,
        }

    def export_certificate(self) -> Dict[str, Any]:
        verification = self.verify_chain()
        records = self.read_records()
        cert = {
            "certificate_type": "QUANTUM_NATIVE_BRIDGE_PROOF",
            "version": VERSION,
            "hash_alg": HASH_ALG,
            "ledger_path": str(self.path),
            "verification": verification,
            "head_record": records[-1].to_dict() if records else None,
            "issued_at_ns": time.time_ns(),
        }
        cert["certificate_hash"] = sha256_hex(canonical_json(cert))
        return cert


def _parse_json_or_text(value: Optional[str]) -> Any:
    if value is None:
        return None
    path = Path(value)
    if path.exists() and path.is_file():
        text = path.read_text(encoding="utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def cli(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Quantum Native Bridge Pro")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_append = sub.add_parser("append")
    p_append.add_argument("--ledger", required=True)
    p_append.add_argument("--root", required=True)
    p_append.add_argument("--template", required=True)
    p_append.add_argument("--phase", required=True)
    p_append.add_argument("--observed")
    p_append.add_argument("--expected-model", help="expected model JSON file or JSON object")
    p_append.add_argument("--backend", default="simulated-or-external")
    p_append.add_argument("--shots", type=int, default=1024)
    p_append.add_argument("--metadata", default="{}")
    p_append.add_argument("--phase-angles", default="[]", help="JSON list of phase angles in radians")

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--ledger", required=True)

    p_cert = sub.add_parser("certificate")
    p_cert.add_argument("--ledger", required=True)
    p_cert.add_argument("--out")

    args = parser.parse_args(list(argv) if argv is not None else None)
    bridge = QuantumNativeBridge(getattr(args, "ledger", "bridge-ledger.jsonl"))

    if args.cmd == "append":
        rec = bridge.append(
            root=_parse_json_or_text(args.root),
            template=_parse_json_or_text(args.template),
            phase=_parse_json_or_text(args.phase),
            observed=_parse_json_or_text(args.observed),
            expected_model=_parse_json_or_text(args.expected_model),
            phase_angles=json.loads(args.phase_angles),
            backend=args.backend,
            shots=args.shots,
            metadata=json.loads(args.metadata),
        )
        print(canonical_json(rec.to_dict()))
        return 0

    if args.cmd == "verify":
        print(json.dumps(bridge.verify_chain(), indent=2, sort_keys=True))
        return 0

    if args.cmd == "certificate":
        cert = bridge.export_certificate()
        text = json.dumps(cert, indent=2, sort_keys=True)
        if args.out:
            Path(args.out).write_text(text + "\n", encoding="utf-8")
            print(args.out)
        else:
            print(text)
        return 0

    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(cli())
