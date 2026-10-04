"""Pre-game team season stats from the play-by-play lake (contract 10).

``build_team_season_stats`` aggregates FBS-vs-FBS games completed *before* week
``as_of_week`` into one long row per ``(team, role, metric)`` with the raw
value, the sample behind it and a national rank (1 = best). Plays use
``play_filters.scrimmage_play_mask``: the V5 eligibility filter (regulation
only; no special teams, penalties, two-point tries, dead plays or garbage time)
minus kicking plays, which Silver can leave flagged ``st == 0`` (returned
punts). Points per scoring opportunity use the V5 score-stream reconstruction.
Team stats is the source of basic stats; the ratings import the play rules from
``data.play_filters`` instead of keeping their own.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.play_filters import (
    eligible_possession_play_mask,
    scrimmage_play_mask,
)
from cks_picks_cfb.ratings.contracts import MeasurementContractError
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
    "ppa_per_play": (True, False),
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
    "down",
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
#: Silver byplay renames CFBD's ``distance`` to ``yards_to_first``.
_DISTANCE_COLUMNS = ("yards_to_first", "distance")
_CONVERSION_FLAGS = ("thirddown_conversion", "fourthdown_conversion")
#: Used when present; the build falls back to the play_type regex without them.
_OPTIONAL_BYPLAY = ("dropback", "rush_attempt", "yards_to_goal", *_CONVERSION_FLAGS)


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


def _distance(plays: pd.DataFrame) -> pd.Series | None:
    """Yards to first down; goal-to-go plays with 0/null use yards to goal."""
    column = next((c for c in _DISTANCE_COLUMNS if c in plays.columns), None)
    if column is None:
        return None
    distance = pd.to_numeric(plays[column], errors="coerce").astype(float)
    if "yards_to_goal" in plays.columns:
        goal = pd.to_numeric(plays["yards_to_goal"], errors="coerce").astype(float)
        distance = distance.where(distance > 0, goal)
    return distance


def _conversions(plays: pd.DataFrame, down: pd.Series, yards: pd.Series) -> pd.Series:
    """1.0/0.0 on 3rd/4th-down plays, NaN elsewhere.

    Silver's per-down conversion flags are authoritative. The fallback (yards
    >= distance, or an offensive touchdown) never credits a turnover return.
    """
    if all(c in plays.columns for c in _CONVERSION_FLAGS):
        third = pd.to_numeric(plays["thirddown_conversion"], errors="coerce")
        fourth = pd.to_numeric(plays["fourthdown_conversion"], errors="coerce")
        flag = third.where(down == 3, fourth.where(down == 4))
        return flag
    distance = _distance(plays)
    play_type = plays["play_type"].astype(str)
    returned = play_type.str.contains("Return|Interception|Fumble", case=False)
    touchdown = play_type.str.contains("Touchdown") & ~returned
    turnover = pd.to_numeric(plays["turnover"], errors="coerce") == 1
    converted = ((yards >= distance) | touchdown) & ~turnover
    return converted.astype(float).where(
        down.isin([3, 4]) & yards.notna() & distance.notna()
    )


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
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for team, team_plays in plays.groupby(team_col):
        ppa = pd.to_numeric(team_plays["ppa"], errors="coerce")
        if "ppa_missing" in team_plays:
            ppa = ppa.mask(team_plays["ppa_missing"].eq(True))
        yards = pd.to_numeric(team_plays["yards_gained"], errors="coerce")
        success = pd.to_numeric(team_plays["success"], errors="coerce")
        turnover = pd.to_numeric(team_plays["turnover"], errors="coerce")
        if {"dropback", "rush_attempt"} <= set(team_plays.columns):
            dropback = pd.to_numeric(team_plays["dropback"], errors="coerce") == 1
            rush_flag = pd.to_numeric(team_plays["rush_attempt"], errors="coerce") == 1
            passing = dropback
            rushing = rush_flag & ~dropback
        else:
            passing = _is_pass(team_plays["play_type"])
            rushing = _is_rush(team_plays["play_type"])
        down = pd.to_numeric(team_plays["down"], errors="coerce")
        values: dict[str, tuple[float | None, int]] = {
            "ppa_per_play": _mean(ppa),
            "epa_pass": _mean(ppa[passing]),
            "epa_rush": _mean(ppa[rushing]),
            "early_down_epa": _mean(ppa[down.isin([1, 2])]),
            "conv_rate_3rd_4th": _mean(_conversions(team_plays, down, yards)),
            "success_rate": _mean(success),
            "explosive_rate": _mean((yards >= 20).astype(float).where(yards.notna())),
            "turnover_rate": _mean(
                (turnover == 1).astype(float).where(turnover.notna())
            ),
        }

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
    has_flags = all(c in byplay.columns for c in _CONVERSION_FLAGS)
    if not has_flags and not any(c in byplay.columns for c in _DISTANCE_COLUMNS):
        raise TeamStatsContractError(
            "byplay needs yards_to_first/distance or the thirddown_conversion "
            "and fourthdown_conversion flags for 3rd/4th-down conversion"
        )
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
    if "season_type" in g.columns:
        g = g[g["season_type"].astype(str).str.lower() == "regular"]
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
    for label, frame_ in (("byplay", plays), ("drives", drv)):
        gaps = sorted(ids - set(frame_["game_id"].astype(int)))
        if gaps:
            raise TeamStatsContractError(
                f"{len(gaps)} completed games have no {label} rows "
                f"(Silver refs out of step?): {gaps[:20]}"
            )

    plays["is_drive_play"] = derive_is_drive_play(plays)
    garbage = pd.to_numeric(plays["garbage"], errors="coerce")
    # The legacy V5 filter still passes returned punts (Silver st == 0); team
    # stats drops them. See data/play_filters.py.
    legacy_eligible = eligible_possession_play_mask(plays)
    plays["eligible"] = scrimmage_play_mask(plays)
    report["punt_plays_excluded"] = int((legacy_eligible & ~plays["eligible"]).sum())
    report["plays_missing_garbage_flag"] = int(
        ((plays["is_drive_play"] == 1) & garbage.isna()).sum()
    )
    plays = plays[plays["eligible"]].copy()

    try:
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
    except MeasurementContractError as exc:
        raise TeamStatsContractError(f"score stream: {exc}") from exc
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
    bad_offense = [
        (int(s_), int(g_), str(o_)) in invalid
        for s_, g_, o_ in drv[["season", "game_id", "offense"]].itertuples(index=False)
    ]
    drv["ppso_valid"] = drv["true_points"].notna() & ~pd.Series(
        bad_offense, index=drv.index, dtype=bool
    )

    rows = _role_rows(plays, drv, "offense", OFFENSE) + _role_rows(
        plays, drv, "defense", DEFENSE
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


UPSERT_TEAM_STAT_SQL = """
INSERT INTO team_season_stats
    (season, as_of_week, team, role, metric, value, n, games, rank, cohort_size,
     source_versions)
VALUES
    (%(season)s, %(as_of_week)s, %(team)s, %(role)s, %(metric)s, %(value)s,
     %(n)s, %(games)s, %(rank)s, %(cohort_size)s, %(source_versions)s::jsonb)
ON CONFLICT (season, as_of_week, team, role, metric) DO UPDATE SET
    value = EXCLUDED.value,
    n = EXCLUDED.n,
    games = EXCLUDED.games,
    rank = EXCLUDED.rank,
    cohort_size = EXCLUDED.cohort_size,
    source_versions = EXCLUDED.source_versions,
    updated_at = NOW()
"""


def to_upsert_records(
    frame: pd.DataFrame, source_versions: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Convert the stats frame to DB-ready dicts (NaN/NA become None).

    ``source_versions`` (dataset name -> Silver version id) is stored on every
    row so a snapshot can be traced to the exact inputs that produced it.
    """
    provenance = json.dumps(source_versions or {}, sort_keys=True)

    def clean(value: Any) -> Any:
        if value is None or value is pd.NA:
            return None
        if isinstance(value, float) and np.isnan(value):
            return None
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        return value

    return [
        {**{key: clean(val) for key, val in row.items()}, "source_versions": provenance}
        for row in frame.to_dict(orient="records")
    ]


def diff_report(
    old: pd.DataFrame, new: pd.DataFrame, *, tolerance: float = 1e-9, top: int = 10
) -> dict[str, Any]:
    """Compare published rows with a rebuilt frame before republishing.

    Both frames use the long format (season, as_of_week, team, role, metric,
    value, rank). Returns counts, per-metric value and rank deltas, and the
    largest rank movers so a methodology change can be reviewed before it is
    written.
    """
    keys = ["as_of_week", "team", "role", "metric"]
    merged = old[keys + ["value", "rank"]].merge(
        new[keys + ["value", "rank"]],
        on=keys,
        how="outer",
        suffixes=("_old", "_new"),
        indicator=True,
    )
    both = merged[merged["_merge"] == "both"].copy()
    both["value_delta"] = pd.to_numeric(
        both["value_new"], errors="coerce"
    ) - pd.to_numeric(both["value_old"], errors="coerce")
    both["rank_shift"] = pd.to_numeric(
        both["rank_new"], errors="coerce"
    ) - pd.to_numeric(both["rank_old"], errors="coerce")
    changed = both[both["value_delta"].abs() > tolerance]
    per_metric = []
    for (role, metric), group in both.groupby(["role", "metric"]):
        moved = group["rank_shift"].abs()
        per_metric.append(
            {
                "role": role,
                "metric": metric,
                "rows": int(len(group)),
                "changed": int((group["value_delta"].abs() > tolerance).sum()),
                "mean_abs_value_delta": float(group["value_delta"].abs().mean()),
                "max_abs_value_delta": float(group["value_delta"].abs().max()),
                "mean_abs_rank_shift": float(moved.mean()),
                "max_abs_rank_shift": float(moved.max())
                if moved.notna().any()
                else 0.0,
                "rank_shift_over_5": int((moved > 5).sum()),
            }
        )
    movers = both.assign(abs_shift=both["rank_shift"].abs()).nlargest(top, "abs_shift")
    return {
        "rows_old": int(len(old)),
        "rows_new": int(len(new)),
        "only_old": int((merged["_merge"] == "left_only").sum()),
        "only_new": int((merged["_merge"] == "right_only").sum()),
        "rows_compared": int(len(both)),
        "rows_changed": int(len(changed)),
        "per_metric": per_metric,
        "top_movers": [
            {
                "as_of_week": int(r.as_of_week),
                "team": r.team,
                "role": r.role,
                "metric": r.metric,
                "rank_old": None if pd.isna(r.rank_old) else int(r.rank_old),
                "rank_new": None if pd.isna(r.rank_new) else int(r.rank_new),
                "value_old": None if pd.isna(r.value_old) else float(r.value_old),
                "value_new": None if pd.isna(r.value_new) else float(r.value_new),
            }
            for r in movers.itertuples(index=False)
        ],
    }
