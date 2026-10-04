"""Ingestion checks: fixture-driven, no cloud or database access."""

from __future__ import annotations

import pandas as pd

from cks_picks_cfb.quality import checks as q
from cks_picks_cfb.quality import ingest as ing


def _ingest(ctx):
    return {r.check_id: r for r in q.run_stage("ingest", ctx).results}


def test_all_ingest_checks_register_at_warn():
    specs = [s for s in q.REGISTRY.values() if s.stage == "ingest"]
    assert len(specs) >= 9 and {s.severity for s in specs} == {q.WARN}
    assert q.registry_problems() == []


def test_empty_context_skips_everything_and_blocks_nothing():
    run = q.run_stage("ingest", {})
    assert run.results and all(r.skipped for r in run.results)
    assert not run.blocked and run.failures == ()


def _versions(rows):
    return pd.DataFrame(rows, columns=["dataset", "version_id", "as_of"])


def test_multi_version_dataset_without_pin_fails_and_the_pin_fixes_it():
    # Mirrors venues: several versions share the newest as_of (one per capture year).
    versions = _versions(
        [
            ("venues", "v2024", "2026-08-31"),
            ("venues", "v2025", "2026-08-31"),
            ("venues", "v2026", "2026-08-09"),
            ("games", "g1", "2026-09-01"),
        ]
    )
    problems = ing.unpinned_multi_version_datasets(versions, {})
    assert problems == {"venues": ["v2024", "v2025"]}
    assert ing.unpinned_multi_version_datasets(versions, {"venues": "v2026"}) == {}
    # A pin that names no real version is still a problem.
    assert "venues" in ing.unpinned_multi_version_datasets(versions, {"venues": "nope"})
    res = _ingest({"catalog_versions": versions})["ingest.versions_pinned"]
    assert not res.passed and not res.skipped


def test_season_partitioned_versions_are_distinguishable_and_need_no_pin():
    rows = [
        ("games", "g2025", "2026-09-01", [2025]),
        ("games", "g2026", "2026-09-01", [2026]),
        ("plays", "p1", "2026-09-01", [2026]),
        ("plays", "p2", "2026-09-01", [2026]),  # overlapping seasons: ambiguous
        ("venues", "v1", "2026-09-01", []),
        ("venues", "v2", "2026-09-01", []),
    ]
    versions = pd.DataFrame(rows, columns=["dataset", "version_id", "as_of", "seasons"])
    problems = ing.unpinned_multi_version_datasets(versions, {})
    assert set(problems) == {"plays", "venues"}


def test_capture_completeness_reports_missing_requests():
    res = _ingest(
        {"expected_requests": {"a", "b", "c"}, "completed_requests": {"a", "c", "z"}}
    )
    r = res["ingest.capture_completeness"]
    assert not r.passed and r.observed == {"missing": 1, "unexpected": 1}


def _games(ids, completed=True, scores=True):
    return pd.DataFrame(
        {
            "season": 2026,
            "week": [1] * len(ids),
            "game_id": ids,
            "completed": [completed] * len(ids),
            "home_points": [10.0 if scores else None] * len(ids),
            "away_points": [7.0] * len(ids),
        }
    )


def test_games_vs_schedule_flags_missing_extra_and_duplicates():
    schedule = pd.DataFrame({"season": 2026, "week": [1, 1, 2], "game_id": [1, 2, 3]})
    gap = ing.games_vs_schedule(_games([1, 1, 9]), schedule)
    assert gap["missing"] == [2, 3] and gap["extra"] == [9] and gap["duplicates"] == 1
    assert gap["weeks_with_missing"] == [1, 2]
    ok = _ingest({"games": _games([1, 2, 3]), "schedule": schedule})
    assert ok["ingest.games_vs_schedule"].passed


def test_completed_games_must_have_both_scores():
    res = _ingest({"games": _games([1, 2], scores=False)})[
        "ingest.completed_games_have_scores"
    ]
    assert not res.passed and res.observed["null_scores"] == 2
    unfinished = _games([1], completed=False, scores=False)
    assert _ingest({"games": unfinished})["ingest.completed_games_have_scores"].passed


def test_plays_floor_and_drives_coverage():
    games = _games([1, 2, 3])
    plays = pd.DataFrame({"game_id": [1] * 80 + [2] * 10})  # game 3 has none
    drives = pd.DataFrame({"game_id": [1, 2]})
    res = ing.play_coverage(games, plays, drives, min_plays=60)
    assert (
        res["no_plays"] == [3] and res["below_floor"] == [2] and res["no_drives"] == [3]
    )
    out = _ingest({"games": games, "plays": plays, "drives": drives})
    assert not out["ingest.plays_and_drives_per_completed_game"].passed


def test_ppa_zero_is_not_missing_and_absent_column_fails():
    plays = pd.DataFrame({"game_id": [1, 1, 1], "ppa": [0.0, None, 1.2]})
    r = _ingest({"plays": plays})["ingest.ppa_coverage"]
    assert r.passed and r.observed == {"plays": 3, "ppa_missing": 1}
    assert not _ingest({"plays": plays.drop(columns="ppa")})[
        "ingest.ppa_coverage"
    ].passed


def test_odds_unmatched_and_price_presence():
    out = _ingest({"odds_capture": {"unmatched_events": 2}})
    assert not out["ingest.odds_unmatched_events"].passed
    no_price = pd.DataFrame(
        {"home_spread_price": [None, None], "over_price": [None, None]}
    )
    assert ing.price_presence(no_price)["rate"] == 0.0
    assert not _ingest({"market_quotes": no_price})[
        "ingest.quote_price_presence"
    ].passed
    some = pd.DataFrame({"home_spread_price": [-110, None], "over_price": [None, None]})
    assert ing.price_presence(some)["with_any_price"] == 1
    assert _ingest({"market_quotes": some})["ingest.quote_price_presence"].passed


def test_schema_contract_records_pass_and_fail_per_dataset():
    from cks_picks_cfb.data.schema_contracts import DatasetSchema

    schema = DatasetSchema(
        dataset="demo",
        schema_version="demo_v1",
        required=("game_id", "value"),
        nonnullable=("game_id",),
        keys=("game_id",),
    )
    good = pd.DataFrame({"game_id": [1, 2], "value": [1.0, 2.0]})
    dup = pd.DataFrame({"game_id": [1, 1], "value": [1.0, 2.0]})
    results = q.run_stage(
        "ingest", {"schemas": {"good": (good, schema), "dup": (dup, schema)}}
    ).results
    by_scope = {
        r.scope["dataset"]: r for r in results if r.check_id == "ingest.schema_contract"
    }
    assert by_scope["good"].passed and not by_scope["dup"].passed
    assert "duplicate keys" in by_scope["dup"].detail


def test_extra_silver_games_are_reported_but_do_not_fail():
    schedule = pd.DataFrame({"season": 2026, "week": [1, 1], "game_id": [1, 2]})
    out = _ingest({"games": _games([1, 2, 77, 78]), "schedule": schedule})
    r = out["ingest.games_vs_schedule"]
    assert r.passed and r.observed["extra"] == 2 and r.observed["missing"] == 0


def test_price_check_skips_when_the_source_has_no_price_columns():
    silver_like = pd.DataFrame({"quote_id": ["a"], "spread": [-3.5]})
    r = _ingest({"market_quotes": silver_like})["ingest.quote_price_presence"]
    assert r.skipped and not r.passed
