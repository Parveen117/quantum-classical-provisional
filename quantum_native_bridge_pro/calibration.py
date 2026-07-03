#!/usr/bin/env python3
"""Calibration and noise-correction helpers for Quantum Native Bridge Pro.

The bridge can run without vendor SDKs, but real quantum workflows need a way to
record calibration, correct simple measurement readout drift, and preserve the
correction evidence. This module provides a small dependency-free implementation
for patent enablement and reproducible testing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple


@dataclass(frozen=True)
class CalibrationProfile:
    profile_id: str
    backend: str
    readout_fidelity: Dict[str, float]
    confusion_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "CalibrationProfile":
        return CalibrationProfile(
            profile_id=str(data["profile_id"]),
            backend=str(data.get("backend", "unknown")),
            readout_fidelity={str(k): float(v) for k, v in dict(data.get("readout_fidelity", {})).items()},
            confusion_matrix={
                str(row): {str(col): float(val) for col, val in dict(cols).items()}
                for row, cols in dict(data.get("confusion_matrix", {})).items()
            },
            metadata=dict(data.get("metadata", {})),
        )


def load_profile(path: str | Path) -> CalibrationProfile:
    return CalibrationProfile.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def normalize_counts(counts: Mapping[str, int | float]) -> Dict[str, float]:
    total = float(sum(float(v) for v in counts.values()))
    if total <= 0:
        raise ValueError("counts must have positive total")
    return {str(k): float(v) / total for k, v in sorted(counts.items())}


def apply_readout_floor(counts: Mapping[str, int | float], profile: CalibrationProfile) -> Dict[str, float]:
    """Apply a conservative fidelity weighting to observed counts.

    This is not a full matrix inversion routine. It is an enablement-safe,
    deterministic correction that records calibration influence without hiding
    residue. Full hardware integrations may replace this with vendor calibration
    matrices or tomography-derived correction.
    """
    dist = normalize_counts(counts)
    weighted: Dict[str, float] = {}
    for state, prob in dist.items():
        fidelity = float(profile.readout_fidelity.get(state, profile.readout_fidelity.get("default", 1.0)))
        weighted[state] = max(0.0, prob * fidelity)
    total = sum(weighted.values())
    if total <= 0:
        return dist
    return {state: value / total for state, value in sorted(weighted.items())}


def calibration_gap(raw_counts: Mapping[str, int | float], corrected_distribution: Mapping[str, float]) -> float:
    raw = normalize_counts(raw_counts)
    keys = set(raw) | set(corrected_distribution)
    return sum(abs(raw.get(k, 0.0) - float(corrected_distribution.get(k, 0.0))) for k in keys) / 2.0


def build_calibrated_observation(
    raw_counts: Mapping[str, int | float], profile: CalibrationProfile
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    corrected = apply_readout_floor(raw_counts, profile)
    gap = calibration_gap(raw_counts, corrected)
    evidence = {
        "calibration_profile_id": profile.profile_id,
        "calibration_backend": profile.backend,
        "calibration_gap": gap,
        "correction_method": "readout_fidelity_weighting",
        "raw_distribution": normalize_counts(raw_counts),
        "corrected_distribution": corrected,
    }
    return corrected, evidence


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Quantum calibration helper")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--counts", required=True, help="JSON counts or path")
    parser.add_argument("--out")
    args = parser.parse_args()

    profile = load_profile(args.profile)
    counts_path = Path(args.counts)
    if counts_path.exists():
        counts = json.loads(counts_path.read_text(encoding="utf-8"))
    else:
        counts = json.loads(args.counts)
    corrected, evidence = build_calibrated_observation(counts, profile)
    result = {"corrected_observation": corrected, "calibration_evidence": evidence}
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
