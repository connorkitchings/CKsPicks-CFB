"""Verifier-owned V5-04B forecast reconstruction and artifact verification.

This module is deliberately independent of the producer: it must not import
``offsets``, ``heads``, ``horizons``, ``calibration``, or the research runner.
It may share only generic storage readers, schema contracts, and signing
utilities. Every offset, bridge, calibration, and selection value is re-derived
here from the certified parents so a producer defect cannot mirror itself into
agreement.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import ndtr
from sklearn.linear_model import Ridge

from cks_picks_cfb.data.data_first_forecast_v1 import (
    FORECAST_CALIBRATION_COLUMNS,
    FORECAST_DATASETS,
    FORECAST_MANIFEST_SCHEMA,
    FORECAST_MODEL_COLUMNS,
    FORECAST_PREDICTION_COLUMNS,
    FORECAST_REGISTRY_COLUMNS,
    FORECAST_SELECTION_COLUMNS,
    HORIZONS,
    REQUIRED_RATING_CANDIDATE,
    WINDOW_COMPARISON_COLUMNS,
)
from cks_picks_cfb.data.data_first_phase2 import (
    DEVELOPMENT_SEASONS,
    FORBIDDEN_SEASONS,
)
from cks_picks_cfb.data.data_first_phase2d import (
    PHASE3_DATASETS,
    REPLACEMENT_ELIGIBILITY_SCHEMA,
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    POSSESSION_RATING_MANIFEST_SCHEMA,
    RATING_DATASETS,
    TEAM_STATE_COLUMNS,
)
from cks_picks_cfb.data.data_first_possession_v1 import (
    POPULATION_COLUMNS,
    POSSESSION_DATASETS,
)
from cks_picks_cfb.data.lake import (
    PARTITIONED_DATASET_KIND,
    DatasetRef,
    PartitionedDatasetRef,
    canonical_frame_digest,
    partition_order_key,
    partitioned_records_sha,
    read_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame

VERIFICATION_MANIFEST_SCHEMA = "data_first_forecast_verification_v1"
OUTER_SEASONS = (2022, 2023, 2024, 2025)
REPORTING_SEASONS = (2018, 2019, 2021)
ALPHA_GRID = (0.1, 1.0, 10.0, 100.0)
SCALING_FLOOR = 0.05
BOOTSTRAP_SEED = 20260908
BOOTSTRAP_REPLICATES = 2000
EQUIVALENT_GAMES = 4
RESIDUAL_FLOOR = 1e-6
# Independent mirror of the producer's final-fit sentinel (heads.FINAL_FIT_SEASON).
# Defined here by hand: the verifier must not import producer modules. Sentinel 0
# marks through-development-window final rows that have no validation season.
FINAL_FIT_SEASON = 0
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


@dataclass(frozen=True)
class StoredOutput:
    """One fully validated stored forecast output."""

    ref: Mapping[str, Any]
    frame: pd.DataFrame
    parts: tuple[Mapping[str, Any], ...] = ()


def _read_json(storage: Any, uri: str, *, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        raw = storage.read_bytes(uri)
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise VerificationError(f"{label} is unreadable") from exc
    if not isinstance(payload, dict):
        raise VerificationError(f"{label} is not a JSON object")
    return payload, raw


def _require_raw_sha(raw: bytes, expected: str, *, label: str) -> None:
    if not expected or hashlib.sha256(raw).hexdigest() != expected:
        raise VerificationError(f"{label} raw checksum mismatch")


def _dataset_ref(value: Mapping[str, Any], *, label: str) -> DatasetRef:
    fields = ("dataset", "version_id", "schema_version", "content_sha", "uri")
    if missing := [field for field in fields if not value.get(field)]:
        raise VerificationError(f"{label} dataset reference is malformed: {missing}")
    return DatasetRef(**{field: str(value[field]) for field in fields})


def _partitioned_ref(
    value: Mapping[str, Any],
    *,
    label: str,
    expected_partition_keys: Sequence[str] | None = None,
) -> PartitionedDatasetRef:
    try:
        return PartitionedDatasetRef(
            artifact_kind=str(value["artifact_kind"]),
            dataset=str(value["dataset"]),
            version_id=str(value["version_id"]),
            schema_version=str(value["schema_version"]),
            content_sha=str(value["content_sha"]),
            records_sha=str(value["records_sha"]),
            uri=str(value["uri"]),
            row_count=int(value["row_count"]),
            partition_keys=tuple(
                value.get("partition_keys") or expected_partition_keys or ()
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise VerificationError(f"{label} partitioned reference is malformed") from exc


def _concat_frames(
    frames: Sequence[pd.DataFrame], columns: Sequence[str]
) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame(columns=list(columns))
    normalized = [frame.loc[:, list(columns)].copy() for frame in frames]
    for column in columns:
        if any(frame[column].isna().all() for frame in normalized) and any(
            frame[column].notna().any() for frame in normalized
        ):
            for frame in normalized:
                frame[column] = frame[column].astype(object)
    return pd.concat(normalized, ignore_index=True, sort=False)


def _read_partitioned(
    storage: Any,
    value: Mapping[str, Any],
    *,
    expected_dataset: str,
    expected_schema: str,
    label: str,
) -> StoredOutput:
    forecast_partition_keys = {
        "forecast_model": ("horizon", "outer_season"),
        "forecast_prediction": ("season", "week"),
    }
    ref = _partitioned_ref(
        value,
        label=label,
        expected_partition_keys=forecast_partition_keys.get(expected_dataset),
    )
    if (
        ref.artifact_kind != PARTITIONED_DATASET_KIND
        or ref.dataset != expected_dataset
        or ref.schema_version != expected_schema
    ):
        raise VerificationError(f"{label} identity mismatch")
    raw = storage.read_bytes(ref.uri)
    if hashlib.sha256(raw).hexdigest() != ref.content_sha:
        raise VerificationError(f"{label} manifest checksum mismatch")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{label} manifest is unreadable") from exc
    parts = list(manifest.get("parts") or [])
    if (
        manifest.get("artifact_kind") != PARTITIONED_DATASET_KIND
        or manifest.get("dataset") != expected_dataset
        or manifest.get("schema_version") != expected_schema
        or tuple(manifest.get("partition_keys") or ()) != ref.partition_keys
        or partitioned_records_sha(parts, ref.partition_keys) != ref.records_sha
        or sum(int(part.get("row_count", -1)) for part in parts) != ref.row_count
    ):
        raise VerificationError(f"{label} partition manifest mismatch")
    schema = schema_for(expected_dataset, expected_schema)
    frames: list[pd.DataFrame] = []
    previous: tuple[tuple[str, int, Any], ...] | None = None
    for part in parts:
        partition = dict(part.get("partition") or {})
        order_key = partition_order_key(partition)
        if tuple(partition) != ref.partition_keys or (
            previous is not None and order_key <= previous
        ):
            raise VerificationError(f"{label} partitions are malformed or unordered")
        previous = order_key
        row_count = int(part.get("row_count", -1))
        child = part.get("ref")
        if child is None:
            if row_count != 0:
                raise VerificationError(f"{label} nonempty partition lacks a child")
            frame = pd.DataFrame(columns=list(schema.required))
        else:
            try:
                frame = read_dataset(
                    storage, _dataset_ref(child, label=f"{label} child")
                )
            except Exception as exc:
                raise VerificationError(f"{label} child is unreadable") from exc
            validate_frame(frame, schema)
        if len(frame) != row_count or canonical_frame_digest(
            frame, columns=schema.required
        ) != str(part.get("records_sha")):
            raise VerificationError(f"{label} child digest mismatch")
        frames.append(frame)
    return StoredOutput(
        ref=asdict(ref),
        frame=_concat_frames(frames, schema.required),
        parts=tuple(parts),
    )


def _read_compact(
    storage: Any,
    value: Mapping[str, Any],
    *,
    expected_dataset: str,
    expected_schema: str,
    label: str,
) -> StoredOutput:
    ref = _dataset_ref(value, label=label)
    if ref.dataset != expected_dataset or ref.schema_version != expected_schema:
        raise VerificationError(f"{label} identity mismatch")
    try:
        frame = read_dataset(storage, ref)
    except Exception as exc:
        raise VerificationError(f"{label} is unreadable") from exc
    schema = schema_for(expected_dataset, expected_schema)
    validate_frame(frame, schema)
    if len(frame) != int(value.get("row_count", -1)) or canonical_frame_digest(
        frame, columns=schema.required
    ) != str(value.get("records_sha")):
        raise VerificationError(f"{label} content mismatch")
    return StoredOutput(ref=dict(value), frame=frame.loc[:, list(schema.required)])


def _read_output(
    storage: Any,
    value: Mapping[str, Any],
    *,
    expected_dataset: str,
    expected_schema: str,
    label: str,
) -> StoredOutput:
    if value.get("artifact_kind") == PARTITIONED_DATASET_KIND:
        return _read_partitioned(
            storage,
            value,
            expected_dataset=expected_dataset,
            expected_schema=expected_schema,
            label=label,
        )
    return _read_compact(
        storage,
        value,
        expected_dataset=expected_dataset,
        expected_schema=expected_schema,
        label=label,
    )


def _assert_allowed_seasons(frame: pd.DataFrame, *, label: str) -> None:
    if "season" not in frame:
        return
    seasons = set(pd.to_numeric(frame["season"], errors="raise").astype(int))
    rejected = seasons & (set(FORBIDDEN_SEASONS) | {2026})
    if rejected:
        raise VerificationError(
            f"{label} contains rejected seasons: {sorted(rejected)}"
        )


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


def _gaussian_crps(actual: np.ndarray, mean: np.ndarray, variance: float) -> np.ndarray:
    sigma = max(float(variance), 1e-6) ** 0.5
    z = (actual - mean) / sigma
    phi = np.exp(-0.5 * z * z) / np.sqrt(2.0 * np.pi)
    return sigma * (z * (2.0 * ndtr(z) - 1.0) + 2.0 * phi - 1.0 / np.sqrt(np.pi))


def _paired_bootstrap(
    candidate: pd.DataFrame,
    reference: pd.DataFrame,
    *,
    seed: int,
    samples: int,
) -> tuple[float, float, float]:
    keys = ["season", "week", "game_id", "target"]
    merged = candidate.merge(
        reference, on=keys, suffixes=("_candidate", "_reference"), validate="one_to_one"
    )
    if len(merged) != len(candidate) or len(merged) != len(reference) or merged.empty:
        raise VerificationError("paired comparison populations differ")
    difference = merged["absolute_error_reference"].to_numpy(float) - merged[
        "absolute_error_candidate"
    ].to_numpy(float)
    rng = np.random.default_rng(seed)
    groups = [
        group.index.to_numpy()
        for _, group in merged.groupby(["season", "week"], sort=True)
    ]
    if not groups:
        raise VerificationError("paired bootstrap lacks season/week groups")
    estimates: list[float] = []
    for _ in range(samples):
        selected = rng.integers(0, len(groups), size=len(groups))
        sampled = np.concatenate(
            [
                groups[index][rng.integers(0, len(groups[index]), len(groups[index]))]
                for index in selected
            ]
        )
        estimates.append(float(difference[sampled].mean()))
    return (
        float(difference.mean()),
        float(np.quantile(estimates, 0.05)),
        float(np.quantile(estimates, 0.95)),
    )


def _evaluate_heads(
    frame: pd.DataFrame,
    *,
    horizon: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    required = {
        "season",
        "week",
        "game_id",
        "actual_margin",
        "actual_total",
        "offset_margin",
        "offset_total",
        *FEATURES,
        "completed_game_stage",
    }
    if missing := sorted(required - set(frame)):
        raise VerificationError(f"forecast frame lacks columns: {missing}")
    clean = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=list(required))
    rows: list[dict[str, object]] = []
    models: list[dict[str, object]] = []
    for target in ("margin", "total"):
        for season in (*OUTER_SEASONS, *REPORTING_SEASONS):
            reporting = season in REPORTING_SEASONS
            test = clean[clean["season"].eq(season)].copy()
            seasons = _fitting_seasons(season, DEVELOPMENT_SEASONS, horizon)
            train = clean[clean["season"].isin(seasons)].copy()
            if train.empty or test.empty:
                raise VerificationError(
                    f"{horizon}/{target}/{season} lacks train or test rows"
                )
            alpha, inner_fallback = _select_inner_alpha(
                train,
                target=target,
                seasons=seasons,
                alpha_grid=ALPHA_GRID,
                floor=SCALING_FLOOR,
            )
            for head, value in (("reference", 10.0), ("challenger", alpha)):
                predicted, variance = _fit_one(
                    train,
                    test,
                    target=target,
                    alpha=value,
                    floor=SCALING_FLOOR,
                )
                offset = test[f"offset_{target}"].to_numpy(float)
                actual = test[f"actual_{target}"].to_numpy(float)
                final = predicted + offset
                if not np.isfinite(final).all():
                    raise VerificationError("bridge emitted a non-finite forecast")
                if not reporting:
                    scores = _gaussian_crps(actual, final, variance)
                    for source, forecast, actual_value, error, score in zip(
                        test.itertuples(index=False),
                        final,
                        actual,
                        np.abs(final - actual),
                        scores,
                        strict=True,
                    ):
                        rows.append(
                            {
                                "horizon": horizon,
                                "head": head,
                                "target": target,
                                "season": int(source.season),
                                "week": int(source.week),
                                "game_id": int(source.game_id),
                                "actual": float(actual_value),
                                "prediction": float(forecast),
                                "absolute_error": float(error),
                                "gaussian_crps": float(score),
                                "offset": float(getattr(source, f"offset_{target}")),
                                "training_seasons": ",".join(map(str, seasons)),
                                "completed_game_stage": int(
                                    source.completed_game_stage
                                ),
                                "venue_unknown": bool(source.venue_unknown),
                            }
                        )
                    models.append(
                        {
                            "horizon": horizon,
                            "target": target,
                            "outer_season": season,
                            "head": head,
                            "alpha": value,
                            "training_seasons": ",".join(map(str, seasons)),
                            "inner_fallback": inner_fallback,
                            "retained": False,
                            "fallback_reason": "insufficient_inner_fold"
                            if inner_fallback
                            else None,
                        }
                    )
    predictions = pd.DataFrame.from_records(rows)
    model_frame = pd.DataFrame.from_records(models)
    retained: dict[str, str] = {}
    for target in ("margin", "total"):
        reference = predictions[
            predictions["target"].eq(target) & predictions["head"].eq("reference")
        ]
        challenger = predictions[
            predictions["target"].eq(target) & predictions["head"].eq("challenger")
        ]
        _, lower, _ = _paired_bootstrap(
            challenger,
            reference,
            seed=BOOTSTRAP_SEED,
            samples=BOOTSTRAP_REPLICATES,
        )
        ref_mae = float(reference["absolute_error"].mean())
        challenger_mae = float(challenger["absolute_error"].mean())
        ref_crps = float(reference["gaussian_crps"].mean())
        challenger_crps = float(challenger["gaussian_crps"].mean())
        improvement = 100.0 * (ref_mae - challenger_mae) / ref_mae if ref_mae else 0.0
        regressions_ok = True
        combined = pd.concat(
            [
                reference.assign(kind="reference"),
                challenger.assign(kind="challenger"),
            ]
        )
        for _, values in combined.groupby(
            ["season", "completed_game_stage"], sort=True
        ):
            base = values[values["kind"].eq("reference")]
            other = values[values["kind"].eq("challenger")]
            if (
                len(base) != len(other)
                or float(other["absolute_error"].mean())
                > float(base["absolute_error"].mean()) * 1.05
            ):
                regressions_ok = False
        keep = (
            challenger_mae <= ref_mae * 1.01
            and challenger_crps <= ref_crps * 1.01
            and regressions_ok
            and improvement >= 0.5
            and lower > 0
        )
        retained[target] = "challenger" if keep else "reference"
        model_frame.loc[
            model_frame["target"].eq(target) & model_frame["head"].eq(retained[target]),
            "retained",
        ] = True
    return predictions, model_frame, retained


def _select_horizon(
    expanding: pd.DataFrame, latest_five: pd.DataFrame
) -> tuple[str, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    latest_passes = True
    for target in ("margin", "total"):
        reference = expanding[expanding["target"].eq(target)].copy()
        candidate = latest_five[latest_five["target"].eq(target)].copy()
        _, lower, upper = _paired_bootstrap(
            candidate,
            reference,
            seed=BOOTSTRAP_SEED,
            samples=BOOTSTRAP_REPLICATES,
        )
        ref_mae = float(reference["absolute_error"].mean())
        cand_mae = float(candidate["absolute_error"].mean())
        ref_crps = float(reference["gaussian_crps"].mean())
        cand_crps = float(candidate["gaussian_crps"].mean())
        improvement = 100.0 * (ref_mae - cand_mae) / ref_mae if ref_mae else 0.0
        slices = pd.concat(
            [
                reference.assign(policy="expanding"),
                candidate.assign(policy="latest_five"),
            ]
        )
        regressions_ok = True
        for _, group in slices.groupby(["season", "completed_game_stage"], sort=True):
            base = group[group["policy"].eq("expanding")]
            short = group[group["policy"].eq("latest_five")]
            if (
                len(base) != len(short)
                or base.empty
                or float(short["absolute_error"].mean())
                > float(base["absolute_error"].mean()) * 1.05
            ):
                regressions_ok = False
        passes = (
            improvement >= 0.5
            and lower > 0
            and cand_mae <= ref_mae * 1.01
            and cand_crps <= ref_crps * 1.01
            and regressions_ok
        )
        latest_passes &= passes
        rows.extend(
            [
                {
                    "target": target,
                    "metric": "mae",
                    "expanding": ref_mae,
                    "latest_five": cand_mae,
                    "improvement_pct": improvement,
                    "bootstrap_90_lower": lower,
                    "bootstrap_90_upper": upper,
                    "passes": passes,
                },
                {
                    "target": target,
                    "metric": "gaussian_crps",
                    "expanding": ref_crps,
                    "latest_five": cand_crps,
                    "improvement_pct": 100.0 * (ref_crps - cand_crps) / ref_crps
                    if ref_crps
                    else 0.0,
                    "bootstrap_90_lower": lower,
                    "bootstrap_90_upper": upper,
                    "passes": passes,
                },
            ]
        )
    return (
        "latest_five" if latest_passes else "expanding",
        pd.DataFrame.from_records(rows),
    )


def _core_outcomes(storage: Any, repair: Mapping[str, Any]) -> pd.DataFrame:
    parent = (repair.get("parents") or {}).get("core_eligibility") or {}
    uri = str(parent.get("uri") or "")
    if not uri:
        raise VerificationError("Repair parent lacks core eligibility lineage")
    payload, raw = _read_json(storage, uri, label="core eligibility")
    _require_raw_sha(raw, str(parent.get("raw_sha256") or ""), label="core eligibility")
    try:
        verify_signed_payload(payload, label="core eligibility")
    except ValueError as exc:
        raise VerificationError(str(exc)) from exc
    if (
        payload.get("schema_version") != REPLACEMENT_ELIGIBILITY_SCHEMA
        or payload.get("state") != "eligible"
        or payload.get("production_activation_authorized") is not False
        or tuple(payload.get("development_seasons") or ()) != DEVELOPMENT_SEASONS
        or tuple(payload.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS
    ):
        raise VerificationError("core eligibility policy mismatch")
    refs: dict[int, dict[str, DatasetRef]] = {}
    for value in payload.get("phase3_input_refs") or []:
        season = int(value.get("season", -1))
        dataset = str(value.get("dataset") or "")
        if value.get("eligible") is not True or dataset not in PHASE3_DATASETS:
            raise VerificationError(
                f"core eligibility rejects source {(season, dataset)}"
            )
        refs.setdefault(season, {})[dataset] = _dataset_ref(
            value, label=f"core {season} {dataset}"
        )
    expected = {
        (season, dataset)
        for season in DEVELOPMENT_SEASONS
        for dataset in PHASE3_DATASETS
    }
    seen = {(season, dataset) for season, values in refs.items() for dataset in values}
    if seen != expected:
        raise VerificationError("core eligibility does not expose the exact source set")
    frames = [
        read_dataset(storage, refs[season]["game_outcomes"])
        for season in DEVELOPMENT_SEASONS
    ]
    outcomes = pd.concat(frames, ignore_index=True, sort=False).loc[
        :, ["season", "game_id", "completed", "home_points", "away_points"]
    ]
    outcomes["season"] = pd.to_numeric(outcomes["season"], errors="raise").astype(int)
    outcomes["game_id"] = pd.to_numeric(outcomes["game_id"], errors="raise").astype(int)
    _assert_allowed_seasons(outcomes, label="game outcomes")
    return outcomes


def _verify_parent_manifests(
    storage: Any,
    *,
    manifest: Mapping[str, Any],
    rating_manifest_uri: str,
    measurement_manifest_uri: str,
    repair_manifest_uri: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    parents = manifest.get("parents") or {}
    expected_uris = {
        "rating_manifest_uri": rating_manifest_uri,
        "measurement_manifest_uri": measurement_manifest_uri,
        "repair_manifest_uri": repair_manifest_uri,
    }
    for key, value in expected_uris.items():
        if parents.get(key) != value:
            raise VerificationError(f"forecast manifest {key} mismatch")
    payloads: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for role, uri in (
        ("rating", rating_manifest_uri),
        ("measurement", measurement_manifest_uri),
        ("repair", repair_manifest_uri),
    ):
        payload, raw = _read_json(storage, uri, label=f"{role} manifest")
        raw_sha = hashlib.sha256(raw).hexdigest()
        if raw_sha != parents.get(f"{role}_manifest_raw_sha256"):
            raise VerificationError(f"{role} parent raw checksum mismatch")
        try:
            verify_signed_payload(payload, label=f"{role} manifest")
        except ValueError as exc:
            raise VerificationError(str(exc)) from exc
        payloads[role] = payload
        hashes[role] = raw_sha
    rating, measurement, repair = (
        payloads["rating"],
        payloads["measurement"],
        payloads["repair"],
    )
    rating_identity = rating.get("identity") or {}
    measurement_identity = measurement.get("identity") or {}
    repair_identity = repair.get("identity") or {}
    if (
        rating.get("schema_version") != POSSESSION_RATING_MANIFEST_SCHEMA
        or rating.get("state") != "frozen"
        or rating_identity.get("run_id")
        != "possession-v1-ratings-20260921-11d59ee-r9cert"
        or rating.get("selected_candidate") != REQUIRED_RATING_CANDIDATE
        or rating.get("production_activation_authorized") is not False
        or set(rating.get("output_refs") or {}) != set(RATING_DATASETS)
    ):
        raise VerificationError("rating parent identity mismatch")
    if (
        measurement_identity.get("run_id") != "possession-v1-measurements-20260921-r9"
        or measurement.get("production_activation_authorized") is not False
        or set(measurement.get("output_refs") or {}) != set(POSSESSION_DATASETS)
    ):
        raise VerificationError("measurement parent identity mismatch")
    if (
        repair_identity.get("run_id") != "repair-v2-20260909T1417Z"
        or repair.get("production_activation_authorized") is not False
    ):
        raise VerificationError("Repair parent identity mismatch")
    rating_parents = rating.get("parents") or {}
    if (
        rating_parents.get("measurement_manifest_uri") != measurement_manifest_uri
        or rating_parents.get("repair_manifest_uri") != repair_manifest_uri
        or rating_parents.get("measurement_manifest_raw_sha256")
        != hashes["measurement"]
        or rating_parents.get("repair_manifest_raw_sha256") != hashes["repair"]
        or measurement.get("repair_manifest_uri") != repair_manifest_uri
        or measurement.get("repair_manifest_raw_sha256") != hashes["repair"]
    ):
        raise VerificationError("recursive forecast parent lineage mismatch")
    return rating, measurement, repair, hashes


def _load_reconstruction_inputs(
    storage: Any,
    *,
    rating: Mapping[str, Any],
    measurement: Mapping[str, Any],
    repair: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    measurement_refs = measurement.get("output_refs") or {}
    population_dataset, population_schema = POSSESSION_DATASETS["population"]
    scoring_dataset, scoring_schema = POSSESSION_DATASETS["scoring_events"]
    population = _read_partitioned(
        storage,
        measurement_refs["population"],
        expected_dataset=population_dataset,
        expected_schema=population_schema,
        label="measurement population",
    ).frame.loc[:, list(POPULATION_COLUMNS)]
    scoring_events = _read_partitioned(
        storage,
        measurement_refs["scoring_events"],
        expected_dataset=scoring_dataset,
        expected_schema=scoring_schema,
        label="measurement scoring events",
    ).frame
    team_dataset, team_schema = RATING_DATASETS["team_states"]
    team_states = _read_partitioned(
        storage,
        (rating.get("output_refs") or {})["team_states"],
        expected_dataset=team_dataset,
        expected_schema=team_schema,
        label="rating team states",
    ).frame.loc[:, list(TEAM_STATE_COLUMNS)]
    outcomes = _core_outcomes(storage, repair)
    for label, frame in (
        ("measurement population", population),
        ("measurement scoring events", scoring_events),
        ("rating team states", team_states),
    ):
        _assert_allowed_seasons(frame, label=label)
    if len(population) != 8936 or int(population["forecast_eligible"].sum()) != 8935:
        raise VerificationError("measurement population reconciliation changed")
    return population, scoring_events, team_states, outcomes


def _retained_predictions(
    predictions: pd.DataFrame, retained: Mapping[str, str]
) -> pd.DataFrame:
    return predictions.merge(
        pd.DataFrame(
            [{"target": target, "head": head} for target, head in retained.items()]
        ),
        on=["target", "head"],
        how="inner",
        validate="many_to_one",
    )


def _fit_final_mirror(
    frame: pd.DataFrame,
    *,
    target: str,
    head: str,
) -> dict[str, object]:
    """Hand-written mirror of the producer final-fit recipe (no imports).

    Reference heads pin alpha 10.0; challenger heads re-run inner-alpha over
    the full development window. A proof Ridge fit on the window must succeed.
    Returns the recipe only — no values are persisted from the proof fit.
    """
    if head not in ("reference", "challenger"):
        raise VerificationError(f"final fit has an unknown head: {head!r}")
    required = {
        "season",
        "actual_margin",
        "actual_total",
        "offset_margin",
        "offset_total",
        *FEATURES,
    }
    if missing := sorted(required - set(frame)):
        raise VerificationError(f"final-fit frame lacks columns: {missing}")
    if set(DEVELOPMENT_SEASONS) & {FINAL_FIT_SEASON}:
        raise VerificationError("final-fit window contains the sentinel season")
    clean = (
        frame.replace([np.inf, -np.inf], np.nan).dropna(subset=list(required)).copy()
    )
    train = clean[clean["season"].isin(tuple(DEVELOPMENT_SEASONS))].copy()
    if train.empty:
        raise VerificationError("final fit has no training rows on the window")
    if head == "reference":
        alpha, inner_fallback = 10.0, False
    else:
        alpha, inner_fallback = _select_inner_alpha(
            train,
            target=target,
            seasons=tuple(DEVELOPMENT_SEASONS),
            alpha_grid=ALPHA_GRID,
            floor=SCALING_FLOOR,
        )
    try:
        _fit_one(train, train, target=target, alpha=alpha, floor=SCALING_FLOOR)
    except (VerificationError, ValueError) as exc:
        raise VerificationError(
            f"final fit failed on the full window: {target}"
        ) from exc
    return {
        "target": target,
        "head": head,
        "alpha": float(alpha),
        "training_seasons": tuple(int(season) for season in DEVELOPMENT_SEASONS),
        "inner_fallback": bool(inner_fallback),
    }


def _final_fit_rows(
    features: pd.DataFrame,
    calibration: pd.DataFrame,
    *,
    horizon: str,
    retained: Mapping[str, str],
    calibration_source_season: int = 2025,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, object]]]:
    """Mirror the producer's final model/calibration row construction.

    Carries the design's latest rolling-origin variance (2025) forward under
    sentinel season 0; fails closed when the source entry is missing or a
    fallback. In-sample final-fit residuals are never used.
    """
    model_rows: list[dict[str, object]] = []
    calibration_rows: list[dict[str, object]] = []
    recipes: dict[str, dict[str, object]] = {}
    for target in ("margin", "total"):
        recipe = _fit_final_mirror(features, target=target, head=retained[target])
        recipes[target] = recipe
        model_rows.append(
            {
                "horizon": horizon,
                "target": target,
                "outer_season": FINAL_FIT_SEASON,
                "head": recipe["head"],
                "alpha": recipe["alpha"],
                "training_seasons": ",".join(map(str, recipe["training_seasons"])),
                "inner_fallback": recipe["inner_fallback"],
                "retained": True,
                "fallback_reason": "insufficient_inner_fold"
                if recipe["inner_fallback"]
                else None,
            }
        )
        source = calibration[
            (calibration["target"] == target)
            & (calibration["season"] == calibration_source_season)
        ]
        if source.empty:
            raise VerificationError(
                f"final fit has no {calibration_source_season} calibration entry "
                f"for {target!r}"
            )
        entry = source.iloc[0]
        if (
            str(entry["fallback_reason"] or "") != ""
            or int(entry["residual_count"]) <= 0
        ):
            raise VerificationError(
                f"final fit cannot carry a fallback calibration entry for {target!r}"
            )
        calibration_rows.append(
            {
                "target": target,
                "season": FINAL_FIT_SEASON,
                "residual_count": int(entry["residual_count"]),
                "variance": float(entry["variance"]),
                "fallback_reason": "",
            }
        )
    return (
        pd.DataFrame.from_records(model_rows),
        pd.DataFrame.from_records(calibration_rows),
        recipes,
    )


def _reconstruct_outputs(
    *,
    population: pd.DataFrame,
    scoring_events: pd.DataFrame,
    team_states: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    offsets = _build_offsets(
        population,
        scoring_events,
        development_seasons=DEVELOPMENT_SEASONS,
        equivalent_games=EQUIVALENT_GAMES,
    )
    features = _feature_frame(
        population=population,
        outcomes=outcomes,
        team_states=team_states,
        offsets=offsets,
    )
    computations: dict[str, tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]] = {}
    retained: dict[str, pd.DataFrame] = {}
    for horizon in HORIZONS:
        computation = _evaluate_heads(features, horizon=horizon)
        computations[horizon] = computation
        retained[horizon] = _retained_predictions(computation[0], computation[2])
    selected_horizon, comparison = _select_horizon(
        retained["expanding"], retained["latest_five"]
    )
    selected_heads = computations[selected_horizon][2]
    calibration, variances = _calibrate_uncertainty(
        features,
        horizon=selected_horizon,
        development_seasons=DEVELOPMENT_SEASONS,
        outer_seasons=OUTER_SEASONS,
        alpha_grid=ALPHA_GRID,
        floor=SCALING_FLOOR,
        residual_floor=RESIDUAL_FLOOR,
    )
    final_models, final_calibration, final_recipes = _final_fit_rows(
        features,
        calibration,
        horizon=selected_horizon,
        retained=selected_heads,
    )
    models = pd.concat(
        [computations[selected_horizon][1], final_models], ignore_index=True
    )
    calibration = pd.concat([calibration, final_calibration], ignore_index=True)
    registry = pd.DataFrame.from_records(
        [
            {
                "horizon": horizon,
                "target": target,
                "reference_alpha": 10.0,
                "alpha_grid": ",".join(map(str, ALPHA_GRID)),
            }
            for horizon in HORIZONS
            for target in ("margin", "total")
        ]
    )
    horizon_sha = hashlib.sha256(
        comparison.to_json(
            orient="records", date_format="iso", double_precision=15
        ).encode()
    ).hexdigest()
    selection = pd.DataFrame.from_records(
        [
            {
                "selected_horizon": selected_horizon,
                "target": target,
                "selected_head": selected_heads[target],
                "selection_reason": "latest_five_gates_passed"
                if selected_horizon == "latest_five"
                else "retain_expanding",
                "horizon_sha256": horizon_sha,
            }
            for target in ("margin", "total")
        ]
    )
    outputs = {
        "forecast_registry": registry,
        "forecast_model": models,
        "forecast_prediction": retained[selected_horizon],
        "forecast_calibration": calibration,
        "window_comparison": comparison,
        "forecast_selection": selection,
    }
    for name, frame in outputs.items():
        dataset, version = FORECAST_DATASETS[name]
        validate_frame(frame, schema_for(dataset, version))
    return outputs, {
        "selected_horizon": selected_horizon,
        "selected_heads": selected_heads,
        "horizon_sha256": horizon_sha,
        "calibration_variances": variances,
        "final_fit_recipes": {
            target: {
                "head": recipe["head"],
                "alpha": recipe["alpha"],
                "training_seasons": recipe["training_seasons"],
                "inner_fallback": recipe["inner_fallback"],
            }
            for target, recipe in final_recipes.items()
        },
        "offsets_sha256": canonical_frame_digest(
            offsets, columns=tuple(offsets.columns)
        ),
    }


_OUTPUT_COLUMNS: dict[str, tuple[str, ...]] = {
    "forecast_registry": FORECAST_REGISTRY_COLUMNS,
    "forecast_model": FORECAST_MODEL_COLUMNS,
    "forecast_prediction": FORECAST_PREDICTION_COLUMNS,
    "forecast_calibration": FORECAST_CALIBRATION_COLUMNS,
    "window_comparison": WINDOW_COMPARISON_COLUMNS,
    "forecast_selection": FORECAST_SELECTION_COLUMNS,
}
_PARTITION_KEYS = {
    "forecast_model": ("horizon", "outer_season"),
    "forecast_prediction": ("season", "week"),
}


def _reconstructed_digest(
    name: str, frame: pd.DataFrame
) -> tuple[str, tuple[dict[str, Any], ...]]:
    columns = _OUTPUT_COLUMNS[name]
    partition_keys = _PARTITION_KEYS.get(name, ())
    if not partition_keys:
        return canonical_frame_digest(frame, columns=columns), ()
    parts: list[dict[str, Any]] = []
    for values, group in frame.groupby(list(partition_keys), sort=True, dropna=False):
        values = values if isinstance(values, tuple) else (values,)
        partition = {
            key: value.item() if hasattr(value, "item") else value
            for key, value in zip(partition_keys, values, strict=True)
        }
        parts.append(
            {
                "partition": partition,
                "row_count": int(len(group)),
                "records_sha": canonical_frame_digest(group, columns=columns),
            }
        )
    parts.sort(key=lambda part: partition_order_key(part["partition"]))
    return partitioned_records_sha(parts, partition_keys), tuple(parts)


def _compare_outputs(
    *,
    stored: Mapping[str, StoredOutput],
    reconstructed: Mapping[str, pd.DataFrame],
) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    for name in sorted(reconstructed):
        expected = reconstructed[name]
        actual = stored[name]
        digest, parts = _reconstructed_digest(name, expected)
        if len(expected) != int(actual.ref.get("row_count", -1)):
            raise VerificationError(f"{name} row count differs from reconstruction")
        if digest != str(actual.ref.get("records_sha")):
            raise VerificationError(f"{name} differs from independent reconstruction")
        if parts:
            declared = tuple(
                {
                    "partition": dict(part["partition"]),
                    "row_count": int(part["row_count"]),
                    "records_sha": str(part["records_sha"]),
                }
                for part in actual.parts
            )
            if parts != declared:
                raise VerificationError(
                    f"{name} partition plan differs from reconstruction"
                )
        comparisons[name] = {
            "row_count": int(len(expected)),
            "records_sha": digest,
            "partition_count": len(parts),
        }
    return comparisons


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
    emit = progress or (lambda *_args, **_kwargs: None)
    if environment != "preview":
        raise VerificationError("forecast verification is preview-only")
    manifest, manifest_raw = _read_json(
        storage, manifest_uri, label="forecast manifest"
    )
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
    if (
        identity.get("environment") != "preview"
        or tuple(identity.get("development_seasons") or ()) != DEVELOPMENT_SEASONS
        or tuple(identity.get("forbidden_seasons") or ()) != FORBIDDEN_SEASONS
    ):
        raise VerificationError("forecast manifest identity policy mismatch")
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
    emit("manifest_verified", manifest_uri=manifest_uri)

    rating, measurement, repair, parent_hashes = _verify_parent_manifests(
        storage,
        manifest=manifest,
        rating_manifest_uri=rating_manifest_uri,
        measurement_manifest_uri=measurement_manifest_uri,
        repair_manifest_uri=repair_manifest_uri,
    )
    emit("parents_verified")

    stored: dict[str, StoredOutput] = {}
    for name, value in output_refs.items():
        dataset, schema = FORECAST_DATASETS[name]
        stored[name] = _read_output(
            storage,
            value,
            expected_dataset=dataset,
            expected_schema=schema,
            label=f"forecast output {name}",
        )
        _assert_allowed_seasons(stored[name].frame, label=f"forecast output {name}")
        emit("stored_output_verified", dataset=name, rows=len(stored[name].frame))

    population, scoring_events, team_states, outcomes = _load_reconstruction_inputs(
        storage,
        rating=rating,
        measurement=measurement,
        repair=repair,
    )
    emit("reconstruction_inputs_loaded")
    reconstructed, details = _reconstruct_outputs(
        population=population,
        scoring_events=scoring_events,
        team_states=team_states,
        outcomes=outcomes,
    )
    emit("reconstruction_complete")
    comparisons = _compare_outputs(stored=stored, reconstructed=reconstructed)

    if details["selected_horizon"] != selected_horizon:
        raise VerificationError("selected horizon differs from reconstruction")
    if details["horizon_sha256"] != manifest.get("horizon_sha256"):
        raise VerificationError("horizon selection digest differs from reconstruction")
    model = reconstructed["forecast_model"]
    outer = pd.to_numeric(model["outer_season"], errors="raise").astype(int)
    final_rows = model[outer.eq(FINAL_FIT_SEASON)]
    validation_rows = model[outer.ne(FINAL_FIT_SEASON)]
    if final_rows.empty or len(final_rows) != 2:
        raise VerificationError("final-fit rows missing from reconstruction")
    head_recipes: dict[str, Any] = {}
    for target, head in details["selected_heads"].items():
        rows = validation_rows[
            validation_rows["target"].eq(target)
            & validation_rows["head"].eq(head)
            & validation_rows["retained"].eq(True)
        ]
        alphas = sorted(set(pd.to_numeric(rows["alpha"], errors="raise").astype(float)))
        if len(alphas) != 1:
            raise VerificationError(f"{target} retained head alpha is inconsistent")
        sentinel = final_rows[final_rows["target"].eq(target)]
        if len(sentinel) != 1 or not bool(sentinel.iloc[0]["retained"]):
            raise VerificationError(
                f"{target} final-fit row missing or unretained in reconstruction"
            )
        row = sentinel.iloc[0]
        window = [
            int(token)
            for token in str(row["training_seasons"]).replace(",", " ").split()
            if token.strip().isdigit()
        ]
        if not window or max(window) < 2025:
            raise VerificationError(
                f"{target} final-fit window does not train through 2025"
            )
        head_recipes[target] = {
            "head": head,
            "alpha": alphas[0],
            "final_alpha": float(pd.to_numeric(row["alpha"], errors="raise")),
            "final_training_seasons": str(row["training_seasons"]),
        }
    if head_recipes != manifest.get("head_recipes"):
        raise VerificationError("head recipes differ from reconstruction")

    calibration = reconstructed["forecast_calibration"]
    calibration_summary = {
        "records_sha": canonical_frame_digest(
            calibration, columns=FORECAST_CALIBRATION_COLUMNS
        ),
        "row_count": int(len(calibration)),
        "by_target": {
            target: {str(int(season)): variance for season, variance in seasons.items()}
            for target, seasons in details["calibration_variances"].items()
        },
    }
    if calibration_summary != manifest.get("calibration_summary"):
        raise VerificationError("calibration summary differs from reconstruction")
    preflight_sha = hashlib.sha256(
        json.dumps(
            {
                name: str(value.get("records_sha"))
                for name, value in output_refs.items()
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    if preflight_sha != manifest.get("preflight_sha256"):
        raise VerificationError("forecast preflight digest mismatch")
    emit("outputs_compared")
    return {
        "verified": True,
        "manifest_uri": manifest_uri,
        "manifest_raw_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "manifest_canonical_sha256": manifest.get("manifest_sha256"),
        "run_id": identity.get("run_id"),
        "code_sha": identity.get("code_sha"),
        "identity_sha256": identity.get("identity_sha256"),
        "selected_horizon": selected_horizon,
        "output_count": len(output_refs),
        "comparisons": comparisons,
        "parent_raw_sha256": parent_hashes,
        "offsets_sha256": details["offsets_sha256"],
        "horizon_sha256": details["horizon_sha256"],
        "rejected_seasons": [2020, 2026],
    }


def publish_verification_manifest(
    storage: Any,
    *,
    result: Mapping[str, Any],
    verifier_code_sha: str,
    rating_manifest_uri: str,
    measurement_manifest_uri: str,
    repair_manifest_uri: str,
) -> dict[str, Any]:
    """Publish the signed Preview verification record for Contract 11D.

    Writes ``verification/verifier-manifest.json`` under the verified run
    prefix. Idempotent: an existing byte-identical manifest is a no-op; any
    different bytes are a permanent collision.
    """
    manifest_uri = str(result["manifest_uri"])
    prefix = manifest_uri.rsplit("/", 1)[0]
    verifier_manifest = signed_payload(
        {
            "schema_version": VERIFICATION_MANIFEST_SCHEMA,
            "state": "verified",
            "run_id": result.get("run_id"),
            "forecast_manifest_uri": manifest_uri,
            "forecast_manifest_raw_sha256": result.get("manifest_raw_sha256"),
            "forecast_manifest_canonical_sha256": result.get(
                "manifest_canonical_sha256"
            ),
            "parents": {
                "rating_manifest_uri": rating_manifest_uri,
                "measurement_manifest_uri": measurement_manifest_uri,
                "repair_manifest_uri": repair_manifest_uri,
            },
            "selected_horizon": result.get("selected_horizon"),
            "comparisons": dict(result.get("comparisons") or {}),
            "final_fit_verified": True,
            "training_max_season": 2025,
            "verifier_code_sha": verifier_code_sha,
            "closes_findings": [
                "audit-structural-002",
                "audit-forecast-final_fit_existence-b1bc852294",
            ],
            "permitted_use": "full_lane_forecast_eligibility_closure_only",
            "production_activation_authorized": False,
            "readiness_recommendation": None,
        }
    )
    verifier_uri = f"{prefix}/verification/verifier-manifest.json"
    encoded = json.dumps(
        verifier_manifest, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(verifier_uri):
        if storage.read_bytes(verifier_uri) != encoded:
            raise VerificationError(
                "verifier manifest collision; the run is already bound to "
                "different verification evidence"
            )
    else:
        storage.write_bytes(encoded, verifier_uri)
    return {
        "published": True,
        "verifier_manifest_uri": verifier_uri,
        "verifier_manifest_sha256": verifier_manifest["manifest_sha256"],
    }
