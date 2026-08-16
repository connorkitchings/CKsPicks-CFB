import pandas as pd
import pytest

from cks_picks_cfb.features.point_in_time import (
    add_completed_game_routing,
    attach_baseline_predictions,
    build_point_in_time_matchups,
    build_team_side_gold,
    team_side_to_wide,
)


def _matchup() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": 10,
                "week": 2,
                "start_date": "2026-09-05T16:00:00Z",
                "home_team": "Alpha",
                "away_team": "Beta",
                "home_current_season_games": 1,
                "away_current_season_games": 0,
                "home_adj_off_success": 0.5,
                "away_adj_off_success": None,
                "home_team_spread_line": -3.5,
                "total_line": 51.5,
            }
        ]
    )


def test_snapshot_is_team_keyed_and_excludes_bookmaker_features():
    result = build_point_in_time_matchups(
        _matchup(), season=2026, as_of="2026-09-01", provenance={"source": "r2"}
    )
    assert result[["season", "week", "game_id", "team"]].values.tolist() == [
        [2026, 2, 10, "Alpha"],
        [2026, 2, 10, "Beta"],
    ]
    assert result["completed_game_count"].tolist() == [1, 0]
    assert set(result["prior_source_season"]) == {2025}
    assert set(result["prior_season_gap"]) == {1}
    assert "team_spread_line" not in result.columns
    assert result.loc[result["team"] == "Beta", "missing_feature_count"].item() == 1


def test_snapshot_rejects_cutoff_after_kickoff():
    with pytest.raises(ValueError, match="cutoff"):
        build_point_in_time_matchups(
            _matchup(), season=2026, as_of="2026-09-06", provenance={}
        )


def test_2021_snapshot_uses_2019_and_rejects_2020_lineage():
    matchup = _matchup().assign(
        week=0,
        start_date="2021-08-28T16:00:00Z",
        home_current_season_games=0,
        away_current_season_games=0,
    )
    result = build_point_in_time_matchups(
        matchup,
        season=2021,
        as_of="2021-08-27",
        provenance={"schedule": "v1"},
    )
    assert set(result["prior_source_season"]) == {2019}
    assert set(result["prior_season_gap"]) == {2}
    with pytest.raises(ValueError, match="2020"):
        build_point_in_time_matchups(
            matchup,
            season=2021,
            as_of="2021-08-27",
            provenance={"schedule": "v1"},
            prior_source_overrides={2021: 2020},
        )


def test_completed_counts_use_kickoff_order_and_ignore_cancelled_games():
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "game_id": 1,
                "start_date": "2026-08-22T16:00:00Z",
                "home_team": "Alpha",
                "away_team": "Gamma",
                "completed": True,
                "status": "final",
            },
            {
                "season": 2026,
                "game_id": 2,
                "start_date": "2026-08-23T16:00:00Z",
                "home_team": "Beta",
                "away_team": "Delta",
                "completed": True,
                "status": "cancelled",
            },
            {
                "season": 2026,
                "game_id": 3,
                "start_date": "2026-08-29T16:00:00Z",
                "home_team": "Alpha",
                "away_team": "Beta",
                "completed": False,
                "status": "scheduled",
            },
        ]
    )
    matchups = schedule[schedule["game_id"] == 3].copy()
    result = add_completed_game_routing(matchups, schedule)
    assert result.loc[result.index[0], "home_completed_games"] == 1
    assert result.loc[result.index[0], "away_completed_games"] == 0
    assert result.loc[result.index[0], "prediction_regime"] == "game_1"


def test_gold_keeps_prior_and_current_blocks_and_builds_wide_view():
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 0,
                "game_id": 3,
                "start_date": "2026-08-29T16:00:00Z",
                "home_team": "Alpha",
                "away_team": "Beta",
                "completed": False,
            }
        ]
    )
    matchups = schedule.assign(
        home_prior_adj_off_epa_pp=0.2,
        away_prior_adj_off_epa_pp=0.1,
        home_adj_off_epa_pp=None,
        away_adj_off_epa_pp=None,
    )
    team_side = build_team_side_gold(
        matchups,
        schedule,
        as_of="2026-08-28T00:00:00Z",
        provenance={"games": "v1"},
    )
    assert len(team_side) == 2
    assert set(team_side["prior_adj_off_epa_pp"]) == {0.1, 0.2}
    assert team_side["current_adj_off_epa_pp"].isna().all()

    wide = team_side_to_wide(team_side)
    assert wide.loc[0, "home_prior_adj_off_epa_pp"] == 0.2
    assert pd.isna(wide.loc[0, "home_adj_off_epa_pp"])
    with_baselines = attach_baseline_predictions(
        wide,
        pd.DataFrame(
            [
                {
                    "season": 2026,
                    "game_id": 3,
                    "baseline_spread_prediction": -2.0,
                    "baseline_total_prediction": 48.0,
                }
            ]
        ),
    )
    assert with_baselines.loc[0, "baseline_total_prediction"] == 48.0
