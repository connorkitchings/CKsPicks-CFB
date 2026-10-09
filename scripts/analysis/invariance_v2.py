#!/usr/bin/env python3
"""Task 5 invariance proof: v1 against v2 over the pinned corpus, with a discrepancy ledger.

``season --season N --output-dir D`` builds both sides from pinned parents (see
``invariance_frames_v2``), compares every table by key, writes a per-season summary and the
discrepancy rows. ``assemble --output-dir D --evidence-dir E`` writes the checksummed
evidence: ``invariance-proof-v2.json`` and ``discrepancy-ledger-v2.csv``. The proof fails if any
difference lies outside the four collision games.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from cks_picks_cfb.rebuild.invariance import (
    CellDiff,
    add_ordinal,
    cell_diff,
    ledger_rows,
    summarize,
)

SCHEMA = "invariance_proof_v2"
COLLISION_GAMES = frozenset({401310699, 401756916, 401761632, 401762831})

DESCENDANTS = {
    "byplay": "drives; team_game; source_reconciliation; possession ledger; admitted scoring ledger; observations; team_game_metrics; season_level_features",
    "drives": "net punt yards and drive aggregates in team_game; possession ledger; team_game_metrics",
    "team_game": "team_season aggregates and opponent-adjusted team statistics; team_game_metrics inputs",
    "source_reconciliation": "coverage flags of team_game_metrics; game usability",
    "possessions": "admitted scoring ledger; observations; team_game_metrics; ratings built from observations",
    "scoring_ledger": "evidence; observations; team_game_metrics; ratings built from observations",
    "evidence": "scoring attribution evidence only",
    "observations": "possession-based ratings (ratings_parity inputs) and their forecasts",
    "team_game_metrics": "season_level_features; published team_season_stats",
    "season_features": "published season-level features and matchup features for later weeks",
}
LEDGER_COLUMNS = (
    "season",
    "game_id",
    "table",
    "key",
    "change",
    "column",
    "v1_value",
    "v2_value",
    "source_evidence",
    "disposition",
    "affected_descendants",
    "explanation",
)
EXPLANATION = {
    "cell_changed": "value follows from a distinct provider play that the legacy sequence key dropped",
    "row_only_in_v1": "legacy row keyed to a sequence or drive number that v2 splits across distinct provider ids",
    "row_only_in_v2": "distinct provider play, drive or event that the legacy sequence key dropped",
}
TOKENS = re.compile(
    r"cfbd_drives:[0-9a-f]{64}|\b\d{4}:\d+:-?\d+:\d+\b|\b[0-9a-f]{20}\b|\b[0-9a-f]{16}\b"
)
ID_COLUMNS = {
    "possessions": ("possession_id", "source_play_ids"),
    "scoring_ledger": (
        "source_event_id",
        "associated_possession_id",
        "conversion_for_event_id",
        "allocation_group_id",
        "evidence_ids",
    ),
    "evidence": (
        "evidence_id",
        "allocation_group_id",
        "source_event_id",
        "possession_id",
        "conversion_for_event_id",
        "source_locator",
    ),
}


def make_remap(tokens: Mapping[str, str]) -> Callable[[Any], Any]:
    """Rewrite every legacy id inside a value to its v2 counterpart (others untouched)."""

    def remap(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        return TOKENS.sub(lambda m: tokens.get(m.group(0), m.group(0)), value)

    return remap


def canonical_locator(value: Any) -> Any:
    """An evidence locator with its id lists sorted.

    The lists are sorted by id string, so the same set of plays is listed in a different
    order once the ids change vocabulary; the sets are what must agree.
    """
    if not isinstance(value, str):
        return value
    try:
        parsed = json.loads(value)
    except ValueError:
        return value
    if isinstance(parsed, dict):
        for key, item in parsed.items():
            if isinstance(item, list) and all(isinstance(i, str) for i in item):
                parsed[key] = sorted(item)
    return json.dumps(parsed, sort_keys=True)


def remap_columns(
    frame: pd.DataFrame, columns: tuple[str, ...], remap: Callable[[Any], Any]
) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column in out.columns:
            out[column] = out[column].map(remap)
    return out


def with_game(diff: CellDiff, game_of: Callable[[pd.DataFrame], pd.Series]) -> CellDiff:
    """Attach a ``game_id`` to a diff of a table that is not keyed by game (0 = none)."""

    def add(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame.assign(game_id=pd.Series(dtype="int64"))
        return frame.assign(game_id=game_of(frame).astype("int64"))

    return replace(
        diff,
        only_left=add(diff.only_left),
        only_right=add(diff.only_right),
        cells=add(diff.cells),
    )


def compare_silver(
    v1: Mapping[str, Any],
    v2: Mapping[str, Any],
    plays: pd.DataFrame,
    attach_ids: Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame],
) -> dict[str, CellDiff]:
    """The four Silver tables, keyed so unchanged games line up exactly."""
    diffs: dict[str, CellDiff] = {}

    left = attach_ids(v1["byplay"], plays)
    diffs["byplay"] = cell_diff(
        left,
        v2["byplay"],
        keys=("game_id", "source_play_id"),
        columns=[c for c in left.columns if c not in ("drive_id", "source_play_id")],
    )

    def drives(frame: pd.DataFrame) -> pd.DataFrame:
        return add_ordinal(
            frame,
            ("game_id", "offense", "defense", "drive_number"),
            ("drive_start_period", "drive_plays"),
        )

    diffs["drives"] = cell_diff(
        drives(v1["drives"]),
        drives(v2["drives"]),
        keys=("game_id", "offense", "defense", "drive_number", "_ordinal"),
        columns=[c for c in v1["drives"].columns if c != "drive_id"],
    )
    diffs["team_game"] = cell_diff(
        v1["team_game"], v2["team_game"], keys=("game_id", "team")
    )
    diffs["source_reconciliation"] = cell_diff(
        v1["source_reconciliation"], v2["source_reconciliation"], keys=("game_id",)
    )
    return diffs


# Evidence columns that ``build_evidence`` copies from the group's representative event (the
# group's event that is first by ``(quarter, play_number)``; ties break on sorted event id, which
# changes with the id vocabulary). ``points`` is deliberately absent: it is the group's net
# points, independent of the representative, so a points difference is always a real difference.
REPRESENTATIVE_COLUMNS = frozenset(
    {
        "source_event_id",
        "possession_id",
        "conversion_for_event_id",
        "quarter",
        "unit_category",
    }
)
_LEDGER_COLUMN = {
    "source_event_id": "source_event_id",
    "possession_id": "associated_possession_id",
    "conversion_for_event_id": "conversion_for_event_id",
    "quarter": "quarter",
    "unit_category": "unit_category",
}


def _same_value(a: Any, b: Any) -> bool:
    if pd.isna(a) and pd.isna(b):
        return True
    return bool(a == b)


def split_representative_choices(
    diff: CellDiff,
    left: pd.DataFrame,
    right: pd.DataFrame,
    ledger: pd.DataFrame,
) -> tuple[CellDiff, list[dict[str, Any]]]:
    """Set aside evidence rows that differ only because a tie chose another representative.

    ``build_evidence`` describes an allocation group through its first event by
    ``(quarter, play_number)``, breaking ties on the sorted event id. When ids change vocabulary
    the same tie can pick another member. A row is set aside only if all of this holds, and each
    set-aside row is listed:

    * every changed column is one the representative supplies (never ``points``);
    * both representatives are events of the same group in the v2 ledger;
    * the two representatives tie on ``(quarter, play_number)`` in that ledger, so the swap is
      a tie-break and not a different first play;
    * on each side, every representative-derived value equals the v2 ledger row of that side's
      representative (the left side is already id-mapped).
    """
    if diff.cells.empty:
        return diff, []
    by_event = ledger.set_index(["game_id", "team", "source_event_id"])
    if by_event.index.duplicated().any():
        raise ValueError("v2 ledger is not unique on (game_id, team, source_event_id)")
    keys = list(diff.keys)
    by_row = diff.cells.groupby(keys)["column"].agg(set)
    left_idx = left.set_index(keys)
    right_idx = right.set_index(keys)
    moved: list[dict[str, Any]] = []
    keep = pd.Series(True, index=diff.cells.index)
    for key, columns in by_row.items():
        if not columns <= REPRESENTATIVE_COLUMNS:
            continue
        parts = key if isinstance(key, tuple) else (key,)
        named = dict(zip(keys, parts, strict=True))
        a, b = left_idx.loc[key], right_idx.loc[key]
        group = b["allocation_group_id"]
        if a["allocation_group_id"] != group:
            continue
        rows = []
        for evidence_row in (a, b):
            index = (
                int(named["game_id"]),
                evidence_row["team"],
                evidence_row["source_event_id"],
            )
            if index not in by_event.index:
                break
            event = by_event.loc[index]
            if event["allocation_group_id"] != group:
                break
            if not all(
                _same_value(evidence_row[column], event[_LEDGER_COLUMN[column]])
                for column in REPRESENTATIVE_COLUMNS
                if column != "source_event_id"
            ):
                break
            rows.append(event)
        else:
            tie = (rows[0]["quarter"], rows[0]["play_number"]) == (
                rows[1]["quarter"],
                rows[1]["play_number"],
            )
            if not tie:
                continue
            mask = pd.Series(True, index=diff.cells.index)
            for name, value in named.items():
                mask &= diff.cells[name] == value
            keep &= ~mask
            moved.append(
                {
                    **{name: _json_safe(value) for name, value in named.items()},
                    "group": group,
                    "v1_representative": a["source_event_id"],
                    "v2_representative": b["source_event_id"],
                    "columns": sorted(columns),
                }
            )
    return replace(diff, cells=diff.cells[keep].reset_index(drop=True)), moved


def _json_safe(value: Any) -> Any:
    return value.item() if hasattr(value, "item") else value


def compare_side(
    sides: Mapping[str, Mapping[str, Any]],
    plays: pd.DataFrame,
    event_map: Mapping[str, str],
    group_map: Mapping[str, str],
    attach_ids: Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame],
) -> tuple[dict[str, CellDiff], list[dict[str, Any]]]:
    """Every table's v1-against-v2 cell diff, keyed so unchanged games line up exactly."""
    v1, v2 = sides["v1"], sides["v2"]
    diffs = compare_silver(v1, v2, plays, attach_ids)

    # Possession ids: map by (game, offense, displayed drive number, ordinal).
    def poss(frame: pd.DataFrame) -> pd.DataFrame:
        return add_ordinal(
            frame, ("game_id", "offense", "drive_number"), ("period_class",)
        )

    p1, p2 = poss(v1["possessions"]), poss(v2["possessions"])
    pair = p1[
        ["game_id", "offense", "drive_number", "_ordinal", "possession_id"]
    ].merge(
        p2[["game_id", "offense", "drive_number", "_ordinal", "possession_id"]],
        on=["game_id", "offense", "drive_number", "_ordinal"],
        suffixes=("_1", "_2"),
    )
    tokens = dict(event_map) | dict(group_map)
    tokens |= dict(zip(pair["possession_id_1"], pair["possession_id_2"], strict=True))
    ev1, ev2 = v1["evidence"], v2["evidence"]
    group_tokens = dict(group_map)
    mapped_group = ev1["allocation_group_id"].map(lambda g: group_tokens.get(g, g))
    evid = ev1.assign(allocation_group_id=mapped_group)[
        ["allocation_group_id", "evidence_id"]
    ].merge(
        ev2[["allocation_group_id", "evidence_id"]],
        on="allocation_group_id",
        suffixes=("_1", "_2"),
    )
    tokens |= dict(zip(evid["evidence_id_1"], evid["evidence_id_2"], strict=True))
    remap = make_remap(tokens)

    diffs["possessions"] = cell_diff(
        remap_columns(p1, ID_COLUMNS["possessions"], remap),
        p2,
        keys=("game_id", "offense", "drive_number", "_ordinal"),
        columns=[c for c in v1["possessions"].columns if c != "drive_id"],
    )
    ledger1 = remap_columns(v1["scoring_ledger"], ID_COLUMNS["scoring_ledger"], remap)
    diffs["scoring_ledger"] = cell_diff(
        ledger1,
        v2["scoring_ledger"],
        keys=("game_id", "team", "source_event_id"),
        columns=[c for c in v1["scoring_ledger"].columns if c != "source_event_id"],
    )
    left_evidence = remap_columns(ev1, ID_COLUMNS["evidence"], remap)
    left_evidence["source_locator"] = left_evidence["source_locator"].map(
        canonical_locator
    )
    diffs["evidence"] = cell_diff(
        left_evidence,
        ev2.assign(source_locator=ev2["source_locator"].map(canonical_locator)),
        keys=("game_id", "evidence_id"),
    )
    right_evidence = ev2.assign(
        source_locator=ev2["source_locator"].map(canonical_locator)
    )
    diffs["evidence"], swaps = split_representative_choices(
        diffs["evidence"], left_evidence, right_evidence, v2["scoring_ledger"]
    )
    diffs["observations"] = cell_diff(
        v1["observations"],
        v2["observations"],
        keys=("game_id", "team", "measurement_id", "unit_role"),
    )
    diffs["team_game_metrics"] = cell_diff(
        v1["team_game_metrics"],
        v2["team_game_metrics"],
        keys=("game_id", "team", "role", "metric"),
    )
    diffs["season_features"] = cell_diff(
        v1["season_features"],
        v2["season_features"],
        keys=("team", "role", "metric", "population"),
    )
    return diffs, swaps


def attach_legacy_ids(byplay: pd.DataFrame, plays: pd.DataFrame) -> pd.DataFrame:
    from cks_picks_cfb.rebuild.silver import attach_legacy_source_ids

    return attach_legacy_source_ids(byplay, plays)


def clusters_by_game(plays: pd.DataFrame, games: set[int]) -> dict[int, str]:
    """The provider plays that share a displayed sequence, per collision game (evidence text)."""
    out: dict[int, str] = {}
    seq = ["game_id", "drive_number", "play_number"]
    ties = plays[plays.duplicated(seq, keep=False) & plays["game_id"].isin(games)]
    for game, rows in ties.groupby("game_id"):
        parts = []
        for (drive, play), group in rows.groupby(["drive_number", "play_number"]):
            ids = ",".join(str(i) for i in group["play_id"].tolist())
            parts.append(f"drive {int(drive)} play {int(play)}: provider plays {ids}")
        out[int(game)] = "; ".join(parts)
    return out


def compare_2026(built: Mapping[str, Any]) -> dict[str, CellDiff]:
    """2026: the Silver tables plus the baseline possessions, events and observations."""
    v1, v2 = built["v1"], built["v2"]
    diffs = compare_silver(v1, v2, built["plays"], attach_legacy_ids)

    def poss(frame: pd.DataFrame) -> pd.DataFrame:
        return add_ordinal(
            frame, ("game_id", "offense", "drive_number"), ("period_class",)
        )

    p1, p2 = poss(v1["possessions"]), poss(v2["possessions"])
    # Baseline events name their associated possession by event id, so one map covers all ids.
    remap = make_remap(dict(built["event_map"]))
    diffs["possessions"] = cell_diff(
        remap_columns(p1, ID_COLUMNS["possessions"], remap),
        p2,
        keys=("game_id", "offense", "drive_number", "_ordinal"),
        columns=[c for c in v1["possessions"].columns if c != "drive_id"],
    )
    diffs["scoring_events"] = cell_diff(
        remap_columns(
            v1["scoring_events"],
            ("source_event_id", "associated_possession_id", "conversion_for_event_id"),
            remap,
        ),
        v2["scoring_events"],
        keys=("game_id", "team", "source_event_id"),
        columns=[
            c
            for c in v1["scoring_events"].columns
            if c not in ("source_event_id", "drive_id")
        ],
    )
    diffs["observations"] = cell_diff(
        v1["observations"],
        v2["observations"],
        keys=("game_id", "team", "measurement_id", "unit_role"),
    )
    return diffs


def run_2026(
    pin_file: Path, label: str, output_dir: Path
) -> dict[str, Any]:  # pragma: no cover
    from scripts.analysis.invariance_frames_v2 import build_2026

    built = build_2026(pin_file)
    diffs = compare_2026(built)
    tables: dict[str, Any] = {}
    ledger: list[dict[str, Any]] = []
    for table, diff in diffs.items():
        name = "scoring_events" if table == "scoring_events" else table
        tables[table] = summarize(
            diff,
            (),
            left_rows=int(len(built["v1"][name])),
            right_rows=int(len(built["v2"][name])),
        )
        ledger.extend(
            ledger_rows(
                diff,
                table=table,
                season=2026,
                collision_games=(),
                evidence_of=lambda g: "",
                disposition_of=lambda c, t, col, a, b: c,
                descendants="",
                explanation=EXPLANATION,
            )
        )
    out = output_dir / f"season=2026-{label}"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(ledger, columns=list(LEDGER_COLUMNS)).to_csv(
        out / "ledger.csv", index=False
    )
    summary = {
        "season": 2026,
        "label": label,
        "pins": str(pin_file),
        "collision_games": [],
        "tables": tables,
        "outside_collision": {
            t: v["outside_collision"]
            for t, v in tables.items()
            if any(
                v["outside_collision"][k]
                for k in ("cells", "rows_only_v1", "rows_only_v2")
            )
        },
        "ledger_rows": len(ledger),
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n"
    )
    return summary


def run_season(season: int, output_dir: Path) -> dict[str, Any]:  # pragma: no cover
    from scripts.analysis.invariance_frames_v2 import build_season

    built = build_season(season)
    plays = built["plays"]
    population = built["population"]
    collisions = set(COLLISION_GAMES) & {int(g) for g in plays["game_id"].unique()}
    diffs, swaps = compare_side(
        built,
        plays,
        built["event_map"],
        built["group_map"],
        attach_legacy_ids,
    )
    games = population.set_index("game_id")
    team_game_of: dict[str, int] = {}
    for game in sorted(collisions):
        if game in games.index:
            for team in (games.loc[game, "home_team"], games.loc[game, "away_team"]):
                team_game_of.setdefault(team, game)
    diffs["season_features"] = with_game(
        diffs["season_features"],
        lambda f: f["team"].map(team_game_of).fillna(0),
    )
    clusters = clusters_by_game(plays, collisions)
    decisions = built["v2"]["decisions"]

    def evidence_of(game: int) -> str:
        touched = decisions[decisions["game_id"] == game]
        status = (
            f"; admission decisions in this game: "
            f"{touched['decision'].value_counts().to_dict()}"
            if not touched.empty
            else ""
        )
        return (clusters.get(game, "no sequence collision in this game") + status)[:900]

    def disposition_of(
        change: str, table: str, column: str, left: Any, right: Any
    ) -> str:
        relabel = (
            table == "scoring_ledger"
            and change == "cell_changed"
            and (
                (
                    column == "admission"
                    and left == "reverted_unverified"
                    and right == "baseline_unchanged"
                )
                or (
                    column == "allocation_group_id"
                    and str(right).startswith("unchanged:")
                )
            )
        )
        if relabel:
            return "relabelled_pinned_group_without_v2_counterpart"
        if change == "row_only_in_v2" and table == "byplay":
            return "corrected_restored_provider_play"
        if change == "cell_changed":
            return "corrected_downstream_value"
        return "rekeyed_or_split_row"

    def descendants(table: str, game: int) -> str:
        if game in games.index:
            row = games.loc[game]
            scope = (
                f"; teams {row['home_team']} and {row['away_team']}, week {int(row['week'])}: "
                f"every as-of-week aggregate from week {int(row['week'])} on"
            )
        else:
            scope = ""
        return DESCENDANTS[table] + scope

    ledger: list[dict[str, Any]] = []
    tables: dict[str, Any] = {}
    sides = built
    sizes = {
        "byplay": ("byplay",),
        "drives": ("drives",),
        "team_game": ("team_game",),
        "source_reconciliation": ("source_reconciliation",),
        "possessions": ("possessions",),
        "scoring_ledger": ("scoring_ledger",),
        "evidence": ("evidence",),
        "observations": ("observations",),
        "team_game_metrics": ("team_game_metrics",),
        "season_features": ("season_features",),
    }
    for table, diff in diffs.items():
        name = sizes[table][0]
        tables[table] = summarize(
            diff,
            COLLISION_GAMES,
            left_rows=int(len(sides["v1"][name])),
            right_rows=int(len(sides["v2"][name])),
        )
        rows = ledger_rows(
            diff,
            table=table,
            season=season,
            collision_games=COLLISION_GAMES,
            evidence_of=evidence_of,
            disposition_of=disposition_of,
            descendants=DESCENDANTS[table],
            explanation=EXPLANATION,
        )
        for row in rows:
            if row["affected_descendants"]:
                row["affected_descendants"] = descendants(table, row["game_id"])
        ledger.extend(rows)
    out = output_dir / f"season={season}"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(ledger, columns=list(LEDGER_COLUMNS)).to_csv(
        out / "ledger.csv", index=False
    )
    summary = {
        "season": season,
        "collision_games": sorted(collisions),
        "tables": tables,
        "outside_collision": {
            t: v["outside_collision"]
            for t, v in tables.items()
            if any(
                v["outside_collision"][k]
                for k in ("cells", "rows_only_v1", "rows_only_v2")
            )
        },
        "ledger_rows": len(ledger),
        "evidence_representative_choices": swaps,
        "dedup_accounting": built["dedup_accounting"],
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n"
    )
    return summary


def _read_ledger(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, keep_default_na=False)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=list(LEDGER_COLUMNS))


def assemble(output_dir: Path, evidence_dir: Path) -> dict[str, Any]:
    seasons = sorted(
        p for p in output_dir.glob("season=*") if (p / "summary.json").exists()
    )
    summaries = [json.loads((p / "summary.json").read_text()) for p in seasons]
    frames = [_read_ledger(p / "ledger.csv") for p in seasons]
    frames = [f for f in frames if not f.empty]
    ledger = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not ledger.empty:
        ledger = ledger.sort_values(
            ["season", "game_id", "table", "key", "column", "change"], kind="mergesort"
        ).reset_index(drop=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(evidence_dir / "discrepancy-ledger-v2.csv", index=False)
    unexplained = (
        int((ledger["disposition"] == "UNEXPLAINED").sum()) if len(ledger) else 0
    )
    outside = {
        s["season"]: s["outside_collision"] for s in summaries if s["outside_collision"]
    }
    by_table: dict[str, dict[str, int]] = {}
    for s in summaries:
        for table, v in s["tables"].items():
            row = by_table.setdefault(
                table,
                {
                    "rows_compared": 0,
                    "cells_compared": 0,
                    "cells_changed": 0,
                    "rows_only_v1": 0,
                    "rows_only_v2": 0,
                },
            )
            for k in row:
                row[k] += int(v[k])
    report = {
        "schema_version": SCHEMA,
        "contract": "docs/plans/2026-10-09/01-byplay-v2-play-identity.md#task-5",
        "seasons": sorted({s["season"] for s in summaries}),
        "pinned_2026_sets": [s["pins"] for s in summaries if "pins" in s],
        "collision_games": sorted(COLLISION_GAMES),
        "per_season": {
            (f"{s['season']}-{s['label']}" if "label" in s else str(s["season"])): s[
                "tables"
            ]
            for s in summaries
        },
        "totals_by_table": by_table,
        "outside_collision": {str(k): v for k, v in outside.items()},
        "dedup_accounting": {
            str(s["season"]): s["dedup_accounting"]
            for s in summaries
            if s.get("dedup_accounting", {}).get("removed_by_historical_dedup")
        },
        "evidence_representative_choices": {
            "note": (
                "Evidence rows whose allocation group is the same but whose representative "
                "event differs: the representative is the group's lexicographically first "
                "event id, which changes with the id vocabulary. Both representatives are "
                "members of the same group in the v2 ledger."
            ),
            "count": sum(
                len(s.get("evidence_representative_choices", [])) for s in summaries
            ),
            "outside_collision_count": sum(
                1
                for s in summaries
                for row in s.get("evidence_representative_choices", [])
                if int(row["game_id"]) not in COLLISION_GAMES
            ),
            "rows": [
                {"season": s["season"], **row}
                for s in summaries
                for row in s.get("evidence_representative_choices", [])
            ],
        },
        "ledger": {
            "rows": int(len(ledger)),
            "unexplained_rows": unexplained,
            "sha256": hashlib.sha256(
                (evidence_dir / "discrepancy-ledger-v2.csv").read_bytes()
            ).hexdigest(),
        },
        "passed": not outside and unexplained == 0,
    }
    (evidence_dir / "invariance-proof-v2.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    return report


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    one = sub.add_parser("season")
    one.add_argument("--season", type=int, required=True)
    one.add_argument("--output-dir", type=Path, required=True)
    live = sub.add_parser("season2026")
    live.add_argument("--pins", type=Path, required=True)
    live.add_argument("--label", required=True)
    live.add_argument("--output-dir", type=Path, required=True)
    many = sub.add_parser("assemble")
    many.add_argument("--output-dir", type=Path, required=True)
    many.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "season2026":
        print(
            json.dumps(
                run_2026(args.pins, args.label, args.output_dir), indent=2, default=str
            )
        )
    elif args.mode == "season":
        print(
            json.dumps(run_season(args.season, args.output_dir), indent=2, default=str)
        )
    else:
        report = assemble(args.output_dir, args.evidence_dir)
        print(
            json.dumps(
                {k: report[k] for k in ("passed", "ledger", "outside_collision")},
                indent=2,
            )
        )
        if not report["passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
