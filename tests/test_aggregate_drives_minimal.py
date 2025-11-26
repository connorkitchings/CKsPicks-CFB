# Unit test for aggregate_drives with a tiny synthetic dataset
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from features.core import aggregate_drives


def test_aggregate_drives_minimal():
    # Minimal plays with required columns
    plays = pd.DataFrame(
        [
            {
                "game_id": 1,
                "drive_number": 1,
                "offense": "A",
                "defense": "B",
                "yards_gained": 5,
                "play_duration": 10,
                "quarter": 1,
                "time_remaining_after": 800,
                "time_remaining_before": 810,
                "eckel": 1,
                "yards_to_goal": 60,
                "scoring": 0,
                "turnover": 0,
                "play_type": "Rush",
                "is_drive_play": 1,
                "play_number": 1,
            },
            {
                "game_id": 1,
                "drive_number": 1,
                "offense": "A",
                "defense": "B",
                "yards_gained": 7,
                "play_duration": 12,
                "quarter": 1,
                "time_remaining_after": 788,
                "time_remaining_before": 800,
                "eckel": 1,
                "yards_to_goal": 53,
                "scoring": 7,
                "turnover": 0,
                "play_type": "Pass",
                "is_drive_play": 1,
                "play_number": 2,
            },
        ]
    )

    drives = aggregate_drives(plays)
    assert len(drives) == 1
    row = drives.iloc[0]
    # drive_plays should sum is_drive_play
    assert row["drive_plays"] == 2
    # drive_yards should sum yards_gained
    assert row["drive_yards"] == 12
    # NOTE: drive_time column was removed in a previous refactoring
    # scoring opportunity derived from eckel
    assert row["had_scoring_opportunity"] == 1
    # points sum
    assert row["points"] == 7
