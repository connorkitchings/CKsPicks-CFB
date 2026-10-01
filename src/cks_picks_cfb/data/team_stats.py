"""Pre-game team season stats from the play-by-play lake (contract 10).

``build_team_season_stats`` aggregates FBS-vs-FBS games completed *before* week
``as_of_week`` into one long row per ``(team, role, metric)`` with the raw
value, the sample behind it and a national rank (1 = best). Plays use the same
filter as the V5 measurement layer (drive plays, garbage time excluded) and
points per scoring opportunity use the same score-stream reconstruction, so
there is one definition of each measurement in the repo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.ratings.observations import (
    derive_is_drive_play,
    true_drive_points,
)

#: Minimum completed FBS games before a team is ranked on any metric.
MIN_GAMES_FOR_RANK = 1

OFFENSE = "offense"
DEFENSE = "defense"

#: metric -> (offense higher_is_better, defense higher_is_better).
#: Defense columns describe what the defense *allowed* (turnover_rate is what
#: it forced, so more is better there).
METRICS: dict[str, tuple[bool, bool]] = {
    "epa_pass": (True, False),
    "epa_rush": (True, False),
    "early_down_epa": (True, False),
    "success_rate": (True, False),
    "explosive_rate": (True, False),
    "scoring_opp_rate": (True, False),
    "pts_per_scoring_opp": (True, False),
    "avg_start_field_pos": (True, False),
    "conv_rate_3rd_4th": (True, False),
    "turnover_rate": (False, True),
}

_REQUIRED_BYPLAY = (
    "season",
    "week",
    "game_id",
    "drive_number",
    "play_number",
    "offense",
    "defense",
    "st",
    "penalty",
    "twopoint",
    "play_type",
    "garbage",
    "ppa",
    "success",
    "yards_gained",
    "turnover",
    "quarter",
    "offense_score",
    "defense_score",
)
_REQUIRED_DRIVES = (
    "season",
    "game_id",
    "drive_number",
    "offense",
    "defense",
    "start_yards_to_goal",
    "had_scoring_opportunity",
)
_REQUIRED_GAMES = ("season", "game_id", "week", "home_team", "away_team")
_REQUIRED_OUTCOMES = ("season", "game_id", "completed", "home_points", "away_points")
#: Without these the 3rd/4th-down metric is null instead of failing the build.
_OPTIONAL_BYPLAY = ("down", "distance")


class TeamStatsContractError(ValueError):
    """Raised when an input frame lacks columns the build depends on."""


@dataclass(frozen=True)
class TeamStatsResult:
    frame: pd.DataFrame
    report: dict[str, Any]


def _require(frame: pd.DataFrame, columns: tuple[str, ...], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise TeamStatsContractError(f"{label} missing columns: {missing}")


def _is_pass(play_type: pd.Series) -> pd.Series:
    text = play_type.astype(str)
    return text.str.contains("Pass|Sack|Interception", case=False, regex=True)


def _is_rush(play_type: pd.Series) -> pd.Series:
    return play_type.astype(str).str.contains("Rush", case=False, regex=False)


def _mean(values: pd.Series) -> tuple[float | None, int]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return None, 0
    return float(clean.mean()), int(len(clean))


def _role_rows(
    plays: pd.DataFrame,
    drives: pd.DataFrame,
    team_col: str,
    role: str,
    has_down: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for team, team_plays in plays.groupby(team_col):
        ppa = pd.to_numeric(team_plays["ppa"], errors="coerce")
        yards = pd.to_numeric(team_plays["yards_gained"], errors="coerce")
        success = pd.to_numeric(team_plays["success"], errors="coerce")
        turnover = pd.to_numeric(team_plays["turnover"], errors="coerce")
        passing = _is_pass(team_plays["play_type"])
        rushing = _is_rush(team_plays["play_type"])
        values: dict[str, tuple[float | None, int]] = {
            "epa_pass": _mean(ppa[passing]),
            "epa_rush": _mean(ppa[rushing]),
            "success_rate": _mean(success),
            "explosive_rate": _mean((yards >= 20).astype(float).where(yards.notna())),
            "turnover_rate": _mean(
                (turnover == 1).astype(float).where(turnover.notna())
            ),
        }
        if has_down:
            down = pd.to_numeric(team_plays["down"], errors="coerce")
            distance = pd.to_numeric(team_plays["distance"], errors="coerce")
            values["early_down_epa"] = _mean(ppa[down.isin([1, 2])])
            late = down.isin([3, 4]) & yards.notna() & distance.notna()
            touchdown = team_plays["play_type"].astype(str).str.contains("Touchdown")
            converted = ((yards >= distance) | touchdown).astype(float)
            values["conv_rate_3rd_4th"] = _mean(converted[late])
        else:
            values["early_down_epa"] = (None, 0)
            values["conv_rate_3rd_4th"] = (None, 0)

        team_drives = drives[drives[team_col] == team]
        start = pd.to_numeric(team_drives["start_yards_to_goal"], errors="coerce")
        values["avg_start_field_pos"] = _mean(100 - start)
        opp = team_drives[team_drives["scoring_opportunity"]]
        n_drives = int(len(team_drives))
        values["scoring_opp_rate"] = (
            (float(len(opp)) / n_drives, n_drives) if n_drives else (None, 0)
        )
        valid_opp = opp[opp["ppso_valid"]]
        values["pts_per_scoring_opp"] = _mean(valid_opp["true_points"])

        for metric, (value, n) in values.items():
            rows.append(
                {
                    "team": team,
                    "role": role,
                    "metric": metric,
                    "value": value,
                    "n": n,
                }
            )
    return rows


def build_team_season_stats(
    *,
    byplay: pd.DataFrame,
    drives: pd.DataFrame,
    games: pd.DataFrame,
    outcomes: pd.DataFrame,
    fbs_teams: set[str],
    season: int,
    as_of_week: int,
    min_games: int = MIN_GAMES_FOR_RANK,
) -> TeamStatsResult:
    """Return long-format stats for games completed before ``as_of_week``."""
    _require(byplay, _REQUIRED_BYPLAY, "byplay")
    _require(drives, _REQUIRED_DRIVES, "drives")
    _require(games, _REQUIRED_GAMES, "games")
    _require(outcomes, _REQUIRED_OUTCOMES, "outcomes")
    has_down = all(c in byplay.columns for c in _OPTIONAL_BYPLAY)
    report: dict[str, Any] = {
        "season": season,
        "as_of_week": as_of_week,
        "missing_optional_columns": [
            c for c in _OPTIONAL_BYPLAY if c not in byplay.columns
        ],
    }

    g = games[pd.to_numeric(games["season"], errors="coerce") == season].copy()
    g["week_num"] = pd.to_numeric(g["week"], errors="coerce")
    done = outcomes[
        (pd.to_numeric(outcomes["season"], errors="coerce") == season)
        & (outcomes["completed"].fillna(False).astype(bool))
    ]
    eligible = g[
        (g["week_num"] < as_of_week)
        & g["home_team"].isin(fbs_teams)
        & g["away_team"].isin(fbs_teams)
        & g["game_id"].isin(done["game_id"])
    ].drop_duplicates(["season", "game_id"])
    report["eligible_games"] = int(len(eligible))
    columns = ["season", "as_of_week", "team", "role", "metric", "value", "n"]
    if eligible.empty:
        frame = pd.DataFrame(columns=columns + ["games", "rank", "cohort_size"])
        return TeamStatsResult(frame=frame, report=report)

    ids = set(eligible["game_id"].astype(int))
    plays = byplay[
        (pd.to_numeric(byplay["season"], errors="coerce") == season)
        & byplay["game_id"].astype(int).isin(ids)
    ].copy()
    drv = drives[
        (pd.to_numeric(drives["season"], errors="coerce") == season)
        & drives["game_id"].astype(int).isin(ids)
    ].copy()

    plays["is_drive_play"] = derive_is_drive_play(plays)
    garbage = pd.to_numeric(plays["garbage"], errors="coerce")
    plays["eligible"] = (plays["is_drive_play"] == 1) & (garbage == 0)
    report["plays_missing_garbage_flag"] = int(
        ((plays["is_drive_play"] == 1) & garbage.isna()).sum()
    )
    plays = plays[plays["eligible"]].copy()

    true = true_drive_points(
        byplay=byplay[
            (pd.to_numeric(byplay["season"], errors="coerce") == season)
            & byplay["game_id"].astype(int).isin(ids)
        ],
        games=eligible,
        outcomes=outcomes[
            (pd.to_numeric(outcomes["season"], errors="coerce") == season)
            & outcomes["game_id"].isin(ids)
        ],
    )
    report["ppso_invalid_offenses"] = len(true.invalid_offenses)

    keys = ["season", "game_id", "drive_number", "offense", "defense"]
    played = plays.groupby(keys).size().rename("eligible_plays").reset_index()
    drv = drv.merge(played, on=keys, how="inner")
    drv["scoring_opportunity"] = (
        pd.to_numeric(drv["had_scoring_opportunity"], errors="coerce").fillna(0) == 1
    )
    drv = drv.merge(
        true.drive_points,
        on=["season", "game_id", "drive_number", "offense"],
        how="left",
    )
    invalid = {(int(s), int(gid), str(t)) for s, gid, t in true.invalid_offenses}
    drv["ppso_valid"] = drv["true_points"].notna() & ~drv.apply(
        lambda r: (int(r["season"]), int(r["game_id"]), str(r["offense"])) in invalid,
        axis=1,
    )

    rows = _role_rows(plays, drv, "offense", OFFENSE, has_down) + _role_rows(
        plays, drv, "defense", DEFENSE, has_down
    )
    frame = pd.DataFrame(rows, columns=["team", "role", "metric", "value", "n"])
    frame = frame[frame["team"].isin(fbs_teams)].copy()

    game_counts: dict[str, int] = {}
    for row in eligible.itertuples(index=False):
        for team in (row.home_team, row.away_team):
            game_counts[team] = game_counts.get(team, 0) + 1
    frame["games"] = frame["team"].map(game_counts).fillna(0).astype(int)
    frame["season"] = season
    frame["as_of_week"] = as_of_week

    frame["rank"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    frame["cohort_size"] = pd.Series(pd.NA, index=frame.index, dtype="Int64")
    for (role, metric), idx in frame.groupby(["role", "metric"]).groups.items():
        higher_off, higher_def = METRICS[metric]
        higher_is_better = higher_off if role == OFFENSE else higher_def
        pool = frame.loc[idx]
        pool = pool[pool["value"].notna() & (pool["games"] >= min_games)]
        if pool.empty:
            continue
        ranks = (
            pool["value"].rank(method="min", ascending=not higher_is_better).astype(int)
        )
        frame.loc[ranks.index, "rank"] = ranks
        frame.loc[ranks.index, "cohort_size"] = int(len(pool))
    frame["value"] = frame["value"].astype(float).replace({np.nan: None})
    frame = frame[columns + ["games", "rank", "cohort_size"]].reset_index(drop=True)
    report["teams"] = int(frame["team"].nunique())
    return TeamStatsResult(frame=frame, report=report)
