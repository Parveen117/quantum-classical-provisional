#!/usr/bin/env python3
"""Run and optionally write the deterministic QEC laboratory certificate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from qec_repetition import build_campaign_certificate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="optional certificate JSON output path")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    certificate = build_campaign_certificate()
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
    return 0 if certificate["classification"] == "PASS_BOUNDED_QEC_ERROR_CONTROL_V1" else 1


if __name__ == "__main__":
    raise SystemExit(main())
