"""Proof-carrying index for the bounded IIT Bombay Qmet evidence stack.

The bundle composes provenance, not scientific claim strength.  Each component
retains its own evidence class and claim boundary.  In particular, IBM QEC
hardware evidence cannot promote a digital-twin sensor result into physical
sensor validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping


HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
GENESIS = "0" * 64
REQUIRED_COMPONENTS = (
    "ibm_shor_hardware_syndrome",
    "rnke_shor_recognition_gate",
    "rnke_hardware_theorem_binding",
    "qseam_nv_odmr_digital_twin",
)
PROHIBITED_AGGREGATE_CLAIMS = (
    "PHYSICAL_SENSOR_VALIDATED",
    "FAULT_TOLERANCE_ESTABLISHED",
    "THRESHOLD_ESTABLISHED",
    "RIEMANN_HYPOTHESIS_PROVED",
    "METROLOGICALLY_TRACEABLE",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_sources(sources: Mapping[str, Any]) -> list[dict[str, Any]]:
    if sources.get("schema") != "qmet-hybrid-evidence-sources-v1":
        raise ValueError("unsupported source-manifest schema")
    if sources.get("composition_policy") != "SEPARATE_EVIDENCE_CLASSES_NO_CROSS_DOMAIN_PROMOTION":
        raise ValueError("unsafe or missing composition policy")
    components = list(sources.get("components", []))
    ids = tuple(item.get("component_id") for item in components)
    if ids != REQUIRED_COMPONENTS:
        raise ValueError("component set or order differs from the predeclared contract")
    classes = [item.get("evidence_class") for item in components]
    if len(set(classes)) != len(classes):
        raise ValueError("evidence classes must remain distinct")
    for item in components:
        for field in ("repository", "path", "observed_outcome", "scope"):
            if not item.get(field):
                raise ValueError(f"{item.get('component_id')}: missing {field}")
        if not HEX40.fullmatch(str(item.get("commit_sha", ""))):
            raise ValueError(f"{item['component_id']}: invalid commit SHA")
        if not HEX40.fullmatch(str(item.get("github_blob_sha", ""))):
            raise ValueError(f"{item['component_id']}: invalid blob SHA")
        if not HEX64.fullmatch(str(item.get("certificate_sha256", ""))):
            raise ValueError(f"{item['component_id']}: invalid certificate SHA-256")
        if item.get("bounded_pass") is not True:
            raise ValueError(f"{item['component_id']}: component did not pass its bounded gate")
        if not item.get("does_not_establish"):
            raise ValueError(f"{item['component_id']}: missing negative claim boundary")
    return components


def validate_qseam_attestation(component: Mapping[str, Any], attestation: Mapping[str, Any]) -> bool:
    expected = {
        "repository": component["repository"],
        "commit_sha": component["commit_sha"],
        "path": component["path"],
        "github_blob_sha": component["github_blob_sha"],
        "campaign_sha256": component["certificate_sha256"],
    }
    if any(attestation.get(key) != value for key, value in expected.items()):
        return False
    return (
        attestation.get("schema") == "qseam-nv-remote-attestation-v1"
        and attestation.get("schema_observed") == "qseam-nv-digital-twin-campaign-v1"
        and attestation.get("all_expected") is True
        and attestation.get("case_count") == 7
        and sum(attestation.get("case_outcomes", {}).values()) == 7
    )


def verify_local_qec_anchors(repo_root: Path, components: list[Mapping[str, Any]]) -> dict[str, bool]:
    """Replay the three same-repository pins when run inside the full checkout."""
    by_id = {item["component_id"]: item for item in components}
    hardware = by_id["ibm_shor_hardware_syndrome"]
    gate = by_id["rnke_shor_recognition_gate"]
    theorem = by_id["rnke_hardware_theorem_binding"]

    hardware_payload = load_json(repo_root / hardware["path"])
    gate_pin = (repo_root / gate["path"]).read_text(encoding="utf-8").split()[0]
    theorem_pin = (repo_root / theorem["path"]).read_text(encoding="utf-8").split()[0]
    return {
        "hardware_internal_certificate_matches":
            hardware_payload.get("certificate_sha256") == hardware["certificate_sha256"],
        "hardware_classification_matches":
            hardware_payload.get("classification") == hardware["observed_outcome"],
        "rnke_gate_pin_matches": gate_pin == gate["certificate_sha256"],
        "theorem_binding_pin_matches": theorem_pin == theorem["certificate_sha256"],
    }


def build_receipts(components: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    parent = GENESIS
    for index, item in enumerate(components):
        source_anchor = {
            "repository": item["repository"],
            "commit_sha": item["commit_sha"],
            "path": item["path"],
            "github_blob_sha": item["github_blob_sha"],
        }
        body = {
            "index": index,
            "parent_receipt_sha256": parent,
            "component_id": item["component_id"],
            "evidence_class": item["evidence_class"],
            "source_anchor_sha256": sha256_json(source_anchor),
            "certificate_sha256": item["certificate_sha256"],
            "observed_outcome": item["observed_outcome"],
            "claim_boundary_sha256": sha256_json(item["does_not_establish"]),
        }
        receipt = {**body, "receipt_sha256": sha256_json(body)}
        receipts.append(receipt)
        parent = receipt["receipt_sha256"]
    return receipts


def verify_receipt_chain(receipts: list[Mapping[str, Any]]) -> bool:
    parent = GENESIS
    for index, receipt in enumerate(receipts):
        body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
        if receipt.get("index") != index:
            return False
        if receipt.get("parent_receipt_sha256") != parent:
            return False
        if receipt.get("receipt_sha256") != sha256_json(body):
            return False
        parent = str(receipt["receipt_sha256"])
    return True


def build_bundle(
    sources: Mapping[str, Any],
    qseam_attestation: Mapping[str, Any],
    local_qec_checks: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    components = validate_sources(sources)
    qseam = next(item for item in components if item["component_id"] == "qseam_nv_odmr_digital_twin")
    qseam_bound = validate_qseam_attestation(qseam, qseam_attestation)
    receipts = build_receipts(components)
    local_checks = dict(local_qec_checks or {})

    checks = {
        "four_predeclared_components_present": len(components) == 4,
        "all_component_bounded_gates_passed": all(item["bounded_pass"] for item in components),
        "evidence_classes_remain_distinct": len({item["evidence_class"] for item in components}) == 4,
        "qseam_remote_attestation_bound": qseam_bound,
        "component_receipt_chain_intact": verify_receipt_chain(receipts),
        "no_cross_domain_promotion": sources["composition_policy"] == "SEPARATE_EVIDENCE_CLASSES_NO_CROSS_DOMAIN_PROMOTION",
        "local_qec_anchor_replay_complete": bool(local_checks) and all(local_checks.values()),
    }
    classification = (
        "PASS_BOUNDED_QMET_HYBRID_EVIDENCE_BUNDLE_V1"
        if all(checks.values())
        else "INCOMPLETE_QMET_HYBRID_EVIDENCE_BUNDLE_V1"
    )
    body: dict[str, Any] = {
        "schema": "qmet-hybrid-evidence-bundle-v1",
        "classification": classification,
        "review_readiness": "READY_FOR_QMET_BOUNDED_POC_REVIEW" if classification.startswith("PASS_") else "NOT_READY",
        "source_manifest_sha256": sha256_json(sources),
        "qseam_attestation_sha256": sha256_json(qseam_attestation),
        "checks": checks,
        "local_qec_anchor_checks": local_checks,
        "component_receipts": receipts,
        "ledger_head_sha256": receipts[-1]["receipt_sha256"],
        "aggregate_truth_table": {
            "hardware_qec_syndrome_observed": True,
            "exact_model_qec_control_verified": True,
            "finite_theorem_hardware_binding_verified": True,
            "digital_twin_sensor_verification_verified": True,
            "physical_sensor_validated": False,
            "metrological_traceability_established": False,
            "fault_tolerance_established": False,
            "threshold_established": False,
            "riemann_hypothesis_claimed": False,
        },
        "prohibited_aggregate_claims": list(PROHIBITED_AGGREGATE_CLAIMS),
        "claim_boundary": (
            "Proof-carrying index of four bounded evidence components. It composes provenance, "
            "not claim strength. QEC hardware evidence does not validate an NV sensor; the Q-Seam "
            "component remains a digital twin until instrument data and traceable calibration exist."
        ),
    }
    body["certificate_sha256"] = sha256_json(body)
    return body


def verify_bundle(bundle: Mapping[str, Any]) -> bool:
    if not HEX64.fullmatch(str(bundle.get("certificate_sha256", ""))):
        return False
    body = {key: value for key, value in bundle.items() if key != "certificate_sha256"}
    if bundle["certificate_sha256"] != sha256_json(body):
        return False
    if not verify_receipt_chain(list(bundle.get("component_receipts", []))):
        return False
    truth = bundle.get("aggregate_truth_table", {})
    return not any(
        (
            truth.get("physical_sensor_validated"),
            truth.get("metrological_traceability_established"),
            truth.get("fault_tolerance_established"),
            truth.get("threshold_established"),
            truth.get("riemann_hypothesis_claimed"),
        )
    )


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, default=here / "qmet_evidence_sources.json")
    parser.add_argument("--qseam-attestation", type=Path, default=here / "qseam_nv_attestation.json")
    parser.add_argument("--repo-root", type=Path, default=here.parents[1])
    parser.add_argument("--output", type=Path, default=here / "generated/qmet_hybrid_evidence_certificate.json")
    args = parser.parse_args()

    sources = load_json(args.sources)
    attestation = load_json(args.qseam_attestation)
    components = validate_sources(sources)
    local_checks = verify_local_qec_anchors(args.repo_root, components)
    certificate = build_bundle(sources, attestation, local_checks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(certificate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"CLASSIFICATION: {certificate['classification']}")
    print(f"READINESS     : {certificate['review_readiness']}")
    print(f"LEDGER HEAD   : {certificate['ledger_head_sha256']}")
    print(f"SHA256        : {certificate['certificate_sha256']}")
    print(f"SAVED         : {args.output}")
    return 0 if certificate["classification"].startswith("PASS_") and verify_bundle(certificate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
