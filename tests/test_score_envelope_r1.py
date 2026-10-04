"""R1 candidate and the 5A group diff, on synthetic ledgers (frozen definitions)."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.ratings import score_envelope_r1 as r1


def _plays(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "season",
            "game_id",
            "quarter",
            "drive_number",
            "play_number",
            "offense",
            "defense",
            "offense_score",
            "defense_score",
        ],
    )


def test_envelope_ignores_a_dip_and_never_exceeds_the_final():
    plays = _plays(
        [
            (2026, 1, 1, 1, 1, "A", "B", 7, 0),
            (2026, 1, 1, 2, 1, "A", "B", 3, 0),  # provider dip: 7 -> 3
            (2026, 1, 2, 3, 1, "A", "B", 10, 0),
            (2026, 1, 4, 4, 1, "A", "B", 14, 0),  # overshoots the certified final of 10
        ]
    )
    out, unresolved = r1.apply_r1(plays, {(1, "A"): 10.0, (1, "B"): 0.0})
    assert list(out["offense_score"]) == [7, 7, 10, 10]
    assert unresolved == set()


def test_envelope_that_cannot_reach_the_final_is_left_unresolved():
    plays = _plays(
        [(2026, 1, 1, 1, 1, "A", "B", 12, 0), (2026, 1, 4, 2, 1, "A", "B", 12, 0)]
    )
    _, unresolved = r1.apply_r1(plays, {(1, "A"): 18.0, (1, "B"): 0.0})
    assert unresolved == {
        (1, "A")
    }  # New Mexico State style: max 12 against a final of 18


def test_restoration_jump_needs_an_earlier_dip_and_a_rise_above_eight():
    dip_then_big_rise = _plays(
        [
            (2026, 1, 1, 1, 1, "A", "B", 14, 0),
            (2026, 1, 1, 2, 1, "A", "B", 7, 0),
            (2026, 1, 1, 3, 1, "A", "B", 21, 0),  # +14 after a dip
        ]
    )
    assert r1.restoration_jumps(dip_then_big_rise) == {(1, "A")}
    big_rise_no_dip = _plays(
        [(2026, 1, 1, 1, 1, "A", "B", 0, 0), (2026, 1, 1, 2, 1, "A", "B", 9, 0)]
    )
    assert r1.restoration_jumps(big_rise_no_dip) == set()
    small_rise = _plays(
        [
            (2026, 1, 1, 1, 1, "A", "B", 14, 0),
            (2026, 1, 1, 2, 1, "A", "B", 7, 0),
            (2026, 1, 1, 3, 1, "A", "B", 14, 0),
        ]
    )
    assert r1.restoration_jumps(small_rise) == set()


def _event(event_id, increment, drive=1, **over):
    base = {
        "season": 2026,
        "game_id": 1,
        "source_event_id": event_id,
        "team": "A",
        "drive_number": drive,
        "period_class": "regulation",
        "score_increment": increment,
        "scoring_category": "eligible_regulation_offense",
        "unit_category": "offense",
        "associated_possession_id": f"p{drive}",
        "conversion_for_event_id": None,
        "quality_reason": None,
        "timing_class": "reconstructed",
    }
    return {**base, **over}


def _ledger(*events):
    return pd.DataFrame(list(events))


def test_identical_ledgers_have_no_groups():
    ledger = _ledger(_event("e1", 7), _event("e2", 3, drive=2))
    assert r1.changed_groups(ledger, ledger.copy()).empty


def test_a_rollback_recovered_by_r1_is_one_points_recovery_group_with_a_dip_restore_cause():
    base = _ledger(
        _event("e1", 7),
        _event("e2", 0, drive=2, quality_reason="score_regression_rollback"),
    )
    cand = _ledger(_event("e1", 7), _event("e2", 7, drive=2))
    groups = r1.changed_groups(base, cand)
    assert len(groups) == 1
    row = groups.iloc[0]
    assert row["channel"] == "points_recovery" and row["net_points"] == 7.0
    assert row["primary_cause"] == "dip_restore" and row["flag_dip_restore"]
    assert len(row["group_id"]) == 16


def test_an_unchanged_event_splits_two_changed_events_into_two_groups():
    base = _ledger(
        _event("e1", 7, quality_reason="x"),
        _event("e2", 3, drive=2),
        _event("e3", 7, drive=3, quality_reason="x"),
    )
    cand = _ledger(_event("e1", 7), _event("e2", 3, drive=2), _event("e3", 7, drive=3))
    assert len(r1.changed_groups(base, cand)) == 2


def test_adjacent_changed_events_form_one_region():
    base = _ledger(
        _event("e1", 7, associated_possession_id="p1"),
        _event("e2", 3, drive=2, associated_possession_id="p2"),
    )
    cand = _ledger(
        _event("e1", 7, associated_possession_id="q1"),
        _event("e2", 3, drive=2, associated_possession_id="q2"),
    )
    groups = r1.changed_groups(base, cand)
    assert len(groups) == 1 and groups.iloc[0]["events"] == 2
    assert groups.iloc[0]["channel"] == "attribution_only"
    assert groups.iloc[0]["primary_cause"] == "category_possession_reassignment"


def test_a_conversion_link_merges_regions_separated_by_an_unchanged_event():
    base = _ledger(
        _event("td", 6, associated_possession_id="p1"),
        _event("mid", 3, drive=2),
        _event(
            "pat",
            1,
            drive=3,
            conversion_for_event_id="td",
            associated_possession_id="p1",
        ),
    )
    cand = _ledger(
        _event("td", 6, associated_possession_id="q1"),
        _event("mid", 3, drive=2),
        _event(
            "pat",
            1,
            drive=3,
            conversion_for_event_id="td",
            associated_possession_id="q1",
        ),
    )
    groups = r1.changed_groups(base, cand)
    assert (
        len(groups) == 1 and groups.iloc[0]["events"] == 2
    )  # td and pat, linked by the conversion


def test_final_cap_and_incomplete_stream_causes_and_precedence():
    capped = _ledger(
        _event(
            "e1",
            0,
            scoring_category="unresolved",
            unit_category="unknown",
            quality_reason="exceeds_repaired_final",
        )
    )
    clipped = _ledger(
        _event(
            "e1",
            0,
            scoring_category="unresolved",
            unit_category="unknown",
            quality_reason="exceeds_repaired_final",
        )
    )
    cand = _ledger(_event("e1", 6))
    g = r1.changed_groups(capped, cand).iloc[0]
    assert (
        g["flag_final_cap"]
        and g["primary_cause"] == "final_cap"
        and not g["flag_incomplete_stream"]
    )
    # An unresolved marker that is not a final-cap marker is an incomplete stream, which outranks the rest.
    unresolved = _ledger(
        _event(
            "e1",
            0,
            scoring_category="unresolved",
            unit_category="unknown",
            quality_reason="malformed_score",
        )
    )
    g2 = r1.changed_groups(unresolved, cand).iloc[0]
    assert g2["primary_cause"] == "incomplete_stream"
    # restoration_gt8 outranks dip_restore when both apply.
    rolled = _ledger(_event("e1", 0, quality_reason="score_regression_rollback"))
    g3 = r1.changed_groups(rolled, cand, restoration_team_games={(1, "A")}).iloc[0]
    assert (
        g3["flag_dip_restore"]
        and g3["flag_restoration_gt8"]
        and g3["primary_cause"] == "restoration_gt8"
    )
    assert clipped is not None


def test_an_event_present_on_one_side_only_is_a_change_and_summary_counts_by_dimension():
    base = _ledger(_event("e1", 7))
    cand = _ledger(_event("e1", 7), _event("e2", 3, drive=2))
    groups = r1.changed_groups(base, cand)
    assert len(groups) == 1 and groups.iloc[0]["net_points"] == 3.0
    summary = r1.summarize_groups(groups)
    assert summary["groups"] == 1 and summary["points_recovered"] == 3.0
    assert summary["by_channel"] == {"points_recovery": 1} and summary["by_season"] == {
        2026: 1
    }
    assert r1.summarize_groups(r1.changed_groups(base, base.copy()))["groups"] == 0
