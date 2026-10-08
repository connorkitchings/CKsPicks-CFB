"""Seeding a week's schedule: only that week, provider names, never overwriting."""

from __future__ import annotations

import pytest

from scripts.pipeline.seed_week_schedule import SEED_SQL, schedule_rows

LOCK = {
    "games": {
        "columns": [
            "week",
            "game_id",
            "start_date",
            "home_team",
            "away_team",
            "home_points",
            "away_points",
        ],
        "rows": [
            [5, 1, "2026-10-03T16:00:00Z", "A", "B", 10, 3],
            [6, 2, "2026-10-10T16:00:00Z", "UTSA", "UConn", None, None],
            [6, 3, "2026-10-10T19:00:00Z", "San José State", "Hawai'i", None, None],
        ],
    }
}


def test_only_the_requested_week_is_seeded_with_provider_names_and_no_scores():
    rows = schedule_rows(LOCK, 6)
    assert [r["game_id"] for r in rows] == [2, 3]
    assert rows[0] == {
        "game_id": 2,
        "season": 2026,
        "week": 6,
        "start_date": "2026-10-10T16:00:00Z",
        "home_team": "UTSA",
        "away_team": "UConn",
    }
    assert rows[1]["home_team"] == "San José State"


def test_an_unknown_or_duplicated_week_is_refused():
    with pytest.raises(ValueError, match="no games for week 9"):
        schedule_rows(LOCK, 9)
    duplicated = {"games": {**LOCK["games"], "rows": [LOCK["games"]["rows"][1]] * 2}}
    with pytest.raises(ValueError, match="duplicates"):
        schedule_rows(duplicated, 6)


def test_the_insert_never_overwrites_an_existing_game():
    assert "ON CONFLICT (game_id) DO NOTHING" in SEED_SQL
    assert "predicted" not in SEED_SQL and "DO UPDATE" not in SEED_SQL
