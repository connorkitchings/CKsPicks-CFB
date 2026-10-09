"""Tests for new features added in Session 1 overhaul.

Covers:
- Vectorized byplay calculations (update_yards_gained, success, explosive)
- Turnover, red zone, sack, penalty, fourth-down metrics in aggregate_team_game
- Luck factor implementation in pipeline
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.features.byplay import (
    allplays_to_byplay,
    calculate_explosive,
    calculate_play_success,
    update_yards_gained,
)
from cks_picks_cfb.features.core import aggregate_team_game
from cks_picks_cfb.features.pipeline import calculate_luck_factor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_play(**kwargs) -> dict:
    """Return a minimal play dict matching allplays_to_byplay requirements."""
    defaults = {
        "season": 2024,
        "week": 1,
        "game_id": 1,
        "offense": "A",
        "defense": "B",
        "play_number": 1,
        "drive_number": 1,
        "quarter": 1,
        "down": 1,
        "yards_to_first": 10,
        "yards_to_goal": 70,
        "yards_gained": 5,
        "yard_line": 30,
        "adj_yd_line": 70,
        "offense_score": 0,
        "defense_score": 0,
        "play_type": "Rush",
        "play_text": "",
        "ppa": 0.0,
        "scoring": 0,
        "turnover": 0,
        "penalty": 0,
        "offense_timeouts": 3,
        "defense_timeouts": 3,
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Vectorized byplay calculations
# ---------------------------------------------------------------------------


class TestVectorizedByplay:
    """Verify vectorized logic matches expected outputs."""

    def test_update_yards_gained_fumble_td_zeros(self):
        """Fumble recovery (touchdown) with nonzero yards should zero out."""
        data = pd.DataFrame(
            [
                {"play_type": "Fumble Recovery (Touchdown)", "yards_gained": 20},
                {"play_type": "Rush", "yards_gained": 5},
                {"play_type": "Fumble Recovery (Opponent)", "yards_gained": 15},
            ]
        )
        # Apply row-wise function for reference
        expected = data.apply(update_yards_gained, axis=1).tolist()
        assert expected == [0, 5, 0]

    def test_success_first_down_50pct(self):
        """Down 1 with 50%+ yards to first should be successful."""
        row = pd.Series(
            {
                "down": 1,
                "yards_gained": 5,
                "yards_to_first": 10,
                "yards_to_goal": 30,
                "play_type": "Rush",
                "turnover": 0,
                "penalty": 0,
            }
        )
        assert calculate_play_success(row) == 1

    def test_success_first_down_failure(self):
        """Down 1 with <50% yards to first should not be successful."""
        row = pd.Series(
            {
                "down": 1,
                "yards_gained": 4,
                "yards_to_first": 10,
                "yards_to_goal": 30,
                "play_type": "Rush",
                "turnover": 0,
                "penalty": 0,
            }
        )
        assert calculate_play_success(row) == 0

    def test_success_turnover_returns_zero(self):
        """Turnover play returns success=0."""
        row = pd.Series(
            {
                "down": 1,
                "yards_gained": 0,
                "yards_to_first": 10,
                "yards_to_goal": 30,
                "play_type": "Interception",
                "turnover": 1,
                "penalty": 0,
            }
        )
        assert calculate_play_success(row) == 0

    def test_success_penalty_returns_none(self):
        """Penalty play returns success=None."""
        row = pd.Series(
            {
                "down": 1,
                "yards_gained": 0,
                "yards_to_first": 10,
                "yards_to_goal": 30,
                "play_type": "Penalty",
                "turnover": 0,
                "penalty": 1,
            }
        )
        assert calculate_play_success(row) is None

    def test_explosive_rush_15_plus(self):
        """Rush play >=15 yards should be explosive."""
        row = pd.Series(
            {
                "play_type": "Rush",
                "yards_gained": 20,
                "rush_result": 1,
                "pass_attempt": 0,
            }
        )
        assert calculate_explosive(row) == 1

    def test_explosive_pass_20_plus(self):
        """Pass play >=20 yards should be explosive."""
        row = pd.Series(
            {
                "play_type": "Pass Reception",
                "yards_gained": 25,
                "rush_result": 0,
                "pass_attempt": 1,
            }
        )
        assert calculate_explosive(row) == 1

    def test_explosive_rush_under_threshold(self):
        """Rush play <15 yards should not be explosive."""
        row = pd.Series(
            {
                "play_type": "Rush",
                "yards_gained": 10,
                "rush_result": 1,
                "pass_attempt": 0,
            }
        )
        assert calculate_explosive(row) == 0


# ---------------------------------------------------------------------------
# Vectorized byplay integration: allplays_to_byplay
# ---------------------------------------------------------------------------


class TestByplayVectorized:
    """End-to-end byplay produces correct columns with vectorized logic."""

    def _minimal_raw_plays(self) -> pd.DataFrame:
        plays = [
            _make_play(
                play_number=1,
                play_type="Rush",
                yards_gained=15,
                down=1,
                yards_to_first=10,
                yards_to_goal=50,
            ),
            _make_play(
                play_number=2,
                play_type="Pass Reception",
                yards_gained=25,
                down=2,
                yards_to_first=8,
                yards_to_goal=40,
                pass_attempt=1,
            ),
            _make_play(
                play_number=3,
                play_type="Interception Return Touchdown",
                yards_gained=10,
                down=3,
                yards_to_first=5,
                yards_to_goal=20,
                offense="A",
                defense="B",
            ),
            _make_play(
                play_number=4,
                play_type="Fumble Recovery (Opponent)",
                yards_gained=10,
                down=1,
                yards_to_first=10,
                yards_to_goal=70,
            ),
            _make_play(
                play_number=5,
                play_type="Fumble Recovery (Touchdown)",
                yards_gained=30,
                down=1,
                yards_to_first=10,
                yards_to_goal=30,
            ),
        ]
        return pd.DataFrame(plays)

    def test_missing_ppa_survives_legacy_zero_fill(self):
        raw = pd.DataFrame(
            [_make_play(play_number=1, ppa=None), _make_play(play_number=2, ppa=0.0)]
        )
        result = allplays_to_byplay(raw).sort_values("play_number")
        assert result.ppa.tolist() == [0.0, 0.0]
        assert result.ppa_missing.tolist() == [True, False]
        assert result.ppa_missing_reason.tolist() == ["provider_missing_ppa", ""]

    def test_nullable_ppa_keeps_missing_null_and_genuine_zero_zero(self):
        raw = pd.DataFrame(
            [
                _make_play(play_number=1, ppa=None),
                _make_play(play_number=2, ppa=0.0),
                _make_play(play_number=3, ppa=0.7),
            ]
        )
        result = allplays_to_byplay(raw, nullable_ppa=True).sort_values("play_number")
        assert result.ppa.isna().tolist() == [True, False, False]
        assert result.ppa.tolist()[1:] == [0.0, 0.7]
        assert result.ppa_missing.tolist() == [True, False, False]
        assert result.ppa_missing_reason.tolist() == ["provider_missing_ppa", "", ""]

    def test_byplay_v1_collapses_only_exact_source_repeats(self):
        play = _make_play(id=101, __capture_id="first")
        result = allplays_to_byplay(
            pd.DataFrame([play, {**play, "__capture_id": "retry"}])
        )
        assert len(result) == 1

    def test_byplay_v1_blocks_distinct_provider_ids_at_same_sequence(self):
        raw = pd.DataFrame(
            [
                _make_play(id=101, play_number=1, ppa=0.1),
                _make_play(id=102, play_number=1, ppa=0.2),
            ]
        )
        with pytest.raises(ValueError, match="byplay_v1 cannot represent distinct"):
            allplays_to_byplay(raw)

    def test_byplay_v1_blocks_conflicting_revisions_of_one_provider_id(self):
        raw = pd.DataFrame(
            [
                _make_play(id=101, play_number=1, ppa=0.1),
                _make_play(id=101, play_number=1, ppa=0.2),
            ]
        )
        with pytest.raises(ValueError, match="byplay_v1 cannot represent distinct"):
            allplays_to_byplay(raw)

    def test_nullable_ppa_changes_nothing_but_ppa(self):
        raw = pd.DataFrame(
            [_make_play(play_number=1, ppa=None), _make_play(play_number=2, ppa=0.0)]
        )
        legacy = (
            allplays_to_byplay(raw).sort_values("play_number").reset_index(drop=True)
        )
        nullable = (
            allplays_to_byplay(raw, nullable_ppa=True)
            .sort_values("play_number")
            .reset_index(drop=True)
        )
        pd.testing.assert_frame_equal(
            legacy.drop(columns=["ppa"]), nullable.drop(columns=["ppa"])
        )

    def test_legacy_default_is_unchanged_by_the_option_existing(self):
        raw = pd.DataFrame([_make_play(play_number=1, ppa=None)])
        assert allplays_to_byplay(raw).ppa.tolist() == [0.0]
        assert allplays_to_byplay(raw, nullable_ppa=False).ppa.tolist() == [0.0]

    def test_returned_punt_is_a_special_teams_play(self):
        raw = pd.DataFrame(
            [
                _make_play(play_number=1, play_type="Rush", down=3),
                _make_play(
                    play_number=2,
                    play_type="Punt Return",
                    down=4,
                    yards_gained=18,
                    yards_to_first=10,
                ),
            ]
        )
        df = allplays_to_byplay(raw).sort_values("play_number")
        punt = df[df["play_type"] == "Punt Return"].iloc[0]
        assert punt["st"] == 1
        assert punt["st_punt"] == 1
        assert df[df["play_type"] == "Rush"].iloc[0]["st"] == 0

    def test_fumble_turnover_column_exists(self):
        df = allplays_to_byplay(self._minimal_raw_plays())
        assert "fumble_turnover" in df.columns

    def test_interception_turnover_column_exists(self):
        df = allplays_to_byplay(self._minimal_raw_plays())
        assert "interception_turnover" in df.columns

    def test_fumble_turnover_values(self):
        df = allplays_to_byplay(self._minimal_raw_plays())
        # "Fumble Recovery (Opponent)" should be flagged
        opp_fumbles = df[df["play_type"] == "Fumble Recovery (Opponent)"]
        assert (opp_fumbles["fumble_turnover"] == 1).all()

    def test_interception_turnover_values(self):
        df = allplays_to_byplay(self._minimal_raw_plays())
        int_plays = df[df["play_type"] == "Interception Return Touchdown"]
        assert (int_plays["interception_turnover"] == 1).all()

    def test_yards_gained_fumble_zeroed(self):
        """Fumble Recovery (Opponent) yards_gained should be 0 after byplay."""
        df = allplays_to_byplay(self._minimal_raw_plays())
        opp_fumbles = df[df["play_type"] == "Fumble Recovery (Opponent)"]
        assert (opp_fumbles["yards_gained"] == 0).all()

    def test_success_explosive_computed(self):
        df = allplays_to_byplay(self._minimal_raw_plays())
        assert "success" in df.columns
        assert "explosive" in df.columns

    def test_rush_15_yards_explosive(self):
        df = allplays_to_byplay(self._minimal_raw_plays())
        rush_plays = df[df["play_type"] == "Rush"]
        # 15-yard rush should be explosive
        big_rushes = rush_plays[rush_plays["yards_gained"] >= 15]
        assert (big_rushes["explosive"] == 1).all()


# ---------------------------------------------------------------------------
# New aggregate_team_game metrics
# ---------------------------------------------------------------------------


def _make_plays_with_all_cols() -> pd.DataFrame:
    """Create a plays DataFrame that includes all new columns."""
    plays = [
        {
            "season": 2024,
            "week": 1,
            "game_id": 1,
            "offense": "A",
            "defense": "B",
            "play_number": 1,
            "play_type": "Rush",
            "rush_attempt": 1,
            "pass_attempt": 0,
            "dropback": 0,
            "sack": 0,
            "success": 1,
            "yards_gained": 8,
            "ppa": 0.3,
            "turnover": 0,
            "fumble_turnover": 0,
            "interception_turnover": 0,
            "penalty": 0,
            "offensive_penalty": 0,
            "defensive_penalty": 0,
            "red_zone": 0,
            "down": 1,
            "yards_to_first": 10,
            "yards_to_goal": 60,
            "thirddown_conversion": None,
            "fourthdown_conversion": None,
            "havoc": 0,
            "line_yards": 4.0,
            "second_level_yards": 1.5,
            "open_field_yards": 0.0,
            "is_power_situation": 0,
            "power_success_converted": 0,
            "st": 0,
        },
        {
            "season": 2024,
            "week": 1,
            "game_id": 1,
            "offense": "A",
            "defense": "B",
            "play_number": 2,
            "play_type": "Pass Reception",
            "rush_attempt": 0,
            "pass_attempt": 1,
            "dropback": 1,
            "sack": 0,
            "success": 1,
            "yards_gained": 15,
            "ppa": 0.5,
            "turnover": 0,
            "fumble_turnover": 0,
            "interception_turnover": 0,
            "penalty": 0,
            "offensive_penalty": 0,
            "defensive_penalty": 0,
            "red_zone": 1,
            "down": 3,
            "yards_to_first": 5,
            "yards_to_goal": 15,
            "thirddown_conversion": 1,
            "fourthdown_conversion": None,
            "havoc": 0,
            "line_yards": np.nan,
            "second_level_yards": np.nan,
            "open_field_yards": np.nan,
            "is_power_situation": 0,
            "power_success_converted": 0,
            "st": 0,
        },
        {
            "season": 2024,
            "week": 1,
            "game_id": 1,
            "offense": "A",
            "defense": "B",
            "play_number": 3,
            "play_type": "Sack",
            "rush_attempt": 0,
            "pass_attempt": 0,
            "dropback": 1,
            "sack": 1,
            "success": 0,
            "yards_gained": -5,
            "ppa": -0.4,
            "turnover": 0,
            "fumble_turnover": 0,
            "interception_turnover": 0,
            "penalty": 0,
            "offensive_penalty": 0,
            "defensive_penalty": 0,
            "red_zone": 0,
            "down": 2,
            "yards_to_first": 8,
            "yards_to_goal": 40,
            "thirddown_conversion": None,
            "fourthdown_conversion": None,
            "havoc": 1,
            "line_yards": np.nan,
            "second_level_yards": np.nan,
            "open_field_yards": np.nan,
            "is_power_situation": 0,
            "power_success_converted": 0,
            "st": 0,
        },
        {
            "season": 2024,
            "week": 1,
            "game_id": 1,
            "offense": "A",
            "defense": "B",
            "play_number": 4,
            "play_type": "Interception",
            "rush_attempt": 0,
            "pass_attempt": 1,
            "dropback": 1,
            "sack": 0,
            "success": 0,
            "yards_gained": 0,
            "ppa": -1.0,
            "turnover": 1,
            "fumble_turnover": 0,
            "interception_turnover": 1,
            "penalty": 0,
            "offensive_penalty": 0,
            "defensive_penalty": 0,
            "red_zone": 0,
            "down": 1,
            "yards_to_first": 10,
            "yards_to_goal": 50,
            "thirddown_conversion": None,
            "fourthdown_conversion": None,
            "havoc": 1,
            "line_yards": np.nan,
            "second_level_yards": np.nan,
            "open_field_yards": np.nan,
            "is_power_situation": 0,
            "power_success_converted": 0,
            "st": 0,
        },
        {
            # Team B on offense
            "season": 2024,
            "week": 1,
            "game_id": 1,
            "offense": "B",
            "defense": "A",
            "play_number": 1,
            "play_type": "Rush",
            "rush_attempt": 1,
            "pass_attempt": 0,
            "dropback": 0,
            "sack": 0,
            "success": 1,
            "yards_gained": 5,
            "ppa": 0.1,
            "turnover": 0,
            "fumble_turnover": 0,
            "interception_turnover": 0,
            "penalty": 1,
            "offensive_penalty": 1,
            "defensive_penalty": 0,
            "red_zone": 0,
            "down": 1,
            "yards_to_first": 10,
            "yards_to_goal": 60,
            "thirddown_conversion": None,
            "fourthdown_conversion": None,
            "havoc": 0,
            "line_yards": 3.0,
            "second_level_yards": 0.5,
            "open_field_yards": 0.0,
            "is_power_situation": 0,
            "power_success_converted": 0,
            "st": 0,
        },
    ]
    return pd.DataFrame(plays)


def _make_drives_minimal() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2024,
                "week": 1,
                "game_id": 1,
                "drive_number": 1,
                "offense": "A",
                "defense": "B",
                "drive_plays": 3,
                "drive_yards": 20,
                "drive_start_period": 1,
                "drive_end_period": 1,
                "start_yards_to_goal": 60,
                "end_yards_to_goal": 15,
                "is_eckel_drive": 0,
                "had_scoring_opportunity": 0,
                "points": 0,
                "turnovers": 0,
                "is_successful_drive": 0,
                "is_busted_drive": 0,
                "is_explosive_drive": 0,
                "points_on_opps": 0,
            },
            {
                "season": 2024,
                "week": 1,
                "game_id": 1,
                "drive_number": 2,
                "offense": "B",
                "defense": "A",
                "drive_plays": 1,
                "drive_yards": 5,
                "drive_start_period": 1,
                "drive_end_period": 1,
                "start_yards_to_goal": 60,
                "end_yards_to_goal": 55,
                "is_eckel_drive": 0,
                "had_scoring_opportunity": 0,
                "points": 0,
                "turnovers": 0,
                "is_successful_drive": 0,
                "is_busted_drive": 0,
                "is_explosive_drive": 0,
                "points_on_opps": 0,
            },
        ]
    )


class TestNewAggregationMetrics:
    """Verify new metrics are computed correctly in aggregate_team_game."""

    @pytest.fixture
    def team_game_df(self):
        plays = _make_plays_with_all_cols()
        drives = _make_drives_minimal()
        return aggregate_team_game(plays, drives)

    def test_turnover_rate_computed(self, team_game_df):
        assert "off_turnover_rate" in team_game_df.columns

    def test_team_a_turnover_rate(self, team_game_df):
        team_a = team_game_df[team_game_df["team"] == "A"].iloc[0]
        # Team A had 1 turnover out of 4 plays
        assert abs(team_a["off_turnover_rate"] - 0.25) < 1e-6

    def test_interception_rate_computed(self, team_game_df):
        assert "off_interception_rate" in team_game_df.columns

    def test_team_a_interception_rate(self, team_game_df):
        team_a = team_game_df[team_game_df["team"] == "A"].iloc[0]
        # Team A had 1 INT out of 4 plays
        assert abs(team_a["off_interception_rate"] - 0.25) < 1e-6

    def test_sack_rate_computed(self, team_game_df):
        assert "off_sack_rate" in team_game_df.columns

    def test_team_a_sack_rate(self, team_game_df):
        team_a = team_game_df[team_game_df["team"] == "A"].iloc[0]
        # Team A: 1 sack on 3 dropbacks
        assert abs(team_a["off_sack_rate"] - 1 / 3) < 1e-6

    def test_penalty_rate_computed(self, team_game_df):
        assert "off_penalty_rate" in team_game_df.columns

    def test_team_b_penalty_rate(self, team_game_df):
        team_b = team_game_df[team_game_df["team"] == "B"].iloc[0]
        # Team B has 1 penalty on 1 play
        assert abs(team_b["off_penalty_rate"] - 1.0) < 1e-6

    def test_red_zone_sr_computed(self, team_game_df):
        assert "off_red_zone_sr" in team_game_df.columns

    def test_team_a_red_zone_sr(self, team_game_df):
        team_a = team_game_df[team_game_df["team"] == "A"].iloc[0]
        # Team A had 1 red zone play (play 2) with success=1
        assert abs(team_a["off_red_zone_sr"] - 1.0) < 1e-6

    def test_def_sack_rate_computed(self, team_game_df):
        assert "def_sack_rate" in team_game_df.columns

    def test_fourth_down_conversion_rate_computed(self, team_game_df):
        assert "off_fourth_down_conversion_rate" in team_game_df.columns

    def test_fourth_down_attempt_rate_computed(self, team_game_df):
        assert "off_fourth_down_attempt_rate" in team_game_df.columns


class TestTier2Metrics:
    """Verify Tier 2 metrics are defined in core.py for aggregation."""

    def test_non_garbage_sr_in_metric_cols(self):
        from cks_picks_cfb.features.core import aggregate_team_season

        base_cols = aggregate_team_season.__code__.co_consts
        assert any("non_garbage_sr" in str(c) for c in base_cols)

    def test_fourth_quarter_sr_defined(self):
        from cks_picks_cfb.features.core import aggregate_team_game

        src = aggregate_team_game.__code__.co_consts
        assert any("fourth_quarter_sr" in str(c) for c in src)

    def test_close_game_sr_defined(self):
        from cks_picks_cfb.features.core import aggregate_team_game

        src = aggregate_team_game.__code__.co_consts
        assert any("close_game_sr" in str(c) for c in src)

    def test_td_rate_defined(self):
        from cks_picks_cfb.features.core import aggregate_team_game

        src = aggregate_team_game.__code__.co_consts
        assert any("td_rate" in str(c) for c in src)

    def test_40_plus_yard_rate_defined(self):
        from cks_picks_cfb.features.core import aggregate_team_game

        src = aggregate_team_game.__code__.co_consts
        assert any("40_plus_yard_rate" in str(c) for c in src)

    def test_kickoff_metrics_defined(self):
        from cks_picks_cfb.features.core import aggregate_team_game

        src = aggregate_team_game.__code__.co_consts
        assert any("touchback_rate" in str(c) for c in src)
        assert any("kick_return_avg_yards" in str(c) for c in src)


class TestIngesters:
    """Verify new ingester classes can be imported."""

    def test_rankings_ingester_importable(self):
        from cks_picks_cfb.data.rankings import RankingsIngester

        assert RankingsIngester is not None

    def test_recruiting_ingester_importable(self):
        from cks_picks_cfb.data.recruiting import RecruitingIngester

        assert RecruitingIngester is not None


# ---------------------------------------------------------------------------
# Luck factor
# ---------------------------------------------------------------------------


class TestLuckFactor:
    """Verify calculate_luck_factor computes correct turnover luck."""

    def _setup(self):
        byplay = pd.DataFrame(
            [
                {"game_id": 1, "offense": "A", "defense": "B", "turnover": 1},
                {"game_id": 1, "offense": "A", "defense": "B", "turnover": 0},
                {"game_id": 1, "offense": "B", "defense": "A", "turnover": 0},
                {"game_id": 1, "offense": "B", "defense": "A", "turnover": 0},
            ]
        )
        team_game = pd.DataFrame(
            [
                {"game_id": 1, "team": "A", "season": 2024, "week": 1},
                {"game_id": 1, "team": "B", "season": 2024, "week": 1},
            ]
        )
        return team_game, byplay

    def test_luck_factor_column_created(self):
        tg, bp = self._setup()
        result = calculate_luck_factor(tg, bp)
        assert "luck_factor" in result.columns

    def test_team_a_luck_negative(self):
        """Team A lost 1 turnover, gained 0 → luck = -1."""
        tg, bp = self._setup()
        result = calculate_luck_factor(tg, bp)
        team_a = result[result["team"] == "A"].iloc[0]
        assert team_a["luck_factor"] == -1.0

    def test_team_b_luck_positive(self):
        """Team B gained 1 turnover, lost 0 → luck = +1."""
        tg, bp = self._setup()
        result = calculate_luck_factor(tg, bp)
        team_b = result[result["team"] == "B"].iloc[0]
        assert team_b["luck_factor"] == 1.0

    def test_no_turnover_column_graceful(self):
        """Missing turnover column falls back to luck_factor=0."""
        byplay = pd.DataFrame([{"game_id": 1, "offense": "A", "defense": "B"}])
        team_game = pd.DataFrame([{"game_id": 1, "team": "A"}])
        result = calculate_luck_factor(team_game, byplay)
        assert result["luck_factor"].iloc[0] == 0.0

    def test_idempotent_on_existing_column(self):
        """Existing luck_factor column is replaced, not duplicated."""
        tg, bp = self._setup()
        tg["luck_factor"] = 99.0  # pre-existing column
        result = calculate_luck_factor(tg, bp)
        assert "luck_factor" in result.columns
        # Should be replaced by computed values
        team_a = result[result["team"] == "A"].iloc[0]
        assert team_a["luck_factor"] != 99.0


def test_the_pipeline_threads_nullable_ppa_to_the_byplay_builder(monkeypatch):
    from cks_picks_cfb.features import pipeline

    seen = {}

    def fake(data, corrections=None, *, nullable_ppa=False):
        seen["nullable_ppa"] = nullable_ppa
        raise RuntimeError("stop after the byplay step")

    monkeypatch.setattr(pipeline, "allplays_to_byplay", fake)
    for flag in (True, False):
        with pytest.raises(RuntimeError, match="stop after"):
            pipeline.build_preaggregation_pipeline(
                pd.DataFrame({"season": [2026], "week": [1]}), nullable_ppa=flag
            )
        assert seen["nullable_ppa"] is flag
