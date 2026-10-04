"""Silver invariants and gate 6. All register at ``warn`` until receipts are reviewed.

Inputs (all optional; a check whose input is absent reports ``skipped``):

- ``source_reconciliation``: the persisted reconciliation Silver dataset
  (``game_id, classification, blocking``)
- ``byplay``: ``game_id, offense, defense, offense_score, defense_score, drive_number,
  play_number`` (``play_number`` restarts in each drive)
  and optionally ``ppa``/``ppa_missing``
- ``drives``: ``game_id, drive_number, offense, points`` (``drive_number`` is one
  sequence per game starting at 1)
- ``games``: ``game_id, home_team, away_team, home_points, away_points, completed``
- ``games_previous``: the previous validated ``games`` version for the same season
- ``capture_index``: ``capture_id, content_sha, object_sha, uri, captured_at``

These checks add evidence the build gates do not record (the standard build already
reconciles scores and refuses blocking conflicts); they never repair data.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from cks_picks_cfb.quality.checks import WARN, Outcome, register_check, skipped

REFRESH_FIELDS = ("completed", "home_points", "away_points")
CAPTURE_PIN_FIELDS = ("content_sha", "object_sha", "uri", "captured_at")


def reconciliation_summary(rec: pd.DataFrame) -> dict[str, Any]:
    blocking = int(rec["blocking"].fillna(True).astype(bool).sum())
    return {
        "games": len(rec),
        "blocking": blocking,
        "by_classification": {
            str(k): int(v) for k, v in rec["classification"].value_counts().items()
        },
    }


def score_stream_regressions(byplay: pd.DataFrame) -> dict[str, Any]:
    """Team-games whose running score ever decreases in (drive, play) order.

    ``play_number`` restarts in each drive, so plays are ordered by drive first.
    """
    frame = byplay.dropna(subset=["offense_score", "defense_score"]).copy()
    frame["order"] = frame["drive_number"].astype(float) * 100_000 + frame[
        "play_number"
    ].astype(float)
    side_a = frame[["game_id", "offense", "offense_score", "order"]].set_axis(
        ["game_id", "team", "score", "order"], axis=1
    )
    side_b = frame[["game_id", "defense", "defense_score", "order"]].set_axis(
        ["game_id", "team", "score", "order"], axis=1
    )
    long = pd.concat([side_a, side_b], ignore_index=True).sort_values(
        ["game_id", "team", "order"], kind="stable"
    )
    long["drop"] = long.groupby(["game_id", "team"])["score"].diff().lt(0)
    per = long.groupby(["game_id", "team"])["drop"].any()
    return {
        "team_games": len(per),
        "regressed": int(per.sum()),
        "games_affected": int(per[per].reset_index()["game_id"].nunique()),
        "fraction": float(per.mean()) if len(per) else 0.0,
    }


def drive_numbering_problems(drives: pd.DataFrame) -> dict[str, Any]:
    """Drive numbers form one sequence per game; each (game, offense, number) is unique.

    A number can appear under both teams when possession changes inside a drive, so
    contiguity is checked on the union of numbers in a game, uniqueness per offense.
    """
    dup = int(drives.duplicated(["game_id", "offense", "drive_number"]).sum())
    gaps: list[int] = []
    for game_id, group in drives.groupby("game_id"):
        ids = sorted(set(group["drive_number"].astype(int)))
        if ids != list(range(1, ids[-1] + 1)):
            gaps.append(int(game_id))
    return {
        "games": int(drives["game_id"].nunique()),
        "duplicate_keys": dup,
        "gap_games": sorted(gaps),
    }


def play_drive_game_coverage(
    byplay: pd.DataFrame, drives: pd.DataFrame
) -> dict[str, Any]:
    plays_games = set(byplay["game_id"].astype(int))
    drive_games = set(drives["game_id"].astype(int))
    return {
        "plays_without_drives": sorted(plays_games - drive_games),
        "drives_without_plays": sorted(drive_games - plays_games),
    }


def points_identity(drives: pd.DataFrame, games: pd.DataFrame) -> dict[str, Any]:
    """Drive points per team against the final score.

    Drive points can fall below the final (defensive and special-teams scores are not
    drive points) but can never exceed it. Excess points are an identity violation.
    """
    done = games[games["completed"].fillna(False).astype(bool)]
    finals = pd.concat(
        [
            done[["game_id", "home_team", "home_points"]].set_axis(
                ["game_id", "team", "final"], axis=1
            ),
            done[["game_id", "away_team", "away_points"]].set_axis(
                ["game_id", "team", "final"], axis=1
            ),
        ],
        ignore_index=True,
    ).dropna(subset=["final"])
    got = (
        drives.groupby(["game_id", "offense"])["points"]
        .sum()
        .rename("drive_points")
        .reset_index()
        .rename(columns={"offense": "team"})
    )
    merged = finals.merge(got, on=["game_id", "team"], how="left")
    unmatched = merged["drive_points"].isna()
    excess = merged[~unmatched & (merged["drive_points"] > merged["final"])]
    return {
        "team_games": len(merged),
        "no_drive_points": int(unmatched.sum()),
        "excess": [
            {
                "game_id": int(r.game_id),
                "team": r.team,
                "drive": float(r.drive_points),
                "final": float(r.final),
            }
            for r in excess.itertuples()
        ],
    }


def ppa_flag_problems(byplay: pd.DataFrame) -> dict[str, Any]:
    if "ppa_missing" not in byplay.columns:
        return {"flag_present": False}
    ppa_null = byplay["ppa"].isna()
    flag = byplay["ppa_missing"].fillna(False).astype(bool)
    return {
        "flag_present": True,
        "plays": len(byplay),
        "null_not_flagged": int((ppa_null & ~flag).sum()),
        "flagged_with_value": int((~ppa_null & flag).sum()),
        "flagged": int(flag.sum()),
    }


def completed_game_changes(
    previous: pd.DataFrame, current: pd.DataFrame
) -> pd.DataFrame:
    """Games completed in either version whose result fields differ between versions."""
    fields = [
        f for f in REFRESH_FIELDS if f in previous.columns and f in current.columns
    ]
    merged = previous[["game_id", *fields]].merge(
        current[
            [
                "game_id",
                *fields,
                *([c for c in ("__capture_id",) if c in current.columns]),
            ]
        ],
        on="game_id",
        suffixes=("_prev", ""),
    )
    done = merged["completed"].fillna(False).astype(bool) | merged[
        "completed_prev"
    ].fillna(False).astype(bool)
    changed = pd.Series(False, index=merged.index)
    for field in fields:
        a, b = merged[f"{field}_prev"], merged[field]
        changed |= ~((a == b) | (a.isna() & b.isna()))
    out = merged[done & changed].reset_index(drop=True)
    out["previously_completed"] = out["completed_prev"].fillna(False).astype(bool)
    return out


def unpinned_refreshes(
    changes: pd.DataFrame, captures: pd.DataFrame
) -> dict[str, list[int]]:
    """Refreshed completed games whose capture is not pinned by id, hash, uri and time."""
    index = captures.set_index("capture_id") if len(captures) else captures
    problems: dict[str, list[int]] = {
        "no_capture_id": [],
        "not_in_catalog": [],
        "incomplete_pin": [],
    }
    for row in changes.to_dict("records"):
        cid = row.get("__capture_id")
        cid = None if cid is None or pd.isna(cid) else str(cid)
        game_id = int(row["game_id"])
        if cid is None:
            problems["no_capture_id"].append(game_id)
        elif cid not in index.index:
            problems["not_in_catalog"].append(game_id)
        elif index.loc[cid, list(CAPTURE_PIN_FIELDS)].isna().any():
            problems["incomplete_pin"].append(game_id)
    return {k: v for k, v in problems.items() if v}


def _counts(d: Mapping[str, Any]) -> dict[str, Any]:
    return {k: (len(v) if isinstance(v, list) else v) for k, v in d.items()}


@register_check(
    "silver.reconciliation_recorded",
    stage="silver",
    severity=WARN,
    description="Score-versus-box reconciliation is recorded and has no blocking conflicts",
)
def _reconciliation(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("source_reconciliation") is None:
        return skipped("source_reconciliation not provided")
    res = reconciliation_summary(ctx["source_reconciliation"])
    return Outcome(res["blocking"] == 0, observed=res, expected={"blocking": 0})


@register_check(
    "silver.score_stream_monotone",
    stage="silver",
    severity=WARN,
    description="Each team's running score never decreases in play order (regressions are counted)",
)
def _monotone(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("byplay") is None:
        return skipped("byplay not provided")
    res = score_stream_regressions(ctx["byplay"])
    return Outcome(res["regressed"] == 0, observed=res, expected={"regressed": 0})


@register_check(
    "silver.drive_numbering",
    stage="silver",
    severity=WARN,
    description="Drive numbers run 1..n without gaps in each game and are unique per offense",
)
def _drive_numbering(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("drives") is None:
        return skipped("drives not provided")
    res = drive_numbering_problems(ctx["drives"])
    return Outcome(
        not res["duplicate_keys"] and not res["gap_games"],
        observed=_counts(res),
        expected={"duplicate_keys": 0, "gap_games": 0},
        detail=f"gap games: {res['gap_games'][:10]}" if res["gap_games"] else "",
    )


@register_check(
    "silver.plays_and_drives_same_games",
    stage="silver",
    severity=WARN,
    description="Plays and drives cover the same games",
)
def _same_games(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("byplay") is None or ctx.get("drives") is None:
        return skipped("byplay/drives not provided")
    res = play_drive_game_coverage(ctx["byplay"], ctx["drives"])
    ok = not (res["plays_without_drives"] or res["drives_without_plays"])
    return Outcome(
        ok,
        observed=_counts(res),
        expected={"plays_without_drives": 0, "drives_without_plays": 0},
    )


@register_check(
    "silver.points_identity",
    stage="silver",
    severity=WARN,
    description="Drive points never exceed the final score for any team-game",
)
def _points_identity(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("drives") is None or ctx.get("games") is None:
        return skipped("drives/games not provided")
    res = points_identity(ctx["drives"], ctx["games"])
    return Outcome(
        not res["excess"],
        observed={
            "team_games": res["team_games"],
            "no_drive_points": res["no_drive_points"],
            "excess": len(res["excess"]),
        },
        expected={"excess": 0},
        detail=f"examples: {res['excess'][:3]}" if res["excess"] else "",
    )


@register_check(
    "silver.ppa_missing_flag",
    stage="silver",
    severity=WARN,
    description="Missing provider PPA is flagged and never stored as a numeric zero",
)
def _ppa_flag(ctx: Mapping[str, Any]) -> Outcome:
    if ctx.get("byplay") is None:
        return skipped("byplay not provided")
    res = ppa_flag_problems(ctx["byplay"])
    if not res["flag_present"]:
        return Outcome(
            False,
            observed=res,
            expected="ppa_missing column present",
            detail="Silver byplay has no ppa_missing flag (built before the flag existed)",
        )
    return Outcome(
        res["null_not_flagged"] == 0 and res["flagged_with_value"] == 0,
        observed=res,
        expected={"null_not_flagged": 0, "flagged_with_value": 0},
    )


@register_check(
    "silver.completed_game_refresh_pinned",
    stage="silver",
    severity=WARN,
    description="Completed games whose result changed between versions carry a pinned capture (gate 6)",
)
def _refresh_pinned(ctx: Mapping[str, Any]) -> Outcome:
    if (
        ctx.get("games") is None
        or ctx.get("games_previous") is None
        or ctx.get("capture_index") is None
    ):
        return skipped("games/games_previous/capture_index not provided")
    changes = completed_game_changes(ctx["games_previous"], ctx["games"])
    problems = unpinned_refreshes(changes, ctx["capture_index"])
    return Outcome(
        not problems,
        observed={
            "changed_completed_games": len(changes),
            "corrections": int(changes["previously_completed"].sum()),
            "new_completions": int((~changes["previously_completed"]).sum()),
            **{k: len(v) for k, v in problems.items()},
        },
        expected="every changed completed game cites a catalogued capture with sha, object sha, uri and time",
        detail=f"{ {k: v[:5] for k, v in problems.items()} }" if problems else "",
    )
