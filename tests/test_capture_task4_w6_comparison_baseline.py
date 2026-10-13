"""Task 4 comparison baseline: fingerprints, capture diffs and the additions declaration.

In-memory rows only; no database.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.pipeline import capture_task4_w6_comparison_baseline as baseline

COLUMNS = ("component_id", "v5_snapshot_id", "season", "as_of_week", "rating_mean")
KEYS = ("component_id",)
TABLE = "team_rating_components"


def component(cid: str, run: str, week: str, mean: str = "0.1") -> dict[str, str]:
    return {
        "component_id": cid,
        "v5_snapshot_id": f"{run}:snap",
        "season": "2026",
        "as_of_week": week,
        "rating_mean": mean,
    }


ROWS = [
    component("c1", "ratings-v1", "5"),
    component("c2", "ratings-v1", "5"),
    component("c3", "corrected-w6live-r1", "6"),
]


def capture_of(rows) -> dict:
    return {
        "tables": {TABLE: baseline.fingerprint(TABLE, rows, COLUMNS, KEYS)},
        "publications": {"run": [{"rating_manifest_sha256": "a" * 64}]},
    }


def test_fingerprint_groups_by_season_week_and_rating_run():
    groups = baseline.fingerprint(TABLE, ROWS, COLUMNS, KEYS)

    assert [(g["week"], g["provenance"], g["rows"]) for g in groups] == [
        ("5", "ratings-v1", 2),
        ("6", "corrected-w6live-r1", 1),
    ]


def test_fingerprint_ignores_row_order():
    assert baseline.fingerprint(TABLE, ROWS, COLUMNS, KEYS) == baseline.fingerprint(
        TABLE, list(reversed(ROWS)), COLUMNS, KEYS
    )


def test_identical_captures_have_no_difference():
    assert baseline.diff_captures(capture_of(ROWS), capture_of(list(ROWS))) == []


def test_changed_value_is_reported_for_its_group_only():
    changed = [*ROWS[:2], component("c3", "corrected-w6live-r1", "6", mean="0.2")]

    problems = baseline.diff_captures(capture_of(ROWS), capture_of(changed))

    assert problems == [
        "team_rating_components ('2026', '6', 'corrected-w6live-r1'): "
        "content changed (rows 1 -> 1)"
    ]


def test_added_and_removed_groups_are_reported():
    moved = [*ROWS[:2], component("c3", "corrected-w6live-r1", "7")]

    problems = baseline.diff_captures(capture_of(ROWS), capture_of(moved))

    assert len(problems) == 2
    assert any("group removed" in p for p in problems)
    assert any("group added" in p for p in problems)


def test_changed_publication_metadata_is_reported():
    current = capture_of(ROWS)
    current["publications"]["run"][0]["rating_manifest_sha256"] = "b" * 64

    assert baseline.diff_captures(capture_of(ROWS), current) == [
        "publication metadata of the rating runs changed"
    ]


DECLARATION = {"column": "component_id", "count": 1, "values": ["c4"]}


def check(built, declaration=DECLARATION):
    return baseline.check_additions(TABLE, ROWS, built, KEYS, declaration)


def test_declared_additions_pass():
    assert check([*ROWS, component("c4", "r", "6")]) == []


def test_published_row_missing_from_build_fails_even_with_additions():
    problems = check([*ROWS[:2], component("c4", "r", "6")])

    assert problems == [f"{TABLE}: 1 published rows missing from the build"]


def test_extra_row_outside_declaration_fails():
    problems = check([*ROWS, component("c4", "r", "6"), component("c5", "r", "6")])

    assert problems == [f"{TABLE}: rows added outside the declaration: ['c5']"]


def test_declared_addition_not_built_fails():
    assert check(ROWS) == [f"{TABLE}: declared additions not built: ['c4']"]


def test_published_row_cannot_be_declared_an_addition():
    declaration = {"column": "component_id", "count": 1, "values": ["c3"]}

    problems = check(ROWS, declaration)

    assert f"{TABLE}: declared values already published: ['c3']" in problems


def test_declaration_count_must_match_its_values():
    declaration = {**DECLARATION, "count": 2}

    problems = check([*ROWS, component("c4", "r", "6")], declaration)

    assert problems == [f"{TABLE}: declaration lists 1 values, count says 2"]


def test_undeclared_table_allows_no_additions():
    problems = check([*ROWS, component("c4", "r", "6")], None)

    assert problems == [f"{TABLE}: 1 rows added with no declaration"]


def test_measurement_declaration_comes_from_both_lock_extensions():
    lock = {
        "extends": {
            "added_post_week": 6,
            "newly_final_game_ids": list(range(100, 158)),
            "previous_extension": {
                "added_post_week": 5,
                "newly_final_game_ids": list(range(200, 256)),
            },
        }
    }

    declaration = baseline.measurement_declaration(lock, "f" * 64)

    assert declaration["count"] == 114
    assert declaration["values"][:2] == [100, 101]


def test_measurement_declaration_refuses_wrong_counts():
    lock = {"extends": {"added_post_week": 6, "newly_final_game_ids": [1, 2]}}

    with pytest.raises(baseline.BaselineError, match="expected"):
        baseline.measurement_declaration(lock, "f" * 64)


def test_component_declaration_requires_exactly_276_unique_ids(tmp_path: Path):
    short = tmp_path / "ids.json"
    short.write_text(json.dumps([f"c{i}" for i in range(275)]))
    duplicated = tmp_path / "dup.json"
    duplicated.write_text(json.dumps(["c1"] * 276))

    with pytest.raises(baseline.BaselineError, match="expected 276"):
        baseline.component_declaration(short)
    with pytest.raises(baseline.BaselineError, match="unique"):
        baseline.component_declaration(duplicated)


def test_committed_placeholder_declares_the_lock_games():
    path = Path("conf/rebuild/task4_w6_comparison_baseline_v1.json")
    doc = json.loads(path.read_text())
    lock_raw = baseline.LOCK.read_bytes()
    expected = baseline.measurement_declaration(
        json.loads(lock_raw), hashlib.sha256(lock_raw).hexdigest()
    )

    assert doc["schema_version"] == baseline.SCHEMA
    assert doc["expected_additions"]["team_game_measurements"] == expected
    assert doc["expected_additions"]["team_rating_components"]["count"] == 276
