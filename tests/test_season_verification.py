"""Season verification checks are computed from the payload, never self-reported."""

from __future__ import annotations

import copy
import json

import pytest

from cks_picks_cfb.season import release
from cks_picks_cfb.season import verification as v
from cks_picks_cfb.season.manifest import canonical, sha
from cks_picks_cfb.season.projection_common import (
    MARKET_POLICY_VERSION,
    MEASUREMENT_OUTPUTS,
    PROJECTION_ORDER,
    RATING_OUTPUTS,
    SELECTION_POLICY_VERSION,
    benchmark_grading_version,
    weekly_run_id,
)

IDENTITY = {
    "model_manifest_sha256": "1" * 64,
    "revision_manifest_sha256": "2" * 64,
    "workflow_version": "season_workflow_v1",
    "grading_policy_sha256": "3" * 64,
    "code_sha": "a" * 40,
    "config_sha": "4" * 64,
    "season": 2026,
    "through_week": 1,
    "active_week": 2,
    "as_of": "2026-09-13T12:00:00Z",
    "next_week_mode": "live",
}
OUTPUT_REFS = {
    name: {"uri": f"/prepared/{name}.parquet", "sha256": sha(name.encode()), "rows": 1}
    for name in RATING_OUTPUTS + MEASUREMENT_OUTPUTS
}
MANIFEST = {"identity": IDENTITY, "output_refs": OUTPUT_REFS}
RELEASE_ID = v.run_id_for(IDENTITY)
LINEAGE = v.lineage_identities(IDENTITY, OUTPUT_REFS)


def _t(day: int, hour: int, minute: int = 0) -> str:
    return f"2026-09-{day:02}T{hour:02}:{minute:02}:00.000000+00:00"


# game_id: (week, kickoff, home, away, final or None)
GAMES = {
    1: (0, _t(5, 16), "A", "B", (24, 17)),
    2: (1, _t(12, 16), "C", "D", (27, 24)),
    3: (1, _t(12, 19), "A", "C", (10, 31)),
    4: (2, _t(19, 16), "B", "D", None),
    5: (3, _t(26, 16), "A", "D", None),  # future week: scheduled, never predicted
}
# game_id: (predicted spread, predicted total)
PREDICTED = {1: (7.0, 48.0), 2: (5.0, 50.0), 3: (-4.0, 45.0), 4: (-1.0, 52.0)}
# quote_id: (game, provider, captured_at, spread, total, prices)
QUOTES = {
    "q1": (1, "book1", _t(5, 12), -3.5, None, (-105.0, -115.0, None, None)),
    "q2": (1, "book2", _t(5, 12), -3.0, None, (-110.0, -110.0, None, None)),
    # CFBD retrospective line: captured after kickoff, no prices (-110 default).
    "q3": (1, "DraftKings", _t(13, 12), None, 45.5, (None, None, None, None)),
    "q4": (2, "book1", _t(12, 10), -3.0, None, (-110.0, -110.0, None, None)),
    "q5": (4, "book1", _t(13, 11), 2.5, None, (-120.0, 100.0, None, None)),
}
# snapshot_id: (game, captured_at, target, line, quotes)
SNAPSHOTS = {
    "s1": (1, _t(5, 12), "spread", -3.25, ["q1", "q2"]),
    "s2": (1, _t(13, 12), "total", 45.5, ["q3"]),
    "s3": (2, _t(12, 10), "spread", -3.0, ["q4"]),
    "s4": (4, _t(13, 11), "spread", 2.5, ["q5"]),
}
# (game, target): (snapshot, quote, side, benchmark or None)
SELECTED = {
    (1, "spread"): ("s1", "q2", "home", "retained_prekickoff"),
    (1, "total"): ("s2", "q3", "over", "cfbd_retrospective"),
    (2, "spread"): ("s3", "q4", "home", "retained_prekickoff"),
    (4, "spread"): ("s4", "q5", "home", None),  # live week: not yet graded
}
TEAMS = ("A", "B", "C", "D")


def _sorted(table: str, rows: list[dict]) -> list[dict]:
    keys = {**release.PROJECTION_KEYS, "prediction_runs": ("run_id",)}[table]
    return sorted(rows, key=lambda row: tuple(row[k] for k in keys))


def synthetic_payload(
    release_id: str = RELEASE_ID,
    rating: str = LINEAGE["rating"],
    measurement: str = LINEAGE["measurement"],
    *,
    as_of: str = IDENTITY["as_of"],
    next_week_mode: str = "live",
) -> dict[str, list[dict]]:
    """A small, fully consistent payload for through_week=1, active_week=2."""
    run = {w: weekly_run_id(release_id, w) for w in range(3)}
    stamp = _t(13, 12)
    prices = ("home_spread_price", "away_spread_price", "over_price", "under_price")
    quotes = [
        {
            "quote_id": qid,
            "game_id": game,
            "provider": provider,
            "captured_at": captured,
            "spread": spread,
            "total": total,
            "source_capture_id": None,
            **dict(zip(prices, quote_prices, strict=True)),
            "quote_updated_at": None,
            "source_event_id": None,
        }
        for qid, (
            game,
            provider,
            captured,
            spread,
            total,
            quote_prices,
        ) in QUOTES.items()
    ]
    snapshots = [
        {
            "snapshot_id": sid,
            "game_id": game,
            "captured_at": captured,
            "spread": line if target == "spread" else None,
            "total": line if target == "total" else None,
            "spread_rule": "median" if target == "spread" else None,
            "total_rule": "median" if target == "total" else None,
            "spread_provider_count": len(ids) if target == "spread" else 0,
            "total_provider_count": len(ids) if target == "total" else 0,
            "source_quote_ids": ids,
            "policy_version": MARKET_POLICY_VERSION,
            "created_at": stamp,
        }
        for sid, (game, captured, target, line, ids) in SNAPSHOTS.items()
    ]
    links = [
        {"snapshot_id": sid, "quote_id": qid, "target": target}
        for sid, (_, _, target, _, ids) in SNAPSHOTS.items()
        for qid in ids
    ]
    quote_rows = {row["quote_id"]: row for row in quotes}
    selections, grades = [], []
    for (game, target), (sid, qid, side, benchmark) in SELECTED.items():
        week, _, _, _, final = GAMES[game]
        point = quote_rows[qid][target]
        mean = PREDICTED[game][0 if target == "spread" else 1]
        price = quote_rows[qid][
            {"home": "home_spread_price", "away": "away_spread_price"}.get(
                side, side + "_price"
            )
        ]
        price = -110.0 if price is None else price
        edge = abs(mean + point) if target == "spread" else abs(mean - point)
        selections.append(
            {
                "run_id": run[week],
                "game_id": game,
                "target": target,
                "snapshot_id": sid,
                "quote_id": qid,
                "side": side,
                "point": point,
                "price": price,
                "edge": edge,
                "policy_version": SELECTION_POLICY_VERSION,
                "created_at": stamp,
            }
        )
        if benchmark is None:
            continue
        result, profit = {
            (1, "spread"): ("win", 0.9091),
            (1, "total"): ("loss", -1.0),
            (2, "spread"): ("push", 0.0),
        }[(game, target)]
        grades.append(
            {
                "run_id": run[week],
                "game_id": game,
                "target": target,
                "market_snapshot_id": sid,
                "market_quote_id": qid,
                "side": side,
                "result": result,
                "profit_units": profit,
                "grading_version": benchmark_grading_version(benchmark),
                "graded_at": stamp,
            }
        )
    selection_by = {(row["game_id"], row["target"]): row for row in selections}
    completed = {"A": [], "B": [], "C": [], "D": []}
    for game, (week, _, home, away, final) in GAMES.items():
        if final:
            completed[home].append(week)
            completed[away].append(week)
    predictions = []
    for game, (spread, total) in PREDICTED.items():
        week, _, home, away, _ = GAMES[game]
        counts = [sum(w < week for w in completed[t]) for t in (home, away)]
        row = {
            "market_snapshot_id": None,
            "run_id": run[week],
            "game_id": game,
            "predicted_spread": spread,
            "predicted_total": total,
            "predicted_spread_std_dev": 17.8,
            "predicted_total_std_dev": 17.4,
            "high_confidence": False,
            "high_confidence_eligible": False,
            "home_completed_games": counts[0],
            "away_completed_games": counts[1],
            "regime": ["preseason", "one_game"][min(counts)],
            "spread_model_version": "v5",
            "total_model_version": "v5",
            "created_at": stamp,
        }
        for target, line, lean, edge in (
            ("spread", "home_team_spread_line", "spread_lean", "edge_spread"),
            ("total", "total_line", "total_lean", "edge_total"),
        ):
            selection = selection_by.get((game, target))
            row[line] = selection["point"] if selection else None
            row[lean] = selection["side"] if selection else None
            row[edge] = selection["edge"] if selection else None
            if selection and row["market_snapshot_id"] is None:
                row["market_snapshot_id"] = selection["snapshot_id"]
        predictions.append(row)
    predicted = {row["game_id"]: row for row in predictions}
    game_columns = (
        *("home_team_spread_line", "total_line", "predicted_spread", "predicted_total"),
        *("predicted_spread_std_dev", "predicted_total_std_dev", "spread_lean"),
        *("total_lean", "edge_spread", "edge_total", "high_confidence"),
    )
    games, results, venues = [], [], []
    grade_by = {(g["game_id"], g["target"]): g for g in grades}
    for game, (week, kickoff, home, away, final) in GAMES.items():
        prediction = predicted.get(game)
        games.append(
            {
                "game_id": game,
                "season": 2026,
                "week": week,
                "start_date": kickoff,
                "home_team": home,
                "away_team": away,
                **{c: prediction[c] if prediction else None for c in game_columns},
                "high_confidence": False,
                "source_config": "season_workflow_v1" if prediction else None,
                "system_name": "V5" if prediction else None,
                "model_id": "v5-intended-update-2026-v1" if prediction else None,
                "inserted_at": stamp,
                "updated_at": stamp,
            }
        )
        venues.append(
            {
                "game_id": game,
                "venue_id": 100 + game,
                "venue_name": f"Stadium {home}",
                "city": "City",
                "state": "ST",
                "country_code": "US",
                "timezone": "America/Chicago",
                "neutral_site": False,
                "source": "cfbd",
                "updated_at": stamp,
            }
        )
        if final:
            results.append(
                {
                    "completion_state": "completed",
                    "source_dataset_version_id": "finals-v1",
                    "game_id": game,
                    "home_points": final[0],
                    "away_points": final[1],
                    "spread_result": grade_by.get((game, "spread"), {}).get("result"),
                    "total_result": grade_by.get((game, "total"), {}).get("result"),
                    "scored_at": stamp,
                }
            )
    week_games = {w: [g for g, spec in GAMES.items() if spec[0] == w] for w in range(3)}
    runs = [
        {
            "run_id": run[w],
            "season": 2026,
            "week": w,
            "state": "scored" if w <= 1 else "published",
            "expected_games": len(week_games[w]),
            "predicted_games": sum(predicted[g]["run_id"] == run[w] for g in predicted),
            "lined_games": sum(
                p["run_id"] == run[w]
                and p["home_team_spread_line"] is not None
                and p["total_line"] is not None
                for p in predictions
            ),
            "data_as_of": as_of,
            "source_config": "season_workflow_v1",
            "system_name": "V5",
            "model_id": "v5-intended-update-2026-v1",
            "code_sha": "a" * 40,
            "config_sha": "4" * 64,
            "model_bundle_sha256": "5" * 64,
            "rating_manifest_sha256": rating,
            "artifact_uri": f"season-run:{release_id}#w{w}",
            "artifact_sha256": "6" * 64,
            "input_dataset_refs": [],
            "validation": {},
            "created_at": stamp,
            "published_at": stamp,
            "frozen_at": None,
            "scored_at": stamp if w <= 1 else None,
            "evidence_class": "pending"
            if w == 2 and next_week_mode == "live"
            else "replay",
        }
        for w in range(3)
    ]
    snapshots_v5 = []
    for i, team in enumerate(TEAMS):
        rating_row = {
            "source_run_id": release_id,
            "source_manifest_sha256": rating,
            "team": team,
            "season": 2026,
            "offense_rating": 0.5 * i,
            "offense_variance": 0.5,
            "defense_rating": -0.5 * i,
            "defense_variance": 0.5,
            "overall_rating": 0.0,
            "overall_variance": 0.25,
            "fallback_reason": None,
            "created_at": stamp,
        }
        for week in range(3):
            suffix = "preseason" if week == 0 else f"week-{week}"
            snapshots_v5.append(
                {
                    **rating_row,
                    "snapshot_id": f"{release_id}:pregame:{team}:{suffix}",
                    "week": week,
                    "game_id": None,
                    "snapshot_class": "pregame",
                    "cutoff_utc": _t(5 + 7 * week, 10),
                }
            )
        for post in range(2):
            snapshots_v5.append(
                {
                    **rating_row,
                    "snapshot_id": f"{release_id}:current:post-week-{post}:{team}",
                    "week": post,
                    "game_id": None,
                    "snapshot_class": "current",
                    "cutoff_utc": _t(12 + 7 * post, 10),
                }
            )
    components = [
        {
            "component_id": f"c-{team}-{role}",
            "v5_snapshot_id": f"{release_id}:{snapshot}",
            "lineage": "intended_update",
            "candidate_id": "ppp__rho_0_60__exposure",
            "source_manifest_sha256": rating,
            "snapshot_class": cls,
            "season": 2026,
            "as_of_week": 2,
            "game_id": None,
            "cutoff_utc": _t(12, 10),
            "rating_team": team,
            "team": team,
            "unit_role": role,
            "rating_mean": mean,
            "rating_variance": 0.5,
            "prior_mean": 0.0,
            "prior_variance": 1.0,
            "prior_weight": 0.5,
            "prior_contribution": 0.0,
            "evidence_weight": 0.5,
            "process_variance": 0.0,
            "k": 8.0,
            "usable_exposure": 8.0,
            "completed_games": 1,
            "evidence": [{"game_id": 1}],
            "excluded_observations": [],
            "prior_detail": {},
            "fallback_reason": None,
            "created_at": stamp,
        }
        for team, role, snapshot, cls, mean in (
            ("A", "offense", "pregame:A:week-2", "pregame", 0.0),
            ("B", "defense", "current:post-week-1:B", "current", -0.5),
        )
    ]
    measurements = [
        {
            "season": 2026,
            "game_id": 1,
            "team": team,
            "unit_role": "offense",
            "measurement_id": "ppp",
            "week": 0,
            "season_type": None,
            "kickoff_utc": GAMES[1][1],
            "opponent": opponent,
            "side": side,
            "numerator": 9.6,
            "denominator": 8.0,
            "raw_value": 1.2,
            "usable_exposure": 8.0,
            "exposure_unit": "possessions",
            "coverage_status": "observed",
            "missing_reason": None,
            "quality_flags": None,
            "timing_class": "replay",
            "rating_usable": True,
            "opponent_fbs": True,
            "measurement_manifest_sha256": measurement,
            "source_versions": {},
            "updated_at": stamp,
        }
        for team, opponent, side in (("A", "B", "home"), ("B", "A", "away"))
    ]
    season_stats = [
        {
            "season": 2026,
            "as_of_week": 2,
            "team": team,
            "role": "offense",
            "metric": "points_per_game",
            "value": 20.0,
            "n": games,
            "games": games,
            "rank": None,
            "cohort_size": None,
            "source_versions": {},
            "updated_at": stamp,
        }
        for team, games in (("A", 2), ("B", 1), ("C", 2), ("D", 1))
    ]
    possession = [
        {
            "season": 2026,
            "as_of_week": 2,
            "team": team,
            "role": "offense",
            "metric": "ppp",
            "value": 1.0 if games else None,
            "numerator": 8.0 * games if games else None,
            "denominator": 8.0 * games if games else None,
            "n": 8.0 * games,
            "games": games,
            "games_excluded": len(excluded),
            "excluded": [{"game_id": g, "reason": "missing_plays"} for g in excluded],
            "rank": None,
            "cohort_size": None,
            "as_of_cutoff": _t(13, 12),
            "rating_manifest_sha256": rating,
            "measurement_manifest_sha256": measurement,
            "source_versions": {},
            "updated_at": stamp,
        }
        for team, games, excluded in (
            ("A", 2, []),
            ("B", 0, [1]),
            ("C", 2, []),
            ("D", 1, []),
        )
    ]
    adjusted = [
        {
            "season": 2026,
            "as_of_week": 2,
            "team": "A",
            "role": "offense",
            "measurement_id": "ppp",
            "raw_value": 1.0,
            "adjusted_value": 1.1,
            "opponent_adjustment": 0.1,
            "adjusted_rank": 1,
            "cohort_size": 4,
            "primary_exposure": 16.0,
            "games": 2,
            "adjustment_method": "opponent_mean",
            "as_of_cutoff": _t(13, 12),
            "rating_manifest_sha256": rating,
            "measurement_manifest_sha256": measurement,
            "updated_at": stamp,
        }
    ]
    publications = [
        {
            "publication_id": f"{release_id}:matchup",
            "season": 2026,
            "lineage": "intended_update",
            "rating_manifest_sha256": rating,
            "rating_manifest_uri": f"season-run:{release_id}#ratings",
            "measurement_manifest_sha256": measurement,
            "measurement_manifest_uri": f"season-run:{release_id}#measurements",
            "observations_records_sha": "7" * 64,
            "as_of_weeks": [2],
            "rating_scale": {},
            "row_counts": {
                "team_game_measurements": len(measurements),
                "team_possession_stats": len(possession),
                "team_possession_adjusted": len(adjusted),
                "team_rating_components": len(components),
            },
            "payload_sha256": "8" * 64,
            "code_sha": "a" * 40,
            "published_at": stamp,
        }
    ]
    stats = {
        "season": 2026,
        "as_of_week": 1,
        "spread_wins": 1,
        "spread_losses": 0,
        "spread_pushes": 1,
        "total_wins": 0,
        "total_losses": 1,
        "total_pushes": 0,
        "spread_profit_units": 0.9091,
        "total_profit_units": -1.0,
        "updated_at": stamp,
    }
    site = [
        {
            "season": 2026,
            "week": w,
            "run_id": run[w],
            "selected_at": stamp,
            "reason": "season_release",
        }
        for w in range(3)
    ]
    tables = {
        "prediction_runs": runs,
        "games": games,
        "game_venues": venues,
        "game_results": results,
        "predictions": predictions,
        "prediction_grades": grades,
        "market_quotes": quotes,
        "market_snapshots": snapshots,
        "market_snapshot_quotes": links,
        "prediction_market_selections": selections,
        "system_stats": [stats],
        "v5_rating_snapshots": snapshots_v5,
        "team_season_stats": season_stats,
        "matchup_data_publications": publications,
        "team_game_measurements": measurements,
        "team_possession_stats": possession,
        "team_possession_adjusted": adjusted,
        "team_rating_components": components,
        "site_week_selections": site,
    }
    return {name: _sorted(name, rows) for name, rows in tables.items()}


PASSING_PREPARE = {
    name: {"passed": True, "observed": {"violations": 0}, "source": "prepare"}
    for name in v.REQUIRED_PREPARE_CHECKS
}


def failing(payload, manifest=MANIFEST) -> set[str]:
    checks = v.derive_checks(payload, manifest)
    assert set(checks) == v.REQUIRED_PROJECTION_CHECKS
    return {name for name, entry in checks.items() if not entry["passed"]}


def report_for(payload, prepare=PASSING_PREPARE) -> dict:
    return v.assemble_report(payload, MANIFEST, prepare)


def _row(payload, table, **match):
    return next(
        row
        for row in payload[table]
        if all(row[k] == value for k, value in match.items())
    )


@pytest.fixture
def payload():
    return synthetic_payload()


def test_synthetic_payload_passes_every_projection_check(payload):
    checks = v.derive_checks(payload, MANIFEST)
    assert {n for n, e in checks.items() if not e["passed"]} == set()
    assert all(entry["source"] == "projection" for entry in checks.values())
    report = report_for(payload)
    assert report["state"] == "passed"
    v.validate_report(json.loads(canonical(report)), projections=payload)


def test_report_is_deterministic_and_canonical(payload):
    first = canonical(report_for(payload))
    assert first == canonical(report_for(copy.deepcopy(payload)))
    assert set(json.loads(first)["checks"]) == v.REQUIRED_CHECKS


def _set(table, match, **values):
    def mutate(payload):
        _row(payload, table, **match).update(values)

    return mutate


def _drop(table, **match):
    def mutate(payload):
        payload[table].remove(_row(payload, table, **match))

    return mutate


def _append(table, row_factory):
    def mutate(payload):
        payload[table].append(row_factory(payload))

    return mutate


def _run_id(week):
    return weekly_run_id(RELEASE_ID, week)


def _extra_quote(payload):
    return {**_row(payload, "market_quotes", quote_id="q5"), "quote_id": "q9"}


NEGATIVES = {
    # tables_complete
    "missing_table": (lambda p: p.pop("game_venues"), None),
    "duplicate_key": (
        _append("game_venues", lambda p: dict(p["game_venues"][0])),
        {"tables_complete"},
    ),
    "unsorted_rows": (lambda p: p["game_venues"].reverse(), {"tables_complete"}),
    "foreign_season": (
        _set("team_season_stats", {"team": "A"}, season=2025),
        {"tables_complete"},
    ),
    # weeks_and_slate
    "run_state": (
        _set("prediction_runs", {"week": 1}, state="published"),
        {"weeks_and_slate"},
    ),
    "live_evidence_class": (
        _set("prediction_runs", {"week": 2}, evidence_class="replay"),
        {"weeks_and_slate"},
    ),
    "site_selection_run": (
        _set("site_week_selections", {"week": 1}, run_id=_run_id(0)),
        {"weeks_and_slate"},
    ),
    "started_live_game_predicted": (
        _set("games", {"game_id": 4}, start_date=_t(13, 11, 30)),
        {"weeks_and_slate"},
    ),
    # predictions_in_games
    "registry_predicted_count": (
        _set("prediction_runs", {"week": 1}, predicted_games=1),
        {"predictions_in_games"},
    ),
    "registry_lined_count": (
        _set("prediction_runs", {"week": 1}, lined_games=2),
        {"predictions_in_games"},
    ),
    # prior_finals_complete
    "missing_prior_final": (
        _drop("game_results", game_id=3),
        {"prior_finals_complete", "stats_games"},
    ),
    "final_for_live_game": (
        _append(
            "game_results",
            lambda p: {**_row(p, "game_results", game_id=3), "game_id": 4},
        ),
        {"prior_finals_complete", "grades_recomputed"},
    ),
    "negative_score": (
        _set("game_results", {"game_id": 3}, home_points=-1),
        {"prior_finals_complete"},
    ),
    # grades_recomputed
    "wrong_result": (
        _set("prediction_grades", {"game_id": 2}, result="win"),
        {"grades_recomputed", "system_stats_match"},
    ),
    "titlecase_result": (
        _set("prediction_grades", {"game_id": 1, "target": "total"}, result="Loss"),
        {"grades_recomputed", "system_stats_match"},
    ),
    "wrong_profit": (
        _set("prediction_grades", {"game_id": 1, "target": "spread"}, profit_units=1.0),
        {"grades_recomputed", "system_stats_match"},
    ),
    "final_selection_ungraded": (
        _drop("prediction_grades", game_id=2),
        {"grades_recomputed", "system_stats_match"},
    ),
    "results_column_disagrees": (
        _set("game_results", {"game_id": 3}, spread_result="win"),
        {"grades_recomputed"},
    ),
    # selection_matches_prediction
    "lean_without_selection": (
        _set("predictions", {"game_id": 3}, spread_lean="home"),
        {"selection_matches_prediction"},
    ),
    "wrong_edge": (
        _set("prediction_market_selections", {"game_id": 2}, edge=2.5),
        {"selection_matches_prediction"},
    ),
    "game_differs_from_prediction": (
        _set("games", {"game_id": 2}, predicted_total=51.0),
        {"selection_matches_prediction"},
    ),
    "unpredicted_game_with_line": (
        _set("games", {"game_id": 5}, total_line=50.0),
        {"selection_matches_prediction"},
    ),
    # market_links
    "selection_quote_from_other_game": (
        _set("market_quotes", {"quote_id": "q4"}, game_id=3),
        {"market_links"},
    ),
    "quote_after_as_of": (
        _set("market_quotes", {"quote_id": "q1"}, captured_at=_t(13, 13)),
        {"market_links"},
    ),
    "unlinked_selection": (
        _drop("market_snapshot_quotes", snapshot_id="s1", quote_id="q2"),
        {"market_links"},
    ),
    "retained_quote_after_kickoff": (
        _set("market_quotes", {"quote_id": "q2"}, captured_at=_t(5, 17)),
        {"market_links"},
    ),
    "selection_price_differs": (
        _set("prediction_market_selections", {"game_id": 4}, price=-110.0),
        {"market_links"},
    ),
    "invalid_benchmark": (
        _set("prediction_grades", {"game_id": 2}, grading_version="closing"),
        {"market_links", "grades_recomputed"},
    ),
    "orphan_link_quote": (
        _append(
            "market_snapshot_quotes",
            lambda p: {"snapshot_id": "s4", "quote_id": "q9", "target": "spread"},
        ),
        {"market_links"},
    ),
    "foreign_snapshot_source": (
        _set("market_snapshots", {"snapshot_id": "s4"}, source_quote_ids=["q1"]),
        {"market_links"},
    ),
    # system_stats_match
    "stats_profit": (
        _set("system_stats", {"season": 2026}, spread_profit_units=0.9090),
        {"system_stats_match"},
    ),
    "stats_counts": (
        _set("system_stats", {"season": 2026}, total_losses=2),
        {"system_stats_match"},
    ),
    # rating_lineage
    "foreign_run_rating": (
        _set("prediction_runs", {"week": 0}, rating_manifest_sha256="9" * 64),
        {"rating_lineage"},
    ),
    "foreign_measurement": (
        _set(
            "team_game_measurements",
            {"team": "A"},
            measurement_manifest_sha256="9" * 64,
        ),
        {"rating_lineage"},
    ),
    "local_manifest_uri": (
        _set(
            "matchup_data_publications",
            {"season": 2026},
            rating_manifest_uri="/Users/me/ratings.json",
        ),
        {"rating_lineage"},
    ),
    # rating_snapshots
    "missing_pregame_week": (
        lambda p: p.__setitem__(
            "v5_rating_snapshots",
            [
                r
                for r in p["v5_rating_snapshots"]
                if not r["snapshot_id"].endswith("week-1")
            ],
        ),
        {"rating_snapshots"},
    ),
    "pregame_with_game": (
        _set(
            "v5_rating_snapshots",
            {"snapshot_id": f"{RELEASE_ID}:pregame:C:week-1"},
            game_id=2,
        ),
        {"rating_snapshots"},
    ),
    "component_differs_from_snapshot": (
        _set(
            "team_rating_components", {"component_id": "c-A-offense"}, rating_mean=0.1
        ),
        {"rating_snapshots"},
    ),
    "component_snapshot_absent": (
        _set(
            "team_rating_components",
            {"component_id": "c-B-defense"},
            v5_snapshot_id="nope",
        ),
        {"rating_snapshots"},
    ),
    # stats_games
    "season_stats_games": (
        _set("team_season_stats", {"team": "C"}, games=1),
        {"stats_games"},
    ),
    "possession_games": (
        _set("team_possession_stats", {"team": "D"}, games=2),
        {"stats_games"},
    ),
    "possession_excluded_mismatch": (
        _set("team_possession_stats", {"team": "B"}, games_excluded=0),
        {"stats_games"},
    ),
    "adjusted_games": (
        _set("team_possession_adjusted", {"team": "A"}, games=3),
        {"stats_games"},
    ),
    # completed_counts_regime
    "completed_count": (
        _set("predictions", {"game_id": 3}, home_completed_games=0),
        {"completed_counts_regime"},
    ),
    "regime": (
        _set("predictions", {"game_id": 4}, regime="established"),
        {"completed_counts_regime"},
    ),
    # matchup_publication
    "row_counts": (
        _set(
            "matchup_data_publications",
            {"season": 2026},
            row_counts={"team_game_measurements": 2},
        ),
        {"matchup_publication"},
    ),
    "as_of_weeks": (
        _set("matchup_data_publications", {"season": 2026}, as_of_weeks=[1]),
        {"matchup_publication"},
    ),
    "environment_column": (
        _set("matchup_data_publications", {"season": 2026}, environment="preview"),
        {"matchup_publication"},
    ),
    "release_id_column": (
        lambda p: [row.update(release_id="preview-x") for row in p["game_venues"]],
        {"matchup_publication"},
    ),
    # venues_cover
    "missing_venue": (_drop("game_venues", game_id=4), {"venues_cover"}),
    "venue_for_unknown_game": (
        _append("game_venues", lambda p: {**p["game_venues"][-1], "game_id": 99}),
        {"venues_cover"},
    ),
}


@pytest.fixture(params=sorted(NEGATIVES))
def negative(request):
    return request.param


def test_each_mutation_fails_exactly_its_checks_and_is_refused(payload, negative):
    mutate, expected = NEGATIVES[negative]
    good_report = report_for(payload)
    mutate(payload)
    failed = failing(payload)
    if expected is None:
        assert "tables_complete" in failed
    else:
        assert failed == expected
        # A report computed from the mutated payload is failed and refused ...
        mutated_report = report_for(payload)
        assert mutated_report["state"] == "failed"
        with pytest.raises(v.VerificationError):
            v.validate_report(mutated_report, projections=payload)
    # ... and the honest report of the original payload does not cover it.
    with pytest.raises(v.VerificationError):
        v.validate_report(good_report, projections=payload)


def test_every_projection_check_has_a_negative_test():
    covered = set().union(*(e for _, e in NEGATIVES.values() if e))
    assert covered == v.REQUIRED_PROJECTION_CHECKS


def test_quote_without_link_target_point_fails(payload):
    payload["market_quotes"].append(_extra_quote(payload))
    payload["market_quotes"] = _sorted("market_quotes", payload["market_quotes"])
    _row(payload, "market_quotes", quote_id="q9").update(spread=None, total=50.0)
    payload["market_snapshot_quotes"].append(
        {"snapshot_id": "s4", "quote_id": "q9", "target": "spread"}
    )
    payload["market_snapshot_quotes"] = _sorted(
        "market_snapshot_quotes", payload["market_snapshot_quotes"]
    )
    assert failing(payload) == {"market_links"}


def test_retrospective_line_in_live_week_fails(payload):
    grade = {
        "run_id": _run_id(2),
        "game_id": 4,
        "target": "spread",
        "market_snapshot_id": "s4",
        "market_quote_id": "q5",
        "side": "home",
        "result": "win",
        "profit_units": 0.8333,
        "grading_version": benchmark_grading_version("cfbd_retrospective"),
        "graded_at": _t(13, 12),
    }
    payload["prediction_grades"] = _sorted(
        "prediction_grades", [*payload["prediction_grades"], grade]
    )
    assert "market_links" in failing(payload)


def test_stats_as_of_week_is_latest_graded_week_like_legacy(payload):
    """Legacy score_to_db: as_of_week = COALESCE(MAX(graded game week), 0); a
    release whose completed weeks carry no graded line reports week 0."""
    payload["prediction_grades"] = []
    for row in payload["game_results"]:
        row.update(spread_result=None, total_result=None)
    stats = payload["system_stats"][0]
    zeroed = {k: 0 for k in stats if k.endswith(("_wins", "_losses", "_pushes"))}
    stats.update(zeroed, spread_profit_units=0.0, total_profit_units=0.0)
    stats["as_of_week"] = 1  # through_week, but nothing graded
    assert "system_stats_match" in failing(payload)
    stats["as_of_week"] = 0
    assert "system_stats_match" not in failing(payload)


def test_lined_games_counts_only_games_with_both_lines_like_legacy(payload):
    """Legacy publish_to_db counts a game as lined only when it has both a spread
    and a total line; game 2 (week 1) has a spread line only."""
    week1 = _row(payload, "prediction_runs", week=1)
    assert week1["lined_games"] == 0
    assert "predictions_in_games" not in failing(payload)
    week1["lined_games"] = 1  # the former "any line" count
    assert failing(payload) == {"predictions_in_games"}


def test_malformed_payload_fails_closed_instead_of_crashing(payload):
    for row in payload["predictions"]:
        del row["regime"]
    assert failing(payload) == {"completed_counts_regime"}
    entry = v.derive_checks(payload, MANIFEST)["completed_counts_regime"]
    assert entry["observed"]["error"] is True


def test_validate_report_rejects_self_reported_or_malformed_checks(payload):
    report = report_for(payload)
    v.validate_report(report, projections=payload)
    cases = []
    for name in ("tables_complete", "checksums_at_read"):
        for bad in (True, "passed", {"passed": "true", "observed": {}}):
            forged = copy.deepcopy(report)
            forged["checks"][name] = bad
            cases.append(forged)
    missing = copy.deepcopy(report)
    missing["checks"].pop("score_reconciliation")
    extra = copy.deepcopy(report)
    extra["checks"]["bonus"] = dict(report["checks"]["venues_cover"])
    v1 = copy.deepcopy(report)
    v1["schema_version"] = "season_verification_v1"
    wrong_source = copy.deepcopy(report)
    wrong_source["checks"]["venues_cover"]["source"] = "prepare"
    tampered_observed = copy.deepcopy(report)
    tampered_observed["checks"]["venues_cover"]["observed"]["venues"] = 99
    digest = copy.deepcopy(report)
    digest["projection_checks"]["games"]["sha256"] = "0" * 64
    counts = copy.deepcopy(report)
    counts["row_counts"]["games"] += 1
    failed_prepare = copy.deepcopy(report)
    failed_prepare["checks"]["paired_predictions"]["passed"] = False
    for forged in (
        *cases,
        missing,
        extra,
        v1,
        wrong_source,
        tampered_observed,
        digest,
        counts,
        failed_prepare,
    ):
        with pytest.raises(v.VerificationError):
            v.validate_report(forged, projections=payload)


def test_validate_report_binds_identity_and_outputs_to_manifest(payload):
    report = report_for(payload)
    v.validate_report(report, projections=payload, manifest=MANIFEST)
    other = {**MANIFEST, "identity": {**IDENTITY, "code_sha": "b" * 40}}
    with pytest.raises(v.VerificationError, match="identity"):
        v.validate_report(report, projections=payload, manifest=other)
    # A report re-derived for another identity cannot cover this payload.
    forged = {**report, "identity": other["identity"]}
    with pytest.raises(v.VerificationError):
        v.validate_report(forged, projections=payload)


def test_manifest_identities_must_match_derivation(payload):
    with pytest.raises(v.VerificationError, match="identities"):
        v.derive_checks(
            payload, {**MANIFEST, "identities": {"rating": "0" * 64, "measurement": ""}}
        )
    assert failing(payload, {**MANIFEST, "identities": LINEAGE}) == set()


def test_projection_digests_equal_release_projection_check(payload):
    digests = v.projection_digests(payload)
    assert list(digests) == list(PROJECTION_ORDER)
    for table in PROJECTION_ORDER:
        assert digests[table] == release.projection_check(payload[table])


def test_run_id_matches_existing_runner_formula():
    assert RELEASE_ID == "season-2026-" + sha(canonical(IDENTITY))[:24]


def test_pinned_bridge_matches_model_validation():
    from cks_picks_cfb.season.manifest import validate_model

    model = {
        "schema_version": "season_model_v1",
        "model_id": "v5-intended-update-2026-v1",
        "design": "ppp__rho_0_60__exposure",
        "development_seasons": [
            2015,
            2016,
            2017,
            2018,
            2019,
            2021,
            2022,
            2023,
            2024,
            2025,
        ],
        "inputs": {
            name: {"uri": name, "sha256": v.PINNED_BRIDGE_SHA256}
            for name in (
                "bridge",
                "priors",
                "terminal",
                "historical_population",
                "historical_events",
            )
        },
    }
    validate_model(model)
