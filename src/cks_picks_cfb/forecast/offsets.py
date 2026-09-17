"""Earlier-only regulation non-offense translation offsets for V5 forecasts."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


class OffsetError(ValueError):
    """Raised when non-offense evidence cannot support a pregame offset."""


@dataclass(frozen=True)
class OffsetComputation:
    offsets: pd.DataFrame
    team_games: pd.DataFrame


def regulation_non_offense_events(events: pd.DataFrame) -> pd.DataFrame:
    """Return only the ledger category permitted to translate forecast targets."""
    required = {
        "season",
        "game_id",
        "team",
        "period_class",
        "scoring_category",
        "score_increment",
    }
    if missing := sorted(required - set(events)):
        raise OffsetError(f"scoring ledger lacks columns: {missing}")
    selected = events[
        events["period_class"].eq("regulation")
        & events["scoring_category"].eq("regulation_non_offense")
    ].copy()
    selected["score_increment"] = pd.to_numeric(
        selected["score_increment"], errors="raise"
    )
    if (selected["score_increment"] < 0).any():
        raise OffsetError("scoring ledger has a negative non-offense increment")
    return selected


def team_game_non_offense(
    population: pd.DataFrame, events: pd.DataFrame
) -> pd.DataFrame:
    """Attribute regulation non-offense points to both schedule participants.

    Population status, not the presence of a scoring row, establishes a usable
    zero-point team game.  This preserves paired coverage and prevents an
    incomplete ledger from silently becoming a zero observation.
    """
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
        raise OffsetError(f"population lacks columns: {missing}")
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
    selected = regulation_non_offense_events(events)
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
            # A scoring event may never be attributed to a non-participant.
            foreign = selected[
                selected["season"].eq(key[0])
                & selected["game_id"].eq(key[1])
                & ~selected["team"].isin((str(game.home_team), str(game.away_team)))
            ]
            if not foreign.empty:
                raise OffsetError(
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


def build_offsets(
    population: pd.DataFrame,
    events: pd.DataFrame,
    *,
    development_seasons: tuple[int, ...],
    equivalent_games: int = 4,
) -> OffsetComputation:
    """Construct one immutable pregame translation per eligible matchup.

    The current-season accumulators advance only after a game is emitted. Games
    sharing a kickoff therefore cannot affect one another's offset.
    """
    if equivalent_games <= 0:
        raise OffsetError("equivalent_games must be positive")
    team_games = team_game_non_offense(population, events)
    seasons = tuple(int(value) for value in development_seasons)
    if tuple(sorted(seasons)) != seasons or 2020 in seasons:
        raise OffsetError("forecast season policy is not sealed")
    prior_means: dict[int, float] = {}
    for index, season in enumerate(seasons):
        previous = seasons[index - 1] if index else None
        if previous is None:
            prior_means[season] = 0.0
            continue
        prior = team_games[team_games["season"].eq(previous) & team_games["usable"]]
        if prior.empty or prior.groupby("game_id")["team"].nunique().ne(2).any():
            raise OffsetError(f"missing paired league evidence for {season}")
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
        # Games at an identical cutoff cannot become evidence for one another.
        for current in pending:
            if len(current) == 2:
                for row in current.itertuples(index=False):
                    history.setdefault((int(season), str(row.team)), []).append(
                        (float(row.non_offense_for), float(row.non_offense_against))
                    )
    return OffsetComputation(pd.DataFrame.from_records(output), team_games)
