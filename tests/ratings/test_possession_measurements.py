"""V5 possession ledger and measurement semantics."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.ratings.possession_measurements import (
    _adjust,
    build_measurements,
    build_replay,
    replay_partitions,
)


def _population() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "season": 2025,
                "week": 1,
                "game_id": 1,
                "kickoff_utc": "2025-09-01T18:00:00Z",
                "home_team": "Alpha",
                "away_team": "Beta",
                "schedule_completed": True,
                "outcome_valid": True,
                "forecast_eligible": True,
                "measurement_usable": True,
                "population_disposition": "eligible_with_measurements",
                "measurement_disposition": "eligible_with_measurements",
                "missing_reason": None,
                "timing_class": "historically_reconstructed",
            },
            {
                "season": 2025,
                "week": 2,
                "game_id": 2,
                "kickoff_utc": "2025-09-08T18:00:00Z",
                "home_team": "Alpha",
                "away_team": "Beta",
                "schedule_completed": True,
                "outcome_valid": True,
                "forecast_eligible": True,
                "measurement_usable": True,
                "population_disposition": "eligible_with_measurements",
                "measurement_disposition": "eligible_with_measurements",
                "missing_reason": None,
                "timing_class": "historically_reconstructed",
            },
        ]
    )


def _row(**overrides):
    row = {
        "season": 2025,
        "week": 1,
        "game_id": 1,
        "drive_number": 1,
        "play_number": 1,
        "offense": "Alpha",
        "defense": "Beta",
        "st": 0,
        "penalty": 0,
        "twopoint": 0,
        "play_type": "Rush",
        "garbage": 0,
        "ppa": 0.2,
        "quarter": 1,
        "offense_score": 0,
        "defense_score": 0,
    }
    row.update(overrides)
    return row


def _plays() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _row(play_number=1),
            _row(play_number=2, offense_score=7, ppa=0.4),
            _row(
                drive_number=2,
                play_number=1,
                offense="Beta",
                defense="Alpha",
                offense_score=0,
                defense_score=7,
            ),
            _row(
                drive_number=2,
                play_number=2,
                offense="Beta",
                defense="Alpha",
                offense_score=3,
                defense_score=7,
                play_type="Field Goal",
            ),
            _row(
                drive_number=3,
                play_number=1,
                offense="Alpha",
                defense="Beta",
                offense_score=7,
                defense_score=3,
            ),
            _row(
                drive_number=3,
                play_number=2,
                offense="Alpha",
                defense="Beta",
                offense_score=7,
                defense_score=10,
                play_type="Interception Return Touchdown",
            ),
            _row(
                game_id=2,
                week=2,
                drive_number=1,
                play_number=1,
                offense_score=0,
                defense_score=0,
            ),
            _row(
                game_id=2,
                week=2,
                drive_number=1,
                play_number=2,
                offense_score=3,
                defense_score=0,
                play_type="Field Goal",
            ),
            _row(
                game_id=2,
                week=2,
                drive_number=2,
                play_number=1,
                offense="Beta",
                defense="Alpha",
                offense_score=0,
                defense_score=3,
            ),
            _row(
                game_id=2,
                week=2,
                drive_number=2,
                play_number=2,
                offense="Beta",
                defense="Alpha",
                offense_score=7,
                defense_score=3,
            ),
        ]
    )


def test_ppp_uses_offensive_attribution_and_defense_mirrors_opponent():
    result = build_measurements(byplay=_plays(), population=_population())
    game = result.observations[result.observations["game_id"].eq(1)]
    ppp = game[game["measurement_id"].eq("ppp")].set_index(["team", "unit_role"])
    assert ppp.loc[("Alpha", "offense"), "raw_value"] == 7.0 / 2.0
    assert ppp.loc[("Beta", "offense"), "raw_value"] == 3.0
    assert ppp.loc[("Beta", "defense"), "raw_value"] == 7.0 / 2.0
    non_offense = game[game["measurement_id"].eq("non_offense_points")].set_index(
        ["team", "unit_role"]
    )
    assert non_offense.loc[("Beta", "offense"), "raw_value"] == 7.0
    events = result.scoring_events[result.scoring_events["game_id"].eq(1)]
    assert set(
        events.loc[
            (events["team"] == "Beta") & (events["score_increment"] == 7),
            "scoring_category",
        ]
    ) == {"regulation_non_offense"}


def test_missing_eligible_ppa_quarantines_epa_without_discarding_ppp():
    plays = _plays()
    plays.loc[(plays["game_id"] == 1) & (plays["offense"] == "Alpha"), "ppa"] = None
    result = build_measurements(byplay=plays, population=_population())
    alpha = result.observations[
        (result.observations["game_id"] == 1)
        & (result.observations["team"] == "Alpha")
        & (result.observations["unit_role"] == "offense")
    ].set_index("measurement_id")
    assert alpha.loc["epa_per_possession", "coverage_status"] == "missing"
    assert alpha.loc["ppp", "coverage_status"] == "observed"


def test_malformed_score_stream_quarantines_ppp_but_preserves_epa():
    plays = _plays()
    plays.loc[
        (plays["game_id"] == 1)
        & (plays["offense"] == "Alpha")
        & (plays["play_number"] == 2),
        "offense_score",
    ] = 24
    result = build_measurements(byplay=plays, population=_population())
    events = result.scoring_events[
        (result.scoring_events["game_id"] == 1)
        & (result.scoring_events["team"] == "Alpha")
    ]
    marker = events[events["scoring_category"].eq("unresolved")].iloc[0]
    assert marker["score_increment"] == 0
    assert marker["quality_reason"] == "impossible_score_increment"
    observations = result.observations.set_index(
        ["game_id", "team", "unit_role", "measurement_id"]
    )
    assert (
        observations.loc[(1, "Alpha", "offense", "ppp"), "coverage_status"] == "missing"
    )
    assert (
        observations.loc[(1, "Beta", "defense", "ppp"), "coverage_status"] == "missing"
    )
    assert (
        observations.loc[
            (1, "Alpha", "offense", "epa_per_possession"), "coverage_status"
        ]
        == "observed"
    )


def test_unresolved_attribution_still_counts_for_final_reconciliation():
    plays = _plays()
    plays.loc[plays["game_id"].eq(1), "quarter"] = None
    result = build_measurements(
        byplay=plays,
        population=_population(),
        outcomes=pd.DataFrame(
            [
                {
                    "season": 2025,
                    "game_id": 1,
                    "home_points": 7,
                    "away_points": 10,
                }
            ]
        ),
    )
    assert result.final_reconciliation[2025]["exact_rate"] == 1.0
    assert result.final_reconciliation[2025]["quarantined_team_scores"] == 0.0


def test_provider_team_aliases_reconcile_against_canonical_population():
    population = _population()
    population.loc[:, "home_team"] = "Southern Mississippi"
    population.loc[:, "away_team"] = "Connecticut"
    plays = _plays().replace(
        {
            "offense": {"Alpha": "Southern Miss", "Beta": "UConn"},
            "defense": {"Alpha": "Southern Miss", "Beta": "UConn"},
        }
    )
    result = build_measurements(
        byplay=plays,
        population=population,
        outcomes=pd.DataFrame(
            [
                {
                    "season": 2025,
                    "game_id": 1,
                    "home_points": 7,
                    "away_points": 10,
                }
            ]
        ),
    )
    assert result.final_reconciliation[2025]["exact_rate"] == 1.0
    assert set(result.scoring_events["team"]) == {
        "Southern Mississippi",
        "Connecticut",
    }


def test_overtime_and_unknown_period_never_create_rating_possessions():
    plays = _plays()
    plays.loc[(plays["game_id"] == 1) & (plays["drive_number"] == 1), "quarter"] = 5
    plays.loc[
        (plays["game_id"] == 1) & (plays["drive_number"].isin([2, 3])), "quarter"
    ] = None
    result = build_measurements(byplay=plays, population=_population())
    ledger = result.possessions[result.possessions["game_id"].eq(1)]
    assert not ledger["possession_eligible"].any()
    categories = set(
        result.scoring_events[result.scoring_events["game_id"].eq(1)][
            "scoring_category"
        ]
    )
    assert "overtime" in categories
    assert "unresolved" in categories


def test_replay_is_strictly_prior_and_keeps_terminal_separate():
    result = build_measurements(byplay=_plays(), population=_population())
    snapshots, history, terminal, evidence = build_replay(
        population=_population(), observations=result.observations
    )
    assert history[history["week"].eq(1)].empty
    assert snapshots[snapshots["week"].eq(1)]["source_game_count"].eq(0).all()
    assert snapshots[snapshots["week"].eq(2)]["source_game_count"].gt(0).any()
    assert not terminal.empty
    assert evidence["iterations"] == [0, 4]


def test_replay_streams_declared_season_week_partitions():
    result = build_measurements(byplay=_plays(), population=_population())
    emitted: list[tuple[str, dict[str, int], pd.DataFrame]] = []
    evidence = replay_partitions(
        population=_population(),
        observations=result.observations,
        emit=lambda name, partition, frame: emitted.append((name, partition, frame)),
    )
    snapshots = [entry for entry in emitted if entry[0] == "snapshots"]
    history = [entry for entry in emitted if entry[0] == "adjusted_history"]
    terminal = [entry for entry in emitted if entry[0] == "terminal"]
    assert [entry[1] for entry in snapshots] == [
        {"season": 2025, "week": 1},
        {"season": 2025, "week": 2},
    ]
    assert [entry[1] for entry in history] == [{"season": 2025, "week": 2}]
    assert [entry[1] for entry in terminal] == [{"season": 2025}]
    assert evidence["max_history_partition_rows"] > 0


def test_four_pass_adjustment_matches_the_league_centered_definition():
    history = pd.DataFrame(
        [
            {
                "team": "Alpha",
                "opponent": "Beta",
                "unit_role": "offense",
                "measurement_id": "ppp",
                "numerator": 10.0,
                "denominator": 10.0,
            },
            {
                "team": "Gamma",
                "opponent": "Delta",
                "unit_role": "offense",
                "measurement_id": "ppp",
                "numerator": 30.0,
                "denominator": 10.0,
            },
            {
                "team": "Beta",
                "opponent": "Alpha",
                "unit_role": "defense",
                "measurement_id": "ppp",
                "numerator": 10.0,
                "denominator": 10.0,
            },
            {
                "team": "Delta",
                "opponent": "Gamma",
                "unit_role": "defense",
                "measurement_id": "ppp",
                "numerator": 30.0,
                "denominator": 10.0,
            },
        ]
    )
    raw, adjusted = _adjust(history)
    assert raw == {
        ("Alpha", "offense", "ppp"): 1.0,
        ("Gamma", "offense", "ppp"): 3.0,
        ("Beta", "defense", "ppp"): 1.0,
        ("Delta", "defense", "ppp"): 3.0,
    }
    # This symmetric fixture alternates between league center and raw values;
    # the required fourth pass therefore returns to the original values.
    assert adjusted == raw
