#!/usr/bin/env python3
"""Command-line entrypoint for Quantum Native Bridge Pro."""

from .bridge import cli

if __name__ == "__main__":
    raise SystemExit(cli())
