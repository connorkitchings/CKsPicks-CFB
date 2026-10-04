"""Rule R1 candidate: monotone score envelope capped at the game final. Not serving.

This module only builds candidate inputs and compares candidate scoring ledgers with the
baseline for the Window 2 Step 5A sizing. Nothing here is wired into serving, ratings or
any publisher. The rule and the group definitions are frozen in
``docs/plans/2026-10-03/window2/5a-frozen-definitions.md``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import numpy as np
import pandas as pd

ORDER_COLUMNS = ["season", "game_id", "quarter", "drive_number", "play_number"]
EVENT_KEYS = ["game_id", "team", "source_event_id"]
COMPARE_FIELDS = [
    "score_increment",
    "scoring_category",
    "unit_category",
    "associated_possession_id",
    "conversion_for_event_id",
    "quality_reason",
]
CAUSE_PRECEDENCE = [
    "incomplete_stream",
    "restoration_gt8",
    "dip_restore",
    "final_cap",
    "conversion_reassignment",
    "category_possession_reassignment",
]


def apply_r1(
    byplay: pd.DataFrame, finals: Mapping[tuple[int, str], float]
) -> tuple[pd.DataFrame, set[tuple[int, str]]]:
    """Replace each team's running score with ``min(F, running max)`` in ledger order.

    ``finals`` maps ``(game_id, team)`` to the certified final score. Returns the
    rewritten frame and the team-games left unresolved because the envelope does not
    reach the final (they stay quarantined exactly as in the baseline).
    """
    frame = byplay.sort_values(ORDER_COLUMNS, kind="mergesort").copy()
    unresolved: set[tuple[int, str]] = set()
    for game_id, group in frame.groupby("game_id", sort=False):
        for team in set(group["offense"]) | set(group["defense"]):
            is_off = (group["offense"] == team).to_numpy()
            is_def = (group["defense"] == team).to_numpy()
            raw = np.where(
                is_off,
                group["offense_score"],
                np.where(is_def, group["defense_score"], np.nan),
            ).astype(float)
            valid = ~np.isnan(raw)
            if not valid.any():
                continue
            values = raw[valid]
            final = finals.get((int(game_id), team))
            if final is None:
                # No certified final: R1 cannot cap or test resolution, so the rows are
                # left exactly as the baseline sees them.
                continue
            envelope = np.minimum(np.maximum.accumulate(values), final)
            if values.max() < final:
                unresolved.add((int(game_id), team))
            full = raw.copy()
            full[valid] = envelope
            index = group.index.to_numpy()
            frame.loc[index[is_off], "offense_score"] = full[is_off]
            frame.loc[index[is_def], "defense_score"] = full[is_def]
    return frame, unresolved


def restoration_jumps(byplay: pd.DataFrame) -> set[tuple[int, str]]:
    """Team-games whose raw score rises by more than eight after an earlier decrease."""
    frame = byplay.sort_values(ORDER_COLUMNS, kind="mergesort")
    found: set[tuple[int, str]] = set()
    for game_id, group in frame.groupby("game_id", sort=False):
        for team in set(group["offense"]) | set(group["defense"]):
            score = np.where(
                group["offense"] == team,
                group["offense_score"],
                np.where(group["defense"] == team, group["defense_score"], np.nan),
            ).astype(float)
            score = score[~np.isnan(score)]
            seen_dip = False
            for step in np.diff(score):
                if step < 0:
                    seen_dip = True
                elif step > 8 and seen_dip:
                    found.add((int(game_id), team))
                    break
    return found


def _same(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a == b) | (a.isna() & b.isna())


def align_events(baseline: pd.DataFrame, candidate: pd.DataFrame) -> pd.DataFrame:
    """Outer-align two scoring ledgers on the event key and mark changed events."""
    base = baseline.reset_index(drop=True).assign(pos_base=lambda d: d.index)
    cand = candidate.reset_index(drop=True).assign(pos_cand=lambda d: d.index)
    merged = base.merge(
        cand, on=EVENT_KEYS, how="outer", suffixes=("_b", "_c"), indicator=True
    )
    changed = merged["_merge"] != "both"
    for field in COMPARE_FIELDS:
        changed = changed | ~_same(merged[f"{field}_b"], merged[f"{field}_c"])
    merged["changed"] = changed
    merged["season"] = merged["season_b"].fillna(merged["season_c"])
    merged["drive_number"] = merged["drive_number_b"].fillna(merged["drive_number_c"])
    merged["pos"] = merged["pos_base"].fillna(merged["pos_cand"])
    return merged


def _group_id(season: Any, game_id: Any, team: str, first_event: str) -> str:
    return hashlib.sha256(
        f"{int(season)}|{int(game_id)}|{team}|{first_event}".encode()
    ).hexdigest()[:16]


def changed_groups(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    *,
    restoration_team_games: set[tuple[int, str]] | frozenset = frozenset(),
    members_out: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """One row per allocation group (frozen definition), with channel, flags and cause.

    ``members_out``, when given, is filled with ``group_id -> [source_event_id, ...]`` for
    every event (baseline-only, candidate-only or both) the group contains.
    """
    merged = align_events(baseline, candidate).sort_values(
        ["game_id", "team", "drive_number", "pos"], kind="mergesort"
    )
    rows: list[dict[str, Any]] = []
    for (game_id, team), events in merged.groupby(["game_id", "team"], sort=False):
        events = events.reset_index(drop=True)
        # Regions: maximal runs of changed events with no unchanged event between them.
        region = (~events["changed"]).cumsum()
        parent: dict[int, int] = {}

        def find(x: int) -> int:
            while parent.setdefault(x, x) != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        changed_idx = events.index[events["changed"]]
        if len(changed_idx) == 0:
            continue
        for i in changed_idx:
            find(int(region[i]))
        # Merge regions linked by a conversion reference to an event in another region.
        event_region = {
            events.loc[i, "source_event_id"]: int(region[i]) for i in changed_idx
        }
        for i in changed_idx:
            for side in ("conversion_for_event_id_b", "conversion_for_event_id_c"):
                ref = events.loc[i, side]
                if isinstance(ref, str) and ref in event_region:
                    parent[find(int(region[i]))] = find(event_region[ref])
        buckets: dict[int, list[int]] = {}
        for i in changed_idx:
            buckets.setdefault(find(int(region[i])), []).append(i)
        for members in buckets.values():
            group = events.loc[sorted(members)]
            base_inc = group["score_increment_b"].fillna(0).sum()
            cand_inc = group["score_increment_c"].fillna(0).sum()
            net = float(cand_inc - base_inc)
            base_reason = group["quality_reason_b"]
            one_sided_unresolved = (
                group["scoring_category_b"].eq("unresolved")
                ^ group["scoring_category_c"].eq("unresolved")
            ) & ~base_reason.eq("exceeds_repaired_final")
            flags = {
                "incomplete_stream": bool(one_sided_unresolved.any()),
                "restoration_gt8": (int(game_id), team) in restoration_team_games,
                "dip_restore": bool(base_reason.eq("score_regression_rollback").any()),
                "final_cap": bool(base_reason.eq("exceeds_repaired_final").any()),
                "conversion_reassignment": not bool(
                    _same(
                        group["conversion_for_event_id_b"],
                        group["conversion_for_event_id_c"],
                    ).all()
                ),
                "category_possession_reassignment": bool(
                    (
                        ~_same(group["scoring_category_b"], group["scoring_category_c"])
                        | ~_same(group["unit_category_b"], group["unit_category_c"])
                        | ~_same(
                            group["associated_possession_id_b"],
                            group["associated_possession_id_c"],
                        )
                    ).any()
                ),
            }
            primary = next((c for c in CAUSE_PRECEDENCE if flags[c]), "other")
            first = str(group["source_event_id"].iloc[0])
            season = group["season"].iloc[0]
            group_id = _group_id(season, game_id, team, first)
            if members_out is not None:
                members_out[group_id] = [str(s) for s in group["source_event_id"]]
            rows.append(
                {
                    "group_id": group_id,
                    "season": int(season),
                    "game_id": int(game_id),
                    "team": team,
                    "events": len(group),
                    "drive_numbers": json.dumps(
                        sorted({int(d) for d in group["drive_number"].dropna()})
                    ),
                    "baseline_points": float(base_inc),
                    "candidate_points": float(cand_inc),
                    "net_points": net,
                    "channel": "points_recovery"
                    if net > 0
                    else "points_reduction"
                    if net < 0
                    else "attribution_only",
                    "primary_cause": primary,
                    **{f"flag_{k}": v for k, v in flags.items()},
                }
            )
    columns = [
        "group_id",
        "season",
        "game_id",
        "team",
        "events",
        "drive_numbers",
        "baseline_points",
        "candidate_points",
        "net_points",
        "channel",
        "primary_cause",
        *[f"flag_{c}" for c in CAUSE_PRECEDENCE],
    ]
    return pd.DataFrame(rows, columns=columns)


def summarize_groups(groups: pd.DataFrame) -> dict[str, Any]:
    """Counts by season, primary cause and channel, and points recovered."""
    if groups.empty:
        return {
            "groups": 0,
            "team_games": 0,
            "by_season": {},
            "by_cause": {},
            "by_channel": {},
            "points_recovered": 0.0,
        }
    return {
        "groups": len(groups),
        "team_games": int(groups[["game_id", "team"]].drop_duplicates().shape[0]),
        "by_season": {
            int(k): int(v) for k, v in groups.groupby("season").size().items()
        },
        "by_cause": {
            str(k): int(v) for k, v in groups.groupby("primary_cause").size().items()
        },
        "by_channel": {
            str(k): int(v) for k, v in groups.groupby("channel").size().items()
        },
        "points_recovered": float(
            groups.loc[groups["net_points"] > 0, "net_points"].sum()
        ),
    }
