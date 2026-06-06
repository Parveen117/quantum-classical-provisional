#!/usr/bin/env python3
"""Quantum-Classical Native Ledger Bridge v2
==========================================

A small executable bridge for testing Root--Template--Phase closure in a
quantum-classical interface toy sector.

The bridge compares:
- native_on: residue is seam-compensated and ledgered;
- native_off: residue remains open.

No external dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class Config:
    samples: int = 512
    dim: int = 12
    phase_noise: float = 0.20
    template_rate: float = 0.18
    compensator: float = 0.35
    ledger: float = 0.65
    seed: int = 117
    out: str = "quantum_classical_native_bridge_v2_report.json"


def sha(obj: Dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def agreement(a: List[int], b: List[int]) -> float:
    return sum(1 for x, y in zip(a, b) if x == y) / len(a)


def coherence(phases: List[float]) -> float:
    real = sum(math.cos(p) for p in phases) / len(phases)
    imag = sum(math.sin(p) for p in phases) / len(phases)
    return math.sqrt(real * real + imag * imag)


def run_condition(cfg: Config, native_on: bool) -> Dict:
    rng = random.Random(cfg.seed)
    rows = []
    k = 0.0

    for i in range(1, cfg.samples + 1):
        root = [rng.randrange(2) for _ in range(cfg.dim)]
        template = [1 if rng.random() < cfg.template_rate else 0 for _ in range(cfg.dim)]
        quantum_phase = [rng.uniform(-math.pi, math.pi) for _ in range(cfg.dim)]
        phase_error = [1 if abs(math.sin(p)) < cfg.phase_noise else 0 for p in quantum_phase]

        lawful_classical = [r ^ t for r, t in zip(root, template)]
        measured = [x ^ e for x, e in zip(lawful_classical, phase_error)]

        raw = 0.0
        comp = 0.0
        ledg = 0.0
        open_res = 0.0
        corrected = []

        for lawful, obs in zip(lawful_classical, measured):
            residue = obs - lawful
            raw += abs(residue)
            if native_on:
                c = cfg.compensator * residue
                rest = residue - c
                m = cfg.ledger * rest
                o = rest - m
                k += m
                final = obs if abs(o) > 0.5 else lawful
            else:
                c = 0.0
                m = 0.0
                o = residue
                final = obs
            comp += abs(c)
            ledg += abs(m)
            open_res += abs(o)
            corrected.append(final)

        rows.append({
            "sample": i,
            "root_recognition": agreement(corrected, lawful_classical),
            "phase_coherence": coherence(quantum_phase),
            "G_UGD_native": open_res / raw if raw else 0.0,
            "raw_residue": raw,
            "seam_compensated": comp,
            "ledgered_memory": ledg,
            "open_residue": open_res,
            "k_memory": k,
        })

    keys = [x for x in rows[0] if x != "sample"]
    avg = {key: sum(row[key] for row in rows) / len(rows) for key in keys}
    return {"averages": avg, "rows": rows}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--samples", type=int, default=512)
    p.add_argument("--dim", type=int, default=12)
    p.add_argument("--phase-noise", type=float, default=0.20)
    p.add_argument("--template-rate", type=float, default=0.18)
    p.add_argument("--compensator", type=float, default=0.35)
    p.add_argument("--ledger", type=float, default=0.65)
    p.add_argument("--seed", type=int, default=117)
    p.add_argument("--out", default="quantum_classical_native_bridge_v2_report.json")
    cfg = Config(**vars(p.parse_args()))

    on = run_condition(cfg, True)
    off = run_condition(cfg, False)
    comparison = {
        "delta_root_recognition": on["averages"]["root_recognition"] - off["averages"]["root_recognition"],
        "delta_G_UGD_native": on["averages"]["G_UGD_native"] - off["averages"]["G_UGD_native"],
        "delta_open_residue": on["averages"]["open_residue"] - off["averages"]["open_residue"],
        "native_bridge_advantage": bool(
            on["averages"]["root_recognition"] > off["averages"]["root_recognition"]
            and on["averages"]["G_UGD_native"] < off["averages"]["G_UGD_native"]
        ),
    }
    report = {"marker": "Quantum-Classical-Native-Ledger-Bridge-v2", "config": asdict(cfg), "native_on": on, "native_off": off, "comparison": comparison}
    report["certificate_hash"] = sha(report)
    Path(cfg.out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"certificate_hash": report["certificate_hash"], "comparison": comparison}, indent=2))
    print("report:", cfg.out)


if __name__ == "__main__":
    main()
