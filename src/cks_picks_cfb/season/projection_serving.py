"""Serving-core projection builder (owner: P1).

Builds the serving-core tables of the Step 2 payload from prepared frames, following
the authoritative spec in :mod:`cks_picks_cfb.season.projection_common`.

Inputs used (nothing is read from a database):

* ``frames["predictions"]``: margin/total rows (``run_id``, ``week``, ``game_id``,
  ``target``, ``mean``, ``variance``, ``completed_game_stage``); one season run id.
* ``frames["grades"]``: ``grading.grade_predictions`` rows, one per game and target.
* ``frames["finals"]``: completed-game scores.
* ``inputs.schedule`` (the FULL season, canonical ``home_team``/``away_team`` plus
  provider ``home_team_provider``/``away_team_provider``), ``inputs.quotes`` and
  ``inputs.historical_lines`` (raw market rows; see ``grading.normalize_quotes``).
* ``revision``: ``captured_at``, ``pre_week_cutoffs`` and ``inputs`` (dataset refs).
* ``identity``: the run identity (``runner.prepare``): ``through_week``,
  ``active_week``, ``as_of``, ``next_week_mode``, ``code_sha``, ``config_sha`` plus
  ``predictions_sha256`` (the ``output_refs["predictions"]["sha256"]`` of the run)
  and optionally ``model_bundle_sha256`` (defaults to the accepted bridge bytes).
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import Any

import pandas as pd

from cks_picks_cfb.features.regimes import upcoming_game_regime
from cks_picks_cfb.season.grading import normalize_quotes
from cks_picks_cfb.season.manifest import utc
from cks_picks_cfb.season.projection_common import (
    MARKET_POLICY_VERSION,
    SELECTION_POLICY_VERSION,
    benchmark_grading_version,
    clean_rows,
    quantize4,
    weekly_run_id,
)

SERVING_KEYS = (
    "games",
    "game_results",
    "predictions",
    "prediction_grades",
    "market_quotes",
    "market_snapshots",
    "market_snapshot_quotes",
    "prediction_market_selections",
    "system_stats",
    "site_week_selections",
    "prediction_runs",
)

MODEL_ID = "v5-intended-update-2026-v1"
SYSTEM_NAME = "Trench Warfare V5 Intended Update"
SOURCE_CONFIG = "conf/weekly_bets/v5_intended_update_2026.yaml"
# The only bridge bytes ``manifest.validate_model`` accepts.
BRIDGE_SHA256 = "a507d0c7cba5419868eac5c0955853d3e2855fc857aabf36f5cd192d5e7a90f1"
SELECTION_REASON = "season release: fixed-model season run"

# Exact ``season_release_<table>`` columns (0025 migration) minus server columns.
COLUMNS: dict[str, tuple[str, ...]] = {
    "games": (
        "game_id", "season", "week", "start_date", "home_team", "away_team",
        "home_team_spread_line", "total_line", "predicted_spread", "predicted_total",
        "predicted_spread_std_dev", "predicted_total_std_dev", "spread_lean",
        "total_lean", "edge_spread", "edge_total", "high_confidence",
        "source_config", "system_name", "model_id", "inserted_at", "updated_at",
    ),
    "game_results": (
        "completion_state", "source_dataset_version_id", "game_id", "home_points",
        "away_points", "spread_result", "total_result", "scored_at",
    ),
    "predictions": (
        "market_snapshot_id", "run_id", "game_id", "home_team_spread_line",
        "total_line", "predicted_spread", "predicted_total",
        "predicted_spread_std_dev", "predicted_total_std_dev", "spread_lean",
        "total_lean", "edge_spread", "edge_total", "high_confidence",
        "high_confidence_eligible", "home_completed_games", "away_completed_games",
        "regime", "spread_model_version", "total_model_version", "created_at",
    ),
    "prediction_grades": (
        "run_id", "game_id", "target", "market_snapshot_id", "market_quote_id",
        "side", "result", "profit_units", "grading_version", "graded_at",
    ),
    "market_quotes": (
        "quote_id", "game_id", "provider", "captured_at", "spread", "total",
        "source_capture_id", "home_spread_price", "away_spread_price", "over_price",
        "under_price", "quote_updated_at", "source_event_id",
    ),
    "market_snapshots": (
        "snapshot_id", "game_id", "captured_at", "spread", "total", "spread_rule",
        "total_rule", "spread_provider_count", "total_provider_count",
        "source_quote_ids", "policy_version", "created_at",
    ),
    "market_snapshot_quotes": ("snapshot_id", "quote_id", "target"),
    "prediction_market_selections": (
        "run_id", "game_id", "target", "snapshot_id", "quote_id", "side", "point",
        "price", "edge", "policy_version", "created_at",
    ),
    "system_stats": (
        "season", "as_of_week", "spread_wins", "spread_losses", "spread_pushes",
        "total_wins", "total_losses", "total_pushes", "spread_profit_units",
        "total_profit_units", "updated_at",
    ),
    "site_week_selections": ("season", "week", "run_id", "selected_at", "reason"),
    "prediction_runs": (
        "run_id", "season", "week", "state", "expected_games", "predicted_games",
        "lined_games", "data_as_of", "source_config", "system_name", "model_id",
        "code_sha", "config_sha", "model_bundle_sha256", "rating_manifest_sha256",
        "artifact_uri", "artifact_sha256", "input_dataset_refs", "validation",
        "created_at", "published_at", "frozen_at", "scored_at", "evidence_class",
    ),
}  # fmt: skip
KEYS: dict[str, tuple[str, ...]] = {
    "games": ("game_id",),
    "game_results": ("game_id",),
    "predictions": ("run_id", "game_id"),
    "prediction_grades": ("run_id", "game_id", "target"),
    "market_quotes": ("quote_id",),
    "market_snapshots": ("snapshot_id",),
    "market_snapshot_quotes": ("snapshot_id", "quote_id", "target"),
    "prediction_market_selections": ("run_id", "game_id", "target"),
    "system_stats": ("season",),
    "site_week_selections": ("season", "week"),
    "prediction_runs": ("run_id",),
}
_QUOTE_FIELDS = (
    "home_spread_price",
    "away_spread_price",
    "over_price",
    "under_price",
    "source_event_id",
)


def _present(value: Any) -> bool:
    if isinstance(value, float):
        return not math.isnan(value)
    return value is not None and value is not pd.NA and value is not pd.NaT


def _table(name: str, records: Iterable[dict]) -> list[dict]:
    key = KEYS[name]
    ordered = sorted(records, key=lambda row: tuple(row[k] for k in key))
    if len({tuple(row[k] for k in key) for row in ordered}) != len(ordered):
        raise ValueError(f"duplicate {name} key")
    frame = pd.DataFrame(ordered, columns=list(COLUMNS[name]), dtype=object)
    return clean_rows(frame, COLUMNS[name])


def _edge(target: str, prediction: float, point: float) -> float:
    return abs(prediction + point) if target == "spread" else abs(prediction - point)


def _season_run_id(predictions: pd.DataFrame) -> str:
    run_ids = set(predictions.run_id.astype(str))
    if len(run_ids) != 1:
        raise ValueError("predictions must come from exactly one season run")
    return run_ids.pop()


def _forecasts(predictions: pd.DataFrame) -> dict[int, dict]:
    """One record per predicted game with paired margin/total forecasts."""
    games: dict[int, dict] = {}
    for row in predictions.itertuples(index=False):
        game = games.setdefault(
            int(row.game_id),
            {"week": int(row.week), "stage": int(row.completed_game_stage)},
        )
        if game["week"] != int(row.week) or row.target in game:
            raise ValueError(f"duplicate forecast for game {row.game_id}")
        game[row.target] = (float(row.mean), math.sqrt(float(row.variance)))
    if any(
        set(game) != {"week", "stage", "margin", "total"} for game in games.values()
    ):
        raise ValueError("every forecast requires a margin and total pair")
    return games


def _selections(grades: pd.DataFrame) -> dict[tuple[int, str], dict]:
    """Selected quotes by (game, target), with lowercase settlement results."""
    selected = {}
    for row in grades.to_dict("records"):
        if not _present(row["side"]):
            continue
        result = row["result"]
        selected[(int(row["game_id"]), str(row["target"]))] = {
            **row,
            "result": str(result).lower() if _present(result) else None,
            "linked": json.loads(row["source_quote_ids"]),
        }
    return selected


def _completed_counts(schedule: pd.DataFrame, game: Any) -> tuple[int, int]:
    """Earlier-week completed games per side, as ``live`` counts them."""
    earlier = schedule[
        schedule.week.lt(game.week) & schedule.kickoff_utc.lt(game.kickoff_utc)
    ]
    return tuple(
        int((earlier.home_team.eq(team) | earlier.away_team.eq(team)).sum())
        for team in (game.home_team, game.away_team)
    )


def _quote_records(inputs: Any, wanted: set[str]) -> list[dict]:
    """Merge the per-target market rows of each wanted quote into one quote row."""
    tables = [
        normalize_quotes(table)
        for table in (inputs.quotes, inputs.historical_lines)
        if not table.empty
    ]
    rows = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    records = []
    for quote_id in sorted(wanted):
        group = (
            rows[rows.quote_id.astype(str).eq(quote_id)].to_dict("records")
            if not rows.empty
            else []
        )
        if not group:
            raise ValueError(f"selected/linked quote {quote_id} is absent from inputs")
        identity = {
            (int(r["game_id"]), str(r["provider"]), utc(r["captured_at"]))
            for r in group
        }
        points = {(r["target"], float(r["point"])) for r in group}
        if len(identity) != 1 or len(points) != len({t for t, _ in points}):
            raise ValueError(f"quote {quote_id} has conflicting definitions")
        game_id, provider, captured_at = identity.pop()
        by_target = dict(points)

        def first(*names: str, rows: list[dict] = group) -> Any:
            values = [r.get(n) for r in rows for n in names if _present(r.get(n))]
            return values[0] if values else None

        updated = first("quote_updated_at")
        capture = first("source_capture_id", "__capture_id")
        records.append(
            {
                "quote_id": quote_id,
                "game_id": game_id,
                "provider": provider,
                "captured_at": captured_at,
                "spread": by_target.get("spread"),
                "total": by_target.get("total"),
                "source_capture_id": None if capture is None else str(capture),
                **{name: first(name) for name in _QUOTE_FIELDS},
                "quote_updated_at": None if updated is None else utc(updated),
            }
        )
        if records[-1]["source_event_id"] is not None:
            records[-1]["source_event_id"] = str(records[-1]["source_event_id"])
    return records


def _snapshots(selected: Mapping[tuple[int, str], dict]) -> dict[str, dict]:
    """Projected snapshots; one id may carry both targets of one game."""
    snapshots: dict[str, dict] = {}
    for (game_id, target), choice in selected.items():
        snapshot = snapshots.setdefault(
            str(choice["snapshot_id"]), {"game_id": game_id, "links": {}}
        )
        if snapshot["game_id"] != game_id or target in snapshot["links"]:
            raise ValueError(f"snapshot {choice['snapshot_id']} spans games")
        snapshot["links"][target] = choice["linked"]
        snapshot[target] = float(choice["canonical_line"])
        snapshot[f"{target}_rule"] = choice["snapshot_rule"]
        snapshot[f"{target}_provider_count"] = int(choice["provider_count"])
        captured = utc(choice["snapshot_captured_at"])
        snapshot["captured_at"] = max(snapshot.get("captured_at", captured), captured)
    return snapshots


def build_serving_core(
    *,
    frames: Mapping[str, pd.DataFrame],
    inputs: Any,
    revision: Mapping[str, Any],
    identity: Mapping[str, Any],
    ratings_id: str,
    measurement_id: str,
) -> dict[str, list[dict]]:
    """Return ``{key: rows}`` for exactly :data:`SERVING_KEYS`.

    ``frames`` are the ``prepare.compute`` outputs, ``inputs`` the
    ``inputs.SeasonInputs``, ``revision`` the parsed revision manifest, ``identity``
    the run identity, and ``ratings_id`` / ``measurement_id`` the values of
    ``projection_common.rating_identity`` / ``measurement_identity``. Serving rows
    carry no measurement lineage, so ``measurement_id`` is accepted but unused.
    """
    season_run = _season_run_id(frames["predictions"])
    through_week = int(identity["through_week"])
    active_week = int(identity["active_week"])
    live_week = (
        active_week
        if active_week > through_week and identity["next_week_mode"] == "live"
        else None
    )
    captured = utc(revision["captured_at"])
    weeks = range(active_week + 1)
    run_ids = {week: weekly_run_id(season_run, week) for week in weeks}
    cutoffs = {
        week: utc(
            identity["as_of"]
            if week == live_week
            else revision["pre_week_cutoffs"][str(week)]
        )
        for week in weeks
    }
    model_version = f"v5:{season_run}:{ratings_id[:12]}"

    schedule = inputs.schedule.sort_values("game_id", kind="stable")
    if schedule.game_id.duplicated().any():
        raise ValueError("schedule duplicates a game")
    forecasts = _forecasts(frames["predictions"])
    selected = _selections(frames["grades"])
    schedule_weeks = dict(zip(schedule.game_id.astype(int), schedule.week.astype(int)))
    for game_id, forecast in forecasts.items():
        if (
            schedule_weeks.get(game_id) != forecast["week"]
            or forecast["week"] not in run_ids
        ):
            raise ValueError(f"forecast for game {game_id} is outside the schedule")
    if any(key[0] not in forecasts for key in selected):
        raise ValueError("market selection lacks a forecast")

    games, predictions = [], []
    for game in schedule.itertuples(index=False):
        game_id = int(game.game_id)
        row = {
            "game_id": game_id,
            "season": int(game.season),
            "week": int(game.week),
            "start_date": utc(game.kickoff_utc),
            "home_team": str(getattr(game, "home_team_provider", game.home_team)),
            "away_team": str(getattr(game, "away_team_provider", game.away_team)),
            "high_confidence": False,
            "inserted_at": captured,
            "updated_at": captured,
        }
        forecast = forecasts.get(game_id)
        if forecast is None:
            games.append(row)
            continue
        spread, total = (
            selected.get((game_id, "spread")),
            selected.get((game_id, "total")),
        )
        (margin, margin_sd), (points, points_sd) = forecast["margin"], forecast["total"]
        shared = {
            "home_team_spread_line": spread["point"] if spread else None,
            "total_line": total["point"] if total else None,
            "predicted_spread": margin,
            "predicted_total": points,
            "predicted_spread_std_dev": margin_sd,
            "predicted_total_std_dev": points_sd,
            "spread_lean": spread["side"] if spread else None,
            "total_lean": total["side"] if total else None,
            "edge_spread": _edge("spread", margin, spread["point"]) if spread else None,
            "edge_total": _edge("total", points, total["point"]) if total else None,
            "high_confidence": False,
        }
        games.append(
            {
                **row,
                **shared,
                "source_config": SOURCE_CONFIG,
                "system_name": SYSTEM_NAME,
                "model_id": MODEL_ID,
            }
        )
        home_completed, away_completed = _completed_counts(inputs.schedule, game)
        if min(home_completed, away_completed, 4) != forecast["stage"]:
            raise ValueError(f"completed-game stage differs for game {game_id}")
        predictions.append(
            {
                **shared,
                "market_snapshot_id": (spread or total or {}).get("snapshot_id"),
                "run_id": run_ids[forecast["week"]],
                "game_id": game_id,
                "high_confidence_eligible": False,
                "home_completed_games": home_completed,
                "away_completed_games": away_completed,
                "regime": upcoming_game_regime(forecast["stage"]),
                "spread_model_version": model_version,
                "total_model_version": model_version,
                "created_at": cutoffs[forecast["week"]],
            }
        )

    selections, grades = [], []
    for (game_id, target), choice in selected.items():
        week = forecasts[game_id]["week"]
        mean = forecasts[game_id]["margin" if target == "spread" else "total"][0]
        common = {"run_id": run_ids[week], "game_id": game_id, "target": target}
        selections.append(
            {
                **common,
                "snapshot_id": str(choice["snapshot_id"]),
                "quote_id": str(choice["quote_id"]),
                "side": choice["side"],
                "point": float(choice["point"]),
                "price": float(choice["price"]),
                "edge": _edge(target, mean, float(choice["point"])),
                "policy_version": SELECTION_POLICY_VERSION,
                "created_at": cutoffs[week],
            }
        )
        if choice["result"] is not None:
            grades.append(
                {
                    **common,
                    "week": week,
                    "market_snapshot_id": str(choice["snapshot_id"]),
                    "market_quote_id": str(choice["quote_id"]),
                    "side": choice["side"],
                    "result": choice["result"],
                    "profit_units": quantize4(choice["units"]),
                    "grading_version": benchmark_grading_version(
                        choice["benchmark_type"]
                    ),
                    "graded_at": captured,
                }
            )

    snapshots = _snapshots(selected)
    snapshot_rows = [
        {
            "snapshot_id": snapshot_id,
            "game_id": snapshot["game_id"],
            "captured_at": snapshot["captured_at"],
            "spread": snapshot.get("spread"),
            "total": snapshot.get("total"),
            "spread_rule": snapshot.get("spread_rule"),
            "total_rule": snapshot.get("total_rule"),
            "spread_provider_count": snapshot.get("spread_provider_count", 0),
            "total_provider_count": snapshot.get("total_provider_count", 0),
            "source_quote_ids": sorted(
                {q for ids in snapshot["links"].values() for q in ids}
            ),
            "policy_version": MARKET_POLICY_VERSION,
            "created_at": captured,
        }
        for snapshot_id, snapshot in snapshots.items()
    ]
    links = [
        {"snapshot_id": snapshot_id, "quote_id": quote_id, "target": target}
        for snapshot_id, snapshot in snapshots.items()
        for target, quote_ids in snapshot["links"].items()
        for quote_id in quote_ids
    ]
    wanted = {row["quote_id"] for row in links} | {
        row["quote_id"] for row in selections
    }
    quotes = _quote_records(inputs, wanted)
    quote_games = {row["quote_id"]: row["game_id"] for row in quotes}
    if any(quote_games[row["quote_id"]] != row["game_id"] for row in selections) or any(
        quote_games[row["quote_id"]] != snapshots[row["snapshot_id"]]["game_id"]
        for row in links
    ):
        raise ValueError("market quote belongs to another game")

    results = {(row["game_id"], row["target"]): row["result"] for row in grades}
    finals_version = f"finals:{revision['inputs']['finals']['sha256'][:16]}"
    game_results = [
        {
            "completion_state": "completed",
            "source_dataset_version_id": finals_version,
            "game_id": int(row.game_id),
            "home_points": int(row.home_points),
            "away_points": int(row.away_points),
            "spread_result": results.get((int(row.game_id), "spread")),
            "total_result": results.get((int(row.game_id), "total")),
            "scored_at": captured,
        }
        for row in frames["finals"].itertuples(index=False)
    ]

    scored = [row for row in grades if row["week"] <= through_week]
    stats = {
        "season": 2026,
        "as_of_week": max((row["week"] for row in scored), default=0),
        "updated_at": captured,
    }
    for target in ("spread", "total"):
        rows = [row for row in scored if row["target"] == target]
        for result, label in (("win", "wins"), ("loss", "losses"), ("push", "pushes")):
            stats[f"{target}_{label}"] = sum(row["result"] == result for row in rows)
        stats[f"{target}_profit_units"] = quantize4(
            sum((Decimal(str(row["profit_units"])) for row in rows), Decimal(0))
        )

    runs, site = [], []
    refs = [
        {"dataset": name, "uri": ref["uri"], "sha256": ref["sha256"]}
        for name, ref in sorted(revision["inputs"].items())
    ]
    for week in weeks:
        week_games = [g for g in games if g["week"] == week]
        predicted = [g for g in week_games if g["game_id"] in forecasts]
        lined = [
            g
            for g in predicted
            if g["home_team_spread_line"] is not None and g["total_line"] is not None
        ]
        state = "scored" if week <= through_week else "published"
        runs.append(
            {
                "run_id": run_ids[week],
                "season": 2026,
                "week": week,
                "state": state,
                "expected_games": len(week_games),
                "predicted_games": len(predicted),
                "lined_games": len(lined),
                "data_as_of": cutoffs[week],
                "source_config": SOURCE_CONFIG,
                "system_name": SYSTEM_NAME,
                "model_id": MODEL_ID,
                "code_sha": identity["code_sha"],
                "config_sha": identity["config_sha"],
                "model_bundle_sha256": identity.get(
                    "model_bundle_sha256", BRIDGE_SHA256
                ),
                "rating_manifest_sha256": ratings_id,
                "artifact_uri": f"season-run:{season_run}/predictions.parquet",
                "artifact_sha256": identity["predictions_sha256"],
                "input_dataset_refs": refs,
                "validation": {
                    "all_predictions_present": len(predicted) == len(week_games),
                    "line_coverage_complete": len(lined) == len(predicted),
                },
                "created_at": cutoffs[week],
                "published_at": cutoffs[week],
                "frozen_at": None,
                "scored_at": captured if state == "scored" else None,
                "evidence_class": "pending" if week == live_week else "replay",
            }
        )
        site.append(
            {
                "season": 2026,
                "week": week,
                "run_id": run_ids[week],
                "selected_at": cutoffs[week],
                "reason": SELECTION_REASON,
            }
        )

    return {
        "games": _table("games", games),
        "game_results": _table("game_results", game_results),
        "predictions": _table("predictions", predictions),
        "prediction_grades": _table("prediction_grades", grades),
        "market_quotes": _table("market_quotes", quotes),
        "market_snapshots": _table("market_snapshots", snapshot_rows),
        "market_snapshot_quotes": _table("market_snapshot_quotes", links),
        "prediction_market_selections": _table(
            "prediction_market_selections", selections
        ),
        "system_stats": _table("system_stats", [stats]),
        "site_week_selections": _table("site_week_selections", site),
        "prediction_runs": _table("prediction_runs", runs),
    }
