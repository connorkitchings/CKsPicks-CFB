#!/usr/bin/env python3
"""Retired compatibility marker for preseason training."""

raise SystemExit(
    "Preseason training now uses the canonical entry point: "
    "PYTHONPATH=src uv run python -m cks_picks_cfb.train "
    "experiment=preseason_regimes"
)
