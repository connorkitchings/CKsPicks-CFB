"""Load the signed V5 historical fit and live application source frames."""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Mapping
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_forecast_v1 import REQUIRED_RATING_CANDIDATE
from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    BRIDGE_MANIFEST_URI,
    LiveForecastContractError,
    verify_application_parents,
)
from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import TEAM_STATE_COLUMNS
from cks_picks_cfb.data.lake import DatasetRef, PartitionedDatasetRef, read_dataset
from cks_picks_cfb.forecast.live import build_live_application_frame
from cks_picks_cfb.forecast.offsets import build_offsets
from cks_picks_cfb.ratings.possession_rating_materializer import (
    _concat_frames,
    _manifest_parts,
    _partitioned_ref,
    _read_child,
    _stream_output,
    load_rating_inputs,
)


class LiveSourceError(ValueError):
    """Raised when immutable forecast sources cannot be reconstructed."""


def _read_json(storage: Any, uri: str) -> tuple[dict[str, Any], bytes]:
    raw = storage.read_bytes(uri)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LiveSourceError(f"unreadable manifest: {uri}") from exc
    if not isinstance(value, dict):
        raise LiveSourceError(f"manifest must be an object: {uri}")
    return value, raw


def _read_frame(storage: Any, value: Mapping[str, Any], name: str) -> pd.DataFrame:
    """Read either canonical compact or partitioned immutable output refs."""
    if value.get("artifact_kind") == "partitioned_dataset_v1":
        raw_manifest = json.loads(storage.read_bytes(str(value["uri"])))
        ref = PartitionedDatasetRef(
            artifact_kind="partitioned_dataset_v1",
            dataset=str(value["dataset"]),
            version_id=str(value["version_id"]),
            schema_version=str(value["schema_version"]),
            content_sha=str(value["content_sha"]),
            records_sha=str(raw_manifest.get("records_sha", "")),
            uri=str(value["uri"]),
            row_count=int(value["row_count"]),
            partition_keys=tuple(
                raw_manifest.get("partition_keys") or value.get("partition_keys") or ()
            ),
        )
        return read_dataset(storage, ref)
    ref = DatasetRef(
        dataset=str(value["dataset"]),
        version_id=str(value["version_id"]),
        schema_version=str(value["schema_version"]),
        content_sha=str(value["content_sha"]),
        uri=str(value["uri"]),
    )
    frame = read_dataset(storage, ref)
    if len(frame) != int(value.get("row_count", len(frame))):
        raise LiveSourceError(f"row count mismatch for {name}")
    return frame


def _population_and_events(
    storage: Any, manifest: Mapping[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    refs = manifest.get("output_refs") or {}
    if not {"population", "scoring_events"} <= set(refs):
        raise LiveSourceError("measurement parent lacks population/scoring outputs")

    def progress(*_args: Any, **_kwargs: Any) -> None:
        return None

    population = _stream_output(
        storage, name="population", value=refs["population"], progress=progress
    )
    events = _stream_output(
        storage, name="scoring_events", value=refs["scoring_events"], progress=progress
    )
    return population, events


def _team_states(storage: Any, manifest: Mapping[str, Any]) -> pd.DataFrame:
    value = (manifest.get("output_refs") or {}).get("team_states")
    if not value:
        raise LiveSourceError("rating replay lacks team_states")
    ref = _partitioned_ref(value, name="team_states")
    if (
        ref.dataset != "possession_team_state"
        or ref.schema_version != "data_first_possession_team_state_v1"
    ):
        raise LiveSourceError("rating team state output identity mismatch")
    _, parts = _manifest_parts(storage, ref)
    frames = [
        _read_child(
            storage,
            dataset=ref.dataset,
            schema_version=ref.schema_version,
            part=part,
        )
        for part in parts
    ]
    return _concat_frames(frames, columns=list(TEAM_STATE_COLUMNS))


def _historical_features(storage: Any, bridge: Mapping[str, Any]) -> pd.DataFrame:
    """Rebuild exact pre-2026 bridge fitting rows from 11C's signed parents."""
    refs = bridge.get("parents") or {}
    required = (
        "rating_manifest_uri",
        "measurement_manifest_uri",
        "repair_manifest_uri",
    )
    if any(not refs.get(key) for key in required):
        raise LiveSourceError("11C bridge lacks its historical source ancestry")
    rating, rating_raw = _read_json(storage, str(refs["rating_manifest_uri"]))
    measurement, measurement_raw = _read_json(
        storage, str(refs["measurement_manifest_uri"])
    )
    repair, repair_raw = _read_json(storage, str(refs["repair_manifest_uri"]))
    for uri_key, sha_key, raw in (
        ("rating_manifest_uri", "rating_raw_sha256", rating_raw),
        ("measurement_manifest_uri", "measurement_raw_sha256", measurement_raw),
        ("repair_manifest_uri", "repair_raw_sha256", repair_raw),
    ):
        expected_sha = refs.get(sha_key)
        if not expected_sha:
            raise LiveSourceError(
                f"11C historical parent checksum is absent: {uri_key}"
            )
        if hashlib.sha256(raw).hexdigest() != expected_sha:
            raise LiveSourceError(f"11C historical parent checksum mismatch: {uri_key}")
    try:
        verify_signed_payload(rating, label="11C historical rating parent")
        verify_signed_payload(measurement, label="11C historical measurement parent")
    except ValueError as exc:
        raise LiveSourceError(str(exc)) from exc
    inputs = load_rating_inputs(
        storage=storage,
        measurement=measurement,
        repair=repair,
        progress=lambda *_args, **_kwargs: None,
    )
    _, events = _population_and_events(storage, measurement)
    team_states = _team_states(storage, rating)
    offsets = build_offsets(
        inputs.population,
        events,
        development_seasons=(
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
        ),
        equivalent_games=4,
    )
    from scripts.research.run_data_first_forecasts import _feature_frame

    features = _feature_frame(
        population=inputs.population,
        outcomes=inputs.outcomes,
        team_states=team_states,
        offsets=offsets.offsets,
    )
    return features


def _week4_gate(
    *,
    schedule: pd.DataFrame,
    population: pd.DataFrame,
    measurement_as_of: str,
    as_of: str,
) -> None:
    required = {
        "season",
        "week",
        "game_id",
        "kickoff_utc",
        "schedule_completed",
        "outcome_valid",
    }
    if missing := sorted(required - set(population)):
        raise LiveSourceError(
            f"2026 measurement population lacks Week 4 gate fields: {missing}"
        )
    scheduled = schedule[schedule["season"].eq(2026)]
    week4_schedule = scheduled[scheduled["week"].eq(4)]
    week4_population = population[
        population["season"].eq(2026) & population["week"].eq(4)
    ]
    expected = set(week4_schedule["game_id"].astype(int))
    observed = set(week4_population["game_id"].astype(int))
    if (
        week4_schedule.duplicated("game_id").any()
        or week4_population.duplicated("game_id").any()
    ):
        raise LiveSourceError(
            "week4_final_population_incomplete: duplicate game identity"
        )
    if not expected or observed != expected:
        raise LiveSourceError(
            "week4_final_population_incomplete: Week 4 schedule is not fully reconciled"
        )
    if (
        not week4_population["schedule_completed"].astype(bool).all()
        or not week4_population["outcome_valid"].astype(bool).all()
    ):
        raise LiveSourceError(
            "week4_final_population_incomplete: one or more Week 4 outcomes are not final"
        )
    latest_kickoff = pd.to_datetime(week4_schedule["kickoff_utc"], utc=True).max()
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        raise LiveSourceError("forecast as-of must be timezone-aware")
    measurement_cutoff = pd.Timestamp(measurement_as_of)
    if measurement_cutoff.tzinfo is None:
        raise LiveSourceError("Week 4 measurement as-of must be timezone-aware")
    if measurement_cutoff.tz_convert("UTC") < latest_kickoff:
        raise LiveSourceError(
            "week4_finals_not_stabilized: measurement predates the final Week 4 kickoff"
        )
    if cutoff.tz_convert("UTC") < latest_kickoff:
        raise LiveSourceError(
            "week4_finals_not_stabilized: forecast cutoff predates the final Week 4 kickoff"
        )


def _validate_schedule_matches_population(
    *, schedule: pd.DataFrame, population: pd.DataFrame
) -> None:
    """Bind every 2026 schedule fact to the certified measurement population."""
    columns = ("season", "week", "game_id", "kickoff_utc", "home_team", "away_team")
    for label, frame in (("schedule", schedule), ("measurement", population)):
        missing = sorted(set(columns) - set(frame))
        if missing:
            raise LiveSourceError(
                f"{label} population lacks schedule fields: {missing}"
            )

    schedule_2026 = schedule.loc[schedule["season"].eq(2026), list(columns)].copy()
    population_2026 = population.loc[
        population["season"].eq(2026), list(columns)
    ].copy()
    for label, frame in (("schedule", schedule_2026), ("measurement", population_2026)):
        if frame.empty:
            raise LiveSourceError(f"{label} has no 2026 schedule rows")
        if frame.duplicated("game_id").any():
            raise LiveSourceError(f"{label} duplicates a 2026 game identity")
        try:
            frame["season"] = pd.to_numeric(frame["season"], errors="raise").astype(int)
            frame["week"] = pd.to_numeric(frame["week"], errors="raise").astype(int)
            frame["game_id"] = pd.to_numeric(frame["game_id"], errors="raise").astype(
                int
            )
            frame["kickoff_utc"] = pd.to_datetime(
                frame["kickoff_utc"], utc=True, errors="raise"
            )
            for side in ("home_team", "away_team"):
                frame[side] = frame[side].astype(str).str.strip()
        except (TypeError, ValueError) as exc:
            raise LiveSourceError(f"{label} has invalid schedule values") from exc
        if frame[["home_team", "away_team"]].eq("").any().any():
            raise LiveSourceError(f"{label} has an empty schedule team")

    left = schedule_2026.sort_values("game_id", kind="mergesort").reset_index(drop=True)
    right = population_2026.sort_values("game_id", kind="mergesort").reset_index(
        drop=True
    )
    if not left.equals(right):
        differing = [
            column for column in columns if not left[column].equals(right[column])
        ]
        raise LiveSourceError(
            "schedule_source_mismatch: full 2026 schedule differs from certified "
            f"measurement population at {differing}"
        )


def load_live_forecast_sources(
    *,
    storage: Any,
    measurement_uri: str,
    rating_uri: str,
    schedule_uri: str,
    bridge_uri: str,
    as_of: str,
) -> dict[str, Any]:
    """Load and validate the complete source set used by live forecast CLIs."""
    if bridge_uri != BRIDGE_MANIFEST_URI:
        raise LiveSourceError("live forecast must use the pinned 11C bridge URI")
    measurement, measurement_raw = _read_json(storage, measurement_uri)
    rating, rating_raw = _read_json(storage, rating_uri)
    bridge, bridge_raw = _read_json(storage, bridge_uri)
    schedule_raw = storage.read_bytes(schedule_uri)
    try:
        schedule = pd.read_parquet(io.BytesIO(schedule_raw))
    except Exception:
        try:
            schedule = pd.DataFrame(json.loads(schedule_raw))
        except Exception as exc:
            raise LiveSourceError(
                "full schedule source must be parquet or canonical JSON"
            ) from exc
    try:
        chain = verify_application_parents(
            measurement=measurement,
            measurement_uri=measurement_uri,
            measurement_raw_sha256=hashlib.sha256(measurement_raw).hexdigest(),
            rating_replay=rating,
            rating_replay_uri=rating_uri,
            rating_replay_raw_sha256=hashlib.sha256(rating_raw).hexdigest(),
            bridge=bridge,
            bridge_uri=bridge_uri,
            bridge_raw_sha256=hashlib.sha256(bridge_raw).hexdigest(),
        )
    except LiveForecastContractError as exc:
        raise LiveSourceError(str(exc)) from exc
    population, scoring_events = _population_and_events(storage, measurement)
    if population.duplicated(["season", "game_id"]).any():
        raise LiveSourceError("Contract 07 population duplicates a game")
    if not population["season"].eq(2026).all():
        raise LiveSourceError("live Contract 07 population must contain only 2026")
    _validate_schedule_matches_population(schedule=schedule, population=population)
    _week4_gate(
        schedule=schedule,
        population=population,
        measurement_as_of=str((measurement.get("identity") or {}).get("as_of", "")),
        as_of=as_of,
    )
    states = _team_states(storage, rating)
    if not states["candidate_id"].eq(REQUIRED_RATING_CANDIDATE).any():
        raise LiveSourceError("Contract 08 output lacks the retained candidate")
    historical_features = _historical_features(storage, bridge)
    historical_population, historical_events = _population_and_events(
        storage,
        _read_json(
            storage,
            str((bridge.get("parents") or {}).get("measurement_manifest_uri", "")),
        )[0],
    )
    combined_population = pd.concat(
        [historical_population, population], ignore_index=True, sort=False
    )
    combined_events = pd.concat(
        [historical_events, scoring_events], ignore_index=True, sort=False
    )
    offsets = build_offsets(
        combined_population,
        combined_events,
        development_seasons=(
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
            2026,
        ),
        equivalent_games=4,
    )
    live_features, state_refs = build_live_application_frame(
        schedule,
        population,
        states[states["candidate_id"].eq(REQUIRED_RATING_CANDIDATE)],
        offsets.offsets,
        as_of=as_of,
    )
    parent_roles = {
        "measurement_uri": measurement_uri,
        "measurement_raw_sha256": hashlib.sha256(measurement_raw).hexdigest(),
        "rating_replay_uri": rating_uri,
        "rating_replay_raw_sha256": hashlib.sha256(rating_raw).hexdigest(),
        "bridge_uri": bridge_uri,
        "bridge_raw_sha256": hashlib.sha256(bridge_raw).hexdigest(),
        "schedule_ref_uri": schedule_uri,
        "schedule_raw_sha256": hashlib.sha256(schedule_raw).hexdigest(),
    }
    recipes = bridge.get("head_recipes") or {}
    if set(recipes) != {"margin", "total"}:
        raise LiveSourceError("11C bridge lacks the fixed final-fit recipes")
    for target, recipe in recipes.items():
        if recipe.get("final_training_seasons") != ",".join(
            map(str, DEVELOPMENT_SEASONS)
        ):
            raise LiveSourceError(
                f"11C {target} recipe is not the through-2025 final fit"
            )
        if (
            recipe.get("head") == "reference"
            and float(recipe.get("final_alpha", 0)) != 10.0
        ):
            raise LiveSourceError(
                f"11C {target} reference alpha differs from the frozen 10.0 head"
            )
    variances = {}
    by_target = (bridge.get("calibration_summary") or {}).get("by_target", {})
    for target in ("margin", "total"):
        values = by_target.get(target) or {}
        variance = values.get("0", values.get(0))
        if variance is None or not pd.notna(float(variance)) or float(variance) <= 0:
            raise LiveSourceError(
                f"11C final calibration variance is absent for {target}"
            )
        variances[target] = float(variance)
    return {
        "chain": chain,
        "measurement": measurement,
        "rating": rating,
        "bridge": bridge,
        "population": population,
        "schedule": schedule,
        "scoring_events": scoring_events,
        "states": states,
        "historical_features": historical_features,
        "live_features": live_features,
        "state_refs": state_refs,
        "parents": parent_roles,
        "recipes": recipes,
        "variances": variances,
    }
