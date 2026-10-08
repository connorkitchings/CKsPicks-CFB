"""The corrected-run loader reads exactly the published frames the successor builders need."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.rebuild import successor_sources as ss


class _Run:
    def __init__(self):
        self.requested: list[str] = []

    def frame(self, relative: str) -> pd.DataFrame:
        self.requested.append(relative)
        if relative == "eligibility/population_raw.parquet":
            return pd.DataFrame(
                {
                    "season": [2025, 2025],
                    "game_id": [1, 2],
                    "schedule_completed": [True, False],
                    "home_points": [10.0, None],
                    "away_points": [3.0, None],
                }
            )
        return pd.DataFrame({"path": [relative]})


@pytest.fixture
def run(monkeypatch):
    import cks_picks_cfb.data.data_first_possession_v1 as population

    monkeypatch.setattr(
        population, "build_population", lambda raw, scope: raw.assign(scope=scope)
    )
    return _Run()


def test_the_nine_cache_frames_come_from_the_named_published_objects(run):
    frames = ss.historical_frames(run)
    assert tuple(frames) == ss.HISTORICAL_FRAMES
    assert sorted(run.requested) == sorted(
        [
            "eligibility/population_raw.parquet",
            "ratings/observations.parquet",
            "ratings/terminal.parquet",
            "forecast/feature_frame.parquet",
            "ratings/snapshots.parquet",
            "ratings/priors.parquet",
            "ratings/rating_states.parquet",
        ]
    )
    assert frames["population"]["scope"].eq("historical").all()
    assert frames["v5_predictions"].empty


def test_outcomes_are_the_population_outcome_columns_with_completed_renamed(run):
    outcomes = ss.historical_frames(run)["outcomes"]
    assert list(outcomes.columns) == ss.OUTCOME_COLUMNS
    assert outcomes["completed"].tolist() == [True, False]


def test_the_cache_files_are_written_under_the_builders_names(run, tmp_path):
    rows = ss.write_historical_cache(run, tmp_path / "cache")
    assert set(rows) == set(ss.HISTORICAL_FRAMES)
    for name in ss.HISTORICAL_FRAMES:
        assert (tmp_path / "cache" / f"{name}.parquet").exists()
