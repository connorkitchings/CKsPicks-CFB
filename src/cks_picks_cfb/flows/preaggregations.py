"""Prefect flow to run pre-aggregations for a season.

This wraps persist_preaggregations with parameters (year, data_root, verbose).
"""

from __future__ import annotations

from prefect import flow

from cks_picks_cfb.features.persist import persist_preaggregations


@flow(name="Preaggregations Flow")
def preaggregations_flow(year: int, data_root: str | None = None, verbose: bool = True):
    """Run the pre-aggregations workflow for a given season.

    Args:
        year: Season year to process.
        data_root: Optional data root override; defaults to environment/config.
        verbose: Whether to print per-partition progress.

    Returns:
        A dict of counts written per artifact type (byplay, drives, team_game, team_season, team_season_adj).
    """
    return persist_preaggregations(year=year, data_root=data_root, verbose=verbose)
