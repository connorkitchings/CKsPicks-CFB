"""Serving-core projections are built deterministically from prepared frames."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from cks_picks_cfb.season import projection_serving as ps
from cks_picks_cfb.season.grading import grade_predictions
from cks_picks_cfb.season.manifest import utc
from cks_picks_cfb.season.projection_common import (
    SERVER_COLUMNS,
    canonical_bytes,
    quantize4,
    weekly_run_id,
)
from contracts.validation import extract_sql_table_columns

ROOT = Path(__file__).resolve().parents[1]
SEASON_RUN = "season-2026-abc"
RATINGS_ID = "ab" * 32
AS_OF = "2026-09-19T14:00:00Z"
GAMES = [  # game_id, week, kickoff, home, away
    (1, 0, "2026-09-05T16:00:00Z", "A", "B"),  # retained pre-kickoff quotes
    (2, 0, "2026-09-05T20:00:00Z", "C", "D"),  # CFBD fallback, spread push
    (3, 1, "2026-09-12T16:00:00Z", "A", "C"),  # no market: ungraded
    (4, 2, "2026-09-19T16:00:00Z", "B", "D"),  # live week, not started
    (5, 2, "2026-09-19T12:00:00Z", "A", "D"),  # live week, already started
    (6, 3, "2026-09-26T16:00:00Z", "B", "C"),  # later week, no prediction
]
MEANS = {1: (6.5, 50.0), 2: (1.0, 44.0), 3: (-2.0, 55.0), 4: (3.5, 47.5)}
STAGES = {1: 0, 2: 0, 3: 1, 4: 1}


def _quote(quote_id, game_id, provider, captured, spread, total, **prices):
    return {
        "quote_id": quote_id,
        "game_id": game_id,
        "provider": provider,
        "captured_at": captured,
        "spread": spread,
        "total": total,
        **prices,
    }


@pytest.fixture
def case():
    schedule = pd.DataFrame(
        [
            {
                "season": 2026,
                "week": week,
                "game_id": game_id,
                "kickoff_utc": utc(kickoff),
                "home_team": home,
                "away_team": away,
                "home_team_provider": f"{home} State",
                "away_team_provider": f"{away} State",
            }
            for game_id, week, kickoff, home, away in GAMES
        ]
    )
    finals = pd.DataFrame(
        [
            {"season": 2026, "game_id": 1, "home_points": 31, "away_points": 24},
            {"season": 2026, "game_id": 2, "home_points": 20, "away_points": 17},
            {"season": 2026, "game_id": 3, "home_points": 10, "away_points": 31},
        ]
    )
    quotes = pd.DataFrame(
        [
            _quote(
                "q1-book1",
                1,
                "book1",
                "2026-09-04T12:00:00Z",
                -3.0,
                48.5,
                home_spread_price=-105.0,
                over_price=-110.0,
            ),
            _quote("q1-book2", 1, "book2", "2026-09-04T13:00:00Z", -4.0, 49.5),
            _quote("q1-late", 1, "book3", "2026-09-05T17:00:00Z", -1.0, 40.0),
            _quote("q4-book1", 4, "book1", "2026-09-18T12:00:00Z", -2.5, 51.0),
        ]
    )
    fallback = pd.DataFrame(
        [_quote("cfbd-2", 2, "CFBD", "2026-09-13T12:00:00Z", -3.0, 50.0)]
    )
    predictions = pd.DataFrame(
        [
            {
                "run_id": SEASON_RUN,
                "season": 2026,
                "week": week,
                "game_id": game_id,
                "target": target,
                "mean": MEANS[game_id][index],
                "variance": 4.0 if target == "margin" else 9.0,
                "completed_game_stage": STAGES[game_id],
            }
            for game_id, week, *_ in GAMES
            if game_id in MEANS
            for index, target in enumerate(("margin", "total"))
        ]
    )
    grades = grade_predictions(
        predictions, schedule, finals, quotes, fallback, live_week=2, as_of=AS_OF
    )
    inputs = SimpleNamespace(
        schedule=schedule, finals=finals, quotes=quotes, historical_lines=fallback
    )
    frames = {
        "schedule": schedule[schedule.week.le(2)],
        "finals": finals,
        "predictions": predictions,
        "grades": grades,
    }
    revision = {
        "captured_at": "2026-09-19T13:00:00Z",
        "pre_week_cutoffs": {"0": "2026-09-05T10:00:00Z", "1": "2026-09-12T10:00:00Z"},
        "inputs": {
            "finals": {"uri": "r2/finals.parquet", "sha256": "f" * 64},
            "schedule": {"uri": "r2/schedule.parquet", "sha256": "5" * 64},
        },
    }
    identity = {
        "through_week": 1,
        "active_week": 2,
        "as_of": AS_OF,
        "next_week_mode": "live",
        "code_sha": "c" * 40,
        "config_sha": "d" * 64,
        "predictions_sha256": "e" * 64,
    }
    return frames, inputs, revision, identity


def build(case):
    frames, inputs, revision, identity = case
    return ps.build_serving_core(
        frames=frames,
        inputs=inputs,
        revision=revision,
        identity=identity,
        ratings_id=RATINGS_ID,
        measurement_id="cd" * 32,
    )


def by(rows, *keys):
    return {
        tuple(row[k] for k in keys) if len(keys) > 1 else row[keys[0]]: row
        for row in rows
    }


def test_every_table_has_exactly_the_migration_columns(case):
    payload = build(case)
    release = extract_sql_table_columns(
        ROOT / "contracts/migrations/0025_season_releases.sql"
    )
    registry = extract_sql_table_columns(ROOT / "contracts/schema.sql")
    assert set(payload) == set(ps.SERVING_KEYS)
    for name, rows in payload.items():
        expected = (
            registry["prediction_runs"]
            if name == "prediction_runs"
            else release["season_release_" + name] - SERVER_COLUMNS
        )
        assert set(ps.COLUMNS[name]) == expected, name
        assert all(set(row) == expected for row in rows), name
        assert rows, name


def test_output_is_deterministic_finite_and_key_sorted(case):
    payload = build(case)
    assert canonical_bytes(payload) == canonical_bytes(build(case))
    for name, rows in payload.items():
        keys = [tuple(row[k] for k in ps.KEYS[name]) for row in rows]
        assert keys == sorted(keys) and len(set(keys)) == len(keys), name
        for row in rows:
            for value in row.values():
                assert not (isinstance(value, float) and not math.isfinite(value))
    stamp = payload["games"][0]["inserted_at"]
    assert stamp == "2026-09-19T13:00:00.000000+00:00"


def test_games_cover_the_full_schedule_with_null_unpredicted_columns(case):
    payload = build(case)
    games = by(payload["games"], "game_id")
    assert set(games) == {game[0] for game in GAMES}
    assert games[1]["home_team"] == "A State"
    assert games[1]["start_date"] == "2026-09-05T16:00:00.000000+00:00"
    for game_id in (5, 6):
        row = games[game_id]
        assert row["high_confidence"] is False
        assert all(
            row[name] is None
            for name in ps.COLUMNS["games"]
            if name.startswith(("predicted", "edge", "source", "system", "model"))
            or name.endswith(("_line", "_lean"))
        )
    assert games[3]["predicted_spread"] == -2.0
    assert games[3]["home_team_spread_line"] is None
    assert games[1]["model_id"] == ps.MODEL_ID
    assert games[1]["predicted_spread_std_dev"] == 2.0
    assert games[1]["predicted_total_std_dev"] == 3.0
    assert {row["game_id"] for row in payload["predictions"]} == set(MEANS)


def test_predictions_use_per_week_run_ids_counts_and_regimes(case):
    payload = build(case)
    rows = by(payload["predictions"], "game_id")
    assert {g: r["run_id"] for g, r in rows.items()} == {
        g: weekly_run_id(SEASON_RUN, week) for g, week, *_ in GAMES if g in MEANS
    }
    assert (rows[3]["home_completed_games"], rows[3]["away_completed_games"]) == (1, 1)
    assert rows[3]["regime"] == "game_2" and rows[1]["regime"] == "game_1"
    assert rows[1]["spread_model_version"] == f"v5:{SEASON_RUN}:{RATINGS_ID[:12]}"
    assert rows[1]["created_at"] == "2026-09-05T10:00:00.000000+00:00"
    assert rows[4]["created_at"] == "2026-09-19T14:00:00.000000+00:00"
    assert not any(
        r["high_confidence"] or r["high_confidence_eligible"] for r in rows.values()
    )
    assert rows[3]["market_snapshot_id"] is None
    assert rows[2]["market_snapshot_id"] is not None


def test_stage_mismatch_is_rejected(case):
    case[0]["predictions"].loc[
        case[0]["predictions"].game_id.eq(3), "completed_game_stage"
    ] = 0
    with pytest.raises(ValueError, match="stage"):
        build(case)


def test_grades_are_lowercase_quantized_and_paired_with_selections(case):
    payload = build(case)
    grades = by(payload["prediction_grades"], "game_id", "target")
    selections = by(payload["prediction_market_selections"], "game_id", "target")
    assert {r["result"] for r in grades.values()} <= {"win", "loss", "push"}
    assert grades[(2, "spread")]["result"] == "push"
    assert grades[(2, "spread")]["profit_units"] == 0.0
    assert grades[(2, "spread")]["grading_version"].endswith(":cfbd_retrospective")
    assert grades[(1, "spread")]["grading_version"].endswith(":retained_prekickoff")
    for row in grades.values():
        assert row["profit_units"] == quantize4(row["profit_units"])
        assert row["graded_at"] == "2026-09-19T13:00:00.000000+00:00"
    win = grades[(1, "total")]
    assert win["result"] == "win" and win["profit_units"] == 0.9091
    scored = {key for key, row in selections.items() if key[0] in (1, 2, 3)}
    assert set(grades) == scored  # every graded-week selection is graded
    assert (4, "spread") in selections and (4, "spread") not in grades
    assert 3 not in {key[0] for key in selections}
    for key, grade in grades.items():
        selection = selections[key]
        assert grade["run_id"] == selection["run_id"]
        assert grade["market_quote_id"] == selection["quote_id"]
        assert grade["market_snapshot_id"] == selection["snapshot_id"]
        assert grade["side"] == selection["side"]


def test_selection_edges_and_lines_follow_market_sign_convention(case):
    payload = build(case)
    games = by(payload["games"], "game_id")
    for row in payload["prediction_market_selections"]:
        spread, total = MEANS[row["game_id"]]
        expected = (
            abs(spread + row["point"])
            if row["target"] == "spread"
            else abs(total - row["point"])
        )
        assert row["edge"] == pytest.approx(expected)
        game = games[row["game_id"]]
        line = "home_team_spread_line" if row["target"] == "spread" else "total_line"
        lean = "spread_lean" if row["target"] == "spread" else "total_lean"
        assert (game[line], game[lean]) == (row["point"], row["side"])
        assert row["policy_version"] == "model_side_best_quote_v2"
    spread = by(payload["prediction_market_selections"], "game_id", "target")[
        (1, "spread")
    ]
    # Home lean (6.5 - 3.5 > 0) shops the highest home-signed point.
    assert (spread["side"], spread["point"], spread["quote_id"]) == (
        "home",
        -3.0,
        "q1-book1",
    )
    assert spread["price"] == -105.0
    assert games[1]["edge_spread"] == 3.5


def test_market_lineage_links_only_projected_quotes(case):
    payload = build(case)
    quotes = by(payload["market_quotes"], "quote_id")
    snapshots = by(payload["market_snapshots"], "snapshot_id")
    links = payload["market_snapshot_quotes"]
    assert set(quotes) == {"q1-book1", "q1-book2", "q4-book1", "cfbd-2"}
    assert (quotes["q1-book1"]["spread"], quotes["q1-book1"]["total"]) == (-3.0, 48.5)
    assert quotes["q1-book1"]["home_spread_price"] == -105.0
    assert quotes["cfbd-2"]["captured_at"] == "2026-09-13T12:00:00.000000+00:00"
    for row in payload["prediction_market_selections"]:
        assert quotes[row["quote_id"]]["game_id"] == row["game_id"]
        assert snapshots[row["snapshot_id"]]["game_id"] == row["game_id"]
        assert {
            "snapshot_id": row["snapshot_id"],
            "quote_id": row["quote_id"],
            "target": row["target"],
        } in links
    for link in links:
        snapshot = snapshots[link["snapshot_id"]]
        assert link["quote_id"] in snapshot["source_quote_ids"]
        assert snapshot[link["target"]] is not None
        assert quotes[link["quote_id"]][link["target"]] is not None
    for snapshot in snapshots.values():
        assert snapshot["policy_version"] == "consensus_then_median_v1"
        assert (snapshot["spread"] is None) != (snapshot["total"] is None)
    game1 = [
        s for s in snapshots.values() if s["game_id"] == 1 and s["spread"] is not None
    ]
    assert game1[0]["spread"] == -3.5  # provider median
    assert game1[0]["spread_rule"] == "provider_median"
    assert game1[0]["spread_provider_count"] == 2
    assert game1[0]["total_provider_count"] == 0


def test_game_results_cover_finals_with_lowercase_results(case):
    payload = build(case)
    results = by(payload["game_results"], "game_id")
    assert set(results) == {1, 2, 3}
    assert results[2]["spread_result"] == "push"
    assert results[3]["spread_result"] is None and results[3]["total_result"] is None
    assert results[1]["source_dataset_version_id"] == "finals:" + "f" * 16
    assert results[1]["completion_state"] == "completed"


def test_system_stats_match_an_independent_aggregation(case):
    frames = case[0]
    payload = build(case)
    graded = frames["grades"][
        frames["grades"].result.notna() & frames["grades"].week.le(1)
    ]
    expected = {"season": 2026, "as_of_week": int(graded.week.max())}
    for target in ("spread", "total"):
        rows = graded[graded.target.eq(target)]
        for result, label in (("win", "wins"), ("loss", "losses"), ("push", "pushes")):
            expected[f"{target}_{label}"] = int(rows.result.eq(result).sum())
        expected[f"{target}_profit_units"] = round(
            float(rows.units.map(quantize4).sum()), 4
        )
    (stats,) = payload["system_stats"]
    assert {k: stats[k] for k in expected} == expected
    assert stats["as_of_week"] == 0


def test_run_registry_and_site_selection_per_week(case):
    payload = build(case)
    runs = by(payload["prediction_runs"], "week")
    site = by(payload["site_week_selections"], "week")
    assert set(runs) == set(site) == {0, 1, 2}
    assert len({r["run_id"] for r in runs.values()}) == 3
    for week, run in runs.items():
        assert run["run_id"] == site[week]["run_id"] == weekly_run_id(SEASON_RUN, week)
        assert site[week]["selected_at"] == run["data_as_of"]
        assert run["frozen_at"] is None
        assert run["rating_manifest_sha256"] == RATINGS_ID
        assert run["artifact_uri"] == f"season-run:{SEASON_RUN}/predictions.parquet"
        assert run["model_bundle_sha256"] == ps.BRIDGE_SHA256
    assert [runs[w]["state"] for w in (0, 1, 2)] == ["scored", "scored", "published"]
    assert [runs[w]["evidence_class"] for w in (0, 1, 2)] == [
        "replay",
        "replay",
        "pending",
    ]
    assert runs[2]["scored_at"] is None
    counts = {
        w: (r["expected_games"], r["predicted_games"], r["lined_games"])
        for w, r in runs.items()
    }
    assert counts == {0: (2, 2, 2), 1: (1, 1, 0), 2: (2, 1, 1)}
    assert runs[2]["validation"]["all_predictions_present"] is False


def test_reconstructed_active_week_is_replay(case):
    case[3]["next_week_mode"] = "reconstructed"
    case[2]["pre_week_cutoffs"]["2"] = "2026-09-19T10:00:00Z"
    runs = by(build(case)["prediction_runs"], "week")
    assert runs[2]["evidence_class"] == "replay"
    assert runs[2]["data_as_of"] == "2026-09-19T10:00:00.000000+00:00"


def test_missing_selected_quote_is_rejected(case):
    inputs = case[1]
    inputs.quotes = inputs.quotes[inputs.quotes.quote_id.ne("q4-book1")]
    with pytest.raises(ValueError, match="absent"):
        build(case)
