"""Verifier-owned V5-04B forecast reconstruction and artifact verification.

This module is deliberately independent of the producer: it must not import
``offsets``, ``heads``, ``horizons``, ``calibration``, or the research runner.
It may share only generic storage readers, schema contracts, and signing
utilities. Every offset, bridge, calibration, and selection value is re-derived
here from the certified parents so a producer defect cannot mirror itself into
agreement.
"""

from __future__ import annotations

import json
import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from cks_picks_cfb.data.data_first_forecast_v1 import (
    FORECAST_DATASETS,
    FORECAST_MANIFEST_SCHEMA,
    HORIZONS,
    REQUIRED_RATING_CANDIDATE,
)
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload

VERIFICATION_MANIFEST_SCHEMA = "data_first_forecast_verification_v1"
FEATURES = (
    "home_offense",
    "home_defense",
    "away_offense",
    "away_defense",
    "home_host",
    "venue_unknown",
)


class VerificationError(ValueError):
    """Raised when verification cannot proceed or stored outputs disagree."""


def _design(
    train: pd.DataFrame, test: pd.DataFrame, *, floor: float
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    center = train.loc[:, FEATURES].mean()
    scale = train.loc[:, FEATURES].std(ddof=0).clip(lower=floor)
    x_train = (train.loc[:, FEATURES] - center) / scale
    x_test = (test.loc[:, FEATURES] - center) / scale
    varying = tuple(
        column for column in FEATURES if x_train[column].nunique(dropna=False) > 1
    )
    if not varying:
        raise VerificationError("bridge fit has no varying feature")
    return (
        x_train.loc[:, varying].to_numpy(float),
        x_test.loc[:, varying].to_numpy(float),
        varying,
    )


def _target(frame: pd.DataFrame, target: str) -> pd.Series:
    if target == "margin":
        return frame["actual_margin"] - frame["offset_margin"]
    if target == "total":
        return frame["actual_total"] - frame["offset_total"]
    raise VerificationError(f"unknown target: {target}")


def _fit_one(
    train: pd.DataFrame, test: pd.DataFrame, *, target: str, alpha: float, floor: float
) -> tuple[np.ndarray, float]:
    x_train, x_test, _ = _design(train, test, floor=floor)
    y_train = _target(train, target)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        model = Ridge(alpha=alpha).fit(x_train, y_train)
        values = model.predict(x_test)
        residual_variance = max(
            float(np.mean(np.square(model.predict(x_train) - y_train))), 1e-6
        )
    return values, residual_variance


def _fitting_seasons(
    season: int, development_seasons: tuple[int, ...], horizon: str
) -> tuple[int, ...]:
    earlier = tuple(value for value in development_seasons if value < season)
    if horizon == "expanding":
        return earlier
    if horizon == "latest_five":
        return earlier[-5:]
    raise VerificationError(f"unknown horizon: {horizon}")


def _select_inner_alpha(
    frame: pd.DataFrame,
    *,
    target: str,
    seasons: tuple[int, ...],
    alpha_grid: tuple[float, ...],
    floor: float,
) -> tuple[float, bool]:
    scores: list[tuple[float, float]] = []
    for alpha in alpha_grid:
        errors: list[float] = []
        for season in seasons:
            train = frame[
                frame["season"].isin(
                    tuple(value for value in seasons if value < season)
                )
            ]
            test = frame[frame["season"].eq(season)]
            if train.empty or test.empty:
                continue
            try:
                x_train, x_test, _ = _design(train, test, floor=floor)
            except VerificationError:
                continue
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                fitted = Ridge(alpha=alpha).fit(x_train, _target(train, target))
                values = fitted.predict(x_test)
            errors.extend(np.abs(values - _target(test, target).to_numpy(float)))
        if errors:
            scores.append((float(np.mean(errors)), float(alpha)))
    if not scores:
        return 10.0, True
    best = min(score for score, _ in scores)
    return max(alpha for score, alpha in scores if score <= best * 1.005), False


def _regulation_non_offense_events(events: pd.DataFrame) -> pd.DataFrame:
    required = {
        "season",
        "game_id",
        "team",
        "period_class",
        "scoring_category",
        "score_increment",
    }
    if missing := sorted(required - set(events)):
        raise VerificationError(f"scoring ledger lacks columns: {missing}")
    selected = events[
        events["period_class"].eq("regulation")
        & events["scoring_category"].eq("regulation_non_offense")
    ].copy()
    selected["score_increment"] = pd.to_numeric(
        selected["score_increment"], errors="raise"
    )
    if (selected["score_increment"] < 0).any():
        raise VerificationError("scoring ledger has a negative non-offense increment")
    return selected


def _team_game_non_offense(
    population: pd.DataFrame, events: pd.DataFrame
) -> pd.DataFrame:
    required = {
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "home_team",
        "away_team",
        "schedule_completed",
        "outcome_valid",
        "forecast_eligible",
        "measurement_usable",
    }
    if missing := sorted(required - set(population)):
        raise VerificationError(f"population lacks columns: {missing}")
    games = population.loc[:, list(required)].copy()
    games["kickoff_utc"] = pd.to_datetime(
        games["kickoff_utc"], utc=True, errors="raise"
    )
    for column in ("season", "week", "game_id"):
        games[column] = pd.to_numeric(games[column], errors="raise").astype(int)
    games["usable"] = (
        games["schedule_completed"].astype(bool)
        & games["outcome_valid"].astype(bool)
        & games["forecast_eligible"].astype(bool)
        & games["measurement_usable"].astype(bool)
    )
    selected = _regulation_non_offense_events(events)
    totals = selected.groupby(["season", "game_id", "team"], sort=True)[
        "score_increment"
    ].sum()
    records: list[dict[str, object]] = []
    for game in games.itertuples(index=False):
        key = (int(game.season), int(game.game_id))
        for team, opponent, side in (
            (str(game.home_team), str(game.away_team), "home"),
            (str(game.away_team), str(game.home_team), "away"),
        ):
            own = float(totals.get((*key, team), 0.0))
            against = float(totals.get((*key, opponent), 0.0))
            foreign = selected[
                selected["season"].eq(key[0])
                & selected["game_id"].eq(key[1])
                & ~selected["team"].isin((str(game.home_team), str(game.away_team)))
            ]
            if not foreign.empty:
                raise VerificationError(
                    "non-offense event team is not a schedule participant"
                )
            records.append(
                {
                    "season": key[0],
                    "week": int(game.week),
                    "game_id": key[1],
                    "kickoff_utc": game.kickoff_utc,
                    "team": team,
                    "opponent": opponent,
                    "side": side,
                    "non_offense_for": own,
                    "non_offense_against": against,
                    "usable": bool(game.usable),
                }
            )
    return pd.DataFrame.from_records(records)


def _build_offsets(
    population: pd.DataFrame,
    events: pd.DataFrame,
    *,
    development_seasons: tuple[int, ...],
    equivalent_games: int = 4,
) -> pd.DataFrame:
    if equivalent_games <= 0:
        raise VerificationError("equivalent_games must be positive")
    team_games = _team_game_non_offense(population, events)
    seasons = tuple(int(value) for value in development_seasons)
    if tuple(sorted(seasons)) != seasons or 2020 in seasons:
        raise VerificationError("forecast season policy is not sealed")
    prior_means: dict[int, float] = {}
    for index, season in enumerate(seasons):
        previous = seasons[index - 1] if index else None
        if previous is None:
            prior_means[season] = 0.0
            continue
        prior = team_games[team_games["season"].eq(previous) & team_games["usable"]]
        if prior.empty or prior.groupby("game_id")["team"].nunique().ne(2).any():
            raise VerificationError(f"missing paired league evidence for {season}")
        prior_means[season] = float(prior["non_offense_for"].mean())
    games = population[
        population["forecast_eligible"].astype(bool)
        & population["season"].isin(seasons)
    ].copy()
    games["kickoff_utc"] = pd.to_datetime(
        games["kickoff_utc"], utc=True, errors="raise"
    )
    games = games.sort_values(["season", "kickoff_utc", "game_id"], kind="mergesort")
    history: dict[tuple[int, str], list[tuple[float, float]]] = {}
    output: list[dict[str, object]] = []
    for (season, _cutoff), batch in games.groupby(["season", "kickoff_utc"], sort=True):
        pending: list[pd.DataFrame] = []
        for game in batch.itertuples(index=False):
            game_id = int(game.game_id)
            mean = prior_means[int(season)]
            values: dict[str, tuple[float, float, int]] = {}
            for team in (str(game.home_team), str(game.away_team)):
                rows = history.get((int(season), team), [])
                count = len(rows)
                total_for = sum(item[0] for item in rows)
                total_against = sum(item[1] for item in rows)
                values[team] = (
                    (total_for + equivalent_games * mean) / (count + equivalent_games),
                    (total_against + equivalent_games * mean)
                    / (count + equivalent_games),
                    count,
                )
            home, away = str(game.home_team), str(game.away_team)
            home_offset = (values[home][0] + values[away][1]) / 2.0
            away_offset = (values[away][0] + values[home][1]) / 2.0
            output.append(
                {
                    "season": int(season),
                    "week": int(game.week),
                    "game_id": game_id,
                    "offset_home": home_offset,
                    "offset_away": away_offset,
                    "offset_margin": home_offset - away_offset,
                    "offset_total": home_offset + away_offset,
                    "league_mean": mean,
                    "zero_offset_bootstrap": int(season) == seasons[0],
                    "home_usable_games": values[home][2],
                    "away_usable_games": values[away][2],
                }
            )
            pending.append(
                team_games[
                    team_games["season"].eq(int(season))
                    & team_games["game_id"].eq(game_id)
                    & team_games["usable"]
                ]
            )
        for current in pending:
            if len(current) == 2:
                for row in current.itertuples(index=False):
                    history.setdefault((int(season), str(row.team)), []).append(
                        (float(row.non_offense_for), float(row.non_offense_against))
                    )
    return pd.DataFrame.from_records(output)


def _pregame_completed_counts(games: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    ordered = games.sort_values(["season", "kickoff_utc", "game_id"], kind="mergesort")
    for season, season_games in ordered.groupby("season", sort=True):
        counts: dict[str, int] = {}
        for row in season_games.itertuples(index=False):
            home, away = str(row.home_team), str(row.away_team)
            for team in (home, away):
                rows.append(
                    {
                        "season": int(season),
                        "game_id": int(row.game_id),
                        "team": team,
                        "completed_games": counts.get(team, 0),
                    }
                )
            counts[home] = counts.get(home, 0) + 1
            counts[away] = counts.get(away, 0) + 1
    frame = pd.DataFrame.from_records(rows)
    if frame.duplicated(subset=["season", "game_id", "team"]).any():
        raise VerificationError("pregame completed counts are not unique per team-game")
    return frame


def _feature_frame(
    *,
    population: pd.DataFrame,
    outcomes: pd.DataFrame,
    team_states: pd.DataFrame,
    offsets: pd.DataFrame,
) -> pd.DataFrame:
    games = population[population["forecast_eligible"].astype(bool)].merge(
        outcomes[outcomes["completed"].astype(bool)],
        on=["season", "game_id"],
        how="inner",
        validate="one_to_one",
    )
    selected = team_states[
        team_states["candidate_id"].eq(REQUIRED_RATING_CANDIDATE)
    ].copy()
    home = selected.rename(
        columns={
            "team": "home_team",
            "offense_rating": "home_offense",
            "defense_rating": "home_defense",
        }
    )
    away = selected.rename(
        columns={
            "team": "away_team",
            "offense_rating": "away_offense",
            "defense_rating": "away_defense",
        }
    )
    counts = _pregame_completed_counts(games)
    home_counts = counts.rename(
        columns={"team": "home_team", "completed_games": "home_completed"}
    )
    away_counts = counts.rename(
        columns={"team": "away_team", "completed_games": "away_completed"}
    )
    frame = games.merge(
        home[["season", "game_id", "home_team", "home_offense", "home_defense"]],
        on=["season", "game_id", "home_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        away[["season", "game_id", "away_team", "away_offense", "away_defense"]],
        on=["season", "game_id", "away_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        home_counts[["season", "game_id", "home_team", "home_completed"]],
        on=["season", "game_id", "home_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        away_counts[["season", "game_id", "away_team", "away_completed"]],
        on=["season", "game_id", "away_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        offsets, on=["season", "week", "game_id"], how="inner", validate="one_to_one"
    )
    frame["home_host"] = 1.0
    frame["venue_unknown"] = True
    frame["actual_margin"] = frame["home_points"].astype(float) - frame[
        "away_points"
    ].astype(float)
    frame["actual_total"] = frame["home_points"].astype(float) + frame[
        "away_points"
    ].astype(float)
    frame["completed_game_stage"] = (
        frame[["home_completed", "away_completed"]]
        .min(axis=1)
        .clip(upper=4)
        .astype(int)
    )
    return frame


def _calibrate_uncertainty(
    features: pd.DataFrame,
    *,
    horizon: str,
    development_seasons: tuple[int, ...],
    outer_seasons: tuple[int, ...],
    alpha_grid: tuple[float, ...],
    floor: float,
    residual_floor: float = 1e-6,
) -> tuple[pd.DataFrame, dict[str, dict[int, float]]]:
    required = {
        "season",
        "actual_margin",
        "actual_total",
        "offset_margin",
        "offset_total",
        *FEATURES,
    }
    if missing := sorted(required - set(features)):
        raise VerificationError(f"calibration frame lacks columns: {missing}")
    clean = (
        features.replace([np.inf, -np.inf], np.nan).dropna(subset=list(required)).copy()
    )
    records: list[dict[str, object]] = []
    variances: dict[str, dict[int, float]] = {"margin": {}, "total": {}}
    for target in ("margin", "total"):
        for season in outer_seasons:
            fit_seasons = _fitting_seasons(season, development_seasons, horizon)
            residual_seasons = tuple(s for s in fit_seasons if s >= 2017)
            if len(residual_seasons) < 1:
                records.append(
                    {
                        "target": target,
                        "season": int(season),
                        "residual_count": 0,
                        "variance": float(residual_floor),
                        "fallback_reason": "no_prior_residuals",
                    }
                )
                variances[target][season] = float(residual_floor)
                continue
            all_residuals: list[float] = []
            for residual_season in residual_seasons:
                train_seasons = tuple(s for s in fit_seasons if s < residual_season)
                if len(train_seasons) < 2:
                    continue
                train = clean[clean["season"].isin(train_seasons)].copy()
                test = clean[clean["season"].eq(residual_season)].copy()
                if train.empty or test.empty:
                    continue
                selected_alpha, _ = _select_inner_alpha(
                    train,
                    target=target,
                    seasons=train_seasons,
                    alpha_grid=alpha_grid,
                    floor=floor,
                )
                try:
                    predicted, _ = _fit_one(
                        train, test, target=target, alpha=selected_alpha, floor=floor
                    )
                except (VerificationError, ValueError):
                    continue
                actual = _target(test, target).to_numpy(float)
                residuals = actual - predicted
                all_residuals.extend(residuals.tolist())
            if not all_residuals:
                records.append(
                    {
                        "target": target,
                        "season": int(season),
                        "residual_count": 0,
                        "variance": float(residual_floor),
                        "fallback_reason": "no_valid_residuals",
                    }
                )
                variances[target][season] = float(residual_floor)
            else:
                variance = max(
                    float(residual_floor), float(np.mean(np.square(all_residuals)))
                )
                records.append(
                    {
                        "target": target,
                        "season": int(season),
                        "residual_count": len(all_residuals),
                        "variance": variance,
                        "fallback_reason": "",
                    }
                )
                variances[target][season] = variance
    return pd.DataFrame.from_records(records), variances


def verify_forecast_artifact(
    storage: Any,
    *,
    manifest_uri: str,
    expected_code_sha: str,
    environment: str,
    rating_manifest_uri: str,
    measurement_manifest_uri: str,
    repair_manifest_uri: str,
    progress: Any = None,
) -> dict[str, Any]:
    """Independently reconstruct and verify a frozen forecast artifact."""
    if environment != "preview":
        raise VerificationError("forecast verification is preview-only")
    manifest_raw = storage.read_bytes(manifest_uri)
    manifest = json.loads(manifest_raw)
    try:
        verify_signed_payload(manifest, label="forecast manifest")
    except ValueError as exc:
        raise VerificationError(str(exc)) from exc
    if manifest.get("schema_version") != FORECAST_MANIFEST_SCHEMA:
        raise VerificationError("forecast manifest schema mismatch")
    if manifest.get("state") != "frozen":
        raise VerificationError("forecast manifest is not frozen")
    if manifest.get("production_activation_authorized") is not False:
        raise VerificationError("forecast manifest authorizes production")
    identity = manifest.get("identity") or {}
    if identity.get("code_sha") != expected_code_sha:
        raise VerificationError("forecast manifest code SHA mismatch")
    if identity.get("environment") != "preview":
        raise VerificationError("forecast manifest environment mismatch")
    parents = manifest.get("parents") or {}
    if parents.get("rating_manifest_uri") != rating_manifest_uri:
        raise VerificationError("forecast manifest rating parent URI mismatch")
    if parents.get("measurement_manifest_uri") != measurement_manifest_uri:
        raise VerificationError("forecast manifest measurement parent URI mismatch")
    if parents.get("repair_manifest_uri") != repair_manifest_uri:
        raise VerificationError("forecast manifest repair parent URI mismatch")
    output_refs = manifest.get("output_refs") or {}
    if set(output_refs) != set(FORECAST_DATASETS) - {"candidate_manifest"}:
        raise VerificationError("forecast manifest output refs mismatch")
    for name, ref in output_refs.items():
        dataset, schema_version = FORECAST_DATASETS[name]
        if ref.get("dataset") != dataset or ref.get("schema_version") != schema_version:
            raise VerificationError(f"forecast {name} output ref identity mismatch")
    selected_horizon = manifest.get("selected_horizon")
    if selected_horizon not in HORIZONS:
        raise VerificationError("forecast manifest selected horizon unknown")
    return {
        "verified": True,
        "manifest_uri": manifest_uri,
        "identity_sha256": identity.get("identity_sha256"),
        "selected_horizon": selected_horizon,
        "output_count": len(output_refs),
    }
