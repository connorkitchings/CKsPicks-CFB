"""Window 2 Step 5C: per-group admission of the R1 candidate. Not serving.

Takes the 5A gate decisions (one status per changed allocation group) and the baseline and
candidate scoring ledgers and produces the *admitted* ledger: a corroborated group takes its
candidate allocation, every other changed group keeps exactly the baseline allocation. Fail
closed: no evidence means baseline, never exclusion and never new points. The independent
check lives in ``ratings/possession_verification.py`` and does not import this module.
"""

from __future__ import annotations

import json
from typing import Mapping

import pandas as pd

from cks_picks_cfb.ratings.score_envelope_r1 import EVENT_KEYS, align_events

ADMITTED = "admitted"
REVERTED_UNVERIFIED = "reverted_unverified"
REVERTED_CONTRADICTED = "reverted_contradicted"
RULE_VERSION = "r1_envelope_v1"
EVIDENCE_SOURCE = "cfbd_drives_5a"

# Frozen 5A statuses: only an explicit corroboration admits a change. A usable game whose
# drives support the baseline or match neither is contradicting evidence; everything else
# (unusable game, indistinguishable at drive level, no data) is simply unverified.
_CONTRADICTED = {"cfbd_supports_baseline", "cfbd_matches_neither"}


def decide(status: str) -> str:
    if status == "corroborated":
        return ADMITTED
    return REVERTED_CONTRADICTED if status in _CONTRADICTED else REVERTED_UNVERIFIED


def build_decisions(
    group_status: pd.DataFrame, members: Mapping[str, list[str]]
) -> pd.DataFrame:
    """One row per group: decision, evidence status and the event ids it covers."""
    frame = group_status[
        [
            "group_id",
            "season",
            "game_id",
            "team",
            "channel",
            "primary_cause",
            "net_points",
            "status",
        ]
    ].copy()
    frame["decision"] = frame["status"].map(decide)
    frame["evidence_source"] = EVIDENCE_SOURCE
    frame["event_ids"] = frame["group_id"].map(
        lambda g: json.dumps(sorted(set(members[g])))
    )
    return frame.sort_values("group_id", kind="mergesort").reset_index(drop=True)


def build_admitted_events(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    decisions: pd.DataFrame,
    members: Mapping[str, list[str]],
) -> pd.DataFrame:
    """Baseline-schema ledger plus ``allocation_group_id``, ``admission`` and ``evidence``."""
    merged = align_events(baseline, candidate)
    decision_by_group = dict(zip(decisions["group_id"], decisions["decision"]))
    group_of: dict[tuple[int, str, str], str] = {}
    info = decisions.set_index("group_id")[["game_id", "team"]].to_dict("index")
    for group_id, ids in members.items():
        game_id, team = int(info[group_id]["game_id"]), str(info[group_id]["team"])
        for event_id in ids:
            group_of[(game_id, team, event_id)] = group_id
    columns = [c for c in baseline.columns]
    rows = []
    for rec in merged.to_dict("records"):
        key = (int(rec["game_id"]), str(rec["team"]), str(rec["source_event_id"]))
        group_id = group_of.get(key)
        if not rec["changed"]:
            side = "b"
        else:
            if group_id is None:
                raise ValueError(f"changed event {key} belongs to no group")
            side = "c" if decision_by_group[group_id] == ADMITTED else "b"
        has_side = rec["_merge"] in (
            "both",
            "left_only" if side == "b" else "right_only",
        )
        if not has_side:
            continue  # removed by an admitted change, or added by a reverted one
        row = {
            c: rec[f"{c}_{side}"] if f"{c}_{side}" in rec else rec[c] for c in columns
        }
        for c in EVENT_KEYS:
            row[c] = rec[c]
        row["allocation_group_id"] = group_id
        row["admission"] = (
            "baseline_unchanged"
            if group_id is None or decision_by_group[group_id] != ADMITTED
            else "corroborated"
        )
        row["evidence_status"] = (
            None if group_id is None else decision_by_group[group_id]
        )
        rows.append(row)
    out = pd.DataFrame(rows)
    for column in ("season", "game_id", "drive_number", "score_increment"):
        out[column] = out[column].astype(baseline[column].dtype)
    return out.sort_values(
        ["game_id", "team", "source_event_id"], kind="mergesort"
    ).reset_index(drop=True)
