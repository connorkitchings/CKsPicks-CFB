#!/usr/bin/env python3
"""Audit decreases in the play-by-play running score (known issue 1).

For every game and team the running score is read from ``offense_score`` when the
team is on offense and from ``defense_score`` when it is on defense, in play
order (``drive_number``, ``play_number``). A decrease is impossible in football,
so each one is reported with its size, the plays around it, whether the score
later returned to its earlier value, and a cause class. The audit also lists
games whose largest running score differs from the game final.

Read-only: it reads local parquet/csv files and writes only the CSV outputs
named on the command line. Example (the certified w4 Silver copies)::

    PYTHONPATH=src:. uv run python scripts/analysis/audit_score_stream.py \\
        --byplay w4_byplay.parquet --games w4_games.parquet \\
        --outcomes w4_game_outcomes.parquet --out-dir /tmp/score_audit
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_BYPLAY = (
    "game_id",
    "drive_number",
    "play_number",
    "offense",
    "defense",
    "offense_score",
    "defense_score",
    "play_type",
    "scoring",
)

CAUSES = (
    "a_drop_to_zero",
    "b_pat_or_2pt_credited_early",
    "c_scoring_row_other_size",
    "d_penalty_adjacent",
    "f_other_nonscoring_prev",
)


def _team_series(group: pd.DataFrame, team: str) -> tuple[pd.DataFrame, np.ndarray]:
    """Rows where ``team`` plays, and its running score on those rows."""
    score = np.where(
        group["offense"] == team,
        group["offense_score"],
        np.where(group["defense"] == team, group["defense_score"], np.nan),
    ).astype(float)
    keep = ~np.isnan(score)
    return group[keep].reset_index(drop=True), score[keep]


def classify_drop(
    *, to_zero: bool, size: float, prev_scoring: bool, prev_type: str, cur_type: str
) -> str:
    """Cause class of one score decrease (first matching rule wins)."""
    if to_zero:
        return "a_drop_to_zero"
    if prev_scoring and size in (1.0, 2.0):
        return "b_pat_or_2pt_credited_early"
    if prev_scoring:
        return "c_scoring_row_other_size"
    if "Penalty" in (prev_type, cur_type):
        return "d_penalty_adjacent"
    return "f_other_nonscoring_prev"


def find_drops(byplay: pd.DataFrame) -> pd.DataFrame:
    """One row per decrease in a team's running score."""
    missing = sorted(set(REQUIRED_BYPLAY) - set(byplay.columns))
    if missing:
        raise ValueError(f"byplay missing columns: {missing}")
    has_td = "td_play" in byplay.columns
    records: list[dict] = []
    for game_id, game in byplay.groupby("game_id", sort=False):
        game = game.sort_values(
            ["drive_number", "play_number"], kind="mergesort"
        ).reset_index(drop=True)
        for team in sorted(set(game["offense"]) | set(game["defense"])):
            rows, score = _team_series(game, str(team))
            for i in np.flatnonzero(np.diff(score) < 0):
                j = i + 1
                prev = rows.iloc[i]
                prev_scoring = bool(prev["scoring"]) or (
                    has_td and int(prev["td_play"]) == 1
                )
                size = float(score[i] - score[j])
                to_zero = bool(score[j] == 0)
                restored = bool((score[j + 1 :] >= score[i]).any())
                records.append(
                    {
                        "game_id": int(game_id),
                        "team": str(team),
                        "week": int(rows["week"].iloc[0]) if "week" in rows else None,
                        "before": float(score[i]),
                        "after": float(score[j]),
                        "size": size,
                        "to_zero": to_zero,
                        "prev_scoring": prev_scoring,
                        "prev_type": str(prev["play_type"]),
                        "cur_type": str(rows.iloc[j]["play_type"]),
                        "restored": restored,
                        "cause": classify_drop(
                            to_zero=to_zero,
                            size=size,
                            prev_scoring=prev_scoring,
                            prev_type=str(prev["play_type"]),
                            cur_type=str(rows.iloc[j]["play_type"]),
                        ),
                    }
                )
    columns = [
        "game_id",
        "team",
        "week",
        "before",
        "after",
        "size",
        "to_zero",
        "prev_scoring",
        "prev_type",
        "cur_type",
        "restored",
        "cause",
    ]
    return pd.DataFrame.from_records(records, columns=columns)


def team_game_count(byplay: pd.DataFrame) -> int:
    """Number of (game, team) pairs that appear in the play-by-play."""
    pairs = set(zip(byplay["game_id"], byplay["offense"], strict=True)) | set(
        zip(byplay["game_id"], byplay["defense"], strict=True)
    )
    return len(pairs)


def summarize(drops: pd.DataFrame, n_team_games: int) -> dict:
    """Counts of events, flagged team-games and causes."""
    flagged = drops[["game_id", "team"]].drop_duplicates()
    return {
        "events": int(len(drops)),
        "team_games": int(n_team_games),
        "flagged_team_games": int(len(flagged)),
        "flagged_share": round(len(flagged) / n_team_games, 3)
        if n_team_games
        else None,
        "restored_events": int(drops["restored"].sum()) if len(drops) else 0,
        "not_restored_events": int((~drops["restored"]).sum()) if len(drops) else 0,
        "by_cause": {cause: int((drops["cause"] == cause).sum()) for cause in CAUSES},
    }


def running_max_vs_final(
    byplay: pd.DataFrame,
    games: pd.DataFrame,
    outcomes: pd.DataFrame,
    canonical: Callable[[str], str] = lambda name: name,
) -> pd.DataFrame:
    """Team-games whose largest running score differs from the game final.

    The maximum is taken over ``offense_score`` and ``defense_score``: an
    offense-only maximum misses points scored while on defense.
    """
    finals = games[["game_id", "home_team", "away_team"]].merge(
        outcomes[["game_id", "home_points", "away_points"]], on="game_id"
    )
    expected: dict[tuple[int, str], float] = {}
    for row in finals.itertuples(index=False):
        expected[(int(row.game_id), canonical(str(row.home_team)))] = float(
            row.home_points
        )
        expected[(int(row.game_id), canonical(str(row.away_team)))] = float(
            row.away_points
        )
    records = []
    for game_id, game in byplay.groupby("game_id", sort=False):
        for team in set(game["offense"]) | set(game["defense"]):
            key = (int(game_id), canonical(str(team)))
            if key not in expected:
                continue
            top = max(
                game.loc[game["offense"] == team, "offense_score"].max(),
                game.loc[game["defense"] == team, "defense_score"].max(),
            )
            if float(top) != expected[key]:
                records.append(
                    {
                        "game_id": key[0],
                        "team": key[1],
                        "final": expected[key],
                        "running_max": float(top),
                    }
                )
    return pd.DataFrame.from_records(
        records, columns=["game_id", "team", "final", "running_max"]
    )


def _read(path: str) -> pd.DataFrame:
    return pd.read_csv(path) if path.endswith(".csv") else pd.read_parquet(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--byplay", required=True)
    parser.add_argument("--games")
    parser.add_argument("--outcomes")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    byplay = _read(args.byplay)
    if args.season is not None and "season" in byplay:
        byplay = byplay[byplay["season"] == args.season]
    drops = find_drops(byplay)
    summary = summarize(drops, team_game_count(byplay))
    print("score-stream audit:", summary)
    if args.games and args.outcomes:
        from cks_picks_cfb.preseason_features import canonical_team

        games = _read(args.games)
        outcomes = _read(args.outcomes)
        canon_by = byplay.assign(
            offense=byplay["offense"].map(canonical_team),
            defense=byplay["defense"].map(canonical_team),
        )
        mismatched = running_max_vs_final(canon_by, games, outcomes, canonical_team)
        print(f"team-games with running max != final: {len(mismatched)}")
        if args.out_dir:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            mismatched.to_csv(args.out_dir / "running_max_vs_final.csv", index=False)
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        drops.to_csv(args.out_dir / "score_drops.csv", index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
