"""Pure, single-candidate replay for the live V5 possession rating state.

The historical rating materializer deliberately runs a 60-candidate tournament.
This module is the isolated Contract 08 path: it reconstructs only the frozen
``ppp__rho_0_60__exposure`` design from a historical terminal measurement and
2026 certified measurements.  It owns no storage I/O and never selects,
fits, or calibrates anything on live outcomes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    PRIOR_COLUMNS,
    RATING_STATE_COLUMNS,
    TEAM_STATE_COLUMNS,
)
from cks_picks_cfb.data.data_first_possession_v1 import ROLES
from cks_picks_cfb.ratings.possession_ratings import RatingPrior, carryover_prior

LIVE_SEASON = 2026
FROZEN_CANDIDATE = "ppp__rho_0_60__exposure"
FROZEN_DEFINITION = "ppp"
FROZEN_UPDATER = "exposure"
_K = 8.0
_AVAILABILITY_HOURS = 6


class LiveReplayError(ValueError):
    """Raised when a live replay input violates its fixed contract."""


@dataclass(frozen=True)
class LiveReplayInputs:
    """Verified, in-memory facts needed to reconstruct a 2026 state replay."""

    population: pd.DataFrame
    observations: pd.DataFrame
    snapshots: pd.DataFrame
    historical_terminal: pd.DataFrame


@dataclass(frozen=True)
class LiveReplayComputation:
    """Canonical replay frames and diagnostics, before immutable publication."""

    priors: pd.DataFrame
    rating_states: pd.DataFrame
    team_states: pd.DataFrame
    diagnostics: dict[str, Any]


def _historical_scale(
    terminal: pd.DataFrame, *, role: str
) -> tuple[float, float, float]:
    rows = terminal[
        terminal["season"].eq(2025)
        & terminal["measurement_id"].eq(FROZEN_DEFINITION)
        & terminal["unit_role"].eq(role)
    ].copy()
    values = pd.to_numeric(rows["adjusted_value"], errors="coerce").dropna()
    floor = 0.30
    if values.empty:
        return 0.0, 1.0, -1.0 if role == "defense" else 1.0
    scale = max(float(values.std(ddof=0)), floor)
    if not np.isfinite(scale) or scale <= 0:
        scale = 1.0
    return float(values.mean()), scale, -1.0 if role == "defense" else 1.0


def _live_games(population: pd.DataFrame) -> pd.DataFrame:
    required = {
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "home_team",
        "away_team",
        "forecast_eligible",
        "schedule_completed",
        "outcome_valid",
        "timing_class",
    }
    if missing := sorted(required - set(population)):
        raise LiveReplayError(f"live population lacks columns: {missing}")
    games = population[
        pd.to_numeric(population["season"], errors="coerce").eq(LIVE_SEASON)
    ].copy()
    if games.empty:
        raise LiveReplayError("live measurement parent has no 2026 population")
    if not games["timing_class"].eq("live").all():
        raise LiveReplayError("live population has a non-live timing class")
    eligible = games[games["forecast_eligible"].eq(True)].copy()
    if eligible.empty:
        raise LiveReplayError("live measurement parent has no forecast-eligible games")
    if not (
        eligible["schedule_completed"].eq(True) & eligible["outcome_valid"].eq(True)
    ).all():
        raise LiveReplayError("live replay cannot advance an incomplete eligible game")
    eligible["week"] = pd.to_numeric(eligible["week"], errors="raise").astype(int)
    eligible["game_id"] = pd.to_numeric(eligible["game_id"], errors="raise").astype(int)
    eligible["kickoff_utc"] = pd.to_datetime(eligible["kickoff_utc"], utc=True)
    if eligible.duplicated("game_id").any():
        raise LiveReplayError("live population duplicates a game")
    weeks = sorted(eligible["week"].unique().tolist())
    if weeks != list(range(weeks[-1] + 1)):
        raise LiveReplayError("live replay weeks must be continuous from Week 0")
    return eligible.sort_values(
        ["kickoff_utc", "game_id"], kind="mergesort"
    ).reset_index(drop=True)


def _boundaries(games: pd.DataFrame) -> pd.DataFrame:
    """First certified later-week inclusion for each team's source game."""
    records: list[dict[str, Any]] = []
    teams = sorted(
        set(games["home_team"].astype(str)) | set(games["away_team"].astype(str))
    )
    for team in teams:
        schedule = games[
            games["home_team"].eq(team) | games["away_team"].eq(team)
        ].sort_values(["kickoff_utc", "game_id"], kind="mergesort")
        for game in schedule.itertuples(index=False):
            ready_at = pd.Timestamp(game.kickoff_utc) + pd.Timedelta(
                hours=_AVAILABILITY_HOURS
            )
            allowed = schedule[
                schedule["week"].gt(int(game.week))
                & schedule["kickoff_utc"].ge(ready_at)
            ]
            if not allowed.empty:
                target = allowed.iloc[0]
                records.append(
                    {
                        "game_id": int(game.game_id),
                        "team": team,
                        "boundary_game_id": int(target.game_id),
                        "boundary_cutoff_utc": pd.Timestamp(target.kickoff_utc),
                    }
                )
    return pd.DataFrame.from_records(records)


def _priors(
    games: pd.DataFrame, terminal: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, tuple[float, float, float]]]:
    required = {
        "season",
        "team",
        "measurement_id",
        "unit_role",
        "adjusted_value",
        "primary_exposure",
    }
    if missing := sorted(required - set(terminal)):
        raise LiveReplayError(f"historical terminal lacks columns: {missing}")
    teams = sorted(
        set(games["home_team"].astype(str)) | set(games["away_team"].astype(str))
    )
    scale = {role: _historical_scale(terminal, role=role) for role in ROLES}
    rows: list[dict[str, Any]] = []
    prior_lookup: dict[str, tuple[float, float, float]] = {}
    for role in ROLES:
        center, spread, sign = scale[role]
        previous = terminal[
            terminal["season"].eq(2025)
            & terminal["measurement_id"].eq(FROZEN_DEFINITION)
            & terminal["unit_role"].eq(role)
        ].copy()
        previous["team"] = previous["team"].astype(str)
        previous = previous.drop_duplicates("team", keep=False).set_index("team")
        for team in teams:
            if team in previous.index:
                value = float(previous.loc[team, "adjusted_value"])
                exposure = float(previous.loc[team, "primary_exposure"])
                if not np.isfinite(value) or not np.isfinite(exposure) or exposure <= 0:
                    carry = RatingPrior(
                        0.0, 1.0, "neutral", None, "invalid_predecessor"
                    )
                else:
                    terminal_z = sign * (value - center) / spread
                    carry = carryover_prior(
                        RatingPrior(
                            terminal_z,
                            1.0 / (1.0 + exposure / _K),
                            "terminal",
                            2025,
                        ),
                        gap=1,
                    )
            else:
                carry = RatingPrior(0.0, 1.0, "neutral", None, "no_predecessor")
            rows.append(
                {
                    "candidate_id": FROZEN_CANDIDATE,
                    "season": LIVE_SEASON,
                    "team": team,
                    "unit_role": role,
                    "prior_mean": float(carry.mean),
                    "prior_variance": float(carry.variance),
                    "prior_source": carry.source,
                    "prior_source_season": carry.source_season,
                    "annual_decay_steps": 1 if carry.source_season else 0,
                    "fallback_reason": carry.fallback_reason,
                }
            )
            prior_lookup[f"{role}\u0000{team}"] = (
                float(carry.mean),
                float(carry.variance),
                sign,
            )
    frame = (
        pd.DataFrame.from_records(rows, columns=list(PRIOR_COLUMNS))
        .sort_values(["unit_role", "team"], kind="mergesort")
        .reset_index(drop=True)
    )
    return frame, prior_lookup


def _streams(
    *,
    observations: pd.DataFrame,
    snapshots: pd.DataFrame,
    boundaries: pd.DataFrame,
    scale: Mapping[str, tuple[float, float, float]],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    required_observations = {
        "season",
        "game_id",
        "kickoff_utc",
        "team",
        "measurement_id",
        "unit_role",
        "denominator",
        "coverage_status",
        "timing_class",
    }
    required_snapshots = {
        "season",
        "as_of_game_id",
        "team",
        "measurement_id",
        "unit_role",
        "adjustment_iteration",
        "adjusted_value",
        "timing_class",
    }
    if missing := sorted(required_observations - set(observations)):
        raise LiveReplayError(f"live observations lack columns: {missing}")
    if missing := sorted(required_snapshots - set(snapshots)):
        raise LiveReplayError(f"live snapshots lack columns: {missing}")
    if (
        not observations["timing_class"].eq("live").all()
        or not snapshots["timing_class"].eq("live").all()
    ):
        raise LiveReplayError("live measurement inputs have a non-live timing class")
    snapshot_values = {
        (
            int(row.as_of_game_id),
            str(row.team),
            str(row.measurement_id),
            str(row.unit_role),
        ): float(row.adjusted_value)
        for row in snapshots.itertuples(index=False)
        if int(row.season) == LIVE_SEASON
        and int(row.adjustment_iteration) == 4
        and pd.notna(row.adjusted_value)
    }
    boundary_by_game = (
        boundaries.set_index(["game_id", "team"])
        if not boundaries.empty
        else pd.DataFrame()
    )
    subset = observations[
        pd.to_numeric(observations["season"], errors="coerce").eq(LIVE_SEASON)
        & observations["measurement_id"].eq(FROZEN_DEFINITION)
        & observations["coverage_status"].eq("observed")
        & pd.to_numeric(observations["denominator"], errors="coerce").gt(0)
    ].copy()
    result: dict[str, dict[str, list[dict[str, Any]]]] = {role: {} for role in ROLES}
    for row in subset.itertuples(index=False):
        game_id = int(row.game_id)
        source_key = (game_id, str(row.team))
        if boundaries.empty or source_key not in boundary_by_game.index:
            continue
        boundary = boundary_by_game.loc[source_key]
        value = snapshot_values.get(
            (
                int(boundary.boundary_game_id),
                str(row.team),
                FROZEN_DEFINITION,
                str(row.unit_role),
            )
        )
        if value is None or not np.isfinite(value):
            continue
        role = str(row.unit_role)
        if role not in result:
            raise LiveReplayError("live observation has an unknown role")
        center, spread, sign = scale[role]
        result[role].setdefault(str(row.team), []).append(
            {
                "game_id": game_id,
                "kickoff_utc": pd.Timestamp(row.kickoff_utc),
                "boundary_cutoff_utc": pd.Timestamp(boundary.boundary_cutoff_utc),
                "adjusted_z": sign * (value - center) / spread,
                "exposure": float(row.denominator),
            }
        )
    for role in ROLES:
        for team in result[role]:
            result[role][team].sort(
                key=lambda item: (item["kickoff_utc"], item["game_id"])
            )
    return result


def build_live_replay(inputs: LiveReplayInputs) -> LiveReplayComputation:
    """Build canonical Contract 08 frames from verified immutable parents."""
    games = _live_games(inputs.population)
    boundaries = _boundaries(games)
    priors, lookup = _priors(games, inputs.historical_terminal)
    scale = {
        role: _historical_scale(inputs.historical_terminal, role=role) for role in ROLES
    }
    streams = _streams(
        observations=inputs.observations,
        snapshots=inputs.snapshots,
        boundaries=boundaries,
        scale=scale,
    )
    state_rows: list[dict[str, Any]] = []
    team_rows: list[dict[str, Any]] = []
    for game in games.itertuples(index=False):
        cutoff = pd.Timestamp(game.kickoff_utc)
        pair: dict[str, dict[str, tuple[float, float, float, int, str | None]]] = {}
        for team in (str(game.home_team), str(game.away_team)):
            pair[team] = {}
            for role in ROLES:
                prior_mean, prior_variance, sign = lookup[f"{role}\u0000{team}"]
                observed = [
                    item
                    for item in streams[role].get(team, [])
                    if item["boundary_cutoff_utc"] <= cutoff
                    and item["game_id"] != int(game.game_id)
                ]
                exposure = float(sum(item["exposure"] for item in observed))
                weighted = float(
                    sum(item["adjusted_z"] * item["exposure"] for item in observed)
                )
                information = exposure / _K
                variance = 1.0 / (1.0 / prior_variance + information)
                mean = variance * (prior_mean / prior_variance + weighted / _K)
                weight = information / (1.0 / prior_variance + information)
                fallback = priors[
                    priors["team"].eq(team) & priors["unit_role"].eq(role)
                ]["fallback_reason"].iloc[0]
                center, spread, _ = scale[role]
                state_rows.append(
                    {
                        "candidate_id": FROZEN_CANDIDATE,
                        "definition": FROZEN_DEFINITION,
                        "season": LIVE_SEASON,
                        "week": int(game.week),
                        "game_id": int(game.game_id),
                        "cutoff_utc": cutoff.isoformat(),
                        "team": team,
                        "unit_role": role,
                        "native_mean": mean * spread / sign + center,
                        "rating_mean": mean,
                        "rating_variance": variance,
                        "prior_mean": prior_mean,
                        "prior_variance": prior_variance,
                        "evidence_weight": weight,
                        "process_variance": 0.0,
                        "usable_exposure": exposure,
                        "completed_games": len(observed),
                        "fallback_reason": fallback,
                    }
                )
                pair[team][role] = (mean, variance, weight, len(observed), fallback)
        for team, roles in pair.items():
            if set(roles) != set(ROLES):
                raise LiveReplayError("replay omitted a team role")
            offense, defense = roles["offense"], roles["defense"]
            fallbacks = [value for value in (offense[4], defense[4]) if value]
            team_rows.append(
                {
                    "candidate_id": FROZEN_CANDIDATE,
                    "definition": FROZEN_DEFINITION,
                    "season": LIVE_SEASON,
                    "week": int(game.week),
                    "game_id": int(game.game_id),
                    "cutoff_utc": cutoff.isoformat(),
                    "team": team,
                    "offense_rating": offense[0],
                    "offense_variance": offense[1],
                    "defense_rating": defense[0],
                    "defense_variance": defense[1],
                    "overall_rating": (offense[0] + defense[0]) / 2.0,
                    "overall_variance": (offense[1] + defense[1]) / 4.0,
                    "fallback_reason": ";".join(sorted(set(fallbacks))) or None,
                }
            )
    states = (
        pd.DataFrame.from_records(state_rows, columns=list(RATING_STATE_COLUMNS))
        .sort_values(["week", "game_id", "team", "unit_role"], kind="mergesort")
        .reset_index(drop=True)
    )
    teams = (
        pd.DataFrame.from_records(team_rows, columns=list(TEAM_STATE_COLUMNS))
        .sort_values(["week", "game_id", "team"], kind="mergesort")
        .reset_index(drop=True)
    )
    return LiveReplayComputation(
        priors=priors,
        rating_states=states,
        team_states=teams,
        diagnostics={
            "live_season": LIVE_SEASON,
            "candidate_id": FROZEN_CANDIDATE,
            "weeks": sorted(games["week"].unique().tolist()),
            "eligible_games": int(len(games)),
            "state_rows": int(len(states)),
            "team_state_rows": int(len(teams)),
            "source_observations": int(
                sum(len(items) for role in streams.values() for items in role.values())
            ),
        },
    )


def build_current_team_states(
    *,
    population: pd.DataFrame,
    observations: pd.DataFrame,
    snapshots: pd.DataFrame,
    terminal: pd.DataFrame,
    priors: pd.DataFrame,
    historical_terminal: pd.DataFrame,
    as_of: str,
    target_week: int,
    target_teams: set[str] | None = None,
) -> pd.DataFrame:
    """Apply the frozen rating update to all certified evidence available now.

    ``team_states`` in the replay are *pregame* rows. Their last row cannot
    represent the current state, because it excludes that game's result. The
    Per-game adjusted observations come from the accepted replay. The
    terminal adjustment supplies the as-of value only for completed games that
    have not yet reached another team's later-week pregame snapshot.
    """
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        raise LiveReplayError("current rating cutoff must be timezone-aware")
    cutoff = cutoff.tz_convert("UTC")
    if population.empty and target_week == 0:
        games = population.copy()
        games["kickoff_utc"] = pd.to_datetime(games["kickoff_utc"], utc=True)
    else:
        games = _live_games(population)
    if games["week"].ge(target_week).any():
        raise LiveReplayError("current state contains target-week or future outcomes")
    if (games["kickoff_utc"] + pd.Timedelta(hours=_AVAILABILITY_HOURS) > cutoff).any():
        raise LiveReplayError(
            "completed game evidence has not passed the availability buffer"
        )
    required = {
        "season",
        "team",
        "measurement_id",
        "unit_role",
        "adjustment_iteration",
        "adjusted_value",
        "primary_exposure",
        "timing_class",
    }
    if missing := sorted(required - set(terminal)):
        raise LiveReplayError(f"current terminal measurements lack columns: {missing}")
    if not terminal["timing_class"].eq("live").all():
        raise LiveReplayError("current terminal measurements are not live evidence")
    required_observations = {
        "season",
        "game_id",
        "kickoff_utc",
        "team",
        "measurement_id",
        "unit_role",
        "denominator",
        "coverage_status",
        "timing_class",
    }
    if missing := sorted(required_observations - set(observations)):
        raise LiveReplayError(f"current observations lack columns: {missing}")
    eligible = observations[
        observations["season"].eq(LIVE_SEASON)
        & observations["measurement_id"].eq(FROZEN_DEFINITION)
        & observations["coverage_status"].eq("observed")
        & pd.to_numeric(observations["denominator"], errors="coerce").gt(0)
    ].copy()
    if eligible.duplicated(["game_id", "team", "unit_role"]).any():
        raise LiveReplayError("current observations duplicate a game/team/role")
    if not eligible.empty:
        game_lookup = games.set_index("game_id")
        for source in eligible.itertuples(index=False):
            game_id = int(source.game_id)
            if game_id not in game_lookup.index:
                raise LiveReplayError(
                    f"current observation refers to an ineligible source game: {game_id}"
                )
            game = game_lookup.loc[game_id]
            if str(source.team) not in (str(game.home_team), str(game.away_team)):
                raise LiveReplayError(
                    "current observation team is not a game participant"
                )
            if str(source.unit_role) not in ROLES:
                raise LiveReplayError("current observation has an unknown role")
            if pd.Timestamp(source.kickoff_utc) != pd.Timestamp(game.kickoff_utc):
                raise LiveReplayError(
                    "current observation kickoff differs from source game"
                )
    boundaries = _boundaries(games)
    scale = {role: _historical_scale(historical_terminal, role=role) for role in ROLES}
    streams = _streams(
        observations=observations,
        snapshots=snapshots,
        boundaries=boundaries,
        scale=scale,
    )
    bounded = (
        set(zip(boundaries["game_id"], boundaries["team"], strict=False))
        if not boundaries.empty
        else set()
    )
    latest = games.sort_values(["kickoff_utc", "game_id"], kind="mergesort")
    rows: list[dict[str, Any]] = []
    teams = set(games["home_team"].astype(str)) | set(games["away_team"].astype(str))
    teams.update(target_teams or ())
    for team in sorted(teams):
        team_games = latest[
            (latest["home_team"].eq(team)) | (latest["away_team"].eq(team))
        ]
        roles: dict[str, tuple[float, float, str | None]] = {}
        for role in ROLES:
            prior = priors[(priors["team"].eq(team)) & (priors["unit_role"].eq(role))]
            if len(prior) != 1:
                raise LiveReplayError(
                    f"current rating lacks one certified {role} prior for {team}"
                )
            prior_row = prior.iloc[0]
            prior_mean = float(prior_row["prior_mean"])
            prior_variance = float(prior_row["prior_variance"])
            if not np.isfinite(prior_variance) or prior_variance <= 0:
                raise LiveReplayError("current rating prior variance is invalid")
            measured = terminal[
                terminal["season"].eq(LIVE_SEASON)
                & terminal["team"].eq(team)
                & terminal["measurement_id"].eq(FROZEN_DEFINITION)
                & terminal["unit_role"].eq(role)
                & terminal["adjustment_iteration"].eq(4)
            ]
            if len(measured) > 1:
                raise LiveReplayError(
                    f"current rating duplicates {team} {role} measurement"
                )
            observed = list(streams[role].get(team, []))
            pending = eligible[
                eligible["team"].eq(team) & eligible["unit_role"].eq(role)
            ]
            for source in pending.itertuples(index=False):
                if (int(source.game_id), team) in bounded:
                    continue
                if len(measured) != 1:
                    raise LiveReplayError(
                        f"current rating lacks terminal adjustment for {team} {role}"
                    )
                value = float(measured.iloc[0]["adjusted_value"])
                if not np.isfinite(value):
                    raise LiveReplayError("current rating measurement is invalid")
                center, spread, sign = _historical_scale(historical_terminal, role=role)
                observed.append(
                    {
                        "game_id": int(source.game_id),
                        "adjusted_z": sign * (value - center) / spread,
                        "exposure": float(source.denominator),
                    }
                )
            exposure = float(sum(item["exposure"] for item in observed))
            weighted = float(
                sum(item["adjusted_z"] * item["exposure"] for item in observed)
            )
            information = exposure / _K
            variance = 1.0 / (1.0 / prior_variance + information)
            mean = variance * (prior_mean / prior_variance + weighted / _K)
            roles[role] = (mean, variance, prior_row["fallback_reason"])
        offense, defense = roles["offense"], roles["defense"]
        fallbacks = [
            str(value)
            for value in (offense[2], defense[2])
            if pd.notna(value) and value
        ]
        rows.append(
            {
                "candidate_id": FROZEN_CANDIDATE,
                "definition": FROZEN_DEFINITION,
                "season": LIVE_SEASON,
                "week": int(team_games.iloc[-1]["week"])
                if not team_games.empty
                else -1,
                "game_id": int(team_games.iloc[-1]["game_id"])
                if not team_games.empty
                else -1,
                "cutoff_utc": cutoff.isoformat(),
                "team": team,
                "offense_rating": offense[0],
                "offense_variance": offense[1],
                "defense_rating": defense[0],
                "defense_variance": defense[1],
                "overall_rating": (offense[0] + defense[0]) / 2.0,
                "overall_variance": (offense[1] + defense[1]) / 4.0,
                "fallback_reason": ";".join(sorted(set(fallbacks))) or None,
            }
        )
    return (
        pd.DataFrame.from_records(rows, columns=list(TEAM_STATE_COLUMNS))
        .sort_values("team")
        .reset_index(drop=True)
    )
