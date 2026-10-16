"""Negative and positive tests of the chart reconciliation (adjusted recomputation)."""

from __future__ import annotations

import copy

import pytest

from cks_picks_cfb.charts.adjusted_epa import build_team_adjusted_epa
from cks_picks_cfb.charts.reconciliation import chart_problems
from tests.test_charts_module import TEAMS, game_rows

ACTIVE_WEEK = 5  # games run in weeks 0-4: adjusted windows 3, 4 and 5


def full_rows():
    """Mirrored team-game rows with every column the reconciliation reads."""
    rows = []
    for row in game_rows().to_dict("records"):
        rows.append(
            {
                **row,
                "points_for": 28 if row["site"] == "home" else 21,
                "points_against": 21 if row["site"] == "home" else 28,
                "off_plays": row["off_epa_n"] + 2,
                "off_success_n": row["off_epa_n"] + 1,
                "off_success_sum": float(row["off_epa_n"] // 2),
                "def_plays": row["def_epa_n"] + 2,
                "def_success_n": row["def_epa_n"] + 1,
                "def_success_sum": float(row["def_epa_n"] // 2),
            }
        )
    return rows


def stats_for(rows, as_of_week):
    out = []
    for team in TEAMS:
        mine = [r for r in rows if r["team"] == team and r["week"] < as_of_week]
        if not mine:
            continue
        for role, prefix in (("offense", "off"), ("defense", "def")):
            for metric, total, count in (
                ("success_rate", "success_sum", "success_n"),
                ("ppa_per_play", "epa_sum", "epa_n"),
            ):
                n = sum(r[f"{prefix}_{count}"] for r in mine)
                out.append(
                    {
                        "season": 2026,
                        "as_of_week": as_of_week,
                        "team": team,
                        "role": role,
                        "metric": metric,
                        "value": sum(r[f"{prefix}_{total}"] for r in mine) / n
                        if n
                        else None,
                        "n": n,
                        "games": len(mine),
                    }
                )
    return out


@pytest.fixture
def tables():
    rows = full_rows()
    roster = [{"season": 2026, "team": t, "conference": "X"} for t in TEAMS]
    adjusted = build_team_adjusted_epa(
        rows, set(TEAMS), season=2026, active_week=ACTIVE_WEEK
    )
    stats = [s for week in (1, 2, 3, 4, 5) for s in stats_for(rows, week)]
    return {
        "roster": roster,
        "game_rows": rows,
        "adjusted_rows": adjusted,
        "stats_rows": stats,
    }


def check(tables):
    problems, observed = chart_problems(**tables, season=2026, active_week=ACTIVE_WEEK)
    return problems, observed


def test_consistent_tables_reconcile(tables):
    problems, observed = check(tables)
    assert problems == []
    assert observed["adjusted_windows"] == 3
    assert {r["as_of_week"] for r in tables["adjusted_rows"]} == {3, 4, 5}


def mutated(tables, edit):
    copy_ = copy.deepcopy(tables)
    edit(copy_)
    return check(copy_)[0]


def test_perturbed_adjusted_value_fails(tables):
    def edit(t):
        t["adjusted_rows"][0]["adjusted_epa_per_play"] += 1e-6

    assert any("adjusted_epa_per_play" in p for p in mutated(tables, edit))


def test_a_value_within_tolerance_still_passes(tables):
    def edit(t):
        t["adjusted_rows"][0]["adjusted_epa_per_play"] += 1e-12

    assert mutated(tables, edit) == []


def test_wrong_rank_fails(tables):
    def edit(t):
        t["adjusted_rows"][0]["adjusted_rank"] += 1

    assert any("adjusted_rank" in p for p in mutated(tables, edit))


def test_wrong_cohort_size_and_venue_flag_fail(tables):
    def cohort(t):
        t["adjusted_rows"][1]["cohort_size"] += 1

    def flag(t):
        t["adjusted_rows"][2]["venue_identified"] = False

    assert any("cohort_size" in p for p in mutated(tables, cohort))
    assert any("venue_identified" in p for p in mutated(tables, flag))


def test_missing_and_extra_windows_fail(tables):
    def missing(t):
        t["adjusted_rows"] = [r for r in t["adjusted_rows"] if r["as_of_week"] != 4]

    def extra(t):
        t["adjusted_rows"].append({**t["adjusted_rows"][0], "as_of_week": 6})

    assert any("missing" in p for p in mutated(tables, missing))
    assert any("unexpected" in p for p in mutated(tables, extra))


def test_missing_or_extra_team_role_row_fails(tables):
    def drop(t):
        t["adjusted_rows"].pop(0)

    def extra(t):
        row = copy.deepcopy(t["adjusted_rows"][0])
        row["team"] = "ZZ"
        t["adjusted_rows"].append(row)

    assert any("missing" in p for p in mutated(tables, drop))
    assert any("unexpected" in p for p in mutated(tables, extra))


def test_team_outside_the_roster_fails(tables):
    def edit(t):
        t["roster"] = [r for r in t["roster"] if r["team"] != "A"]

    problems = mutated(tables, edit)
    assert any("outside the roster" in p for p in problems)


def test_broken_mirror_fails(tables):
    def edit(t):
        t["game_rows"][0]["def_success_sum"] += 1.0

    assert any("not mirrored" in p for p in mutated(tables, edit))


def test_cumulative_mismatch_fails(tables):
    def value(t):
        row = next(
            s
            for s in t["stats_rows"]
            if s["metric"] == "success_rate" and s["as_of_week"] == 5
        )
        row["value"] += 0.01

    def count(t):
        row = next(s for s in t["stats_rows"] if s["metric"] == "ppa_per_play")
        row["n"] += 1

    def games(t):
        t["stats_rows"][0]["games"] += 1

    assert any("value" in p for p in mutated(tables, value))
    assert any(" n " in p for p in mutated(tables, count))
    assert any("games" in p for p in mutated(tables, games))


def test_null_metric_where_nothing_was_observed_reconciles(tables):
    """A team with no valid offensive EPA anywhere has a null value and n = 0."""

    def edit(t):
        for row in t["game_rows"]:
            if row["team"] == "H":
                row["off_epa_n"], row["off_epa_sum"] = 0, 0.0
            if row["opponent"] == "H":
                row["def_epa_n"], row["def_epa_sum"] = 0, 0.0
        t["adjusted_rows"] = build_team_adjusted_epa(
            t["game_rows"], set(TEAMS), season=2026, active_week=ACTIVE_WEEK
        )
        t["stats_rows"] = [
            s for week in (1, 2, 3, 4, 5) for s in stats_for(t["game_rows"], week)
        ]

    copy_ = copy.deepcopy(tables)
    edit(copy_)
    assert not any(
        r["team"] == "H" and r["role"] == "offense" for r in copy_["adjusted_rows"]
    )
    assert check(copy_)[0] == []


def release_games(tables):
    """The release's own games and finals matching the mirrored chart rows."""
    games, results = {}, {}
    for row in tables["game_rows"]:
        if row["site"] == "home":
            games[row["game_id"]] = {
                "game_id": row["game_id"],
                "week": row["week"],
                "home_team": row["team"],
                "away_team": row["opponent"],
            }
            results[row["game_id"]] = {
                "game_id": row["game_id"],
                "home_points": row["points_for"],
                "away_points": row["points_against"],
            }
    return list(games.values()), list(results.values())


def check_with_games(tables, games, results):
    return chart_problems(
        **tables, games=games, results=results, season=2026, active_week=ACTIVE_WEEK
    )[0]


def test_rows_agree_with_the_release_games_and_finals(tables):
    games, results = release_games(tables)
    assert check_with_games(tables, games, results) == []

    wrong_points = copy.deepcopy(results)
    wrong_points[0]["home_points"] += 1
    assert any(
        "points differ" in p for p in check_with_games(tables, games, wrong_points)
    )

    wrong_week = copy.deepcopy(games)
    wrong_week[0]["week"] += 1
    assert any(
        "week differs" in p for p in check_with_games(tables, wrong_week, results)
    )

    swapped = copy.deepcopy(games)
    swapped[0]["home_team"], swapped[0]["away_team"] = (
        swapped[0]["away_team"],
        swapped[0]["home_team"],
    )
    problems = check_with_games(tables, swapped, results)
    assert any("site contradicts" in p for p in problems)

    assert any("absent" in p for p in check_with_games(tables, games[1:], results))
    assert any("absent" in p for p in check_with_games(tables, games, results[1:]))


def test_tables_survive_a_json_round_trip_and_still_reconcile(tables):
    """Staged payloads are JSON: ints, bools and floats must compare exactly after it."""
    import json

    again = json.loads(json.dumps(tables))
    assert check(again)[0] == []
    again["adjusted_rows"][0]["adjusted_epa_per_play"] += 1e-6
    assert check(again)[0]


def test_a_one_role_team_passes_coverage_in_either_direction(tables):
    def one_role(t, offense_only):
        extra = [
            {
                "season": 2026,
                "week": 0,
                "game_id": 90,
                "team": "Z",
                "opponent": "A",
                "site": "home",
                "points_for": 3,
                "points_against": 0,
                "off_plays": 30,
                "off_success_n": 30,
                "off_success_sum": 12.0,
                "off_epa_n": 30 if offense_only else 0,
                "off_epa_sum": 6.0 if offense_only else 0.0,
                "def_plays": 30,
                "def_success_n": 30,
                "def_success_sum": 12.0,
                "def_epa_n": 0 if offense_only else 30,
                "def_epa_sum": 0.0 if offense_only else 6.0,
            },
        ]
        mirror = {
            **extra[0],
            "team": "A",
            "opponent": "Z",
            "site": "away",
            "points_for": 0,
            "points_against": 3,
            **{f"off_{k}": extra[0][f"def_{k}"] for k in ("epa_n", "epa_sum")},
            **{f"def_{k}": extra[0][f"off_{k}"] for k in ("epa_n", "epa_sum")},
        }
        t["game_rows"] += [extra[0], mirror]
        t["roster"].append({"season": 2026, "team": "Z", "conference": "X"})
        t["adjusted_rows"] = build_team_adjusted_epa(
            t["game_rows"],
            {r["team"] for r in t["roster"]},
            season=2026,
            active_week=ACTIVE_WEEK,
        )
        t["stats_rows"] = []
        roles = {r["role"] for r in t["adjusted_rows"] if r["team"] == "Z"}
        assert roles == ({"offense"} if offense_only else {"defense"})

    for offense_only in (True, False):
        copy_ = copy.deepcopy(tables)
        one_role(copy_, offense_only)
        assert check(copy_)[0] == []
