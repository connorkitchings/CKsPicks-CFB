"""Re-key the pinned Window-2 5C admission decisions to provider-keyed event ids.

The CFBD corroboration behind the decisions compares points per ``(team, drive_number)``
against hash-pinned drive bundles and never looks at a play id. The decisions therefore stay
valid when their legacy ``season:game:drive:play`` event ids are replaced by the provider ids
of the same plays (``season:game_id:source_play_id``). This module performs that mapping and
checks it against ledgers recomputed from ``byplay_v2``; it never reads CFBD and decides
nothing new except that a group which exists only in v2 fails closed (``reverted_unverified``).

Not serving. The independent ledger verifier does not import this module.
"""

from __future__ import annotations

import json
import math
from collections.abc import Collection, Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.ratings.score_envelope_r1 import _group_id

NEW_GROUP_STATUS = "no_evidence_v2_group"
GROUP_FIELDS = ("channel", "primary_cause")


class RekeyError(ValueError):
    """A pinned decision cannot be mapped without guessing."""


def recover_first_event(
    season: Any, game_id: Any, team: str, group_id: str, members: Collection[str]
) -> str:
    """The event whose id the pinned group id was hashed from.

    ``event_ids`` in the decisions file is string-sorted, so the group's first event (in ledger
    order) is recovered by hashing each member until exactly one reproduces ``group_id``.
    """
    matches = [m for m in members if _group_id(season, game_id, team, m) == group_id]
    if len(matches) != 1:
        raise RekeyError(
            f"group {group_id}: {len(matches)} members reproduce the group id"
        )
    return matches[0]


def legacy_event_map(plays: pd.DataFrame, season: int) -> dict[str, str]:
    """Legacy ``season:game:drive:play`` id -> v2 id of the play that legacy build kept.

    The legacy by-play kept the first row at each displayed sequence **in the Silver file
    order**, so ``plays`` must be the unsorted normalized Silver plays. A sequence shared by
    distinct provider plays therefore maps to the file-first play; the other play has no legacy
    event.
    """
    first = plays.drop_duplicates(
        ["game_id", "drive_number", "play_number"], keep="first"
    )
    return {
        f"{int(season)}:{int(g)}:{int(d)}:{int(p)}": f"{int(season)}:{int(g)}:{int(i)}"
        for g, d, p, i in zip(
            first["game_id"],
            first["drive_number"],
            first["play_number"],
            first["play_id"],
        )
    }


def rekey_decisions(
    decisions: pd.DataFrame, event_map: Mapping[str, str]
) -> pd.DataFrame:
    """The pinned decisions with provider-keyed ``event_ids`` and a re-derived ``group_id``.

    The v1 id is kept as ``group_id_v1`` so the mapping stays auditable.
    """
    rows = []
    for row in decisions.to_dict("records"):
        members = json.loads(row["event_ids"])
        try:
            mapped = sorted({event_map[m] for m in members})
            first = event_map[
                recover_first_event(
                    row["season"], row["game_id"], row["team"], row["group_id"], members
                )
            ]
        except KeyError as error:
            raise RekeyError(
                f"group {row['group_id']}: unmapped event {error}"
            ) from error
        rows.append(
            {
                **row,
                "group_id_v1": row["group_id"],
                "group_id": _group_id(
                    row["season"], row["game_id"], row["team"], first
                ),
                "event_ids": json.dumps(mapped),
            }
        )
    out = pd.DataFrame(rows)
    columns = list(decisions.columns)
    columns.insert(columns.index("group_id") + 1, "group_id_v1")
    return out[columns].sort_values("group_id", kind="mergesort").reset_index(drop=True)


def rekey_status(status: pd.DataFrame, group_ids: Mapping[str, str]) -> pd.DataFrame:
    """The pinned corroboration status keyed by the v2 group id (v1 id kept alongside)."""
    out = status.assign(group_id_v1=status["group_id"])
    out["group_id"] = out["group_id_v1"].map(group_ids)
    if out["group_id"].isna().any():
        raise RekeyError("a status row has no re-keyed decision")
    columns = list(status.columns)
    columns.insert(columns.index("group_id") + 1, "group_id_v1")
    return out[columns].sort_values("group_id", kind="mergesort").reset_index(drop=True)


def canonical_equal(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, Any]:
    """Null-safe, order-independent frame equality that names the differing columns."""
    columns = sorted(set(left.columns) & set(right.columns))
    a, b = left[columns].astype(object), right[columns].astype(object)
    a, b = a.mask(a.isna(), "<NA>"), b.mask(b.isna(), "<NA>")
    a = a.sort_values(columns, kind="mergesort").reset_index(drop=True)
    b = b.sort_values(columns, kind="mergesort").reset_index(drop=True)
    if len(a) != len(b):
        return {"equal": False, "rows": [len(a), len(b)], "columns": []}
    bad = [c for c in columns if (a[c] != b[c]).any()]
    return {"equal": not bad, "rows": [len(a), len(b)], "columns": bad}


def admitted_equal_outside(
    v2_admitted: pd.DataFrame,
    v1_admitted: pd.DataFrame,
    event_map: Mapping[str, str],
    group_map: Mapping[str, str],
    collision_games: Collection[int],
) -> dict[str, Any]:
    """The v1 admitted ledger, mapped to v2 ids, against the v2 one, outside collision games.

    Event ids, the ids a row refers to (possession and conversion references) and the
    allocation group are mapped; the v2-only identity columns and the evidence label are
    dropped. Games in ``collision_games`` are excluded because they legitimately differ.
    """
    mapped = v1_admitted.copy()
    for column in (
        "source_event_id",
        "associated_possession_id",
        "conversion_for_event_id",
    ):
        mapped[column] = mapped[column].map(
            lambda v: event_map.get(v, v) if isinstance(v, str) else v
        )
    mapped["allocation_group_id"] = mapped["allocation_group_id"].map(
        lambda v: group_map.get(v, v) if isinstance(v, str) else v
    )
    skip = {int(g) for g in collision_games}
    left = mapped[~mapped["game_id"].isin(skip)].drop(
        columns=["evidence_status"], errors="ignore"
    )
    right = v2_admitted[~v2_admitted["game_id"].isin(skip)].drop(
        columns=["drive_id", "source_play_id", "evidence_status"], errors="ignore"
    )
    return canonical_equal(left, right)


def _close(a: float, b: float) -> bool:
    return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)


def reconcile_groups(
    pinned: pd.DataFrame,
    rekeyed: pd.DataFrame,
    recomputed: pd.DataFrame,
    members_v2: Mapping[str, list[str]],
    collision_games: Collection[int],
) -> dict[str, Any]:
    """Check the re-keyed decisions against groups recomputed from ``byplay_v2`` ledgers.

    Outside the collision games every re-keyed group must equal a recomputed group (same
    members, points, channel and cause). Inside them a difference is allowed and reported, and a
    group that exists only in v2 is added with status ``no_evidence_v2_group`` so it fails
    closed. Returns ``problems``, the differences, the final v2 status rows and counts.
    """
    collision = {int(g) for g in collision_games}
    problems: list[str] = []
    if (
        rekeyed["group_id"].duplicated().any()
        or rekeyed["group_id_v1"].duplicated().any()
    ):
        problems.append("group id mapping is not a bijection")
    if len(rekeyed) != len(pinned):
        problems.append("re-keyed decision count differs from the pinned count")
    for column in ("decision", "season", "primary_cause"):
        before = pinned.groupby(column).size().to_dict()
        after = rekeyed.groupby(column).size().to_dict()
        if before != after:
            problems.append(f"counts by {column} changed under the mapping")

    pinned_by = rekeyed.set_index("group_id")
    new_by = recomputed.set_index("group_id")
    matched = sorted(set(pinned_by.index) & set(new_by.index))
    only_pinned = sorted(set(pinned_by.index) - set(new_by.index))
    only_new = sorted(set(new_by.index) - set(pinned_by.index))
    differing: list[dict[str, Any]] = []
    for group in matched:
        old, new = pinned_by.loc[group], new_by.loc[group]
        reasons = []
        if sorted(json.loads(old["event_ids"])) != sorted(set(members_v2[group])):
            reasons.append("members")
        if not _close(old["net_points"], new["net_points"]):
            reasons.append("net_points")
        reasons += [f for f in GROUP_FIELDS if old[f] != new[f]]
        if reasons:
            differing.append(
                {"group_id": group, "game_id": int(old["game_id"]), "fields": reasons}
            )

    def outside(items: list[Any], game_of: Any) -> list[Any]:
        return [i for i in items if int(game_of(i)) not in collision]

    for label, bad in (
        (
            "re-keyed groups not recomputed",
            outside(only_pinned, lambda g: pinned_by.loc[g, "game_id"]),
        ),
        (
            "recomputed groups not re-keyed",
            outside(only_new, lambda g: new_by.loc[g, "game_id"]),
        ),
        ("groups that differ", outside(differing, lambda d: d["game_id"])),
    ):
        if bad:
            problems.append(f"{len(bad)} {label} outside the collision games")

    kept = rekeyed[rekeyed["group_id"].isin(matched)]
    added = recomputed[recomputed["group_id"].isin(only_new)]
    final = pd.concat(
        [
            kept[
                [
                    "group_id",
                    "season",
                    "game_id",
                    "team",
                    "channel",
                    "primary_cause",
                    "net_points",
                ]
            ],
            added[
                [
                    "group_id",
                    "season",
                    "game_id",
                    "team",
                    "channel",
                    "primary_cause",
                    "net_points",
                ]
            ],
        ],
        ignore_index=True,
    )
    status_of = dict(zip(rekeyed["group_id"], rekeyed["status"]))
    final["status"] = [status_of.get(g, NEW_GROUP_STATUS) for g in final["group_id"]]
    return {
        "problems": problems,
        "matched": len(matched),
        "pinned_only": [
            {"group_id": g, "game_id": int(pinned_by.loc[g, "game_id"])}
            for g in only_pinned
        ],
        "recomputed_only": [
            {"group_id": g, "game_id": int(new_by.loc[g, "game_id"])} for g in only_new
        ],
        "differing": differing,
        "final_status": final.sort_values("group_id", kind="mergesort").reset_index(
            drop=True
        ),
    }
