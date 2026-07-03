#!/usr/bin/env python3
"""Backend comparison layer for Quantum Native Bridge Pro.

This module compares the same quantum workload across multiple backend/session
observations. It is dependency-free and evidence-oriented: each backend gets an
expected-model evaluation, and every pair of backends receives a distribution
separation score.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .expected_models import ExpectedModel, evaluate_expected_model, l1_gap, load_model, normalize_distribution


@dataclass(frozen=True)
class BackendObservation:
    backend_id: str
    observed_counts: Dict[str, int]
    session_id: str = ""
    calibration_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BackendComparisonReport:
    report_type: str
    model_id: str
    backends: int
    classification: str
    max_backend_gap: float
    mean_backend_gap: float
    recognized_backends: int
    bounded_backends: int
    actionable_backends: int
    backend_results: List[Dict[str, Any]]
    pairwise_backend_gaps: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_observations(path: str | Path) -> List[BackendObservation]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "observations" in data:
        data = data["observations"]
    observations: List[BackendObservation] = []
    for idx, item in enumerate(data, start=1):
        observations.append(
            BackendObservation(
                backend_id=str(item.get("backend_id", f"backend-{idx}")),
                observed_counts={str(k): int(v) for k, v in dict(item["observed_counts"]).items()},
                session_id=str(item.get("session_id", "")),
                calibration_id=str(item.get("calibration_id", "")),
                metadata=dict(item.get("metadata", {})),
            )
        )
    return observations


def pairwise_gaps(observations: Iterable[BackendObservation]) -> List[Dict[str, Any]]:
    obs = list(observations)
    gaps: List[Dict[str, Any]] = []
    for left, right in itertools.combinations(obs, 2):
        gap = l1_gap(normalize_distribution(left.observed_counts), normalize_distribution(right.observed_counts))
        gaps.append(
            {
                "left_backend": left.backend_id,
                "right_backend": right.backend_id,
                "distribution_gap": gap,
                "left_session_id": left.session_id,
                "right_session_id": right.session_id,
            }
        )
    return gaps


def classify_backend_comparison(max_gap: float, actionable_backends: int, tolerance: float) -> str:
    if actionable_backends:
        return "BACKEND_ACTIONABLE_DIVERGENCE"
    if max_gap <= tolerance:
        return "BACKEND_CONSENSUS_RECOGNITION"
    if max_gap <= 2.0 * tolerance:
        return "BACKEND_BOUNDED_DIVERGENCE"
    return "BACKEND_ACTIONABLE_DIVERGENCE"


def compare_backends(model: ExpectedModel, observations: Iterable[BackendObservation], backend_gap_tolerance: float | None = None) -> BackendComparisonReport:
    obs = list(observations)
    if len(obs) < 2:
        raise ValueError("at least two backend observations are required")
    backend_results: List[Dict[str, Any]] = []
    for item in obs:
        result = evaluate_expected_model(model, item.observed_counts)
        result.update(
            {
                "backend_id": item.backend_id,
                "session_id": item.session_id,
                "calibration_id": item.calibration_id,
                "metadata": item.metadata,
            }
        )
        backend_results.append(result)

    gaps = pairwise_gaps(obs)
    max_gap = max(float(g["distribution_gap"]) for g in gaps)
    mean_gap = sum(float(g["distribution_gap"]) for g in gaps) / len(gaps)
    recognized = sum(1 for r in backend_results if r["classification"] == "RECOGNITION")
    bounded = sum(1 for r in backend_results if r["classification"] == "BOUNDED_RESIDUE")
    actionable = sum(1 for r in backend_results if r["classification"] == "ACTIONABLE_RESIDUE")
    tolerance = float(backend_gap_tolerance if backend_gap_tolerance is not None else model.tolerance)
    classification = classify_backend_comparison(max_gap, actionable, tolerance)

    return BackendComparisonReport(
        report_type="QUANTUM_BACKEND_COMPARISON_REPORT",
        model_id=model.model_id,
        backends=len(obs),
        classification=classification,
        max_backend_gap=max_gap,
        mean_backend_gap=mean_gap,
        recognized_backends=recognized,
        bounded_backends=bounded,
        actionable_backends=actionable,
        backend_results=backend_results,
        pairwise_backend_gaps=gaps,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Quantum backend comparison")
    parser.add_argument("--model", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    report = compare_backends(load_model(args.model), load_observations(args.observations))
    text = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
