"""Unit and integration tests for V6 Preseason Continuity Prior Engine."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from cks_picks_cfb.ratings_lab.contracts import Game, Observation, Rating
from cks_picks_cfb.ratings_lab.priors import (
    FOUR_FACTOR_IDS,
    ContinuityTable,
    PreseasonPrior,
    TeamContinuity,
    compute_terminal_seeds,
)
from cks_picks_cfb.ratings_lab.replay import replay
from cks_picks_cfb.ratings_lab.updaters import ExposureDesign

# ---------------------------------------------------------------------------
# Task 1: Terminal Seed Standardization & Defensive Polarity
# ---------------------------------------------------------------------------


def test_terminal_seeds_defensive_sign():
    """Verify that defensive negation ensures a stingy defense receives a positive rating."""
    obs = [
        # Offense: Team A has high success rate (0.60), Team B has low (0.40)
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="Georgia",
            role="offense",
            measurement_id="rush_success_rate",
            value=0.60,
            exposure=30.0,
            available_utc="2024-09-01T06:00:00Z",
            timing_class="historically_reconstructed",
        ),
        Observation(
            season=2024,
            week=1,
            game_id=2,
            team="Vanderbilt",
            role="offense",
            measurement_id="rush_success_rate",
            value=0.40,
            exposure=30.0,
            available_utc="2024-09-01T06:00:00Z",
            timing_class="historically_reconstructed",
        ),
        # Defense: Georgia allows low success rate (0.30), Vanderbilt allows high (0.50)
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="Georgia",
            role="defense",
            measurement_id="rush_success_rate",
            value=0.30,
            exposure=30.0,
            available_utc="2024-09-01T06:00:00Z",
            timing_class="historically_reconstructed",
        ),
        Observation(
            season=2024,
            week=1,
            game_id=2,
            team="Vanderbilt",
            role="defense",
            measurement_id="rush_success_rate",
            value=0.50,
            exposure=30.0,
            available_utc="2024-09-01T06:00:00Z",
            timing_class="historically_reconstructed",
        ),
    ]

    seeds = compute_terminal_seeds(
        obs, measurement_id="rush_success_rate", signed_defense=True
    )

    # Offense: Georgia (0.60) > Vanderbilt (0.40) -> Georgia > 0, Vanderbilt < 0
    assert seeds[(2024, "Georgia", "offense")].mean > 0.0
    assert seeds[(2024, "Vanderbilt", "offense")].mean < 0.0

    # Defense: Georgia allowed 0.30 (better) vs Vanderbilt allowed 0.50 (worse)
    # With signed_defense=True, Georgia's signed value is -0.30 > -0.50 -> Georgia > 0, Vanderbilt < 0
    assert seeds[(2024, "Georgia", "defense")].mean > 0.0
    assert seeds[(2024, "Vanderbilt", "defense")].mean < 0.0

    # Verify symmetry
    assert math.isclose(seeds[(2024, "Georgia", "offense")].mean, 1.0, rel_tol=1e-3)
    assert math.isclose(seeds[(2024, "Vanderbilt", "offense")].mean, -1.0, rel_tol=1e-3)
    assert math.isclose(seeds[(2024, "Georgia", "defense")].mean, 1.0, rel_tol=1e-3)
    assert math.isclose(seeds[(2024, "Vanderbilt", "defense")].mean, -1.0, rel_tol=1e-3)


def test_terminal_seeds_all_six_ids():
    """Verify seed generation across all six 4-factor measurement IDs."""
    obs = []
    for mid in FOUR_FACTOR_IDS:
        obs.extend(
            [
                Observation(
                    season=2024,
                    week=1,
                    game_id=1,
                    team="Alabama",
                    role="offense",
                    measurement_id=mid,
                    value=0.55,
                    exposure=25.0,
                    available_utc="2024-09-01T06:00:00Z",
                    timing_class="historically_reconstructed",
                ),
                Observation(
                    season=2024,
                    week=1,
                    game_id=1,
                    team="Auburn",
                    role="offense",
                    measurement_id=mid,
                    value=0.45,
                    exposure=25.0,
                    available_utc="2024-09-01T06:00:00Z",
                    timing_class="historically_reconstructed",
                ),
            ]
        )

    seeds = compute_terminal_seeds(obs, signed_defense=True)
    # With measurement_id=None and multiple IDs, keys are (season, team, role, measurement_id)
    for mid in FOUR_FACTOR_IDS:
        key_bama = (2024, "Alabama", "offense", mid)
        key_auburn = (2024, "Auburn", "offense", mid)
        assert key_bama in seeds
        assert key_auburn in seeds
        assert seeds[key_bama].mean > seeds[key_auburn].mean


# ---------------------------------------------------------------------------
# Task 2: Continuity Ingestion & Validation
# ---------------------------------------------------------------------------


def test_continuity_table_standardization():
    """Verify per-season standardization of returning production and recruiting."""
    df = pd.DataFrame(
        [
            {
                "season": 2024,
                "team": "Georgia",
                "return_percent_ppa": 0.80,
                "recruiting_4yr": 310.0,
                "coach_new": 0,
            },
            {
                "season": 2024,
                "team": "Florida",
                "return_percent_ppa": 0.40,
                "recruiting_4yr": 270.0,
                "coach_new": 1,
            },
        ]
    )

    table = ContinuityTable.from_dataframe(df)
    uga = table.get(2024, "Georgia")
    uf = table.get(2024, "Florida")

    assert uga is not None
    assert uf is not None
    # Georgia has above-average returning production and recruiting
    assert uga.return_std > 0.0
    assert uga.rec_std > 0.0
    assert uga.new_coach == 0.0

    # Florida has below-average returning production, recruiting, and a new coach
    assert uf.return_std < 0.0
    assert uf.rec_std < 0.0
    assert uf.new_coach == 1.0


def test_continuity_table_rejects_2020():
    """Verify that any 2020 input is rejected fail-closed."""
    df = pd.DataFrame(
        [
            {
                "season": 2020,
                "team": "Georgia",
                "return_percent_ppa": 0.70,
                "recruiting_4yr": 300.0,
                "coach_new": 0,
            }
        ]
    )
    with pytest.raises(ValueError, match="2020 season data is strictly excluded"):
        ContinuityTable.from_dataframe(df)


def test_continuity_table_rejects_post_kickoff_timestamp():
    """Verify that preseason context dated after season kickoff is rejected."""
    games = [
        Game(
            season=2024,
            week=1,
            game_id=100,
            kickoff_utc="2024-08-31T16:00:00Z",
            home_team="Georgia",
            away_team="Clemson",
        )
    ]
    # Continuity row timestamped after kickoff
    df = pd.DataFrame(
        [
            {
                "season": 2024,
                "team": "Georgia",
                "return_percent_ppa": 0.75,
                "recruiting_4yr": 300.0,
                "coach_new": 0,
                "effective_at": "2024-09-01T12:00:00Z",
            }
        ]
    )
    with pytest.raises(ValueError, match="dated after kickoff"):
        ContinuityTable.from_dataframe(df, games=games)


def test_continuity_table_requires_kickoffs_when_effective_at_present():
    """Verify that effective_at timestamps without games or kickoffs raises ValueError."""
    df = pd.DataFrame(
        [
            {
                "season": 2024,
                "team": "Georgia",
                "return_percent_ppa": 0.75,
                "recruiting_4yr": 300.0,
                "coach_new": 0,
                "effective_at": "2024-08-15T12:00:00Z",
            }
        ]
    )
    with pytest.raises(
        ValueError, match="neither games nor earliest_kickoffs were supplied"
    ):
        ContinuityTable.from_dataframe(df)


# ---------------------------------------------------------------------------
# Task 3: PreseasonPrior Engine Validation & Math
# ---------------------------------------------------------------------------


def test_preseason_prior_rho_validation():
    """Verify strict validation on rho formats (float broadcast, dict, invalid keys/bounds)."""
    # 1. Valid float
    p_float = PreseasonPrior(rho=0.60)
    assert p_float.resolve_rho("rush_success_rate") == 0.60
    assert p_float.resolve_rho("pass_explosiveness") == 0.60

    # 2. Valid dict with family keys
    p_family = PreseasonPrior(rho={"SR": 0.65, "Expl": 0.45})
    assert p_family.resolve_rho("rush_success_rate") == 0.65
    assert p_family.resolve_rho("pass_success_rate") == 0.65
    assert p_family.resolve_rho("rush_explosiveness") == 0.45
    assert p_family.resolve_rho("pass_explosiveness_margin") == 0.45

    # 3. Valid dict with exact ID override
    p_override = PreseasonPrior(
        rho={"SR": 0.60, "Expl": 0.40, "rush_success_rate": 0.70}
    )
    assert p_override.resolve_rho("rush_success_rate") == 0.70
    assert p_override.resolve_rho("pass_success_rate") == 0.60

    # 4. Unknown key
    with pytest.raises(ValueError, match="Unknown rho key: 'foobar'"):
        PreseasonPrior(rho={"foobar": 0.50})

    # 5. Out of bounds values
    with pytest.raises(ValueError, match="must be in"):
        PreseasonPrior(rho=0.0)
    with pytest.raises(ValueError, match="must be in"):
        PreseasonPrior(rho=1.5)
    with pytest.raises(ValueError, match="must be in"):
        PreseasonPrior(rho={"SR": -0.1, "Expl": 0.5})

    # 6. Incomplete dict missing a family
    with pytest.raises(ValueError, match="rho dict incomplete"):
        PreseasonPrior(rho={"SR": 0.60})


def test_preseason_prior_formula_math():
    """Verify exact numerical blend formula:
    prior_mean = rho^gap * terminal + 0.25*ret + 0.20*rec - 0.15*coach
    """
    cont_records = {
        (2024, "Georgia"): TeamContinuity(
            season=2024,
            team="Georgia",
            return_std=1.2,
            rec_std=1.5,
            new_coach=0.0,
        ),
        (2024, "Florida"): TeamContinuity(
            season=2024,
            team="Florida",
            return_std=-0.8,
            rec_std=0.5,
            new_coach=1.0,
        ),
    }
    cont_table = ContinuityTable(cont_records)

    terminal_seeds = {
        (2023, "Georgia", "offense", "rush_success_rate"): Rating(1.50, 1.0),
        (2023, "Florida", "offense", "rush_success_rate"): Rating(-0.50, 1.0),
    }

    prior_engine = PreseasonPrior(
        rho={"SR": 0.60, "Expl": 0.45},
        beta_ret=0.25,
        beta_rec=0.20,
        beta_coach=-0.15,
        prior_variance=1.0,
        continuity=cont_table,
        terminal_seeds=terminal_seeds,
    )

    # Georgia:
    # terminal_decayed = 0.60^1 * 1.50 = 0.90
    # continuity = 0.25 * 1.2 + 0.20 * 1.5 - 0.15 * 0.0 = 0.30 + 0.30 = 0.60
    # prior_mean = 0.90 + 0.60 = 1.50
    rating_uga, reason_uga = prior_engine.build_prior(
        2024, "Georgia", "offense", "rush_success_rate"
    )
    assert reason_uga is None
    assert math.isclose(rating_uga.mean, 1.50, abs_tol=1e-5)
    assert rating_uga.variance == 1.0

    # Florida:
    # terminal_decayed = 0.60^1 * (-0.50) = -0.30
    # continuity = 0.25 * (-0.8) + 0.20 * (0.5) - 0.15 * 1.0 = -0.20 + 0.10 - 0.15 = -0.25
    # prior_mean = -0.30 - 0.25 = -0.55
    rating_uf, reason_uf = prior_engine.build_prior(
        2024, "Florida", "offense", "rush_success_rate"
    )
    assert reason_uf is None
    assert math.isclose(rating_uf.mean, -0.55, abs_tol=1e-5)
    assert rating_uf.variance == 1.0


def test_preseason_prior_gap2_handling():
    """Verify 2019 -> 2021 gap uses gap=2 with rho^2 decay."""
    terminal_seeds = {
        (2019, "LSU", "offense", "pass_explosiveness"): Rating(2.0, 1.0),
    }
    cont_records = {
        (2021, "LSU"): TeamContinuity(
            season=2021,
            team="LSU",
            return_std=0.0,
            rec_std=0.0,
            new_coach=0.0,
        )
    }
    prior_engine = PreseasonPrior(
        rho=0.50,
        continuity=ContinuityTable(cont_records),
        terminal_seeds=terminal_seeds,
    )

    # 2021 target with 2019 terminal -> gap = 2
    # terminal_decayed = (0.50^2) * 2.0 = 0.25 * 2.0 = 0.50
    rating, reason = prior_engine.build_prior(
        2021, "LSU", "offense", "pass_explosiveness", previous_season=2019
    )
    assert reason is None
    assert math.isclose(rating.mean, 0.50, abs_tol=1e-5)


def test_preseason_prior_missing_input_fallback():
    """Verify fallback to neutral Rating(0.0, 1.0) when inputs are missing."""
    prior_engine = PreseasonPrior(
        rho=0.60,
        continuity=None,
        terminal_seeds={},
        fallback_to_neutral=True,
    )

    # Team not in terminal seeds
    rating, reason = prior_engine.build_prior(
        2024, "NewTeam", "offense", "rush_success_rate"
    )
    assert rating.mean == 0.0
    assert rating.variance == 1.0
    assert reason == "missing_terminal_seed"


# ---------------------------------------------------------------------------
# Task 4: Replay Integration Dry Run
# ---------------------------------------------------------------------------


def test_replay_with_preseason_priors_dry_run():
    """Dry run verifying that fixed_priors emitted by PreseasonPrior integrate into replay_ratings."""
    games = [
        Game(
            season=2024,
            week=1,
            game_id=1,
            kickoff_utc="2024-08-31T16:00:00Z",
            home_team="Georgia",
            away_team="Clemson",
        ),
        # FCS opponent game: Austin Peay has no prior terminal
        Game(
            season=2024,
            week=2,
            game_id=2,
            kickoff_utc="2024-09-07T16:00:00Z",
            home_team="Georgia",
            away_team="Austin Peay",
        ),
    ]

    obs = [
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="Georgia",
            role="offense",
            measurement_id="rush_success_rate",
            value=0.55,
            exposure=35.0,
            available_utc="2024-08-31T23:00:00Z",
            timing_class="historically_reconstructed",
        ),
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="Clemson",
            role="defense",
            measurement_id="rush_success_rate",
            value=0.45,
            exposure=35.0,
            available_utc="2024-08-31T23:00:00Z",
            timing_class="historically_reconstructed",
        ),
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="Clemson",
            role="offense",
            measurement_id="rush_success_rate",
            value=0.35,
            exposure=30.0,
            available_utc="2024-08-31T23:00:00Z",
            timing_class="historically_reconstructed",
        ),
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="Georgia",
            role="defense",
            measurement_id="rush_success_rate",
            value=0.30,
            exposure=30.0,
            available_utc="2024-08-31T23:00:00Z",
            timing_class="historically_reconstructed",
        ),
    ]

    # Pre-computed terminal seeds for FBS teams from 2023
    terminal_seeds = {
        (2023, "Georgia", "offense", "rush_success_rate"): Rating(1.2, 1.0),
        (2023, "Georgia", "defense", "rush_success_rate"): Rating(1.1, 1.0),
        (2023, "Clemson", "offense", "rush_success_rate"): Rating(0.4, 1.0),
        (2023, "Clemson", "defense", "rush_success_rate"): Rating(0.8, 1.0),
    }

    cont_records = {
        (2024, "Georgia"): TeamContinuity(
            season=2024, team="Georgia", return_std=0.5, rec_std=1.2, new_coach=0.0
        ),
        (2024, "Clemson"): TeamContinuity(
            season=2024, team="Clemson", return_std=0.2, rec_std=0.8, new_coach=0.0
        ),
    }

    prior_engine = PreseasonPrior(
        rho=0.60,
        continuity=ContinuityTable(cont_records),
        terminal_seeds=terminal_seeds,
        fallback_to_neutral=True,
    )

    all_teams = {"Georgia", "Clemson", "Austin Peay"}
    fixed_priors, neutral_fallback_keys = prior_engine.build_fixed_priors(
        season=2024,
        measurement_id="rush_success_rate",
        teams=all_teams,
    )

    # Austin Peay should be in neutral_fallback_keys
    assert (2024, "Austin Peay", "offense") in neutral_fallback_keys
    assert (2024, "Austin Peay", "defense") in neutral_fallback_keys
    # Georgia and Clemson should be in fixed_priors
    assert (2024, "Georgia", "offense") in fixed_priors
    assert (2024, "Clemson", "defense") in fixed_priors

    # Run replay
    design = ExposureDesign("test_exposure_design")
    states = replay(
        games=games,
        observations=obs,
        design=design,
        measurement_id="rush_success_rate",
        timing_class="historically_reconstructed",
        fixed_priors=fixed_priors,
        neutral_fallback_keys=neutral_fallback_keys,
    )

    assert len(states) > 0
    # Verify pregame states carry initialized prior means
    uga_states = [
        s
        for s in states
        if s.team == "Georgia" and s.game_id == 1 and s.role == "offense"
    ]
    assert len(uga_states) == 1
    assert math.isclose(
        uga_states[0].prior.mean, fixed_priors[(2024, "Georgia", "offense")].mean
    )
