#!/usr/bin/env python3
"""Run and optionally write the deterministic 9-qubit Shor-code certificate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qec_shor import build_shor_campaign_certificate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="optional certificate JSON output path")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    certificate = build_shor_campaign_certificate()
    rendered = json.dumps(
        certificate,
        sort_keys=True,
        indent=None if args.compact else 2,
        separators=(",", ":") if args.compact else None,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if certificate["classification"] == "PASS_BOUNDED_SHOR_QEC_V1" else 1


if __name__ == "__main__":
    raise SystemExit(main())
