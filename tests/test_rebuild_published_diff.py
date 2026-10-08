"""Published-versus-rebuilt diff: buckets, population differences and tolerance."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.rebuild import published_diff as pd_


def _frame(**overrides):
    base = pd.DataFrame(
        {
            "week": [1, 1, 1, 1],
            "team": ["A", "A", "B", "B"],
            "metric": ["ppp", "epa_per_play", "ppp", "plays_per_possession"],
            "value": [2.0, 0.10, 3.0, 5.5],
            "rank": [2, 1, 1, 2],
        }
    )
    return base.assign(**overrides)


KEYS = ["week", "team", "metric"]
COLUMNS = ["value", "rank"]


def _diff(built, published, **kw):
    return pd_.diff_frames(
        built,
        published,
        keys=KEYS,
        columns=COLUMNS,
        metric_of=lambda row: row["metric"],
        **kw,
    )


def test_identical_frames_have_no_differences():
    report = _diff(_frame(), _frame())
    assert report["rows_with_a_difference"] == 0 and not report["unexplained"]
    assert report["cells_compared"] == 8


def test_missing_ppa_and_punt_differences_are_explained():
    built = _frame(value=[2.0, 0.12, 3.0, 5.4])
    report = _diff(built, _frame())
    assert set(report["differences_by_bucket"]) == {"missing_ppa", "punt"}
    assert (
        not report["unexplained"] and report["samples"]["punt"][0]["published"] == 5.5
    )


def test_a_scoring_difference_is_an_unexplained_finding():
    built = _frame(value=[2.5, 0.10, 3.0, 5.5])
    report = _diff(built, _frame())
    assert report["unexplained"] and "scoring" in report["unexplained_buckets"]


def test_unknown_metric_and_rank_follow_through_in_a_scoring_cohort_are_findings():
    built = _frame(metric=["ppp", "epa_per_play", "ppp", "mystery"])
    published = _frame(
        metric=["ppp", "epa_per_play", "ppp", "mystery"], rank=[2, 1, 1, 3]
    )
    report = _diff(built, published)
    assert report["unexplained"] and "other:mystery" in report["unexplained_buckets"]


def test_rows_on_one_side_only_are_attributed_by_metric():
    # the dropped row is (B, plays_per_possession): a punt-bucket row, so it is explained
    report = _diff(_frame().iloc[:3], _frame())
    assert report["population"]["only_published"] == 1
    assert report["population"]["by_bucket"]["only_published"] == {"punt": 1}
    assert not report["unexplained"]
    # a dropped scoring row is an unexplained population difference
    dropped = _diff(_frame().iloc[[1, 2, 3]], _frame())
    assert dropped["unexplained"] and dropped["unexplained_population"][
        "only_published"
    ] == {"scoring": 1}


def test_tolerance_ignores_float_noise_but_not_real_changes():
    assert not _diff(_frame(value=[2.0 + 1e-12, 0.10, 3.0, 5.5]), _frame())[
        "unexplained"
    ]
    assert _diff(_frame(value=[2.001, 0.10, 3.0, 5.5]), _frame())["unexplained"]


def test_json_columns_compare_as_json_not_text():
    left = pd.DataFrame({"k": [1], "d": ['{"a": 1, "b": 2}']})
    right = pd.DataFrame({"k": [1], "d": ['{"b":2,"a":1}']})
    report = pd_.diff_frames(
        left, right, keys=["k"], columns=["d"], metric_of=lambda r: None, jsonb=["d"]
    )
    assert report["rows_with_a_difference"] == 0


def test_summary_counts_cells_by_bucket():
    tables = {"t": _diff(_frame(value=[2.0, 0.12, 3.0, 5.4]), _frame())}
    summary = pd_.summarize(tables)
    assert summary["differing_cells_by_bucket"] == {"missing_ppa": 1, "punt": 1}
    assert summary["all_differences_explained"]


def test_boolean_columns_compare_without_arithmetic_errors():
    left = pd.DataFrame({"k": [1, 2], "flag": [True, False]})
    right = pd.DataFrame({"k": [1, 2], "flag": [True, True]})
    report = pd_.diff_frames(
        left, right, keys=["k"], columns=["flag"], metric_of=lambda r: None
    )
    assert report["rows_with_a_difference"] == 1 and report["cells_compared"] == 2


def test_timezone_aware_timestamps_compare_as_instants_not_numbers():
    from datetime import UTC, datetime

    built = pd.DataFrame({"k": [1, 2], "t": [pd.Timestamp("2026-09-03T04:00:00Z")] * 2})
    published = pd.DataFrame(
        {
            "k": [1, 2],
            "t": [
                datetime(2026, 9, 3, 4, tzinfo=UTC),
                datetime(2026, 9, 3, 5, tzinfo=UTC),
            ],
        }
    )
    report = pd_.diff_frames(
        built, published, keys=["k"], columns=["t"], metric_of=lambda r: None
    )
    assert report["rows_with_a_difference"] == 1  # only the one-hour difference


def test_expected_buckets_can_be_widened_for_a_proven_cause():
    left = pd.DataFrame({"k": [1], "v": [1.0]})
    right = pd.DataFrame({"k": [1], "v": [2.0]})
    metric = lambda row: "history_correction"  # noqa: E731
    assert pd_.diff_frames(left, right, keys=["k"], columns=["v"], metric_of=metric)[
        "unexplained"
    ]
    widened = pd_.diff_frames(
        left,
        right,
        keys=["k"],
        columns=["v"],
        metric_of=metric,
        expected={"missing_ppa", "punt", "history_correction"},
    )
    assert not widened["unexplained"]


def _games(game_ids, **overrides):
    return pd.DataFrame(
        {
            "game_id": game_ids,
            "metric": ["ppp"] * len(game_ids),
            "value": [1.0] * len(game_ids),
        }
    ).assign(**overrides)


def _diff_games(built, published, **kw):
    return pd_.diff_frames(
        built,
        published,
        keys=["game_id", "metric"],
        columns=["value"],
        metric_of=lambda row: row["metric"],
        **kw,
    )


def _in_new_games(frame):
    return frame["game_id"].isin([3, 4])


def test_rows_of_added_scope_are_counted_not_compared():
    report = _diff_games(
        _games([1, 2, 3, 4]), _games([1, 2]), added_scope=_in_new_games
    )
    assert not report["unexplained"]
    assert report["added_scope"]["rows"] == 2
    assert report["population"]["only_built"] == 0
    assert report["rows_built"] == 4 and report["rows_compared"] == 2


def test_without_the_scope_the_same_extra_rows_are_findings():
    report = _diff_games(_games([1, 2, 3, 4]), _games([1, 2]))
    assert report["unexplained"] and report["population"]["only_built"] == 2


def test_a_published_row_inside_the_added_scope_is_a_finding():
    report = _diff_games(
        _games([1, 2, 3]), _games([1, 2, 3]), added_scope=_in_new_games
    )
    assert report["unexplained"]
    assert report["added_scope"]["published_rows_in_scope"] == 1


def test_a_difference_outside_the_added_scope_is_still_found():
    built = _games([1, 2, 3, 4], value=[1.0, 9.0, 1.0, 1.0])
    report = _diff_games(built, _games([1, 2]), added_scope=_in_new_games)
    assert report["unexplained"] and "scoring" in report["unexplained_buckets"]


def test_a_bucket_override_names_only_the_cells_it_matches():
    built = _games([1, 2], value=[5.0, 7.0])
    published = _games([1, 2])
    report = _diff_games(
        built,
        published,
        expected={"proven"},
        bucket_override=lambda row, column: "proven" if row["game_id"] == 1 else None,
    )
    assert report["differences_by_bucket"]["proven"] == {"value": 1}
    assert "scoring" in report["unexplained_buckets"]


def test_summary_reports_added_scope_rows_per_table():
    report = _diff_games(_games([1, 3]), _games([1]), added_scope=_in_new_games)
    summary = pd_.summarize({"t": report})
    assert summary["added_scope_rows"] == {"t": 1}
    assert summary["all_differences_explained"]
