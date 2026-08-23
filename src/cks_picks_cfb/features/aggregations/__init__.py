"""Core aggregation functions for plays -> drives -> team-game -> team-season."""

from cks_picks_cfb.features.aggregations.drives import aggregate_drives
from cks_picks_cfb.features.aggregations.opponent_adjustment import (
    apply_iterative_opponent_adjustment,
)
from cks_picks_cfb.features.aggregations.team_game import (
    aggregate_team_game,
    calculate_st_analytics_agg,
)
from cks_picks_cfb.features.aggregations.team_season import aggregate_team_season

__all__ = [
    "aggregate_drives",
    "aggregate_team_game",
    "aggregate_team_season",
    "apply_iterative_opponent_adjustment",
    "calculate_st_analytics_agg",
]
