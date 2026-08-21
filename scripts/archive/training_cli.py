#!/usr/bin/env python3
"""Retired compatibility marker for the former Typer training wrapper."""

raise SystemExit(
    "This wrapper is retired. Use the canonical entry point: "
    "PYTHONPATH=src uv run python -m cks_picks_cfb.train [Hydra overrides]"
)
