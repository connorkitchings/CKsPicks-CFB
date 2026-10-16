"""One row per team per game with eligible-play success and EPA sums.

Plays, games and metric validity are identical to ``build_team_season_stats``
(``data/team_stats.py``): ``scrimmage_play_mask`` plays of FBS-vs-FBS, regular
season, completed games; EPA is ``ppa`` masked where ``ppa_missing``; success and
EPA each drop their own missing values. Counts and sums are stored so any
cumulative window reproduces the team-stats values exactly.
"""

from __future__ import annotations

from collections.abc import Collection

import pandas as pd

from cks_picks_cfb.data.play_filters import scrimmage_play_mask

STAT_FIELDS = ("plays", "success_n", "success_sum", "epa_n", "epa_sum")
TEAM_GAME_COLUMNS = (
    "season",
    "week",
    "game_id",
    "team",
    "opponent",
    "site",
    "points_for",
    "points_against",
    *(f"{role}_{field}" for role in ("off", "def") for field in STAT_FIELDS),
)
_REQUIRED_PLAYS = ("season", "game_id", "offense", "defense", "ppa", "success")


class TeamGameStatsError(ValueError):
    """The inputs cannot produce team-game chart statistics."""


def _side_stats(plays: pd.DataFrame, team_col: str) -> dict[tuple[int, str], dict]:
    ppa = pd.to_numeric(plays["ppa"], errors="coerce")
    if "ppa_missing" in plays:
        ppa = ppa.mask(plays["ppa_missing"].eq(True))
    success = pd.to_numeric(plays["success"], errors="coerce")
    frame = pd.DataFrame(
        {
            "game_id": plays["game_id"].astype(int).to_numpy(),
            "team": plays[team_col].astype(str).to_numpy(),
            "ppa": ppa.to_numpy(),
            "success": success.to_numpy(),
        }
    )
    out: dict[tuple[int, str], dict] = {}
    for (game_id, team), group in frame.groupby(["game_id", "team"]):
        epa = group["ppa"].dropna()
        ok = group["success"].dropna()
        out[(int(game_id), str(team))] = {
            "plays": int(len(group)),
            "success_n": int(len(ok)),
            "success_sum": float(ok.sum()),
            "epa_n": int(len(epa)),
            "epa_sum": float(epa.sum()),
        }
    return out


def build_team_game_stats(
    *,
    byplay: pd.DataFrame,
    games: pd.DataFrame,
    finals: pd.DataFrame,
    fbs_teams: Collection[str],
    neutral_game_ids: Collection[int],
    season: int,
    active_week: int,
) -> pd.DataFrame:
    """Two mirrored rows per completed FBS-vs-FBS regular-season game before ``active_week``.

    ``games`` carries provider team names (``home_team``/``away_team``), ``week``
    and ``game_id``; ``finals`` the final points; ``neutral_game_ids`` the games
    played at a neutral site.
    """
    missing = [c for c in _REQUIRED_PLAYS if c not in byplay.columns]
    if missing:
        raise TeamGameStatsError(f"byplay lacks columns: {missing}")
    fbs = set(fbs_teams)
    schedule = games[pd.to_numeric(games["season"], errors="coerce") == season].copy()
    schedule["week_num"] = pd.to_numeric(schedule["week"], errors="coerce")
    if "season_type" in schedule.columns:
        schedule = schedule[
            schedule["season_type"].astype(str).str.lower() == "regular"
        ]
    scores = finals[pd.to_numeric(finals["season"], errors="coerce") == season]
    eligible = schedule[
        (schedule["week_num"] < active_week)
        & schedule["home_team"].isin(fbs)
        & schedule["away_team"].isin(fbs)
        & schedule["game_id"].isin(scores["game_id"])
    ].drop_duplicates(["season", "game_id"])
    if eligible.empty:
        return pd.DataFrame(columns=list(TEAM_GAME_COLUMNS))
    points = scores.drop_duplicates("game_id").set_index("game_id")
    ids = set(eligible["game_id"].astype(int))
    plays = byplay[
        (pd.to_numeric(byplay["season"], errors="coerce") == season)
        & byplay["game_id"].astype(int).isin(ids)
    ].copy()
    gaps = sorted(ids - set(plays["game_id"].astype(int)))
    if gaps:
        raise TeamGameStatsError(f"completed games without plays: {gaps[:20]}")
    plays = plays[scrimmage_play_mask(plays)]
    offense = _side_stats(plays, "offense")
    defense = _side_stats(plays, "defense")
    empty = dict.fromkeys(STAT_FIELDS, 0)
    neutral = {int(g) for g in neutral_game_ids}
    rows = []
    for game in eligible.itertuples(index=False):
        game_id = int(game.game_id)
        final = points.loc[game_id]
        home_points, away_points = final["home_points"], final["away_points"]
        sides = (
            (game.home_team, game.away_team, "home", home_points, away_points),
            (game.away_team, game.home_team, "away", away_points, home_points),
        )
        for team, opponent, site, scored, allowed in sides:
            row = {
                "season": season,
                "week": int(game.week_num),
                "game_id": game_id,
                "team": str(team),
                "opponent": str(opponent),
                "site": "neutral" if game_id in neutral else site,
                "points_for": int(scored),
                "points_against": int(allowed),
            }
            for role, stats in (("off", offense), ("def", defense)):
                found = stats.get((game_id, str(team)), empty)
                row.update({f"{role}_{field}": found[field] for field in STAT_FIELDS})
            rows.append(row)
    frame = pd.DataFrame(rows, columns=list(TEAM_GAME_COLUMNS))
    return frame.sort_values(
        ["season", "game_id", "team"], kind="mergesort"
    ).reset_index(drop=True)
