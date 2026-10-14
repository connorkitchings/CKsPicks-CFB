"""Serving-core projection builder (owner: P1).

Builds the serving-core tables of the Step 2 payload from prepared frames, following
the authoritative spec in :mod:`cks_picks_cfb.season.projection_common`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas

SERVING_KEYS = (
    "games",
    "game_results",
    "predictions",
    "prediction_grades",
    "market_quotes",
    "market_snapshots",
    "market_snapshot_quotes",
    "prediction_market_selections",
    "system_stats",
    "site_week_selections",
    "prediction_runs",
)


def build_serving_core(
    *,
    frames: Mapping[str, pandas.DataFrame],
    inputs: Any,
    revision: Mapping[str, Any],
    identity: Mapping[str, str],
    ratings_id: str,
    measurement_id: str,
) -> dict[str, list[dict]]:
    """Return ``{key: rows}`` for exactly :data:`SERVING_KEYS`.

    ``frames`` are the ``prepare.compute`` outputs, ``inputs`` the
    ``inputs.SeasonInputs``, ``revision`` the parsed revision manifest, ``identity``
    the run identity, and ``ratings_id`` / ``measurement_id`` the values of
    ``projection_common.rating_identity`` / ``measurement_identity``.
    """
    raise NotImplementedError
