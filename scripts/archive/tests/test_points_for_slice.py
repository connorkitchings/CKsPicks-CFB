"""Regression checks for the points-for training slice."""

from __future__ import annotations

import csv
from pathlib import Path

SLICE_PATH = Path("outputs/prototypes/points_for_training_slice_2023_filtered.csv")
MIN_ROWS = 500
MIN_GAMES = 2.0


def test_points_for_slice_exists() -> None:
    assert SLICE_PATH.is_file(), f"Expected slice at {SLICE_PATH}"


def test_points_for_slice_rows_and_games() -> None:
    with SLICE_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) >= MIN_ROWS, f"Expected at least {MIN_ROWS} rows"

    for row in rows:
        assert row["home_points"] != "", (
            f"Missing home_points for game {row['game_id']}"
        )
        assert row["away_points"] != "", (
            f"Missing away_points for game {row['game_id']}"
        )
        home_games = float(row["home_games_played"])
        away_games = float(row["away_games_played"])
        assert home_games >= MIN_GAMES, (
            f"Home team below min games ({home_games}) for game {row['game_id']}"
        )
        assert away_games >= MIN_GAMES, (
            f"Away team below min games ({away_games}) for game {row['game_id']}"
        )
