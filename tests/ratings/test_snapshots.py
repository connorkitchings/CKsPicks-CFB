"""Opponent-adjustment and pregame snapshot point-in-time tests (Task 3)."""

from __future__ import annotations

import pandas as pd
import pytest
from helpers import AS_OF, simple_league

from cks_picks_cfb.ratings.contracts import load_measurement_config
from cks_picks_cfb.ratings.observations import build_measurement_observations
from cks_picks_cfb.ratings.snapshots import _adjust_measurement, build_pregame_snapshots

CONFIG = load_measurement_config("conf/ratings/measurement_baseline_v1.yaml")


def _observations(league=None):
    league = league or simple_league()
    return build_measurement_observations(
        byplay=league["byplay"],
        drives=league["drives"],
        games=league["games"],
        outcomes=league["outcomes"],
        reconciled_team_game=league["reconciled_team_game"],
        config=CONFIG,
        as_of=AS_OF,
        code_sha="codesha",
        config_sha="configsha",
        parent_ref_shas="aaa;bbb",
    ).frame


def _snapshots(observations, league=None):
    league = league or simple_league()
    return build_pregame_snapshots(
        observations=observations,
        games=league["games"],
        config=CONFIG,
        code_sha="codesha",
        config_sha="configsha",
        parent_observation_version_id="obsver",
        parent_ref_shas="aaa;bbb",
    ).frame


def _row(frame, **filters):
    mask = pd.Series(True, index=frame.index)
    for column, value in filters.items():
        mask &= frame[column] == value
    matches = frame[mask]
    assert len(matches) == 1, f"expected one row for {filters}, got {len(matches)}"
    return matches.iloc[0]


def test_adjustment_iteration_one_matches_hand_computed_recurrence():
    rows = pd.DataFrame(
        [
            {
                "game_id": 1,
                "team": "A",
                "opponent": "B",
                "unit_role": "offense",
                "numerator": 1.0,
                "denominator": 10.0,
            },
            {
                "game_id": 1,
                "team": "B",
                "opponent": "A",
                "unit_role": "defense",
                "numerator": 2.0,
                "denominator": 10.0,
            },
            {
                "game_id": 1,
                "team": "B",
                "opponent": "A",
                "unit_role": "offense",
                "numerator": 3.0,
                "denominator": 10.0,
            },
            {
                "game_id": 1,
                "team": "A",
                "opponent": "B",
                "unit_role": "defense",
                "numerator": 0.5,
                "denominator": 10.0,
            },
        ]
    )
    offense, defense = _adjust_measurement(rows, iterations=1)
    raw_off_a, raw_off_b = 0.10, 0.30
    raw_def_a, raw_def_b = 0.05, 0.20
    center_off = (raw_off_a + raw_off_b) / 2
    center_def = (raw_def_a + raw_def_b) / 2
    assert offense["A"].adjusted == pytest.approx(raw_off_a - (raw_def_b - center_def))
    assert offense["B"].adjusted == pytest.approx(raw_off_b - (raw_def_a - center_def))
    assert defense["A"].adjusted == pytest.approx(raw_def_a - (raw_off_b - center_off))
    assert defense["B"].adjusted == pytest.approx(raw_def_b - (raw_off_a - center_off))
    assert offense["A"].league_center == pytest.approx(center_def)
    assert offense["A"].schedule_strength == pytest.approx(
        offense["A"].raw - offense["A"].adjusted
    )


def test_adjustment_is_deterministic_and_converges_to_symmetric_solution():
    rows = pd.DataFrame(
        [
            {
                "game_id": 1,
                "team": "A",
                "opponent": "B",
                "unit_role": "offense",
                "numerator": 1.0,
                "denominator": 10.0,
            },
            {
                "game_id": 1,
                "team": "B",
                "opponent": "A",
                "unit_role": "defense",
                "numerator": 2.0,
                "denominator": 10.0,
            },
        ]
    )
    first = _adjust_measurement(rows, iterations=4)
    second = _adjust_measurement(rows, iterations=4)
    assert first[0]["A"].adjusted == second[0]["A"].adjusted
    lone_league = first[0]["A"]
    assert lone_league.adjusted == pytest.approx(lone_league.raw)


def test_first_game_teams_get_explicit_missing_state_without_priors():
    snapshots = _snapshots(_observations())
    week_one = _row(
        snapshots,
        season=2025,
        as_of_game_id=1,
        team="Alpha",
        measurement_id="epa_per_play",
        unit_role="offense",
    )
    assert week_one["coverage_status"] == "missing"
    assert week_one["missing_reason"] == "no_eligible_evidence"
    assert week_one["games_exposure"] == 0
    assert week_one["raw_aggregate"] is None or pd.isna(week_one["raw_aggregate"])
    assert week_one["adjustment_method"] == "iterative_additive_league_centered"
    assert week_one["adjustment_iteration"] == 4


def test_snapshot_for_week_two_uses_only_week_one_evidence():
    snapshots = _snapshots(_observations())
    week_two = _row(
        snapshots,
        season=2025,
        as_of_game_id=3,
        team="Alpha",
        measurement_id="epa_per_play",
        unit_role="offense",
    )
    assert week_two["coverage_status"] == "observed"
    assert week_two["games_exposure"] == 1
    assert week_two["included_observations"] == 1
    assert week_two["primary_exposure"] == 2.0
    assert week_two["evidence_max_kickoff_utc"] == "2025-09-06T18:00:00+00:00"


def test_future_observation_change_cannot_alter_earlier_snapshot():
    league = simple_league()
    baseline = _snapshots(_observations(league))
    mutated_league = simple_league()
    mutated_league["byplay"].loc[mutated_league["byplay"]["game_id"] == 4, "ppa"] = 9.9
    mutated = _snapshots(_observations(mutated_league))
    through_game_four = baseline["as_of_game_id"].isin([1, 2, 3, 4])
    mutated_through_four = mutated["as_of_game_id"].isin([1, 2, 3, 4])
    assert baseline[through_game_four].equals(mutated[mutated_through_four])
    # The 2026 target cannot absorb 2025 evidence as current-season evidence.
    game_five = baseline["as_of_game_id"] == 5
    assert baseline[game_five].equals(mutated[game_five])


def test_same_kickoff_games_cannot_inform_one_another():
    league = simple_league()
    league["games"].loc[league["games"]["game_id"] == 2, "kickoff_utc"] = (
        "2025-09-06T18:00:00+00:00"
    )
    snapshots = _snapshots(_observations(league), league)
    gamma = _row(
        snapshots,
        season=2025,
        as_of_game_id=2,
        team="Gamma",
        measurement_id="epa_per_play",
        unit_role="offense",
    )
    assert gamma["coverage_status"] == "missing"
    assert gamma["games_exposure"] == 0


def test_adjustment_identity_and_retained_iterations():
    snapshots = _snapshots(_observations())
    observed = snapshots[
        (snapshots["measurement_id"] == "epa_per_play")
        & (snapshots["coverage_status"] == "observed")
    ]
    assert len(observed) > 0
    identity = (
        observed["raw_aggregate"].astype(float)
        - observed["adjusted_value"].astype(float)
        - observed["schedule_strength_component"].astype(float)
    ).abs()
    assert (identity < 1e-9).all()
    iter0 = (
        observed["adjusted_value_iter0"].astype(float)
        - observed["raw_aggregate"].astype(float)
    ).abs()
    assert (iter0 < 1e-9).all()
    assert (observed["adjustment_iteration"] == 4).all()
    assert observed["league_center"].notna().all()


def test_context_only_measurements_pass_through_unchanged():
    snapshots = _snapshots(_observations())
    context = snapshots[
        snapshots["measurement_id"].isin(
            ["average_start_field_position", "plays_per_drive", "turnover_rate"]
        )
    ]
    observed = context[context["coverage_status"] == "observed"]
    assert len(observed) > 0
    assert (observed["adjustment_method"] == "none").all()
    assert (observed["adjustment_iteration"] == 0).all()
    assert (
        observed["adjusted_value"].astype(float)
        == observed["raw_aggregate"].astype(float)
    ).all()
    assert observed["schedule_strength_component"].isna().all()
    assert observed["league_center"].isna().all()


def test_authentic_evidence_requires_effective_time_before_target_kickoff():
    league = simple_league()
    for name in ("byplay", "drives"):
        league[name]["captured_at"] = AS_OF.isoformat()
    observations = _observations(league)
    alpha_2026 = observations[
        (observations["season"] == 2026)
        & (observations["game_id"] == 5)
        & (observations["team"] == "Alpha")
        & (observations["measurement_id"] == "epa_per_play")
        & (observations["unit_role"] == "offense")
    ].copy()
    assert (alpha_2026["temporal_status"] == "authentic").all()
    assert (alpha_2026["effective_at"] == AS_OF.isoformat()).all()

    league["games"].loc[league["games"]["game_id"] == 6, "kickoff_utc"] = (
        "2026-08-30T11:00:00+00:00"
    )
    league["games"].loc[league["games"]["game_id"] == 6, ["home_team", "away_team"]] = [
        "Alpha",
        "Delta",
    ]
    snapshots = _snapshots(observations, league)
    before_effective = _row(
        snapshots,
        season=2026,
        as_of_game_id=6,
        team="Alpha",
        measurement_id="epa_per_play",
        unit_role="offense",
    )
    assert before_effective["coverage_status"] == "missing"

    league["games"].loc[league["games"]["game_id"] == 6, "kickoff_utc"] = (
        "2026-09-05T19:00:00+00:00"
    )
    snapshots_later = _snapshots(observations, league)
    after_effective = _row(
        snapshots_later,
        season=2026,
        as_of_game_id=6,
        team="Alpha",
        measurement_id="epa_per_play",
        unit_role="offense",
    )
    assert after_effective["coverage_status"] == "observed"
    assert after_effective["games_exposure"] == 1
    assert after_effective["evidence_max_effective_at"] == AS_OF.isoformat()


def test_disconnected_schedules_remain_finite():
    snapshots = _snapshots(_observations())
    adjusted = snapshots[
        (snapshots["coverage_status"] == "observed")
        & (snapshots["adjustment_method"] == "iterative_additive_league_centered")
    ]
    assert adjusted["adjusted_value"].notna().all()
    assert adjusted["adjusted_value"].astype(float).abs().max() < 1e6


def test_snapshot_keys_are_unique_and_deterministic():
    first = _snapshots(_observations())
    second = _snapshots(_observations())
    assert first.equals(second)
    assert not first.duplicated(
        ["season", "as_of_game_id", "team", "measurement_id", "unit_role"]
    ).any()
    per_game_pairs = first.groupby("as_of_game_id")[
        ["measurement_id", "unit_role"]
    ].apply(lambda rows: set(zip(rows["measurement_id"], rows["unit_role"])))
    assert all(pairs == per_game_pairs.iloc[0] for pairs in per_game_pairs)
    assert len(per_game_pairs.iloc[0]) == 13
