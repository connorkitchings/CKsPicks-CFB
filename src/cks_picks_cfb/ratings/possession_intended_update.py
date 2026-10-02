"""Versioned V5 intended-update ratings, separate from the accepted V5 replay.

Each available source game contributes its own opponent-adjusted PPP and usable
possessions once. Opponent context is recalculated at each target cutoff.
This module is pure computation; artifact certification and serving are separate.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.ratings.possession_live_replay import _historical_scale

MODEL_ID = "v5-intended-update-2026-v1"
CANDIDATE_ID = "ppp__rho_0_60__exposure__game_at_cutoff_v1"
MEASUREMENT_ID = "ppp"
EXPOSURE_K = 8.0
AVAILABILITY_HOURS = 6
ROLES = ("offense", "defense")


class IntendedUpdateError(ValueError):
    """The successor inputs or chronology do not satisfy the fixed design."""


@dataclass(frozen=True)
class RatingGeneration:
    """A fully explained rating generation at one forecast or display cutoff."""

    rating_states: pd.DataFrame
    team_states: pd.DataFrame


def _time(value: Any) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if result.tzinfo is None:
        raise IntendedUpdateError("rating cutoff must have a timezone")
    return result.tz_convert("UTC")


def usable_ppp_mask(source: pd.DataFrame) -> pd.Series:
    """A PPP observation feeds the rating only when it is observed, has a
    positive denominator and finite numerator and value. Everything else is an
    excluded game (the rating's explanation never lists those)."""
    return (
        source.coverage_status.eq("observed")
        & pd.to_numeric(source.denominator, errors="coerce").gt(0)
        & np.isfinite(pd.to_numeric(source.raw_value, errors="coerce"))
        & np.isfinite(pd.to_numeric(source.numerator, errors="coerce"))
    )


def _source_rows(observations: pd.DataFrame, schedule: pd.DataFrame) -> pd.DataFrame:
    required = {
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "team",
        "opponent",
        "measurement_id",
        "unit_role",
        "raw_value",
        "numerator",
        "denominator",
        "coverage_status",
    }
    if missing := sorted(required - set(observations)):
        raise IntendedUpdateError(f"observations lack columns: {missing}")
    source = observations[observations.measurement_id.eq(MEASUREMENT_ID)].copy()
    if source.duplicated(["season", "game_id", "team", "unit_role"]).any():
        raise IntendedUpdateError("duplicate team-game-role PPP observation")
    keys = schedule[
        ["season", "week", "game_id", "kickoff_utc", "home_team", "away_team"]
    ]
    checked = source.merge(
        keys,
        on=["season", "week", "game_id"],
        how="left",
        validate="many_to_one",
        suffixes=("", "_schedule"),
        indicator=True,
    )
    if checked._merge.ne("both").any():
        raise IntendedUpdateError("PPP observation has no scheduled game")
    if any(
        row.team not in (row.home_team, row.away_team)
        or row.opponent not in (row.home_team, row.away_team)
        or row.team == row.opponent
        for row in checked.itertuples(index=False)
    ):
        raise IntendedUpdateError("PPP observation has invalid team or opponent")
    if not (
        pd.to_datetime(checked.kickoff_utc, utc=True)
        == pd.to_datetime(checked.kickoff_utc_schedule, utc=True)
    ).all():
        raise IntendedUpdateError("PPP observation kickoff differs from schedule")
    source["kickoff_utc"] = pd.to_datetime(source.kickoff_utc, utc=True)
    source["available_utc"] = source.kickoff_utc + pd.Timedelta(
        hours=AVAILABILITY_HOURS
    )
    source["denominator"] = pd.to_numeric(source.denominator, errors="coerce")
    source["raw_value"] = pd.to_numeric(source.raw_value, errors="coerce")
    source["numerator"] = pd.to_numeric(source.numerator, errors="coerce")
    source["usable"] = usable_ppp_mask(source)
    if not source.unit_role.isin(ROLES).all():
        raise IntendedUpdateError("PPP source has an unknown role")
    return source.sort_values(
        ["season", "week", "game_id", "team", "unit_role"], kind="mergesort"
    )


def _four_pass_context(
    rows: pd.DataFrame,
) -> tuple[dict[tuple[str, str], float], dict[str, float]]:
    """Return pass-three opponent estimates and centers used by pass four."""
    if rows.empty:
        return {}, {}
    sums: dict[tuple[str, str], float] = defaultdict(float)
    exposure: dict[tuple[str, str], float] = defaultdict(float)
    for row in rows.itertuples(index=False):
        key = str(row.team), str(row.unit_role)
        sums[key] += float(row.numerator)
        exposure[key] += float(row.denominator)
    raw = {key: sums[key] / amount for key, amount in exposure.items() if amount > 0}
    adjusted = dict(raw)
    context: dict[tuple[str, str], float] = {}
    centers: dict[str, float] = {}
    for _ in range(4):
        center_sum: dict[str, float] = defaultdict(float)
        center_exposure: dict[str, float] = defaultdict(float)
        for row in rows.itertuples(index=False):
            key = str(row.team), str(row.unit_role)
            if key in adjusted:
                role = str(row.unit_role)
                amount = float(row.denominator)
                center_sum[role] += adjusted[key] * amount
                center_exposure[role] += amount
        centers = {
            role: center_sum[role] / amount
            for role, amount in center_exposure.items()
            if amount > 0
        }
        context = adjusted
        delta_sum: dict[tuple[str, str], float] = defaultdict(float)
        delta_exposure: dict[tuple[str, str], float] = defaultdict(float)
        for row in rows.itertuples(index=False):
            role = str(row.unit_role)
            opposite = "defense" if role == "offense" else "offense"
            opponent = adjusted.get((str(row.opponent), opposite))
            center = centers.get(opposite)
            if opponent is None or center is None:
                continue
            key = str(row.team), role
            amount = float(row.denominator)
            delta_sum[key] += (opponent - center) * amount
            delta_exposure[key] += amount
        adjusted = {
            key: value - delta_sum[key] / delta_exposure[key]
            if delta_exposure[key] > 0
            else value
            for key, value in raw.items()
        }
    return context, centers


class IntendedUpdate:
    """Evaluate fixed-prior 2026 ratings at game or post-week cutoffs."""

    def __init__(
        self,
        *,
        schedule: pd.DataFrame,
        observations: pd.DataFrame,
        priors: pd.DataFrame,
        historical_terminal: pd.DataFrame,
    ) -> None:
        required = {
            "season",
            "week",
            "game_id",
            "kickoff_utc",
            "home_team",
            "away_team",
        }
        if missing := sorted(required - set(schedule)):
            raise IntendedUpdateError(f"schedule lacks columns: {missing}")
        games = schedule[schedule.season.eq(2026)].copy()
        if games.empty or games.duplicated(["season", "game_id"]).any():
            raise IntendedUpdateError("2026 schedule is empty or duplicated")
        games["kickoff_utc"] = pd.to_datetime(games.kickoff_utc, utc=True)
        if games[["week", "kickoff_utc", "home_team", "away_team"]].isna().any().any():
            raise IntendedUpdateError("2026 schedule is incomplete")
        self.schedule = games.sort_values(
            ["week", "kickoff_utc", "game_id"], kind="mergesort"
        )
        self.sources = _source_rows(observations, self.schedule)
        if not set(self.sources.season.astype(int)) <= {2026}:
            raise IntendedUpdateError(
                "2026 updater received another season's observations"
            )
        if not {"season", "team", "unit_role", "prior_mean", "prior_variance"} <= set(
            priors
        ):
            raise IntendedUpdateError("certified prior frame is incomplete")
        selected = priors[priors.season.eq(2026)].copy()
        if selected.duplicated(["team", "unit_role"]).any():
            raise IntendedUpdateError("duplicate certified prior")
        self.priors = {
            (str(row.team), str(row.unit_role)): (
                float(row.prior_mean),
                float(row.prior_variance),
            )
            for row in selected.itertuples(index=False)
        }
        self.teams = sorted(
            set(self.schedule.home_team.astype(str))
            | set(self.schedule.away_team.astype(str))
        )
        if set(self.priors) != {(team, role) for team in self.teams for role in ROLES}:
            raise IntendedUpdateError("certified priors do not cover scheduled teams")
        if any(
            not np.isfinite(mean) or not np.isfinite(var) or var <= 0
            for mean, var in self.priors.values()
        ):
            raise IntendedUpdateError("invalid certified prior value")
        self.scales = {
            role: _historical_scale(historical_terminal, role=role) for role in ROLES
        }

    def _evidence(
        self, *, week: int, cutoff: pd.Timestamp, exclude_game_id: int | None = None
    ) -> pd.DataFrame:
        source = self.sources
        return source[
            source.week.lt(week)
            & source.available_utc.le(cutoff)
            & source.usable
            & (
                source.game_id.ne(exclude_game_id)
                if exclude_game_id is not None
                else True
            )
        ]

    def _states(
        self,
        *,
        week: int,
        cutoff: pd.Timestamp,
        game_id: int | None,
        teams: Iterable[str],
    ) -> RatingGeneration:
        evidence = self._evidence(week=week, cutoff=cutoff, exclude_game_id=game_id)
        opponent_values, centers = _four_pass_context(evidence)
        rating_rows: list[dict[str, Any]] = []
        for team in teams:
            for role in ROLES:
                prior_mean, prior_variance = self.priors[(team, role)]
                center, spread, sign = self.scales[role]
                items = evidence[evidence.team.eq(team) & evidence.unit_role.eq(role)]
                contributions: list[dict[str, Any]] = []
                information_sum = 0.0
                exposure = 0.0
                for item in items.itertuples(index=False):
                    opposite = "defense" if role == "offense" else "offense"
                    opponent = opponent_values.get((str(item.opponent), opposite))
                    opponent_center = centers.get(opposite)
                    missing = opponent is None or opponent_center is None
                    native = (
                        float(item.raw_value)
                        if missing
                        else float(item.raw_value) - (opponent - opponent_center)
                    )
                    z_value = sign * (native - center) / spread
                    possessions = float(item.denominator)
                    exposure += possessions
                    information_sum += possessions * z_value / EXPOSURE_K
                    contributions.append(
                        {
                            "game_id": int(item.game_id),
                            "source_week": int(item.week),
                            "available_utc": _time(item.available_utc).isoformat(),
                            "exposure": possessions,
                            "raw_ppp": float(item.raw_value),
                            "adjusted_ppp": native,
                            "adjusted_z": z_value,
                            "missing_context_reason": "missing_opponent_context_raw_ppp"
                            if missing
                            else None,
                        }
                    )
                variance = 1.0 / (1.0 / prior_variance + exposure / EXPOSURE_K)
                mean = variance * (prior_mean / prior_variance + information_sum)
                for item in contributions:
                    item["contribution"] = (
                        variance * item["exposure"] * item["adjusted_z"] / EXPOSURE_K
                    )
                rating_rows.append(
                    {
                        "candidate_id": CANDIDATE_ID,
                        "season": 2026,
                        "week": week,
                        "game_id": game_id,
                        "cutoff_utc": cutoff,
                        "team": team,
                        "unit_role": role,
                        "rating_mean": float(mean),
                        "rating_variance": float(variance),
                        "prior_mean": prior_mean,
                        "prior_variance": prior_variance,
                        "usable_exposure": exposure,
                        "source_game_ids": json.dumps(
                            [item["game_id"] for item in contributions]
                        ),
                        "explanation": json.dumps(
                            {
                                "k": EXPOSURE_K,
                                "prior_weight": variance / prior_variance,
                                "prior_contribution": variance
                                * prior_mean
                                / prior_variance,
                                "evidence_contributions": contributions,
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    }
                )
        role_frame = pd.DataFrame.from_records(rating_rows)
        off = role_frame[role_frame.unit_role.eq("offense")].set_index("team")
        defense = role_frame[role_frame.unit_role.eq("defense")].set_index("team")
        combined = []
        for team in sorted(teams):
            offense = off.loc[team]
            defensive = defense.loc[team]
            combined.append(
                {
                    "candidate_id": CANDIDATE_ID,
                    "season": 2026,
                    "week": week,
                    "game_id": game_id,
                    "cutoff_utc": cutoff,
                    "team": team,
                    "offense_rating": float(offense.rating_mean),
                    "offense_variance": float(offense.rating_variance),
                    "defense_rating": float(defensive.rating_mean),
                    "defense_variance": float(defensive.rating_variance),
                    "overall_rating": float(
                        (offense.rating_mean + defensive.rating_mean) / 2
                    ),
                    "overall_variance": float(
                        (offense.rating_variance + defensive.rating_variance) / 4
                    ),
                }
            )
        return RatingGeneration(role_frame, pd.DataFrame.from_records(combined))

    def pregame(self) -> RatingGeneration:
        ratings = []
        teams = []
        for game in self.schedule.itertuples(index=False):
            generation = self._states(
                week=int(game.week),
                cutoff=_time(game.kickoff_utc),
                game_id=int(game.game_id),
                teams=(str(game.home_team), str(game.away_team)),
            )
            ratings.append(generation.rating_states)
            teams.append(generation.team_states)
        return RatingGeneration(
            pd.concat(ratings, ignore_index=True),
            pd.concat(teams, ignore_index=True),
        )

    def current(self, *, post_week: int, cutoff_utc: str) -> RatingGeneration:
        cutoff = _time(cutoff_utc)
        if (
            self.schedule[self.schedule.week.eq(post_week)].kickoff_utc.max()
            + pd.Timedelta(hours=AVAILABILITY_HOURS)
            > cutoff
        ):
            raise IntendedUpdateError("post-week cutoff precedes six-hour availability")
        return self._states(
            week=post_week + 1,
            cutoff=cutoff,
            game_id=None,
            teams=self.teams,
        )
