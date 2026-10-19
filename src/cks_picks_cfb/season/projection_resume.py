"""Season-release resume projection: SOS, SOR and WAA for each rating period.

Pure and deterministic. The inputs are the rating periods the release already holds,
the full schedule, the finals frame that ``game_results`` is built from, the FBS team
names and the pinned V5 margin bridge. The output is one :class:`TeamResume` per
(rating period, FBS team). Definitions follow
``docs/plans/2026-10-19/02-sos-sor-release-projection.md``.

Caller contract:

* ``ratings`` carries ``period_id`` (the caller's period label), ``cutoff_utc``,
  ``post_week`` (null for preseason), ``team``, ``offense_rating``, ``defense_rating``
  and ``overall_rating``. ``frames["current_ratings"]`` supplies all of these except
  ``period_id``.
* ``schedule`` and ``finals`` use the same canonical team names as ``ratings``. A rated
  FBS team that the schedule never names is an error, not a silent drop.
* The margin bridge has no venue or per-game offset term: a game is scored with its
  recorded home and away labels, and ``offset_margin`` is not applied.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, NamedTuple

import pandas as pd

from cks_picks_cfb.season.projection_common import clean_value
from cks_picks_cfb.season.projection_football import _fbs_teams
from cks_picks_cfb.season.projection_serving import BRIDGE_SHA256

ELITE_SIZE = 25
MIN_RESUME_GAMES = 3
#: The period id of the preseason; generations use :func:`source_qualified_period_id`.
PRESEASON_PERIOD = "preseason"
#: Natural key of ``season_release_team_resume`` (``release.PROJECTION_KEYS``).
RESUME_ROW_KEY = ("period_id", "team")
MARGIN_FEATURES = ("home_offense", "home_defense", "away_offense", "away_defense")
RATING_COLUMNS = (
    "period_id",
    "cutoff_utc",
    "post_week",
    "team",
    "offense_rating",
    "defense_rating",
    "overall_rating",
)
SCHEDULE_COLUMNS = ("game_id", "kickoff_utc", "home_team", "away_team")
FINAL_COLUMNS = ("game_id", "home_points", "away_points")

#: (offense_rating, defense_rating) of one team.
Rating = tuple[float, float]


@dataclass(frozen=True)
class MarginBridge:
    """The V5 margin head restated on raw team ratings, with its calibration sigma.

    ``margin_home = intercept + home_offense * H_off + home_defense * H_def
    + away_offense * A_off + away_defense * A_def`` and the home team wins with
    probability ``Phi(margin_home / sigma)``.
    """

    intercept: float
    home_offense: float
    home_defense: float
    away_offense: float
    away_defense: float
    sigma: float


@dataclass(frozen=True)
class TeamResume:
    """One row of the resume projection: a team's record and résumé in one period."""

    period_id: str
    cutoff_utc: pd.Timestamp
    post_week: int | None
    team: str
    overall_rank: int
    completed_games: int
    scheduled_games: int
    wins: int
    losses: int
    elite_reference_size: int
    elite_reference_kind: str
    average_reference_size: int
    sos_played_elite: float | None
    sos_remaining_elite: float | None
    sos_full_elite: float | None
    sos_played_average: float | None
    sos_remaining_average: float | None
    sos_full_average: float | None
    sor_p: float | None
    sor: float | None
    sor_rank: int | None
    waa: float | None


RESUME_COLUMNS = tuple(field.name for field in fields(TeamResume))


class _Game(NamedTuple):
    game_id: int
    kickoff_utc: pd.Timestamp
    home_team: str
    away_team: str
    home_points: float
    away_points: float


def margin_bridge_from_bundle(bundle: Mapping[str, Any]) -> MarginBridge:
    """Restate the bundle's margin head on raw ratings.

    The bundle standardizes each feature as ``(x - center) / scale``, so the raw-rating
    slope is ``coefficient / scale`` and the intercept absorbs ``-slope * center``.
    """
    if bundle.get("schema_version") != "v5_inference_bundle_v1":
        raise ValueError("bridge schema_version is not v5_inference_bundle_v1")
    spec = bundle["targets"]["margin"]
    names = list(spec["feature_names"])
    if names != list(MARGIN_FEATURES):
        raise ValueError(f"margin bridge features changed: {names}")
    coefficients = dict(zip(names, map(float, spec["coefficients"]), strict=True))
    slopes = {name: coefficients[name] / float(spec["scale"][name]) for name in names}
    intercept = float(spec["intercept"]) - math.fsum(
        slopes[name] * float(spec["center"][name]) for name in names
    )
    return MarginBridge(
        intercept=intercept,
        home_offense=slopes["home_offense"],
        home_defense=slopes["home_defense"],
        away_offense=slopes["away_offense"],
        away_defense=slopes["away_defense"],
        sigma=math.sqrt(float(spec["calibration_variance"])),
    )


def load_pinned_bridge(path: Path) -> MarginBridge:
    """Read the margin bridge from the bundle file, which must be the pinned bytes."""
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BRIDGE_SHA256:
        raise ValueError("bridge bytes differ from the pinned B2 bundle")
    return margin_bridge_from_bundle(json.loads(raw))


def win_probability(
    bridge: MarginBridge,
    *,
    reference_is_home: bool,
    reference: Rating,
    opponent: Rating,
) -> float:
    """Probability that ``reference`` beats ``opponent`` in the recorded home/away slot."""
    home, away = (reference, opponent) if reference_is_home else (opponent, reference)
    margin_home = (
        bridge.intercept
        + bridge.home_offense * home[0]
        + bridge.home_defense * home[1]
        + bridge.away_offense * away[0]
        + bridge.away_defense * away[1]
    )
    signed_margin = margin_home if reference_is_home else -margin_home
    return _normal_cdf(signed_margin / bridge.sigma)


def at_least_wins_probability(win_probs: Sequence[float], wins: int) -> float:
    """Exact Poisson-binomial ``P(at least wins)`` for independent games."""
    distribution = [1.0]
    for p in win_probs:
        following = [0.0] * (len(distribution) + 1)
        for count, mass in enumerate(distribution):
            following[count] += mass * (1.0 - p)
            following[count + 1] += mass * p
        distribution = following
    # Rounding in the convolution can push the sum a few ulps past 1.0.
    return min(1.0, max(0.0, math.fsum(distribution[wins:])))


def _sor(sor_p: float) -> float:
    """Strength of record ``(1 - P) * 100``, bounded to [0, 100] with no negative zero."""
    return max(0.0, min(100.0, (1.0 - sor_p) * 100.0))


def rank_order(overall: Mapping[str, float]) -> list[str]:
    """Teams best first by overall rating; equal ratings are ordered by team name."""
    return sorted(overall, key=lambda team: (-overall[team], team))


def elite_reference_members(ranked: Sequence[str]) -> dict[str, tuple[str, ...]]:
    """The teams each team's elite reference averages, given teams ranked best first.

    A team ranked in the top 25 is measured against the other top-25 teams plus the
    26th-ranked team, so it never sees itself. Every other team, including the 26th,
    is measured against the plain top 25. With fewer than 26 teams, a top-25 team is
    measured against every other team.
    """
    top = tuple(ranked[:ELITE_SIZE])
    members: dict[str, tuple[str, ...]] = {}
    for index, team in enumerate(ranked):
        if index < ELITE_SIZE:
            candidates = ranked[: ELITE_SIZE + 1]
            members[team] = tuple(
                other for position, other in enumerate(candidates) if position != index
            )
        else:
            members[team] = top
    return members


def completed_game_ids(
    schedule: pd.DataFrame, finals: pd.DataFrame, cutoff_utc: str
) -> set[int]:
    """Games completed at ``cutoff_utc``: kicked off at or before it, with a final."""
    _require_columns("schedule", schedule, SCHEDULE_COLUMNS)
    _require_columns("finals", finals, FINAL_COLUMNS)
    cutoff = pd.Timestamp(cutoff_utc)
    return {
        game.game_id for game in _games(schedule, finals) if _is_completed(game, cutoff)
    }


def build_team_resume(
    *,
    ratings: pd.DataFrame,
    schedule: pd.DataFrame,
    finals: pd.DataFrame,
    fbs_teams: Collection[str],
    bridge: MarginBridge,
) -> list[TeamResume]:
    """One :class:`TeamResume` per (rating period, FBS team), sorted by period and team."""
    _require_columns("ratings", ratings, RATING_COLUMNS)
    if ratings.duplicated(["period_id", "team"]).any():
        raise ValueError("ratings repeat a team within a rating period")
    games = _games(schedule, finals)
    scheduled_teams = {game.home_team for game in games} | {
        game.away_team for game in games
    }
    fbs = set(fbs_teams)
    rated = ratings[ratings["team"].isin(fbs)].assign(
        cutoff_utc=lambda frame: pd.to_datetime(frame["cutoff_utc"], utc=True)
    )
    unmatched = sorted(set(rated["team"]) - scheduled_teams)
    if unmatched:
        raise ValueError(
            f"FBS teams rated but absent from the schedule (name mismatch?): {unmatched}"
        )
    games_by_team: dict[str, list[_Game]] = defaultdict(list)
    for game in games:
        games_by_team[game.home_team].append(game)
        games_by_team[game.away_team].append(game)

    rows: list[TeamResume] = []
    for period_id, period in rated.groupby("period_id", sort=True):
        if (
            period["cutoff_utc"].nunique() != 1
            or period["post_week"].nunique(dropna=False) != 1
        ):
            raise ValueError(f"rating period {period_id} mixes cutoffs or post weeks")
        post_week = period["post_week"].iloc[0]
        rows.extend(
            _period_rows(
                str(period_id),
                period["cutoff_utc"].iloc[0],
                None if pd.isna(post_week) else int(post_week),
                period,
                games_by_team,
                bridge,
            )
        )
    return sorted(rows, key=lambda row: (row.cutoff_utc, row.period_id, row.team))


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _mean(ratings: Iterable[Rating]) -> Rating:
    rows = list(ratings)
    return (
        math.fsum(offense for offense, _ in rows) / len(rows),
        math.fsum(defense for _, defense in rows) / len(rows),
    )


def _sos(win_probs: Sequence[float]) -> float | None:
    """Mean opponent difficulty ``(1 - p) * 100``; None when no games."""
    if not win_probs:
        return None
    return 100.0 * math.fsum(1.0 - p for p in win_probs) / len(win_probs)


def _is_completed(game: _Game, cutoff: pd.Timestamp) -> bool:
    return (
        game.kickoff_utc <= cutoff
        and pd.notna(game.home_points)
        and pd.notna(game.away_points)
    )


def _games(schedule: pd.DataFrame, finals: pd.DataFrame) -> list[_Game]:
    decided = finals.dropna(subset=["home_points", "away_points"])
    tied = decided.loc[decided["home_points"] == decided["away_points"], "game_id"]
    if not tied.empty:
        raise ValueError(
            f"FBS games cannot end tied; equal final scores for game_ids "
            f"{tied.astype(int).tolist()}"
        )
    if finals["game_id"].duplicated().any():
        raise ValueError("finals repeats a game_id")
    if schedule["game_id"].duplicated().any():
        raise ValueError("schedule repeats a game_id")
    merged = (
        schedule[list(SCHEDULE_COLUMNS)]
        .assign(
            kickoff_utc=lambda frame: pd.to_datetime(frame["kickoff_utc"], utc=True)
        )
        .merge(finals[list(FINAL_COLUMNS)], on="game_id", how="left")
    )
    if merged["kickoff_utc"].isna().any():
        raise ValueError("schedule has a game without kickoff_utc")
    return [
        _Game(
            game_id=int(row.game_id),
            kickoff_utc=row.kickoff_utc,
            home_team=str(row.home_team),
            away_team=str(row.away_team),
            home_points=float(row.home_points),
            away_points=float(row.away_points),
        )
        for row in merged.itertuples(index=False)
    ]


def _period_rows(
    period_id: str,
    cutoff: pd.Timestamp,
    post_week: int | None,
    period: pd.DataFrame,
    games_by_team: Mapping[str, list[_Game]],
    bridge: MarginBridge,
) -> list[TeamResume]:
    overall = {
        str(team): float(value)
        for team, value in zip(period["team"], period["overall_rating"], strict=True)
    }
    vectors = {
        str(team): (float(offense), float(defense))
        for team, offense, defense in zip(
            period["team"],
            period["offense_rating"],
            period["defense_rating"],
            strict=True,
        )
    }
    if len(vectors) < 2:
        raise ValueError(f"rating period {period_id} has fewer than two FBS teams")
    ranked = rank_order(overall)
    members = elite_reference_members(ranked)
    average = _mean(vectors.values())
    rows: list[TeamResume] = []
    for rank, team in enumerate(ranked, start=1):
        elite = _mean(vectors[other] for other in members[team])
        full_elite: list[float] = []
        full_average: list[float] = []
        remaining_elite: list[float] = []
        remaining_average: list[float] = []
        completed_elite: list[float] = []
        completed_average: list[float] = []
        wins = 0
        for game in games_by_team.get(team, []):
            is_home = game.home_team == team
            opponent_name = game.away_team if is_home else game.home_team
            if opponent_name not in vectors:
                continue
            opponent = vectors[opponent_name]
            p_elite = win_probability(
                bridge,
                reference_is_home=is_home,
                reference=elite,
                opponent=opponent,
            )
            p_average = win_probability(
                bridge,
                reference_is_home=is_home,
                reference=average,
                opponent=opponent,
            )
            full_elite.append(p_elite)
            full_average.append(p_average)
            if game.kickoff_utc > cutoff:
                remaining_elite.append(p_elite)
                remaining_average.append(p_average)
            if _is_completed(game, cutoff):
                completed_elite.append(p_elite)
                completed_average.append(p_average)
                own, other = (
                    (game.home_points, game.away_points)
                    if is_home
                    else (game.away_points, game.home_points)
                )
                wins += int(own > other)
        completed = len(completed_elite)
        resume = completed >= MIN_RESUME_GAMES
        sor_p = at_least_wins_probability(completed_elite, wins) if resume else None
        rows.append(
            TeamResume(
                period_id=period_id,
                cutoff_utc=cutoff,
                post_week=post_week,
                team=team,
                overall_rank=rank,
                completed_games=completed,
                scheduled_games=len(full_elite),
                wins=wins,
                losses=completed - wins,
                elite_reference_size=len(members[team]),
                elite_reference_kind=(
                    "top25_excluding_self" if rank <= ELITE_SIZE else "top25"
                ),
                average_reference_size=len(ranked),
                sos_played_elite=_sos(completed_elite),
                sos_remaining_elite=_sos(remaining_elite),
                sos_full_elite=_sos(full_elite),
                sos_played_average=_sos(completed_average),
                sos_remaining_average=_sos(remaining_average),
                sos_full_average=_sos(full_average),
                sor_p=sor_p,
                sor=None if sor_p is None else _sor(sor_p),
                sor_rank=None,
                waa=(wins - math.fsum(completed_average) if resume else None),
            )
        )
    return _with_sor_ranks(rows)


def _with_sor_ranks(rows: list[TeamResume]) -> list[TeamResume]:
    """Rank SOR within a period, 1 is best; ties go to the better overall rank."""
    ordered = sorted(
        (row for row in rows if row.sor is not None),
        key=lambda row: (-row.sor, row.overall_rank),
    )
    ranks = {row.team: position for position, row in enumerate(ordered, start=1)}
    return [replace(row, sor_rank=ranks.get(row.team)) for row in rows]


def _require_columns(name: str, frame: pd.DataFrame, columns: Sequence[str]) -> None:
    if missing := sorted(set(columns) - set(frame.columns)):
        raise ValueError(f"{name} lacks columns: {missing}")


# --------------------------------------------------------------------------
# Release payload glue
# --------------------------------------------------------------------------
def source_qualified_period_id(ratings_id: str, cutoff: object) -> str:
    """The period id of a generation, as the served rating snapshots name it.

    Matches ``sourceQualifiedPeriodId`` in ``web/src/lib/rating-periods.ts``:
    ``<source sha256>@<cutoff as JavaScript toISOString()>``, which is millisecond
    precision with a ``Z`` suffix.
    """
    stamp = pd.Timestamp(cutoff)
    if stamp.tzinfo is None:
        raise ValueError(f"naive rating cutoff: {cutoff!r}")
    stamp = stamp.tz_convert("UTC")
    return (
        f"{ratings_id}@{stamp.strftime('%Y-%m-%dT%H:%M:%S')}"
        f".{stamp.microsecond // 1000:03d}Z"
    )


def period_ratings(frames: Mapping[str, pd.DataFrame], ratings_id: str) -> pd.DataFrame:
    """Every served rating period's team ratings, tagged with ``period_id``.

    The preseason is the week-0 pregame state of ``frames["ratings"]``. Each
    generation is one post-week of ``frames["current_ratings"]``, the rows the served
    ``current`` snapshots are built from, so the ids agree with those snapshots.
    """
    pregame = frames["ratings"]
    preseason = pregame[pregame["target_week"].astype(int).eq(0)].assign(
        period_id=PRESEASON_PERIOD, post_week=None
    )
    current = frames["current_ratings"]
    generations = current.assign(
        period_id=[
            source_qualified_period_id(ratings_id, cutoff)
            for cutoff in current["cutoff_utc"]
        ]
    )
    return pd.concat([preseason, generations], ignore_index=True)[list(RATING_COLUMNS)]


def canonical_fbs_teams(inputs: Any) -> set[str]:
    """Canonical names of the FBS teams. FCS opponents are not in the set.

    The pinned teams input names teams by provider; the schedule maps each provider
    name to its canonical name, and a provider name must not map to two of them.
    """
    canonical: dict[str, str] = {}
    for side in ("home", "away"):
        pairs = zip(
            inputs.schedule[f"{side}_team_provider"],
            inputs.schedule[f"{side}_team"],
            strict=True,
        )
        for provider, name in pairs:
            if canonical.setdefault(str(provider), str(name)) != str(name):
                raise ValueError(f"provider team {provider!r} has two canonical names")
    return {canonical[name] for name in _fbs_teams(inputs.teams) if name in canonical}


def resume_rows(resumes: Sequence[TeamResume]) -> list[dict]:
    """Payload rows of ``season_release_team_resume``, sorted by the natural key."""
    rows = [
        {column: clean_value(getattr(resume, column)) for column in RESUME_COLUMNS}
        for resume in resumes
    ]
    return sorted(rows, key=lambda row: tuple(row[key] for key in RESUME_ROW_KEY))


def build_resume(
    *,
    frames: Mapping[str, pd.DataFrame],
    inputs: Any,
    ratings_id: str,
) -> dict[str, list[dict]]:
    """``{"team_resume": rows}``: one row per FBS team per served rating period.

    ``ratings_id`` is the rating lineage identity, which every served rating snapshot
    carries as ``source_manifest_sha256``. The bridge must be the pinned bytes.
    """
    if inputs.bridge_sha256 != BRIDGE_SHA256:
        raise ValueError("bridge bytes differ from the pinned B2 bundle")
    resumes = build_team_resume(
        ratings=period_ratings(frames, ratings_id),
        schedule=inputs.schedule,
        finals=frames["finals"],
        fbs_teams=canonical_fbs_teams(inputs),
        bridge=margin_bridge_from_bundle(inputs.bridge),
    )
    return {"team_resume": resume_rows(resumes)}
