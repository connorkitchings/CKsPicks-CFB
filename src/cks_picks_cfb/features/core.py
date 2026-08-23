"""Core aggregation functions for plays -> drives -> team-game -> team-season.

(Shim module re-exporting from cks_picks_cfb.features.aggregations)
"""

from cks_picks_cfb.features.aggregations import (
    aggregate_drives,
    aggregate_team_game,
    aggregate_team_season,
    apply_iterative_opponent_adjustment,
    calculate_st_analytics_agg,
)

__all__ = [
    "aggregate_drives",
    "aggregate_team_game",
    "aggregate_team_season",
    "apply_iterative_opponent_adjustment",
    "calculate_st_analytics_agg",
]
