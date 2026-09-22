"""Source loading and 05 lineage verification for Contract 06 evidence."""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    LIVE_FORECAST_MANIFEST_SCHEMA,
)
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.lake import (
    DatasetRef,
    PartitionedDatasetRef,
    iter_partitioned_dataset,
    read_dataset,
)
from cks_picks_cfb.forecast.shadow_verification import (
    FREEZE_MANIFEST_SCHEMA,
    SCORE_MANIFEST_SCHEMA,
    SHADOW_MANIFEST_SCHEMA,
    VERIFICATION_MANIFEST_SCHEMA,
    _load_compact,
    _load_partitioned,
    verify_shadow_artifact,
)


class EvidenceSourceError(ValueError):
    """Raised when Contract 06 source lineage cannot be independently checked."""


EVIDENCE_INPUT_SCHEMA = "data_first_v5_evidence_input_v1"
AUTHENTIC_QUOTE_MANIFEST_SCHEMA = "data_first_v5_authentic_quote_manifest_v1"


def _json(storage: Any, uri: str, *, label: str) -> tuple[dict[str, Any], bytes]:
    if not uri:
        raise EvidenceSourceError(f"{label} URI is required")
    raw = storage.read_bytes(uri)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvidenceSourceError(f"{label} is not valid JSON: {uri}") from exc
    if not isinstance(value, dict):
        raise EvidenceSourceError(f"{label} must be a JSON object")
    return value, raw


def _frame_bytes(raw: bytes, *, label: str) -> pd.DataFrame:
    try:
        return pd.read_parquet(io.BytesIO(raw))
    except Exception:
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                value = value.get("records", value.get("data", value))
            return pd.DataFrame(value)
        except Exception:
            try:
                return pd.read_csv(io.BytesIO(raw))
            except Exception as exc:
                raise EvidenceSourceError(f"cannot read {label} frame") from exc


def _source_frame(storage: Any, uri: str, *, label: str) -> tuple[pd.DataFrame, str]:
    if not uri:
        raise EvidenceSourceError(f"{label} source URI is required")
    raw = storage.read_bytes(uri)
    return _frame_bytes(raw, label=label), hashlib.sha256(raw).hexdigest()


def _dataset(storage: Any, ref: Mapping[str, Any], *, label: str) -> pd.DataFrame:
    required = {"dataset", "version_id", "schema_version", "content_sha", "uri"}
    if missing := sorted(required - set(ref)):
        raise EvidenceSourceError(f"{label} ref lacks fields: {missing}")
    if ref.get("artifact_kind") == "partitioned_dataset_v1":
        raw_manifest = json.loads(storage.read_bytes(str(ref["uri"])))
        partitioned = PartitionedDatasetRef(
            artifact_kind="partitioned_dataset_v1",
            dataset=str(ref["dataset"]),
            version_id=str(ref["version_id"]),
            schema_version=str(ref["schema_version"]),
            content_sha=str(ref["content_sha"]),
            records_sha=str(raw_manifest.get("records_sha", "")),
            uri=str(ref["uri"]),
            row_count=int(ref.get("row_count", raw_manifest.get("row_count", -1))),
            partition_keys=tuple(
                raw_manifest.get("partition_keys") or ref.get("partition_keys") or ()
            ),
        )
        frames = list(iter_partitioned_dataset(storage, partitioned))
        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    else:
        frame = read_dataset(
            storage,
            DatasetRef(
                dataset=str(ref["dataset"]),
                version_id=str(ref["version_id"]),
                schema_version=str(ref["schema_version"]),
                content_sha=str(ref["content_sha"]),
                uri=str(ref["uri"]),
            ),
        )
    if int(ref.get("row_count", len(frame))) != len(frame):
        raise EvidenceSourceError(f"{label} row count mismatch")
    return frame


def _receipt(
    storage: Any,
    *,
    uri: str,
    manifest_uri: str,
    expected_kind: str,
    reconstructed: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    receipt, raw = _json(storage, uri, label=f"{expected_kind} verifier receipt")
    try:
        verify_signed_payload(receipt, label=f"{expected_kind} verifier receipt")
    except ValueError as exc:
        raise EvidenceSourceError(str(exc)) from exc
    if (
        receipt.get("schema_version") != VERIFICATION_MANIFEST_SCHEMA
        or receipt.get("state") != "verified"
        or receipt.get("verified") is not True
        or receipt.get("kind") != expected_kind
        or receipt.get("manifest_uri") != manifest_uri
    ):
        raise EvidenceSourceError(
            f"{expected_kind} verifier receipt does not bind the exact source manifest"
        )
    for key, value in reconstructed.items():
        if receipt.get(key) != value:
            raise EvidenceSourceError(
                f"{expected_kind} verifier receipt is stale at field {key}"
            )
    return receipt, hashlib.sha256(raw).hexdigest()


def _require_code(
    manifest: Mapping[str, Any], expected_code_sha: str, label: str
) -> None:
    code_sha = (manifest.get("identity") or {}).get("code_sha")
    if code_sha != expected_code_sha:
        raise EvidenceSourceError(
            f"{label} code SHA differs from expected committed code"
        )


def _readiness_blocker(storage: Any, manifest: Mapping[str, Any]) -> str:
    ref = (manifest.get("output_refs") or {}).get("readiness") or {}
    if not ref:
        return "readiness output missing"
    frame = _load_compact(storage, ref, name="readiness", dataset_key="readiness")
    blockers = [
        str(value)
        for value in frame.get("blocked_reason", pd.Series(dtype=str)).tolist()
        if value and not pd.isna(value)
    ]
    return "; ".join(dict.fromkeys(blockers))


def _live_forecast(
    storage: Any,
    *,
    readiness: Mapping[str, Any],
    expected_code_sha: str,
) -> tuple[dict[str, Any], pd.DataFrame, str, str]:
    parent_set = (readiness.get("identity") or {}).get("parents") or {}
    manifest_uri = str(parent_set.get("forecast_manifest_uri", ""))
    forecast, raw = _json(storage, manifest_uri, label="candidate forecast manifest")
    if forecast.get("schema_version") != LIVE_FORECAST_MANIFEST_SCHEMA:
        raise EvidenceSourceError(
            "Contract 06 admits only the versioned outcome-free live forecast"
        )
    try:
        verify_signed_payload(forecast, label="live forecast manifest")
    except ValueError as exc:
        raise EvidenceSourceError(str(exc)) from exc
    _require_code(forecast, expected_code_sha, "live forecast")
    predictions = _dataset(
        storage, forecast.get("output_ref") or {}, label="live forecast predictions"
    )
    return (
        forecast,
        predictions,
        manifest_uri,
        hashlib.sha256(raw).hexdigest(),
    )


def _outcome_version_rows(
    *,
    candidate: str,
    season: int,
    week: int,
    freeze_run_id: str,
    outcome_version: str,
    score_completed_at: str,
    last_game_completed_at: Any,
    outcome_uri: str,
    outcome_sha: str,
    evaluation_uri: str,
    score_manifest_sha: str,
    evaluation_verified: bool,
    supersedes_uri: str,
) -> dict[str, Any]:
    return {
        "candidate": candidate,
        "season": season,
        "week": week,
        "run_id": freeze_run_id,
        "outcome_version": outcome_version,
        "score_completed_at": score_completed_at,
        "last_game_completed_at": last_game_completed_at,
        "outcome_ref": outcome_uri,
        "outcome_raw_sha256": outcome_sha,
        "evaluation_ref": evaluation_uri,
        "evaluation_manifest_sha256": score_manifest_sha,
        "evaluation_verified": evaluation_verified,
        "supersedes_score_manifest_uri": supersedes_uri,
    }


def _football_rows(
    *,
    forecast: Mapping[str, Any],
    all_predictions: pd.DataFrame,
    freeze_predictions: pd.DataFrame,
    outcomes: pd.DataFrame,
    v4_predictions: pd.DataFrame,
    season: int,
    week: int,
) -> pd.DataFrame:
    required_predictions = {
        "season",
        "week",
        "game_id",
        "target",
        "mean",
        "variance",
        "completed_game_stage",
    }
    if missing := sorted(required_predictions - set(all_predictions)):
        raise EvidenceSourceError(f"live forecasts lack report fields: {missing}")
    required_outcomes = {
        "game_id",
        "actual_margin",
        "actual_total",
        "last_completion_time",
    }
    if missing := sorted(required_outcomes - set(outcomes)):
        raise EvidenceSourceError(f"outcome source lacks report fields: {missing}")
    needed = all_predictions[
        all_predictions["season"].eq(season) & all_predictions["week"].eq(week)
    ].copy()
    needed["game_id"] = needed["game_id"].astype(int)
    if needed.duplicated(["game_id", "target"]).any():
        raise EvidenceSourceError("live forecast duplicates game/target report keys")
    if outcomes.duplicated("game_id").any():
        raise EvidenceSourceError("outcome source duplicates a game identity")
    outcome_rows = outcomes.loc[:, list(required_outcomes)].copy()
    long = pd.concat(
        [
            outcome_rows[["game_id", "actual_margin"]]
            .rename(columns={"actual_margin": "actual"})
            .assign(target="margin"),
            outcome_rows[["game_id", "actual_total"]]
            .rename(columns={"actual_total": "actual"})
            .assign(target="total"),
        ],
        ignore_index=True,
    ).dropna(subset=["actual"])
    rows = needed.merge(
        long, on=["game_id", "target"], how="inner", validate="one_to_one"
    )
    if rows.empty:
        return pd.DataFrame(
            columns=[
                "season",
                "week",
                "game_id",
                "target",
                "actual",
                "v5_mean",
                "v5_variance",
                "v4_mean",
                "completed_game_stage",
                "broader_population",
                "paired_population",
            ]
        )
    rows = rows.merge(
        outcome_rows[["game_id", "last_completion_time"]],
        on="game_id",
        how="left",
        validate="many_to_one",
    )
    v4 = v4_predictions.copy()
    if not {"game_id", "target", "mean"} <= set(v4):
        raise EvidenceSourceError("V4 parent must expose game_id, target, and mean")
    v4["game_id"] = pd.to_numeric(v4["game_id"], errors="coerce")
    if v4.duplicated(["game_id", "target"]).any():
        raise EvidenceSourceError("V4 parent duplicates game/target keys")
    rows = rows.merge(
        v4[["game_id", "target", "mean"]].rename(columns={"mean": "v4_mean"}),
        on=["game_id", "target"],
        how="left",
        validate="one_to_one",
    )
    frozen_keys = set(
        map(
            tuple,
            freeze_predictions[["game_id", "target"]]
            .assign(game_id=lambda frame: frame["game_id"].astype(int))
            .to_numpy(),
        )
    )
    rows["paired_population"] = [
        (int(game), str(target)) in frozen_keys
        for game, target in zip(rows["game_id"], rows["target"])
    ]
    if not np.isfinite(
        pd.to_numeric(rows.loc[rows["paired_population"], "v4_mean"], errors="coerce")
    ).all():
        raise EvidenceSourceError("paired live rows lack a finite V4 prediction")
    rows["season"] = int(season)
    rows["week"] = int(week)
    rows["game_id"] = rows["game_id"].astype(int)
    rows["v5_mean"] = pd.to_numeric(rows["mean"], errors="coerce")
    rows["v5_variance"] = pd.to_numeric(rows["variance"], errors="coerce")
    rows["completed_game_stage"] = (
        pd.to_numeric(rows["completed_game_stage"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    rows["broader_population"] = True
    return rows.loc[
        :,
        [
            "season",
            "week",
            "game_id",
            "target",
            "actual",
            "v5_mean",
            "v5_variance",
            "v4_mean",
            "completed_game_stage",
            "broader_population",
            "paired_population",
        ],
    ]


def _load_verified_score_version(
    storage: Any,
    *,
    version: Mapping[str, Any],
    freeze_uri: str,
    schedule_uri: str,
    v4_uri: str,
    freeze_predictions: pd.DataFrame,
    season: int,
    week: int,
    attempt_run_id: str,
    candidate: str,
    expected_code_sha: str,
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    score_uri = str(version.get("score_manifest_uri", ""))
    score_v_uri = str(version.get("score_verifier_uri", ""))
    outcome_uri = str(version.get("outcome_uri", ""))
    score, score_raw = _json(storage, score_uri, label="score manifest")
    if score.get("schema_version") != SCORE_MANIFEST_SCHEMA:
        raise EvidenceSourceError("score manifest schema mismatch")
    _require_code(score, expected_code_sha, "score")
    if (score.get("parents") or {}).get("freeze_manifest_uri") != freeze_uri:
        raise EvidenceSourceError("score manifest does not bind this freeze")
    outcomes, outcome_sha = _source_frame(
        storage, outcome_uri, label="versioned outcome source"
    )
    score_result = verify_shadow_artifact(
        storage,
        manifest_uri=score_uri,
        expected_code_sha=expected_code_sha,
        environment="preview",
        schedule_uri=schedule_uri,
        v4_prediction_uri=v4_uri,
        outcome_uri=outcome_uri,
    )
    _, score_receipt_sha = _receipt(
        storage,
        uri=score_v_uri,
        manifest_uri=score_uri,
        expected_kind="score",
        reconstructed=score_result,
    )
    score_raw_sha = hashlib.sha256(score_raw).hexdigest()
    summary = score.get("score_summary") or {}
    outcome_version = str(summary.get("outcome_version", ""))
    evaluation_ref = (score.get("output_refs") or {}).get("shadow_evaluation") or {}
    evaluation = _load_partitioned(
        storage,
        evaluation_ref,
        name="shadow_evaluation",
        dataset_key="shadow_evaluation",
    )
    if (
        not outcome_version
        or not evaluation["outcome_version"].astype(str).eq(outcome_version).all()
    ):
        raise EvidenceSourceError("score evaluation rows use another outcome version")
    game_ids = set(freeze_predictions["game_id"].astype(int))
    included = outcomes[outcomes["game_id"].astype(int).isin(game_ids)]
    completion_values = pd.to_datetime(
        included["last_completion_time"], utc=True, errors="coerce"
    ).dropna()
    last_completed = (
        completion_values.max().isoformat() if len(completion_values) else None
    )
    evaluation_uri = str(evaluation_ref.get("uri", ""))
    evaluation_bytes_sha = hashlib.sha256(
        storage.read_bytes(evaluation_uri)
    ).hexdigest()
    evaluation_row = _outcome_version_rows(
        candidate=candidate,
        season=season,
        week=week,
        freeze_run_id=attempt_run_id,
        outcome_version=outcome_version,
        score_completed_at=str((score.get("identity") or {}).get("as_of", "")),
        last_game_completed_at=last_completed,
        outcome_uri=outcome_uri,
        outcome_sha=outcome_sha,
        evaluation_uri=evaluation_uri,
        score_manifest_sha=score_raw_sha,
        evaluation_verified=True,
        supersedes_uri=str(version.get("supersedes_score_manifest_uri", "")),
    )
    parents = [
        {"role": "score_manifest", "uri": score_uri, "raw_sha256": score_raw_sha},
        {"role": "score_verifier", "uri": score_v_uri, "raw_sha256": score_receipt_sha},
        {"role": "outcome_version", "uri": outcome_uri, "raw_sha256": outcome_sha},
        {
            "role": "evaluation_dataset",
            "uri": evaluation_uri,
            "raw_sha256": evaluation_bytes_sha,
            "content_sha": str(evaluation_ref.get("content_sha", "")),
        },
    ]
    return (
        {"outcome_version": outcome_version, "score_uri": score_uri},
        outcomes,
        evaluation_row,
        parents,
    )


def collect_verified_sources(
    storage: Any,
    *,
    descriptor: Mapping[str, Any],
    expected_code_sha: str,
) -> dict[str, Any]:
    """Verify each 05 parent and produce normalized Contract 06 source rows."""
    if descriptor.get("schema_version") != EVIDENCE_INPUT_SCHEMA:
        raise EvidenceSourceError("unexpected Contract 06 evidence input schema")
    candidate = str(descriptor.get("candidate", ""))
    if not candidate:
        raise EvidenceSourceError("evidence input candidate is required")
    attempts: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    football_versions: dict[str, list[pd.DataFrame]] = {}
    football_latest: list[pd.DataFrame] = []
    parent_records: list[dict[str, Any]] = []
    quote_populations: list[pd.DataFrame] = []
    attempt_items = descriptor.get("attempts") or []
    if not isinstance(attempt_items, list):
        raise EvidenceSourceError("attempts must be an ordered list")
    for item in attempt_items:
        if not isinstance(item, Mapping):
            raise EvidenceSourceError("each attempt must be an object")
        readiness_uri = str(item.get("readiness_manifest_uri", ""))
        readiness_v_uri = str(item.get("readiness_verifier_uri", ""))
        season = int(item.get("season", 0))
        week = int(item.get("week", 0))
        attempt_run_id = str(item.get("run_id", ""))
        if not attempt_run_id:
            raise EvidenceSourceError("each attempt requires a freeze run_id")
        attempt_row: dict[str, Any] = {
            "candidate": candidate,
            "season": season,
            "week": week,
            "run_id": attempt_run_id,
            "diagnostic_only": True,
            "readiness_verified": False,
            "readiness_overall": "unverified",
            "readiness_blocker": "readiness evidence missing or invalid",
            "first_kickoff": None,
            "freeze_completed_at": None,
            "declared_games": 0,
            "paired_games": 0,
            "declared_game_ids": [],
            "paired_game_ids": [],
            "excluded_game_ids": [],
            "normal_coverage": False,
            "freeze_manifest_sha256": "",
            "freeze_ref": str(item.get("freeze_manifest_uri", "")),
        }
        readiness = None
        forecast = None
        all_predictions = pd.DataFrame()
        readiness_result: dict[str, Any] = {}
        readiness_raw_sha = ""
        try:
            readiness, readiness_raw = _json(
                storage, readiness_uri, label="readiness manifest"
            )
            if readiness.get("schema_version") != SHADOW_MANIFEST_SCHEMA:
                raise EvidenceSourceError("readiness manifest schema mismatch")
            _require_code(readiness, expected_code_sha, "readiness")
            readiness_result = verify_shadow_artifact(
                storage,
                manifest_uri=readiness_uri,
                expected_code_sha=expected_code_sha,
                environment="preview",
            )
            _, readiness_receipt_sha = _receipt(
                storage,
                uri=readiness_v_uri,
                manifest_uri=readiness_uri,
                expected_kind="readiness",
                reconstructed=readiness_result,
            )
            readiness_raw_sha = hashlib.sha256(readiness_raw).hexdigest()
            readiness_overall = str(readiness.get("readiness_overall", ""))
            if readiness_overall not in ("ready", "blocked"):
                raise EvidenceSourceError("readiness manifest verdict is invalid")
            if readiness_result.get("readiness_overall") != readiness_overall:
                raise EvidenceSourceError(
                    "readiness verifier verdict differs from manifest"
                )
            attempt_row.update(
                readiness_verified=True,
                readiness_overall=readiness_overall,
                readiness_blocker=_readiness_blocker(storage, readiness),
            )
            forecast, all_predictions, forecast_uri, forecast_sha = _live_forecast(
                storage,
                readiness=readiness,
                expected_code_sha=expected_code_sha,
            )
            if str(forecast["identity"]["run_id"]) != candidate:
                raise EvidenceSourceError(
                    "attempt candidate differs from live forecast"
                )
            parent_records.extend(
                [
                    {
                        "role": "readiness_manifest",
                        "uri": readiness_uri,
                        "raw_sha256": readiness_raw_sha,
                    },
                    {
                        "role": "readiness_verifier",
                        "uri": readiness_v_uri,
                        "raw_sha256": readiness_receipt_sha,
                    },
                    {
                        "role": "candidate_forecast_manifest",
                        "uri": forecast_uri,
                        "raw_sha256": forecast_sha,
                    },
                    {
                        "role": "candidate_forecast_predictions",
                        "uri": str((forecast.get("output_ref") or {}).get("uri", "")),
                        "content_sha": str(
                            (forecast.get("output_ref") or {}).get("content_sha", "")
                        ),
                    },
                ]
            )
        except Exception as exc:
            attempt_row["readiness_blocker"] = f"readiness_verification_failed: {exc}"
            attempts.append(attempt_row)
            continue

        freeze_uri = str(item.get("freeze_manifest_uri", ""))
        freeze_v_uri = str(item.get("freeze_verifier_uri", ""))
        schedule_uri = str(item.get("schedule_uri", ""))
        v4_uri = str(item.get("v4_prediction_uri", ""))
        freeze = None
        freeze_predictions = pd.DataFrame()
        freeze_raw_sha = ""
        schedule = pd.DataFrame()
        v4 = pd.DataFrame()
        freeze_failure = ""
        if freeze_uri:
            try:
                freeze, freeze_raw = _json(storage, freeze_uri, label="freeze manifest")
                if freeze.get("schema_version") != FREEZE_MANIFEST_SCHEMA:
                    raise EvidenceSourceError("freeze manifest schema mismatch")
                _require_code(freeze, expected_code_sha, "freeze")
                schedule, schedule_sha = _source_frame(
                    storage, schedule_uri, label="freeze schedule"
                )
                v4, v4_sha = _source_frame(storage, v4_uri, label="V4 predictions")
                freeze_result = verify_shadow_artifact(
                    storage,
                    manifest_uri=freeze_uri,
                    expected_code_sha=expected_code_sha,
                    environment="preview",
                    schedule_uri=schedule_uri,
                    v4_prediction_uri=v4_uri,
                )
                _, freeze_receipt_sha = _receipt(
                    storage,
                    uri=freeze_v_uri,
                    manifest_uri=freeze_uri,
                    expected_kind="freeze",
                    reconstructed=freeze_result,
                )
                freeze_raw_sha = hashlib.sha256(freeze_raw).hexdigest()
                freeze_record = _load_compact(
                    storage,
                    (freeze.get("output_refs") or {}).get("shadow_freeze") or {},
                    name="shadow_freeze",
                    dataset_key="shadow_freeze",
                )
                freeze_predictions = _load_partitioned(
                    storage,
                    (freeze.get("output_refs") or {}).get("shadow_prediction") or {},
                    name="shadow_prediction",
                    dataset_key="shadow_prediction",
                )
                row = freeze_record.iloc[0]
                if (
                    str(row["candidate"]) != candidate
                    or int(row["season"]) != season
                    or int(row["week"]) != week
                    or str(row["run_id"]) != attempt_run_id
                ):
                    raise EvidenceSourceError("freeze identity differs from attempt")
                declared_game_ids = sorted(
                    schedule.loc[
                        schedule["season"].eq(season) & schedule["week"].eq(week),
                        "game_id",
                    ]
                    .astype(int)
                    .unique()
                    .tolist()
                )
                paired_game_ids = sorted(
                    freeze_predictions["game_id"].astype(int).unique().tolist()
                )
                attempt_row.update(
                    diagnostic_only=bool(freeze_result.get("diagnostic_only", False)),
                    first_kickoff=str(row["first_kickoff"]),
                    freeze_completed_at=str(
                        (freeze.get("identity") or {}).get("as_of", "")
                    ),
                    declared_games=int(row["broader_count"]),
                    paired_games=int(row["paired_count"]),
                    declared_game_ids=declared_game_ids,
                    paired_game_ids=paired_game_ids,
                    excluded_game_ids=sorted(
                        set(declared_game_ids) - set(paired_game_ids)
                    ),
                    normal_coverage=(
                        int(row["broader_count"])
                        == len(
                            schedule[
                                schedule["season"].eq(season)
                                & schedule["week"].eq(week)
                            ]
                        )
                    ),
                    freeze_manifest_sha256=freeze_raw_sha,
                    freeze_ref=freeze_uri,
                )
                parent_records.extend(
                    [
                        {
                            "role": "freeze_manifest",
                            "uri": freeze_uri,
                            "raw_sha256": freeze_raw_sha,
                        },
                        {
                            "role": "freeze_verifier",
                            "uri": freeze_v_uri,
                            "raw_sha256": freeze_receipt_sha,
                        },
                        {
                            "role": "freeze_schedule",
                            "uri": schedule_uri,
                            "raw_sha256": schedule_sha,
                        },
                        {"role": "v4_predictions", "uri": v4_uri, "raw_sha256": v4_sha},
                    ]
                )
            except Exception as exc:
                freeze_failure = f"freeze_verification_failed: {exc}"
                attempt_row["readiness_blocker"] = "; ".join(
                    value
                    for value in (attempt_row["readiness_blocker"], freeze_failure)
                    if value
                )
        attempts.append(attempt_row)
        if freeze is None:
            continue

        versions = item.get("score_versions") or []
        if not isinstance(versions, list):
            raise EvidenceSourceError("score_versions must be an ordered list")
        previous_score_uri = ""
        seen_versions: set[str] = set()
        attempt_versions: list[pd.DataFrame] = []
        for version in versions:
            score_uri = str(version.get("score_manifest_uri", ""))
            supersedes = str(version.get("supersedes_score_manifest_uri", ""))
            if supersedes != previous_score_uri:
                raise EvidenceSourceError(
                    "score correction chain must append and link the previous score manifest"
                )
            outcome_version = ""
            try:
                score_info, outcomes, evaluation_row, score_parents = (
                    _load_verified_score_version(
                        storage,
                        version=version,
                        freeze_uri=freeze_uri,
                        schedule_uri=schedule_uri,
                        v4_uri=v4_uri,
                        freeze_predictions=freeze_predictions,
                        season=season,
                        week=week,
                        attempt_run_id=attempt_run_id,
                        candidate=candidate,
                        expected_code_sha=expected_code_sha,
                    )
                )
                outcome_version = score_info["outcome_version"]
                if outcome_version in seen_versions:
                    raise EvidenceSourceError(
                        "score outcome versions must be unique within a freeze"
                    )
                seen_versions.add(outcome_version)
                evaluations.append(evaluation_row)
                if readiness_overall == "ready" and not attempt_row["diagnostic_only"]:
                    metrics_rows = _football_rows(
                        forecast=forecast,
                        all_predictions=all_predictions,
                        freeze_predictions=freeze_predictions,
                        outcomes=outcomes,
                        v4_predictions=v4,
                        season=season,
                        week=week,
                    )
                    key = f"{season}-w{week}:{attempt_run_id}:{outcome_version}"
                    football_versions.setdefault(key, []).append(metrics_rows)
                    attempt_versions.append(metrics_rows)
                parent_records.extend(score_parents)
            except Exception as exc:
                if isinstance(exc, EvidenceSourceError) and "correction chain" in str(
                    exc
                ):
                    raise
                attempt_row["readiness_blocker"] = "; ".join(
                    value
                    for value in (
                        attempt_row["readiness_blocker"],
                        f"score_verification_failed: {exc}",
                    )
                    if value
                )
                try:
                    failed_score, failed_raw = _json(
                        storage, score_uri, label="failed score manifest"
                    )
                    outcome_version = str(
                        (failed_score.get("score_summary") or {}).get(
                            "outcome_version", ""
                        )
                    )
                    failed_sha = hashlib.sha256(failed_raw).hexdigest()
                    parent_records.append(
                        {
                            "role": "unverified_score_manifest",
                            "uri": score_uri,
                            "raw_sha256": failed_sha,
                        }
                    )
                except Exception:
                    failed_sha = ""
                    outcome_version = ""
                evaluations.append(
                    _outcome_version_rows(
                        candidate=candidate,
                        season=season,
                        week=week,
                        freeze_run_id=attempt_run_id,
                        outcome_version=outcome_version,
                        score_completed_at="",
                        last_game_completed_at=None,
                        outcome_uri=str(version.get("outcome_uri", "")),
                        outcome_sha="",
                        evaluation_uri="",
                        score_manifest_sha=failed_sha,
                        evaluation_verified=False,
                        supersedes_uri=supersedes,
                    )
                )
            if score_uri:
                previous_score_uri = score_uri
        if attempt_versions:
            football_latest.append(attempt_versions[-1])

    attempts_frame = pd.DataFrame.from_records(attempts)
    evaluations_frame = pd.DataFrame.from_records(evaluations)
    football_by_version = {
        key: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        for key, frames in football_versions.items()
    }
    quotes_config = descriptor.get("quotes") or {}
    review_config = descriptor.get("review") or {}
    review = None
    if review_config.get("uri"):
        review, review_raw = _json(
            storage, str(review_config["uri"]), label="Contract 06 review input"
        )
        try:
            verify_signed_payload(review, label="Contract 06 review input")
        except ValueError as exc:
            raise EvidenceSourceError(str(exc)) from exc
        if (
            review.get("schema_version") != "data_first_v5_evidence_review_v1"
            or review.get("state") != "reviewed"
            or review.get("candidate") != candidate
        ):
            raise EvidenceSourceError("review input is not signed for this candidate")
        parent_records.append(
            {
                "role": "recommendation_review",
                "uri": str(review_config["uri"]),
                "raw_sha256": hashlib.sha256(review_raw).hexdigest(),
            }
        )
    if quotes_config.get("manifest_uri"):
        quote_manifest_uri = str(quotes_config["manifest_uri"])
        quote_manifest, quote_manifest_raw = _json(
            storage, quote_manifest_uri, label="authentic quote manifest"
        )
        try:
            verify_signed_payload(quote_manifest, label="authentic quote manifest")
        except ValueError as exc:
            raise EvidenceSourceError(str(exc)) from exc
        if (
            quote_manifest.get("schema_version") != AUTHENTIC_QUOTE_MANIFEST_SCHEMA
            or quote_manifest.get("state") != "captured"
            or (quote_manifest.get("identity") or {}).get("environment") != "preview"
            or quote_manifest.get("authentic_source") is not True
            or not (quote_manifest.get("provider") or "").strip()
            or quote_manifest.get("production_activation_authorized") is not False
        ):
            raise EvidenceSourceError(
                "quote source is not a signed authentic Preview capture"
            )
        quote_ref = quote_manifest.get("output_ref") or {}
        quotes = _dataset(storage, quote_ref, label="authentic quote records")
        if (
            not quotes.empty
            and not quotes["provider"]
            .astype(str)
            .eq(str(quote_manifest["provider"]))
            .all()
        ):
            raise EvidenceSourceError(
                "quote record provider differs from its authentic capture manifest"
            )
        quote_sha = hashlib.sha256(quote_manifest_raw).hexdigest()
        quote_cutoff = str(quotes_config.get("cutoff", ""))
        if not quote_cutoff:
            raise EvidenceSourceError("authentic quote cutoff is required")
        manifest_as_of = pd.Timestamp(
            str((quote_manifest.get("identity") or {}).get("as_of", ""))
        )
        cutoff_ts = pd.Timestamp(quote_cutoff)
        if (
            manifest_as_of.tzinfo is None
            or cutoff_ts.tzinfo is None
            or cutoff_ts.tz_convert("UTC") > manifest_as_of.tz_convert("UTC")
        ):
            raise EvidenceSourceError(
                "quote cutoff must be timezone-aware and no later than its capture manifest"
            )
        quote_populations = football_latest
    else:
        quotes = pd.DataFrame()
        quote_sha = ""
        quote_cutoff = str(descriptor.get("as_of", ""))
        quote_populations = football_latest
    football_quotes_population = (
        pd.concat(quote_populations, ignore_index=True)
        if quote_populations
        else pd.DataFrame(columns=["game_id", "target"])
    )
    if quotes_config.get("manifest_uri"):
        parent_records.append(
            {
                "role": "authentic_quotes",
                "uri": str(quotes_config["manifest_uri"]),
                "raw_sha256": quote_sha,
            }
        )
        parent_records.append(
            {
                "role": "authentic_quote_records",
                "uri": str((quote_manifest.get("output_ref") or {}).get("uri", "")),
                "content_sha": str(
                    (quote_manifest.get("output_ref") or {}).get("content_sha", "")
                ),
            }
        )
    return {
        "candidate": candidate,
        "attempts": attempts_frame,
        "evaluations": evaluations_frame,
        "football_by_version": football_by_version,
        "football_quote_population": football_quotes_population,
        "quotes": quotes,
        "quote_cutoff": quote_cutoff,
        "quote_raw_sha256": quote_sha,
        "parents": parent_records,
        "review": review,
        "football_latest": (
            pd.concat(football_latest, ignore_index=True)
            if football_latest
            else pd.DataFrame(
                columns=[
                    "season",
                    "week",
                    "game_id",
                    "target",
                    "actual",
                    "v5_mean",
                    "v5_variance",
                    "v4_mean",
                    "completed_game_stage",
                    "broader_population",
                    "paired_population",
                ]
            )
        ),
    }
