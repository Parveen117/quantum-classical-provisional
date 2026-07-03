#!/usr/bin/env python3
"""Expected distribution models for Quantum Native Bridge Pro.

This module upgrades the bridge from a generic hash expectation into named
quantum workload expectations. It is still dependency-free, so it can run in
Jupyter, CI, and patent evidence packages without vendor lock-in.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class ExpectedModel:
    model_id: str
    model_type: str
    distribution: Dict[str, float]
    tolerance: float = 0.15
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "ExpectedModel":
        return ExpectedModel(
            model_id=str(data["model_id"]),
            model_type=str(data.get("model_type", "custom")),
            distribution=normalize_distribution(dict(data["distribution"])),
            tolerance=float(data.get("tolerance", 0.15)),
            metadata=dict(data.get("metadata", {})),
        )


def normalize_distribution(distribution: Mapping[str, int | float]) -> Dict[str, float]:
    total = float(sum(float(v) for v in distribution.values()))
    if total <= 0:
        raise ValueError("distribution must have positive total")
    return {str(k): float(v) / total for k, v in sorted(distribution.items())}


def l1_gap(expected: Mapping[str, float], observed: Mapping[str, int | float]) -> float:
    exp = normalize_distribution(expected)
    obs = normalize_distribution(observed)
    keys = set(exp) | set(obs)
    return sum(abs(exp.get(k, 0.0) - obs.get(k, 0.0)) for k in keys) / 2.0


def classify_gap(gap: float, tolerance: float) -> str:
    if gap <= tolerance:
        return "RECOGNITION"
    if gap <= 2.0 * tolerance:
        return "BOUNDED_RESIDUE"
    return "ACTIONABLE_RESIDUE"


def bell_model(model_id: str = "bell_phi_plus", tolerance: float = 0.08) -> ExpectedModel:
    return ExpectedModel(
        model_id=model_id,
        model_type="bell_state",
        distribution={"00": 0.5, "01": 0.0, "10": 0.0, "11": 0.5},
        tolerance=tolerance,
        metadata={"description": "Bell Phi+ style correlated pair in Z basis"},
    )


def single_qubit_bias_model(p0: float, model_id: str = "single_qubit_bias", tolerance: float = 0.10) -> ExpectedModel:
    p0 = max(0.0, min(1.0, float(p0)))
    return ExpectedModel(
        model_id=model_id,
        model_type="single_qubit_bias",
        distribution={"0": p0, "1": 1.0 - p0},
        tolerance=tolerance,
        metadata={"description": "Single qubit biased measurement expectation"},
    )


def ghz_model(qubits: int, model_id: Optional[str] = None, tolerance: float = 0.10) -> ExpectedModel:
    if qubits < 2:
        raise ValueError("GHZ model requires at least two qubits")
    zero = "0" * qubits
    one = "1" * qubits
    return ExpectedModel(
        model_id=model_id or f"ghz_{qubits}",
        model_type="ghz_state",
        distribution={zero: 0.5, one: 0.5},
        tolerance=tolerance,
        metadata={"description": f"{qubits}-qubit GHZ endpoint distribution"},
    )


def model_from_template(template: Mapping[str, Any]) -> ExpectedModel:
    name = str(template.get("expected_model", template.get("model", "custom"))).lower()
    if name in {"bell", "bell_phi_plus", "bell-state", "bell_state"}:
        return bell_model(tolerance=float(template.get("tolerance", 0.08)))
    if name in {"ghz", "ghz_state"}:
        return ghz_model(int(template.get("qubits", 3)), tolerance=float(template.get("tolerance", 0.10)))
    if name in {"single", "single_qubit_bias"}:
        return single_qubit_bias_model(float(template.get("p0", 0.5)), tolerance=float(template.get("tolerance", 0.10)))
    if "distribution" in template:
        return ExpectedModel.from_dict({
            "model_id": str(template.get("model_id", "custom_distribution")),
            "model_type": "custom",
            "distribution": dict(template["distribution"]),
            "tolerance": float(template.get("tolerance", 0.15)),
            "metadata": dict(template.get("metadata", {})),
        })
    return ExpectedModel(
        model_id="uniform_fallback",
        model_type="fallback",
        distribution={"0": 0.5, "1": 0.5},
        tolerance=0.25,
        metadata={"description": "Fallback only; prefer a circuit-specific model"},
    )


def evaluate_expected_model(model: ExpectedModel, observed: Mapping[str, int | float]) -> Dict[str, Any]:
    gap = l1_gap(model.distribution, observed)
    cls = classify_gap(gap, model.tolerance)
    return {
        "model_id": model.model_id,
        "model_type": model.model_type,
        "expected_distribution": normalize_distribution(model.distribution),
        "observed_distribution": normalize_distribution(observed),
        "distribution_gap": gap,
        "tolerance": model.tolerance,
        "classification": cls,
        "recognized": cls == "RECOGNITION",
    }


def load_model(path: str | Path) -> ExpectedModel:
    return ExpectedModel.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Expected model evaluator")
    parser.add_argument("--model", help="expected model JSON file")
    parser.add_argument("--template", help="template JSON file used to derive model")
    parser.add_argument("--observed", required=True, help="observed counts JSON file")
    parser.add_argument("--out")
    args = parser.parse_args()

    observed = json.loads(Path(args.observed).read_text(encoding="utf-8"))
    if args.model:
        model = load_model(args.model)
    elif args.template:
        model = model_from_template(json.loads(Path(args.template).read_text(encoding="utf-8")))
    else:
        model = bell_model()
    result = evaluate_expected_model(model, observed)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
