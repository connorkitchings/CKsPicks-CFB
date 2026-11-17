import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.ratings_lab.error_slices import (
    MIN_CELL_GAMES,
    assign_terciles,
    attach_slices,
    early_season_cost,
    game_attributes,
    partial_quarantine_games,
    quarantine_exposed_games,
    require_development_view,
    slice_table,
    tercile_edges,
    week_bucket,
)


def _frame(n: int = 300, *, target: str = "margin", season: int = 2022, seed: int = 0):
    rng = np.random.default_rng(seed)
    prediction = rng.normal(0, 10, n)
    return pd.DataFrame(
        {
            "season": season,
            "week": rng.integers(1, 15, n),
            "game_id": np.arange(n),
            "target": target,
            "actual": prediction + rng.normal(0, 5, n),
            "prediction": prediction,
            "interval_90_lower": prediction - 8,
            "interval_90_upper": prediction + 8,
            "completed_game_stage": rng.integers(0, 5, n),
        }
    )


def test_slice_counts_sum_to_total_and_empty_slices_are_omitted():
    frame = _frame()
    frame["bucket"] = frame["week"].map(week_bucket)
    order = ["1", "2", "3", "4", "5-8", "9-12", "13-16", "never"]
    table = slice_table(frame, "bucket", order)
    assert table["games"].sum() == len(frame)
    assert "never" not in set(table["slice"])


def test_bias_is_actual_minus_prediction():
    frame = _frame(20)
    frame["actual"] = frame["prediction"] + 3.0
    frame["bucket"] = "all"
    row = slice_table(frame, "bucket").iloc[0]
    assert row["bias"] == pytest.approx(3.0)
    assert row["mae"] == pytest.approx(3.0)
    assert row["rmse"] == pytest.approx(3.0)


def test_interval_coverage_counts_actuals_inside_the_interval():
    frame = _frame(10)
    frame["bucket"] = "all"
    frame["actual"] = frame["prediction"]
    frame.loc[:2, "actual"] = frame.loc[:2, "prediction"] + 100
    row = slice_table(frame, "bucket").iloc[0]
    assert row["coverage"] == pytest.approx(0.7)


def test_cells_under_the_minimum_are_flagged():
    frame = _frame(MIN_CELL_GAMES + 10)
    frame["bucket"] = np.where(frame["game_id"] < 10, "small", "large")
    table = slice_table(frame, "bucket").set_index("slice")
    assert bool(table.loc["small", "small"]) is True
    assert bool(table.loc["large", "small"]) is False


def test_slice_value_missing_from_ordering_is_rejected():
    frame = _frame(10)
    frame["bucket"] = "x"
    with pytest.raises(ValueError, match="missing from ordering"):
        slice_table(frame, "bucket", ["y"])


@pytest.mark.parametrize("season", [2026, 2020])
def test_seasons_outside_the_development_view_are_rejected(season):
    with pytest.raises(ValueError, match="outside the development view"):
        require_development_view(_frame(5, season=season))


def test_terciles_split_data_into_near_equal_groups():
    values = pd.Series(np.arange(300, dtype=float))
    edges = tercile_edges(values)
    labels = assign_terciles(values, edges, ("a", "b", "c"))
    assert labels.value_counts().to_dict() == {"a": 100, "b": 100, "c": 100}


def test_early_season_cost_reports_excess_over_later_level():
    frame = _frame(400)
    frame.loc[frame["week"].eq(1), "actual"] += 20
    cost = early_season_cost(frame).set_index("week")
    assert cost.loc[1, "excess"] > 5
    assert (cost["later_mae"] == cost["later_mae"].iloc[0]).all()


def _observations() -> pd.DataFrame:
    def game(gid, week, team_a, team_b, quarantined):
        rows = []
        for i, (team, role) in enumerate(
            [
                (team_a, "offense"),
                (team_a, "defense"),
                (team_b, "offense"),
                (team_b, "defense"),
            ]
        ):
            hit = i in quarantined
            rows.append(
                {
                    "season": 2022,
                    "week": week,
                    "game_id": gid,
                    "team": team,
                    "measurement_id": "ppp",
                    "unit_role": role,
                    "coverage_status": "missing" if hit else "observed",
                    "missing_reason": "unresolved_scoring_attribution" if hit else None,
                }
            )
        return rows

    return pd.DataFrame(
        game(1, 1, "A", "B", {0, 3})  # partial
        + game(2, 1, "C", "D", {0, 1, 2, 3})  # whole-game, not partial
        + game(3, 2, "A", "E", set())
        + game(4, 2, "F", "G", set())
    )


def test_partial_quarantine_excludes_whole_game_and_clean_games():
    assert partial_quarantine_games(_observations()) == {(2022, 1)}


def test_exposure_requires_an_earlier_week_partial_game_for_either_team():
    features = pd.DataFrame(
        {
            "season": 2022,
            "week": [2, 2, 1],
            "game_id": [3, 4, 1],
            "home_team": ["A", "F", "A"],
            "away_team": ["E", "G", "B"],
        }
    )
    flags = quarantine_exposed_games(_observations(), features)
    assert flags.tolist() == [True, False, False]


def test_game_attributes_and_attach_cover_every_game_once():
    margin = _frame(300, target="margin")
    total = _frame(300, target="total", seed=1)
    total["prediction"] += 55
    common = pd.concat([margin, total], ignore_index=True)
    features = pd.DataFrame(
        {"season": 2022, "game_id": np.arange(300), "week": margin["week"]}
    )
    attrs, edges = game_attributes(
        common, features, pd.Series(False, index=features.index)
    )
    assert len(attrs) == 300
    assert edges["gap"][0] < edges["gap"][1]
    joined = attach_slices(common, attrs)
    assert len(joined) == len(common)
    table = slice_table(joined[joined["target"].eq("total")], "totals_regime")
    assert table["games"].sum() == 300
