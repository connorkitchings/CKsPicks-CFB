"""Conversion of the existing baseline ledger and possessions to the v1 contracts."""

from __future__ import annotations

import pandas as pd
import pytest

from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.metrics import contracts as gc
from cks_picks_cfb.metrics import ledger as ml

VERSIONS = {"byplay": "v1"}


def _plays():
    rows = [
        # drive 1: A scores a touchdown (6) and the extra point (7) on the next play
        dict(
            season=2026,
            game_id=1,
            drive_number=1,
            play_number=1,
            quarter=1,
            offense="A",
            defense="B",
            offense_score=0,
            defense_score=0,
        ),
        dict(
            season=2026,
            game_id=1,
            drive_number=1,
            play_number=2,
            quarter=1,
            offense="A",
            defense="B",
            offense_score=6,
            defense_score=0,
        ),
        dict(
            season=2026,
            game_id=1,
            drive_number=1,
            play_number=3,
            quarter=1,
            offense="A",
            defense="B",
            offense_score=7,
            defense_score=0,
        ),
        # drive 2: B (the defense here would not matter); B scores a field goal
        dict(
            season=2026,
            game_id=1,
            drive_number=2,
            play_number=1,
            quarter=2,
            offense="B",
            defense="A",
            offense_score=0,
            defense_score=7,
        ),
        dict(
            season=2026,
            game_id=1,
            drive_number=2,
            play_number=2,
            quarter=2,
            offense="B",
            defense="A",
            offense_score=3,
            defense_score=7,
        ),
    ]
    return pd.DataFrame(rows)


def _events():
    def e(
        play,
        team,
        inc,
        category="eligible_regulation_offense",
        unit="offense",
        assoc="2026:1:1:2",
        conv=None,
        drive=1,
        reason=None,
    ):
        return dict(
            season=2026,
            game_id=1,
            source_event_id=f"2026:1:{drive}:{play}",
            team=team,
            drive_number=drive,
            period_class="regulation",
            score_increment=inc,
            scoring_category=category,
            unit_category=unit,
            associated_possession_id=assoc,
            conversion_for_event_id=conv,
            quality_reason=reason,
            timing_class="live",
        )

    return pd.DataFrame(
        [
            e(2, "A", 6, assoc="2026:1:1:2"),
            e(3, "A", 1, assoc="2026:1:1:2", conv="2026:1:1:2"),
            e(2, "B", 3, assoc="2026:1:2:2", drive=2),
            e(
                1,
                "B",
                0,
                category="unresolved",
                unit="unknown",
                assoc=None,
                drive=2,
                reason="malformed_score",
            ),
        ]
    )


FINALS = {(1, "A"): 7.0, (1, "B"): 3.0}


def test_events_convert_to_a_valid_v1_ledger():
    v1 = ml.scoring_events_to_v1(
        _events(), _plays(), finals=FINALS, source_versions=VERSIONS
    )
    validate_frame(
        v1, schema_for("football_scoring_ledger", "football_scoring_ledger_v1")
    )
    poss = _possessions()
    assert gc.scoring_ledger_problems(v1, poss) == []
    assert set(v1.admission) == {"baseline_unchanged"} and set(v1.rule_version) == {
        "baseline_v1"
    }


def test_unresolved_markers_get_null_increments_not_zero():
    v1 = ml.scoring_events_to_v1(
        _events(), _plays(), finals=FINALS, source_versions=VERSIONS
    )
    marker = v1[v1.scoring_category == "unresolved"].iloc[0]
    assert (
        pd.isna(marker.score_increment) and marker.quality_reason == "malformed_score"
    )
    assert (v1[v1.scoring_category != "unresolved"].score_increment >= 0).all()


def test_the_play_id_reference_becomes_a_stable_possession_id():
    v1 = ml.scoring_events_to_v1(
        _events(), _plays(), finals=FINALS, source_versions=VERSIONS
    )
    td = v1[(v1.team == "A") & (v1.play_number == 2)].iloc[0]
    assert td.associated_possession_id == gc.possession_id_for(2026, 1, 1, "A")
    assert td.associated_possession_id != "2026:1:1:2"
    fg = v1[
        (v1.team == "B")
        & (v1.drive_number == 2)
        & (v1.scoring_category != "unresolved")
    ].iloc[0]
    assert fg.associated_possession_id == gc.possession_id_for(2026, 1, 2, "B")
    marker = v1[v1.scoring_category == "unresolved"].iloc[0]
    assert marker.associated_possession_id is None


def test_conversion_reference_and_score_context_are_carried():
    v1 = ml.scoring_events_to_v1(
        _events(), _plays(), finals=FINALS, source_versions=VERSIONS
    )
    pat = v1[(v1.team == "A") & (v1.play_number == 3)].iloc[0]
    assert pat.conversion_for_event_id == "2026:1:1:2" and pat.quarter == 1
    assert (pat.raw_score_before, pat.raw_score_after) == (
        6.0,
        7.0,
    )  # A's running score on the prior and the event play
    assert pat.certified_final == 7
    assert v1[v1.team == "B"].certified_final.iloc[0] == 3


def test_an_event_without_a_matching_play_is_an_error_not_a_guess():
    events = _events()
    events.loc[0, "source_event_id"] = "2026:1:9:9"
    with pytest.raises(ml.LedgerConversionError, match="no matching play"):
        ml.scoring_events_to_v1(
            events, _plays(), finals=FINALS, source_versions=VERSIONS
        )


def test_group_ids_default_to_unchanged_and_accept_a_mapping():
    v1 = ml.scoring_events_to_v1(
        _events(), _plays(), finals=FINALS, source_versions=VERSIONS
    )
    assert set(v1.allocation_group_id) == {"unchanged:1:A", "unchanged:1:B"}
    grouped = ml.scoring_events_to_v1(
        _events(),
        _plays(),
        finals=FINALS,
        source_versions=VERSIONS,
        groups={(1, "A", "2026:1:1:2"): "grp1"},
    )
    assert (
        grouped[
            (grouped.team == "A") & (grouped.play_number == 2)
        ].allocation_group_id.iloc[0]
        == "grp1"
    )


def test_admitted_groups_become_corroborated_with_evidence_and_rule_version():
    v1 = ml.scoring_events_to_v1(
        _events(),
        _plays(),
        finals=FINALS,
        source_versions=VERSIONS,
        groups={(1, "A", "2026:1:1:2"): "grp1"},
        admitted_evidence={"grp1": ("cfbd_drives:abc",)},
        admitted_rule_version="r1_envelope_v1",
    )
    hit = v1[v1.allocation_group_id == "grp1"]
    assert list(hit.admission) == ["corroborated"]
    assert list(hit.rule_version) == ["r1_envelope_v1"]
    assert list(hit.evidence_ids) == ['["cfbd_drives:abc"]']
    rest = v1[v1.allocation_group_id != "grp1"]
    assert set(rest.admission) == {"baseline_unchanged"}
    assert set(rest.rule_version) == {"baseline_v1"}
    assert gc.scoring_ledger_problems(v1) == []


def _existing_possessions():
    base = dict(
        season=2026,
        week=1,
        game_id=1,
        period_class="regulation",
        eligible_play_count=3,
        ineligible_play_count=0,
        mixed_eligibility=False,
        possession_eligible=True,
        source_play_ids="[]",
        quality_reason=None,
        timing_class="live",
    )
    return pd.DataFrame(
        [
            {**base, "drive_number": 1, "offense": "A", "defense": "B"},
            {**base, "drive_number": 2, "offense": "B", "defense": "A"},
            {**base, "drive_number": 3, "offense": "A", "defense": "B"},
        ]
    )


def _drives():
    return pd.DataFrame(
        [
            dict(
                game_id=1,
                drive_number=1,
                offense="A",
                start_yards_to_goal=75.0,
                had_scoring_opportunity=1,
            ),
            dict(
                game_id=1,
                drive_number=2,
                offense="B",
                start_yards_to_goal=70.0,
                had_scoring_opportunity=0,
            ),
        ]
    )


def _possessions():
    return ml.possessions_to_v1(
        _existing_possessions(), _drives(), source_versions=VERSIONS
    )


def test_possessions_gain_ids_field_position_and_opportunity_flags():
    v1 = _possessions()
    validate_frame(v1, schema_for("football_possessions", "football_possessions_v1"))
    assert gc.possessions_problems(v1) == []
    first = v1[v1.drive_number == 1].iloc[0]
    assert first.possession_id == gc.possession_id_for(2026, 1, 1, "A")
    assert first.start_yards_to_goal == 75.0 and first.scoring_opportunity is True
    assert v1[v1.drive_number == 2].iloc[0].scoring_opportunity is False


def test_a_possession_without_a_drive_row_keeps_nulls_not_defaults():
    third = _possessions()[lambda f: f.drive_number == 3].iloc[0]
    assert pd.isna(third.start_yards_to_goal) and third.scoring_opportunity is None
