import os
from pathlib import Path

import pytest

from analysis.unadjusted import (
    build_leaderboard,
    load_running_season_snapshot,
    scatter_plot,
)
from utils.base import Partition
from utils.local_storage import LocalStorage

pd = pytest.importorskip("pandas")

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
plt = pytest.importorskip("matplotlib.pyplot")


def _prepare_minimal_data(tmp_path, *, year: int = 2024) -> None:
    raw_root = Path(str(tmp_path)) / "raw"
    processed_root = Path(str(tmp_path)) / "processed"
    os.makedirs(raw_root, exist_ok=True)
    os.makedirs(processed_root, exist_ok=True)

    raw_storage = LocalStorage(
        data_root=str(tmp_path), file_format="csv", data_type="raw"
    )
    processed_storage = LocalStorage(
        data_root=str(tmp_path), file_format="csv", data_type="processed"
    )

    teams = [
        {"school": "Team A", "classification": "fbs", "year": year},
        {"school": "Team B", "classification": "fbs", "year": year},
        {"school": "Team C", "classification": "fcs", "year": year},
    ]
    raw_storage.write("teams", teams, Partition({"year": year}))

    team_game_records = [
        # Week 1: FBS vs FBS matchup
        {
            "season": year,
            "week": 1,
            "game_id": 1,
            "team": "Team A",
            "off_ypp": 7.0,
            "def_ypp": 4.0,
        },
        {
            "season": year,
            "week": 1,
            "game_id": 1,
            "team": "Team B",
            "off_ypp": 6.0,
            "def_ypp": 5.0,
        },
        # Week 2: Team A vs FCS (should be excluded)
        {
            "season": year,
            "week": 2,
            "game_id": 2,
            "team": "Team A",
            "off_ypp": 9.0,
            "def_ypp": 2.0,
        },
        {
            "season": year,
            "week": 2,
            "game_id": 2,
            "team": "Team C",
            "off_ypp": 3.0,
            "def_ypp": 8.0,
        },
        # Week 3: Postseason FBS vs FBS (should be excluded)
        {
            "season": year,
            "week": 3,
            "game_id": 3,
            "team": "Team A",
            "off_ypp": 5.0,
            "def_ypp": 6.0,
        },
        {
            "season": year,
            "week": 3,
            "game_id": 3,
            "team": "Team B",
            "off_ypp": 4.0,
            "def_ypp": 7.0,
        },
    ]
    processed_storage.write("team_game", team_game_records, Partition({"year": year}))

    games_records = [
        {
            "id": 1,
            "season": year,
            "season_type": "regular",
            "start_date": f"{year}-09-01T18:00:00-04:00",
            "home_team": "Team A",
            "away_team": "Team B",
            "home_classification": "fbs",
            "away_classification": "fbs",
        },
        {
            "id": 2,
            "season": year,
            "season_type": "regular",
            "start_date": f"{year}-10-01T18:00:00-04:00",
            "home_team": "Team A",
            "away_team": "Team C",
            "home_classification": "fbs",
            "away_classification": "fcs",
        },
        {
            "id": 3,
            "season": year,
            "season_type": "regular",
            "start_date": f"{year}-11-01T18:00:00-04:00",
            "home_team": "Team A",
            "away_team": "Team B",
            "home_classification": "fbs",
            "away_classification": "fbs",
        },
    ]
    raw_storage.write("games", games_records, Partition({"year": year}))


def test_load_running_season_snapshot_latest(tmp_path):
    _prepare_minimal_data(tmp_path)

    snapshot, meta = load_running_season_snapshot(2024, data_root=str(tmp_path))
    assert meta.year == 2024
    assert meta.before_week == 4
    assert set(snapshot["team"]) == {"Team A", "Team B"}
    assert snapshot.loc[snapshot["team"] == "Team A", "games_played"].iloc[0] == 2


def test_load_running_season_snapshot_specific_week(tmp_path):
    _prepare_minimal_data(tmp_path)

    snapshot, meta = load_running_season_snapshot(
        2024, data_root=str(tmp_path), before_week=2
    )
    assert meta.before_week == 2
    assert set(snapshot["team"]) == {"Team A", "Team B"}
    assert snapshot.loc[snapshot["team"] == "Team A", "off_ypp"].iloc[
        0
    ] == pytest.approx(7.0)


def test_build_leaderboard_orders_by_side():
    snapshot = pd.DataFrame(
        {
            "team": ["A", "B", "C"],
            "games_played": [6, 6, 6],
            "off_ypp": [7.0, 6.5, 6.0],
            "def_ypp": [5.5, 4.0, 4.5],
        }
    )
    offense_board = build_leaderboard(snapshot, "ypp", side="offense", limit=2)
    assert offense_board.iloc[0]["team"] == "A"
    assert offense_board.iloc[1]["team"] == "B"

    defense_board = build_leaderboard(snapshot, "ypp", side="defense", limit=3)
    assert list(defense_board["team"]) == ["B", "C", "A"]


def test_scatter_plot_returns_figure():
    snapshot = pd.DataFrame(
        {
            "team": ["A", "B"],
            "games_played": [6, 6],
            "off_ypp": [7.0, 6.5],
            "off_sr": [0.45, 0.4],
        }
    )
    fig, ax = scatter_plot(
        snapshot,
        "ypp",
        "sr",
        side="offense",
        highlight_team="A",
        show_medians=False,
    )
    assert fig is not None
    assert ax is not None
    plt.close(fig)
