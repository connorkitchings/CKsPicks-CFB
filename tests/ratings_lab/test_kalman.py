"""Unit and integration tests for V6 Kalman Filter & Retrospective Re-anchoring (Phase 3)."""

from __future__ import annotations

import math
from pathlib import Path

from cks_picks_cfb.ratings_lab.contracts import Game, Observation, Rating
from cks_picks_cfb.ratings_lab.kalman import (
    FCS_COMPOSITE_NAME,
    FCS_PINNED_PRIOR,
    KalmanExposureDesign,
)
from cks_picks_cfb.ratings_lab.reanchoring import (
    batch_refilter_states,
    filter_cutoff_games,
    reanchor_schedule_graph,
)
from cks_picks_cfb.ratings_lab.replay import replay
from cks_picks_cfb.ratings_lab.updaters import load_candidate_configs

# ---------------------------------------------------------------------------
# Task 1: Kalman Exposure Filter Math & Stability
# ---------------------------------------------------------------------------


def test_kalman_exposure_scaling_and_update():
    """Verify measurement noise scales inversely with exposure n_t, and gain K_t updates state."""
    design = KalmanExposureDesign(
        candidate_id="test_kalman_v1",
        q=0.02,
        sigma2_noise=1.0,
    )

    prior = Rating(mean=0.0, variance=1.0)

    # Observation with n_t = 50 plays, value = 0.50
    obs_high_n = [
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="Georgia",
            role="offense",
            measurement_id="rush_success_rate",
            value=0.50,
            exposure=50.0,
            available_utc="2024-09-01T06:00:00Z",
            timing_class="historically_reconstructed",
        )
    ]

    rating_high, expl_high = design.estimate(prior, obs_high_n)
    # v_pred = 1.0 + 0.02 = 1.02
    # R_t = 1.0 / 50.0 = 0.02
    # K_t = 1.02 / (1.02 + 0.02) = 1.02 / 1.04 ≈ 0.9808
    # m = 0.0 + K_t * 0.50 ≈ 0.4904
    # v = (1 - K_t) * 1.02 ≈ 0.0196
    step_high = expl_high["evidence_contributions"][0]
    assert math.isclose(step_high["measurement_noise"], 0.02, rel_tol=1e-4)
    assert step_high["kalman_gain"] > 0.95
    assert math.isclose(rating_high.mean, 0.4904, abs_tol=1e-3)
    assert rating_high.variance < 0.05

    # Observation with low n_t = 5 plays, value = 0.50
    obs_low_n = [
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="Georgia",
            role="offense",
            measurement_id="rush_success_rate",
            value=0.50,
            exposure=5.0,
            available_utc="2024-09-01T06:00:00Z",
            timing_class="historically_reconstructed",
        )
    ]

    rating_low, expl_low = design.estimate(prior, obs_low_n)
    # R_t = 1.0 / 5.0 = 0.20
    # K_t = 1.02 / (1.02 + 0.20) = 1.02 / 1.22 ≈ 0.836
    step_low = expl_low["evidence_contributions"][0]
    assert math.isclose(step_low["measurement_noise"], 0.20, rel_tol=1e-4)
    assert step_low["kalman_gain"] < step_high["kalman_gain"]
    assert rating_low.mean < rating_high.mean


def test_kalman_missing_observation_skips_update():
    """Verify missing observations skip measurement update, keep mean, and expand variance by q."""
    design = KalmanExposureDesign(
        candidate_id="test_kalman_missing_v1",
        q=0.03,
        sigma2_noise=1.0,
    )

    prior = Rating(mean=1.20, variance=0.20)

    # Observation with None value (e.g. game missing data)
    obs_missing = [
        Observation(
            season=2024,
            week=1,
            game_id=10,
            team="Georgia",
            role="offense",
            measurement_id="rush_success_rate",
            value=None,
            exposure=0.0,
            available_utc="2024-09-01T06:00:00Z",
            timing_class="historically_reconstructed",
            missing_reason="postponed_or_missing",
        )
    ]

    rating, expl = design.estimate(prior, obs_missing)
    # Mean must remain exactly 1.20 (no zero-imputation!)
    assert math.isclose(rating.mean, 1.20, abs_tol=1e-6)
    # Variance must expand by q = 0.03 -> 0.20 + 0.03 = 0.23
    assert math.isclose(rating.variance, 0.23, abs_tol=1e-6)
    assert expl["evidence_contributions"][0]["skipped"] is True


# ---------------------------------------------------------------------------
# Task 2: FCS Composite Anchor & Bounded Innovation
# ---------------------------------------------------------------------------


def test_fcs_downweight_and_innovation_cap():
    """Verify FBS playing FCS applies 25% exposure downweight and 1.5 innovation cap."""
    fcs_game_id = 999
    design = KalmanExposureDesign(
        candidate_id="test_kalman_fcs",
        q=0.02,
        sigma2_noise=1.0,
        fcs_exposure_weight=0.25,
        fcs_innovation_cap=1.5,
        fcs_game_ids=frozenset([fcs_game_id]),
    )

    prior = Rating(mean=0.0, variance=0.50)

    # FBS blowout: huge observation value = 4.0 (innovation = 4.0 - 0.0 = 4.0)
    obs_fcs_blowout = [
        Observation(
            season=2024,
            week=1,
            game_id=fcs_game_id,
            team="Georgia",
            role="offense",
            measurement_id="rush_explosiveness",
            value=4.0,
            exposure=20.0,
            available_utc="2024-09-01T06:00:00Z",
            timing_class="historically_reconstructed",
        )
    ]

    rating_fcs, expl_fcs = design.estimate(prior, obs_fcs_blowout)
    step_fcs = expl_fcs["evidence_contributions"][0]

    # 1. Effective exposure down-weight: 20 * 0.25 = 5.0 -> R_t = 1.0 / (0.25 * 20) = 0.20
    assert step_fcs["is_fcs"] is True
    assert math.isclose(
        step_fcs["measurement_noise"], 1.0 / (0.25 * 20.0), rel_tol=1e-4
    )

    # 2. Innovation capped at 1.5
    assert step_fcs["innovation"] == 4.0
    assert step_fcs["capped_innovation"] == 1.5
    assert step_fcs["was_capped"] is True

    # Same blowout in an FBS game: innovation must NOT be capped
    fbs_game_id = 888
    obs_fbs_blowout = [
        Observation(
            season=2024,
            week=1,
            game_id=fbs_game_id,
            team="Georgia",
            role="offense",
            measurement_id="rush_explosiveness",
            value=4.0,
            exposure=20.0,
            available_utc="2024-09-01T06:00:00Z",
            timing_class="historically_reconstructed",
        )
    ]

    rating_fbs, expl_fbs = design.estimate(prior, obs_fbs_blowout)
    step_fbs = expl_fbs["evidence_contributions"][0]

    assert step_fbs["is_fcs"] is False
    assert math.isclose(step_fbs["measurement_noise"], 1.0 / 20.0, rel_tol=1e-4)
    assert step_fbs["innovation"] == 4.0
    assert step_fbs["capped_innovation"] == 4.0
    assert step_fbs["was_capped"] is False
    assert rating_fbs.mean > rating_fcs.mean


def test_fcs_composite_node_pinned():
    """Verify FCS_COMPOSITE itself returns pinned prior Rating(-2.0, 0.5) and never updates."""
    design = KalmanExposureDesign(candidate_id="test_kalman_fcs_node")
    prior = Rating(mean=0.0, variance=1.0)

    obs = [
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team=FCS_COMPOSITE_NAME,
            role="offense",
            measurement_id="rush_success_rate",
            value=0.80,
            exposure=40.0,
            available_utc="2024-09-01T06:00:00Z",
            timing_class="historically_reconstructed",
        )
    ]

    rating, expl = design.estimate(prior, obs)
    assert rating.mean == FCS_PINNED_PRIOR.mean
    assert rating.variance == FCS_PINNED_PRIOR.variance
    assert expl["is_fcs_composite"] is True


# ---------------------------------------------------------------------------
# Task 3: Retrospective Re-anchoring & Schedule Graph
# ---------------------------------------------------------------------------


def test_filter_cutoff_games_causality():
    """Verify causality filter strictly excludes games after cutoff + buffer."""
    games = [
        Game(
            season=2024,
            week=1,
            game_id=1,
            kickoff_utc="2024-08-31T16:00:00Z",  # + 6h = 22:00:00Z
            home_team="Georgia",
            away_team="Clemson",
        ),
        Game(
            season=2024,
            week=2,
            game_id=2,
            kickoff_utc="2024-09-07T16:00:00Z",
            home_team="Georgia",
            away_team="Tennessee",
        ),
    ]

    # Cutoff at 2024-09-01T00:00:00Z: Game 1 is eligible, Game 2 is not
    admissible = filter_cutoff_games(games, cutoff_utc="2024-09-01T00:00:00Z")
    assert len(admissible) == 1
    assert admissible[0].game_id == 1

    # Cutoff before Game 1 buffer: 0 games admissible
    early = filter_cutoff_games(games, cutoff_utc="2024-08-31T20:00:00Z")
    assert len(early) == 0


def test_reanchor_schedule_graph_4pass_and_shrinkage():
    """Verify 4-pass schedule opponent adjustment with early-season shrinkage."""
    games = [
        Game(
            season=2024,
            week=1,
            game_id=1,
            kickoff_utc="2024-08-31T16:00:00Z",
            home_team="TeamStrong",
            away_team="TeamWeak",
        )
    ]

    # Raw observation: TeamStrong scored high (0.60), TeamWeak allowed high (0.60)
    raw_obs = [
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="TeamStrong",
            role="offense",
            measurement_id="rush_success_rate",
            value=0.60,
            exposure=30.0,
            available_utc="2024-08-31T23:00:00Z",
            timing_class="historically_reconstructed",
        ),
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="TeamWeak",
            role="defense",
            measurement_id="rush_success_rate",
            value=0.60,
            exposure=30.0,
            available_utc="2024-08-31T23:00:00Z",
            timing_class="historically_reconstructed",
        ),
    ]

    priors = {
        (2024, "TeamStrong", "offense"): Rating(1.0, 1.0),
        (2024, "TeamStrong", "defense"): Rating(1.0, 1.0),
        # TeamWeak defense has poor prior (-1.0)
        (2024, "TeamWeak", "defense"): Rating(-1.0, 1.0),
        (2024, "TeamWeak", "offense"): Rating(-1.0, 1.0),
    }

    # Week 1: early season shrinkage w_1 = 1 / (1 + 2) = 1/3
    reanchored_w1 = reanchor_schedule_graph(
        games=games,
        observations=raw_obs,
        priors=priors,
        week=1,
        num_passes=4,
        shrinkage_k=2.0,
    )

    # Facing a weak defense (-1.0) adjusts TeamStrong's raw performance downward
    # Adjusted < Raw (0.60)
    ts_adj = next(o for o in reanchored_w1 if o.team == "TeamStrong")
    assert ts_adj.value < 0.60

    # Week 3: full adjustment w_3 = 1.0 (stronger adjustment effect than week 1)
    reanchored_w3 = reanchor_schedule_graph(
        games=games,
        observations=raw_obs,
        priors=priors,
        week=3,
        num_passes=4,
        shrinkage_k=2.0,
    )
    ts_adj_w3 = next(o for o in reanchored_w3 if o.team == "TeamStrong")
    # With full weight (no shrinkage to raw), adjustment is more pronounced
    assert ts_adj_w3.value < ts_adj.value


def test_batch_refilter_states():
    """Verify batch_refilter_states produces frozen RatingState objects for week T."""
    games = [
        Game(
            season=2024,
            week=1,
            game_id=1,
            kickoff_utc="2024-08-31T16:00:00Z",
            home_team="Georgia",
            away_team="Clemson",
        )
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
            exposure=30.0,
            available_utc="2024-08-31T23:00:00Z",
            timing_class="historically_reconstructed",
        )
    ]
    priors = {
        (2024, "Georgia", "offense"): Rating(1.0, 1.0),
        (2024, "Georgia", "defense"): Rating(1.0, 1.0),
        (2024, "Clemson", "offense"): Rating(0.5, 1.0),
        (2024, "Clemson", "defense"): Rating(0.5, 1.0),
    }
    design = KalmanExposureDesign("test_kalman_batch")

    states = batch_refilter_states(
        games=games,
        reanchored_obs=obs,
        priors=priors,
        design=design,
        week=1,
        cutoff_utc="2024-09-01T00:00:00Z",
    )

    assert len(states) == 4  # 2 teams x 2 roles
    uga_off = next(s for s in states if s.team == "Georgia" and s.role == "offense")
    assert uga_off.week == 1
    assert uga_off.usable_exposure == 30.0
    assert uga_off.rating.mean > 0.0


# ---------------------------------------------------------------------------
# Task 4: Replay & YAML Candidate Integration
# ---------------------------------------------------------------------------


def test_replay_with_kalman_design():
    """Verify KalmanExposureDesign runs cleanly through standard replay() engine."""
    games = [
        Game(
            season=2024,
            week=1,
            game_id=1,
            kickoff_utc="2024-08-31T16:00:00Z",
            home_team="Georgia",
            away_team="Clemson",
        )
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
            exposure=30.0,
            available_utc="2024-08-31T23:00:00Z",
            timing_class="historically_reconstructed",
        )
    ]
    design = KalmanExposureDesign("kalman_replay_test")
    states = replay(
        games=games,
        observations=obs,
        design=design,
        measurement_id="rush_success_rate",
    )
    assert len(states) > 0


def test_yaml_candidate_loading_kalman():
    """Verify load_candidate_configs parses kalman_exposure YAML configs with family mappings."""
    configs_dir = Path("conf/research/candidates")
    configs = load_candidate_configs(configs_dir)

    assert "kalman_exposure_v1" in configs
    kalman_candidate = configs["kalman_exposure_v1"]
    assert isinstance(kalman_candidate, KalmanExposureDesign)
    assert kalman_candidate.candidate_id == "kalman_exposure_v1"
    assert kalman_candidate.q == {"SR": 0.02, "Expl": 0.05, "Finish": 0.03}
    assert kalman_candidate.sigma2_noise == {"SR": 0.25, "Expl": 4.00, "Finish": 1.00}
    assert kalman_candidate.resolve_q("rush_success_rate") == 0.02
    assert kalman_candidate.resolve_q("rush_explosiveness") == 0.05
    assert kalman_candidate.resolve_q("finish_points_per_opp") == 0.03
    assert kalman_candidate.resolve_sigma2("rush_success_rate") == 0.25
    assert kalman_candidate.resolve_sigma2("rush_explosiveness") == 4.00
    assert kalman_candidate.resolve_sigma2("finish_points_per_opp") == 1.00
    assert kalman_candidate.fcs_exposure_weight == 0.25
    assert kalman_candidate.fcs_innovation_cap == 1.5


def test_batch_refilter_states_multi_mid_separation():
    """Verify batch_refilter_states keeps multi-ID streams separated without crosstalk."""
    games = [
        Game(
            season=2024,
            week=1,
            game_id=1,
            kickoff_utc="2024-08-31T16:00:00Z",
            home_team="Georgia",
            away_team="Clemson",
        )
    ]
    # Feed mixed observations: Georgia has both SR and Expl
    obs = [
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="Georgia",
            role="offense",
            measurement_id="rush_success_rate",
            value=0.55,
            exposure=30.0,
            available_utc="2024-08-31T23:00:00Z",
            timing_class="historically_reconstructed",
        ),
        Observation(
            season=2024,
            week=1,
            game_id=1,
            team="Georgia",
            role="offense",
            measurement_id="rush_explosiveness",
            value=1.50,
            exposure=12.0,
            available_utc="2024-08-31T23:00:00Z",
            timing_class="historically_reconstructed",
        ),
    ]
    priors = {
        (2024, "Georgia", "offense", "rush_success_rate"): Rating(0.5, 1.0),
        (2024, "Georgia", "offense", "rush_explosiveness"): Rating(1.2, 1.0),
    }
    design = KalmanExposureDesign(
        candidate_id="test_multi_mid",
        q={"SR": 0.02, "Expl": 0.05},
        sigma2_noise={"SR": 0.25, "Expl": 4.00},
    )

    states = batch_refilter_states(
        games=games,
        reanchored_obs=obs,
        priors=priors,
        design=design,
        week=1,
        cutoff_utc="2024-09-01T00:00:00Z",
    )

    # 2 teams x 2 roles x 2 mids = 8 states
    assert len(states) == 8

    uga_sr = next(
        s
        for s in states
        if s.team == "Georgia"
        and s.role == "offense"
        and s.explanation.get("measurement_id") == "rush_success_rate"
    )
    uga_expl = next(
        s
        for s in states
        if s.team == "Georgia"
        and s.role == "offense"
        and s.explanation.get("measurement_id") == "rush_explosiveness"
    )

    assert uga_sr.usable_exposure == 30.0
    assert uga_expl.usable_exposure == 12.0
    # Prior and posterior separated per ID
    assert uga_sr.prior.mean == 0.5
    assert uga_expl.prior.mean == 1.2
    assert uga_sr.explanation["measurement_id"] == "rush_success_rate"
    assert uga_expl.explanation["measurement_id"] == "rush_explosiveness"


def test_kalman_mapping_validation():
    """Verify KalmanExposureDesign strictly validates Mapping parameters."""
    import pytest

    # Unknown family/ID key in q
    with pytest.raises(ValueError, match="Unknown key in q mapping"):
        KalmanExposureDesign("test_bad_q_key", q={"unknown_factor": 0.02})

    # Negative value in q
    with pytest.raises(ValueError, match="must be positive and finite"):
        KalmanExposureDesign("test_neg_q", q={"SR": -0.02})

    # Non-numeric value in q
    with pytest.raises(ValueError, match="must be numeric"):
        KalmanExposureDesign("test_nan_q", q={"SR": "abc"})

    # Unknown key in sigma2_noise
    with pytest.raises(ValueError, match="Unknown key in sigma2_noise mapping"):
        KalmanExposureDesign("test_bad_s2_key", sigma2_noise={"bad_id": 1.0})

    # Zero/negative value in sigma2_noise
    with pytest.raises(ValueError, match="must be positive and finite"):
        KalmanExposureDesign("test_zero_s2", sigma2_noise={"SR": 0.0})
