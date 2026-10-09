"""Convert the existing possession and scoring-event frames to the v1 Gold contracts.

``possession_measurements.build_possession_ledger`` emits ``associated_possession_id`` as the
source *play* id (``season:game:drive:play``), unresolved markers with a zero increment, and no
quarter, raw score or envelope fields. The v1 contracts need a stable possession id, null
increments for unresolved markers, and the score context. These converters add them without
changing any allocation: the baseline ledger converts to ``admission = baseline_unchanged``.

Admission of candidate allocations (R1) is Step 5C; the schema and the conversion here are the
contract it will fill.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from cks_picks_cfb.data.play_order import order_plays
from cks_picks_cfb.metrics.contracts import canonical_json_text, possession_id_for

BASELINE_RULE = "baseline_v1"


class LedgerConversionError(ValueError):
    """An event could not be tied to its play; conversion never guesses."""


def source_event_id(
    season: Any, game_id: Any, drive_number: Any, play_number: Any
) -> str:
    """The ledger's play id format (see ``possession_measurements._source_id``)."""
    return f"{int(season)}:{int(game_id)}:{int(drive_number)}:{int(play_number)}"


def possessions_to_v1(
    possessions: pd.DataFrame,
    drives: pd.DataFrame,
    *,
    source_versions: Mapping[str, str],
) -> pd.DataFrame:
    """Add the stable id, start field position and scoring-opportunity flag.

    ``drives`` is the Silver drives dataset (``had_scoring_opportunity``,
    ``start_yards_to_goal``) keyed by game, drive number and offense. A possession with no
    drive row keeps null for both fields rather than a default. ``possession_eligible`` is
    narrowed to regulation possessions without a quality reason; a start field position
    outside 0-100 becomes null.
    """
    keys = ["season", "game_id", "drive_number", "offense"]
    if "season" not in drives:
        # Legacy single-season inputs predate the Gold converter. Never infer
        # a season for a multi-season frame.
        seasons = possessions.season.unique()
        if len(seasons) != 1:
            raise LedgerConversionError(
                "drive season is required for multi-season input"
            )
        drives = drives.assign(season=int(seasons[0]))
    if drives.duplicated(keys).any() or possessions.duplicated(keys).any():
        raise LedgerConversionError("duplicate possession or drive identity")
    keep = drives[
        [
            "season",
            "game_id",
            "drive_number",
            "offense",
            "start_yards_to_goal",
            "had_scoring_opportunity",
        ]
    ]
    merged = possessions.merge(
        keep,
        on=keys,
        how="left",
        validate="one_to_one",
    )
    opportunity = pd.to_numeric(merged["had_scoring_opportunity"], errors="coerce")
    merged["scoring_opportunity"] = opportunity.map({1.0: True, 0.0: False}).astype(
        object
    )
    merged.loc[opportunity.isna(), "scoring_opportunity"] = None
    # Gold ``possession_eligible`` means measurement-eligible: the legacy flag only says the
    # possession had eligible plays. A possession in an unknown period or carrying a quality
    # reason is never eligible (the metric builder already requires all three), and the
    # legacy detail stays in the play counts and ``quality_reason``.
    merged["possession_eligible"] = (
        merged["possession_eligible"].fillna(False).astype(bool)
        & merged["period_class"].eq("regulation")
        & merged["quality_reason"].isna()
    )
    # An impossible field position is unknown, never clipped or guessed; the Silver drive
    # keeps the provider value.
    yards = pd.to_numeric(merged["start_yards_to_goal"], errors="coerce")
    merged["start_yards_to_goal"] = yards.where(yards.between(0, 100))
    merged["possession_id"] = [
        possession_id_for(s, g, d, o)
        for s, g, d, o in zip(
            merged["season"],
            merged["game_id"],
            merged["drive_number"],
            merged["offense"],
        )
    ]
    merged["source_versions"] = canonical_json_text(
        dict(sorted(source_versions.items()))
    )
    columns = [
        "season",
        "week",
        "game_id",
        "drive_number",
        "possession_id",
        "offense",
        "defense",
        "period_class",
        "eligible_play_count",
        "ineligible_play_count",
        "mixed_eligibility",
        "possession_eligible",
        "scoring_opportunity",
        "start_yards_to_goal",
        "source_play_ids",
        "quality_reason",
        "timing_class",
        "source_versions",
    ]
    return merged[columns]


def scoring_events_to_v1(
    events: pd.DataFrame,
    plays: pd.DataFrame,
    *,
    finals: Mapping[tuple[int, str], float],
    source_versions: Mapping[str, str],
    rule_version: str = BASELINE_RULE,
    groups: Mapping[tuple[int, str, str], str] | None = None,
    admitted_evidence: Mapping[str, tuple[str, ...]] | None = None,
    admitted_rule_version: str | None = None,
    populate_envelopes: bool = False,
) -> pd.DataFrame:
    """Baseline events to ``football_scoring_ledger_v1`` with ``admission = baseline_unchanged``.

    ``plays`` is the ledger's input byplay frame (canonical team names) and supplies each
    event's quarter, the play's offense and the raw running scores. ``groups`` optionally maps
    ``(game_id, team, source_event_id)`` to an allocation group id; other events get
    ``unchanged:<game_id>:<team>``. ``admitted_evidence`` maps an *admitted* group id to its
    sorted evidence ids: those groups' events become ``admission = corroborated`` under
    ``admitted_rule_version`` (the events passed in must already be the admitted allocation).
    """
    frame = plays.copy()
    frame["_id"] = [
        source_event_id(s, g, d, p)
        for s, g, d, p in zip(
            frame["season"],
            frame["game_id"],
            frame["drive_number"],
            frame["play_number"],
        )
    ]
    if frame["_id"].duplicated().any():
        raise LedgerConversionError("duplicate source play identity")
    if events.duplicated(["season", "game_id", "source_event_id", "team"]).any():
        raise LedgerConversionError("duplicate scoring event identity")
    by_id = frame.set_index("_id")
    missing = sorted(set(events["source_event_id"]) - set(by_id.index))
    if missing:
        raise LedgerConversionError(
            f"{len(missing)} events have no matching play, e.g. {missing[:3]}"
        )
    # Each team's running raw score on every play, in stream order, to give before and after values.
    ordered = order_plays(frame)
    long = pd.concat(
        [
            ordered[["game_id", "_id", "offense", "offense_score"]].set_axis(
                ["game_id", "_id", "team", "score"], axis=1
            ),
            ordered[["game_id", "_id", "defense", "defense_score"]].set_axis(
                ["game_id", "_id", "team", "score"], axis=1
            ),
        ]
    ).sort_values(["game_id", "team"], kind="mergesort")
    long = long.assign(order=long.groupby(["game_id", "team"]).cumcount())
    # keep stream order inside each team-game: ``ordered`` fixed it, so re-sort by position
    position = {pid: i for i, pid in enumerate(ordered["_id"])}
    long["pos"] = long["_id"].map(position)
    long = long.sort_values(["game_id", "team", "pos"], kind="mergesort").reset_index(
        drop=True
    )
    long["before"] = long.groupby(["game_id", "team"])["score"].shift(1)
    long.loc[long.groupby(["game_id", "team"]).cumcount().eq(0), "before"] = 0.0
    long["envelope_after"] = None
    long["envelope_before"] = None
    if populate_envelopes:
        for (game_id, team), rows in long.groupby(["game_id", "team"], sort=False):
            final = finals.get((int(game_id), team))
            if final is None:
                continue
            running = 0
            for idx in rows.index:
                raw = long.loc[idx, "score"]
                if pd.isna(raw) or not np.isfinite(raw) or raw < 0 or raw != int(raw):
                    # Invalid streams cannot produce asserted envelope context.
                    running = None
                    continue
                if running is not None:
                    long.loc[idx, "envelope_before"] = running
                    running = min(int(final), max(running, int(raw)))
                    long.loc[idx, "envelope_after"] = running
    lookup = long.drop_duplicates(["game_id", "team", "_id"]).set_index(
        ["game_id", "team", "_id"]
    )

    rows: list[dict[str, Any]] = []
    versions = canonical_json_text(dict(sorted(source_versions.items())))
    for e in events.to_dict("records"):
        play = by_id.loc[e["source_event_id"]]
        key = (int(e["game_id"]), e["team"], e["source_event_id"])
        score = lookup.loc[key] if key in lookup.index else None
        unresolved = e["scoring_category"] == "unresolved"
        possession = None
        if e["associated_possession_id"] is not None and not pd.isna(
            e["associated_possession_id"]
        ):
            # The baseline stores the play id; the possession is the play's offense's drive.
            linked = e["associated_possession_id"]
            if linked not in by_id.index:
                raise LedgerConversionError("associated possession play is missing")
            linked_play = by_id.loc[linked]
            if (linked_play["season"], linked_play["game_id"]) != (
                e["season"],
                e["game_id"],
            ):
                raise LedgerConversionError(
                    "associated possession crosses game identity"
                )
            possession = possession_id_for(
                e["season"],
                e["game_id"],
                int(linked_play["drive_number"]),
                linked_play["offense"],
            )
        group = (groups or {}).get(key) or f"unchanged:{int(e['game_id'])}:{e['team']}"
        final = finals.get((int(e["game_id"]), e["team"]))
        evidence = (admitted_evidence or {}).get(group)
        disposition = e.get(
            "admission", "corroborated" if evidence else "baseline_unchanged"
        )
        if disposition not in {
            "baseline_unchanged",
            "corroborated",
            "reverted_unverified",
            "reverted_contradicted",
        }:
            raise LedgerConversionError("unknown or candidate admission")
        if (disposition == "corroborated") != bool(evidence):
            raise LedgerConversionError(
                "admission disagrees with corroborating evidence"
            )
        rows.append(
            {
                "season": int(e["season"]),
                "game_id": int(e["game_id"]),
                "source_event_id": e["source_event_id"],
                "team": e["team"],
                "drive_number": int(e["drive_number"]),
                "quarter": int(play["quarter"]),
                "play_number": int(play["play_number"]),
                "period_class": e["period_class"],
                "score_increment": None if unresolved else int(e["score_increment"]),
                "scoring_category": e["scoring_category"],
                "unit_category": e["unit_category"],
                "associated_possession_id": possession,
                "conversion_for_event_id": None
                if pd.isna(e["conversion_for_event_id"])
                else e["conversion_for_event_id"],
                "raw_score_before": None if score is None else float(score["before"]),
                "raw_score_after": None if score is None else float(score["score"]),
                "envelope_before": score["envelope_before"]
                if populate_envelopes and evidence and score is not None
                else None,
                "envelope_after": score["envelope_after"]
                if populate_envelopes and evidence and score is not None
                else None,
                "certified_final": None if final is None else int(final),
                "quality_reason": None
                if pd.isna(e["quality_reason"])
                else e["quality_reason"],
                "rule_version": admitted_rule_version
                if evidence and admitted_rule_version
                else rule_version,
                "allocation_group_id": group,
                "admission": disposition,
                "evidence_ids": canonical_json_text(sorted(evidence or ())),
                "timing_class": e["timing_class"],
                "source_versions": versions,
            }
        )
    out = pd.DataFrame(rows)
    for column in ("score_increment", "certified_final"):
        out[column] = out[column].astype("Int64")
    return out.replace({np.nan: None})
