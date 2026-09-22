#!/usr/bin/env python3
"""V5-05A shadow readiness validation and frozen replay runner.

Dry run validates authentic source availability for one prospective slate and
proves frozen-algorithm replay, emitting deterministic evidence including the
readiness plan. The evidence-bound apply path publishes the immutable
readiness record with the terminal shadow manifest written last.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv

from cks_picks_cfb.data.data_first_forecast_v1 import REQUIRED_RATING_CANDIDATE
from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    LIVE_FORECAST_MANIFEST_SCHEMA,
    validate_prediction_frame,
)
from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_possession_rating_v1 import (
    PRIOR_COLUMNS,
    TEAM_STATE_COLUMNS,
)
from cks_picks_cfb.data.data_first_shadow_v1 import (
    READINESS_COLUMNS,
    SHADOW_DATASETS,
    SHADOW_MANIFEST_NAME,
    SHADOW_MANIFEST_SCHEMA,
    SHADOW_OUTPUT_ROOT,
    shadow_identity,
    shadow_manifest,
    validate_shadow_config,
    verify_candidate_parents,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    PartitionedDatasetRef,
    canonical_frame_digest,
    read_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.offsets import build_offsets
from cks_picks_cfb.forecast.shadow import (
    SourceStatus,
    _timing,
    perturbation_invariance_proof,
    replay_frozen_forecast,
)
from cks_picks_cfb.ratings.possession_rating_materializer import (
    _concat_frames,
    _manifest_parts,
    _partitioned_ref,
    _read_child,
    _stream_output,
    load_rating_inputs,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/shadow_v1.yaml"

REPLAY_SEASONS = (2024, 2025)
REPLAY_CUTOFF_SEASON = 2025
REPLAY_ALPHA_GRID = (0.1, 1.0, 10.0, 100.0)
REPLAY_FLOOR = 0.05
REPLAY_BOOTSTRAP_SEED = 20260908
REPLAY_BOOTSTRAP_SAMPLES = 2000


class ShadowRunError(ValueError):
    """Raised before a V5-05A run can produce reviewable evidence."""


class _Progress:
    """Bounded, secret-safe stderr progress heartbeat for long phases.

    Mirrors the proven forecast-runner pattern: a daemon heartbeat thread, an
    interval cap on routine events, forced emission for phase boundaries, and
    a blocked-keyword filter so credentials can never reach stderr. Stdout
    stays pure JSON evidence.
    """

    _FORCED_EVENTS = frozenset(
        {
            "preflight_started",
            "parents_loaded",
            "sources_streamed",
            "readiness_built",
            "replay_started",
            "replay_complete",
            "evidence_constructed",
            "dry_run_complete",
            "apply_started",
            "apply_complete",
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
            name=f"shadow-readiness-progress-{self.run_id}",
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


def _clean_worktree() -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, text=True
    ).strip()


def _utc(value: str) -> datetime:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        raise ShadowRunError("--as-of must be timezone-aware")
    return parsed.to_pydatetime().astimezone(timezone.utc)


def _immutable_json(storage: object, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise ShadowRunError(f"immutable object collision at {uri}")
        return
    storage.write_bytes(encoded, uri)


def _read_json(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:
        raise ShadowRunError(f"unreadable manifest: {uri}") from exc


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
        raise ShadowRunError(f"certified parent output identity mismatch: {dataset}")
    _, parts = _manifest_parts(storage, ref)
    frames = [
        _read_child(storage, dataset=dataset, schema_version=schema, part=part)
        for part in parts
    ]
    return _concat_frames(frames, columns=columns) if frames else pd.DataFrame()


def _pregame_completed_counts(games: pd.DataFrame) -> pd.DataFrame:
    """Per-team pregame counts of earlier completed eligible games in-season.

    Mirrors the 04A runner merge for replay purposes only: regime stages come
    from the kickoff-ordered eligible completed schedule, never from rating
    exposure counters.
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
        raise ShadowRunError("pregame completed counts are not unique per team-game")
    return frame


def _assemble_feature_frame(
    *,
    population: pd.DataFrame,
    outcomes: pd.DataFrame,
    team_states: pd.DataFrame,
    offsets: pd.DataFrame,
) -> pd.DataFrame:
    """Assemble the frozen-bridge feature frame for replay.

    Mirrors the 04A runner merge for replay purposes only: inner joins on
    exact schedule keys, retained-candidate team states, pregame regime
    stages, and pregame non-offense offsets.
    """
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
    """Record deterministic compact membership without writes (05A: compact only)."""
    if partition_keys:
        raise ShadowRunError("05A plans only the compact readiness dataset")
    return {
        "name": name,
        "partition_keys": [],
        "parts": [],
        "row_count": len(frame),
        "records_sha": canonical_frame_digest(frame, columns=columns),
    }


class ShadowPreflightEvidence:
    def __init__(
        self,
        plan: dict[str, Any],
        overall: str,
        replay_sha: str | None,
    ) -> None:
        self.plan = plan
        self.overall = overall
        self.replay_sha = replay_sha


def _load_shadow_preflight_evidence(
    path: Path, *, identity: Mapping[str, Any]
) -> ShadowPreflightEvidence:
    """Load an exact reviewed dry-run plan without trusting it blindly."""
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise ShadowRunError("preflight evidence is unreadable") from exc
    if payload.get("state") != "dry_run" or payload.get("identity") != dict(identity):
        raise ShadowRunError("preflight evidence identity does not match apply")
    raw_plans = payload.get("preflight_plans")
    if not isinstance(raw_plans, dict) or set(raw_plans) != {"readiness"}:
        raise ShadowRunError("preflight evidence lacks the readiness plan")
    raw = raw_plans.get("readiness")
    dataset, schema_version = SHADOW_DATASETS["readiness"]
    if not isinstance(raw, dict) or (
        raw.get("name") != "readiness"
        or raw.get("partition_keys") != []
        or not isinstance(raw.get("parts"), list)
        or raw.get("parts") != []
    ):
        raise ShadowRunError("preflight evidence has an invalid readiness plan")
    if not isinstance(raw.get("row_count"), int) or raw.get("row_count") <= 0:
        raise ShadowRunError("preflight evidence has an invalid readiness row count")
    if not isinstance(raw.get("records_sha"), str) or len(raw.get("records_sha")) != 64:
        raise ShadowRunError("preflight evidence has an invalid readiness digest")
    if payload.get("row_counts") != {"readiness": raw["row_count"]}:
        raise ShadowRunError("preflight evidence summary does not match its plan")
    if payload.get("output_records_sha256") != {"readiness": raw["records_sha"]}:
        raise ShadowRunError("preflight evidence summary does not match its plan")
    overall = payload.get("readiness_overall")
    if overall not in ("ready", "blocked"):
        raise ShadowRunError("preflight evidence has an unknown readiness verdict")
    replay_sha = payload.get("replay_sha256")
    if replay_sha is not None and (
        not isinstance(replay_sha, str) or len(replay_sha) != 64
    ):
        raise ShadowRunError("preflight evidence has an invalid replay digest")
    _ = schema_for(dataset, schema_version)
    return ShadowPreflightEvidence(
        plan={
            "row_count": int(raw["row_count"]),
            "records_sha": str(raw["records_sha"]),
        },
        overall=str(overall),
        replay_sha=replay_sha,
    )


def _existing_shadow_manifest(
    storage: Any, *, manifest_uri: str, identity: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Validate an existing terminal manifest without replaying its producer."""
    if not storage.exists(manifest_uri):
        return None
    existing = json.loads(storage.read_bytes(manifest_uri))
    from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload

    try:
        verify_signed_payload(existing, label="existing shadow manifest")
    except ValueError as exc:
        raise ShadowRunError(str(exc)) from exc
    if (existing.get("identity") or {}).get("identity_sha256") != identity[
        "identity_sha256"
    ]:
        raise ShadowRunError("shadow run ID already has a different identity")
    outputs = existing.get("output_refs") or {}
    if (
        existing.get("state") != "frozen"
        or existing.get("schema_version") != SHADOW_MANIFEST_SCHEMA
        or existing.get("production_activation_authorized") is not False
        or set(outputs) != {"readiness"}
    ):
        raise ShadowRunError("existing shadow manifest is incomplete")
    dataset, schema_version = SHADOW_DATASETS["readiness"]
    ref = outputs.get("readiness") or {}
    required_ref_fields = {
        "artifact_kind",
        "dataset",
        "version_id",
        "schema_version",
        "content_sha",
        "records_sha",
        "uri",
        "row_count",
    }
    if required_ref_fields - set(ref) or (
        ref.get("dataset") != dataset or ref.get("schema_version") != schema_version
    ):
        raise ShadowRunError("existing readiness output reference is invalid")
    if existing.get("readiness_overall") not in ("ready", "blocked"):
        raise ShadowRunError("existing shadow manifest has an unknown verdict")
    return existing


def _load_parents(
    storage: Any, args: argparse.Namespace, progress: _Progress
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    forecast, forecast_raw = _read_json(storage, args.candidate_manifest_uri)
    rating, rating_raw = _read_json(storage, args.rating_manifest_uri)
    measurement, measurement_raw = _read_json(storage, args.measurement_manifest_uri)
    repair, repair_raw = _read_json(storage, args.repair_manifest_uri)
    bridge = None
    bridge_raw = b""
    if forecast.get("schema_version") == LIVE_FORECAST_MANIFEST_SCHEMA:
        bridge_uri = str((forecast.get("parents") or {}).get("bridge_uri") or "")
        if not bridge_uri:
            raise ShadowRunError("live forecast does not bind its 11C bridge manifest")
        bridge, bridge_raw = _read_json(storage, bridge_uri)
    parents = verify_candidate_parents(
        forecast,
        rating,
        measurement,
        repair,
        forecast_manifest_uri=args.candidate_manifest_uri,
        forecast_raw_sha256=hashlib.sha256(forecast_raw).hexdigest(),
        rating_manifest_uri=args.rating_manifest_uri,
        rating_raw_sha256=hashlib.sha256(rating_raw).hexdigest(),
        measurement_manifest_uri=args.measurement_manifest_uri,
        measurement_raw_sha256=hashlib.sha256(measurement_raw).hexdigest(),
        repair_manifest_uri=args.repair_manifest_uri,
        repair_raw_sha256=hashlib.sha256(repair_raw).hexdigest(),
        bridge=bridge,
        bridge_raw_sha256=hashlib.sha256(bridge_raw).hexdigest() if bridge_raw else "",
    )
    progress.emit(
        "parents_loaded",
        forecast_parent=forecast["identity"]["run_id"],
        rating_parent=rating["identity"]["run_id"],
        measurement_parent=measurement["identity"]["run_id"],
        repair_parent=repair["identity"]["run_id"],
    )
    return parents, forecast, rating


def _load_sources(
    storage: Any,
    parents: Mapping[str, Any],
    rating: Mapping[str, Any],
    progress: _Progress,
) -> dict[str, Any]:
    measurement = parents["measurement"]
    repair = parents["repair"]
    forecast = parents["forecast"]
    if forecast.get("schema_version") == LIVE_FORECAST_MANIFEST_SCHEMA:
        from cks_picks_cfb.forecast.live_sources import load_live_forecast_sources

        live = load_live_forecast_sources(
            storage=storage,
            measurement_uri=parents["measurement_manifest_uri"],
            rating_uri=parents["rating_manifest_uri"],
            schedule_uri=str(
                (forecast.get("parents") or {}).get("schedule_ref_uri", "")
            ),
            bridge_uri=str((forecast.get("parents") or {}).get("bridge_uri", "")),
            as_of=str((forecast.get("identity") or {}).get("as_of", "")),
        )
        population = live["population"]
        outcomes = (
            population[
                population["schedule_completed"].astype(bool)
                & population["outcome_valid"].astype(bool)
            ]
            .loc[:, ["season", "week", "game_id", "schedule_completed"]]
            .rename(columns={"schedule_completed": "completed"})
        )
        priors = _stream_partitioned(
            storage,
            value=rating["output_refs"]["priors"],
            dataset="possession_rating_prior",
            schema="data_first_possession_rating_prior_v1",
            columns=list(PRIOR_COLUMNS),
        )
        progress.emit(
            "sources_streamed",
            scoring_events=len(live["scoring_events"]),
            team_states=len(live["states"]),
            priors=len(priors),
        )
        return {
            "population": population,
            "outcomes": outcomes,
            "scoring_events": live["scoring_events"],
            "team_states": live["states"],
            "priors": priors,
            "historical_features": live["historical_features"],
        }
    rating_inputs = load_rating_inputs(
        storage=storage,
        measurement=measurement,
        repair=repair,
        progress=progress.emit,
    )
    scoring_events = _stream_output(
        storage,
        name="scoring_events",
        value=measurement["output_refs"]["scoring_events"],
        progress=progress.emit,
    )
    team_states = _stream_partitioned(
        storage,
        value=rating["output_refs"]["team_states"],
        dataset="possession_team_state",
        schema="data_first_possession_team_state_v1",
        columns=list(TEAM_STATE_COLUMNS),
    )
    priors = _stream_partitioned(
        storage,
        value=rating["output_refs"]["priors"],
        dataset="possession_rating_prior",
        schema="data_first_possession_rating_prior_v1",
        columns=list(PRIOR_COLUMNS),
    )
    progress.emit(
        "sources_streamed",
        scoring_events=len(scoring_events),
        team_states=len(team_states),
        priors=len(priors),
    )
    return {
        "population": rating_inputs.population,
        "outcomes": rating_inputs.outcomes,
        "scoring_events": scoring_events,
        "team_states": team_states,
        "priors": priors,
    }


def _live_candidate_status(
    *,
    storage: Any,
    forecast: Mapping[str, Any],
    population: pd.DataFrame,
    season: int,
    week: int,
    cutoff: str,
) -> SourceStatus:
    """Require complete outcome-free predictions for the requested live slate."""
    ref = forecast.get("output_ref") or {}
    try:
        part_manifest = json.loads(storage.read_bytes(ref["uri"]))
        stored_ref = PartitionedDatasetRef(
            artifact_kind=ref["artifact_kind"],
            dataset=ref["dataset"],
            version_id=ref["version_id"],
            schema_version=ref["schema_version"],
            content_sha=ref["content_sha"],
            records_sha=part_manifest.get("records_sha", ""),
            uri=ref["uri"],
            row_count=int(ref["row_count"]),
            partition_keys=tuple(
                part_manifest.get("partition_keys") or ("season", "week")
            ),
        )
        predictions = read_dataset(storage, stored_ref)
        validate_prediction_frame(
            predictions, run_id=str(forecast["identity"]["run_id"])
        )
        observed = set(
            predictions.loc[
                predictions["season"].eq(season) & predictions["week"].eq(week),
                ["game_id", "target"],
            ]
            .assign(game_id=lambda value: value["game_id"].astype(int))
            .itertuples(index=False, name=None)
        )
        declared = population[
            population["season"].eq(season) & population["week"].eq(week)
        ]
        if "forecast_eligible" in declared:
            declared = declared[declared["forecast_eligible"].astype(bool)]
        expected = set(declared["game_id"].astype(int))
        if not expected:
            return SourceStatus(
                "candidate",
                "unavailable",
                "missing",
                "",
                f"no schedule rows for {season} week {week}",
            )
        expected_pairs = {
            (game_id, target) for game_id in expected for target in ("margin", "total")
        }
        if observed != expected_pairs:
            missing = sorted(expected_pairs - observed)
            extra = sorted(observed - expected_pairs)
            return SourceStatus(
                "candidate",
                "unavailable",
                "missing",
                "",
                "live forecast population mismatch; "
                f"missing game/target={missing[:5]}, extra game/target={extra[:5]}",
            )
        return SourceStatus(
            "candidate",
            "available",
            _timing(str(forecast["identity"]["as_of"]), cutoff),
            "",
            "",
        )
    except (KeyError, OSError, ValueError, TypeError):
        return SourceStatus(
            "candidate",
            "unavailable",
            "missing",
            "",
            "live forecast output unavailable or invalid",
        )


def preflight(
    *, storage: Any, args: argparse.Namespace, progress: _Progress
) -> dict[str, Any]:
    progress.emit("preflight_started", run_id=args.run_id, as_of=args.as_of)
    config = yaml.safe_load(Path(args.config).read_text())
    validate_shadow_config(config)
    parents, forecast, rating = _load_parents(storage, args, progress)
    measurement_as_of = str(parents["measurement"]["identity"]["as_of"])
    rating_as_of = str(parents["rating"]["identity"]["as_of"])
    identity = shadow_identity(
        run_id=args.run_id,
        as_of=args.as_of,
        code_sha=args.expected_code_sha,
        config_sha=hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
        parents={
            "forecast_manifest_uri": parents["forecast_manifest_uri"],
            "forecast_raw_sha256": parents["forecast_raw_sha256"],
            "rating_manifest_uri": parents["rating_manifest_uri"],
            "rating_raw_sha256": parents["rating_raw_sha256"],
            "measurement_manifest_uri": parents["measurement_manifest_uri"],
            "measurement_raw_sha256": parents["measurement_raw_sha256"],
            "repair_manifest_uri": parents["repair_manifest_uri"],
            "repair_raw_sha256": parents["repair_raw_sha256"],
        },
        candidate=forecast["identity"]["run_id"],
    )
    sources = _load_sources(storage, parents, rating, progress)
    from cks_picks_cfb.forecast.shadow import check_source_availability as check

    statuses = check(
        candidate=forecast["identity"]["run_id"],
        season=int(args.season),
        week=int(args.week),
        cutoff=str(args.as_of),
        forecast=forecast,
        rating_states=sources["team_states"],
        schedule=sources["population"],
        outcomes=sources["outcomes"],
        scoring_events=sources["scoring_events"],
        priors=sources["priors"],
        measurement_as_of=measurement_as_of,
        rating_as_of=rating_as_of,
    )
    if forecast.get("schema_version") == LIVE_FORECAST_MANIFEST_SCHEMA:
        candidate_status = _live_candidate_status(
            storage=storage,
            forecast=forecast,
            population=sources["population"],
            season=int(args.season),
            week=int(args.week),
            cutoff=str(args.as_of),
        )
        statuses = [
            candidate_status if status.source == "candidate" else status
            for status in statuses
        ]
    from cks_picks_cfb.forecast.shadow import build_readiness_report as build

    records, overall = build(
        candidate=forecast["identity"]["run_id"],
        season=int(args.season),
        week=int(args.week),
        run_id=args.run_id,
        statuses=statuses,
    )
    progress.emit("readiness_built", overall=overall, rows=len(records))
    replay_sha: str | None = None
    if args.replay:
        progress.emit("replay_started")
        if "historical_features" in sources:
            features = sources["historical_features"]
        else:
            offsets = build_offsets(
                sources["population"],
                sources["scoring_events"],
                development_seasons=tuple(DEVELOPMENT_SEASONS),
                equivalent_games=int(
                    config.get("offsets", {}).get("equivalent_games", 4)
                ),
            )
            features = _assemble_feature_frame(
                population=sources["population"],
                outcomes=sources["outcomes"],
                team_states=sources["team_states"],
                offsets=offsets.offsets,
            )
        first = replay_frozen_forecast(
            features=features,
            horizon="expanding",
            development_seasons=tuple(DEVELOPMENT_SEASONS),
            replay_seasons=REPLAY_SEASONS,
            alpha_grid=REPLAY_ALPHA_GRID,
            floor=REPLAY_FLOOR,
            cutoff_season=REPLAY_CUTOFF_SEASON,
            bootstrap_seed=REPLAY_BOOTSTRAP_SEED,
            bootstrap_samples=REPLAY_BOOTSTRAP_SAMPLES,
        )
        second = replay_frozen_forecast(
            features=features,
            horizon="expanding",
            development_seasons=tuple(DEVELOPMENT_SEASONS),
            replay_seasons=REPLAY_SEASONS,
            alpha_grid=REPLAY_ALPHA_GRID,
            floor=REPLAY_FLOOR,
            cutoff_season=REPLAY_CUTOFF_SEASON,
            bootstrap_seed=REPLAY_BOOTSTRAP_SEED,
            bootstrap_samples=REPLAY_BOOTSTRAP_SAMPLES,
            reference_sha=first.predictions_sha,
        )
        if not second.identical:
            raise ShadowRunError("frozen replay is not byte-identical")
        perturbation_invariance_proof(
            features=features,
            perturb_season=REPLAY_SEASONS[-1],
            horizon="expanding",
            development_seasons=tuple(DEVELOPMENT_SEASONS),
            replay_seasons=REPLAY_SEASONS,
            alpha_grid=REPLAY_ALPHA_GRID,
            floor=REPLAY_FLOOR,
            cutoff_season=REPLAY_CUTOFF_SEASON,
            bootstrap_seed=REPLAY_BOOTSTRAP_SEED,
            bootstrap_samples=REPLAY_BOOTSTRAP_SAMPLES,
        )
        replay_sha = first.predictions_sha
        progress.emit("replay_complete", replay_sha=replay_sha[:12])
    dataset, schema = SHADOW_DATASETS["readiness"]
    validate_frame(records, schema_for(dataset, schema))
    plan = _plan("readiness", records, READINESS_COLUMNS, ())
    evidence = {
        "state": "dry_run",
        "identity": identity,
        "parent_uris": {
            "forecast_manifest_uri": parents["forecast_manifest_uri"],
            "rating_manifest_uri": parents["rating_manifest_uri"],
            "measurement_manifest_uri": parents["measurement_manifest_uri"],
            "repair_manifest_uri": parents["repair_manifest_uri"],
        },
        "forecast_parent": forecast["identity"]["run_id"],
        "rating_parent": rating["identity"]["run_id"],
        "season": int(args.season),
        "week": int(args.week),
        "readiness_overall": overall,
        "readiness_by_source": {
            status.source: {
                "status": status.status,
                "timing_class": status.timing_class,
                "fallback": status.fallback,
                "blocked_reason": status.blocked_reason,
            }
            for status in statuses
        },
        "replay_sha256": replay_sha,
        "preflight_plans": {"readiness": plan},
        "row_counts": {"readiness": plan["row_count"]},
        "output_records_sha256": {"readiness": plan["records_sha"]},
        "production_activation_authorized": False,
    }
    progress.emit("evidence_constructed")
    return evidence


def apply(
    *,
    storage: Any,
    args: argparse.Namespace,
    identity: Mapping[str, Any],
    evidence: ShadowPreflightEvidence,
) -> dict[str, Any]:
    """Recompute readiness and publish it exactly as the evidence plans."""
    prefix = f"{SHADOW_OUTPUT_ROOT}/{args.run_id}"
    manifest_uri = f"{prefix}/{SHADOW_MANIFEST_NAME}"
    if (
        _existing_shadow_manifest(storage, manifest_uri=manifest_uri, identity=identity)
        is not None
    ):
        return {"state": "already_applied", "manifest_uri": manifest_uri}
    preexisting = sorted(storage.list_files(prefix))
    if preexisting:
        raise ShadowRunError(
            "shadow run prefix has a partial artifact and is permanently ineligible"
        )
    config = yaml.safe_load(Path(args.config).read_text())
    validate_shadow_config(config)
    progress = _Progress(args.run_id)
    progress.start()
    atexit.register(progress.close)
    progress.emit("apply_started", force=True)
    _immutable_json(
        storage,
        f"{prefix}/publication-plan.json",
        {
            "identity": dict(identity),
            "readiness_overall": evidence.overall,
            "plans": {
                "readiness": {
                    "row_count": evidence.plan["row_count"],
                    "records_sha": evidence.plan["records_sha"],
                    "parts": [],
                }
            },
            "production_activation_authorized": False,
        },
    )
    parents, forecast, rating = _load_parents(storage, args, progress)
    measurement_as_of = str(parents["measurement"]["identity"]["as_of"])
    rating_as_of = str(parents["rating"]["identity"]["as_of"])
    sources = _load_sources(storage, parents, rating, progress)
    from cks_picks_cfb.forecast.shadow import check_source_availability as check

    statuses = check(
        candidate=forecast["identity"]["run_id"],
        season=int(args.season),
        week=int(args.week),
        cutoff=str(args.as_of),
        forecast=forecast,
        rating_states=sources["team_states"],
        schedule=sources["population"],
        outcomes=sources["outcomes"],
        scoring_events=sources["scoring_events"],
        priors=sources["priors"],
        measurement_as_of=measurement_as_of,
        rating_as_of=rating_as_of,
    )
    if forecast.get("schema_version") == LIVE_FORECAST_MANIFEST_SCHEMA:
        candidate_status = _live_candidate_status(
            storage=storage,
            forecast=forecast,
            population=sources["population"],
            season=int(args.season),
            week=int(args.week),
            cutoff=str(args.as_of),
        )
        statuses = [
            candidate_status if status.source == "candidate" else status
            for status in statuses
        ]
    from cks_picks_cfb.forecast.shadow import build_readiness_report as build

    records, overall = build(
        candidate=forecast["identity"]["run_id"],
        season=int(args.season),
        week=int(args.week),
        run_id=args.run_id,
        statuses=statuses,
    )
    if overall != evidence.overall:
        raise ShadowRunError("apply replay differs from preflight verdict")
    dataset, schema_version = SHADOW_DATASETS["readiness"]
    schema = schema_for(dataset, schema_version)
    validate_frame(records, schema)
    records_sha = canonical_frame_digest(records, columns=schema.required)
    if (
        len(records) != evidence.plan["row_count"]
        or records_sha != evidence.plan["records_sha"]
    ):
        raise ShadowRunError("apply recomputation differs from preflight: readiness")
    as_of = _utc(str(identity["as_of"]))
    rating_ref = parents["rating"]["output_refs"]["team_states"]
    measurement_ref = parents["measurement"]["output_refs"]["population"]
    from cks_picks_cfb.data.lake import DatasetRef, build_dataset_version

    def _parent_ref(value: Mapping[str, Any], *, name: str) -> DatasetRef:
        fields = ("dataset", "version_id", "schema_version", "content_sha", "uri")
        if missing := [item for item in fields if not value.get(item)]:
            raise ShadowRunError(
                f"parent output reference is malformed: {name} {missing}"
            )
        return DatasetRef(**{item: value[item] for item in fields})

    ref, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=dataset,
            parent_refs=(
                _parent_ref(rating_ref, name="03 team states"),
                _parent_ref(measurement_ref, name="R6 population"),
            ),
            code_sha=str(identity["code_sha"]),
            config_sha=str(identity["config_sha"]),
            as_of=as_of,
            schema_version=schema_version,
            tier="gold",
        ),
        records=records.loc[:, list(schema.required)].to_dict("records"),
    )
    refs = {
        "readiness": {
            "artifact_kind": "dataset_v1",
            "dataset": ref.dataset,
            "version_id": ref.version_id,
            "schema_version": ref.schema_version,
            "content_sha": ref.content_sha,
            "records_sha": records_sha,
            "uri": ref.uri,
            "row_count": int(len(records)),
        }
    }
    manifest = shadow_manifest(
        identity=identity,
        parents={
            "forecast_manifest_uri": args.candidate_manifest_uri,
            "forecast_manifest_raw_sha256": hashlib.sha256(
                storage.read_bytes(args.candidate_manifest_uri)
            ).hexdigest(),
            "rating_manifest_uri": args.rating_manifest_uri,
            "rating_manifest_raw_sha256": hashlib.sha256(
                storage.read_bytes(args.rating_manifest_uri)
            ).hexdigest(),
            "measurement_manifest_uri": args.measurement_manifest_uri,
            "measurement_manifest_raw_sha256": hashlib.sha256(
                storage.read_bytes(args.measurement_manifest_uri)
            ).hexdigest(),
            "repair_manifest_uri": args.repair_manifest_uri,
            "repair_manifest_raw_sha256": hashlib.sha256(
                storage.read_bytes(args.repair_manifest_uri)
            ).hexdigest(),
        },
        output_refs=refs,
        readiness_overall=overall,
    )
    _immutable_json(storage, f"{prefix}/identity.json", dict(identity))
    _immutable_json(storage, f"{prefix}/readiness-ref.json", refs["readiness"])
    _immutable_json(storage, manifest_uri, manifest)
    progress.emit("apply_complete", force=True, manifest_uri=manifest_uri)
    progress.close()
    return {
        "state": "applied",
        "manifest_uri": manifest_uri,
        "readiness_overall": overall,
        "already_applied": False,
    }


def main(argv: list[str] | None = None) -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--environment", required=True, choices=("preview",))
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--candidate-manifest-uri", required=True)
    parser.add_argument("--rating-manifest-uri", required=True)
    parser.add_argument("--measurement-manifest-uri", required=True)
    parser.add_argument("--repair-manifest-uri", required=True)
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--week", required=True, type=int)
    parser.add_argument("--v4-prediction-ref-uri")
    parser.add_argument("--input-refs-uri")
    parser.add_argument("--slate-ref-uri")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--preflight-evidence",
        help="reviewed dry-run JSON used for a write-only apply",
    )
    args = parser.parse_args(argv)
    if _git_sha() != args.expected_code_sha:
        raise ShadowRunError("expected code SHA does not match committed HEAD")
    if bool(args.preflight_evidence) != bool(args.apply):
        raise ShadowRunError("--apply and --preflight-evidence must be used together")
    storage = get_storage(environment="preview")
    if args.apply:
        if not _clean_worktree():
            raise ShadowRunError("apply requires a completely clean committed worktree")
        validate_shadow_config(yaml.safe_load(Path(args.config).read_text()))
        identity = shadow_identity(
            run_id=args.run_id,
            as_of=args.as_of,
            code_sha=args.expected_code_sha,
            config_sha=hashlib.sha256(Path(args.config).read_bytes()).hexdigest(),
            parents={
                "forecast_manifest_uri": args.candidate_manifest_uri,
                "forecast_raw_sha256": hashlib.sha256(
                    storage.read_bytes(args.candidate_manifest_uri)
                ).hexdigest(),
                "rating_manifest_uri": args.rating_manifest_uri,
                "rating_raw_sha256": hashlib.sha256(
                    storage.read_bytes(args.rating_manifest_uri)
                ).hexdigest(),
                "measurement_manifest_uri": args.measurement_manifest_uri,
                "measurement_raw_sha256": hashlib.sha256(
                    storage.read_bytes(args.measurement_manifest_uri)
                ).hexdigest(),
                "repair_manifest_uri": args.repair_manifest_uri,
                "repair_raw_sha256": hashlib.sha256(
                    storage.read_bytes(args.repair_manifest_uri)
                ).hexdigest(),
            },
        )
        evidence = _load_shadow_preflight_evidence(
            Path(args.preflight_evidence), identity=identity
        )
        result = apply(storage=storage, args=args, identity=identity, evidence=evidence)
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    progress = _Progress(args.run_id)
    progress.start()
    try:
        evidence = preflight(storage=storage, args=args, progress=progress)
        print(json.dumps(evidence, indent=2, sort_keys=True, default=str))
        progress.emit(
            "dry_run_complete", identity=evidence["identity"]["identity_sha256"]
        )
    finally:
        progress.close()


if __name__ == "__main__":
    main()
