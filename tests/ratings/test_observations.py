"""Raw long-form observation builder tests (Task 2)."""

from __future__ import annotations

import pandas as pd
import pytest
from helpers import (
    AS_OF,
    drive_row,
    game_row,
    outcome_row,
    play_row,
    reconciled_row,
    simple_league,
)

from cks_picks_cfb.ratings.contracts import load_measurement_config
from cks_picks_cfb.ratings.observations import build_measurement_observations

CONFIG = load_measurement_config("conf/ratings/measurement_baseline_v1.yaml")
V3_CONFIG = load_measurement_config("conf/ratings/measurement_baseline_v3.yaml")


def _build(league, **overrides):
    kwargs = dict(
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
    )
    kwargs.update(overrides)
    return build_measurement_observations(**kwargs)


def _score_stream_league():
    """One fully reconciled game with 7 and 3 true drive points."""
    byplay = pd.DataFrame(
        [
            play_row(
                game_id=1,
                drive_number=1,
                play_number=1,
                offense="Alpha",
                defense="Beta",
                offense_score=0,
                defense_score=0,
            ),
            play_row(
                game_id=1,
                drive_number=1,
                play_number=2,
                offense="Alpha",
                defense="Beta",
                offense_score=7,
                defense_score=0,
            ),
            play_row(
                game_id=1,
                drive_number=2,
                play_number=1,
                offense="Beta",
                defense="Alpha",
                offense_score=0,
                defense_score=7,
            ),
            play_row(
                game_id=1,
                drive_number=2,
                play_number=2,
                offense="Beta",
                defense="Alpha",
                offense_score=3,
                defense_score=7,
            ),
        ]
    )
    return {
        "byplay": byplay,
        "drives": pd.DataFrame(
            [
                drive_row(
                    drive_number=1,
                    offense="Alpha",
                    defense="Beta",
                    points=1,
                    points_on_opps=1,
                ),
                drive_row(
                    drive_number=2,
                    offense="Beta",
                    defense="Alpha",
                    points=1,
                    points_on_opps=1,
                ),
            ]
        ),
        "games": pd.DataFrame([game_row()]),
        "outcomes": pd.DataFrame([outcome_row(home_points=7, away_points=3)]),
        "reconciled_team_game": pd.DataFrame(
            [reconciled_row(team="Alpha"), reconciled_row(team="Beta")]
        ),
    }


def _build_v3(league):
    return _build(league, config=V3_CONFIG)


def test_eligible_game_yields_every_measurement_role_and_side():
    result = _build(simple_league())
    game_one = result.frame[result.frame["game_id"] == 1]
    pairs = set(zip(game_one["measurement_id"], game_one["unit_role"]))
    assert len(pairs) == 13
    assert len(game_one) == 26
    assert set(game_one["team"]) == {"Alpha", "Beta"}
    assert set(game_one["side"]) == {"home", "away"}


def test_exact_numerators_and_denominators():
    byplay = []
    drives = []
    for play_number in range(1, 5):
        byplay.append(
            play_row(
                game_id=1,
                drive_number=1,
                play_number=play_number,
                offense="Alpha",
                defense="Beta",
                ppa=0.1 * play_number,
                success=1 if play_number <= 3 else 0,
                yards_gained=25 if play_number == 1 else 4,
                turnover=1 if play_number == 4 else 0,
            )
        )
    drives.append(drive_row(game_id=1, drive_number=1, start_yards_to_goal=75))
    league = {
        "byplay": pd.DataFrame(byplay),
        "drives": pd.DataFrame(drives),
        "games": pd.DataFrame([game_row()]),
        "outcomes": pd.DataFrame([outcome_row()]),
        "reconciled_team_game": pd.DataFrame(
            [reconciled_row(team="Alpha"), reconciled_row(team="Beta")]
        ),
    }
    result = _build(league)
    alpha = result.frame[
        (result.frame["game_id"] == 1)
        & (result.frame["team"] == "Alpha")
        & (result.frame["unit_role"] == "offense")
    ].set_index("measurement_id")

    assert alpha.loc["epa_per_play", "numerator"] == pytest.approx(1.0)
    assert alpha.loc["epa_per_play", "denominator"] == 4
    assert alpha.loc["epa_per_play", "raw_value"] == pytest.approx(0.25)
    assert alpha.loc["success_rate", "numerator"] == 3
    assert alpha.loc["success_rate", "raw_value"] == pytest.approx(0.75)
    assert alpha.loc["explosive_rate_20", "numerator"] == 1
    assert alpha.loc["explosive_rate_20", "raw_value"] == pytest.approx(0.25)
    assert alpha.loc["turnover_rate", "numerator"] == 1
    assert alpha.loc["plays_per_drive", "numerator"] == 4
    assert alpha.loc["plays_per_drive", "denominator"] == 1
    assert alpha.loc["points_per_scoring_opportunity", "numerator"] == 7
    assert alpha.loc["points_per_scoring_opportunity", "denominator"] == 1
    assert alpha.loc["average_start_field_position", "numerator"] == 25
    assert alpha.loc["average_start_field_position", "raw_value"] == pytest.approx(25.0)


def test_v3_ppso_uses_score_stream_not_boolean_scoring_events():
    result = _build_v3(_score_stream_league())
    ppso = result.frame[
        result.frame["measurement_id"] == "points_per_scoring_opportunity"
    ].set_index(["team", "unit_role"])
    assert ppso.loc[("Alpha", "offense"), "raw_value"] == 7.0
    assert ppso.loc[("Beta", "defense"), "raw_value"] == 7.0
    assert ppso.loc[("Beta", "offense"), "raw_value"] == 3.0
    assert ppso.loc[("Alpha", "defense"), "raw_value"] == 3.0
    assert result.audit["score_reconciliation"][2025]["exact_rate"] == 1.0


def test_v3_score_stream_mismatch_quarantines_offense_and_paired_defense():
    league = _score_stream_league()
    league["outcomes"].loc[0, "home_points"] = 10
    result = _build_v3(league).frame
    ppso = result[
        result["measurement_id"] == "points_per_scoring_opportunity"
    ].set_index(["team", "unit_role"])
    for key in (("Alpha", "offense"), ("Beta", "defense")):
        assert ppso.loc[key, "coverage_status"] == "missing"
        assert ppso.loc[key, "missing_reason"] == "score_stream_mismatch"
        assert "score_stream_mismatch" in ppso.loc[key, "quality_flags"]
    for key in (("Beta", "offense"), ("Alpha", "defense")):
        assert ppso.loc[key, "coverage_status"] == "observed"


def test_v3_invalid_drive_points_are_quarantined_without_clipping():
    league = _score_stream_league()
    alpha_last = (league["byplay"]["offense"] == "Alpha") & (
        league["byplay"]["play_number"] == 2
    )
    league["byplay"].loc[alpha_last, "offense_score"] = 9
    league["byplay"].loc[league["byplay"]["defense"] == "Alpha", "defense_score"] = 9
    league["outcomes"].loc[0, "home_points"] = 9
    result = _build_v3(league).frame
    alpha = result[
        (result["team"] == "Alpha")
        & (result["unit_role"] == "offense")
        & (result["measurement_id"] == "points_per_scoring_opportunity")
    ].iloc[0]
    assert alpha["missing_reason"] == "score_stream_mismatch"
    assert alpha["raw_value"] is None or pd.isna(alpha["raw_value"])


def test_v3_rejects_nonfinite_score_stream_values():
    league = _score_stream_league()
    league["byplay"]["offense_score"] = league["byplay"]["offense_score"].astype(
        float
    )
    league["byplay"].loc[0, "offense_score"] = float("inf")
    result = _build_v3(league).frame
    alpha = result[
        (result["team"] == "Alpha")
        & (result["unit_role"] == "offense")
        & (result["measurement_id"] == "points_per_scoring_opportunity")
    ].iloc[0]
    assert alpha["missing_reason"] == "score_stream_mismatch"


def test_v3_changes_only_ppso_values_and_schema_lineage():
    league = _score_stream_league()
    v2 = _build(league).frame
    v3 = _build_v3(league).frame
    keys = ["season", "game_id", "team", "measurement_id", "unit_role"]
    other = v2[v2["measurement_id"] != "points_per_scoring_opportunity"].merge(
        v3[v3["measurement_id"] != "points_per_scoring_opportunity"],
        on=keys,
        suffixes=("_v2", "_v3"),
    )
    for column in ("numerator", "denominator", "raw_value", "coverage_status"):
        assert other[f"{column}_v2"].equals(other[f"{column}_v3"])
    assert set(v3["measurement_schema_version"]) == {
        "rating_measurement_observations_v3"
    }


def test_garbage_and_non_drive_plays_are_ineligible():
    byplay = [
        play_row(game_id=1, drive_number=1, play_number=1, ppa=0.5, success=1),
        play_row(game_id=1, drive_number=1, play_number=2, garbage=1, ppa=0.9),
        play_row(game_id=1, drive_number=1, play_number=3, penalty=1, ppa=0.9),
        play_row(game_id=1, drive_number=1, play_number=4, st=1, ppa=0.9),
        play_row(game_id=1, drive_number=1, play_number=5, twopoint=1, ppa=0.9),
        play_row(
            game_id=1, drive_number=1, play_number=6, play_type="Timeout", ppa=0.9
        ),
    ]
    league = {
        "byplay": pd.DataFrame(byplay),
        "drives": pd.DataFrame([drive_row(game_id=1, drive_number=1)]),
        "games": pd.DataFrame([game_row()]),
        "outcomes": pd.DataFrame([outcome_row()]),
        "reconciled_team_game": pd.DataFrame(
            [reconciled_row(team="Alpha"), reconciled_row(team="Beta")]
        ),
    }
    result = _build(league)
    epa = result.frame[
        (result.frame["game_id"] == 1)
        & (result.frame["team"] == "Alpha")
        & (result.frame["unit_role"] == "offense")
        & (result.frame["measurement_id"] == "epa_per_play")
    ].iloc[0]
    assert epa["numerator"] == pytest.approx(0.5)
    assert epa["denominator"] == 1
    assert "garbage_flag_missing" not in (epa["quality_flags"] or "")


def test_zero_denominator_yields_null_with_reason():
    drives = [
        drive_row(
            game_id=1,
            drive_number=1,
            had_scoring_opportunity=0,
            points=7,
            points_on_opps=0,
        )
    ]
    league = simple_league()
    league["drives"] = pd.DataFrame(drives)
    result = _build(league)
    ppo = result.frame[
        (result.frame["game_id"] == 1)
        & (result.frame["measurement_id"] == "points_per_scoring_opportunity")
    ]
    assert len(ppo) == 4
    assert (ppo["raw_value"].isna()).all()
    assert (ppo["coverage_status"] == "missing").all()
    assert (ppo["missing_reason"] == "zero_denominator").all()


def test_source_evidence_missing_rows_are_explicit():
    league = simple_league()
    league["byplay"] = league["byplay"][league["byplay"]["game_id"] != 1]
    league["drives"] = league["drives"][league["drives"]["game_id"] != 1]
    result = _build(league)
    game_one = result.frame[result.frame["game_id"] == 1]
    assert len(game_one) == 26
    assert (game_one["coverage_status"] == "missing").all()
    assert (game_one["missing_reason"] == "source_evidence_missing").all()


def test_offense_and_defense_rows_are_mirrored():
    result = _build(simple_league())
    frame = result.frame[result.frame["measurement_id"] != "plays_per_drive"]
    offense = frame[frame["unit_role"] == "offense"]
    defense = frame[frame["unit_role"] == "defense"]
    offense_keys = set(
        zip(
            offense["game_id"],
            offense["team"],
            offense["opponent"],
            offense["measurement_id"],
        )
    )
    defense_keys = set(
        zip(
            defense["game_id"],
            defense["opponent"],
            defense["team"],
            defense["measurement_id"],
        )
    )
    assert offense_keys == defense_keys


def test_cancelled_incomplete_and_future_games_are_excluded_with_reasons():
    league = simple_league()
    league["games"] = pd.concat(
        [
            league["games"],
            pd.DataFrame(
                [
                    game_row(
                        game_id=7,
                        season=2025,
                        week=2,
                        kickoff_utc="2025-09-13T01:00:00+00:00",
                        home_team="Alpha",
                        away_team="Delta",
                        completed=False,
                        status="cancelled",
                    ),
                    game_row(
                        game_id=8,
                        season=2026,
                        week=2,
                        kickoff_utc="2026-09-12T19:00:00+00:00",
                        home_team="Alpha",
                        away_team="Delta",
                        completed=False,
                        status="scheduled",
                    ),
                ]
            ),
        ],
        ignore_index=True,
    )
    result = _build(league)
    observed_games = set(result.frame["game_id"])
    assert {7, 8}.isdisjoint(observed_games)
    reasons = {
        entry["game_id"]: entry["reason"] for entry in result.audit["excluded_games"]
    }
    assert reasons[7] == "cancelled_or_postponed"
    assert reasons[8] == "incomplete"


def test_unreconciled_game_fails_closed():
    league = simple_league()
    league["reconciled_team_game"] = league["reconciled_team_game"][
        league["reconciled_team_game"]["game_id"] != 2
    ]
    result = _build(league)
    assert 2 not in set(result.frame["game_id"])
    reasons = {
        entry["game_id"]: entry["reason"] for entry in result.audit["excluded_games"]
    }
    assert reasons[2] == "unreconciled"


def test_2020_season_fails_closed():
    league = simple_league()
    league["games"] = pd.concat(
        [
            league["games"],
            pd.DataFrame(
                [
                    game_row(
                        season=2020,
                        game_id=9,
                        kickoff_utc="2020-09-12T19:00:00+00:00",
                    )
                ]
            ),
        ],
        ignore_index=True,
    )
    with pytest.raises(Exception, match="forbidden"):
        _build(league)


def test_out_of_scope_seasons_are_dropped_and_audited():
    league = simple_league()
    league["games"] = pd.concat(
        [
            league["games"],
            pd.DataFrame(
                [
                    game_row(
                        season=2019,
                        game_id=10,
                        kickoff_utc="2019-09-12T19:00:00+00:00",
                    )
                ]
            ),
        ],
        ignore_index=True,
    )
    result = _build(league)
    assert 2019 not in set(result.frame["season"])
    assert result.audit["out_of_scope_season_games"] == {2019: 1}


def test_temporal_status_encoding():
    result = _build(simple_league())
    frame = result.frame
    historical = frame[frame["season"] == 2025]
    protected = frame[frame["season"] == 2026]
    assert (historical["temporal_status"] == "reconstructed").all()
    assert historical["effective_at"].isna().all()
    assert historical["eligible_after"].isna().all()
    assert (protected["temporal_status"] == "reconstructed").all()
    assert protected["effective_at"].isna().all()


def test_authentic_status_requires_genuine_parent_capture_time():
    league = simple_league()
    for name in ("byplay", "drives"):
        frame = league[name]
        frame["captured_at"] = "2026-08-29T12:00:00+00:00"
    frame = _build(league).frame
    protected = frame[frame["season"] == 2026]
    assert (protected["temporal_status"] == "authentic").all()
    assert (protected["effective_at"] == "2026-08-29T12:00:00+00:00").all()


def test_completed_game_after_as_of_fails_closed():
    league = simple_league()
    late = game_row(
        game_id=11,
        season=2026,
        week=1,
        kickoff_utc="2026-09-20T19:00:00+00:00",
    )
    league["games"] = pd.concat(
        [league["games"], pd.DataFrame([late])], ignore_index=True
    )
    league["outcomes"] = pd.concat(
        [league["outcomes"], pd.DataFrame([outcome_row(season=2026, game_id=11)])],
        ignore_index=True,
    )
    league["reconciled_team_game"] = pd.concat(
        [
            league["reconciled_team_game"],
            pd.DataFrame(
                [
                    reconciled_row(season=2026, game_id=11, team="Alpha"),
                    reconciled_row(season=2026, game_id=11, team="Beta"),
                ]
            ),
        ],
        ignore_index=True,
    )
    with pytest.raises(Exception, match="as-of cutoff"):
        _build(league)


def test_success_rate_denominator_uses_computable_success_only():
    byplay = [
        play_row(game_id=1, drive_number=1, play_number=1, success=1),
        play_row(game_id=1, drive_number=1, play_number=2, success=0),
        play_row(game_id=1, drive_number=1, play_number=3, success=None),
        play_row(
            game_id=1,
            drive_number=1,
            play_number=4,
            play_type="End of Half",
            success=None,
        ),
    ]
    league = {
        "byplay": pd.DataFrame(byplay),
        "drives": pd.DataFrame([drive_row(game_id=1, drive_number=1)]),
        "games": pd.DataFrame([game_row()]),
        "outcomes": pd.DataFrame([outcome_row()]),
        "reconciled_team_game": pd.DataFrame(
            [reconciled_row(team="Alpha"), reconciled_row(team="Beta")]
        ),
    }
    result = _build(league)
    sr = result.frame[
        (result.frame["game_id"] == 1)
        & (result.frame["team"] == "Alpha")
        & (result.frame["unit_role"] == "offense")
    ].set_index("measurement_id")
    assert sr.loc["success_rate", "numerator"] == 1
    assert sr.loc["success_rate", "denominator"] == 2
    assert sr.loc["success_rate", "raw_value"] == pytest.approx(0.5)
    assert sr.loc["epa_per_play", "denominator"] == 4
    flags = sr.loc["epa_per_play", "quality_flags"]
    assert "success_missing_on_eligible_plays" in flags


def test_epa_denominator_excludes_missing_ppa():
    league = simple_league()
    mask = (league["byplay"]["game_id"] == 1) & (league["byplay"]["offense"] == "Alpha")
    league["byplay"].loc[mask, "ppa"] = None
    result = _build(league).frame
    row = result[
        (result["game_id"] == 1)
        & (result["team"] == "Alpha")
        & (result["measurement_id"] == "epa_per_play")
        & (result["unit_role"] == "offense")
    ].iloc[0]
    assert row["denominator"] == 0
    assert row["raw_value"] is None or pd.isna(row["raw_value"])


def test_identical_parents_rebuild_byte_equivalent_rows():
    first = _build(simple_league())
    second = _build(simple_league())
    assert first.frame.equals(second.frame)
    assert first.audit == second.audit
