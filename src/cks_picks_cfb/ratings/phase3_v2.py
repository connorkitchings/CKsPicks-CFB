"""Pregame replay construction for Phase 3 v2.

The arithmetic is intentionally small and deterministic: source observations are
admitted by the v2 cutoff before four-pass opponent adjustment, then the existing
sealed Phase 3 state/tournament primitives consume the resulting snapshot state.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_phase3_v2 import (
    ADJUSTED_COMPONENTS,
    HISTORY_COLUMNS_V2,
    RECENCY_MODES,
    SNAPSHOT_COLUMNS_V2,
    TERMINAL_COLUMNS_V2,
    Phase3V2Error,
    source_is_available,
    weekly_cutoffs,
)
from cks_picks_cfb.ratings.phase3 import (
    _measurement_adjustments,
    _recency_weight,
    build_component_states,
    run_candidate_tournament,
)

_HALF_LIFE = {"primary": None, "half_life_4_games": 4.0}
_AVAILABILITY_POLICY = "prior_week_and_source_kickoff_plus_6h"


def _finite(value: Any) -> float | None:
    value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(value) or not np.isfinite(value) else float(value)


def _weighted_sums(
    history: pd.DataFrame,
) -> dict[tuple[str, str, str], tuple[float, float]]:
    grouped = history.groupby(["measurement_id", "unit_role", "team"], sort=False).agg(
        numerator=("numerator", "sum"), denominator=("denominator", "sum")
    )
    return {
        (str(measurement), str(role), str(team)): (
            float(row.numerator),
            float(row.denominator),
        )
        for (measurement, role, team), row in grouped.iterrows()
    }


def _adjustment_trace(
    rows: pd.DataFrame,
) -> tuple[
    dict[str, dict[str, float]],
    dict[str, dict[str, float]],
    dict[str, float],
]:
    """Return final values plus the exact opponent state used in pass four."""
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
            )
            .reset_index()
        )
        evidence[role] = grouped
        raw[role] = {
            str(row.team): float(row.numerator / row.denominator)
            for row in grouped.itertuples(index=False)
            if float(row.denominator) > 0
        }
        adjusted[role] = dict(raw[role])
        edges[role] = role_rows[
            ["game_id", "team", "opponent", "denominator"]
        ].drop_duplicates()

    iteration_three: dict[str, dict[str, float]] = {
        "offense": {},
        "defense": {},
    }
    final_centers = {"offense": float("nan"), "defense": float("nan")}
    for iteration in range(1, 5):
        centers = {}
        for role in ("offense", "defense"):
            values = evidence[role].copy()
            values["value"] = values["team"].astype(str).map(adjusted[role])
            values = values.dropna(subset=["value"])
            centers[role] = (
                float(np.average(values["value"], weights=values["denominator"]))
                if len(values) and float(values["denominator"].sum()) > 0
                else float("nan")
            )
        if iteration == 4:
            iteration_three = {role: dict(values) for role, values in adjusted.items()}
            final_centers = centers
        updated: dict[str, dict[str, float]] = {}
        for role, opponent_role in (("offense", "defense"), ("defense", "offense")):
            next_values = dict(raw[role])
            if not edges[role].empty and np.isfinite(centers[opponent_role]):
                opponent_values = pd.Series(
                    adjusted[opponent_role], name="opponent_value", dtype=float
                )
                joined = (
                    edges[role]
                    .merge(
                        opponent_values,
                        left_on="opponent",
                        right_index=True,
                        how="left",
                    )
                    .dropna(subset=["opponent_value"])
                )
                if not joined.empty:
                    joined["delta"] = (
                        joined["opponent_value"] - centers[opponent_role]
                    ) * joined["denominator"]
                    totals = joined.groupby("team", sort=False).agg(
                        delta=("delta", "sum"),
                        denominator=("denominator", "sum"),
                    )
                    for team, value in raw[role].items():
                        if team in totals.index and totals.loc[team, "denominator"] > 0:
                            next_values[team] = value - float(
                                totals.loc[team, "delta"]
                                / totals.loc[team, "denominator"]
                            )
            updated[role] = next_values
        adjusted = updated
    return adjusted, iteration_three, final_centers


def _history_for_cutoff(
    *, observations: pd.DataFrame, season: int, week: int, cutoff: pd.Timestamp
) -> pd.DataFrame:
    source = observations[
        (observations["season"].astype(int) == season)
        & (observations["coverage_status"] == "observed")
        & (observations["denominator"].astype(float) > 0)
    ].copy()
    source["kickoff_utc"] = pd.to_datetime(source["kickoff_utc"], utc=True)
    admitted = source.apply(
        lambda row: source_is_available(
            source_week=int(row.week),
            source_kickoff_utc=row.kickoff_utc,
            target_week=week,
            target_week_cutoff_utc=cutoff,
        ),
        axis=1,
    )
    return source.loc[admitted].copy()


def build_replayable_measurements(
    *, population: pd.DataFrame, observations: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build cutoff-specific snapshots, source history, and terminal state.

    Four adjustment passes are executed for every target cutoff. History stores
    the exact iteration-three opponent state and pass-four source correction,
    so exposure-weighting the source rows reconstitutes the iteration-four state.
    """
    required = {
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "home_team",
        "away_team",
        "forecast_eligible",
    }
    if missing := sorted(required - set(population)):
        raise Phase3V2Error(f"Population cannot build replay state: {missing}")
    if observations["season"].astype(int).isin((2020,)).any():
        raise Phase3V2Error("Replay observations contain forbidden 2020")
    cutoffs = weekly_cutoffs(population)
    schedule = population[population["forecast_eligible"]].copy()
    schedule["kickoff_utc"] = pd.to_datetime(schedule["kickoff_utc"], utc=True)
    snapshots: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    terminal_rows: list[dict[str, Any]] = []

    universe = (
        pd.concat(
            [
                schedule[["season", "home_team"]].rename(columns={"home_team": "team"}),
                schedule[["season", "away_team"]].rename(columns={"away_team": "team"}),
            ],
            ignore_index=True,
        )
        .drop_duplicates()
        .sort_values(["season", "team"], kind="mergesort")
    )

    for recency_mode in RECENCY_MODES:
        half_life = _HALF_LIFE[recency_mode]
        for cutoff_row in cutoffs.itertuples(index=False):
            season, week, cutoff = (
                int(cutoff_row.season),
                int(cutoff_row.week),
                cutoff_row.target_week_cutoff_utc,
            )
            history = _history_for_cutoff(
                observations=observations, season=season, week=week, cutoff=cutoff
            )
            effective = _recency_weight(history, half_life) if half_life else history
            measurement_ids = sorted(set(observations["measurement_id"].astype(str)))
            roles = {
                measurement: sorted(
                    set(
                        observations.loc[
                            observations["measurement_id"].astype(str) == measurement,
                            "unit_role",
                        ].astype(str)
                    )
                )
                for measurement in measurement_ids
            }
            cache = {
                measurement: _measurement_adjustments(
                    effective[effective["measurement_id"].astype(str) == measurement],
                    measurement,
                    4,
                )
                for measurement in measurement_ids
            }
            traces = {
                measurement: _adjustment_trace(
                    effective[effective["measurement_id"].astype(str) == measurement]
                )
                for measurement in ADJUSTED_COMPONENTS
            }
            sums = _weighted_sums(effective)
            games = schedule[
                (schedule["season"].astype(int) == season)
                & (schedule["week"].astype(int) == week)
            ]
            for game in games.itertuples(index=False):
                for team in (str(game.home_team), str(game.away_team)):
                    for measurement in measurement_ids:
                        for role in roles[measurement]:
                            value = cache[measurement].get(role, {}).get(team)
                            numerator, denominator = sums.get(
                                (measurement, role, team), (0.0, 0.0)
                            )
                            raw = _finite(value["raw"]) if value else None
                            adjusted = _finite(value["adjusted"]) if value else None
                            for iteration, adjusted_value in ((0, raw), (4, adjusted)):
                                snapshots.append(
                                    {
                                        "season": season,
                                        "week": week,
                                        "as_of_game_id": int(game.game_id),
                                        "as_of_kickoff_utc": game.kickoff_utc,
                                        "target_week_cutoff_utc": cutoff,
                                        "team": team,
                                        "measurement_id": measurement,
                                        "unit_role": role,
                                        "recency_mode": recency_mode,
                                        "adjustment_iteration": iteration,
                                        "raw_value": raw,
                                        "adjusted_value": adjusted_value,
                                        "primary_exposure": float(value["exposure"])
                                        if value
                                        else 0.0,
                                        "games_exposure": int(value["games"])
                                        if value
                                        else 0,
                                        "source_game_count": int(
                                            history["game_id"].nunique()
                                        ),
                                        "timing_class": "historically_reconstructed",
                                        "availability_policy": _AVAILABILITY_POLICY,
                                    }
                                )
            for source in effective[
                effective["measurement_id"].isin(ADJUSTED_COMPONENTS)
            ].itertuples(index=False):
                _, iteration_three, centers = traces[str(source.measurement_id)]
                opponent_role = (
                    "defense" if str(source.unit_role) == "offense" else "offense"
                )
                opponent_value = _finite(
                    iteration_three[opponent_role].get(str(source.opponent))
                )
                center = _finite(centers[opponent_role])
                correction = (
                    opponent_value - center
                    if opponent_value is not None and center is not None
                    else 0.0
                )
                history_rows.append(
                    {
                        "season": season,
                        "week": week,
                        "as_of_game_id": int(games["game_id"].min()),
                        "as_of_kickoff_utc": cutoff,
                        "target_week_cutoff_utc": cutoff,
                        "source_season": int(source.season),
                        "source_week": int(source.week),
                        "source_game_id": int(source.game_id),
                        "source_kickoff_utc": source.kickoff_utc,
                        "source_available_utc": pd.Timestamp(source.kickoff_utc)
                        + pd.Timedelta(hours=6),
                        "team": str(source.team),
                        "opponent": str(source.opponent),
                        "measurement_id": str(source.measurement_id),
                        "unit_role": str(source.unit_role),
                        "recency_mode": recency_mode,
                        "raw_value": _finite(source.raw_value),
                        "numerator": float(source.numerator),
                        "denominator": float(source.denominator),
                        "iteration_three_opponent_value": opponent_value,
                        "schedule_strength_component": correction,
                        "iteration_zero_value": _finite(source.raw_value),
                        "iteration_four_value": (
                            _finite(source.raw_value - correction)
                            if _finite(source.raw_value) is not None
                            else None
                        ),
                        "included": True,
                        "missing_reason": None,
                        "timing_class": "historically_reconstructed",
                    }
                )

        for season in DEVELOPMENT_SEASONS:
            season_observations = observations[
                (observations["season"].astype(int) == season)
                & (observations["coverage_status"] == "observed")
                & (observations["denominator"].astype(float) > 0)
            ].copy()
            effective = (
                _recency_weight(season_observations, half_life)
                if half_life
                else season_observations
            )
            for measurement in sorted(set(observations["measurement_id"].astype(str))):
                cache = _measurement_adjustments(
                    effective[effective["measurement_id"].astype(str) == measurement],
                    measurement,
                    4,
                )
                for role, values in cache.items():
                    for row in universe[
                        universe["season"].astype(int) == season
                    ].itertuples(index=False):
                        value = values.get(str(row.team))
                        terminal_rows.append(
                            {
                                "season": season,
                                "team": str(row.team),
                                "measurement_id": measurement,
                                "unit_role": role,
                                "recency_mode": recency_mode,
                                "raw_value": _finite(value["raw"]) if value else None,
                                "adjusted_value": _finite(value["adjusted"])
                                if value
                                else None,
                                "primary_exposure": float(value["exposure"])
                                if value
                                else 0.0,
                                "games_exposure": int(value["games"]) if value else 0,
                                "source_game_count": int(
                                    season_observations["game_id"].nunique()
                                ),
                                "timing_class": "historically_reconstructed",
                            }
                        )

    snapshot = pd.DataFrame.from_records(snapshots, columns=SNAPSHOT_COLUMNS_V2)
    history = pd.DataFrame.from_records(history_rows, columns=HISTORY_COLUMNS_V2)
    terminal = pd.DataFrame.from_records(terminal_rows, columns=TERMINAL_COLUMNS_V2)
    snapshot = snapshot.sort_values(
        [
            "season",
            "week",
            "as_of_game_id",
            "team",
            "measurement_id",
            "unit_role",
            "recency_mode",
            "adjustment_iteration",
        ],
        kind="mergesort",
    ).reset_index(drop=True)
    history = history.sort_values(
        [
            "season",
            "week",
            "as_of_game_id",
            "source_game_id",
            "team",
            "measurement_id",
            "unit_role",
            "recency_mode",
        ],
        kind="mergesort",
    ).reset_index(drop=True)
    terminal = terminal.sort_values(
        ["season", "team", "measurement_id", "unit_role", "recency_mode"],
        kind="mergesort",
    ).reset_index(drop=True)
    return snapshot, history, terminal


def _v1_adjusted(snapshot: pd.DataFrame) -> pd.DataFrame:
    """Translate v2 snapshots into the stable v1 state-builder input shape."""
    rows = snapshot.copy()
    rows["numerator"] = rows["raw_value"].fillna(0.0) * rows["primary_exposure"]
    rows["denominator"] = rows["primary_exposure"]
    rows["league_center"] = None
    rows["schedule_strength_component"] = rows["raw_value"] - rows["adjusted_value"]
    rows["coverage_status"] = np.where(
        rows["adjusted_value"].notna(), "observed", "missing"
    )
    rows["missing_reason"] = np.where(
        rows["adjusted_value"].notna(), None, "no_prior_week_evidence"
    )
    rows["parent_identity_sha"] = "phase3-v2"
    rows["code_sha"] = "phase3-v2"
    rows["config_sha"] = "phase3-v2"
    return rows.rename(columns={"as_of_game_id": "as_of_game_id"})[
        [
            "season",
            "week",
            "as_of_game_id",
            "as_of_kickoff_utc",
            "team",
            "measurement_id",
            "unit_role",
            "recency_mode",
            "adjustment_iteration",
            "numerator",
            "denominator",
            "primary_exposure",
            "games_exposure",
            "raw_value",
            "adjusted_value",
            "league_center",
            "schedule_strength_component",
            "coverage_status",
            "missing_reason",
            "parent_identity_sha",
            "code_sha",
            "config_sha",
        ]
    ]


def _v1_terminal(terminal: pd.DataFrame) -> pd.DataFrame:
    return terminal[
        [
            "season",
            "team",
            "measurement_id",
            "unit_role",
            "recency_mode",
            "adjusted_value",
            "primary_exposure",
            "games_exposure",
        ]
    ].copy()


def run_repaired_tournament(
    *, population: pd.DataFrame, snapshots: pd.DataFrame, terminal: pd.DataFrame
) -> pd.DataFrame:
    """Run the sealed Ridge tournament while retaining every eligible game."""
    adjusted = _v1_adjusted(snapshots)
    states = {
        mode: build_component_states(
            adjusted=adjusted, terminal=_v1_terminal(terminal), recency_mode=mode
        )
        for mode in RECENCY_MODES
    }
    games = population[population["forecast_eligible"]].copy()
    outcomes = games[["season", "game_id", "home_points", "away_points"]].copy()
    outcomes = outcomes.rename(
        columns={"home_points": "home_score", "away_points": "away_score"}
    )
    predictions = run_candidate_tournament(
        primary_states=states["primary"],
        sensitivity_states=states["half_life_4_games"],
        games=games,
        outcomes=outcomes,
        ridge_alpha=10.0,
    )
    return (
        predictions.rename(columns={"feature_fallback": "feature_fallback"})[
            [
                "season",
                "week",
                "game_id",
                "kickoff_utc",
                "candidate",
                "recency_mode",
                "target",
                "actual",
                "prediction",
                "absolute_error",
                "fold_id",
                "training_seasons",
                "feature_fallback",
                "fallback_count",
            ]
        ]
        .sort_values(
            ["recency_mode", "candidate", "season", "week", "game_id", "target"],
            kind="mergesort",
        )
        .reset_index(drop=True)
    )
