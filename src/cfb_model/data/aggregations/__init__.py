"""Aggregation utilities for transforming play-level data.

This package contains drive, team-game, and team-season aggregations, as well
as iterative opponent adjustments and a small pre-aggregation pipeline helper.
"""

from .core import (
    aggregate_drives,
    aggregate_team_game,
    aggregate_team_season,
    apply_iterative_opponent_adjustment,
)
from .pipeline import build_preaggregation_pipeline

__all__ = [
    "aggregate_drives",
    "aggregate_team_game",
    "aggregate_team_season",
    "apply_iterative_opponent_adjustment",
    "build_preaggregation_pipeline",
]
