"""The invariance comparison catches differences and ledgers them (contract 2026-10-09/01, Task 5)."""

import json

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.rebuild.invariance import (
    add_ordinal,
    cell_diff,
    ledger_rows,
    summarize,
)
from scripts.analysis.invariance_v2 import (
    EXPLANATION,
    canonical_locator,
    make_remap,
    remap_columns,
    split_representative_choices,
    with_game,
)

COLLISION = {7}


def frame(rows):
    return pd.DataFrame(rows, columns=["game_id", "team", "value", "note"])


def test_identical_frames_have_no_differences_and_nulls_compare_equal():
    a = frame([(1, "A", 1.0, None), (2, "B", np.nan, "x")])
    diff = cell_diff(a, a.copy(), keys=("game_id", "team"))
    assert diff.cells.empty and diff.only_left.empty and diff.only_right.empty
    assert diff.rows_compared == 2 and diff.cells_compared == 4


def test_a_changed_cell_and_one_sided_rows_are_reported_by_key():
    a = frame([(1, "A", 1.0, "x"), (2, "B", 2.0, "y"), (3, "C", 3.0, "z")])
    b = frame([(1, "A", 1.0, "x"), (2, "B", 2.5, "y"), (4, "D", 4.0, "w")])
    diff = cell_diff(a, b, keys=("game_id", "team"))
    assert diff.cells[["game_id", "column", "left", "right"]].values.tolist() == [
        [2, "value", 2.0, 2.5]
    ]
    assert diff.only_left["game_id"].tolist() == [3]
    assert diff.only_right["game_id"].tolist() == [4]


def test_floats_within_tolerance_are_equal():
    a, b = frame([(1, "A", 1.0, "x")]), frame([(1, "A", 1.0 + 1e-12, "x")])
    assert cell_diff(a, b, keys=("game_id", "team")).cells.empty


def test_duplicate_keys_are_refused_unless_numbered():
    dup = frame([(1, "A", 1.0, "x"), (1, "A", 2.0, "y")])
    with pytest.raises(ValueError, match="not unique"):
        cell_diff(dup, dup, keys=("game_id", "team"))
    numbered = add_ordinal(dup, ("game_id", "team"), ("value",))
    assert numbered["_ordinal"].tolist() == [0, 1]
    assert cell_diff(
        numbered, numbered, keys=("game_id", "team", "_ordinal")
    ).cells.empty


def test_summary_separates_collision_games_from_the_rest():
    a = frame([(7, "A", 1.0, "x"), (2, "B", 2.0, "y")])
    b = frame([(7, "A", 9.0, "x"), (2, "B", 3.0, "y")])
    diff = cell_diff(a, b, keys=("game_id", "team"))
    out = summarize(diff, COLLISION, left_rows=2, right_rows=2)
    assert out["cells_changed"] == 2
    assert out["outside_collision"] == {
        "games": [2],
        "cells": 1,
        "rows_only_v1": 0,
        "rows_only_v2": 0,
    }
    clean = summarize(
        cell_diff(a.iloc[:1], b.iloc[:1], keys=("game_id", "team")),
        COLLISION,
        left_rows=1,
        right_rows=1,
    )
    assert clean["outside_collision"]["games"] == []


def test_ledger_rows_name_values_evidence_and_flag_anything_outside():
    a = frame([(7, "A", 1.0, "x"), (2, "B", 2.0, "y"), (7, "C", 3.0, "z")])
    b = frame([(7, "A", 9.0, "x"), (2, "B", 3.0, "y")])
    diff = cell_diff(a, b, keys=("game_id", "team"))
    rows = ledger_rows(
        diff,
        table="t",
        season=2025,
        collision_games=COLLISION,
        evidence_of=lambda g: f"cluster in {g}",
        disposition_of=lambda change, table, column, a, b: change,
        descendants="downstream",
        explanation=EXPLANATION,
    )
    by_key = {(r["game_id"], r["change"]): r for r in rows}
    changed = by_key[(7, "cell_changed")]
    assert (changed["v1_value"], changed["v2_value"]) == (1.0, 9.0)
    assert (
        changed["source_evidence"] == "cluster in 7" and changed["affected_descendants"]
    )
    assert by_key[(7, "row_only_in_v1")]["v1_value"] == "present"
    outside = by_key[(2, "cell_changed")]
    assert outside["disposition"] == "UNEXPLAINED" and outside["source_evidence"] == ""
    assert json.loads(changed["key"]) == {"game_id": 7, "team": "A"}


def test_legacy_ids_inside_text_and_json_are_rewritten_everywhere():
    event = "2025:7:19:4"
    tokens = {
        event: "2025:7:-22488",
        "ab" * 8: "cd" * 8,
        "1" * 20: "2" * 20,
        "cfbd_drives:" + "e" * 64: "cfbd_drives:" + "f" * 64,
    }
    remap = make_remap(tokens)
    assert remap(event) == "2025:7:-22488"
    locator = json.dumps({"event_ids": [event], "other": "2025:7:1:1"})
    assert json.loads(remap(locator)) == {
        "event_ids": ["2025:7:-22488"],
        "other": "2025:7:1:1",
    }
    assert remap("ab" * 8) == "cd" * 8 and remap("1" * 20) == "2" * 20
    assert remap("cfbd_drives:" + "e" * 64) == "cfbd_drives:" + "f" * 64
    assert remap(None) is None and remap(3) == 3
    frame_ = pd.DataFrame({"x": [event], "y": [event]})
    assert remap_columns(frame_, ("x",), remap)["x"].tolist() == ["2025:7:-22488"]
    assert remap_columns(frame_, ("x",), remap)["y"].tolist() == [event]


def test_tables_not_keyed_by_game_get_a_game_from_a_team_map():
    a = pd.DataFrame({"team": ["A", "B"], "metric": ["m", "m"], "v": [1.0, 2.0]})
    b = a.assign(v=[1.0, 5.0])
    diff = with_game(
        cell_diff(a, b, keys=("team", "metric")),
        lambda f: f["team"].map({"A": 7}).fillna(0),
    )
    assert diff.cells["game_id"].tolist() == [0]
    rows = ledger_rows(
        diff,
        table="t",
        season=1,
        collision_games=COLLISION,
        evidence_of=lambda g: "",
        disposition_of=lambda c, t, col, a, b: c,
        descendants="d",
        explanation=EXPLANATION,
    )
    assert rows[0]["disposition"] == "UNEXPLAINED"  # team B has no collision game


def test_locator_id_lists_compare_as_sets():
    a = json.dumps({"event_ids": ["b", "a"], "game_id": 1, "x": "s"})
    b = json.dumps({"x": "s", "game_id": 1, "event_ids": ["a", "b"]})
    assert canonical_locator(a) == canonical_locator(b)
    c = json.dumps({"event_ids": ["a", "c"], "game_id": 1, "x": "s"})
    assert canonical_locator(a) != canonical_locator(c)
    assert (
        canonical_locator(None) is None and canonical_locator("not json") == "not json"
    )


EVIDENCE_KEYS = ("game_id", "evidence_id")


def evidence_row(rep, **extra):
    row = {
        "game_id": 1,
        "evidence_id": "e",
        "team": "T",
        "allocation_group_id": "g",
        "source_event_id": rep,
        "possession_id": "p",
        "conversion_for_event_id": None,
        "unit_category": "offense",
        "quarter": 2,
        "points": 3,
    }
    row.update(extra)
    return pd.DataFrame([row])


def ledger_of(*events):
    return pd.DataFrame(
        [
            {
                "game_id": 1,
                "team": "T",
                "source_event_id": event,
                "allocation_group_id": "g",
                "associated_possession_id": possession,
                "conversion_for_event_id": None,
                "unit_category": "offense",
                "quarter": quarter,
                "play_number": play,
            }
            for event, quarter, play, possession in events
        ]
    )


def split(left, right, ledger):
    return split_representative_choices(
        cell_diff(left, right, keys=EVIDENCE_KEYS), left, right, ledger
    )


def test_a_tie_break_swap_of_the_representative_is_set_aside_and_listed():
    ledger = ledger_of(("a", 2, 5, "p"), ("b", 2, 5, "p"))
    kept, moved = split(evidence_row("b"), evidence_row("a"), ledger)
    assert kept.cells.empty and len(moved) == 1
    assert (moved[0]["v1_representative"], moved[0]["v2_representative"]) == ("b", "a")
    assert moved[0]["columns"] == ["source_event_id"]


def test_a_swap_between_plays_that_do_not_tie_is_a_real_difference():
    ledger = ledger_of(("a", 2, 5, "p"), ("b", 2, 6, "p"))
    kept, moved = split(evidence_row("b"), evidence_row("a"), ledger)
    assert set(kept.cells["column"]) == {"source_event_id"} and not moved


def test_points_never_ride_along_with_a_representative_swap():
    ledger = ledger_of(("a", 2, 5, "p"), ("b", 2, 5, "p"))
    kept, moved = split(evidence_row("b"), evidence_row("a", points=7), ledger)
    assert set(kept.cells["column"]) == {"source_event_id", "points"} and not moved


def test_a_derived_value_that_disagrees_with_the_ledger_is_not_set_aside():
    ledger = ledger_of(("a", 2, 5, "p"), ("b", 2, 5, "p"))
    right = evidence_row("a", possession_id="elsewhere")
    kept, moved = split(evidence_row("b"), right, ledger)
    assert set(kept.cells["column"]) == {"source_event_id", "possession_id"}
    assert not moved


def test_a_representative_missing_from_the_ledger_is_not_set_aside():
    ledger = ledger_of(("a", 2, 5, "p"))
    kept, moved = split(evidence_row("b"), evidence_row("a"), ledger)
    assert len(kept.cells) == 1 and not moved


def test_another_group_is_not_a_representative_swap():
    ledger = ledger_of(("a", 2, 5, "p"), ("b", 2, 5, "p"))
    kept, moved = split(
        evidence_row("b", allocation_group_id="h"), evidence_row("a"), ledger
    )
    assert "allocation_group_id" in set(kept.cells["column"]) and not moved
