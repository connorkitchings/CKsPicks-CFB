"""Unit tests for external feature merge functions.

Covers:
- merge_external_ratings: SP+/FPI/SRS columns and differentials
- merge_recruiting_composite: talent composite and diff
- merge_rankings: rank columns, unranked fill, and derived flags
"""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.features.external import (
    merge_external_ratings,
    merge_rankings,
    merge_recruiting_composite,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _matchup(home="Alabama", away="Georgia", week=3) -> pd.DataFrame:
    return pd.DataFrame(
        [{"game_id": 1, "home_team": home, "away_team": away, "week": week}]
    )


class _MockStorage:
    """Minimal storage stub that returns pre-loaded data."""

    def __init__(self, data: dict[str, list[dict]]):
        self._data = data  # key = "raw/entity/year=N"

    def read_index(self, entity: str, filters: dict) -> list[dict]:
        year = filters.get("year", "")
        week = filters.get("week")
        key = f"{entity}/year={year}"
        if week is not None:
            key += f"/week={week}"
        return self._data.get(key, [])


# ---------------------------------------------------------------------------
# merge_external_ratings
# ---------------------------------------------------------------------------


class TestMergeExternalRatings:
    def _make_storage(self, year=2023):
        ratings = [
            {
                "rating_type": "sp",
                "team": "Alabama",
                "rating": 30.0,
                "year": year,
                "week": 10,
            },
            {
                "rating_type": "sp",
                "team": "Georgia",
                "rating": 28.5,
                "year": year,
                "week": 10,
            },
            {
                "rating_type": "fpi",
                "team": "Alabama",
                "rating": 25.0,
                "year": year,
                "week": 10,
            },
            {
                "rating_type": "fpi",
                "team": "Georgia",
                "rating": 22.0,
                "year": year,
                "week": 10,
            },
            {
                "rating_type": "fei",
                "team": "Alabama",
                "rating": 20.1,
                "year": year,
                "week": 10,
            },
            {
                "rating_type": "fei",
                "team": "Georgia",
                "rating": 18.5,
                "year": year,
                "week": 10,
            },
        ]
        return _MockStorage({"raw/external_ratings/year=2023/week=10": ratings})

    def test_sp_rating_columns_added(self):
        storage = self._make_storage()
        result = merge_external_ratings(_matchup(), year=2023, week=10, storage=storage)
        assert "home_sp_rating" in result.columns
        assert "away_sp_rating" in result.columns

    def test_sp_rating_values_correct(self):
        storage = self._make_storage()
        result = merge_external_ratings(_matchup(), year=2023, week=10, storage=storage)
        assert abs(result["home_sp_rating"].iloc[0] - 30.0) < 1e-6
        assert abs(result["away_sp_rating"].iloc[0] - 28.5) < 1e-6

    def test_sp_rating_diff_computed(self):
        storage = self._make_storage()
        result = merge_external_ratings(_matchup(), year=2023, week=10, storage=storage)
        assert "sp_rating_diff" in result.columns
        assert abs(result["sp_rating_diff"].iloc[0] - (30.0 - 28.5)) < 1e-6

    def test_fpi_columns_added(self):
        storage = self._make_storage()
        result = merge_external_ratings(_matchup(), year=2023, week=10, storage=storage)
        assert "home_fpi" in result.columns
        assert "away_fpi" in result.columns
        assert "fpi_diff" in result.columns

    def test_fei_columns_added(self):
        storage = self._make_storage()
        result = merge_external_ratings(_matchup(), year=2023, week=10, storage=storage)
        assert "home_fei" in result.columns
        assert "away_fei" in result.columns
        assert "fei_diff" in result.columns

    def test_no_data_returns_unchanged(self):
        storage = _MockStorage({})
        original = _matchup()
        result = merge_external_ratings(
            original.copy(), year=2023, week=10, storage=storage
        )
        assert list(result.columns) == list(original.columns)

    def test_unknown_team_fills_nan(self):
        storage = self._make_storage()
        df = pd.DataFrame(
            [{"game_id": 2, "home_team": "Unknown", "away_team": "Georgia", "week": 10}]
        )
        result = merge_external_ratings(df, year=2023, week=10, storage=storage)
        assert pd.isna(result["home_sp_rating"].iloc[0])
        assert abs(result["away_sp_rating"].iloc[0] - 28.5) < 1e-6


# ---------------------------------------------------------------------------
# merge_recruiting_composite
# ---------------------------------------------------------------------------


class TestMergeRecruitingComposite:
    def _make_storage(self, years=(2020, 2021, 2022, 2023)):
        data = {}
        for y in years:
            key = f"raw/recruiting/year={y}"
            data[key] = [
                {"team": "Alabama", "points": 300.0 + y - 2020, "year": y},
                {"team": "Georgia", "points": 250.0 + y - 2020, "year": y},
            ]
        return _MockStorage(data)

    def test_talent_composite_added(self):
        storage = self._make_storage()
        result = merge_recruiting_composite(_matchup(), year=2023, storage=storage)
        assert "home_talent_composite" in result.columns
        assert "away_talent_composite" in result.columns

    def test_talent_diff_computed(self):
        storage = self._make_storage()
        result = merge_recruiting_composite(_matchup(), year=2023, storage=storage)
        assert "talent_diff" in result.columns
        expected_diff = (
            result["home_talent_composite"].iloc[0]
            - result["away_talent_composite"].iloc[0]
        )
        assert abs(result["talent_diff"].iloc[0] - expected_diff) < 1e-6

    def test_averages_across_n_years(self):
        storage = self._make_storage()
        result = merge_recruiting_composite(
            _matchup(), year=2023, storage=storage, n_years=4
        )
        # Alabama: (300, 301, 302, 303) over years 2020-2023 → mean = 301.5
        assert abs(result["home_talent_composite"].iloc[0] - 301.5) < 1e-6

    def test_no_data_returns_unchanged(self):
        storage = _MockStorage({})
        original = _matchup()
        result = merge_recruiting_composite(original.copy(), year=2023, storage=storage)
        assert list(result.columns) == list(original.columns)

    def test_unknown_team_fills_nan(self):
        storage = self._make_storage()
        df = pd.DataFrame(
            [{"game_id": 2, "home_team": "Unknown", "away_team": "Alabama", "week": 3}]
        )
        result = merge_recruiting_composite(df, year=2023, storage=storage)
        assert pd.isna(result["home_talent_composite"].iloc[0])


# ---------------------------------------------------------------------------
# merge_rankings
# ---------------------------------------------------------------------------


class TestMergeRankings:
    def _make_storage(self, year=2023):
        rankings = [
            # Week 3 AP Top 25
            {
                "season": year,
                "week": 3,
                "poll": "AP Top 25",
                "team": "Alabama",
                "rank": 2,
                "year": year,
            },
            {
                "season": year,
                "week": 3,
                "poll": "AP Top 25",
                "team": "Georgia",
                "rank": 1,
                "year": year,
            },
            # Week 3 Coaches Poll
            {
                "season": year,
                "week": 3,
                "poll": "Coaches Poll",
                "team": "Alabama",
                "rank": 3,
                "year": year,
            },
            {
                "season": year,
                "week": 3,
                "poll": "Coaches Poll",
                "team": "Georgia",
                "rank": 1,
                "year": year,
            },
        ]
        return _MockStorage({"raw/rankings/year=2023": rankings})

    def test_rank_columns_added(self):
        storage = self._make_storage()
        result = merge_rankings(_matchup(), year=2023, storage=storage)
        assert "home_rank" in result.columns
        assert "away_rank" in result.columns

    def test_rank_values_averaged(self):
        storage = self._make_storage()
        result = merge_rankings(_matchup(), year=2023, storage=storage)
        # Alabama: (2+3)/2 = 2.5 → rounds to 2 or 3 depending on rounding
        home_rank = result["home_rank"].iloc[0]
        assert home_rank in (2, 3)  # within range of AP/Coaches values
        # Georgia: (1+1)/2 = 1
        assert result["away_rank"].iloc[0] == 1

    def test_unranked_fills_26(self):
        storage = self._make_storage()
        df = pd.DataFrame(
            [
                {
                    "game_id": 2,
                    "home_team": "Ohio State",
                    "away_team": "Michigan",
                    "week": 3,
                }
            ]
        )
        result = merge_rankings(df, year=2023, storage=storage)
        assert result["home_rank"].iloc[0] == 26
        assert result["away_rank"].iloc[0] == 26

    def test_is_ranked_flags(self):
        storage = self._make_storage()
        result = merge_rankings(_matchup(), year=2023, storage=storage)
        assert result["is_ranked_home"].iloc[0] == 1
        assert result["is_ranked_away"].iloc[0] == 1

    def test_rank_diff_computed(self):
        storage = self._make_storage()
        result = merge_rankings(_matchup(), year=2023, storage=storage)
        assert "rank_diff" in result.columns
        expected = result["home_rank"].iloc[0] - result["away_rank"].iloc[0]
        assert result["rank_diff"].iloc[0] == expected

    def test_no_data_returns_unchanged(self):
        storage = _MockStorage({})
        original = _matchup()
        result = merge_rankings(original.copy(), year=2023, storage=storage)
        assert list(result.columns) == list(original.columns)

    def test_missing_week_column_returns_unchanged(self):
        storage = self._make_storage()
        df = pd.DataFrame(
            [{"game_id": 1, "home_team": "Alabama", "away_team": "Georgia"}]
        )
        result = merge_rankings(df, year=2023, storage=storage)
        # No week column → should return unchanged
        assert "home_rank" not in result.columns
