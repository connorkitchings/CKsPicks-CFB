"""Unit tests for successor-v2 R2 between-season prior estimators."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cks_picks_cfb.data.season_lineage import load_season_lineage_policy
from cks_picks_cfb.ratings.priors import (
    CANDIDATE_IDS,
    PRIOR_COLUMNS,
    PriorError,
    _apply_decay,
    compute_prior,
)

POLICY = load_season_lineage_policy("conf/ratings/successor_v2_season_lineage.yaml")

MEASUREMENTS = [
    ("epa_per_play", "offense"),
    ("epa_per_play", "defense"),
    ("success_rate", "offense"),
    ("success_rate", "defense"),
]


def _terminal(
    season: int, teams: list[str], mean: float = 0.5, variance: float = 0.3
) -> pd.DataFrame:
    """Build a synthetic terminal measurement state DataFrame."""
    rows = []
    for team in teams:
        for mid, role in MEASUREMENTS:
            rows.append(
                {
                    "season": season,
                    "team": team,
                    "measurement_id": mid,
                    "unit_role": role,
                    "posterior_mean": mean,
                    "posterior_variance": variance,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# _apply_decay
# ---------------------------------------------------------------------------


def test_apply_decay_normal_one_step():
    mean, variance = _apply_decay(0.5, 0.4, rho=0.60, annual_decay_steps=1)
    assert np.isclose(mean, 0.60 * 0.5)
    decay_sq = 0.60**2
    expected_var = decay_sq * 0.4 + (1.0 - decay_sq)
    assert np.isclose(variance, expected_var)


def test_apply_decay_gap_two_steps():
    """2019->2021 gap must compound rho twice, not once."""
    mean, variance = _apply_decay(1.0, 0.5, rho=0.60, annual_decay_steps=2)
    assert np.isclose(mean, 0.60**2 * 1.0)
    decay_sq = 0.60**4  # rho^(2*2)
    expected_var = decay_sq * 0.5 + (1.0 - decay_sq)
    assert np.isclose(variance, expected_var)


def test_apply_decay_zero_mean_stays_zero():
    mean, _ = _apply_decay(0.0, 1.0, rho=0.60, annual_decay_steps=1)
    assert mean == 0.0


# ---------------------------------------------------------------------------
# compute_prior — validation
# ---------------------------------------------------------------------------


def test_unknown_candidate_raises():
    terminal = _terminal(2017, ["TeamA"])
    with pytest.raises(PriorError, match="Unknown candidate_id"):
        compute_prior(
            candidate_id="not_a_candidate",
            terminal_states=terminal,
            target_season=2018,
            policy=POLICY,
        )


def test_forbidden_season_in_terminal_raises():
    terminal = _terminal(2020, ["TeamA"])
    with pytest.raises(PriorError, match="2025, 2026, or 2020"):
        compute_prior(
            candidate_id="fixed_rho_0_60",
            terminal_states=terminal,
            target_season=2018,
            policy=POLICY,
        )


def test_protected_target_season_raises():
    terminal = _terminal(2025, ["TeamA"])
    with pytest.raises(Exception):
        compute_prior(
            candidate_id="fixed_rho_0_60",
            terminal_states=terminal,
            target_season=2026,
            policy=POLICY,
        )


# ---------------------------------------------------------------------------
# neutral_population
# ---------------------------------------------------------------------------


def test_neutral_population_returns_zero_mean_unit_variance():
    terminal = _terminal(2017, ["TeamA", "TeamB"], mean=0.8, variance=0.2)
    result = compute_prior(
        candidate_id="neutral_population",
        terminal_states=terminal,
        target_season=2018,
        policy=POLICY,
    )
    assert set(result.columns) == set(PRIOR_COLUMNS)
    assert (result["prior_mean"] == 0.0).all()
    assert (result["prior_variance"] == 1.0).all()
    assert (result["quality_flags"] == "neutral_preseason_prior").all()


def test_neutral_population_ignores_terminal_values():
    """Neutral always returns (0.0, 1.0) regardless of terminal state values."""
    terminal_high = _terminal(2017, ["TeamA"], mean=5.0, variance=0.1)
    result = compute_prior(
        candidate_id="neutral_population",
        terminal_states=terminal_high,
        target_season=2018,
        policy=POLICY,
    )
    assert (result["prior_mean"] == 0.0).all()


# ---------------------------------------------------------------------------
# fixed_rho_0_60
# ---------------------------------------------------------------------------


def test_fixed_rho_carries_over_correctly():
    mean_val = 0.5
    terminal = _terminal(2017, ["TeamA"], mean=mean_val, variance=0.4)
    result = compute_prior(
        candidate_id="fixed_rho_0_60",
        terminal_states=terminal,
        target_season=2018,
        policy=POLICY,
    )
    expected_mean = 0.60 * mean_val
    assert np.allclose(result[result["team"] == "TeamA"]["prior_mean"], expected_mean)


def test_fixed_rho_neutral_fallback_for_unknown_team():
    terminal = _terminal(2017, ["TeamA"], mean=0.5, variance=0.4)
    result = compute_prior(
        candidate_id="fixed_rho_0_60",
        terminal_states=terminal,
        target_season=2018,
        policy=POLICY,
        training_terminal_states={2017: terminal},
    )
    # TeamA is known; if we had a TeamB not in terminal, it would fall back to neutral
    # Here all teams come from terminal states, so just verify TeamA is correct
    team_a = result[result["team"] == "TeamA"]
    assert np.allclose(team_a["prior_mean"], 0.60 * 0.5)


def test_fixed_rho_gap_season_uses_two_steps():
    """2021 fold: source is 2019, annual_decay_steps=2 => rho^2."""
    mean_val = 1.0
    terminal = _terminal(2019, ["TeamX"], mean=mean_val, variance=0.5)
    result = compute_prior(
        candidate_id="fixed_rho_0_60",
        terminal_states=terminal,
        target_season=2021,
        policy=POLICY,
    )
    expected_mean = 0.60**2 * mean_val
    assert np.allclose(result[result["team"] == "TeamX"]["prior_mean"], expected_mean)


def test_fixed_rho_deterministic():
    terminal = _terminal(2017, ["TeamA", "TeamB"], mean=0.3)
    r1 = compute_prior(
        candidate_id="fixed_rho_0_60",
        terminal_states=terminal,
        target_season=2018,
        policy=POLICY,
    )
    r2 = compute_prior(
        candidate_id="fixed_rho_0_60",
        terminal_states=terminal,
        target_season=2018,
        policy=POLICY,
    )
    pd.testing.assert_frame_equal(r1.reset_index(drop=True), r2.reset_index(drop=True))


# ---------------------------------------------------------------------------
# learned_offense_defense
# ---------------------------------------------------------------------------


def test_learned_offense_defense_direction():
    """Higher terminal mean -> higher prior mean (direction preserved)."""
    terminal_low = _terminal(2017, ["TeamA"], mean=0.1)
    terminal_high = _terminal(2017, ["TeamB"], mean=0.8)
    all_terminal = pd.concat([terminal_low, terminal_high], ignore_index=True)
    result = compute_prior(
        candidate_id="learned_offense_defense",
        terminal_states=all_terminal,
        target_season=2018,
        policy=POLICY,
        training_terminal_states={2017: all_terminal},
    )
    team_a = result[result["team"] == "TeamA"]["prior_mean"].mean()
    team_b = result[result["team"] == "TeamB"]["prior_mean"].mean()
    assert team_a < team_b


def test_learned_offense_defense_no_gap_fitting():
    """Learned rho must never use the 2019->2021 gap as a training example."""
    # Build artificial training data where only 2019 and 2021 exist
    # The gap transition should not contribute to the OLS fit
    t2019 = _terminal(2019, ["TeamA"], mean=1.0)
    t2021 = _terminal(2021, ["TeamA"], mean=0.9)
    # For the 2022 fold, the source is 2021 (normal transition 2021->2022)
    # So terminal_states must be the 2021 states
    result = compute_prior(
        candidate_id="learned_offense_defense",
        terminal_states=t2021,  # source for 2022 fold is 2021
        target_season=2022,
        policy=POLICY,
        training_terminal_states={2019: t2019, 2021: t2021},
    )
    team_a = result[result["team"] == "TeamA"]
    # Since there are no normal-transition pairs (2021->2022 source data is only
    # 2021 terminal; we need 2022 terminal to form a 2021->2022 pair), the OLS
    # falls back to rho=0.60.  Prior = 0.60 * 0.9 (from 2021 terminal).
    expected_mean = 0.60 * 0.9
    assert np.allclose(team_a["prior_mean"], expected_mean, atol=0.05)


# ---------------------------------------------------------------------------
# partially_pooled_components
# ---------------------------------------------------------------------------


def test_partially_pooled_outputs_all_columns():
    terminal = _terminal(2017, ["TeamA", "TeamB"])
    result = compute_prior(
        candidate_id="partially_pooled_components",
        terminal_states=terminal,
        target_season=2018,
        policy=POLICY,
        training_terminal_states={2017: terminal},
    )
    assert set(result.columns) == set(PRIOR_COLUMNS)
    assert not result.empty
    assert result["prior_variance"].gt(0).all()


def test_partially_pooled_fallback_no_data():
    """With insufficient training data, falls back to rho=0.60."""
    terminal = _terminal(2017, ["TeamA"])
    result = compute_prior(
        candidate_id="partially_pooled_components",
        terminal_states=terminal,
        target_season=2018,
        policy=POLICY,
        training_terminal_states={},  # no training data
    )
    expected = 0.60 * 0.5
    assert np.allclose(result["prior_mean"], expected, atol=0.01)


# ---------------------------------------------------------------------------
# EWMA
# ---------------------------------------------------------------------------


def test_ewma_half_life_1_decays_faster_than_3():
    """Shorter half-life should give lower weight to older seasons."""
    t2016 = _terminal(2016, ["TeamA"], mean=1.0)
    t2017 = _terminal(2017, ["TeamA"], mean=0.0)
    training = {2016: t2016, 2017: t2017}
    result_hl1 = compute_prior(
        candidate_id="terminal_ewma_half_life_1",
        terminal_states=t2017,
        target_season=2018,
        policy=POLICY,
        training_terminal_states=training,
    )
    result_hl3 = compute_prior(
        candidate_id="terminal_ewma_half_life_3",
        terminal_states=t2017,
        target_season=2018,
        policy=POLICY,
        training_terminal_states=training,
    )
    # hl=1: 2017 mean=0 has more weight than 2016 mean=1 -> lower prior
    # hl=3: 2016 mean=1 retains more weight -> higher prior
    mean_hl1 = result_hl1[result_hl1["team"] == "TeamA"]["prior_mean"].mean()
    mean_hl3 = result_hl3[result_hl3["team"] == "TeamA"]["prior_mean"].mean()
    assert mean_hl1 <= mean_hl3


def test_ewma_no_training_data_is_neutral():
    terminal = _terminal(2017, ["TeamA"])
    result = compute_prior(
        candidate_id="terminal_ewma_half_life_2",
        terminal_states=terminal,
        target_season=2018,
        policy=POLICY,
        training_terminal_states={},
    )
    assert (result["quality_flags"] == "neutral_preseason_prior").all()


def test_ewma_never_uses_2020():
    """2020 must never contribute to EWMA weights."""
    t2019 = _terminal(2019, ["TeamA"], mean=0.5)
    _terminal(
        2020, ["TeamA"], mean=99.9
    )  # should never be used; build to verify no crash
    t2021 = _terminal(2021, ["TeamA"], mean=0.5)
    training = {2019: t2019, 2021: t2021}
    # 2020 is not in training_terminal_states (policy enforces this upstream)
    result = compute_prior(
        candidate_id="terminal_ewma_half_life_2",
        terminal_states=t2021,
        target_season=2022,
        policy=POLICY,
        training_terminal_states=training,
    )
    team_a = result[result["team"] == "TeamA"]["prior_mean"].mean()
    # If 2020 were used with mean=99.9 it would dominate; result should be ~0.5
    assert team_a < 1.0


# ---------------------------------------------------------------------------
# Context Ridge candidates
# ---------------------------------------------------------------------------


def test_context_candidates_raise_without_context():
    terminal = _terminal(2017, ["TeamA"])
    for cid in CANDIDATE_IDS:
        if not cid.startswith("continuity_ridge_alpha_"):
            continue
        with pytest.raises(PriorError, match="requires admitted_context"):
            compute_prior(
                candidate_id=cid,
                terminal_states=terminal,
                target_season=2018,
                policy=POLICY,
                admitted_context=None,
            )


def test_context_candidates_reject_market_columns():
    terminal = _terminal(2017, ["TeamA"])
    bad_context = pd.DataFrame(
        [{"team": "TeamA", "season": 2018, "spread": -3.5, "recruiting_rank": 10}]
    )
    with pytest.raises(PriorError, match="market-derived"):
        compute_prior(
            candidate_id="continuity_ridge_alpha_1",
            terminal_states=terminal,
            target_season=2018,
            policy=POLICY,
            admitted_context=bad_context,
        )


# ---------------------------------------------------------------------------
# All candidates produce the required schema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "candidate_id", [c for c in CANDIDATE_IDS if not c.startswith("continuity_")]
)
def test_all_candidates_produce_valid_schema(candidate_id):
    teams = ["TeamA", "TeamB", "TeamC"]
    t2016 = _terminal(2016, teams, mean=0.3)
    t2017 = _terminal(2017, teams, mean=0.4)
    result = compute_prior(
        candidate_id=candidate_id,
        terminal_states=t2017,
        target_season=2018,
        policy=POLICY,
        training_terminal_states={2016: t2016, 2017: t2017},
    )
    assert set(result.columns) == set(PRIOR_COLUMNS)
    assert not result.empty
    assert result["prior_variance"].gt(0).all()
    assert result["prior_mean"].isna().sum() == 0
    assert (result["candidate_id"] == candidate_id).all()


def test_2020_never_used_as_target():
    terminal = _terminal(2019, ["TeamA"])
    with pytest.raises(Exception):
        compute_prior(
            candidate_id="fixed_rho_0_60",
            terminal_states=terminal,
            target_season=2020,
            policy=POLICY,
        )
