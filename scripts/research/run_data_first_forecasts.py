#!/usr/bin/env python3
"""Read-only V5-04A forecast-offset, bridge, and horizon preflight.

This runner is deliberately incapable of publishing.  V5-04B owns calibration,
immutable child writes, candidate manifests, and independent verification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_forecast_v1 import (
    FORECAST_DATASETS,
    FORECAST_MODEL_COLUMNS,
    FORECAST_PREDICTION_COLUMNS,
    FORECAST_REGISTRY_COLUMNS,
    FORECAST_SELECTION_COLUMNS,
    REQUIRED_RATING_CANDIDATE,
    WINDOW_COMPARISON_COLUMNS,
    forecast_identity,
    validate_config,
    verify_rating_parent,
)
from cks_picks_cfb.data.data_first_possession_rating_v1 import TEAM_STATE_COLUMNS
from cks_picks_cfb.data.lake import (
    canonical_frame_digest,
    partition_order_key,
    partitioned_records_sha,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.heads import evaluate_heads
from cks_picks_cfb.forecast.horizons import select_horizon
from cks_picks_cfb.forecast.offsets import build_offsets
from cks_picks_cfb.ratings.possession_rating_materializer import (
    _concat_frames,
    _manifest_parts,
    _partitioned_ref,
    _read_child,
    _stream_output,
    load_rating_inputs,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/forecast_v1.yaml"


class ForecastRunError(ValueError):
    """Raised before a V5-04A preflight could produce reviewable evidence."""


class _Progress:
    """Bounded, secret-safe stderr progress heartbeat for long phases.

    Mirrors the proven ratings-runner pattern: a daemon heartbeat thread, an
    interval cap on routine events, forced emission for phase boundaries, and
    a blocked-keyword filter so credentials can never reach stderr.  Stdout
    stays pure JSON evidence.
    """

    _FORCED_EVENTS = frozenset(
        {
            "preflight_started",
            "parents_loaded",
            "offsets_built",
            "horizon_started",
            "horizon_complete",
            "horizon_selected",
            "evidence_constructed",
            "dry_run_complete",
        }
    )
    _BLOCKED_MARKERS = ("credential", "password", "secret", "token", "access_key")

    def __init__(self, run_id: str, interval_seconds: float = 30.0) -> None:
        self.run_id = run_id
        self.interval_seconds = interval_seconds
        self.started = time.monotonic()
        self.last = float("-inf")
        self.phase = "initializing"
        self.fields: dict[str, Any] = {}
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread: threading.Thread | None = None

    @classmethod
    def _safe(cls, fields: Mapping[str, Any]) -> dict[str, Any]:
        return {
            str(key): value
            for key, value in fields.items()
            if not any(marker in str(key).casefold() for marker in cls._BLOCKED_MARKERS)
        }

    def emit(self, event: str, /, **fields: Any) -> None:
        now = time.monotonic()
        force = bool(fields.pop("force", False)) or event in self._FORCED_EVENTS
        safe = self._safe(fields)
        with self.lock:
            self.phase = str(safe.pop("phase", event))
            self.fields = safe
            if not force and now - self.last < self.interval_seconds:
                return
            self.last = now
            self._write(event, self.phase, safe, now)

    def _write(
        self, event: str, phase: str, fields: Mapping[str, Any], now: float
    ) -> None:
        print(
            json.dumps(
                {
                    "event": event,
                    "phase": phase,
                    "run_id": self.run_id,
                    "elapsed_seconds": round(now - self.started, 3),
                    **fields,
                },
                sort_keys=True,
                default=str,
            ),
            file=sys.stderr,
            flush=True,
        )

    def start(self) -> None:
        def heartbeat() -> None:
            while not self.stop.wait(self.interval_seconds):
                with self.lock:
                    now = time.monotonic()
                    self._write("heartbeat", self.phase, self.fields, now)
                    self.last = now

        self.thread = threading.Thread(
            target=heartbeat,
            name=f"forecast-progress-{self.run_id}",
            daemon=True,
        )
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=1.0)


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _read_json(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:
        raise ForecastRunError(f"unreadable manifest: {uri}") from exc


def _stream_partitioned(
    storage: Any,
    *,
    value: Mapping[str, Any],
    dataset: str,
    schema: str,
    columns: list[str],
) -> pd.DataFrame:
    ref = _partitioned_ref(value, name=dataset)
    if ref.dataset != dataset or ref.schema_version != schema:
        raise ForecastRunError(f"retained rating output identity mismatch: {dataset}")
    _, parts = _manifest_parts(storage, ref)
    frames = [
        _read_child(storage, dataset=dataset, schema_version=schema, part=part)
        for part in parts
    ]
    return _concat_frames(frames, columns=columns) if frames else pd.DataFrame()


def _pregame_completed_counts(games: pd.DataFrame) -> pd.DataFrame:
    """Per-team pregame counts of earlier completed eligible games in-season.

    ``possession_rating_state.completed_games`` counts assimilated
    observations (boundary cutoffs), not completed-game regimes; the regime
    stage must come from the eligible completed schedule itself, ordered by
    ``(kickoff_utc, game_id)`` with the current game excluded.
    """
    rows: list[dict[str, object]] = []
    ordered = games.sort_values(["season", "kickoff_utc", "game_id"], kind="mergesort")
    for season, season_games in ordered.groupby("season", sort=True):
        counts: dict[str, int] = {}
        for row in season_games.itertuples(index=False):
            home, away = str(row.home_team), str(row.away_team)
            for team in (home, away):
                rows.append(
                    {
                        "season": int(season),
                        "game_id": int(row.game_id),
                        "team": team,
                        "completed_games": counts.get(team, 0),
                    }
                )
            counts[home] = counts.get(home, 0) + 1
            counts[away] = counts.get(away, 0) + 1
    frame = pd.DataFrame.from_records(rows)
    if frame.duplicated(subset=["season", "game_id", "team"]).any():
        raise ForecastRunError("pregame completed counts are not unique per team-game")
    return frame


def _feature_frame(
    *,
    population: pd.DataFrame,
    outcomes: pd.DataFrame,
    team_states: pd.DataFrame,
    offsets: pd.DataFrame,
) -> pd.DataFrame:
    games = population[population["forecast_eligible"].astype(bool)].merge(
        outcomes[outcomes["completed"].astype(bool)],
        on=["season", "game_id"],
        how="inner",
        validate="one_to_one",
    )
    selected = team_states[
        team_states["candidate_id"].eq(REQUIRED_RATING_CANDIDATE)
    ].copy()
    home = selected.rename(
        columns={
            "team": "home_team",
            "offense_rating": "home_offense",
            "defense_rating": "home_defense",
        }
    )
    away = selected.rename(
        columns={
            "team": "away_team",
            "offense_rating": "away_offense",
            "defense_rating": "away_defense",
        }
    )
    counts = _pregame_completed_counts(games)
    home_counts = counts.rename(
        columns={"team": "home_team", "completed_games": "home_completed"}
    )
    away_counts = counts.rename(
        columns={"team": "away_team", "completed_games": "away_completed"}
    )
    frame = games.merge(
        home[
            [
                "season",
                "game_id",
                "home_team",
                "home_offense",
                "home_defense",
            ]
        ],
        on=["season", "game_id", "home_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        away[
            [
                "season",
                "game_id",
                "away_team",
                "away_offense",
                "away_defense",
            ]
        ],
        on=["season", "game_id", "away_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        home_counts[["season", "game_id", "home_team", "home_completed"]],
        on=["season", "game_id", "home_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        away_counts[["season", "game_id", "away_team", "away_completed"]],
        on=["season", "game_id", "away_team"],
        how="inner",
        validate="one_to_one",
    )
    frame = frame.merge(
        offsets, on=["season", "week", "game_id"], how="inner", validate="one_to_one"
    )
    frame["home_host"] = 1.0
    frame["venue_unknown"] = True
    frame["actual_margin"] = frame["home_points"].astype(float) - frame[
        "away_points"
    ].astype(float)
    frame["actual_total"] = frame["home_points"].astype(float) + frame[
        "away_points"
    ].astype(float)
    frame["completed_game_stage"] = (
        frame[["home_completed", "away_completed"]]
        .min(axis=1)
        .clip(upper=4)
        .astype(int)
    )
    return frame


def _plan(
    name: str,
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    partition_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Record deterministic compact or bounded partition membership without writes."""
    if not partition_keys:
        return {
            "name": name,
            "partition_keys": [],
            "parts": [],
            "row_count": len(frame),
            "records_sha": canonical_frame_digest(frame, columns=columns),
        }
    parts: list[dict[str, Any]] = []
    for values, group in frame.groupby(list(partition_keys), sort=True, dropna=False):
        values = values if isinstance(values, tuple) else (values,)
        partition = {
            key: value.item() if hasattr(value, "item") else value
            for key, value in zip(partition_keys, values, strict=True)
        }
        parts.append(
            {
                "partition": partition,
                "row_count": len(group),
                "records_sha": canonical_frame_digest(group, columns=columns),
            }
        )
    parts.sort(key=lambda item: partition_order_key(item["partition"]))
    return {
        "name": name,
        "partition_keys": list(partition_keys),
        "parts": parts,
        "row_count": len(frame),
        "records_sha": partitioned_records_sha(parts, partition_keys),
    }


def _retained_rows(frame: pd.DataFrame, *, target: str, head: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame[frame["target"].eq(target) & frame["head"].eq(head)]


def _slice_metrics(frame: pd.DataFrame, key: str) -> dict[str, dict[str, float]]:
    slices: dict[str, dict[str, float]] = {}
    if frame.empty:
        return slices
    for value, group in frame.groupby(key, sort=True):
        slices[str(int(value))] = {
            "mae": float(group["absolute_error"].mean()),
            "gaussian_crps": float(group["gaussian_crps"].mean()),
            "n": int(len(group)),
        }
    return slices


def _head_metrics_block(computations: Mapping[str, Any]) -> dict[str, Any]:
    """Build the expanded, deterministic per-horizon/per-target metric block."""
    block: dict[str, Any] = {}
    for horizon, computation in computations.items():
        block[horizon] = {}
        for target, head in computation.retained.items():
            selection = _retained_rows(
                computation.predictions, target=target, head=head
            )
            reporting = _retained_rows(
                computation.reporting_predictions, target=target, head=head
            )
            block[horizon][target] = {
                "head": head,
                "selection": {
                    "pooled": {
                        "mae": float(selection["absolute_error"].mean()),
                        "gaussian_crps": float(selection["gaussian_crps"].mean()),
                        "n": int(len(selection)),
                    },
                    "by_season": _slice_metrics(selection, "season"),
                    "by_completed_game_stage": _slice_metrics(
                        selection, "completed_game_stage"
                    ),
                },
                "reporting": {
                    "by_season": _slice_metrics(reporting, "season"),
                },
            }
    return block


def _horizon_populations(computations: Mapping[str, Any]) -> dict[str, Any]:
    """Per-horizon retained-head selection row counts for population equality."""
    return {
        horizon: {
            target: int(
                len(_retained_rows(computation.predictions, target=target, head=head))
            )
            for target, head in computation.retained.items()
        }
        for horizon, computation in computations.items()
    }


def preflight(
    *, storage: Any, args: argparse.Namespace, progress: _Progress
) -> dict[str, Any]:
    progress.emit("preflight_started", run_id=args.run_id, as_of=args.as_of)
    config = yaml.safe_load(Path(args.config).read_text())
    validate_config(config)
    selection = config["selection"]
    rating, rating_raw = _read_json(storage, args.rating_manifest_uri)
    measurement, measurement_raw = _read_json(storage, args.measurement_manifest_uri)
    repair, repair_raw = _read_json(storage, args.repair_manifest_uri)
    parents = verify_rating_parent(
        rating,
        rating_manifest_uri=args.rating_manifest_uri,
        rating_raw_sha256=hashlib.sha256(rating_raw).hexdigest(),
        measurement=measurement,
        measurement_manifest_uri=args.measurement_manifest_uri,
        measurement_raw_sha256=hashlib.sha256(measurement_raw).hexdigest(),
        repair=repair,
        repair_manifest_uri=args.repair_manifest_uri,
        repair_raw_sha256=hashlib.sha256(repair_raw).hexdigest(),
    )
    identity = forecast_identity(
        run_id=args.run_id,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
        config_sha=hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        parents={
            "rating_manifest_uri": parents["rating_manifest_uri"],
            "rating_raw_sha256": parents["rating_raw_sha256"],
            "measurement_manifest_uri": parents["measurement_manifest_uri"],
            "measurement_raw_sha256": parents["measurement_raw_sha256"],
            "repair_manifest_uri": parents["repair_manifest_uri"],
            "repair_raw_sha256": parents["repair_raw_sha256"],
        },
    )
    progress.emit(
        "parents_loaded",
        rating_parent=rating["identity"]["run_id"],
        measurement_parent=measurement["identity"]["run_id"],
        repair_parent=repair["identity"]["run_id"],
    )
    # Reuse 03's audited source loading.  It validates bounded parent parts and
    # chronology before any forecast feature is formed.
    rating_inputs = load_rating_inputs(
        storage=storage,
        measurement=measurement,
        repair=repair,
        progress=progress.emit,
    )
    progress.emit("source_streamed", source="rating_inputs")
    scoring_events = _stream_output(
        storage,
        name="scoring_events",
        value=measurement["output_refs"]["scoring_events"],
        progress=progress.emit,
    )
    progress.emit("source_streamed", source="scoring_events", rows=len(scoring_events))
    team_states = _stream_partitioned(
        storage,
        value=rating["output_refs"]["team_states"],
        dataset="possession_team_state",
        schema="data_first_possession_team_state_v1",
        columns=list(TEAM_STATE_COLUMNS),
    )
    progress.emit("source_streamed", source="team_states", rows=len(team_states))
    offsets = build_offsets(
        rating_inputs.population,
        scoring_events,
        development_seasons=tuple(config["development_seasons"]),
        equivalent_games=int(config["offsets"]["equivalent_games"]),
    )
    progress.emit("offsets_built", rows=len(offsets.offsets))
    features = _feature_frame(
        population=rating_inputs.population,
        outcomes=rating_inputs.outcomes,
        team_states=team_states,
        offsets=offsets.offsets,
    )
    bridge = config["bridge"]
    computations: dict[str, Any] = {}
    for horizon in config["horizons"]:
        progress.emit("horizon_started", horizon=horizon)
        computations[horizon] = evaluate_heads(
            features,
            horizon=horizon,
            development_seasons=tuple(config["development_seasons"]),
            outer_seasons=tuple(selection["outer_seasons"]),
            reporting_seasons=tuple(selection["reporting_seasons"]),
            alpha_grid=tuple(bridge["alpha_grid"]),
            floor=float(bridge["scaling_floor"]),
            bootstrap_seed=int(selection["bootstrap_seed"]),
            bootstrap_samples=int(selection["bootstrap_replicates"]),
        )
        progress.emit("horizon_complete", horizon=horizon)
    retained = {
        horizon: computation.predictions.merge(
            pd.DataFrame(
                [
                    {"target": target, "head": head}
                    for target, head in computation.retained.items()
                ]
            ),
            on=["target", "head"],
            how="inner",
            validate="many_to_one",
        )
        for horizon, computation in computations.items()
    }
    selected_horizon, comparison = select_horizon(
        retained["expanding"],
        retained["latest_five"],
        seed=int(selection["bootstrap_seed"]),
        samples=int(selection["bootstrap_replicates"]),
    )
    progress.emit("horizon_selected", selected_horizon=selected_horizon)
    predictions = retained[selected_horizon].copy()
    models = computations[selected_horizon].models.copy()
    registry = pd.DataFrame.from_records(
        [
            {
                "horizon": horizon,
                "target": target,
                "reference_alpha": 10.0,
                "alpha_grid": ",".join(map(str, bridge["alpha_grid"])),
            }
            for horizon in config["horizons"]
            for target in ("margin", "total")
        ]
    )
    horizon_sha = hashlib.sha256(
        comparison.to_json(
            orient="records", date_format="iso", double_precision=15
        ).encode()
    ).hexdigest()
    selection_frame = pd.DataFrame.from_records(
        [
            {
                "selected_horizon": selected_horizon,
                "target": target,
                "selected_head": computations[selected_horizon].retained[target],
                "selection_reason": "latest_five_gates_passed"
                if selected_horizon == "latest_five"
                else "retain_expanding",
                "horizon_sha256": horizon_sha,
            }
            for target in ("margin", "total")
        ]
    )
    outputs = {
        "forecast_registry": (registry, FORECAST_REGISTRY_COLUMNS, ()),
        "forecast_model": (
            models,
            FORECAST_MODEL_COLUMNS,
            ("horizon", "outer_season"),
        ),
        "forecast_prediction": (
            predictions,
            FORECAST_PREDICTION_COLUMNS,
            ("season", "week"),
        ),
        "window_comparison": (comparison, WINDOW_COMPARISON_COLUMNS, ()),
        "forecast_selection": (selection_frame, FORECAST_SELECTION_COLUMNS, ()),
    }
    for name, (frame, _columns, _keys) in outputs.items():
        dataset, schema = FORECAST_DATASETS[name]
        validate_frame(frame, schema_for(dataset, schema))
    plans = {
        name: _plan(name, frame, columns, keys)
        for name, (frame, columns, keys) in outputs.items()
    }
    evidence = {
        "state": "dry_run",
        "identity": identity,
        "parent_uris": {
            "rating_manifest_uri": parents["rating_manifest_uri"],
            "measurement_manifest_uri": parents["measurement_manifest_uri"],
            "repair_manifest_uri": parents["repair_manifest_uri"],
        },
        "rating_parent": rating["identity"]["run_id"],
        "measurement_parent": measurement["identity"]["run_id"],
        "repair_parent": repair["identity"]["run_id"],
        "selection_seasons": list(selection["outer_seasons"]),
        "reporting_seasons": list(selection["reporting_seasons"]),
        "offsets_sha256": canonical_frame_digest(
            offsets.offsets, columns=tuple(offsets.offsets.columns)
        ),
        "head_metrics": _head_metrics_block(computations),
        "horizon_populations": _horizon_populations(computations),
        "selected_horizon": selected_horizon,
        "horizon_sha256": horizon_sha,
        "preflight_plans": plans,
        "row_counts": {name: value["row_count"] for name, value in plans.items()},
        "output_records_sha256": {
            name: value["records_sha"] for name, value in plans.items()
        },
        "calibration": {"state": "deferred_to_v5_04b"},
        "production_activation_authorized": False,
    }
    progress.emit("evidence_constructed")
    return evidence


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--v4-benchmark-manifest-uri")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    if args.apply:
        raise ForecastRunError("--apply is blocked by V5-04B")
    if _git_sha() != args.expected_code_sha:
        raise ForecastRunError("expected code SHA does not match committed HEAD")
    progress = _Progress(args.run_id)
    progress.start()
    try:
        evidence = preflight(
            storage=get_storage(environment="preview"), args=args, progress=progress
        )
        print(
            json.dumps(
                evidence,
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        progress.emit(
            "dry_run_complete", identity=evidence["identity"]["identity_sha256"]
        )
    finally:
        progress.close()


if __name__ == "__main__":
    main()
