"""team_game_metrics builder: null semantics, defense mirror, aggregation, PPP independence."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.metrics import builders as b
from cks_picks_cfb.metrics import contracts as gc

T0 = pd.Timestamp("2026-09-05T19:00:00Z")
VERSIONS = {"byplay": "v1", "ledger": "v1", "coverage": "coverage-v1"}


def _play(
    offense,
    defense,
    *,
    ppa=0.5,
    missing=False,
    dropback=1,
    rush=0,
    down=1,
    success=1,
    yards=6,
    turnover=0,
    play_type="Pass Reception",
    **over,
):
    row = {
        "season": 2026,
        "game_id": 1,
        "offense": offense,
        "defense": defense,
        "quarter": 1,
        "st": 0,
        "penalty": 0,
        "twopoint": 0,
        "garbage": 0,
        "play_type": play_type,
        "ppa": None if missing else ppa,
        "ppa_missing": missing,
        "dropback": dropback,
        "rush_attempt": rush,
        "down": down,
        "success": success,
        "yards_gained": yards,
        "turnover": turnover,
        "thirddown_conversion": 0,
        "fourthdown_conversion": 0,
        "distance": 10,
        "yards_to_goal": 60,
    }
    return {**row, **over}


def _plays(**a_over):
    rows = [
        _play("A", "B", ppa=0.4),  # pass, down 1
        _play(
            "A", "B", ppa=-0.1, dropback=0, rush=1, play_type="Rush", yards=3, success=0
        ),  # rush, down 1
        _play("A", "B", ppa=0.0, down=2),  # genuine zero PPA
        _play("A", "B", ppa=1.2, down=3, yards=25),  # explosive, 3rd down
        _play("B", "A", ppa=0.2, dropback=0, rush=1, play_type="Rush", yards=4),
        _play("B", "A", ppa=0.3, down=2),
        _play("B", "A", ppa=-0.5, down=3, success=0, yards=1, turnover=1),
    ]
    return pd.DataFrame(rows)


def _possessions():
    def poss(drive, offense, defense, opp, start):
        return {
            "season": 2026,
            "week": 1,
            "game_id": 1,
            "drive_number": drive,
            "possession_id": gc.possession_id_for(2026, 1, drive, offense),
            "offense": offense,
            "defense": defense,
            "period_class": "regulation",
            "eligible_play_count": 3,
            "ineligible_play_count": 0,
            "mixed_eligibility": False,
            "possession_eligible": True,
            "scoring_opportunity": opp,
            "start_yards_to_goal": start,
            "source_play_ids": "[]",
            "quality_reason": None,
            "timing_class": "live",
            "source_versions": json.dumps(VERSIONS, sort_keys=True),
        }

    return pd.DataFrame(
        [
            poss(1, "A", "B", True, 75.0),
            poss(2, "B", "A", False, 70.0),
            poss(3, "A", "B", False, 80.0),
        ]
    )


def _event(
    event_id,
    team,
    increment,
    category="eligible_regulation_offense",
    drive=1,
    admission="baseline_unchanged",
):
    return {
        "season": 2026,
        "game_id": 1,
        "source_event_id": event_id,
        "team": team,
        "drive_number": drive,
        "quarter": 1,
        "play_number": 1,
        "period_class": "regulation",
        "score_increment": increment,
        "scoring_category": category,
        "unit_category": "offense" if category != "unresolved" else "unknown",
        "associated_possession_id": gc.possession_id_for(2026, 1, drive, team)
        if category == "eligible_regulation_offense"
        else None,
        "conversion_for_event_id": None,
        "raw_score_before": 0.0,
        "raw_score_after": float(increment or 0),
        "envelope_before": None,
        "envelope_after": None,
        "certified_final": None,
        "quality_reason": None,
        "rule_version": "baseline_v1",
        "allocation_group_id": "g",
        "admission": admission,
        "evidence_ids": "[]",
        "timing_class": "live",
        "source_versions": json.dumps(VERSIONS, sort_keys=True),
    }


def _ledger(*extra):
    return pd.DataFrame(
        [_event("e1", "A", 7.0, drive=1), _event("e2", "B", 3.0, drive=2), *extra]
    )


def _games(home_points=17, away_points=10):
    return pd.DataFrame(
        [
            {
                "season": 2026,
                "week": 1,
                "game_id": 1,
                "season_type": "regular",
                "home_team": "A",
                "away_team": "B",
                "kickoff_utc": T0,
                "home_points": home_points,
                "away_points": away_points,
                "home_fbs": True,
                "away_fbs": True,
            }
        ]
    )


def _build(plays=None, ledger=None, games=None):
    return b.build_team_game_metrics(
        plays=_plays() if plays is None else plays,
        possessions=_possessions(),
        ledger=_ledger() if ledger is None else ledger,
        games=_games() if games is None else games,
        source_versions=VERSIONS,
        timing_class="live",
        coverage=pd.DataFrame(
            [
                dict(
                    season=2026,
                    game_id=1,
                    team=team,
                    plays_complete=True,
                    possessions_complete=True,
                    scoring_complete=True,
                )
                for team in ("A", "B")
            ]
        ),
    )


def _get(frame, team, role, metric):
    row = frame[(frame.team == team) & (frame.role == role) & (frame.metric == metric)]
    assert len(row) == 1, (team, role, metric)
    return row.iloc[0]


def test_a_complete_game_is_valid_under_schema_and_semantics():
    frame = _build()
    validate_frame(frame, schema_for("team_game_metrics", "team_game_metrics_v1"))
    assert gc.team_game_metrics_problems(frame) == []
    assert gc.defense_mirror_problems(frame) == []
    assert set(frame.metric) >= set(b.reg.BY_NAME) - {
        "possessions_per_game",
        "non_offense_points_per_game",
    }
    assert (frame.coverage_status == "observed").all()


def test_values_follow_the_registry_formulas():
    f = _build()
    assert _get(f, "A", "offense", "eligible_possessions").value == 2
    assert _get(f, "A", "offense", "offensive_possession_points").value == 7
    assert _get(f, "A", "offense", "ppp").value == pytest.approx(3.5)  # Q / D
    assert _get(f, "A", "offense", "eligible_scrimmage_plays").value == 4
    assert _get(f, "A", "offense", "plays_per_possession").value == pytest.approx(2.0)
    assert _get(f, "A", "offense", "eligible_epa").value == pytest.approx(
        1.5
    )  # 0.4 - 0.1 + 0 + 1.2
    assert _get(f, "A", "offense", "ppa_per_play").value == pytest.approx(0.375)
    assert (
        _get(f, "A", "offense", "epa_per_play").value
        == _get(f, "A", "offense", "ppa_per_play").value
    )
    assert _get(f, "A", "offense", "epa_per_possession").value == pytest.approx(0.75)
    assert _get(f, "A", "offense", "epa_pass").value == pytest.approx(1.6 / 3)
    assert _get(f, "A", "offense", "epa_rush").value == pytest.approx(-0.1)
    assert _get(f, "A", "offense", "early_down_epa").value == pytest.approx(
        (0.4 - 0.1 + 0.0) / 3
    )
    assert _get(f, "A", "offense", "success_rate").value == pytest.approx(0.75)
    assert _get(f, "A", "offense", "explosive_rate").value == pytest.approx(0.25)
    assert _get(f, "A", "offense", "scoring_opp_rate").value == pytest.approx(
        0.5
    )  # 1 of 2 eligible drives
    assert _get(f, "A", "offense", "pts_per_scoring_opp").value == pytest.approx(7.0)
    assert _get(f, "A", "offense", "avg_start_field_pos").value == pytest.approx(
        22.5
    )  # mean(25, 20)
    assert _get(f, "B", "offense", "turnover_rate").value == pytest.approx(1 / 3)
    assert _get(f, "A", "offense", "points_scored").value == 17
    assert _get(f, "B", "offense", "points_scored").value == 10


def test_a_genuine_zero_ppa_is_observed_not_missing():
    f = _build()
    assert _get(f, "A", "offense", "eligible_epa").coverage_status == "observed"
    assert _get(f, "A", "offense", "early_down_epa").coverage_status == "observed"


def test_missing_ppa_withholds_only_the_epa_metrics_that_contain_it():
    plays = _plays()
    plays.loc[0, ["ppa", "ppa_missing"]] = [
        None,
        True,
    ]  # a missing pass (dropback) PPA on A's first play
    f = _build(plays)
    assert gc.team_game_metrics_problems(f) == []
    for metric in (
        "eligible_epa",
        "ppa_per_play",
        "epa_per_play",
        "epa_pass",
        "early_down_epa",
        "epa_per_possession",
    ):
        row = _get(f, "A", "offense", metric)
        assert (
            row.coverage_status == "missing"
            and row.missing_reason == "ppa_incomplete"
            and pd.isna(row.value)
        ), metric
    # Rush PPA is independently complete, and every independent metric is untouched.
    assert _get(f, "A", "offense", "epa_rush").coverage_status == "observed"
    for metric in (
        "ppp",
        "offensive_possession_points",
        "success_rate",
        "explosive_rate",
        "eligible_scrimmage_plays",
    ):
        assert _get(f, "A", "offense", metric).coverage_status == "observed", metric
    # The known denominator is preserved while the numerator is withheld.
    pass_row = _get(f, "A", "offense", "epa_pass")
    assert (
        pass_row.denominator == 3
        and pass_row.eligible_count == 3
        and pass_row.observed_count == 2
    )
    # The other team is unaffected, and the defense row mirrors the withheld measurement.
    assert _get(f, "B", "offense", "eligible_epa").coverage_status == "observed"
    mirror = _get(f, "B", "defense", "eligible_epa")
    assert (
        mirror.coverage_status == "missing"
        and mirror.missing_reason == "ppa_incomplete"
    )
    assert gc.defense_mirror_problems(f) == []


def test_ppp_and_scoring_do_not_depend_on_any_epa_input():
    base = _build()
    perturbed_plays = _plays()
    perturbed_plays["ppa"] = 99.0
    perturbed_plays.loc[[0, 3], ["ppa", "ppa_missing"]] = [None, True]
    perturbed = _build(perturbed_plays)
    independent = [m for m in b.reg.BY_NAME if not b.reg.BY_NAME[m].requires_ppa]
    for metric in independent:
        pd.testing.assert_frame_equal(
            base[base.metric == metric].reset_index(drop=True),
            perturbed[perturbed.metric == metric].reset_index(drop=True),
        )
    assert not base[base.metric.isin(["eligible_epa"])].equals(
        perturbed[perturbed.metric.isin(["eligible_epa"])]
    )


def test_an_unresolved_scoring_marker_withholds_that_teams_point_metrics_only():
    marker = _event("m1", "A", None, category="unresolved")
    f = _build(ledger=_ledger(marker))
    assert gc.team_game_metrics_problems(f) == []
    for metric in b.POINT_METRICS:
        row = _get(f, "A", "offense", metric)
        assert (
            row.coverage_status == "missing"
            and row.missing_reason == "unresolved_scoring_stream"
        ), metric
    assert _get(f, "B", "offense", "ppp").coverage_status == "observed"
    assert _get(f, "A", "offense", "success_rate").coverage_status == "observed"
    assert _get(f, "A", "offense", "eligible_epa").coverage_status == "observed"


def test_reverted_rows_retain_baseline_points():
    reverted = _event("e3", "A", 7.0, drive=3, admission="reverted_unverified")
    f = _build(ledger=_ledger(reverted))
    assert (
        _get(f, "A", "offense", "offensive_possession_points").value == 14
    )  # reverted output carries baseline points, not rejected candidate points


def test_no_certified_final_withholds_points_scored_with_a_reason():
    f = _build(games=_games(home_points=None, away_points=10))
    row = _get(f, "A", "offense", "points_scored")
    assert (
        row.coverage_status == "missing"
        and row.missing_reason == "no_certified_final"
        and pd.isna(row.value)
    )
    assert _get(f, "B", "defense", "points_scored").coverage_status == "missing"
    assert gc.team_game_metrics_problems(f) == []


def test_a_zero_event_population_has_an_undefined_ratio_not_zero():
    plays = _plays()
    plays = plays[~((plays.offense == "A") & (plays.dropback == 1))]
    f = _build(plays)
    row = _get(f, "A", "offense", "epa_pass")
    assert (
        row.denominator == 0
        and pd.isna(row.value)
        and row.coverage_status == "observed"
    )
    assert gc.team_game_metrics_problems(f) == []


def test_missing_required_columns_fail_loudly_not_with_defaults():
    with pytest.raises(b.BuilderInputError, match="plays missing columns"):
        _build(plays=_plays().drop(columns=["success"]))


def test_aggregation_sums_numerators_and_denominators_not_game_means():
    g1 = _build()
    g2 = g1.copy()
    g2["week"] = 2
    g2["game_id"] = 2
    rows = g2[
        (g2.metric == "success_rate") & (g2.team == "A") & (g2.role == "offense")
    ].index
    g2.loc[rows, ["numerator", "denominator", "value"]] = [1.0, 1.0, 1.0]
    both = pd.concat([g1, g2], ignore_index=True)
    agg = b.aggregate_through_week(both, as_of_week=3)
    row = agg[
        (agg.team == "A") & (agg.role == "offense") & (agg.metric == "success_rate")
    ].iloc[0]
    assert (
        row.numerator == 4.0
        and row.denominator == 5.0
        and row.value == pytest.approx(0.8)
    )  # not (0.75 + 1) / 2
    assert row.games == 2 and row.coverage_status == "observed"


def test_a_missing_game_withholds_the_aggregate_but_not_independent_metrics():
    plays = _plays()
    plays.loc[0, ["ppa", "ppa_missing"]] = [None, True]
    g1 = _build(plays)
    g2 = _build()
    g2["week"] = 2
    g2["game_id"] = 2
    agg = b.aggregate_through_week(pd.concat([g1, g2], ignore_index=True), as_of_week=3)
    epa = agg[
        (agg.team == "A") & (agg.role == "offense") & (agg.metric == "eligible_epa")
    ].iloc[0]
    assert (
        epa.coverage_status == "missing"
        and epa.games_missing == 1
        and pd.isna(epa.value)
        and epa.missing_reason == "ppa_incomplete"
    )
    ppp = agg[(agg.team == "A") & (agg.role == "offense") & (agg.metric == "ppp")].iloc[
        0
    ]
    assert ppp.coverage_status == "observed" and ppp.value == pytest.approx(3.5)


def test_absent_source_requires_coverage_instead_of_inventing_zero():
    f = b.build_team_game_metrics(
        plays=_plays().iloc[:0],
        possessions=_possessions().iloc[:0],
        ledger=_ledger().iloc[:0],
        games=_games(),
        source_versions=VERSIONS,
        timing_class="reconstructed",
    )
    for metric in (
        "ppp",
        "eligible_scrimmage_plays",
        "offensive_possession_points",
        "eligible_epa",
    ):
        row = _get(f, "A", "offense", metric)
        assert row.coverage_status == "missing"
        assert pd.isna(row.value) and pd.isna(row.numerator)
    assert _get(f, "A", "offense", "points_scored").value == 17


def test_verified_scoreless_game_remains_zero():
    f = _build(ledger=_ledger().iloc[:0], games=_games(home_points=0, away_points=0))
    assert _get(f, "A", "offense", "ppp").value == 0
    assert _get(f, "A", "offense", "ppp").coverage_status == "observed"


def test_unknown_opportunity_and_field_position_withhold_dependent_metrics():
    possessions = _possessions()
    possessions["scoring_opportunity"] = possessions.scoring_opportunity.astype(object)
    possessions.loc[0, ["scoring_opportunity", "start_yards_to_goal"]] = [None, None]
    coverage = pd.DataFrame(
        [
            dict(
                season=2026,
                game_id=1,
                team=t,
                plays_complete=True,
                possessions_complete=True,
                scoring_complete=True,
            )
            for t in ("A", "B")
        ]
    )
    f = b.build_team_game_metrics(
        plays=_plays(),
        possessions=possessions,
        ledger=_ledger(),
        games=_games(),
        source_versions=VERSIONS,
        timing_class="reconstructed",
        coverage=coverage,
    )
    for metric in ("scoring_opp_rate", "pts_per_scoring_opp", "avg_start_field_pos"):
        row = _get(f, "A", "offense", metric)
        assert row.coverage_status == "missing" and pd.isna(row.value)
    assert _get(f, "A", "offense", "avg_start_field_pos").denominator == 2
    assert _get(f, "A", "offense", "ppp").value == 3.5


def test_same_team_and_game_ids_in_different_seasons_do_not_mix():
    current = _build()
    previous = current.assign(season=2025)
    result = b.aggregate_through_week(pd.concat([current, previous]), as_of_week=2)
    rows = result.query("team == 'A' and role == 'offense' and metric == 'ppp'")
    assert set(rows.season) == {2025, 2026}
    assert list(rows.games) == [1, 1]
    assert list(rows.value) == [3.5, 3.5]


def test_missing_success_does_not_shrink_eligible_population():
    plays = _plays()
    plays.loc[0, "success"] = None
    row = _get(_build(plays), "A", "offense", "success_rate")
    assert row.denominator == 4 and row.observed_count == 3
    assert row.coverage_status == "missing" and pd.isna(row.numerator)


def test_candidate_disposition_cannot_enter_final_metric_consumer():
    ledger = _ledger()
    ledger.loc[0, "admission"] = "candidate"
    with pytest.raises(b.BuilderInputError, match="candidate"):
        _build(ledger=ledger)
