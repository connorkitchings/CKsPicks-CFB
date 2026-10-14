"""Football-data projection builder (owner: P2).

Builds venue, rating, stat, measurement and publication tables of the Step 2
payload, following the authoritative spec in
:mod:`cks_picks_cfb.season.projection_common`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas

FOOTBALL_KEYS = (
    "game_venues",
    "v5_rating_snapshots",
    "team_season_stats",
    "matchup_data_publications",
    "team_game_measurements",
    "team_possession_stats",
    "team_possession_adjusted",
    "team_rating_components",
)


def build_football(
    *,
    frames: Mapping[str, pandas.DataFrame],
    inputs: Any,
    revision: Mapping[str, Any],
    identity: Mapping[str, str],
    ratings_id: str,
    measurement_id: str,
) -> dict[str, list[dict]]:
    """Return ``{key: rows}`` for exactly :data:`FOOTBALL_KEYS`.

    Arguments are as for ``projection_serving.build_serving_core``.
    """
    raise NotImplementedError
