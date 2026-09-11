"""Pregame replay construction for Phase 3 v2.

The arithmetic is intentionally small and deterministic: source observations are
admitted by the v2 cutoff before four-pass opponent adjustment, then the existing
sealed Phase 3 state/tournament primitives consume the resulting snapshot state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_phase3 import CANDIDATE_COMPONENTS
from cks_picks_cfb.data.data_first_phase3_v2 import (
    ADJUSTED_COMPONENTS,
    AVAILABILITY_BUFFER_HOURS,
    HISTORY_COLUMNS_V2,
    RECENCY_MODES,
    SNAPSHOT_COLUMNS_V2,
    TERMINAL_COLUMNS_V2,
    Phase3V2Error,
    weekly_cutoffs,
)
from cks_picks_cfb.ratings.phase3 import (
    _measurement_adjustments,
    _posterior,
    _recency_weight,
    _scales,
    build_component_states,
    run_candidate_tournament,
)

_HALF_LIFE = {"primary": None, "half_life_4_games": 4.0}
_AVAILABILITY_POLICY = "prior_week_and_source_kickoff_plus_6h"


def _finite(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


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
    admitted = (source["week"].astype(int) < week) & (
        source["kickoff_utc"] + pd.Timedelta(hours=AVAILABILITY_BUFFER_HOURS) <= cutoff
    )
    return source.loc[admitted].copy()


def _compact_game_features(
    *, states: pd.DataFrame, games: pd.DataFrame, candidate: str
) -> pd.DataFrame:
    """Build one candidate's game features without legacy Python aggregations."""
    components = CANDIDATE_COMPONENTS[candidate]
    selected = states[states["measurement_id"].isin(components)].copy()
    selected["uncertainty_squared"] = (
        pd.to_numeric(selected["state_uncertainty"], errors="coerce") ** 2
    )
    keys = ["season", "week", "game_id", "kickoff_utc", "team", "unit_role"]
    composites = (
        selected.groupby(keys, sort=False)
        .agg(
            component_rows=("measurement_id", "nunique"),
            available_rows=("evidence_available", "sum"),
            state_value=("state_value", "mean"),
            uncertainty_squared=("uncertainty_squared", "sum"),
        )
        .reset_index()
    )
    complete = (composites["component_rows"] == len(components)) & (
        composites["available_rows"] == len(components)
    )
    composites["state_uncertainty"] = np.sqrt(composites["uncertainty_squared"]) / len(
        components
    )
    composites.loc[~complete, ["state_value", "state_uncertainty"]] = np.nan

    team_sides = states[["season", "week", "game_id", "kickoff_utc", "team"]]
    game_count = states[["season", "game_id"]].drop_duplicates().shape[0]
    if team_sides.drop_duplicates().shape[0] < game_count * 2:
        raise Phase3V2Error(f"candidate {candidate} lacks two teams per game")

    schedule = games[
        ["season", "week", "game_id", "kickoff_utc", "home_team", "away_team"]
    ].drop_duplicates(["season", "game_id"])
    result = schedule.copy()
    for side in ("home", "away"):
        for role in ("offense", "defense"):
            values = composites[composites["unit_role"] == role][
                ["season", "game_id", "team", "state_value", "state_uncertainty"]
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


@dataclass(frozen=True)
class ReplayPartition:
    """Bounded Phase 3 replay output for one weekly cutoff or terminal season."""

    season: int
    week: int | None
    snapshots: pd.DataFrame
    history: pd.DataFrame
    terminal: pd.DataFrame


@dataclass
class CompactTournamentFeatureBuilder:
    """Incrementally convert snapshot partitions into tournament game features.

    Raw iteration-four component rows are deliberately transient.  Only compact
    game/candidate/recency feature rows survive across weekly partitions.
    """

    terminal_history: dict[str, pd.DataFrame] = field(default_factory=dict)
    terminal_states: dict[
        str, dict[int, dict[tuple[str, str, str], tuple[float, float]]]
    ] = field(default_factory=dict)
    feature_frames: list[pd.DataFrame] = field(default_factory=list)
    raw_component_rows: int = 0
    max_component_partition_rows: int = 0
    max_feature_partition_rows: int = 0
    seen_seasons: set[int] = field(default_factory=set)
    closed_seasons: set[int] = field(default_factory=set)
    last_week_by_season: dict[int, int] = field(default_factory=dict)

    def _history(self, mode: str, columns: pd.Index) -> pd.DataFrame:
        if mode not in self.terminal_history:
            self.terminal_history[mode] = pd.DataFrame(columns=columns)
        return self.terminal_history[mode]

    @staticmethod
    def _prior(
        season: int,
        states: dict[int, dict[tuple[str, str, str], tuple[float, float]]],
    ) -> tuple[int | None, int, dict[tuple[str, str, str], tuple[float, float]]]:
        previous = [value for value in DEVELOPMENT_SEASONS if value < season]
        source_season = previous[-1] if previous else None
        return (
            source_season,
            season - source_season if source_season is not None else 0,
            states.get(source_season, {}) if source_season is not None else {},
        )

    @staticmethod
    def _state_rows(
        current: pd.DataFrame,
        *,
        scales: dict[tuple[str, str], tuple[float, float]],
        priors: dict[tuple[str, str, str], tuple[float, float]],
        source_season: int | None,
        decay_steps: int,
        mode: str,
    ) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for row in current.itertuples(index=False):
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
                {
                    "epa_per_play": 100.0,
                    "epa_pass": 100.0,
                    "epa_rush": 100.0,
                    "success_rate": 100.0,
                    "explosive_rate_20": 100.0,
                    "points_per_scoring_opportunity": 8.0,
                }[str(row.measurement_id)],
            )
            available = observed_z is not None or prior is not None
            rows.append(
                {
                    "season": int(row.season),
                    "week": int(row.week),
                    "game_id": int(row.as_of_game_id),
                    "kickoff_utc": row.as_of_kickoff_utc,
                    "team": str(row.team),
                    "measurement_id": str(row.measurement_id),
                    "unit_role": str(row.unit_role),
                    "recency_mode": mode,
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
        return pd.DataFrame.from_records(rows)

    def add_week(self, *, snapshots: pd.DataFrame, games: pd.DataFrame) -> None:
        if snapshots.empty:
            raise Phase3V2Error("compact feature builder received an empty week")
        season_values = set(snapshots["season"].astype(int))
        if len(season_values) != 1:
            raise Phase3V2Error("compact feature builder week spans seasons")
        season = next(iter(season_values))
        if season in self.closed_seasons:
            raise Phase3V2Error("compact feature builder received a closed season")
        if self.seen_seasons and season < max(self.seen_seasons):
            raise Phase3V2Error("compact feature builder received out-of-order season")
        week_values = set(snapshots["week"].astype(int))
        if len(week_values) != 1:
            raise Phase3V2Error("compact feature builder week spans canonical weeks")
        week = next(iter(week_values))
        if week <= self.last_week_by_season.get(season, -1):
            raise Phase3V2Error("compact feature builder received out-of-order week")
        self.seen_seasons.add(season)
        self.last_week_by_season[season] = week
        for mode in RECENCY_MODES:
            current = snapshots[
                (snapshots["recency_mode"] == mode)
                & (snapshots["adjustment_iteration"].astype(int) == 4)
                & snapshots["measurement_id"].isin(ADJUSTED_COMPONENTS)
            ].copy()
            if current.empty:
                raise Phase3V2Error("compact feature builder lacks adjusted components")
            self.raw_component_rows += len(current)
            self.max_component_partition_rows = max(
                self.max_component_partition_rows, len(current)
            )
            history = self._history(mode, snapshots.columns)
            scales = _scales(history, season)
            states = self.terminal_states.setdefault(mode, {})
            source_season, decay_steps, priors = self._prior(season, states)
            component_states = self._state_rows(
                current,
                scales=scales,
                priors=priors,
                source_season=source_season,
                decay_steps=decay_steps,
                mode=mode,
            )
            if len(component_states) != len(current):
                raise Phase3V2Error("compact component state row loss")
            self.max_component_partition_rows = max(
                self.max_component_partition_rows, len(component_states)
            )
            for candidate in CANDIDATE_COMPONENTS:
                features = _compact_game_features(
                    states=component_states, games=games, candidate=candidate
                )
                features["recency_mode"] = mode
                self.max_feature_partition_rows = max(
                    self.max_feature_partition_rows, len(features)
                )
                self.feature_frames.append(features)

    def add_terminal(self, terminal: pd.DataFrame) -> None:
        if terminal.empty:
            raise Phase3V2Error("compact feature builder lacks terminal state")
        season_values = set(terminal["season"].astype(int))
        if len(season_values) != 1:
            raise Phase3V2Error("compact terminal spans seasons")
        season = next(iter(season_values))
        if season in self.closed_seasons:
            raise Phase3V2Error("compact terminal repeated a season")
        for mode in RECENCY_MODES:
            current = terminal[
                (terminal["recency_mode"] == mode)
                & terminal["measurement_id"].isin(ADJUSTED_COMPONENTS)
            ].copy()
            history = self._history(mode, terminal.columns)
            scales = _scales(history, season)
            states = self.terminal_states.setdefault(mode, {})
            source_season, decay_steps, priors = self._prior(season, states)
            next_states: dict[tuple[str, str, str], tuple[float, float]] = {}
            for row in current.itertuples(index=False):
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
                    {
                        "epa_per_play": 100.0,
                        "epa_pass": 100.0,
                        "epa_rush": 100.0,
                        "success_rate": 100.0,
                        "explosive_rate_20": 100.0,
                        "points_per_scoring_opportunity": 8.0,
                    }[str(row.measurement_id)],
                )
            states[season] = next_states
            self.terminal_history[mode] = (
                current.reset_index(drop=True)
                if history.empty
                else pd.concat([history, current], ignore_index=True)
            )
        self.closed_seasons.add(season)

    def finish(self) -> pd.DataFrame:
        if not self.feature_frames:
            raise Phase3V2Error("compact feature builder emitted no features")
        if self.seen_seasons != self.closed_seasons:
            raise Phase3V2Error("compact feature builder lacks terminal transition")
        features = pd.concat(self.feature_frames, ignore_index=True)
        key = ["season", "game_id", "candidate", "recency_mode"]
        if features.duplicated(key).any():
            raise Phase3V2Error("compact feature builder emitted duplicate keys")
        return features.sort_values(key, kind="mergesort").reset_index(drop=True)


def _replay_week(
    *,
    schedule: pd.DataFrame,
    observations: pd.DataFrame,
    season: int,
    week: int,
    cutoff: pd.Timestamp,
    measurement_ids: list[str],
    roles: dict[str, list[str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build one bounded target-week partition for both recency modes."""
    games = schedule[
        (schedule["season"].astype(int) == season)
        & (schedule["week"].astype(int) == week)
    ]
    snapshot_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    for recency_mode in RECENCY_MODES:
        half_life = _HALF_LIFE[recency_mode]
        history = _history_for_cutoff(
            observations=observations, season=season, week=week, cutoff=cutoff
        )
        effective = _recency_weight(history, half_life) if half_life else history
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
                            snapshot_rows.append(
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
            raw_value = _finite(source.raw_value)
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
                    "raw_value": raw_value,
                    "numerator": float(source.numerator),
                    "denominator": float(source.denominator),
                    "iteration_three_opponent_value": opponent_value,
                    "schedule_strength_component": correction,
                    "iteration_zero_value": raw_value,
                    "iteration_four_value": (
                        _finite(raw_value - correction)
                        if raw_value is not None
                        else None
                    ),
                    "included": True,
                    "missing_reason": None,
                    "timing_class": "historically_reconstructed",
                }
            )
    snapshot = pd.DataFrame.from_records(snapshot_rows, columns=SNAPSHOT_COLUMNS_V2)
    history = pd.DataFrame.from_records(history_rows, columns=HISTORY_COLUMNS_V2)
    return (
        snapshot.sort_values(
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
        ).reset_index(drop=True),
        history.sort_values(
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
        ).reset_index(drop=True),
    )


def _terminal_for_season(
    *,
    observations: pd.DataFrame,
    universe: pd.DataFrame,
    season: int,
    measurement_ids: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    season_observations = observations[
        (observations["season"].astype(int) == season)
        & (observations["coverage_status"] == "observed")
        & (observations["denominator"].astype(float) > 0)
    ].copy()
    for recency_mode in RECENCY_MODES:
        half_life = _HALF_LIFE[recency_mode]
        effective = (
            _recency_weight(season_observations, half_life)
            if half_life
            else season_observations
        )
        for measurement in measurement_ids:
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
                    rows.append(
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
    return (
        pd.DataFrame.from_records(rows, columns=TERMINAL_COLUMNS_V2)
        .sort_values(
            ["season", "team", "measurement_id", "unit_role", "recency_mode"],
            kind="mergesort",
        )
        .reset_index(drop=True)
    )


def iter_replayable_measurements(
    *, population: pd.DataFrame, observations: pd.DataFrame
) -> Iterator[ReplayPartition]:
    """Yield one target-week partition at a time; never retain full history."""
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
    empty_snapshot = pd.DataFrame(columns=SNAPSHOT_COLUMNS_V2)
    empty_history = pd.DataFrame(columns=HISTORY_COLUMNS_V2)
    empty_terminal = pd.DataFrame(columns=TERMINAL_COLUMNS_V2)
    for season in sorted(schedule["season"].astype(int).unique().tolist()):
        season_cutoffs = cutoffs[cutoffs["season"].astype(int) == season]
        for cutoff_row in season_cutoffs.itertuples(index=False):
            week = int(cutoff_row.week)
            snapshots, history = _replay_week(
                schedule=schedule,
                observations=observations,
                season=season,
                week=week,
                cutoff=cutoff_row.target_week_cutoff_utc,
                measurement_ids=measurement_ids,
                roles=roles,
            )
            yield ReplayPartition(season, week, snapshots, history, empty_terminal)
        yield ReplayPartition(
            season,
            None,
            empty_snapshot,
            empty_history,
            _terminal_for_season(
                observations=observations,
                universe=universe,
                season=season,
                measurement_ids=measurement_ids,
            ),
        )


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
