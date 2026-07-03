#!/usr/bin/env python3
"""Multi-run stability analysis for Quantum Native Bridge Pro.

This layer evaluates repeated quantum-classical runs against an expected model.
It separates one healthy result from a stable operating region, because one run
is a data point and a repeated pattern is evidence. Humanity learned this slowly.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .expected_models import ExpectedModel, evaluate_expected_model, load_model


@dataclass(frozen=True)
class StabilityRun:
    run_id: str
    observed_counts: Dict[str, int]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StabilityReport:
    report_type: str
    model_id: str
    runs: int
    mean_gap: float
    max_gap: float
    min_gap: float
    stdev_gap: float
    recognized: int
    bounded_residue: int
    actionable_residue: int
    stable: bool
    classification: str
    run_results: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_runs(path: str | Path) -> List[StabilityRun]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "runs" in data:
        data = data["runs"]
    runs: List[StabilityRun] = []
    for idx, item in enumerate(data, start=1):
        runs.append(
            StabilityRun(
                run_id=str(item.get("run_id", f"run-{idx}")),
                observed_counts={str(k): int(v) for k, v in dict(item["observed_counts"]).items()},
                metadata=dict(item.get("metadata", {})),
            )
        )
    return runs


def analyze_stability(model: ExpectedModel, runs: Iterable[StabilityRun], stability_tolerance: float | None = None) -> StabilityReport:
    run_list = list(runs)
    if not run_list:
        raise ValueError("at least one run is required")
    results: List[Dict[str, Any]] = []
    for run in run_list:
        result = evaluate_expected_model(model, run.observed_counts)
        result["run_id"] = run.run_id
        result["metadata"] = run.metadata
        results.append(result)

    gaps = [float(r["distribution_gap"]) for r in results]
    recognized = sum(1 for r in results if r["classification"] == "RECOGNITION")
    bounded = sum(1 for r in results if r["classification"] == "BOUNDED_RESIDUE")
    actionable = sum(1 for r in results if r["classification"] == "ACTIONABLE_RESIDUE")
    mean_gap = statistics.mean(gaps)
    stdev_gap = statistics.pstdev(gaps) if len(gaps) > 1 else 0.0
    tolerance = float(stability_tolerance if stability_tolerance is not None else model.tolerance)

    stable = actionable == 0 and mean_gap <= tolerance and max(gaps) <= 2.0 * tolerance
    if stable and recognized == len(results):
        cls = "STABLE_RECOGNITION"
    elif stable:
        cls = "STABLE_BOUNDED_REGION"
    elif actionable < len(results):
        cls = "MIXED_STABILITY_REGION"
    else:
        cls = "UNSTABLE_ACTIONABLE_REGION"

    return StabilityReport(
        report_type="QUANTUM_RUNTIME_STABILITY_REPORT",
        model_id=model.model_id,
        runs=len(results),
        mean_gap=mean_gap,
        max_gap=max(gaps),
        min_gap=min(gaps),
        stdev_gap=stdev_gap,
        recognized=recognized,
        bounded_residue=bounded,
        actionable_residue=actionable,
        stable=stable,
        classification=cls,
        run_results=results,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Quantum runtime stability analysis")
    parser.add_argument("--model", required=True)
    parser.add_argument("--runs", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    report = analyze_stability(load_model(args.model), load_runs(args.runs))
    text = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
