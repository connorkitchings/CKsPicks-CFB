"""CFBD drive corroboration: the four frozen checks and the group rule, on synthetic drives."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.ratings import drive_corroboration as dc


def _drive(
    number, offense, home_off, start, end, period=1, end_period=None, drive_id=None
):
    """A CFBD-shaped drive; ``start``/``end`` are (home, away) scores."""
    s_off, s_def = (start[0], start[1]) if home_off else (start[1], start[0])
    e_off, e_def = (end[0], end[1]) if home_off else (end[1], end[0])
    return {
        "id": drive_id or f"d{number}",
        "driveNumber": number,
        "offense": offense,
        "defense": "B" if offense == "A" else "A",
        "isHomeOffense": home_off,
        "startPeriod": period,
        "endPeriod": end_period or period,
        "startOffenseScore": s_off,
        "endOffenseScore": e_off,
        "startDefenseScore": s_def,
        "endDefenseScore": e_def,
    }


def _clean():
    # A (home) scores a touchdown plus conversion, B (away) kicks a field goal.
    return pd.DataFrame(
        [
            _drive(1, "A", True, (0, 0), (7, 0), period=1),
            _drive(2, "B", False, (7, 0), (7, 3), period=2),
            _drive(3, "A", True, (7, 3), (7, 3), period=3),
        ]
    )


KW = dict(
    home="A",
    away="B",
    final_home=7,
    final_away=3,
    home_line_scores=[7, 0, 0, 0],
    away_line_scores=[0, 3, 0, 0],
    ledger_regulation_all={(1, "A"), (2, "B"), (3, "A")},
    ledger_regulation_eligible={(1, "A"), (2, "B"), (3, "A")},
)


def _check(drives=None, **over):
    return dc.check_game(_clean() if drives is None else drives, **{**KW, **over})


def test_a_clean_game_passes_all_four_checks():
    r = _check()
    assert r["usable"] and r["reasons"] == []


def test_check1_final_opening_and_quarter_totals():
    assert (
        "c1:last_drive_end_differs_from_certified_final"
        in _check(final_home=10)["reasons"]
    )
    bad_open = _clean()
    bad_open.loc[0, ["startOffenseScore"]] = 3
    assert "c1:first_drive_not_0_0" in _check(bad_open)["reasons"]
    # Line scores say B scored in the 3rd quarter, but the drives put that field goal in the 2nd.
    wrong = _check(away_line_scores=[0, 0, 3, 0])
    assert "c1:cumulative_through_period_2_differs_from_line_scores" in wrong["reasons"]
    assert not wrong["usable"]


def test_a_drive_that_spans_a_quarter_boundary_counts_in_the_period_it_ends():
    spanning = pd.DataFrame(
        [
            _drive(1, "A", True, (0, 0), (7, 0), period=1, end_period=2),
            _drive(2, "B", False, (7, 0), (7, 3), period=2),
        ]
    )
    sets = {(1, "A"), (2, "B")}
    ok = _check(
        spanning,
        final_home=7,
        final_away=3,
        home_line_scores=[0, 7, 0, 0],
        away_line_scores=[0, 3, 0, 0],
        ledger_regulation_all=sets,
        ledger_regulation_eligible=sets,
    )
    assert ok["c1"], ok["reasons"]


def test_non_drive_points_are_explicit_and_relax_the_mid_half_quarters():
    gap = pd.DataFrame(
        [
            _drive(1, "A", True, (0, 0), (0, 0), period=1),
            _drive(
                2, "B", False, (0, 6), (0, 6), period=2
            ),  # B scored 6 between drives
        ]
    )
    sets = {(1, "A"), (2, "B")}
    r = _check(
        gap,
        final_home=0,
        final_away=6,
        home_line_scores=[0, 0, 0, 0],
        away_line_scores=[6, 0, 0, 0],
        ledger_regulation_all=sets,
        ledger_regulation_eligible=sets,
    )
    assert r["non_drive_points"] == 6 and r["c1"], r["reasons"]


def test_a_final_total_match_alone_does_not_make_a_game_usable():
    # Every CFBD drive must be a ledger possession ...
    small = {(1, "A"), (2, "B")}
    missing = _check(ledger_regulation_all=small, ledger_regulation_eligible=small)
    assert missing["c1"] and not missing["c2"] and not missing["usable"]
    assert missing["c2_cfbd_not_in_ledger"] == 1
    assert "c2:cfbd_drive_missing_from_ledger" in missing["reasons"]
    # ... and every eligible ledger possession must be a CFBD drive.
    big = {(1, "A"), (2, "B"), (3, "A"), (4, "B")}
    extra = _check(ledger_regulation_all=big, ledger_regulation_eligible=big)
    assert not extra["c2"] and extra["c2_eligible_not_in_cfbd"] == 1


def test_ledger_only_possessions_without_eligible_plays_are_not_drives():
    all_rows = {
        (1, "A"),
        (2, "B"),
        (3, "A"),
        (3, "B"),
    }  # (3, "B") is a return-only possession
    r = _check(
        ledger_regulation_all=all_rows,
        ledger_regulation_eligible={(1, "A"), (2, "B"), (3, "A")},
    )
    assert r["c2"] and r["usable"] and not r["c2_strict"]


def test_check3_rejects_impossible_drive_deltas():
    one_point = _clean()
    one_point.loc[0, "endOffenseScore"] = 1
    r = _check(one_point, final_home=1)
    assert not r["c3"] and any(x.startswith("c3:drive_1") for x in r["reasons"])
    assert _check()["c3"]


def test_check4_regression_duplicates_excess_and_period_order():
    regress = _clean()
    regress.loc[2, ["startOffenseScore", "startDefenseScore"]] = [2, 3]
    assert "c4:score_regression_between_drives" in _check(regress)["reasons"]
    dup = _clean()
    dup.loc[2, "driveNumber"] = 2
    dup.loc[2, "id"] = "d3b"
    assert "c4:duplicate_drive_number" in _check(dup)["reasons"]
    assert "c4:excess_points_over_certified_final" in _check(final_home=4)["reasons"]
    order = _clean()
    order.loc[2, "startPeriod"] = 1
    order.loc[2, "endPeriod"] = 1
    order.loc[1, "startPeriod"] = 2
    assert "c4:period_order_conflict" in _check(order)["reasons"]


def test_no_drives_is_unusable():
    r = _check(pd.DataFrame())
    assert not r["usable"] and "no_drives" in r["reasons"]


def test_cfbd_points_split_offense_and_defense_scoring():
    drives = pd.DataFrame(
        [_drive(1, "A", True, (0, 0), (6, 2))]
    )  # TD, then a defensive 2 on the conversion
    table = dc.cfbd_points_by_drive(drives, "A", "B")
    assert table[("A", 1)] == (6, 0) and table[("B", 1)] == (0, 2)


def _events(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "team",
            "drive_number",
            "score_increment",
            "unit_category",
            "period_class",
        ],
    )


def test_ledger_points_ignore_overtime_and_split_units():
    ev = _events(
        [
            ("A", 1, 7, "offense", "regulation"),
            ("A", 1, 6, "non_offense", "regulation"),
            ("A", 9, 3, "offense", "overtime"),
        ]
    )
    assert dc.ledger_points_by_drive(ev) == {("A", 1): (7.0, 6.0)}


def test_group_statuses():
    cfbd = {("A", 1): (7, 0)}
    base_wrong = {("A", 1): (0.0, 0.0)}  # baseline rolled the touchdown back
    cand_right = {("A", 1): (7.0, 0.0)}
    kw = dict(game_usable=True, has_cfbd=True)
    assert (
        dc.classify_group({1}, "A", cfbd, base_wrong, cand_right, **kw)
        == "corroborated"
    )
    assert (
        dc.classify_group({1}, "A", cfbd, cand_right, base_wrong, **kw)
        == "cfbd_supports_baseline"
    )
    assert (
        dc.classify_group({1}, "A", cfbd, cand_right, cand_right, **kw)
        == "indistinguishable_at_drive_level"
    )
    other = {("A", 1): (3.0, 0.0)}
    assert (
        dc.classify_group({1}, "A", cfbd, base_wrong, other, **kw)
        == "cfbd_matches_neither"
    )
    assert (
        dc.classify_group(
            {1}, "A", cfbd, base_wrong, cand_right, game_usable=False, has_cfbd=True
        )
        == "game_unusable"
    )
    assert (
        dc.classify_group(
            {1}, "A", cfbd, base_wrong, cand_right, game_usable=True, has_cfbd=False
        )
        == "no_cfbd_data"
    )
    assert (
        dc.classify_group({9}, "A", cfbd, base_wrong, cand_right, **kw)
        == "no_regulation_drive"
    )


def test_every_touched_drive_must_match_for_a_group_to_be_corroborated():
    cfbd = {("A", 1): (7, 0), ("A", 2): (3, 0)}
    base = {("A", 1): (0.0, 0.0), ("A", 2): (3.0, 0.0)}
    cand_partly = {("A", 1): (7.0, 0.0), ("A", 2): (0.0, 0.0)}
    kw = dict(game_usable=True, has_cfbd=True)
    assert (
        dc.classify_group({1, 2}, "A", cfbd, base, cand_partly, **kw)
        == "cfbd_matches_neither"
    )
    cand_all = {("A", 1): (7.0, 0.0), ("A", 2): (3.0, 0.0)}
    assert dc.classify_group({1, 2}, "A", cfbd, base, cand_all, **kw) == "corroborated"


def test_parse_drives_dedupes_and_canonicalizes():
    rows = [_drive(1, "A", True, (0, 0), (0, 0)), _drive(1, "A", True, (0, 0), (0, 0))]
    frame = dc.parse_drives(rows, lambda name: name.lower())
    assert len(frame) == 1 and frame.iloc[0]["offense"] == "a"
