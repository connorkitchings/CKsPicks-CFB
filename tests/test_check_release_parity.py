"""Parity gate between the active Preview release and a prepared candidate."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from decimal import Decimal

from scripts.pipeline import check_release_parity as parity

OLD_RUN = "season-2026-" + "a" * 24
NEW_RUN = "season-2026-" + "b" * 24
STAMP = "2026-10-20T14:39:00.000000+00:00"
LATER = "2026-10-25T20:52:00.000000+00:00"

# Completed week N=8, upcoming W=9. Games 1..2 are week 7, 3 is week 8, 4..5 week 9.
GAME_WEEKS = {1: 7, 2: 7, 3: 8, 4: 9, 5: 9}


def release(run: str) -> dict[str, list[dict]]:
    games, predictions, grades, snapshots = [], [], [], []
    for game, week in GAME_WEEKS.items():
        lined = week == 9
        games.append(
            {
                "game_id": game,
                "week": week,
                "home_team_spread_line": -3.5 if lined else None,
                "total_line": 50.5 if lined else None,
                "spread_lean": "home" if lined else None,
                "total_lean": None,
                "edge_spread": 1.5 if lined else None,
                "edge_total": None,
                "high_confidence": False,
                "predicted_spread": 4.0 + game,
                "inserted_at": STAMP,
            }
        )
        predictions.append(
            {
                "run_id": f"{run}:w{week}",
                "game_id": game,
                "predicted_spread": 4.0 + game,
                "predicted_total": 55.0,
                "predicted_spread_std_dev": 17.8,
                "predicted_total_std_dev": 17.4,
                "home_team_spread_line": -3.5 if lined else None,
                "total_line": 50.5 if lined else None,
                "spread_lean": "home" if lined else None,
                "total_lean": None,
                "edge_spread": 1.5 if lined else None,
                "edge_total": None,
                "high_confidence": False,
                "market_snapshot_id": f"snap-{game}" if lined else None,
                "created_at": STAMP,
            }
        )
        if week < 9:
            grades.append(
                {
                    "run_id": f"{run}:w{week}",
                    "game_id": game,
                    "target": "spread",
                    "result": "win",
                    "profit_units": 0.9091,
                    "graded_at": STAMP,
                }
            )
    for week in (1, 8):
        snapshots.append(
            {
                "snapshot_id": f"{run}:pregame:Team:week-{week}",
                "source_run_id": run,
                "source_manifest_sha256": run[-1] * 64,
                "week": week,
                "snapshot_class": "pregame",
                "overall_rating": 1.25 + week,
                "overall_variance": 0.5,
                "created_at": STAMP,
            }
        )
    return {
        "games": games,
        "predictions": predictions,
        "prediction_grades": grades,
        "v5_rating_snapshots": snapshots,
        "market_quotes": [
            {"quote_id": "q-4", "game_id": 4, "spread": -3.5},
            {"quote_id": "q-1", "game_id": 1, "spread": -1.0},
        ],
        "market_snapshots": [
            {
                "snapshot_id": "snap-4",
                "game_id": 4,
                "spread": -3.5,
                "created_at": STAMP,
            },
            {
                "snapshot_id": "snap-5",
                "game_id": 5,
                "spread": -2.0,
                "created_at": STAMP,
            },
        ],
        "market_snapshot_quotes": [
            {"snapshot_id": "snap-4", "quote_id": "q-4", "target": "spread"}
        ],
        "prediction_market_selections": [
            {
                "run_id": f"{run}:w9",
                "game_id": 4,
                "target": "spread",
                "snapshot_id": "snap-4",
                "quote_id": "q-4",
                "edge": 1.5,
            }
        ],
    }


def run(old, new, mode="close-week", completed=8, upcoming=9):
    return parity.compare_releases(
        old, new, mode=mode, completed_week=completed, upcoming_week=upcoming
    )


def row(tables, name, **match):
    return next(r for r in tables[name] if all(r[k] == v for k, v in match.items()))


def test_identical_release_with_new_identity_passes_in_both_modes():
    old, new = release(OLD_RUN), release(NEW_RUN)
    assert run(old, new).passed
    assert run(old, new, mode="market-refresh").passed


def test_changed_completed_week_prediction_fails_close_week():
    old, new = release(OLD_RUN), release(NEW_RUN)
    row(new, "predictions", game_id=1)["predicted_spread"] += 1e-6

    report = run(old, new)

    assert not report.passed
    assert any(
        f.startswith("predictions ") and "/1:" in f and "predicted_spread" in f
        for f in report.failures
    )


def test_drift_under_tolerance_and_decimal_types_are_equal():
    old, new = release(OLD_RUN), release(NEW_RUN)
    row(new, "predictions", game_id=1)["predicted_spread"] += 1e-12
    row(old, "prediction_grades", game_id=1)["profit_units"] = Decimal("0.9091")

    assert run(old, new).passed


def test_changed_grade_and_pregame_snapshot_fail_close_week():
    old, new = release(OLD_RUN), release(NEW_RUN)
    row(new, "prediction_grades", game_id=2)["result"] = "loss"
    row(new, "v5_rating_snapshots", week=1)["overall_rating"] = 9.0

    failures = run(old, new).failures

    assert any(f.startswith("prediction_grades ") and "/2/" in f for f in failures)
    assert any("v5_rating_snapshots" in f and "overall_rating" in f for f in failures)


def test_close_week_ignores_completed_week_row_and_current_snapshots():
    # Week 8 is just completed: its rows may legitimately change in close-week.
    old, new = release(OLD_RUN), release(NEW_RUN)
    row(new, "predictions", game_id=3)["predicted_spread"] += 5
    row(new, "v5_rating_snapshots", week=8)["overall_rating"] = 9.0
    new["prediction_grades"].append(
        {"run_id": f"{NEW_RUN}:w8", "game_id": 3, "target": "total", "result": "win"}
    )

    assert run(old, new).passed


def test_changed_market_column_passes_only_in_market_refresh():
    old, new = release(OLD_RUN), release(NEW_RUN)
    for table in ("games", "predictions"):
        changed = row(new, table, game_id=5)
        changed.update(home_team_spread_line=-7.0, edge_spread=4.0, spread_lean="away")
    new["market_snapshots"][1]["spread"] = -7.0
    new["market_quotes"].append({"quote_id": "q-5", "game_id": 5, "spread": -7.0})
    new["market_snapshot_quotes"].append(
        {"snapshot_id": "snap-5", "quote_id": "q-5", "target": "spread"}
    )

    assert run(old, new, mode="market-refresh").passed


def test_changed_market_column_of_a_completed_week_fails_both_modes():
    old, new = release(OLD_RUN), release(NEW_RUN)
    row(new, "predictions", game_id=1)["total_line"] = 44.0

    assert not run(old, new, mode="close-week").passed
    assert not run(old, new, mode="market-refresh").passed


def test_market_refresh_fails_on_non_market_or_earlier_week_changes():
    old, new = release(OLD_RUN), release(NEW_RUN)
    row(new, "predictions", game_id=5)["predicted_spread"] += 1  # model column
    row(new, "prediction_grades", game_id=3)["result"] = "loss"  # grade
    row(new, "v5_rating_snapshots", week=8)["overall_rating"] = 9.0  # ratings
    new["market_quotes"][1]["spread"] = -2.0  # earlier-week quote

    failures = run(old, new, mode="market-refresh").failures

    assert any(f.startswith("predictions ") and "/5:" in f for f in failures)
    assert any(f.startswith("prediction_grades ") and "/3/" in f for f in failures)
    assert any(f.startswith("v5_rating_snapshots") for f in failures)
    assert any(f.startswith("market_quotes q-1") for f in failures)


def test_market_refresh_fails_when_a_row_disappears_or_appears():
    old, new = release(OLD_RUN), release(NEW_RUN)
    new["prediction_grades"].pop()
    new["games"].append({"game_id": 99, "week": 3, "inserted_at": STAMP})

    failures = run(old, new, mode="market-refresh").failures

    assert any("missing from the candidate" in f for f in failures)
    assert any("new in the candidate" in f for f in failures)


def test_unpredicted_upcoming_game_fails_but_missing_lines_do_not():
    old, new = release(OLD_RUN), release(NEW_RUN)
    for table in ("games", "predictions"):
        for r in new[table]:
            if r["game_id"] == 5:
                r.update(home_team_spread_line=None, total_line=None)
    report = run(old, new)
    assert report.passed
    assert (
        report.upcoming_games,
        report.upcoming_predicted,
        report.upcoming_lined,
    ) == (
        2,
        2,
        1,
    )

    new["predictions"] = [r for r in new["predictions"] if r["game_id"] != 5]
    unpredicted = run(old, new)
    assert not unpredicted.passed
    assert any("1 of 2 games predicted" in f for f in unpredicted.failures)


def test_missing_required_table_fails_closed():
    old, new = release(OLD_RUN), release(NEW_RUN)
    del new["prediction_grades"]

    assert not run(old, new).passed


def test_normalize_value_masks_runs_and_unifies_timestamps():
    moment = datetime(2026, 10, 20, 14, 39, tzinfo=timezone.utc)
    assert parity.normalize_value(moment) == parity.normalize_value(
        "2026-10-20T14:39:00Z"
    )
    assert parity.normalize_value(f"{OLD_RUN}:w3") == parity.normalize_value(
        f"{NEW_RUN}:w3"
    )


def test_main_writes_public_safe_report_and_exit_code(tmp_path, monkeypatch):
    old, new = release(OLD_RUN), release(NEW_RUN)
    (tmp_path / "serving-projections.json").write_text(json.dumps(new))
    row(old, "predictions", game_id=1)["predicted_spread"] += 1

    class Conn:
        read_only = False

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    import psycopg

    monkeypatch.setattr(psycopg, "connect", lambda url: Conn())
    monkeypatch.setattr(parity, "read_active_preview", lambda conn: copy.deepcopy(old))
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@host/db")
    report_path = tmp_path / "out" / "report.json"

    code = parity.main(
        [
            "--candidate-dir",
            str(tmp_path),
            "--mode",
            "close-week",
            "--completed-week",
            "8",
            "--upcoming-week",
            "9",
            "--report",
            str(report_path),
        ]
    )

    report = json.loads(report_path.read_text())
    assert code == 1 and report["passed"] is False
    assert "secret" not in report_path.read_text()


def identity_tables(digest: str, cutoff: str) -> dict[str, list[dict]]:
    """Tables whose keys/values embed release-specific hashes and cutoffs."""
    return {
        "team_resume": [
            {
                "period_id": f"{digest * 24}@2026-09-03T04:00:00.000Z",
                "team": "A",
                "wins": 5,
                "sor": 0.61,
                "cutoff_utc": "2026-10-18T14:00:00Z",
            }
        ],
        "matchup_data_publications": [
            {
                "publication_id": f"2026:intended_update:{digest * 6}:{digest * 6}",
                "payload_sha256": digest * 32,
            }
        ],
        "team_possession_stats": [
            {
                "season": 2026,
                "as_of_week": 8,
                "team": "A",
                "role": "offense",
                "metric": "poss",
                "poss": 31.0,
                "source_versions": {"rating_run": f"season-2026-{digest * 12}"},
            }
        ],
        "team_rating_components": [
            {
                "component_id": "c-w9",
                "as_of_week": 9,
                "game_id": None,
                "rating_mean": 0.7,
                "cutoff_utc": cutoff,
            }
        ],
    }


def identity_pair():
    old, new = release(OLD_RUN), release(NEW_RUN)
    old.update(identity_tables("a1", "2026-10-25T16:00:00Z"))
    new.update(identity_tables("b2", "2026-10-25T20:52:00Z"))
    for tables, digest in ((old, "c1"), (new, "d2")):
        for r in tables["predictions"]:
            r["spread_model_version"] = f"v5:season-2026-{digest * 12}:{digest * 6}"
        tables["v5_rating_snapshots"].append(
            {
                "snapshot_id": "s-w9",
                "week": 9,
                "snapshot_class": "pregame",
                "overall_rating": 2.5,
                "cutoff_utc": "2026-10-25T16:00:00Z"
                if digest == "c1"
                else "2026-10-25T20:52:00Z",
            }
        )
    return old, new


def test_market_refresh_ignores_release_hashes_and_upcoming_cutoffs():
    old, new = identity_pair()

    assert run(old, new, mode="market-refresh").passed


def test_market_refresh_still_requires_earlier_week_cutoffs_identical():
    old, new = identity_pair()
    row(new, "v5_rating_snapshots", week=8)["cutoff_utc"] = "2026-10-20T18:00:00Z"

    assert any(
        "v5_rating_snapshots" in f and "cutoff_utc" in f
        for f in run(old, new, mode="market-refresh").failures
    )


def test_changed_substantive_values_fail_despite_masked_identity():
    old, new = identity_pair()
    new["team_resume"][0]["sor"] = 0.62
    row(new, "v5_rating_snapshots", week=9)["overall_rating"] = 2.6
    new["team_rating_components"][0]["rating_mean"] = 0.8
    new["team_possession_stats"][0]["poss"] = 32.0

    failures = run(old, new, mode="market-refresh").failures

    assert any(f.startswith("team_resume") and "sor" in f for f in failures)
    assert any("v5_rating_snapshots" in f and "overall_rating" in f for f in failures)
    assert any("team_rating_components" in f and "rating_mean" in f for f in failures)
    assert any("team_possession_stats" in f and "poss" in f for f in failures)


def test_hash_keyed_rows_pair_up_but_added_or_removed_rows_still_fail():
    old, new = identity_pair()
    new["team_resume"].append(
        {"period_id": f"{'b2' * 24}@2026-09-03T04:00:00.000Z", "team": "B", "wins": 1}
    )
    new["matchup_data_publications"] = []

    failures = run(old, new, mode="market-refresh").failures

    assert any(
        f.startswith("team_resume") and "new in the candidate" in f for f in failures
    )
    assert any(
        f.startswith("matchup_data_publications") and "missing" in f for f in failures
    )


def test_hash_mask_leaves_plain_numbers_and_words_alone():
    assert parity.normalize_value("123456789012") == "123456789012"
    assert parity.normalize_value("defaced-cafe") == "defaced-cafe"
    assert parity.normalize_value("v5:" + "0a" * 6) == "v5:<hash>"


def resume_pair(old_ranks, new_ranks, new_sor=None):
    """Four teams in one period: B, C, D tie at the bottom (0.0 vs 1.1e-14)."""
    sors = {"A": 50.0, "B": 0.0, "C": 1.1e-14, "D": 0.0}

    def table(ranks, sor_override=None):
        return {
            "team_resume": [
                {
                    "period_id": "p1",
                    "team": team,
                    "sor": (sor_override or {}).get(team, sors[team]),
                    "sor_rank": ranks[team],
                }
                for team in sors
            ]
        }

    return table(old_ranks), table(new_ranks, new_sor)


def resume_failures(old, new):
    old_all, new_all = release(OLD_RUN), release(NEW_RUN)
    old_all.update(old)
    new_all.update(new)
    return run(old_all, new_all, mode="market-refresh").failures


def test_sor_rank_may_permute_inside_a_tied_sor_group():
    old, new = resume_pair(
        {"A": 1, "C": 2, "B": 3, "D": 4}, {"A": 1, "B": 2, "D": 3, "C": 4}
    )

    assert not [f for f in resume_failures(old, new) if f.startswith("team_resume")]


def test_sor_rank_change_outside_the_tied_group_still_fails():
    old, new = resume_pair(
        {"A": 1, "C": 2, "B": 3, "D": 4}, {"A": 2, "B": 1, "D": 3, "C": 4}
    )

    failures = resume_failures(old, new)

    assert any("team_resume" in f and "sor_rank" in f for f in failures)


def test_sor_rank_change_without_a_tie_fails_and_sor_stays_strict():
    old, new = resume_pair(
        {"A": 1, "C": 2, "B": 3, "D": 4},
        {"A": 1, "C": 2, "B": 3, "D": 4},
        new_sor={"A": 50.5},
    )
    assert any("team_resume" in f and "sor" in f for f in resume_failures(old, new))

    old, new = resume_pair(
        {"A": 1, "C": 2, "B": 3, "D": 4}, {"A": 1, "C": 2, "B": 3, "D": 4}
    )
    new["team_resume"][0]["sor_rank"] = 2
    assert any("sor_rank" in f for f in resume_failures(old, new))
