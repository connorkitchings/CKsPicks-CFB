"""Preseason schedule assembly and home/away matchup construction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from cks_picks_cfb.data.storage import StorageBackend
from cks_picks_cfb.preseason_features import (
    MATCHUP_CONTEXT_FEATURES,
    PRESEASON_FEATURES,
    TEAM_FEATURES,
    _coach_features,
    _prior_quality,
    _records,
    _recruiting_features,
    _returning_production,
    _snapshot_source,
    _talent_features,
    _transfer_features,
    canonical_team,
    snapshot_is_complete,
    v4_snapshot_is_usable,
)


def _schedule(
    storage: StorageBackend, year: int, include_targets: bool
) -> pd.DataFrame:
    games = _records(storage, "raw/games", {"year": year})
    if games.empty:
        return games
    games = games.rename(columns={"id": "game_id", "start_date": "start_date"}).copy()
    games["week"] = pd.to_numeric(games.get("week"), errors="coerce")
    games = games[games["week"].ge(0)].copy()
    for side in ("home", "away"):
        games[f"{side}_team"] = games[f"{side}_team"].map(canonical_team)
    teams = _records(storage, "raw/teams", {"year": year})
    if {"school", "classification"}.issubset(teams.columns):
        fbs_teams = set(
            teams.loc[
                teams["classification"].astype(str).str.lower() == "fbs", "school"
            ].map(canonical_team)
        )
        if fbs_teams:
            games = games[
                games["home_team"].isin(fbs_teams) & games["away_team"].isin(fbs_teams)
            ].copy()
    neutral_site = (
        games["neutral_site"]
        if "neutral_site" in games
        else pd.Series(False, index=games.index)
    )
    games["neutral_site"] = neutral_site.fillna(False).astype(int)
    home_conf, away_conf = games.get("home_conference"), games.get("away_conference")
    games["same_conference"] = (
        (home_conf.notna() & away_conf.notna() & (home_conf == away_conf)).astype(int)
        if isinstance(home_conf, pd.Series) and isinstance(away_conf, pd.Series)
        else 0
    )
    if include_targets and {"home_points", "away_points"}.issubset(games.columns):
        games["spread_target"] = pd.to_numeric(
            games["home_points"], errors="coerce"
        ) - pd.to_numeric(games["away_points"], errors="coerce")
        games["total_target"] = pd.to_numeric(
            games["home_points"], errors="coerce"
        ) + pd.to_numeric(games["away_points"], errors="coerce")
    return games


def _merge_side(
    matchups: pd.DataFrame, team_features: pd.DataFrame, side: str
) -> pd.DataFrame:
    renamed = team_features.rename(
        columns={
            "team": f"_{side}_team",
            **{
                column: f"{side}_{column}"
                for column in team_features.columns
                if column != "team"
            },
        }
    )
    return matchups.merge(
        renamed, left_on=f"{side}_team", right_on=f"_{side}_team", how="left"
    ).drop(columns=[f"_{side}_team"], errors="ignore")


def build_preseason_matchups(
    storage: StorageBackend,
    *,
    year: int,
    as_of: str,
    include_targets: bool,
    require_complete_snapshot: bool = True,
    allow_optional_talent: bool = False,
) -> pd.DataFrame:
    """Build line-free preseason features for every scheduled FBS matchup."""
    complete = (
        v4_snapshot_is_usable(storage, year, as_of)
        if allow_optional_talent
        else snapshot_is_complete(storage, year, as_of)
    )
    if require_complete_snapshot and not complete:
        raise RuntimeError(f"Preseason snapshot {year}/{as_of} is incomplete")
    tables = [
        _prior_quality(storage, year),
        _returning_production(
            _snapshot_source(storage, year, as_of, "returning_production")
        ),
        _transfer_features(_snapshot_source(storage, year, as_of, "transfers")),
        _recruiting_features(
            _snapshot_source(storage, year, as_of, "recruiting"), year
        ),
        _talent_features(_snapshot_source(storage, year, as_of, "talent")),
        _coach_features(_snapshot_source(storage, year, as_of, "coaches"), year),
    ]
    team_features: pd.DataFrame | None = None
    for table in tables:
        if not table.empty:
            team_features = (
                table
                if team_features is None
                else team_features.merge(table, on="team", how="outer")
            )
    if team_features is None:
        team_features = pd.DataFrame(columns=["team", *TEAM_FEATURES])
    for feature in TEAM_FEATURES:
        if feature not in team_features:
            team_features[feature] = np.nan
    matchups = _schedule(storage, year, include_targets)
    if matchups.empty:
        return matchups
    prior_source_year = 2019 if year == 2021 else year - 1
    matchups["prior_source_season"] = prior_source_year
    matchups["prior_season_gap"] = year - prior_source_year
    matchups["feature_as_of"] = as_of
    for side in ("home", "away"):
        matchups = _merge_side(matchups, team_features[["team", *TEAM_FEATURES]], side)
        for feature in TEAM_FEATURES:
            column = f"{side}_{feature}"
            matchups[f"{column}_missing"] = matchups[column].isna().astype(int)
    for feature in PRESEASON_FEATURES:
        if feature not in matchups:
            matchups[feature] = 0 if feature in MATCHUP_CONTEXT_FEATURES else np.nan
    return matchups
