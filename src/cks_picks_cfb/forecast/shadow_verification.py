"""Verifier-owned V5 shadow reconstruction and artifact verification.

This module is deliberately independent of the producer: it must not import
``cks_picks_cfb.forecast.shadow`` (the producer), any research runner, or the
forecast math modules ``offsets``/``heads``/``horizons``/``calibration``. It
may share only ``data_first_shadow_v1`` constants/schemas, generic ``lake``
readers, ``data_first_phase2d`` signing, ``schema_contracts``, and ``storage``.
Every availability, timing, population, prediction, score, and counter value is
re-derived here from source artifacts so a producer defect cannot mirror
itself into agreement.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    LIVE_FORECAST_COLUMNS,
    LIVE_FORECAST_DATASET,
    LIVE_FORECAST_MANIFEST_SCHEMA,
)
from cks_picks_cfb.data.data_first_phase2d import (
    signed_payload,
    verify_signed_payload,
)
from cks_picks_cfb.data.data_first_shadow_v1 import (
    DIAGNOSTIC_CLASS,
    FREEZE_HARD_LEAD_SECONDS,
    MINIMUM_PAIRED_GAMES,
    READINESS_COLUMNS,
    REQUIRED_FORECAST_MANIFEST_URI,
    REQUIRED_MEASUREMENT_MANIFEST_URI,
    REQUIRED_RATING_MANIFEST_URI,
    REQUIRED_REPAIR_MANIFEST_URI,
    SCORE_STABILIZATION_SECONDS,
    SHADOW_DATASETS,
    SHADOW_MANIFEST_SCHEMA,
    SHADOW_PREDICTION_COLUMNS,
    shadow_identity,
    verify_candidate_parents,
)
from cks_picks_cfb.data.lake import (
    DatasetRef,
    PartitionedDatasetRef,
    canonical_frame_digest,
    iter_partitioned_dataset,
    read_dataset,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.storage import StorageError

VERIFICATION_MANIFEST_SCHEMA = "data_first_shadow_verification_v1"
VERIFICATION_MANIFEST_NAME = "verification/verifier-manifest.json"
FREEZE_MANIFEST_SCHEMA = "data_first_shadow_freeze_manifest_v1"
SCORE_MANIFEST_SCHEMA = "data_first_shadow_score_manifest_v1"
REHEARSAL_MANIFEST_SCHEMA = "data_first_shadow_rehearsal_manifest_v1"
MANDATORY_READINESS_SOURCES = (
    "candidate",
    "schedule",
    "completed_games",
    "scoring",
    "team_states",
)
NEUTRAL_PRIOR_FALLBACK = "neutral"


class ShadowVerificationError(ValueError):
    """Raised when verification cannot proceed or stored outputs disagree."""


# ---------------------------------------------------------------------------
# Generic helpers (verifier-owned; no producer imports)
# ---------------------------------------------------------------------------


def _read_json(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    if not uri:
        raise ShadowVerificationError("manifest URI is empty")
    raw = storage.read_bytes(uri)
    try:
        return json.loads(raw), raw
    except json.JSONDecodeError as exc:
        raise ShadowVerificationError(f"unreadable manifest: {uri}") from exc


def _read_frame(storage: Any, uri: str, *, name: str) -> pd.DataFrame:
    if not uri:
        raise ShadowVerificationError(f"{name} source URI is required")
    raw = storage.read_bytes(uri)
    try:
        return pd.read_parquet(io.BytesIO(raw))
    except Exception:
        try:
            return pd.DataFrame(json.loads(raw))
        except Exception as exc:
            raise ShadowVerificationError(
                f"cannot load {name} source from {uri}"
            ) from exc


def _dataset_ref(value: Mapping[str, Any], *, name: str) -> DatasetRef:
    missing = [
        key
        for key in ("dataset", "version_id", "schema_version", "content_sha", "uri")
        if not value.get(key)
    ]
    if missing:
        raise ShadowVerificationError(f"{name} output ref is missing {missing}")
    return DatasetRef(
        dataset=str(value["dataset"]),
        version_id=str(value["version_id"]),
        schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]),
        uri=str(value["uri"]),
    )


def _partitioned_ref(
    storage: Any, value: Mapping[str, Any], *, name: str
) -> PartitionedDatasetRef:
    if value.get("artifact_kind") != "partitioned_dataset_v1":
        raise ShadowVerificationError(f"{name} output is not a partitioned dataset")
    part_manifest = json.loads(storage.read_bytes(str(value.get("uri", ""))))
    ref = _dataset_ref(value, name=name)
    partition_keys = tuple(
        part_manifest.get("partition_keys") or value.get("partition_keys") or ()
    )
    row_count = int(value.get("row_count", part_manifest.get("row_count", -1)))
    return PartitionedDatasetRef(
        artifact_kind="partitioned_dataset_v1",
        dataset=ref.dataset,
        version_id=ref.version_id,
        schema_version=ref.schema_version,
        content_sha=ref.content_sha,
        records_sha=str(part_manifest.get("records_sha", "")),
        uri=ref.uri,
        row_count=row_count,
        partition_keys=partition_keys,
    )


def _load_ref_frame(
    storage: Any, value: Mapping[str, Any], *, name: str
) -> pd.DataFrame:
    """Load a compact or partitioned output ref through generic lake readers."""
    if value.get("artifact_kind") == "partitioned_dataset_v1":
        ref = _partitioned_ref(storage, value, name=name)
        frames = list(iter_partitioned_dataset(storage, ref))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return read_dataset(storage, _dataset_ref(value, name=name))


def _load_compact(
    storage: Any, value: Mapping[str, Any], *, name: str, dataset_key: str
) -> pd.DataFrame:
    dataset, schema_version = SHADOW_DATASETS[dataset_key]
    if value.get("dataset") != dataset or value.get("schema_version") != schema_version:
        raise ShadowVerificationError(f"{name} output ref identity mismatch")
    if value.get("artifact_kind") not in (None, "dataset_v1"):
        raise ShadowVerificationError(f"{name} output must be a compact dataset")
    frame = read_dataset(storage, _dataset_ref(value, name=name))
    validate_frame(frame, schema_for(dataset, schema_version))
    if int(value.get("row_count", -1)) != len(frame):
        raise ShadowVerificationError(f"{name} row count disagrees with stored data")
    return frame


def _load_partitioned(
    storage: Any, value: Mapping[str, Any], *, name: str, dataset_key: str
) -> pd.DataFrame:
    dataset, schema_version = SHADOW_DATASETS[dataset_key]
    if value.get("dataset") != dataset or value.get("schema_version") != schema_version:
        raise ShadowVerificationError(f"{name} output ref identity mismatch")
    ref = _partitioned_ref(storage, value, name=name)
    frames = list(iter_partitioned_dataset(storage, ref))
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    validate_frame(frame, schema_for(dataset, schema_version))
    if int(value.get("row_count", -1)) != len(frame):
        raise ShadowVerificationError(f"{name} row count disagrees with stored data")
    return frame


def _frame_digest(frame: pd.DataFrame, columns: Sequence[str]) -> str:
    return canonical_frame_digest(frame, columns=list(columns))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ShadowVerificationError(message)


def _hex64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


# ---------------------------------------------------------------------------
# Identity and parent reconciliation (all manifest kinds)
# ---------------------------------------------------------------------------


def _verify_identity(identity: Mapping[str, Any], *, expected_code_sha: str) -> str:
    _require(identity.get("environment") == "preview", "identity is not preview")
    _require(
        identity.get("code_sha") == expected_code_sha,
        "identity code SHA does not match the expected committed SHA",
    )
    recorded = identity.get("identity_sha256")
    _require(_hex64(recorded), "identity digest is missing or malformed")
    rebuilt = shadow_identity(
        run_id=str(identity.get("run_id", "")),
        as_of=str(identity.get("as_of", "")),
        code_sha=str(identity.get("code_sha", "")),
        config_sha=str(identity.get("config_sha", "")),
        parents=dict(identity.get("parents") or {}),
    )
    _require(
        rebuilt["identity_sha256"] == recorded,
        "identity digest does not match verifier recomputation",
    )
    return str(recorded)


def _verify_parent_chain(storage: Any, identity: Mapping[str, Any]) -> dict[str, Any]:
    parents = identity.get("parents") or {}
    forecast, forecast_raw = _read_json(
        storage, str(parents.get("forecast_manifest_uri", ""))
    )
    rating, rating_raw = _read_json(
        storage, str(parents.get("rating_manifest_uri", ""))
    )
    measurement, measurement_raw = _read_json(
        storage, str(parents.get("measurement_manifest_uri", ""))
    )
    repair, repair_raw = _read_json(
        storage, str(parents.get("repair_manifest_uri", ""))
    )
    bridge = None
    bridge_raw = b""
    if forecast.get("schema_version") == LIVE_FORECAST_MANIFEST_SCHEMA:
        bridge_uri = str((forecast.get("parents") or {}).get("bridge_uri", ""))
        _require(bool(bridge_uri), "live forecast does not bind its 11C bridge")
        bridge, bridge_raw = _read_json(storage, bridge_uri)
    try:
        return verify_candidate_parents(
            forecast,
            rating,
            measurement,
            repair,
            forecast_manifest_uri=str(parents.get("forecast_manifest_uri", "")),
            forecast_raw_sha256=hashlib.sha256(forecast_raw).hexdigest(),
            rating_manifest_uri=str(parents.get("rating_manifest_uri", "")),
            rating_raw_sha256=hashlib.sha256(rating_raw).hexdigest(),
            measurement_manifest_uri=str(parents.get("measurement_manifest_uri", "")),
            measurement_raw_sha256=hashlib.sha256(measurement_raw).hexdigest(),
            repair_manifest_uri=str(parents.get("repair_manifest_uri", "")),
            repair_raw_sha256=hashlib.sha256(repair_raw).hexdigest(),
            bridge=bridge,
            bridge_raw_sha256=(
                hashlib.sha256(bridge_raw).hexdigest() if bridge_raw else ""
            ),
        )
    except ValueError as exc:
        raise ShadowVerificationError(f"parent chain rejected: {exc}") from exc


def _require_pinned_manifest_uris(
    parents: Mapping[str, Any], *, live: bool = False
) -> None:
    if live:
        required = {
            "forecast_manifest_uri",
            "forecast_raw_sha256",
            "rating_manifest_uri",
            "rating_raw_sha256",
            "measurement_manifest_uri",
            "measurement_raw_sha256",
            "repair_manifest_uri",
            "repair_raw_sha256",
        }
        _require(
            required <= set(parents) and all(parents.get(key) for key in required),
            "live readiness must bind exact refreshed forecast, 07, 08, and repair parents",
        )
        return
    _require(
        parents.get("forecast_manifest_uri") == REQUIRED_FORECAST_MANIFEST_URI,
        "forecast parent is not the certified 04 candidate",
    )
    _require(
        parents.get("rating_manifest_uri") == REQUIRED_RATING_MANIFEST_URI,
        "rating parent is not the certified 03 retained manifest",
    )
    _require(
        parents.get("measurement_manifest_uri") == REQUIRED_MEASUREMENT_MANIFEST_URI,
        "measurement parent is not the certified R6 manifest",
    )
    _require(
        parents.get("repair_manifest_uri") == REQUIRED_REPAIR_MANIFEST_URI,
        "repair parent is not the certified repair-v2 manifest",
    )


# ---------------------------------------------------------------------------
# Readiness reconstruction (verifier-owned availability logic)
# ---------------------------------------------------------------------------


def _verifier_timing_class(as_of: str, cutoff: str) -> str:
    source_time = pd.Timestamp(as_of)
    cutoff_time = pd.Timestamp(cutoff)
    if source_time.tzinfo is None or cutoff_time.tzinfo is None:
        raise ShadowVerificationError("timing evidence must be timezone-aware")
    return (
        "pre_cutoff"
        if source_time.astimezone(cutoff_time.tzinfo) <= cutoff_time
        else "post_cutoff"
    )


def _load_readiness_sources(
    storage: Any, *, chain: Mapping[str, Any]
) -> dict[str, pd.DataFrame]:
    """Read readiness source datasets through generic lake readers only."""
    measurement = chain["measurement"]
    repair = chain["repair"]
    rating = chain["rating"]

    if (chain["forecast"].get("schema_version")) == LIVE_FORECAST_MANIFEST_SCHEMA:
        population = _load_ref_frame(
            storage,
            (measurement.get("output_refs") or {}).get("population") or {},
            name="measurement:population",
        )
        scoring_events = _load_ref_frame(
            storage,
            (measurement.get("output_refs") or {}).get("scoring_events") or {},
            name="measurement:scoring_events",
        )
        schedule_uri = str(
            (chain["forecast"].get("parents") or {}).get("schedule_ref_uri", "")
        )
        _require(bool(schedule_uri), "live forecast lacks its full schedule source")
        schedule_raw = storage.read_bytes(schedule_uri)
        expected_schedule_sha = str(
            (chain["forecast"].get("parents") or {}).get("schedule_raw_sha256", "")
        )
        _require(
            hashlib.sha256(schedule_raw).hexdigest() == expected_schedule_sha,
            "live forecast schedule bytes differ from its parent checksum",
        )
        full_schedule = _read_frame(storage, schedule_uri, name="live schedule")
        _require(
            {"season", "week", "game_id"} <= set(full_schedule),
            "live full schedule lacks game identity columns",
        )
        _require(
            set(
                map(
                    tuple,
                    full_schedule.loc[
                        full_schedule["season"].eq(2026),
                        ["season", "week", "game_id"],
                    ]
                    .astype(int)
                    .to_numpy(),
                )
            )
            == set(
                map(
                    tuple,
                    population.loc[
                        population["season"].eq(2026),
                        ["season", "week", "game_id"],
                    ]
                    .astype(int)
                    .to_numpy(),
                )
            ),
            "live schedule and Contract 07 population membership differ",
        )
        team_states = _load_ref_frame(
            storage,
            (rating.get("output_refs") or {}).get("team_states") or {},
            name="rating:team_states",
        )
        priors = _load_ref_frame(
            storage,
            (rating.get("output_refs") or {}).get("priors") or {},
            name="rating:priors",
        )
        outcomes = population[
            population.get(
                "schedule_completed", pd.Series(False, index=population.index)
            ).astype(bool)
            & population.get(
                "outcome_valid", pd.Series(False, index=population.index)
            ).astype(bool)
        ].copy()
        if {"season", "week", "game_id"} <= set(outcomes):
            outcomes = outcomes.loc[:, ["season", "week", "game_id"]].assign(
                completed=True
            )
        else:
            outcomes = pd.DataFrame(columns=["season", "week", "game_id", "completed"])
        return {
            "schedule": population,
            "outcomes": outcomes,
            "scoring_events": scoring_events,
            "team_states": team_states,
            "priors": priors,
        }

    population = _load_ref_frame(
        storage,
        (measurement.get("output_refs") or {}).get("population") or {},
        name="measurement:population",
    )
    scoring_events = _load_ref_frame(
        storage,
        (measurement.get("output_refs") or {}).get("scoring_events") or {},
        name="measurement:scoring_events",
    )

    eligibility_uri = str(
        ((repair.get("parents") or {}).get("core_eligibility") or {}).get("uri", "")
    )
    _require(bool(eligibility_uri), "repair parent lacks core eligibility lineage")
    eligibility, _eligibility_raw = _read_json(storage, eligibility_uri)
    try:
        verify_signed_payload(eligibility, label="core eligibility")
    except ValueError as exc:
        raise ShadowVerificationError(f"core eligibility rejected: {exc}") from exc
    _require(
        eligibility.get("state") == "eligible"
        and eligibility.get("production_activation_authorized") is False,
        "core eligibility is not sealed Preview evidence",
    )
    outcome_refs = []
    for value in eligibility.get("phase3_input_refs") or []:
        if (
            str(value.get("dataset")) == "game_outcomes"
            and value.get("eligible") is True
        ):
            outcome_refs.append(value)
    _require(bool(outcome_refs), "core eligibility exposes no game outcome sources")
    outcomes = pd.concat(
        [
            read_dataset(
                storage,
                _dataset_ref(value, name="core:game_outcomes"),
            )
            for value in outcome_refs
        ],
        ignore_index=True,
        sort=False,
    )

    team_states = _load_ref_frame(
        storage,
        (rating.get("output_refs") or {}).get("team_states") or {},
        name="rating:team_states",
    )
    priors = _load_ref_frame(
        storage,
        (rating.get("output_refs") or {}).get("priors") or {},
        name="rating:priors",
    )
    return {
        "schedule": population,
        "outcomes": outcomes,
        "scoring_events": scoring_events,
        "team_states": team_states,
        "priors": priors,
    }


def _verify_live_prediction_coverage(
    storage: Any,
    *,
    forecast: Mapping[str, Any],
    population: pd.DataFrame,
    season: int,
    week: int,
) -> None:
    """Verify live output bytes and exact game/target coverage independently."""
    output_ref = forecast.get("output_ref") or {}
    _require(
        output_ref.get("dataset") == LIVE_FORECAST_DATASET[0]
        and output_ref.get("schema_version") == LIVE_FORECAST_DATASET[1],
        "live forecast output identity mismatch",
    )
    predictions = _load_ref_frame(storage, output_ref, name="live forecast predictions")
    _require(
        int(output_ref.get("row_count", -1))
        == len(predictions)
        == int(forecast.get("row_count", -2)),
        "live forecast output row count mismatch",
    )
    _require(
        set(LIVE_FORECAST_COLUMNS) <= set(predictions),
        "live forecast rows lack required outcome-free fields",
    )
    _require(
        not ({"actual", "absolute_error", "gaussian_crps"} & set(predictions)),
        "live forecast output contains outcome-bearing fields",
    )
    _require(
        not predictions.duplicated(
            ["run_id", "season", "week", "game_id", "target"]
        ).any(),
        "live forecast output duplicates a prediction key",
    )
    _require(
        set(predictions["season"].astype(int)) == {2026}
        and predictions["target"].isin(("margin", "total")).all(),
        "live forecast output includes an invalid season or target",
    )
    _require(
        predictions["run_id"]
        .astype(str)
        .eq(str((forecast.get("identity") or {}).get("run_id", "")))
        .all()
        and predictions["timing_class"].eq("live").all(),
        "live forecast output identity or timing class mismatch",
    )
    for column in (
        "mean",
        "variance",
        "interval_lower_95",
        "interval_upper_95",
        "offset",
    ):
        values = pd.to_numeric(predictions[column], errors="coerce").to_numpy(float)
        _require(
            np.isfinite(values).all(), f"live forecast {column} contains invalid values"
        )
    _require(
        (pd.to_numeric(predictions["variance"], errors="coerce") > 0).all(),
        "live forecast variance must be positive",
    )
    _require(
        canonical_frame_digest(predictions, columns=list(LIVE_FORECAST_COLUMNS))
        == str(forecast.get("prediction_records_sha256", "")),
        "live forecast output digest mismatch",
    )
    declared = population[population["season"].eq(season) & population["week"].eq(week)]
    if "forecast_eligible" in declared:
        declared = declared[declared["forecast_eligible"].astype(bool)]
    expected_games = set(declared["game_id"].astype(int))
    observed_games = set(
        predictions.loc[
            predictions["season"].eq(season) & predictions["week"].eq(week),
            "game_id",
        ].astype(int)
    )
    _require(
        bool(expected_games), f"no declared schedule rows for {season} week {week}"
    )
    if "kickoff_utc" in declared:
        kickoff = pd.to_datetime(declared["kickoff_utc"], utc=True, errors="coerce")
        cutoff = pd.Timestamp(str((forecast.get("identity") or {}).get("as_of", "")))
        _require(
            not kickoff.isna().any()
            and cutoff.tzinfo is not None
            and kickoff.gt(cutoff.tz_convert("UTC")).all(),
            "live forecast includes a game not strictly after its source cutoff",
        )
    _require(
        expected_games == observed_games,
        "live forecast game coverage differs from Contract 07 schedule",
    )
    expected_pairs = {
        (game, target) for game in expected_games for target in ("margin", "total")
    }
    actual_pairs = set(
        map(
            tuple,
            predictions.loc[
                predictions["season"].eq(season) & predictions["week"].eq(week),
                ["game_id", "target"],
            ]
            .assign(game_id=lambda frame: frame["game_id"].astype(int))
            .to_numpy(),
        )
    )
    _require(
        expected_pairs == actual_pairs,
        "live forecast target coverage differs from Contract 07 schedule",
    )


def _live_readiness_candidate_status(
    storage: Any,
    *,
    forecast: Mapping[str, Any],
    population: pd.DataFrame,
    season: int,
    week: int,
    cutoff: str,
) -> dict[str, str]:
    """Independently derive the live candidate readiness row, including blockers."""
    try:
        predictions = _load_ref_frame(
            storage,
            forecast.get("output_ref") or {},
            name="live forecast predictions",
        )
        declared = population[
            population["season"].eq(season) & population["week"].eq(week)
        ]
        if "forecast_eligible" in declared:
            declared = declared[declared["forecast_eligible"].astype(bool)]
        expected_games = set(declared["game_id"].astype(int))
        if not expected_games:
            return {
                "status": "unavailable",
                "timing_class": "missing",
                "fallback": "",
                "blocked_reason": f"no schedule rows for {season} week {week}",
            }
        expected_pairs = {
            (game_id, target)
            for game_id in expected_games
            for target in ("margin", "total")
        }
        observed_pairs = set(
            map(
                tuple,
                predictions.loc[
                    predictions["season"].eq(season) & predictions["week"].eq(week),
                    ["game_id", "target"],
                ]
                .assign(game_id=lambda frame: frame["game_id"].astype(int))
                .to_numpy(),
            )
        )
        if observed_pairs != expected_pairs:
            missing = sorted(expected_pairs - observed_pairs)
            extra = sorted(observed_pairs - expected_pairs)
            return {
                "status": "unavailable",
                "timing_class": "missing",
                "fallback": "",
                "blocked_reason": (
                    "live forecast population mismatch; "
                    f"missing game/target={missing[:5]}, extra game/target={extra[:5]}"
                ),
            }
        _verify_live_prediction_coverage(
            storage,
            forecast=forecast,
            population=population,
            season=season,
            week=week,
        )
        forecast_as_of = str((forecast.get("identity") or {}).get("as_of", ""))
        return {
            "status": "available",
            "timing_class": _verifier_timing_class(forecast_as_of, cutoff),
            "fallback": "",
            "blocked_reason": "",
        }
    except (KeyError, OSError, ValueError, TypeError, StorageError):
        return {
            "status": "unavailable",
            "timing_class": "missing",
            "fallback": "",
            "blocked_reason": "live forecast output unavailable or invalid",
        }


def _reconstruct_readiness(
    *,
    cutoff: str,
    chain: Mapping[str, Any],
    stored: pd.DataFrame,
    sources: Mapping[str, Any],
    candidate_status: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Re-derive every readiness row and verdict from source artifacts."""
    _require(len(stored) > 0, "stored readiness record is empty")
    _require(bool(cutoff), "readiness assessment cutoff is missing")
    season = int(stored["season"].iloc[0])
    week = int(stored["week"].iloc[0])
    candidate = str(stored["candidate"].iloc[0])
    run_id = str(stored["run_id"].iloc[0])
    forecast = chain["forecast"]
    measurement_as_of = str(chain["measurement"]["identity"]["as_of"])
    rating_as_of = str(chain["rating"]["identity"]["as_of"])

    schedule: pd.DataFrame = sources["schedule"]
    outcomes: pd.DataFrame = sources["outcomes"]
    scoring_events: pd.DataFrame = sources["scoring_events"]
    team_states: pd.DataFrame = sources["team_states"]
    priors: pd.DataFrame = sources["priors"]

    rows: dict[str, dict[str, Any]] = {}

    candidate_as_of = str((forecast.get("identity") or {}).get("as_of") or "")
    _require(bool(candidate_as_of), "forecast manifest as-of is missing")
    rows["candidate"] = (
        dict(candidate_status)
        if candidate_status is not None
        else {
            "status": "available",
            "timing_class": _verifier_timing_class(candidate_as_of, cutoff),
            "fallback": "",
            "blocked_reason": "",
        }
    )

    week_schedule = (
        schedule[schedule["season"].eq(season) & schedule["week"].eq(week)]
        if {"season", "week"}.issubset(schedule.columns)
        else pd.DataFrame()
    )
    if week_schedule.empty:
        rows["schedule"] = {
            "status": "unavailable",
            "timing_class": "missing",
            "fallback": "",
            "blocked_reason": f"no schedule rows for {season} week {week}",
        }
    else:
        rows["schedule"] = {
            "status": "available",
            "timing_class": _verifier_timing_class(measurement_as_of, cutoff),
            "fallback": "",
            "blocked_reason": "",
        }

    prior_outcomes = pd.DataFrame()
    if not outcomes.empty and "season" in outcomes:
        prior_outcomes = outcomes[outcomes["season"].lt(season)]
        if "week" in outcomes:
            prior_outcomes = pd.concat(
                [
                    prior_outcomes,
                    outcomes[outcomes["season"].eq(season) & outcomes["week"].lt(week)],
                ]
            )
    if prior_outcomes.empty:
        rows["completed_games"] = {
            "status": "unavailable",
            "timing_class": "missing",
            "fallback": "",
            "blocked_reason": "no finalized outcomes precede the slate",
        }
    else:
        rows["completed_games"] = {
            "status": "available",
            "timing_class": _verifier_timing_class(measurement_as_of, cutoff),
            "fallback": "",
            "blocked_reason": "",
        }

    if scoring_events.empty:
        rows["scoring"] = {
            "status": "unavailable",
            "timing_class": "missing",
            "fallback": "",
            "blocked_reason": "scoring ledger is empty",
        }
    else:
        rows["scoring"] = {
            "status": "available",
            "timing_class": _verifier_timing_class(measurement_as_of, cutoff),
            "fallback": "",
            "blocked_reason": "",
        }

    if priors.empty:
        rows["priors"] = {
            "status": "unavailable",
            "timing_class": "missing",
            "fallback": NEUTRAL_PRIOR_FALLBACK,
            "blocked_reason": "",
        }
    else:
        rows["priors"] = {
            "status": "available",
            "timing_class": _verifier_timing_class(rating_as_of, cutoff),
            "fallback": "",
            "blocked_reason": "",
        }

    has_season_states = (
        not team_states.empty
        and "season" in team_states
        and not team_states[team_states["season"].eq(season)].empty
    )
    if has_season_states:
        rows["team_states"] = {
            "status": "available",
            "timing_class": _verifier_timing_class(rating_as_of, cutoff),
            "fallback": "",
            "blocked_reason": "",
        }
    else:
        rows["team_states"] = {
            "status": "unavailable",
            "timing_class": "missing",
            "fallback": "",
            "blocked_reason": f"no team states for {season}",
        }

    overall = "ready"
    for source in MANDATORY_READINESS_SOURCES:
        row = rows[source]
        if row["status"] != "available" or row["timing_class"] != "pre_cutoff":
            overall = "blocked"
            break

    rebuilt = pd.DataFrame.from_records(
        [
            {
                "candidate": candidate,
                "season": season,
                "week": week,
                "run_id": run_id,
                "source": source,
                **rows[source],
                "overall": overall,
            }
            for source in sorted(rows)
        ]
    )
    validate_frame(rebuilt, schema_for(*SHADOW_DATASETS["readiness"]))
    return {"frame": rebuilt, "overall": overall}


def _compare_readiness(
    stored: pd.DataFrame, rebuilt: pd.DataFrame, *, manifest_overall: str
) -> None:
    _require(
        set(stored["source"]) == set(rebuilt["source"]),
        "readiness source set disagrees with verifier reconstruction",
    )
    stored_sorted = stored.sort_values("source").reset_index(drop=True)
    rebuilt_sorted = rebuilt.sort_values("source").reset_index(drop=True)
    for column in READINESS_COLUMNS:
        left = stored_sorted[column].astype(str).tolist()
        right = rebuilt_sorted[column].astype(str).tolist()
        _require(
            left == right,
            f"readiness column {column} disagrees with verifier reconstruction",
        )
    stored_overall = str(stored_sorted["overall"].iloc[0])
    _require(
        stored_overall == manifest_overall,
        "stored readiness verdict disagrees with the manifest verdict",
    )


# ---------------------------------------------------------------------------
# Replay reconstruction (structural evidence; math modules stay forbidden)
# ---------------------------------------------------------------------------


def _reconstruct_replay(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate recorded frozen-replay evidence without recomputing heads."""
    digest = payload.get("replay_sha256")
    if digest is not None:
        _require(_hex64(digest), "recorded replay digest is malformed")
    identical = payload.get("byte_identical")
    if identical is not None:
        _require(identical is True, "replay byte-identity did not hold")
    perturbation = payload.get("perturbation_invariance")
    if perturbation is not None:
        _require(perturbation is True, "recorded perturbation invariance did not hold")
    return {
        "replay_sha256": digest,
        "byte_identical": identical,
        "perturbation_invariance": perturbation,
    }


# ---------------------------------------------------------------------------
# Freeze reconstruction (verifier-owned timing/population/prediction math)
# ---------------------------------------------------------------------------


def _verifier_slate_digest(pairs: set[tuple[int, str]]) -> str:
    ordered = sorted((int(game_id), str(target)) for game_id, target in pairs)
    return hashlib.sha256(
        json.dumps(ordered, separators=(",", ":")).encode()
    ).hexdigest()


def _verifier_identity_sha(parts: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _verifier_expected_predictions(
    schedule: pd.DataFrame, v4: pd.DataFrame, *, candidate: str
) -> pd.DataFrame:
    """Re-derive the frozen diagnostic V5 prediction rule from sources.

    The frozen diagnostic rule (05B): every scheduled (game, target) that has
    a finite V4 counterpart receives mean 0.0, variance 100.0, symmetric 95%
    interval +/-19.6, zero offset, and candidate self references. Implemented
    here independently so a producer defect cannot mirror into agreement.
    """
    game_ids = schedule["game_id"].astype(int).tolist()
    v4_keys = set()
    for _, row in v4.iterrows():
        value = row.get("mean")
        try:
            if math.isfinite(float(value)):
                v4_keys.add((int(row["game_id"]), str(row["target"])))
        except (TypeError, ValueError):
            continue
    rows = []
    for gid in game_ids:
        for target in ("margin", "total"):
            if (gid, target) not in v4_keys:
                continue
            rows.append(
                {
                    "candidate": candidate,
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


def _reconstruct_freeze(
    storage: Any,
    *,
    manifest: Mapping[str, Any],
    sources: Mapping[str, Any],
) -> dict[str, Any]:
    freeze_frame = _load_compact(
        storage,
        (manifest.get("output_refs") or {}).get("shadow_freeze") or {},
        name="shadow_freeze",
        dataset_key="shadow_freeze",
    )
    predictions = _load_partitioned(
        storage,
        (manifest.get("output_refs") or {}).get("shadow_prediction") or {},
        name="shadow_prediction",
        dataset_key="shadow_prediction",
    )
    _require(len(freeze_frame) == 1, "freeze record must hold exactly one row")
    record = freeze_frame.iloc[0]

    season = int(record["season"])
    week = int(record["week"])
    schedule: pd.DataFrame = sources["schedule"]
    v4: pd.DataFrame = sources["v4_predictions"]

    # Timing ---------------------------------------------------------------
    freeze_ts = pd.Timestamp(record["freeze_time"])
    _require(freeze_ts.tzinfo is not None, "freeze_time must be timezone-aware")
    week_schedule = schedule[
        schedule["season"].eq(season) & schedule["week"].eq(week)
    ].copy()
    _require(not week_schedule.empty, "schedule source has no rows for the slate")
    _require(
        "kickoff_utc" in week_schedule.columns, "schedule source lacks kickoff_utc"
    )
    first_kickoff = pd.Timestamp(week_schedule["kickoff_utc"].dropna().min())
    if first_kickoff.tzinfo is None:
        first_kickoff = first_kickoff.tz_localize("UTC")
    _require(
        pd.Timestamp(record["first_kickoff"]) == first_kickoff,
        "first kickoff disagrees with the schedule source",
    )
    lead = (first_kickoff - freeze_ts).total_seconds()
    _require(
        abs(lead - float(record["lead_seconds"])) < 1e-6,
        "recorded lead seconds disagree with verifier recomputation",
    )
    _require(lead >= FREEZE_HARD_LEAD_SECONDS, "freeze violates the T-1h hard gate")

    # Population ------------------------------------------------------------
    candidate = str(record["candidate"])
    broader = set(week_schedule["game_id"].astype(int).tolist())
    expected_predictions = _verifier_expected_predictions(
        week_schedule, v4, candidate=candidate
    )
    expected_pairs = set(
        zip(
            expected_predictions["game_id"].astype(int),
            expected_predictions["target"].astype(str),
        )
    )
    stored_pairs = set(
        zip(predictions["game_id"].astype(int), predictions["target"].astype(str))
    )
    paired_games = {game_id for game_id, _ in expected_pairs}
    excluded = broader - paired_games
    _require(
        int(record["paired_count"]) == len(paired_games),
        "paired count disagrees with verifier reconstruction",
    )
    _require(
        int(record["broader_count"]) == len(broader),
        "broader count disagrees with verifier reconstruction",
    )
    _require(
        int(record["excluded_count"]) == len(excluded),
        "excluded count disagrees with verifier reconstruction",
    )
    _require(
        int(record["paired_count"]) >= MINIMUM_PAIRED_GAMES,
        "freeze population is below the minimum paired gate",
    )

    # Predictions ------------------------------------------------------------
    stored_reduced = predictions.loc[:, list(SHADOW_PREDICTION_COLUMNS)].copy()
    expected_reduced = expected_predictions.assign(
        season=season,
        week=week,
        run_id=str(record["run_id"]),
    ).loc[:, list(SHADOW_PREDICTION_COLUMNS)]
    _require(
        _frame_digest(stored_reduced, SHADOW_PREDICTION_COLUMNS)
        == _frame_digest(expected_reduced, SHADOW_PREDICTION_COLUMNS),
        "stored predictions disagree with verifier reconstruction",
    )

    # Slate digest and identity ---------------------------------------------
    slate_digest = _verifier_slate_digest(stored_pairs)
    _require(
        str(record["slate_digest"]) == slate_digest,
        "slate digest disagrees with verifier reconstruction",
    )
    identity_parts = {
        "candidate": candidate,
        "season": season,
        "week": week,
        "run_id": str(record["run_id"]),
        "freeze_time": str(record["freeze_time"]),
        "v4_ref_uri": str(record["v4_ref_uri"]),
        "slate_digest": slate_digest,
    }
    _require(
        str(record["identity_sha256"]) == _verifier_identity_sha(identity_parts),
        "freeze identity digest disagrees with verifier reconstruction",
    )
    _require(
        str((manifest.get("parents") or {}).get("v4_prediction_ref_uri", ""))
        == str(record["v4_ref_uri"]),
        "freeze manifest v4 parent disagrees with the freeze record",
    )
    if "diagnostic_only" in manifest:
        _require(
            isinstance(manifest["diagnostic_only"], bool),
            "freeze diagnostic classification must be boolean",
        )
    summary = manifest.get("freeze_summary") or {}
    for key in (
        "season",
        "week",
        "freeze_time",
        "slate_digest",
        "paired_count",
        "broader_count",
        "excluded_count",
    ):
        _require(
            str(summary.get(key)) == str(record[key]),
            f"freeze summary {key} disagrees with the freeze record",
        )
    _require(
        abs(float(summary.get("lead_seconds", -1.0)) - lead) < 1e-6,
        "freeze summary lead seconds disagree with the record",
    )
    return {
        "freeze_record": freeze_frame,
        "predictions": predictions,
        "paired_count": int(record["paired_count"]),
        "slate_digest": slate_digest,
        "season": season,
        "week": week,
        "candidate": candidate,
    }


# ---------------------------------------------------------------------------
# Score reconstruction (verifier-owned stabilization and scoring math)
# ---------------------------------------------------------------------------


def _verifier_crps(error: float, variance: Any) -> float:
    try:
        fv = float(variance)
    except (TypeError, ValueError):
        return abs(float(error))
    if not math.isfinite(fv) or fv <= 0:
        return abs(float(error))
    sigma = math.sqrt(fv)
    z = float(error) / sigma
    phi_z = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    big_phi_z = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return sigma * (
        2.0 * phi_z + z * (2.0 * big_phi_z - 1.0) - 1.0 / math.sqrt(math.pi)
    )


def _reconstruct_scores(
    storage: Any,
    *,
    manifest: Mapping[str, Any],
    sources: Mapping[str, Any],
    freeze: Mapping[str, Any],
) -> dict[str, Any]:
    evaluation = _load_partitioned(
        storage,
        (manifest.get("output_refs") or {}).get("shadow_evaluation") or {},
        name="shadow_evaluation",
        dataset_key="shadow_evaluation",
    )
    outcome_version = str(
        (manifest.get("score_summary") or {}).get("outcome_version", "")
    )
    _require(bool(outcome_version), "score summary lacks an outcome version")
    outcomes: pd.DataFrame = sources["outcomes"]
    _require(not outcomes.empty, "outcome source is empty")
    missing = {
        "game_id",
        "actual_margin",
        "actual_total",
        "last_completion_time",
    } - set(outcomes.columns)
    _require(not missing, f"outcome source is missing columns: {sorted(missing)}")

    scored_at = pd.Timestamp(str((manifest.get("identity") or {}).get("as_of", "")))
    _require(scored_at.tzinfo is not None, "scored-at must be timezone-aware")
    freeze_game_ids = set(freeze["predictions"]["game_id"].astype(int).tolist())
    included = outcomes[outcomes["game_id"].astype(int).isin(freeze_game_ids)]
    _require(not included.empty, "no outcomes match the frozen paired games")
    completions = included["last_completion_time"].dropna()
    _require(
        not completions.empty,
        "all included outcomes lack a trustworthy completion timestamp",
    )
    last_completion = pd.Timestamp(completions.max())
    if last_completion.tzinfo is None:
        last_completion = last_completion.tz_localize("UTC")
    elapsed = (scored_at - last_completion).total_seconds()
    _require(
        elapsed >= SCORE_STABILIZATION_SECONDS,
        f"scoring violates the 24h stabilization gate ({elapsed:.0f}s elapsed)",
    )

    rows = []
    for _, row in freeze["predictions"].iterrows():
        gid = int(row["game_id"])
        target = str(row["target"])
        outcome_rows = included[included["game_id"].astype(int).eq(gid)]
        _require(not outcome_rows.empty, f"outcome missing for frozen game {gid}")
        outcome = outcome_rows.iloc[0]
        column = "actual_margin" if target == "margin" else "actual_total"
        actual = outcome[column]
        _require(
            pd.notna(actual),
            f"outcome value missing for frozen game {gid} target {target}",
        )
        actual = float(actual)
        error = float(row["mean"]) - actual
        covered = bool(
            float(row["interval_lower_95"]) <= actual <= float(row["interval_upper_95"])
        )
        rows.append(
            {
                "game_id": gid,
                "target": target,
                "actual": actual,
                "error": error,
                "crps": _verifier_crps(error, row.get("variance")),
                "coverage_95": covered,
            }
        )
    rebuilt = pd.DataFrame.from_records(rows)
    _require(
        len(rebuilt) == len(evaluation),
        "evaluation row count disagrees with verifier reconstruction",
    )

    stored_sorted = evaluation.sort_values(["game_id", "target"]).reset_index(drop=True)
    rebuilt_sorted = rebuilt.sort_values(["game_id", "target"]).reset_index(drop=True)
    for column in ("actual", "error", "crps"):
        left = stored_sorted[column].astype(float).to_numpy()
        right = rebuilt_sorted[column].astype(float).to_numpy()
        _require(
            bool((np.abs(left - right) < 1e-9).all()),
            f"evaluation column {column} disagrees with verifier reconstruction",
        )
    _require(
        stored_sorted["coverage_95"].astype(bool).tolist()
        == rebuilt_sorted["coverage_95"].astype(bool).tolist(),
        "evaluation coverage flags disagree with verifier reconstruction",
    )

    margin_errors = rebuilt_sorted[rebuilt_sorted["target"] == "margin"]["error"]
    total_errors = rebuilt_sorted[rebuilt_sorted["target"] == "total"]["error"]
    mae_margin = float(margin_errors.abs().mean()) if not margin_errors.empty else None
    mae_total = float(total_errors.abs().mean()) if not total_errors.empty else None
    summary = manifest.get("score_summary") or {}
    for key, value in (("mae_margin", mae_margin), ("mae_total", mae_total)):
        recorded = summary.get(key)
        _require(
            (recorded is None and value is None)
            or (
                recorded is not None
                and value is not None
                and abs(float(recorded) - value) < 1e-9
            ),
            f"score summary {key} disagrees with verifier reconstruction",
        )
    paired_count = int(rebuilt["game_id"].nunique())
    _require(
        int(summary.get("paired_count", -1)) == paired_count,
        "score summary paired count disagrees with verifier reconstruction",
    )
    return {
        "evaluation": evaluation,
        "paired_count": paired_count,
        "mae_margin": mae_margin,
        "mae_total": mae_total,
        "outcome_version": outcome_version,
    }


# ---------------------------------------------------------------------------
# Counter reconstruction (verifier-owned no-double-count logic)
# ---------------------------------------------------------------------------


def _reconstruct_counter(
    storage: Any,
    *,
    manifest: Mapping[str, Any],
    freeze: Mapping[str, Any],
) -> dict[str, Any]:
    counter = _load_compact(
        storage,
        (manifest.get("output_refs") or {}).get("shadow_evidence_counter") or {},
        name="shadow_evidence_counter",
        dataset_key="evidence_counter",
    )
    for _, row in counter.iterrows():
        _require(bool(row["freeze_ref"]), "counter row lacks a freeze reference")
    slates = counter[counter["qualifying"].astype(bool)]
    duplicates = slates.duplicated(subset=["candidate", "season", "week"])
    _require(not bool(duplicates.any()), "evidence counter double-counts a slate")
    qualifying_count = int(
        len(slates.drop_duplicates(subset=["candidate", "season", "week"]))
    )
    summary = manifest.get("score_summary") or {}
    _require(
        int(summary.get("qualifying_slates_total", -1)) == qualifying_count,
        "qualifying slate total disagrees with verifier reconstruction",
    )
    diagnostic_rows = counter[counter["reason"].astype(str).eq(DIAGNOSTIC_CLASS)]
    _require(
        not bool(diagnostic_rows["qualifying"].astype(bool).any()),
        "diagnostic class rows may never qualify as evidence",
    )
    if len(counter):
        latest = counter.iloc[-1]
        _require(
            int(latest["season"]) == freeze["season"]
            and int(latest["week"]) == freeze["week"],
            "counter tail row does not match the scored slate",
        )
        _require(
            str(latest["freeze_ref"])
            == str((manifest.get("parents") or {}).get("freeze_manifest_uri", "")),
            "counter freeze reference does not match the score parent",
        )
    return {"counter": counter, "qualifying_count": qualifying_count}


# ---------------------------------------------------------------------------
# Rehearsal verification (diagnostic class is permanent)
# ---------------------------------------------------------------------------


def _reconstruct_rehearsal(
    storage: Any,
    *,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    rehearsal = _load_compact(
        storage,
        (manifest.get("output_refs") or {}).get("shadow_rehearsal") or {},
        name="shadow_rehearsal",
        dataset_key="shadow_rehearsal",
    )
    _require(len(rehearsal) == 1, "rehearsal record must hold exactly one row")
    row = rehearsal.iloc[0]
    _require(
        bool(row["diagnostic_only"]) is True,
        "rehearsal record must carry the permanent diagnostic-only class",
    )
    cases = manifest.get("rehearsal_cases") or {}
    failed = [
        name
        for name, case in cases.items()
        if case.get("disposition") != case.get("expected")
    ]
    _require(
        int(row["cases_failed"]) == len(failed),
        "rehearsal failure count disagrees with the recorded cases",
    )
    _require(
        int(row["cases_passed"]) + int(row["cases_failed"]) == len(cases),
        "rehearsal case totals disagree with the recorded cases",
    )
    _require(
        str(row["verifier_ref"])
        == str((manifest.get("verification") or {}).get("verifier_manifest_uri", "")),
        "rehearsal verifier reference does not match the manifest",
    )
    return {
        "rehearsal": rehearsal,
        "cases_passed": int(row["cases_passed"]),
        "cases_failed": int(row["cases_failed"]),
        "season_range": str(row["season_range"]),
    }


# ---------------------------------------------------------------------------
# Top-level dispatch
# ---------------------------------------------------------------------------


def _base_manifest_checks(
    manifest: Mapping[str, Any],
    *,
    expected_schema: str,
    expected_code_sha: str,
) -> str:
    _require(
        manifest.get("schema_version") == expected_schema,
        f"manifest schema mismatch: {manifest.get('schema_version')}",
    )
    _require(manifest.get("state") == "frozen", "manifest is not frozen")
    _require(
        manifest.get("production_activation_authorized") is False,
        "manifest authorizes production",
    )
    return _verify_identity(
        manifest.get("identity") or {}, expected_code_sha=expected_code_sha
    )


def verify_shadow_artifact(
    storage: Any,
    *,
    manifest_uri: str,
    expected_code_sha: str,
    environment: str,
    sources: Mapping[str, Any] | None = None,
    schedule_uri: str = "",
    v4_prediction_uri: str = "",
    outcome_uri: str = "",
    readiness_cutoff: str = "",
) -> dict[str, Any]:
    """Independently reconstruct and verify a frozen shadow artifact.

    ``sources`` may carry caller-loaded frames (``schedule``, ``v4_predictions``,
    ``outcomes``); otherwise the verifier reads them from the given URIs (V4
    and outcome URIs default to the manifest parents). ``readiness_cutoff``
    overrides the readiness assessment cutoff (defaults to the manifest
    identity as-of).
    """
    if environment != "preview":
        raise ShadowVerificationError("shadow verification is preview-only")
    if sources is None:
        sources = {}
    try:
        return _verify_dispatch(
            storage,
            manifest_uri=manifest_uri,
            expected_code_sha=expected_code_sha,
            sources=sources,
            schedule_uri=schedule_uri,
            v4_prediction_uri=v4_prediction_uri,
            outcome_uri=outcome_uri,
            readiness_cutoff=readiness_cutoff,
        )
    except FileNotFoundError as exc:
        raise ShadowVerificationError(f"source object is missing: {exc}") from exc
    except StorageError as exc:
        raise ShadowVerificationError(f"storage rejected source: {exc}") from exc


def _verify_dispatch(
    storage: Any,
    *,
    manifest_uri: str,
    expected_code_sha: str,
    sources: Mapping[str, Any],
    schedule_uri: str,
    v4_prediction_uri: str,
    outcome_uri: str,
    readiness_cutoff: str,
) -> dict[str, Any]:
    manifest, _raw = _read_json(storage, manifest_uri)
    schema_version = str(manifest.get("schema_version"))
    result: dict[str, Any] = {
        "verified": True,
        "manifest_uri": manifest_uri,
        "schema_version": schema_version,
    }

    if schema_version == SHADOW_MANIFEST_SCHEMA:
        try:
            verify_signed_payload(manifest, label="shadow manifest")
        except ValueError as exc:
            raise ShadowVerificationError(str(exc)) from exc
        identity = manifest.get("identity") or {}
        identity_sha = _base_manifest_checks(
            manifest,
            expected_schema=SHADOW_MANIFEST_SCHEMA,
            expected_code_sha=expected_code_sha,
        )
        chain = _verify_parent_chain(storage, identity)
        _require_pinned_manifest_uris(
            identity.get("parents") or {},
            live=chain["forecast"].get("schema_version")
            == LIVE_FORECAST_MANIFEST_SCHEMA,
        )
        _require(
            set(manifest.get("output_refs") or {}) == {"readiness"},
            "05A manifest must reference exactly the readiness output",
        )
        stored = _load_compact(
            storage,
            (manifest.get("output_refs") or {}).get("readiness") or {},
            name="readiness",
            dataset_key="readiness",
        )
        loaded = dict(sources)
        if not loaded:
            loaded = _load_readiness_sources(storage, chain=chain)
        cutoff = readiness_cutoff or str(identity.get("as_of", ""))
        live_candidate_status = None
        if chain["forecast"].get("schema_version") == LIVE_FORECAST_MANIFEST_SCHEMA:
            live_candidate_status = _live_readiness_candidate_status(
                storage,
                forecast=chain["forecast"],
                population=loaded["schedule"],
                season=int(stored["season"].iloc[0]),
                week=int(stored["week"].iloc[0]),
                cutoff=cutoff,
            )
        rebuilt = _reconstruct_readiness(
            cutoff=cutoff,
            chain=chain,
            stored=stored,
            sources=loaded,
            candidate_status=live_candidate_status,
        )
        _compare_readiness(
            stored,
            rebuilt["frame"],
            manifest_overall=str(manifest.get("readiness_overall", "")),
        )
        result |= {
            "kind": "readiness",
            "identity_sha256": identity_sha,
            "readiness_overall": rebuilt["overall"],
            "sources": sorted(rebuilt["frame"]["source"].tolist()),
            "cutoff": cutoff,
        }
        return result

    if schema_version == FREEZE_MANIFEST_SCHEMA:
        _base_manifest_checks(
            manifest,
            expected_schema=FREEZE_MANIFEST_SCHEMA,
            expected_code_sha=expected_code_sha,
        )
        schedule = sources.get("schedule")
        if schedule is None:
            schedule = _read_frame(storage, schedule_uri, name="schedule")
        v4 = sources.get("v4_predictions")
        if v4 is None:
            v4_uri = v4_prediction_uri or str(
                (manifest.get("parents") or {}).get("v4_prediction_ref_uri", "")
            )
            v4 = _read_frame(storage, v4_uri, name="v4_predictions")
        freeze = _reconstruct_freeze(
            storage,
            manifest=manifest,
            sources={"schedule": schedule, "v4_predictions": v4},
        )
        readiness_uri = str(
            (manifest.get("parents") or {}).get("readiness_manifest_uri", "")
        )
        _require(bool(readiness_uri), "freeze manifest lacks a readiness parent")
        readiness, _ = _read_json(storage, readiness_uri)
        _require(
            readiness.get("schema_version") == SHADOW_MANIFEST_SCHEMA
            and readiness.get("state") == "frozen",
            "readiness parent manifest is not a frozen 05A shadow manifest",
        )
        result |= {
            "kind": "freeze",
            "paired_count": freeze["paired_count"],
            "slate_digest": freeze["slate_digest"],
            "season": freeze["season"],
            "week": freeze["week"],
            "diagnostic_only": bool(manifest.get("diagnostic_only", False)),
        }
        return result

    if schema_version == SCORE_MANIFEST_SCHEMA:
        _base_manifest_checks(
            manifest,
            expected_schema=SCORE_MANIFEST_SCHEMA,
            expected_code_sha=expected_code_sha,
        )
        freeze_uri = str((manifest.get("parents") or {}).get("freeze_manifest_uri", ""))
        _require(bool(freeze_uri), "score manifest lacks a freeze parent")
        freeze_manifest, _ = _read_json(storage, freeze_uri)
        _require(
            freeze_manifest.get("schema_version") == FREEZE_MANIFEST_SCHEMA
            and freeze_manifest.get("state") == "frozen",
            "freeze parent manifest is not a frozen 05B freeze manifest",
        )
        schedule = sources.get("schedule")
        v4 = sources.get("v4_predictions")
        if schedule is None:
            schedule = _read_frame(storage, schedule_uri, name="schedule")
        if v4 is None:
            v4_uri = v4_prediction_uri or str(
                (freeze_manifest.get("parents") or {}).get("v4_prediction_ref_uri", "")
            )
            v4 = _read_frame(storage, v4_uri, name="v4_predictions")
        freeze = _reconstruct_freeze(
            storage,
            manifest=freeze_manifest,
            sources={"schedule": schedule, "v4_predictions": v4},
        )
        outcomes = sources.get("outcomes")
        if outcomes is None:
            outcome_source = outcome_uri or str(
                (manifest.get("parents") or {}).get("outcome_ref_uri", "")
            )
            outcomes = _read_frame(storage, outcome_source, name="outcomes")
        score = _reconstruct_scores(
            storage, manifest=manifest, sources={"outcomes": outcomes}, freeze=freeze
        )
        counter = _reconstruct_counter(storage, manifest=manifest, freeze=freeze)
        result |= {
            "kind": "score",
            "paired_count": score["paired_count"],
            "mae_margin": score["mae_margin"],
            "mae_total": score["mae_total"],
            "qualifying_count": counter["qualifying_count"],
        }
        return result

    if schema_version == REHEARSAL_MANIFEST_SCHEMA:
        _base_manifest_checks(
            manifest,
            expected_schema=REHEARSAL_MANIFEST_SCHEMA,
            expected_code_sha=expected_code_sha,
        )
        replay = _reconstruct_replay(manifest.get("replay") or {})
        _require(
            _hex64(replay["replay_sha256"]),
            "rehearsal manifest must record the frozen replay digest",
        )
        _require(
            replay["byte_identical"] is True,
            "rehearsal replay byte-identity did not hold",
        )
        _require(
            replay["perturbation_invariance"] is True,
            "rehearsal perturbation invariance did not hold",
        )
        rehearsal = _reconstruct_rehearsal(storage, manifest=manifest)
        result |= {
            "kind": "rehearsal",
            "cases_passed": rehearsal["cases_passed"],
            "cases_failed": rehearsal["cases_failed"],
            "season_range": rehearsal["season_range"],
            "replay_sha256": replay["replay_sha256"],
        }
        return result

    raise ShadowVerificationError(f"unknown shadow manifest schema: {schema_version}")


def write_verifier_manifest(
    storage: Any,
    *,
    run_prefix: str,
    payload: Mapping[str, Any],
) -> str:
    """Write the signed verifier manifest idempotently (immutable collision)."""
    manifest = signed_payload(
        {
            "schema_version": VERIFICATION_MANIFEST_SCHEMA,
            "state": "verified",
            **dict(payload),
        }
    )
    uri = f"{run_prefix.rstrip('/')}/{VERIFICATION_MANIFEST_NAME}"
    encoded = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        existing = storage.read_bytes(uri)
        if existing != encoded:
            raise ShadowVerificationError(
                f"immutable verifier manifest collision at {uri}"
            )
        return uri
    storage.write_bytes(encoded, uri)
    return uri
