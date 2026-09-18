#!/usr/bin/env python3
"""V5-05C diagnostic shadow rehearsal runner.

Runs the full future-like sequence on pinned historical refs — readiness,
frozen replay, freeze validation, stabilized scoring, and counter
reconstruction — plus all six negative cases. Every output carries the
permanent ``diagnostic_only`` class and can never count as prospective
evidence. The independent verifier runs separately via
``verify_v5_shadow.py`` and owns the ``verification/verifier-manifest.json``
this run's artifacts reference.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import io
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

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_shadow_v1 import (
    DIAGNOSTIC_CLASS,
    SHADOW_DATASETS,
    SHADOW_OUTPUT_ROOT,
    SHADOW_REHEARSAL_COLUMNS,
    shadow_identity,
    validate_shadow_config,
    verify_candidate_parents,
)
from cks_picks_cfb.data.lake import (
    BuildRequest,
    build_dataset_version,
    canonical_frame_digest,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.offsets import build_offsets
from cks_picks_cfb.forecast.shadow import (
    build_readiness_report,
    check_source_availability,
    perturbation_invariance_proof,
    plan_freeze,
    replay_frozen_forecast,
    score_freeze,
    update_evidence_counter,
)
from cks_picks_cfb.ratings.possession_rating_materializer import (
    _stream_output,
    load_rating_inputs,
)
from scripts.research.run_v5_shadow_readiness import (
    REPLAY_ALPHA_GRID,
    REPLAY_BOOTSTRAP_SAMPLES,
    REPLAY_BOOTSTRAP_SEED,
    REPLAY_CUTOFF_SEASON,
    REPLAY_FLOOR,
    REPLAY_SEASONS,
    _assemble_feature_frame,
    _stream_partitioned,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "conf/research/data_first_football_v1/shadow_v1.yaml"

REHEARSAL_MANIFEST_NAME = "rehearsal-manifest.json"
REHEARSAL_MANIFEST_SCHEMA = "data_first_shadow_rehearsal_manifest_v1"
VERIFIER_MANIFEST_URI_SUFFIX = "verification/verifier-manifest.json"
NEGATIVE_CASES = (
    "timing_violation",
    "population_below_gate",
    "missing_outcome",
    "correction_version",
    "immutable_collision",
    "candidate_change_reset",
)
DEFAULT_FREEZE_TIME = "2025-11-15T14:00:00+00:00"
DEFAULT_SCORED_AT = "2025-11-17T00:00:00+00:00"


class RehearsalRunError(ValueError):
    """Raised before a V5-05C rehearsal run can produce reviewable evidence."""


class _Progress:
    _FORCED = frozenset(
        {
            "preflight_started",
            "parents_loaded",
            "sources_streamed",
            "readiness_built",
            "replay_started",
            "replay_complete",
            "freeze_planned",
            "scoring_complete",
            "negatives_complete",
            "dry_run_complete",
            "apply_started",
            "apply_complete",
        }
    )
    _BLOCKED = ("credential", "password", "secret", "token", "access_key")

    def __init__(self, run_id: str, interval: float = 30.0) -> None:
        self.run_id = run_id
        self.interval = interval
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
            k: v
            for k, v in fields.items()
            if not any(b in str(k).casefold() for b in cls._BLOCKED)
        }

    def emit(self, event: str, /, **fields: Any) -> None:
        now = time.monotonic()
        force = bool(fields.pop("force", False)) or event in self._FORCED
        safe = self._safe(fields)
        with self.lock:
            self.phase = str(safe.pop("phase", event))
            self.fields = safe
            if not force and now - self.last < self.interval:
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
            while not self.stop.wait(self.interval):
                with self.lock:
                    now = time.monotonic()
                    self._write("heartbeat", self.phase, self.fields, now)
                    self.last = now

        self.thread = threading.Thread(
            target=heartbeat, name=f"shadow-rehearsal-{self.run_id}", daemon=True
        )
        self.thread.start()

    def close(self) -> None:
        self.stop.set()
        if self.thread:
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
        raise RehearsalRunError("timestamp must be timezone-aware")
    return parsed.to_pydatetime().astimezone(timezone.utc)


def _immutable_json(storage: Any, uri: str, payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != encoded:
            raise RehearsalRunError(f"immutable object collision at {uri}")
        return
    storage.write_bytes(encoded, uri)


def _read_json(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:
        raise RehearsalRunError(f"unreadable manifest: {uri}") from exc


def _load_frame(storage: Any, uri: str, *, name: str) -> pd.DataFrame:
    if not uri:
        raise RehearsalRunError(f"--{name} is required for the rehearsal")
    raw = storage.read_bytes(uri)
    try:
        return pd.read_parquet(io.BytesIO(raw))
    except Exception:
        try:
            return pd.DataFrame(json.loads(raw))
        except Exception as exc:
            raise RehearsalRunError(f"cannot load {name} from {uri}") from exc


def _load_parents(storage: Any, args: argparse.Namespace, progress: _Progress) -> tuple:
    forecast, forecast_raw = _read_json(storage, args.candidate_manifest_uri)
    rating, rating_raw = _read_json(storage, args.rating_manifest_uri)
    measurement, measurement_raw = _read_json(storage, args.measurement_manifest_uri)
    repair, repair_raw = _read_json(storage, args.repair_manifest_uri)
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
    )
    progress.emit(
        "parents_loaded",
        forecast_parent=forecast["identity"]["run_id"],
        rating_parent=rating["identity"]["run_id"],
    )
    return parents, forecast, rating


def _load_sources(
    storage: Any,
    parents: Mapping[str, Any],
    rating: Mapping[str, Any],
    progress: _Progress,
) -> dict[str, Any]:
    from cks_picks_cfb.data.data_first_possession_rating_v1 import (
        PRIOR_COLUMNS,
        TEAM_STATE_COLUMNS,
    )

    measurement = parents["measurement"]
    repair = parents["repair"]
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


def _synthetic_v5_predictions(
    schedule: pd.DataFrame, season: int, week: int, candidate: str
) -> pd.DataFrame:
    """The frozen 05B diagnostic prediction rule (documented, deterministic)."""
    game_ids = (
        schedule[schedule["season"].eq(season) & schedule["week"].eq(week)]["game_id"]
        .astype(int)
        .tolist()
    )
    rows = []
    for gid in game_ids:
        for target in ("margin", "total"):
            rows.append(
                {
                    "game_id": gid,
                    "target": target,
                    "mean": 0.0,
                    "variance": 100.0,
                    "interval_lower_95": -19.6,
                    "interval_upper_95": 19.6,
                    "offset": 0.0,
                    "model_ref": candidate,
                    "state_ref": candidate,
                }
            )
    return pd.DataFrame(rows)


def _disposition(ok: bool, expected: str, detail: str) -> dict[str, Any]:
    return {
        "expected": expected,
        "disposition": expected if ok else "unexpected",
        "detail": detail,
    }


def _run_negative_cases(
    *,
    config: Mapping[str, Any],
    schedule: pd.DataFrame,
    v4: pd.DataFrame,
    outcomes: pd.DataFrame,
    freeze_plan: Any,
    score_result: Any,
    selected_cases: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    """Exercise every negative case in memory; no durable writes occur here."""
    cases: dict[str, dict[str, Any]] = {}
    season = int(freeze_plan.season)
    week = int(freeze_plan.week)
    candidate = freeze_plan.candidate
    min_paired = int(config.get("minimum_paired_games", 40))
    hard_lead = float(config.get("freeze_hard_lead_seconds", 3600.0))
    stabilization = float(config.get("score_stabilization_seconds", 86400.0))

    if "timing_violation" in selected_cases:
        first_kickoff = pd.Timestamp(freeze_plan.first_kickoff)
        inside = (first_kickoff - pd.Timedelta(seconds=1800)).isoformat()
        try:
            plan_freeze(
                candidate=candidate,
                season=season,
                week=week,
                run_id=freeze_plan.run_id,
                freeze_time=inside,
                schedule=schedule,
                v5_predictions=_synthetic_v5_predictions(
                    schedule, season, week, candidate
                ),
                v4_predictions=v4,
                v4_ref_uri=freeze_plan.v4_ref_uri,
                min_paired_games=min_paired,
                freeze_hard_lead_seconds=hard_lead,
            )
            cases["timing_violation"] = _disposition(
                False, "rejected", "freeze inside the hard gate was accepted"
            )
        except ValueError as exc:
            cases["timing_violation"] = _disposition(
                "hard gate" in str(exc),
                "rejected",
                f"rejected: {exc}",
            )

    if "population_below_gate" in selected_cases:
        short_schedule = schedule.head(min_paired - 1).copy()
        try:
            plan_freeze(
                candidate=candidate,
                season=season,
                week=week,
                run_id=freeze_plan.run_id,
                freeze_time=freeze_plan.freeze_time,
                schedule=short_schedule,
                v5_predictions=_synthetic_v5_predictions(
                    short_schedule, season, week, candidate
                ),
                v4_predictions=v4,
                v4_ref_uri=freeze_plan.v4_ref_uri,
                min_paired_games=min_paired,
                freeze_hard_lead_seconds=hard_lead,
            )
            cases["population_below_gate"] = _disposition(
                False, "rejected", "below-gate population was accepted"
            )
        except ValueError as exc:
            cases["population_below_gate"] = _disposition(
                "minimum" in str(exc) or "paired" in str(exc),
                "rejected",
                f"rejected: {exc}",
            )

    if "missing_outcome" in selected_cases:
        frozen_games = set(freeze_plan.predictions["game_id"].astype(int).tolist())
        dropped_game = sorted(frozen_games)[0]
        partial_outcomes = outcomes[
            ~outcomes["game_id"].astype(int).eq(dropped_game)
        ].copy()
        partial_score = score_freeze(
            candidate=candidate,
            season=season,
            week=week,
            run_id=freeze_plan.run_id,
            freeze_record=freeze_plan.freeze_record,
            predictions=freeze_plan.predictions,
            outcomes=partial_outcomes,
            outcome_version="v1",
            scored_at=DEFAULT_SCORED_AT,
            min_stabilization_seconds=stabilization,
        )
        scored_games = set(partial_score.evaluation["game_id"].astype(int).tolist())
        detected = scored_games != frozen_games
        cases["missing_outcome"] = _disposition(
            detected,
            "rejected",
            (
                f"producer silently scored {len(scored_games)} of "
                f"{len(frozen_games)} frozen games; independent reconstruction "
                "detects the missing outcome"
                if detected
                else "missing outcome was not detectable"
            ),
        )

    if "correction_version" in selected_cases:
        corrected = outcomes.copy()
        corrected.loc[corrected.index[0], "actual_margin"] = (
            float(corrected.loc[corrected.index[0], "actual_margin"]) + 3.0
        )
        second = score_freeze(
            candidate=candidate,
            season=season,
            week=week,
            run_id=freeze_plan.run_id,
            freeze_record=freeze_plan.freeze_record,
            predictions=freeze_plan.predictions,
            outcomes=corrected,
            outcome_version="v2",
            scored_at=DEFAULT_SCORED_AT,
            min_stabilization_seconds=stabilization,
        )
        counter, count = update_evidence_counter(
            score_result.counter_record,
            second.counter_record,
            candidate=candidate,
            season=season,
            week=week,
        )
        counted_once = count == 1 and len(counter) == 2
        cases["correction_version"] = _disposition(
            counted_once,
            "counted_once",
            (
                f"correction appended outcome_version v2; {len(counter)} rows, "
                f"{count} qualifying slate"
                if counted_once
                else "correction changed the qualifying count"
            ),
        )

    if "immutable_collision" in selected_cases:
        prefix = f"{SHADOW_OUTPUT_ROOT}/{freeze_plan.run_id}"
        store: dict[str, bytes] = {
            f"{prefix}/rehearsal-manifest.json": b"different-identity-bytes"
        }

        class _Seeded:
            def exists(self, uri: str) -> bool:
                return uri in store

            def read_bytes(self, uri: str) -> bytes:
                return store[uri]

            def write_bytes(self, payload: bytes, uri: str) -> None:
                store[uri] = payload

        collided = False
        try:
            _immutable_json(
                _Seeded(),
                f"{prefix}/rehearsal-manifest.json",
                {"identity": "different"},
            )
        except RehearsalRunError:
            collided = True
        cases["immutable_collision"] = _disposition(
            collided,
            "rejected",
            (
                "pre-existing manifest with a different identity aborts the run"
                if collided
                else "immutable collision was accepted"
            ),
        )

    if "candidate_change_reset" in selected_cases:
        other_candidate = f"{candidate}-successor"
        other_record = score_result.counter_record.copy()
        other_record["candidate"] = other_candidate
        merged, count = update_evidence_counter(
            score_result.counter_record,
            other_record,
            candidate=other_candidate,
            season=season,
            week=week,
        )
        per_candidate = (
            merged[merged["qualifying"].astype(bool)]
            .groupby("candidate")["season"]
            .count()
        )
        reset = count == 2 and per_candidate.to_dict() == {
            candidate: 1,
            other_candidate: 1,
        }
        cases["candidate_change_reset"] = _disposition(
            reset,
            "reset",
            (
                "a changed candidate starts a fresh evidence ledger; each "
                "candidate holds exactly one slate"
                if reset
                else "candidate change did not reset the ledger"
            ),
        )

    return cases


def _build_rehearsal_record(
    *,
    candidate: str,
    run_id: str,
    season_range: str,
    cases: Mapping[str, dict[str, Any]],
    verifier_uri: str,
) -> pd.DataFrame:
    failed = [
        name for name, case in cases.items() if case["disposition"] == "unexpected"
    ]
    frame = pd.DataFrame.from_records(
        [
            {
                "candidate": candidate,
                "run_id": run_id,
                "season_range": season_range,
                "diagnostic_only": True,
                "cases_passed": len(cases) - len(failed),
                "cases_failed": len(failed),
                "verifier_ref": verifier_uri,
            }
        ]
    )
    validate_frame(frame, schema_for(*SHADOW_DATASETS["shadow_rehearsal"]))
    return frame


def _plan_evidence(
    *,
    identity: Mapping[str, Any],
    args: argparse.Namespace,
    record: pd.DataFrame,
    readiness_overall: str,
    replay_sha: str,
    freeze_plan: Any,
    score_result: Any,
    qualifying_count: int,
    cases: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    record_sha = canonical_frame_digest(record, columns=list(SHADOW_REHEARSAL_COLUMNS))
    return {
        "state": "dry_run",
        "identity": dict(identity),
        "readiness_overall": readiness_overall,
        "replay_sha256": replay_sha,
        "freeze": {
            "season": freeze_plan.season,
            "week": freeze_plan.week,
            "freeze_time": freeze_plan.freeze_time,
            "lead_seconds": freeze_plan.lead_seconds,
            "slate_digest": freeze_plan.slate_digest,
            "paired_count": freeze_plan.paired_count,
        },
        "score": {
            "outcome_version": score_result.outcome_version,
            "paired_count": score_result.paired_count,
            "mae_margin": score_result.mae_margin,
            "mae_total": score_result.mae_total,
        },
        "counter_qualifying": qualifying_count,
        "diagnostic_class": DIAGNOSTIC_CLASS,
        "cases": {name: dict(case) for name, case in cases.items()},
        "rehearsal_plan": {
            "name": "shadow_rehearsal",
            "partition_keys": [],
            "row_count": len(record),
            "records_sha": record_sha,
        },
        "row_counts": {"shadow_rehearsal": len(record)},
        "output_records_sha256": {"shadow_rehearsal": record_sha},
        "production_activation_authorized": False,
    }


def preflight(
    *, storage: Any, args: argparse.Namespace, progress: _Progress
) -> dict[str, Any]:
    progress.emit("preflight_started", run_id=args.run_id, as_of=args.as_of)
    config = yaml.safe_load(Path(args.config).read_text())
    validate_shadow_config(config)
    parents, forecast, rating = _load_parents(storage, args, progress)
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
    )
    sources = _load_sources(storage, parents, rating, progress)

    # Readiness on the pinned historical slate ------------------------------
    statuses = check_source_availability(
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
        measurement_as_of=str(parents["measurement"]["identity"]["as_of"]),
        rating_as_of=str(parents["rating"]["identity"]["as_of"]),
    )
    _, readiness_overall = build_readiness_report(
        candidate=forecast["identity"]["run_id"],
        season=int(args.season),
        week=int(args.week),
        run_id=args.run_id,
        statuses=statuses,
    )
    progress.emit("readiness_built", overall=readiness_overall)

    # Frozen replay ----------------------------------------------------------
    progress.emit("replay_started")
    offsets = build_offsets(
        sources["population"],
        sources["scoring_events"],
        development_seasons=tuple(DEVELOPMENT_SEASONS),
        equivalent_games=int(config.get("offsets", {}).get("equivalent_games", 4)),
    )
    features = _assemble_feature_frame(
        population=sources["population"],
        outcomes=sources["outcomes"],
        team_states=sources["team_states"],
        offsets=offsets.offsets,
    )
    replay_kwargs = dict(
        horizon="expanding",
        development_seasons=tuple(DEVELOPMENT_SEASONS),
        replay_seasons=REPLAY_SEASONS,
        alpha_grid=REPLAY_ALPHA_GRID,
        floor=REPLAY_FLOOR,
        cutoff_season=REPLAY_CUTOFF_SEASON,
        bootstrap_seed=REPLAY_BOOTSTRAP_SEED,
        bootstrap_samples=REPLAY_BOOTSTRAP_SAMPLES,
    )
    first = replay_frozen_forecast(features=features, **replay_kwargs)
    second = replay_frozen_forecast(
        features=features, reference_sha=first.predictions_sha, **replay_kwargs
    )
    if not second.identical:
        raise RehearsalRunError("frozen replay is not byte-identical")
    perturbation_invariance_proof(
        features=features, perturb_season=REPLAY_SEASONS[-1], **replay_kwargs
    )
    replay_sha = first.predictions_sha
    progress.emit("replay_complete", replay_sha=replay_sha[:12])

    # Freeze validation ------------------------------------------------------
    schedule = _load_frame(storage, args.slate_ref_uri, name="slate-ref-uri")
    v4 = _load_frame(storage, args.v4_prediction_ref_uri, name="v4-prediction-ref-uri")
    v5 = _synthetic_v5_predictions(
        schedule, int(args.season), int(args.week), forecast["identity"]["run_id"]
    )
    freeze_plan = plan_freeze(
        candidate=forecast["identity"]["run_id"],
        season=int(args.season),
        week=int(args.week),
        run_id=args.run_id,
        freeze_time=args.freeze_time,
        schedule=schedule,
        v5_predictions=v5,
        v4_predictions=v4,
        v4_ref_uri=args.v4_prediction_ref_uri,
        is_diagnostic=True,
        min_paired_games=int(config.get("minimum_paired_games", 40)),
        freeze_hard_lead_seconds=float(config.get("freeze_hard_lead_seconds", 3600.0)),
    )
    progress.emit(
        "freeze_planned",
        paired_count=freeze_plan.paired_count,
        lead_seconds=freeze_plan.lead_seconds,
    )

    # Stabilized scoring -----------------------------------------------------
    outcomes = _load_frame(storage, args.outcome_ref_uri, name="outcome-ref-uri")
    score_result = score_freeze(
        candidate=forecast["identity"]["run_id"],
        season=int(args.season),
        week=int(args.week),
        run_id=args.run_id,
        freeze_record=freeze_plan.freeze_record,
        predictions=freeze_plan.predictions,
        outcomes=outcomes,
        outcome_version="v1",
        scored_at=args.scored_at,
        freeze_ref=args.freeze_manifest_uri,
        min_stabilization_seconds=float(
            config.get("score_stabilization_seconds", 86400.0)
        ),
    )
    diagnostic_counter = score_result.counter_record.copy()
    diagnostic_counter["qualifying"] = False
    diagnostic_counter["reason"] = DIAGNOSTIC_CLASS
    _, qualifying_count = update_evidence_counter(
        pd.DataFrame(
            columns=[
                "candidate",
                "season",
                "week",
                "qualifying",
                "reason",
                "freeze_ref",
                "evaluation_ref",
            ]
        ),
        diagnostic_counter,
        candidate=forecast["identity"]["run_id"],
        season=int(args.season),
        week=int(args.week),
    )
    if qualifying_count != 0:
        raise RehearsalRunError("diagnostic rehearsal may never count as qualifying")
    progress.emit("scoring_complete", paired_count=score_result.paired_count)

    # Negative cases ---------------------------------------------------------
    selected = tuple(
        name.strip()
        for name in (args.negatives or ",".join(NEGATIVE_CASES)).split(",")
        if name.strip()
    )
    unknown = [name for name in selected if name not in NEGATIVE_CASES]
    if unknown:
        raise RehearsalRunError(f"unknown negative cases: {unknown}")
    cases = _run_negative_cases(
        config=config,
        schedule=schedule,
        v4=v4,
        outcomes=outcomes,
        freeze_plan=freeze_plan,
        score_result=score_result,
        selected_cases=selected,
    )
    mainline = {
        "mainline_positive": {
            "expected": "passed",
            "disposition": "passed",
            "detail": (
                f"readiness={readiness_overall}; replay byte-identical; "
                f"freeze paired={freeze_plan.paired_count}; "
                f"score paired={score_result.paired_count}; qualifying=0"
            ),
        }
    }
    cases = mainline | cases
    failed = [
        name for name, case in cases.items() if case["disposition"] == "unexpected"
    ]
    progress.emit("negatives_complete", failed=len(failed), total=len(cases))

    verifier_uri = f"{SHADOW_OUTPUT_ROOT}/{args.run_id}/{VERIFIER_MANIFEST_URI_SUFFIX}"
    record = _build_rehearsal_record(
        candidate=forecast["identity"]["run_id"],
        run_id=args.run_id,
        season_range=args.season_range,
        cases=cases,
        verifier_uri=verifier_uri,
    )
    return _plan_evidence(
        identity=identity,
        args=args,
        record=record,
        readiness_overall=readiness_overall,
        replay_sha=replay_sha,
        freeze_plan=freeze_plan,
        score_result=score_result,
        qualifying_count=qualifying_count,
        cases=cases,
    )


def _load_rehearsal_preflight(
    path: Path, *, identity: Mapping[str, Any]
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise RehearsalRunError("preflight evidence is unreadable") from exc
    if payload.get("state") != "dry_run" or payload.get("identity") != dict(identity):
        raise RehearsalRunError("preflight evidence identity does not match apply")
    plan = payload.get("rehearsal_plan") or {}
    if plan.get("name") != "shadow_rehearsal":
        raise RehearsalRunError("preflight evidence missing the rehearsal plan")
    cases = payload.get("cases") or {}
    failed = [
        name for name, case in cases.items() if case.get("disposition") == "unexpected"
    ]
    if failed:
        raise RehearsalRunError(
            f"preflight evidence has unexpected negative dispositions: {failed}"
        )
    return payload


def apply(
    *,
    storage: Any,
    args: argparse.Namespace,
    identity: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    prefix = f"{SHADOW_OUTPUT_ROOT}/{args.run_id}"
    manifest_uri = f"{prefix}/{REHEARSAL_MANIFEST_NAME}"
    if storage.exists(manifest_uri):
        existing = json.loads(storage.read_bytes(manifest_uri))
        if (existing.get("identity") or {}).get("identity_sha256") == identity[
            "identity_sha256"
        ]:
            return {"state": "already_applied", "rehearsal_manifest_uri": manifest_uri}
        raise RehearsalRunError("rehearsal run ID already has a different identity")
    preexisting = sorted(storage.list_files(prefix))
    if preexisting:
        raise RehearsalRunError(
            "rehearsal run prefix has a partial artifact and is permanently ineligible"
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
            "plans": {"shadow_rehearsal": evidence["rehearsal_plan"]},
            "production_activation_authorized": False,
        },
    )

    record = _build_rehearsal_record(
        candidate=evidence["identity"]["candidate"],
        run_id=args.run_id,
        season_range=args.season_range,
        cases=evidence["cases"],
        verifier_uri=f"{prefix}/{VERIFIER_MANIFEST_URI_SUFFIX}",
    )
    record_sha = canonical_frame_digest(record, columns=list(SHADOW_REHEARSAL_COLUMNS))
    if record_sha != evidence["rehearsal_plan"].get("records_sha"):
        raise RehearsalRunError(
            "apply recomputation differs from preflight: shadow_rehearsal"
        )

    dataset, schema_version = SHADOW_DATASETS["shadow_rehearsal"]
    schema = schema_for(dataset, schema_version)
    ref, _ = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=dataset,
            parent_refs=(),
            code_sha=str(identity["code_sha"]),
            config_sha=str(identity["config_sha"]),
            as_of=_utc(str(identity["as_of"])),
            schema_version=schema_version,
            tier="gold",
        ),
        records=record.loc[:, list(schema.required)].to_dict("records"),
    )

    rehearsal_manifest = {
        "schema_version": REHEARSAL_MANIFEST_SCHEMA,
        "state": "frozen",
        "identity": dict(identity),
        "parents": {
            "forecast_manifest_uri": identity["parents"]["forecast_manifest_uri"],
            "rating_manifest_uri": identity["parents"]["rating_manifest_uri"],
            "measurement_manifest_uri": identity["parents"]["measurement_manifest_uri"],
            "repair_manifest_uri": identity["parents"]["repair_manifest_uri"],
            "readiness_manifest_uri": args.readiness_manifest_uri,
            "freeze_manifest_uri": args.freeze_manifest_uri,
            "v4_prediction_ref_uri": args.v4_prediction_ref_uri,
            "slate_ref_uri": args.slate_ref_uri,
            "outcome_ref_uri": args.outcome_ref_uri,
        },
        "replay": {
            "replay_sha256": evidence["replay_sha256"],
            "byte_identical": True,
            "perturbation_invariance": True,
        },
        "readiness_overall": evidence["readiness_overall"],
        "rehearsal_cases": dict(evidence["cases"]),
        "verification": {
            "verifier_manifest_uri": f"{prefix}/{VERIFIER_MANIFEST_URI_SUFFIX}"
        },
        "output_refs": {
            "shadow_rehearsal": {
                "artifact_kind": "dataset_v1",
                "dataset": ref.dataset,
                "version_id": ref.version_id,
                "schema_version": ref.schema_version,
                "content_sha": ref.content_sha,
                "uri": ref.uri,
                "row_count": len(record),
            }
        },
        "diagnostic_class": DIAGNOSTIC_CLASS,
        "production_activation_authorized": False,
    }
    _immutable_json(storage, manifest_uri, rehearsal_manifest)
    progress.emit("apply_complete", force=True, rehearsal_manifest_uri=manifest_uri)
    progress.close()
    return {
        "state": "applied",
        "rehearsal_manifest_uri": manifest_uri,
        "cases_passed": record["cases_passed"].iloc[0],
        "cases_failed": record["cases_failed"].iloc[0],
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
    parser.add_argument("--readiness-manifest-uri", required=True)
    parser.add_argument("--freeze-manifest-uri", required=True)
    parser.add_argument("--v4-prediction-ref-uri", required=True)
    parser.add_argument("--slate-ref-uri", required=True)
    parser.add_argument("--outcome-ref-uri", required=True)
    parser.add_argument("--season", required=True, type=int)
    parser.add_argument("--week", required=True, type=int)
    parser.add_argument("--freeze-time", default=DEFAULT_FREEZE_TIME)
    parser.add_argument("--scored-at", default=DEFAULT_SCORED_AT)
    parser.add_argument(
        "--season-range",
        default=f"{REPLAY_SEASONS[0]}-{REPLAY_SEASONS[-1]}",
    )
    parser.add_argument(
        "--negatives",
        default=",".join(NEGATIVE_CASES),
        help="comma-separated negative cases to exercise",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence")
    args = parser.parse_args(argv)

    if _git_sha() != args.expected_code_sha:
        raise RehearsalRunError("expected code SHA does not match committed HEAD")
    if bool(args.preflight_evidence) != bool(args.apply):
        raise RehearsalRunError(
            "--apply and --preflight-evidence must be used together"
        )
    expected_range = f"{REPLAY_SEASONS[0]}-{REPLAY_SEASONS[-1]}"
    if args.season_range != expected_range:
        raise RehearsalRunError(
            f"--season-range must match the exercised replay span {expected_range}"
        )
    storage = get_storage(environment="preview")
    if args.apply:
        if not _clean_worktree():
            raise RehearsalRunError(
                "apply requires a completely clean committed worktree"
            )
        validate_shadow_config(yaml.safe_load(Path(args.config).read_text()))
        parents, _forecast, _rating = _load_parents(
            storage, args, _Progress(args.run_id)
        )
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
        )
        evidence = _load_rehearsal_preflight(
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
