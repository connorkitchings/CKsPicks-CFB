"""Preview-only Phase 3 measurement certification and core tournament.

This module deliberately contains no storage calls.  It turns already verified
Phase 2d frames into deterministic Phase 3 evidence so dry runs and apply runs
execute exactly the same computation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS
from cks_picks_cfb.data.data_first_phase2d import sha256, signed_payload
from cks_picks_cfb.data.data_first_phase3 import (
    CANDIDATE_COMPONENTS,
    CORE_CANDIDATES,
    PHASE3_ADJUSTED_COLUMNS,
    PHASE3_ATTRIBUTION_COLUMNS,
    PHASE3_PREDICTION_COLUMNS,
    PHASE3_RETAINED_CORE_SCHEMA,
    Phase3Error,
)
from cks_picks_cfb.ratings.contracts import (
    OBSERVATION_COLUMNS,
    MeasurementConfig,
    assert_no_market_fields,
)

PASS_RUSH_COMPONENTS = ("epa_pass", "epa_rush")
ADJUSTED_COMPONENTS = (
    "epa_per_play",
    "success_rate",
    "explosive_rate_20",
    "points_per_scoring_opportunity",
    *PASS_RUSH_COMPONENTS,
)
VALIDATION_SEASONS = (2018, 2019, 2021, 2022, 2023, 2024, 2025)
RECENCY_MODES = ("primary", "half_life_4_games")
RATING_RECENCY_MODES = (
    "primary",
    "half_life_2_games",
    "half_life_4_games",
    "half_life_8_games",
)
TARGETS = ("margin", "total")

_NON_COUNT_PLAY_TYPES = ("Timeout", "Uncategorized", "placeholder", "End Period")
_EQUIVALENT_EXPOSURE = {
    "epa_per_play": 100.0,
    "epa_pass": 100.0,
    "epa_rush": 100.0,
    "success_rate": 100.0,
    "explosive_rate_20": 100.0,
    "points_per_scoring_opportunity": 8.0,
}
_FALLBACK_CENTER_SCALE = {
    "epa_per_play": (0.00, 0.15),
    "epa_pass": (0.00, 0.15),
    "epa_rush": (0.00, 0.15),
    "success_rate": (0.42, 0.06),
    "explosive_rate_20": (0.10, 0.04),
    "points_per_scoring_opportunity": (4.00, 0.75),
}
_SCALE_FLOOR = {
    "epa_per_play": 0.05,
    "epa_pass": 0.05,
    "epa_rush": 0.05,
    "success_rate": 0.02,
    "explosive_rate_20": 0.01,
    "points_per_scoring_opportunity": 0.25,
}


@dataclass(frozen=True)
class Phase3Computation:
    observations: pd.DataFrame
    adjusted_measurements: pd.DataFrame
    fold_predictions: pd.DataFrame
    attribution: pd.DataFrame
    retained_core: dict[str, Any]
    certification: dict[str, Any]


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")


def build_pass_rush_observations(
    *, byplay: pd.DataFrame, base_observations: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build canonical, mutually exclusive pass/rush EPA observations.

    Classification is deliberately fail closed: exactly one of ``dropback`` or
    ``rush_attempt`` must be one.  Ambiguous rows, non-drive plays, garbage-time
    plays, and missing-PPA rows remain counted in the returned audit rather than
    being silently assigned to a component.
    """
    required = {
        "season",
        "game_id",
        "offense",
        "defense",
        "play_type",
        "st",
        "penalty",
        "twopoint",
        "garbage",
        "ppa",
        "dropback",
        "rush_attempt",
    }
    if missing := sorted(required - set(byplay)):
        raise Phase3Error(f"byplay cannot classify pass/rush EPA: {missing}")
    assert_no_market_fields(base_observations.columns, context="Phase 3 observations")

    accepted = set(
        base_observations[["season", "game_id"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    plays = byplay.copy()
    plays["season"] = _numeric(plays, "season").astype("Int64")
    plays["game_id"] = _numeric(plays, "game_id").astype("Int64")
    plays = plays[
        plays[["season", "game_id"]].apply(tuple, axis=1).isin(accepted)
    ].copy()
    drive_play = (
        (_numeric(plays, "st").fillna(0) == 0)
        & (_numeric(plays, "penalty").fillna(0) == 0)
        & (_numeric(plays, "twopoint").fillna(0) == 0)
        & ~plays["play_type"].astype(str).isin(_NON_COUNT_PLAY_TYPES)
    )
    non_garbage = _numeric(plays, "garbage") == 0
    dropback = _numeric(plays, "dropback") == 1
    rush = _numeric(plays, "rush_attempt") == 1
    ppa = _numeric(plays, "ppa")
    plays["classification"] = np.select(
        [dropback & ~rush, rush & ~dropback], ["pass", "rush"], default="ambiguous"
    )
    plays["eligible_classified"] = (
        drive_play
        & non_garbage
        & (plays["classification"] != "ambiguous")
        & ppa.notna()
    )
    eligible = plays[plays["eligible_classified"]].copy()
    eligible["ppa_numeric"] = _numeric(eligible, "ppa")

    metadata = base_observations[
        base_observations["measurement_id"] == "epa_per_play"
    ].set_index(["season", "game_id", "team", "unit_role"])
    rows: list[dict[str, Any]] = []
    for key, source in metadata.iterrows():
        season, game_id, team, role = key
        side_column = "offense" if role == "offense" else "defense"
        team_plays = eligible[
            (eligible["season"] == season)
            & (eligible["game_id"] == game_id)
            & (eligible[side_column].astype(str) == str(team))
        ]
        for classification, measurement_id in (
            ("pass", "epa_pass"),
            ("rush", "epa_rush"),
        ):
            selected = team_plays[team_plays["classification"] == classification]
            denominator = float(len(selected))
            numerator = float(selected["ppa_numeric"].sum()) if denominator else 0.0
            record = source.to_dict()
            record.update(
                {
                    "season": int(season),
                    "game_id": int(game_id),
                    "team": str(team),
                    "unit_role": str(role),
                    "measurement_id": measurement_id,
                    "numerator": numerator,
                    "denominator": denominator,
                    "raw_value": numerator / denominator if denominator else None,
                    "coverage_status": "observed" if denominator else "missing",
                    "missing_reason": None if denominator else "zero_denominator",
                    "exposure_unit": "plays",
                }
            )
            rows.append({column: record.get(column) for column in OBSERVATION_COLUMNS})

    frame = pd.DataFrame.from_records(rows, columns=OBSERVATION_COLUMNS)
    audit = {
        "source_rows": int(len(plays)),
        "eligible_pass_rows": int(
            ((plays["classification"] == "pass") & plays["eligible_classified"]).sum()
        ),
        "eligible_rush_rows": int(
            ((plays["classification"] == "rush") & plays["eligible_classified"]).sum()
        ),
        "excluded_non_drive_play": int((~drive_play).sum()),
        "excluded_garbage_or_missing_flag": int((drive_play & ~non_garbage).sum()),
        "excluded_ambiguous_classification": int(
            (drive_play & non_garbage & (plays["classification"] == "ambiguous")).sum()
        ),
        "excluded_missing_ppa": int(
            (
                drive_play
                & non_garbage
                & (plays["classification"] != "ambiguous")
                & ppa.isna()
            ).sum()
        ),
    }
    audit["classified_or_explained"] = (
        sum(int(value) for key, value in audit.items() if key != "source_rows")
        == audit["source_rows"]
    )
    return frame, audit


def independent_definition_audit(
    *, byplay: pd.DataFrame, drives: pd.DataFrame, observations: pd.DataFrame
) -> dict[str, Any]:
    """Independently recompute play/drive numerators and denominators."""
    plays = byplay.copy()
    plays["season"] = _numeric(plays, "season").astype("Int64")
    plays["game_id"] = _numeric(plays, "game_id").astype("Int64")
    accepted = set(
        observations[["season", "game_id"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    plays = plays[
        plays[["season", "game_id"]].apply(tuple, axis=1).isin(accepted)
    ].copy()
    eligible = plays[
        (_numeric(plays, "st").fillna(0) == 0)
        & (_numeric(plays, "penalty").fillna(0) == 0)
        & (_numeric(plays, "twopoint").fillna(0) == 0)
        & ~plays["play_type"].astype(str).isin(_NON_COUNT_PLAY_TYPES)
        & (_numeric(plays, "garbage") == 0)
    ].copy()
    eligible["ppa_numeric"] = _numeric(eligible, "ppa")
    eligible["success_numeric"] = _numeric(eligible, "success")
    eligible["yards_numeric"] = _numeric(eligible, "yards_gained")
    eligible["turnover_numeric"] = _numeric(eligible, "turnover")

    expected_rows: list[dict[str, Any]] = []

    def append_play_metrics(role: str, team_column: str) -> None:
        for key, rows in eligible.groupby(
            ["season", "game_id", team_column], sort=False
        ):
            season, game_id, team = key
            ppa = rows["ppa_numeric"]
            success = rows["success_numeric"]
            values = {
                "epa_per_play": (float(ppa.sum()), float(ppa.notna().sum())),
                "success_rate": (
                    float((success == 1).sum()),
                    float(success.notna().sum()),
                ),
                "explosive_rate_20": (
                    float((rows["yards_numeric"] >= 20).sum()),
                    float(len(rows)),
                ),
                "turnover_rate": (
                    float((rows["turnover_numeric"] == 1).sum()),
                    float(len(rows)),
                ),
            }
            for measurement_id, (numerator, denominator) in values.items():
                expected_rows.append(
                    {
                        "season": int(season),
                        "game_id": int(game_id),
                        "team": str(team),
                        "unit_role": role,
                        "measurement_id": measurement_id,
                        "expected_numerator": numerator,
                        "expected_denominator": denominator,
                    }
                )

    append_play_metrics("offense", "offense")
    append_play_metrics("defense", "defense")

    drive_keys = (
        eligible.groupby(
            ["season", "game_id", "drive_number", "offense", "defense"], sort=False
        )
        .size()
        .rename("eligible_plays")
        .reset_index()
    )
    eligible_drives = drives.copy()
    eligible_drives["season"] = _numeric(eligible_drives, "season").astype("Int64")
    eligible_drives["game_id"] = _numeric(eligible_drives, "game_id").astype("Int64")
    eligible_drives = eligible_drives.merge(
        drive_keys,
        on=["season", "game_id", "drive_number", "offense", "defense"],
        how="inner",
        validate="one_to_one",
    )
    eligible_drives["start_distance"] = 100 - _numeric(
        eligible_drives, "start_yards_to_goal"
    )
    for role, team_column in (("offense", "offense"), ("defense", "defense")):
        valid_starts = eligible_drives[eligible_drives["start_distance"].notna()]
        for key, rows in valid_starts.groupby(
            ["season", "game_id", team_column], sort=False
        ):
            season, game_id, team = key
            expected_rows.append(
                {
                    "season": int(season),
                    "game_id": int(game_id),
                    "team": str(team),
                    "unit_role": role,
                    "measurement_id": "average_start_field_position",
                    "expected_numerator": float(rows["start_distance"].sum()),
                    "expected_denominator": float(len(rows)),
                }
            )
    for key, rows in eligible_drives.groupby(
        ["season", "game_id", "offense"], sort=False
    ):
        season, game_id, team = key
        expected_rows.append(
            {
                "season": int(season),
                "game_id": int(game_id),
                "team": str(team),
                "unit_role": "offense",
                "measurement_id": "plays_per_drive",
                "expected_numerator": float(rows["eligible_plays"].sum()),
                "expected_denominator": float(len(rows)),
            }
        )

    keys = ["season", "game_id", "team", "unit_role", "measurement_id"]
    expected = pd.DataFrame.from_records(expected_rows)
    actual = observations[
        observations["measurement_id"].isin(
            [
                "epa_per_play",
                "success_rate",
                "explosive_rate_20",
                "turnover_rate",
                "average_start_field_position",
                "plays_per_drive",
            ]
        )
    ][keys + ["numerator", "denominator"]].copy()
    compared = actual.merge(expected, on=keys, how="left", validate="one_to_one")
    # A missing expected aggregate is a legitimate explicit zero-exposure row.
    compared[["expected_numerator", "expected_denominator"]] = compared[
        ["expected_numerator", "expected_denominator"]
    ].fillna(0.0)
    compared["numerator_delta"] = _numeric(compared, "numerator") - _numeric(
        compared, "expected_numerator"
    )
    compared["denominator_delta"] = _numeric(compared, "denominator") - _numeric(
        compared, "expected_denominator"
    )
    exact = np.isclose(compared["numerator_delta"], 0.0, atol=1e-12) & np.isclose(
        compared["denominator_delta"], 0.0, atol=1e-12
    )
    sampled = compared.sort_values(keys, kind="mergesort").head(50)
    return {
        "all_rows_exact": bool(exact.all()),
        "compared_rows": int(len(compared)),
        "mismatch_rows": int((~exact).sum()),
        "maximum_abs_numerator_delta": float(
            compared["numerator_delta"].abs().max() if len(compared) else 0.0
        ),
        "maximum_abs_denominator_delta": float(
            compared["denominator_delta"].abs().max() if len(compared) else 0.0
        ),
        "sample_sha256": sha256(sampled.to_dict("records")),
        "aggregate_sha256": sha256(
            compared.groupby("measurement_id", sort=True)[
                [
                    "numerator",
                    "denominator",
                    "expected_numerator",
                    "expected_denominator",
                ]
            ]
            .sum()
            .reset_index()
            .to_dict("records")
        ),
    }


def _recency_weight(history: pd.DataFrame, half_life: float) -> pd.DataFrame:
    if history.empty:
        return history
    weighted = history.sort_values(
        ["season", "team", "measurement_id", "unit_role", "week", "game_id"],
        ascending=[True, True, True, True, False, False],
        kind="mergesort",
    ).copy()
    age = weighted.groupby(
        ["season", "team", "measurement_id", "unit_role"], sort=False
    ).cumcount()
    weight = np.power(0.5, age.to_numpy(dtype=float) / half_life)
    weighted["numerator"] = _numeric(weighted, "numerator") * weight
    weighted["denominator"] = _numeric(weighted, "denominator") * weight
    return weighted


def _simple_adjustment(rows: pd.DataFrame, role: str) -> dict[str, dict[str, float]]:
    selected = rows[rows["unit_role"] == role]
    if selected.empty:
        return {}
    grouped = selected.groupby("team", sort=False).agg(
        numerator=("numerator", "sum"),
        denominator=("denominator", "sum"),
        games=("game_id", "nunique"),
    )
    return {
        str(team): {
            "raw": float(row.numerator / row.denominator)
            if row.denominator > 0
            else float("nan"),
            "adjusted": float(row.numerator / row.denominator)
            if row.denominator > 0
            else float("nan"),
            "league_center": float("nan"),
            "schedule_strength": 0.0,
            "games": int(row.games),
            "exposure": float(row.denominator),
        }
        for team, row in grouped.iterrows()
    }


def _weighted_center(values: Mapping[str, float], evidence: pd.DataFrame) -> float:
    weights = evidence.set_index("team")["denominator"].to_dict()
    pairs = [
        (value, float(weights[team]))
        for team, value in values.items()
        if np.isfinite(value) and float(weights.get(team, 0.0)) > 0
    ]
    if not pairs:
        return float("nan")
    return float(
        np.average(
            [value for value, _ in pairs],
            weights=[weight for _, weight in pairs],
        )
    )


def _four_iteration_adjustment(
    rows: pd.DataFrame, iterations: int
) -> dict[str, dict[str, dict[str, float]]]:
    """Independent additive opponent adjustment used only by Phase 3."""
    if iterations != 4:
        raise Phase3Error(
            "Phase 3 opponent adjustment requires exactly four iterations"
        )
    evidence: dict[str, pd.DataFrame] = {}
    raw: dict[str, dict[str, float]] = {}
    adjusted: dict[str, dict[str, float]] = {}
    edges: dict[str, pd.DataFrame] = {}
    for role in ("offense", "defense"):
        role_rows = rows[rows["unit_role"] == role]
        grouped = (
            role_rows.groupby("team", sort=False)
            .agg(
                numerator=("numerator", "sum"),
                denominator=("denominator", "sum"),
                games=("game_id", "nunique"),
            )
            .reset_index()
        )
        evidence[role] = grouped
        raw[role] = {
            str(row.team): float(row.numerator / row.denominator)
            if row.denominator > 0
            else float("nan")
            for row in grouped.itertuples(index=False)
        }
        adjusted[role] = dict(raw[role])
        edges[role] = role_rows[
            ["game_id", "team", "opponent", "denominator"]
        ].drop_duplicates()

    centers = {"offense": float("nan"), "defense": float("nan")}
    strengths: dict[str, dict[str, float]] = {"offense": {}, "defense": {}}
    for _ in range(iterations):
        centers = {
            role: _weighted_center(adjusted[role], evidence[role])
            for role in ("offense", "defense")
        }
        updated: dict[str, dict[str, float]] = {}
        for role, opponent_role in (("offense", "defense"), ("defense", "offense")):
            next_values = dict(raw[role])
            role_strengths = {team: 0.0 for team in raw[role]}
            if not edges[role].empty and np.isfinite(centers[opponent_role]):
                opponent_values = pd.Series(
                    adjusted[opponent_role], name="opponent_adjusted", dtype=float
                )
                deltas = (
                    edges[role]
                    .merge(
                        opponent_values,
                        left_on="opponent",
                        right_index=True,
                        how="left",
                    )
                    .dropna(subset=["opponent_adjusted"])
                )
                deltas["weighted_delta"] = (
                    deltas["opponent_adjusted"] - centers[opponent_role]
                ) * deltas["denominator"]
                totals = deltas.groupby("team", sort=False).agg(
                    weighted_delta=("weighted_delta", "sum"),
                    denominator=("denominator", "sum"),
                )
                for team, value in raw[role].items():
                    if team in totals.index and totals.loc[team, "denominator"] > 0:
                        strength = float(
                            totals.loc[team, "weighted_delta"]
                            / totals.loc[team, "denominator"]
                        )
                        role_strengths[team] = strength
                        next_values[team] = value - strength
            updated[role] = next_values
            strengths[role] = role_strengths
        adjusted = updated

    result: dict[str, dict[str, dict[str, float]]] = {}
    for role, opponent_role in (("offense", "defense"), ("defense", "offense")):
        indexed = evidence[role].set_index("team") if not evidence[role].empty else None
        result[role] = {
            team: {
                "raw": raw[role][team],
                "adjusted": adjusted[role][team],
                "league_center": centers[opponent_role],
                "schedule_strength": strengths[role].get(team, 0.0),
                "games": int(indexed.loc[team, "games"]) if indexed is not None else 0,
                "exposure": float(indexed.loc[team, "denominator"])
                if indexed is not None
                else 0.0,
            }
            for team in raw[role]
        }
    return result


def _measurement_adjustments(
    rows: pd.DataFrame, measurement_id: str, iterations: int
) -> dict[str, dict[str, dict[str, float]]]:
    if measurement_id in ADJUSTED_COMPONENTS:
        return _four_iteration_adjustment(rows, iterations)
    return {role: _simple_adjustment(rows, role) for role in ("offense", "defense")}


def build_adjusted_measurements(
    *,
    observations: pd.DataFrame,
    games: pd.DataFrame,
    config: MeasurementConfig,
    identity_sha: str,
    code_sha: str,
    config_sha: str,
    recency_mode: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build week-open pregame and season-terminal iteration-0/4 measurements."""
    if recency_mode not in RATING_RECENCY_MODES:
        raise Phase3Error(f"unsupported recency mode: {recency_mode}")
    if observations["season"].isin(FORBIDDEN_SEASONS).any():
        raise Phase3Error("Phase 3 observations include 2020")

    schedule = games.copy()
    schedule["season"] = _numeric(schedule, "season").astype(int)
    schedule["week"] = _numeric(schedule, "week").astype(int)
    schedule["game_id"] = _numeric(schedule, "game_id").astype(int)
    schedule["kickoff_ts"] = pd.to_datetime(
        schedule["kickoff_utc"], utc=True, errors="raise"
    )
    accepted_ids = set(
        observations[["season", "game_id"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    schedule = schedule[
        schedule[["season", "game_id"]].apply(tuple, axis=1).isin(accepted_ids)
    ].copy()
    if schedule.duplicated(["season", "game_id"]).any():
        raise Phase3Error("Phase 3 schedule contains duplicate games")

    source = observations.copy()
    source["season"] = _numeric(source, "season").astype(int)
    source["week"] = _numeric(source, "week").astype(int)
    measurement_ids = tuple(sorted(set(source["measurement_id"].astype(str))))
    roles_by_measurement = {
        measurement_id: tuple(
            sorted(
                set(
                    source.loc[
                        source["measurement_id"] == measurement_id, "unit_role"
                    ].astype(str)
                )
            )
        )
        for measurement_id in measurement_ids
    }
    source = source[source["coverage_status"] == "observed"].copy()
    records: list[dict[str, Any]] = []
    terminal_records: list[dict[str, Any]] = []

    def adjusted_for(
        history: pd.DataFrame,
    ) -> dict[str, dict[str, dict[str, dict[str, float]]]]:
        return {
            measurement_id: _measurement_adjustments(
                history[history["measurement_id"] == measurement_id],
                measurement_id,
                config.adjustment_iterations,
            )
            for measurement_id in measurement_ids
        }

    for season in DEVELOPMENT_SEASONS:
        season_schedule = schedule[schedule["season"] == season]
        season_observations = source[source["season"] == season]
        for week in sorted(set(season_schedule["week"])):
            week_games = season_schedule[season_schedule["week"] == week].sort_values(
                ["kickoff_ts", "game_id"], kind="mergesort"
            )
            history = season_observations[season_observations["week"] < week]
            half_life = {
                "half_life_2_games": 2.0,
                "half_life_4_games": 4.0,
                "half_life_8_games": 8.0,
            }.get(recency_mode)
            effective_history = (
                _recency_weight(history, half_life=half_life)
                if half_life is not None
                else history
            )
            cache = adjusted_for(effective_history)
            totals = (
                effective_history.groupby(
                    ["measurement_id", "unit_role", "team"], sort=False
                )
                .agg(numerator=("numerator", "sum"), denominator=("denominator", "sum"))
                .to_dict("index")
            )
            for game in week_games.itertuples(index=False):
                for team in (str(game.home_team), str(game.away_team)):
                    for measurement_id in measurement_ids:
                        for role in roles_by_measurement[measurement_id]:
                            value = cache[measurement_id].get(role, {}).get(team)
                            sums = totals.get((measurement_id, role, team), {})
                            raw = value["raw"] if value is not None else float("nan")
                            adjusted = (
                                value["adjusted"] if value is not None else float("nan")
                            )
                            exposure = value["exposure"] if value is not None else 0.0
                            for iteration, output_value in ((0, raw), (4, adjusted)):
                                records.append(
                                    {
                                        "season": season,
                                        "week": int(week),
                                        "as_of_game_id": int(game.game_id),
                                        "as_of_kickoff_utc": game.kickoff_ts.isoformat(),
                                        "team": team,
                                        "measurement_id": measurement_id,
                                        "unit_role": role,
                                        "recency_mode": recency_mode,
                                        "adjustment_iteration": iteration,
                                        "numerator": float(sums.get("numerator", 0.0)),
                                        "denominator": float(
                                            sums.get("denominator", 0.0)
                                        ),
                                        "primary_exposure": exposure,
                                        "games_exposure": int(
                                            value["games"] if value else 0
                                        ),
                                        "raw_value": None
                                        if not np.isfinite(raw)
                                        else raw,
                                        "adjusted_value": None
                                        if not np.isfinite(output_value)
                                        else output_value,
                                        "league_center": None
                                        if value is None
                                        or not np.isfinite(value["league_center"])
                                        else value["league_center"],
                                        "schedule_strength_component": None
                                        if value is None
                                        else value["schedule_strength"],
                                        "coverage_status": "observed"
                                        if exposure > 0 and np.isfinite(output_value)
                                        else "missing",
                                        "missing_reason": None
                                        if exposure > 0 and np.isfinite(output_value)
                                        else "no_prior_week_evidence",
                                        "parent_identity_sha": identity_sha,
                                        "code_sha": code_sha,
                                        "config_sha": config_sha,
                                    }
                                )
        terminal_half_life = {
            "half_life_2_games": 2.0,
            "half_life_4_games": 4.0,
            "half_life_8_games": 8.0,
        }.get(recency_mode)
        terminal_history = (
            _recency_weight(season_observations, half_life=terminal_half_life)
            if terminal_half_life is not None
            else season_observations
        )
        terminal_cache = adjusted_for(terminal_history)
        for measurement_id in measurement_ids:
            for role in roles_by_measurement[measurement_id]:
                for team, value in terminal_cache[measurement_id].get(role, {}).items():
                    terminal_records.append(
                        {
                            "season": season,
                            "team": team,
                            "measurement_id": measurement_id,
                            "unit_role": role,
                            "recency_mode": recency_mode,
                            "adjusted_value": value["adjusted"],
                            "primary_exposure": value["exposure"],
                            "games_exposure": value["games"],
                        }
                    )
    return (
        pd.DataFrame.from_records(records, columns=PHASE3_ADJUSTED_COLUMNS),
        pd.DataFrame.from_records(terminal_records),
    )


def _scales(
    terminal: pd.DataFrame, season: int
) -> dict[tuple[str, str], tuple[float, float]]:
    prior = terminal[terminal["season"] < season]
    result: dict[tuple[str, str], tuple[float, float]] = {}
    for measurement_id in ADJUSTED_COMPONENTS:
        for role in ("offense", "defense"):
            values = _numeric(
                prior[
                    (prior["measurement_id"] == measurement_id)
                    & (prior["unit_role"] == role)
                ],
                "adjusted_value",
            ).dropna()
            if len(values) >= 2:
                center = float(values.mean())
                scale = max(float(values.std(ddof=1)), _SCALE_FLOOR[measurement_id])
            else:
                center, scale = _FALLBACK_CENTER_SCALE[measurement_id]
            result[(measurement_id, role)] = (center, scale)
    return result


def _posterior(
    prior_mean: float,
    prior_variance: float,
    observed_z: float | None,
    exposure: float,
    equivalent_exposure: float,
) -> tuple[float, float]:
    prior_precision = 1.0 / prior_variance
    observation_precision = (
        exposure / equivalent_exposure if observed_z is not None else 0.0
    )
    total = prior_precision + observation_precision
    mean = (
        prior_precision * prior_mean + observation_precision * (observed_z or 0.0)
    ) / total
    return float(mean), float(1.0 / total)


def build_component_states(
    *, adjusted: pd.DataFrame, terminal: pd.DataFrame, recency_mode: str
) -> pd.DataFrame:
    """Apply the fixed rho=.60 exposure updater without selecting it."""
    current = adjusted[
        (adjusted["recency_mode"] == recency_mode)
        & (adjusted["adjustment_iteration"] == 4)
        & adjusted["measurement_id"].isin(ADJUSTED_COMPONENTS)
    ].copy()
    terminal = terminal[
        (terminal["recency_mode"] == recency_mode)
        & terminal["measurement_id"].isin(ADJUSTED_COMPONENTS)
    ].copy()
    terminal_states: dict[int, dict[tuple[str, str, str], tuple[float, float]]] = {}
    rows: list[dict[str, Any]] = []
    for season in DEVELOPMENT_SEASONS:
        scales = _scales(terminal, season)
        previous_seasons = [value for value in DEVELOPMENT_SEASONS if value < season]
        source_season = previous_seasons[-1] if previous_seasons else None
        decay_steps = season - source_season if source_season is not None else 0
        priors = (
            terminal_states.get(source_season, {}) if source_season is not None else {}
        )
        season_rows = current[current["season"] == season]
        for row in season_rows.itertuples(index=False):
            key = (str(row.team), str(row.measurement_id), str(row.unit_role))
            prior = priors.get(key)
            if prior is None:
                prior_mean, prior_variance = 0.0, 1.0
            else:
                decay = 0.60**decay_steps
                prior_mean = decay * prior[0]
                prior_variance = decay**2 * prior[1] + (1 - decay**2)
            center, scale = scales[(row.measurement_id, row.unit_role)]
            native = pd.to_numeric(
                pd.Series([row.adjusted_value]), errors="coerce"
            ).iloc[0]
            observed_z = None if pd.isna(native) else float((native - center) / scale)
            if row.unit_role == "defense" and observed_z is not None:
                observed_z *= -1
            mean, variance = _posterior(
                prior_mean,
                prior_variance,
                observed_z,
                float(row.primary_exposure),
                _EQUIVALENT_EXPOSURE[row.measurement_id],
            )
            available = observed_z is not None or prior is not None
            rows.append(
                {
                    "season": season,
                    "week": int(row.week),
                    "game_id": int(row.as_of_game_id),
                    "kickoff_utc": row.as_of_kickoff_utc,
                    "team": str(row.team),
                    "measurement_id": str(row.measurement_id),
                    "unit_role": str(row.unit_role),
                    "recency_mode": recency_mode,
                    "state_value": mean if available else None,
                    "state_uncertainty": float(np.sqrt(variance))
                    if available
                    else None,
                    "evidence_available": available,
                    "prior_source_season": source_season if prior is not None else None,
                    "annual_decay_steps": decay_steps if prior is not None else None,
                    "standardization_center": center,
                    "standardization_scale": scale,
                }
            )

        terminal_native = terminal[terminal["season"] == season]
        next_states: dict[tuple[str, str, str], tuple[float, float]] = {}
        for row in terminal_native.itertuples(index=False):
            key = (str(row.team), str(row.measurement_id), str(row.unit_role))
            prior = priors.get(key)
            if prior is None:
                prior_mean, prior_variance = 0.0, 1.0
            else:
                decay = 0.60**decay_steps
                prior_mean = decay * prior[0]
                prior_variance = decay**2 * prior[1] + (1 - decay**2)
            center, scale = scales[(row.measurement_id, row.unit_role)]
            observed_z = (float(row.adjusted_value) - center) / scale
            if row.unit_role == "defense":
                observed_z *= -1
            next_states[key] = _posterior(
                prior_mean,
                prior_variance,
                observed_z,
                float(row.primary_exposure),
                _EQUIVALENT_EXPOSURE[row.measurement_id],
            )
        terminal_states[season] = next_states
    return pd.DataFrame.from_records(rows)


def _candidate_features(states: pd.DataFrame, candidate: str) -> pd.DataFrame:
    components = CANDIDATE_COMPONENTS[candidate]
    selected = states[states["measurement_id"].isin(components)].copy()
    grouped = selected.groupby(
        ["season", "week", "game_id", "kickoff_utc", "team", "unit_role"],
        sort=False,
    )
    composites = grouped.agg(
        component_rows=("measurement_id", "nunique"),
        available_rows=("evidence_available", "sum"),
        state_value=("state_value", "mean"),
        state_uncertainty=(
            "state_uncertainty",
            lambda values: float(np.sqrt(np.square(values.dropna()).sum()))
            / len(components)
            if len(values.dropna())
            else np.nan,
        ),
    ).reset_index()
    complete = (composites["component_rows"] == len(components)) & (
        composites["available_rows"] == len(components)
    )
    composites.loc[~complete, ["state_value", "state_uncertainty"]] = np.nan

    team_sides = states[
        ["season", "week", "game_id", "kickoff_utc", "team"]
    ].drop_duplicates()
    ordered_teams = team_sides.sort_values(
        ["season", "game_id", "team"], kind="mergesort"
    )
    # Team names alone do not encode sides.  The caller replaces these with the
    # authoritative schedule sides before fitting.
    game_count = states[["season", "game_id"]].drop_duplicates().shape[0]
    if len(ordered_teams) < game_count * 2:
        raise Phase3Error(f"candidate {candidate} lacks two teams per game")
    return composites


def _game_features(
    *, states: pd.DataFrame, games: pd.DataFrame, candidate: str
) -> pd.DataFrame:
    composites = _candidate_features(states, candidate)
    schedule = games[
        ["season", "week", "game_id", "kickoff_utc", "home_team", "away_team"]
    ].drop_duplicates(["season", "game_id"])
    result = schedule.copy()
    for side in ("home", "away"):
        for role in ("offense", "defense"):
            values = composites[composites["unit_role"] == role][
                [
                    "season",
                    "game_id",
                    "team",
                    "state_value",
                    "state_uncertainty",
                ]
            ].rename(
                columns={
                    "team": f"{side}_team_join",
                    "state_value": f"{side}_{role}",
                    "state_uncertainty": f"{side}_{role}_uncertainty",
                }
            )
            result = result.merge(
                values,
                left_on=["season", "game_id", f"{side}_team"],
                right_on=["season", "game_id", f"{side}_team_join"],
                how="left",
                validate="one_to_one",
            ).drop(columns=[f"{side}_team_join"])
    result["candidate"] = candidate
    return result


def _prepare_fold(
    train: pd.DataFrame,
    validate: pd.DataFrame,
    feature_names: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    train = train.copy()
    validate = validate.copy()
    fallback_means: dict[str, float] = {}
    fallback_uncertainty: dict[str, float] = {}
    train_fallback = pd.Series(False, index=train.index)
    validate_fallback = pd.Series(False, index=validate.index)
    for feature in feature_names:
        values = _numeric(train, feature)
        finite = values[np.isfinite(values)]
        if finite.empty:
            raise Phase3Error(f"training fold has no finite values for {feature}")
        mean = float(finite.mean())
        fallback_means[feature] = mean
        train_missing = ~np.isfinite(_numeric(train, feature))
        validate_missing = ~np.isfinite(_numeric(validate, feature))
        train_fallback |= train_missing
        validate_fallback |= validate_missing
        train.loc[train_missing, feature] = mean
        validate.loc[validate_missing, feature] = mean
        uncertainty = f"{feature}_uncertainty"
        train_uncertainty = _numeric(train, uncertainty)
        finite_uncertainty = train_uncertainty[np.isfinite(train_uncertainty)]
        maximum = (
            float(finite_uncertainty.max()) if not finite_uncertainty.empty else 1.0
        )
        fallback_uncertainty[feature] = maximum
        train.loc[~np.isfinite(train_uncertainty), uncertainty] = maximum
        validate.loc[~np.isfinite(_numeric(validate, uncertainty)), uncertainty] = (
            maximum
        )
    x_train = train[list(feature_names)].to_numpy(dtype=float)
    x_validate = validate[list(feature_names)].to_numpy(dtype=float)
    center = x_train.mean(axis=0)
    scale = x_train.std(axis=0, ddof=0)
    scale[~np.isfinite(scale) | (scale == 0)] = 1.0
    return (
        (x_train - center) / scale,
        (x_validate - center) / scale,
        {
            "center": center.tolist(),
            "scale": scale.tolist(),
            "fallback_means": fallback_means,
            "fallback_uncertainty": fallback_uncertainty,
            "train_fallback": train_fallback,
            "validate_fallback": validate_fallback,
            "validate_frame": validate,
        },
    )


def run_candidate_tournament(
    *,
    primary_states: pd.DataFrame,
    sensitivity_states: pd.DataFrame,
    games: pd.DataFrame,
    outcomes: pd.DataFrame,
    ridge_alpha: float,
) -> pd.DataFrame:
    """Fit the sealed expanding-season Ridge scaffold for every candidate."""
    assert_no_market_fields(primary_states.columns, context="Phase 3 model inputs")
    schedule = games.copy()
    for column in ("season", "week", "game_id"):
        schedule[column] = _numeric(schedule, column).astype(int)
    schedule = schedule[
        [
            "season",
            "week",
            "game_id",
            "kickoff_utc",
            "home_team",
            "away_team",
        ]
    ].drop_duplicates(["season", "game_id"])
    accepted = set(
        primary_states[["season", "game_id"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    schedule = schedule[
        schedule[["season", "game_id"]].apply(tuple, axis=1).isin(accepted)
    ].copy()
    scores = outcomes[["season", "game_id", "home_points", "away_points"]].copy()
    scores["season"] = _numeric(scores, "season").astype(int)
    scores["game_id"] = _numeric(scores, "game_id").astype(int)
    scores["home_points"] = _numeric(scores, "home_points")
    scores["away_points"] = _numeric(scores, "away_points")
    universe = schedule.merge(
        scores, on=["season", "game_id"], how="inner", validate="one_to_one"
    )
    if len(universe) != len(schedule):
        raise Phase3Error("eligible Phase 3 game population lost an outcome row")
    if not np.isfinite(universe[["home_points", "away_points"]].to_numpy()).all():
        raise Phase3Error("eligible Phase 3 outcomes contain non-finite scores")
    universe["margin"] = universe["home_points"] - universe["away_points"]
    universe["total"] = universe["home_points"] + universe["away_points"]
    if universe["season"].isin(FORBIDDEN_SEASONS).any():
        raise Phase3Error("Phase 3 tournament contains 2020")

    features = ("home_offense", "home_defense", "away_offense", "away_defense")
    output: list[dict[str, Any]] = []
    for recency_mode, states in (
        ("primary", primary_states),
        ("half_life_4_games", sensitivity_states),
    ):
        for candidate in CORE_CANDIDATES:
            candidate_frame = _game_features(
                states=states, games=universe, candidate=candidate
            ).merge(
                universe[
                    [
                        "season",
                        "game_id",
                        "home_points",
                        "away_points",
                        "margin",
                        "total",
                    ]
                ],
                on=["season", "game_id"],
                how="inner",
                validate="one_to_one",
            )
            for validation_season in VALIDATION_SEASONS:
                train = candidate_frame[candidate_frame["season"] < validation_season]
                validate = candidate_frame[
                    candidate_frame["season"] == validation_season
                ]
                if train.empty or validate.empty:
                    raise Phase3Error(
                        f"empty temporal fold for validation season {validation_season}"
                    )
                x_train, x_validate, metadata = _prepare_fold(train, validate, features)
                completed_training_seasons = sorted(set(train["season"].astype(int)))
                if any(
                    season >= validation_season for season in completed_training_seasons
                ):
                    raise Phase3Error("future season entered a Phase 3 training fold")
                validate_prepared = metadata["validate_frame"]
                for target in TARGETS:
                    model = Ridge(alpha=ridge_alpha)
                    model.fit(x_train, _numeric(train, target).to_numpy(dtype=float))
                    predictions = model.predict(x_validate)
                    for position, row in enumerate(
                        validate_prepared.itertuples(index=False)
                    ):
                        fallback = bool(metadata["validate_fallback"].iloc[position])
                        fallback_count = sum(
                            int(
                                not np.isfinite(
                                    float(getattr(validate.iloc[position], feature))
                                )
                            )
                            if pd.notna(getattr(validate.iloc[position], feature))
                            else 1
                            for feature in features
                        )
                        actual = float(getattr(row, target))
                        prediction = float(predictions[position])
                        output.append(
                            {
                                "season": validation_season,
                                "week": int(row.week),
                                "game_id": int(row.game_id),
                                "kickoff_utc": str(row.kickoff_utc),
                                "candidate": candidate,
                                "recency_mode": recency_mode,
                                "target": target,
                                "actual": actual,
                                "prediction": prediction,
                                "absolute_error": abs(actual - prediction),
                                "fold_id": f"validate-{validation_season}",
                                "training_seasons": _json(completed_training_seasons),
                                "feature_names": _json(features),
                                "standardization_center": _json(metadata["center"]),
                                "standardization_scale": _json(metadata["scale"]),
                                "ridge_coefficients": _json(model.coef_.tolist()),
                                "ridge_intercept": float(model.intercept_),
                                "feature_fallback": fallback,
                                "fallback_count": fallback_count,
                                "fallback_uncertainty": max(
                                    metadata["fallback_uncertainty"].values()
                                )
                                if fallback
                                else 0.0,
                            }
                        )
    predictions = pd.DataFrame.from_records(output, columns=PHASE3_PREDICTION_COLUMNS)
    expected: set[tuple[int, int, str]] | None = None
    for recency_mode in RECENCY_MODES:
        for candidate in CORE_CANDIDATES:
            keys = set(
                predictions[
                    (predictions["recency_mode"] == recency_mode)
                    & (predictions["candidate"] == candidate)
                ][["season", "game_id", "target"]].itertuples(index=False, name=None)
            )
            if expected is None:
                expected = keys
            elif keys != expected:
                raise Phase3Error("candidate tournament silently changed population")
    return predictions.sort_values(
        ["recency_mode", "candidate", "season", "week", "game_id", "target"],
        kind="mergesort",
    ).reset_index(drop=True)


def hierarchical_bootstrap_interval(
    losses: pd.DataFrame,
    candidate: str,
    *,
    replicates: int,
    confidence: float,
    seed: int,
) -> tuple[float, float, float]:
    """Paired season→week hierarchical bootstrap of baseline minus candidate MAE."""
    if replicates <= 0 or not 0 < confidence < 1:
        raise Phase3Error("invalid Phase 3 bootstrap settings")
    selected = losses[losses["candidate"].isin(["epa_only", candidate])]
    paired = selected.pivot_table(
        index=["season", "week", "game_id", "target"],
        columns="candidate",
        values="absolute_error",
        aggfunc="first",
    )
    if paired[["epa_only", candidate]].isna().any().any():
        raise Phase3Error(f"bootstrap pairing failed for {candidate}")
    paired["improvement"] = paired["epa_only"] - paired[candidate]
    cells = (
        paired.reset_index()
        .groupby(["season", "week"], sort=True)["improvement"]
        .agg(["mean", "count"])
        .reset_index()
    )
    seasons = sorted(set(cells["season"].astype(int)))
    weeks = {
        season: cells[cells["season"] == season].reset_index(drop=True)
        for season in seasons
    }
    rng = np.random.default_rng(seed)
    draws = np.empty(replicates, dtype=float)
    for index in range(replicates):
        numerator = 0.0
        denominator = 0
        for season in rng.choice(seasons, size=len(seasons), replace=True):
            options = weeks[int(season)]
            positions = rng.integers(0, len(options), size=len(options))
            sampled = options.iloc[positions]
            numerator += float((sampled["mean"] * sampled["count"]).sum())
            denominator += int(sampled["count"].sum())
        draws[index] = numerator / denominator
    alpha = (1 - confidence) / 2
    return (
        float(paired["improvement"].mean()),
        float(np.quantile(draws, alpha)),
        float(np.quantile(draws, 1 - alpha)),
    )


def evaluate_tournament(
    predictions: pd.DataFrame,
    *,
    minimum_improvement_pct: float,
    maximum_seasonal_regression_pct: float,
    sensitivity_maximum_regression_pct: float,
    bootstrap_replicates: int,
    bootstrap_confidence: float,
    bootstrap_seed: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    primary = predictions[predictions["recency_mode"] == "primary"]
    sensitivity = predictions[predictions["recency_mode"] == "half_life_4_games"]
    baseline_mae = float(
        primary.loc[primary["candidate"] == "epa_only", "absolute_error"].mean()
    )
    sensitivity_baseline = float(
        sensitivity.loc[sensitivity["candidate"] == "epa_only", "absolute_error"].mean()
    )
    baseline_keys = set(
        primary.loc[
            primary["candidate"] == "epa_only", ["season", "game_id", "target"]
        ].itertuples(index=False, name=None)
    )
    summaries: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(CORE_CANDIDATES):
        candidate_primary = primary[primary["candidate"] == candidate]
        candidate_sensitivity = sensitivity[sensitivity["candidate"] == candidate]
        mae = float(candidate_primary["absolute_error"].mean())
        sensitivity_mae = float(candidate_sensitivity["absolute_error"].mean())
        improvement_pct = (baseline_mae - mae) / baseline_mae * 100
        sensitivity_regression = (
            (sensitivity_mae - sensitivity_baseline) / sensitivity_baseline * 100
        )
        keys = set(
            candidate_primary[["season", "game_id", "target"]].itertuples(
                index=False, name=None
            )
        )
        coverage_equal = keys == baseline_keys
        regressions: list[float] = []
        for (season, target), rows in candidate_primary.groupby(
            ["season", "target"], sort=True
        ):
            candidate_season_mae = float(rows["absolute_error"].mean())
            baseline_season_mae = float(
                primary[
                    (primary["candidate"] == "epa_only")
                    & (primary["season"] == season)
                    & (primary["target"] == target)
                ]["absolute_error"].mean()
            )
            regressions.append(
                (candidate_season_mae - baseline_season_mae) / baseline_season_mae * 100
            )
        maximum_regression = max(regressions)
        if candidate == "epa_only":
            bootstrap_mean, lower, upper = 0.0, 0.0, 0.0
            bootstrap_passed = False
        else:
            bootstrap_mean, lower, upper = hierarchical_bootstrap_interval(
                primary,
                candidate,
                replicates=bootstrap_replicates,
                confidence=bootstrap_confidence,
                seed=bootstrap_seed + candidate_index,
            )
            bootstrap_passed = lower > 0
        seasonal_passed = maximum_regression <= maximum_seasonal_regression_pct
        sensitivity_passed = (
            sensitivity_regression <= sensitivity_maximum_regression_pct
        )
        primary_passed = (
            candidate != "epa_only"
            and improvement_pct >= minimum_improvement_pct
            and bootstrap_passed
            and coverage_equal
            and seasonal_passed
            and sensitivity_passed
        )
        summaries.append(
            {
                "candidate": candidate,
                "components": _json(CANDIDATE_COMPONENTS[candidate]),
                "component_count": len(CANDIDATE_COMPONENTS[candidate]),
                "validation_rows": int(len(candidate_primary)),
                "validation_games": int(candidate_primary["game_id"].nunique()),
                "fallback_rows": int(candidate_primary["feature_fallback"].sum()),
                "pooled_mae": mae,
                "baseline_mae": baseline_mae,
                "improvement_pct": improvement_pct,
                "bootstrap_mean_improvement": bootstrap_mean,
                "bootstrap_90_lower": lower,
                "bootstrap_90_upper": upper,
                "bootstrap_excludes_zero": bootstrap_passed,
                "coverage_equal": coverage_equal,
                "maximum_seasonal_regression_pct": maximum_regression,
                "seasonal_gate_passed": seasonal_passed,
                "sensitivity_mae": sensitivity_mae,
                "sensitivity_baseline_mae": sensitivity_baseline,
                "sensitivity_regression_pct": sensitivity_regression,
                "sensitivity_gate_passed": sensitivity_passed,
                "primary_gate_passed": primary_passed,
                "selected": False,
            }
        )
    attribution = pd.DataFrame.from_records(
        summaries, columns=PHASE3_ATTRIBUTION_COLUMNS
    )
    passing = attribution[attribution["primary_gate_passed"]]
    if passing.empty:
        selected = "epa_only"
    else:
        best = float(passing["pooled_mae"].min())
        eligible = passing[passing["pooled_mae"] <= best * 1.005]
        selected = str(
            eligible.sort_values(
                ["component_count", "candidate"], kind="mergesort"
            ).iloc[0]["candidate"]
        )
    attribution.loc[attribution["candidate"] == selected, "selected"] = True
    manifest = signed_payload(
        {
            "schema_version": PHASE3_RETAINED_CORE_SCHEMA,
            "state": "frozen",
            "selected_candidate": selected,
            "selected_components": list(CANDIDATE_COMPONENTS[selected]),
            "baseline_candidate": "epa_only",
            "validation_seasons": list(VALIDATION_SEASONS),
            "candidate_summary_sha256": sha256(attribution.to_dict("records")),
            "auxiliary_context_consumed": False,
            "production_activation_authorized": False,
        }
    )
    return attribution, manifest


def certify_measurements(
    *,
    observations: pd.DataFrame,
    adjusted: pd.DataFrame,
    observation_audits: Mapping[int, Mapping[str, Any]],
    pass_rush_audits: Mapping[int, Mapping[str, Any]],
    definition_audits: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    numeric = observations.copy()
    numeric["numerator"] = _numeric(numeric, "numerator")
    numeric["denominator"] = _numeric(numeric, "denominator")
    numeric["raw_value"] = _numeric(numeric, "raw_value")
    observed = numeric[numeric["coverage_status"] == "observed"]
    raw_exact = bool(
        np.allclose(
            observed["raw_value"],
            observed["numerator"] / observed["denominator"],
            rtol=0,
            atol=1e-12,
        )
    )
    missing = numeric[numeric["coverage_status"] == "missing"]
    zero_exposure_explicit = bool(
        (missing["denominator"] == 0).all()
        and missing["raw_value"].isna().all()
        and missing["missing_reason"].notna().all()
    )
    dual = numeric[numeric["unit_role"].isin(["offense", "defense"])]
    symmetry = dual.groupby(
        ["season", "game_id", "measurement_id", "unit_role"], sort=False
    )[["numerator", "denominator"]].sum()
    offense = symmetry.xs("offense", level="unit_role")
    defense = symmetry.xs("defense", level="unit_role")
    shared = offense.index.intersection(defense.index)
    symmetric = bool(
        np.allclose(offense.loc[shared], defense.loc[shared], rtol=0, atol=1e-10)
    )
    iteration_set = set(adjusted["adjustment_iteration"].astype(int))
    iteration_contract = iteration_set == {0, 4}
    iteration_four = adjusted[adjusted["adjustment_iteration"] == 4].dropna(
        subset=["raw_value", "adjusted_value", "schedule_strength_component"]
    )
    adjustment_reconciles = bool(
        np.allclose(
            _numeric(iteration_four, "raw_value")
            - _numeric(iteration_four, "adjusted_value"),
            _numeric(iteration_four, "schedule_strength_component"),
            rtol=0,
            atol=1e-10,
        )
    )
    adjusted_evidence = iteration_four[
        iteration_four["measurement_id"].isin(ADJUSTED_COMPONENTS)
        & (_numeric(iteration_four, "primary_exposure") > 0)
    ]
    league_centered = bool(adjusted_evidence["league_center"].notna().all())
    pass_rush_explained = all(
        bool(audit.get("classified_or_explained"))
        for audit in pass_rush_audits.values()
    )
    definitions_exact = all(
        bool(audit.get("all_rows_exact")) for audit in definition_audits.values()
    )
    score_reconciliation = {
        str(season): audit.get("score_reconciliation", {})
        for season, audit in observation_audits.items()
    }
    ppso = numeric[numeric["measurement_id"] == "points_per_scoring_opportunity"]
    score_mismatch = (
        ppso["quality_flags"]
        .fillna("")
        .str.contains("score_stream_mismatch", regex=False)
    )
    score_streams_reconciled = bool(
        (
            (ppso.loc[score_mismatch, "coverage_status"] == "missing")
            & (ppso.loc[score_mismatch, "missing_reason"] == "score_stream_mismatch")
            & ppso.loc[score_mismatch, "raw_value"].isna()
        ).all()
    )
    checks = {
        "raw_ratio_exact": raw_exact,
        "zero_exposure_is_explicit": zero_exposure_explicit,
        "offense_defense_symmetry": symmetric,
        "retained_iterations_are_zero_and_four": iteration_contract,
        "adjustment_reconciles": adjustment_reconciles,
        "league_center_present_for_adjusted_evidence": league_centered,
        "pass_rush_rows_classified_or_explained": pass_rush_explained,
        "independent_definition_recomputation_exact": definitions_exact,
        "score_stream_mismatches_quarantined": score_streams_reconciled,
        "forbidden_2020_absent": not observations["season"]
        .isin(FORBIDDEN_SEASONS)
        .any(),
    }
    report = {
        "schema_version": "data_first_phase3_measurement_certification_v1",
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "observation_rows": int(len(observations)),
        "adjusted_rows": int(len(adjusted)),
        "score_reconciliation": score_reconciliation,
        "pass_rush_classification": {
            str(season): dict(audit) for season, audit in pass_rush_audits.items()
        },
        "independent_definition_recomputation": {
            str(season): dict(audit) for season, audit in definition_audits.items()
        },
    }
    report["report_sha256"] = sha256(report)
    return report
