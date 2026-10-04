"""Publish-boundary checks: fixture-driven, no cloud or database access."""

from __future__ import annotations

import json

import pytest

from cks_picks_cfb.quality import checks as q
from cks_picks_cfb.quality import publish as pub


def _rec(game_id=1, **over):
    base = {
        "game_id": game_id,
        "season": 2026,
        "week": 1,
        "home_team": "A",
        "away_team": "B",
        "predicted_spread": -3.0,
        "predicted_total": 50.0,
        "home_team_spread_line": None,
        "total_line": None,
        "predicted_spread_std_dev": 18.0,
        "predicted_total_std_dev": 17.5,
        "edge_spread": 1.0,
        "edge_total": 1.0,
        "spread_lean": None,
        "total_lean": None,
        "spread_market_quote_id": None,
        "total_market_quote_id": None,
        "source_quote_ids": json.dumps([]),
    }
    return {**base, **over}


def _pre(ctx):
    return {
        r.check_id: r
        for r in q.run_stage("publish", ctx, prefix="publish.pre.").results
    }


def _post(ctx):
    return {
        r.check_id: r
        for r in q.run_stage("publish", ctx, prefix="publish.post.").results
    }


def test_publish_checks_are_blocking_and_skip_without_inputs():
    specs = [s for s in q.REGISTRY.values() if s.stage == "publish"]
    assert len(specs) == 11 and {s.severity for s in specs} == {q.BLOCK}
    run = q.run_stage("publish", {})
    assert all(r.skipped for r in run.results) and not run.blocked


def test_prefix_runs_only_the_requested_phase():
    pre = q.run_stage("publish", {}, prefix="publish.pre.")
    post = q.run_stage("publish", {}, prefix="publish.post.")
    assert {r.check_id.split(".")[1] for r in pre.results} == {"pre"}
    assert {r.check_id.split(".")[1] for r in post.results} == {"post"}


def test_duplicate_key_blocks_the_payload():
    run = q.run_stage(
        "publish", {"records": [_rec(1), _rec(1), _rec(2)]}, prefix="publish.pre."
    )
    assert run.blocked
    assert not _pre({"records": [_rec(1), _rec(1)]})["publish.pre.keys"].passed
    assert _pre({"records": [_rec(1), _rec(2)]})["publish.pre.keys"].passed
    with pytest.raises(pub.PublishQualityError, match="nothing committed"):
        pub.raise_if_blocked(run, "pre-write")


def test_null_required_field_blocks():
    res = _pre({"records": [_rec(1, predicted_spread=None), _rec(2)]})[
        "publish.pre.required_fields"
    ]
    assert not res.passed and res.observed == {"predicted_spread": 1}


def test_value_ranges_flag_impossible_numbers_but_allow_real_ones():
    ok = _rec(
        1, home_team_spread_line=-51.5, total_line=72.5
    )  # the real extremes seen in Preview
    assert pub.out_of_range([ok]) == []
    bad = _rec(
        2,
        predicted_spread=150.0,
        total_line=500.0,
        predicted_spread_std_dev=0.0,
        edge_total=-1.0,
        spread_lean="draw",
    )
    fields = {p["field"] for p in pub.out_of_range([bad])}
    assert fields == {
        "predicted_spread",
        "total_line",
        "predicted_spread_std_dev",
        "edge_total",
        "spread_lean",
    }


def test_schedule_coverage_blocks_missing_games_and_allows_an_explicit_partial_slate():
    records = [_rec(1), _rec(2)]
    assert _pre({"records": records, "schedule_game_ids": {1, 2}})[
        "publish.pre.schedule_coverage"
    ].passed
    missing = _pre({"records": records, "schedule_game_ids": {1, 2, 3}})[
        "publish.pre.schedule_coverage"
    ]
    assert not missing.passed and missing.observed["missing"] == 1
    allowed = _pre(
        {
            "records": records,
            "schedule_game_ids": {1, 2, 3},
            "allow_partial_slate": True,
        }
    )["publish.pre.schedule_coverage"]
    assert (
        allowed.passed
        and "allowed by operator" in allowed.detail
        and allowed.observed["partial_slate_allowed"]
    )
    extra = _pre(
        {
            "records": records + [_rec(9)],
            "schedule_game_ids": {1, 2},
            "allow_partial_slate": True,
        }
    )["publish.pre.schedule_coverage"]
    assert not extra.passed  # an override never admits a game outside the schedule


def _quotes():
    return {
        "q1": {"spread": -3.5, "total": 50.5},
        "q2": {"spread": -2.5, "total": 49.5},
        "q3": {"spread": -4.0, "total": 51.0},
    }


def _selected(side, quote_id, target="spread"):
    q_ = _quotes()[quote_id]
    key = (
        ("spread_lean", "spread_market_quote_id", "home_team_spread_line", q_["spread"])
        if target == "spread"
        else ("total_lean", "total_market_quote_id", "total_line", q_["total"])
    )
    return _rec(
        1,
        **{
            key[0]: side,
            key[1]: quote_id,
            key[2]: key[3],
            "source_quote_ids": json.dumps(["q1", "q2", "q3"]),
        },
    )


def test_best_quote_rule_for_each_side():
    quotes = _quotes()
    # Spread points are home-signed: Home wants the highest (-2.5, q2), Away the lowest (-4.0, q3).
    assert pub.best_quote_violations([_selected("home", "q2")], quotes) == []
    assert pub.best_quote_violations([_selected("away", "q3")], quotes) == []
    wrong_away = pub.best_quote_violations(
        [_selected("away", "q2")], quotes
    )  # the served October defect
    assert (
        wrong_away
        and wrong_away[0]["best"] == -4.0
        and wrong_away[0]["selected"] == -2.5
    )
    assert pub.best_quote_violations([_selected("home", "q3")], quotes)
    # Totals: Over wants the lowest (49.5, q2), Under the highest (51.0, q3).
    assert pub.best_quote_violations([_selected("over", "q2", "total")], quotes) == []
    assert pub.best_quote_violations([_selected("under", "q3", "total")], quotes) == []
    assert pub.best_quote_violations([_selected("over", "q3", "total")], quotes)
    assert pub.best_quote_violations([_selected("under", "q1", "total")], quotes)


def test_best_quote_ignores_null_leans_and_flags_an_unlinked_quote():
    quotes = _quotes()
    assert pub.best_quote_violations([_rec(1)], quotes) == []
    unlinked = _selected("away", "q3")
    unlinked["source_quote_ids"] = json.dumps(["q1", "q2"])
    res = pub.best_quote_violations([unlinked], quotes)
    assert res and "not among the linked" in res[0]["why"]
    assert not _pre({"records": [_selected("away", "q2")], "quote_by_id": quotes})[
        "publish.pre.best_quote"
    ].passed


def test_venue_city_is_checked_for_published_runs_only():
    records = [_rec(1), _rec(2)]
    rows = [{"game_id": 1, "city": "Fargo"}, {"game_id": 2, "city": " "}]
    res = _pre({"records": records, "state": "published", "venue_rows": rows})[
        "publish.pre.venue_city"
    ]
    assert not res.passed and res.observed["missing_city"] == 1
    assert _pre({"records": records, "state": "preview", "venue_rows": rows})[
        "publish.pre.venue_city"
    ].skipped


def test_readback_compares_database_state_with_the_payload():
    quotes = _quotes()
    records = [_selected("away", "q3"), _rec(2)]
    exp = pub.expected_selections(records, quotes)
    assert exp == {(1, "spread"): {"quote_id": "q3", "side": "away", "point": -4.0}}
    good = {
        "prediction_game_ids": {1, 2},
        "selections": {
            (1, "spread"): {"quote_id": "q3", "side": "away", "point": -4.0}
        },
    }
    ctx = {"records": records, "quote_by_id": quotes, "readback": good}
    assert all(r.passed for r in _post(ctx).values() if not r.skipped)
    short = {**good, "prediction_game_ids": {1}}
    assert not _post({**ctx, "readback": short})[
        "publish.post.predictions_readback"
    ].passed
    drift = {
        **good,
        "selections": {
            (1, "spread"): {"quote_id": "q2", "side": "away", "point": -2.5}
        },
    }
    res = _post({**ctx, "readback": drift})["publish.post.selections_readback"]
    assert not res.passed and res.observed["differing"] == 1
    gone = {**good, "selections": {}}
    assert (
        _post({**ctx, "readback": gone})["publish.post.selections_readback"].observed[
            "missing"
        ]
        == 1
    )


def test_fetch_readback_reads_predictions_and_selections():
    class Cur:
        def execute(self, query, params=()):
            self.rows = (
                [(1,), (2,)]
                if "FROM predictions" in query
                else [(1, "spread", "q3", "away", -4.0)]
            )

        def fetchall(self):
            return self.rows

    rb = pub.fetch_readback(Cur(), "run")
    assert rb["prediction_game_ids"] == {1, 2}
    assert rb["selections"] == {
        (1, "spread"): {"quote_id": "q3", "side": "away", "point": -4.0}
    }


def test_finalize_writes_a_receipt_and_is_deterministic(tmp_path):
    run = q.run_stage("publish", {"records": [_rec(1)]}, prefix="publish.pre.")
    r1 = pub.finalize(run, identity={"run_id": "r"}, output_root=tmp_path)
    r2 = pub.finalize(run, identity={"run_id": "r"}, output_root=tmp_path)
    assert (
        r1["receipt_id"] == r2["receipt_id"]
        and (tmp_path / r1["_path"].split(str(tmp_path) + "/")[-1]).exists()
    )


def test_venue_payload_requires_one_row_with_a_city_per_game():
    rows = [
        {"game_id": 1, "city": "Fargo"},
        {"game_id": 1, "city": "Fargo"},
        {"game_id": 2, "city": ""},
    ]
    gaps = pub.venue_payload_gaps(rows, [1, 2, 3])
    assert gaps == {"missing_row": [3], "no_city": [2], "duplicate": [1]}
    ctx = {"venue_payload": rows, "venue_game_ids": [1, 2, 3]}
    assert not _pre(ctx)["publish.pre.venue_payload"].passed
    good = {"venue_payload": [{"game_id": 1, "city": "Fargo"}], "venue_game_ids": [1]}
    assert _pre(good)["publish.pre.venue_payload"].passed


def test_venues_readback_detects_missing_extra_and_lost_cities():
    payload = [{"game_id": 1, "city": "Fargo"}, {"game_id": 2, "city": "Dublin"}]
    ok = _post(
        {"venue_payload": payload, "venue_readback": [(1, "Fargo"), (2, "Dublin")]}
    )
    assert ok["publish.post.venues_readback"].passed
    bad = _post({"venue_payload": payload, "venue_readback": [(1, None), (3, "X")]})[
        "publish.post.venues_readback"
    ]
    assert (
        not bad.passed
        and bad.observed["missing"] == 1
        and bad.observed["extra"] == 1
        and bad.observed["city_lost"] == 1
    )


def test_recompute_grade_matches_the_frozen_side_and_point():
    # Home wins 24-21. Frozen Away +3.5 line (home-signed -3.5): margin 3 + -3.5 < 0, Away covers.
    assert pub.recompute_grade("spread", "away", -3.5, 24, 21) == "win"
    assert pub.recompute_grade("spread", "home", -3.5, 24, 21) == "loss"
    assert pub.recompute_grade("spread", "home", -3.0, 24, 21) == "push"
    assert pub.recompute_grade("total", "under", 50.5, 24, 21) == "win"
    assert pub.recompute_grade("total", "over", 45.0, 24, 21) == "push"


def test_grade_check_flags_a_stored_result_that_disagrees():
    good = {
        "game_id": 1,
        "target": "spread",
        "side": "away",
        "point": -3.5,
        "result": "win",
        "home_points": 24,
        "away_points": 21,
    }
    assert _post({"grade_readback": [good]})["publish.post.grades_recomputed"].passed
    bad = {**good, "result": "loss"}
    res = _post({"grade_readback": [good, bad]})["publish.post.grades_recomputed"]
    assert not res.passed and res.observed == {"graded": 2, "mismatches": 1}
