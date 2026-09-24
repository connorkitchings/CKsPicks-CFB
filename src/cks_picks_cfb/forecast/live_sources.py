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
from cks_picks_cfb.data.data_first_phase2 import (
    DEVELOPMENT_SEASONS,
    FORBIDDEN_SEASONS,
)
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.data_first_possession_rating_v1 import TEAM_STATE_COLUMNS
from cks_picks_cfb.data.data_first_possession_v1 import POPULATION_COLUMNS
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.forecast.historical_features import _feature_frame
from cks_picks_cfb.forecast.live import build_live_application_frame
from cks_picks_cfb.forecast.offsets import build_offsets
from cks_picks_cfb.preseason_features import canonical_team
from cks_picks_cfb.ratings.possession_live_replay import build_current_team_states
from cks_picks_cfb.ratings.possession_live_replay_verification import (
    verify_current_state,
)
from cks_picks_cfb.ratings.possession_rating_materializer import (
    _concat_frames,
    _core_eligibility_refs,
    _manifest_parts,
    _partitioned_ref,
    _read_child,
    _stream_output,
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
        if name in {
            "population",
            "scoring_events",
            "observations",
            "snapshots",
            "terminal",
        }:
            return _stream_output(
                storage,
                name=name,
                value=value,
                progress=lambda *_args, **_kwargs: None,
            )
        ref = _partitioned_ref(value, name=name)
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
        frame = _concat_frames(
            frames, columns=list(frames[0].columns) if frames else []
        )
        if len(frame) != int(value["row_count"]):
            raise LiveSourceError(f"row count mismatch for {name}")
        return frame
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
        ("rating_manifest_uri", "rating_manifest_raw_sha256", rating_raw),
        (
            "measurement_manifest_uri",
            "measurement_manifest_raw_sha256",
            measurement_raw,
        ),
        ("repair_manifest_uri", "repair_manifest_raw_sha256", repair_raw),
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
    output_refs = measurement.get("output_refs") or {}
    if not {"population", "scoring_events"} <= set(output_refs):
        raise LiveSourceError("historical measurement lacks bridge input refs")

    def progress(*_args: Any, **_kwargs: Any) -> None:
        return None

    population = _stream_output(
        storage, name="population", value=output_refs["population"], progress=progress
    ).loc[:, list(POPULATION_COLUMNS)]
    if (
        len(population) != 8936
        or int(population["forecast_eligible"].sum()) != 8935
        or population["season"].isin(FORBIDDEN_SEASONS).any()
    ):
        raise LiveSourceError("historical bridge population reconciliation changed")
    events = _stream_output(
        storage,
        name="scoring_events",
        value=output_refs["scoring_events"],
        progress=progress,
    )
    eligibility_refs = _core_eligibility_refs(storage, repair)
    outcomes = pd.concat(
        [
            read_dataset(storage, eligibility_refs[season]["game_outcomes"])
            for season in sorted(eligibility_refs)
        ],
        ignore_index=True,
        sort=False,
    ).loc[:, ["season", "game_id", "completed", "home_points", "away_points"]]
    for name in ("season", "game_id"):
        outcomes[name] = pd.to_numeric(outcomes[name], errors="raise").astype(int)
    team_states = _team_states(storage, rating)
    offsets = build_offsets(
        population,
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
    features = _feature_frame(
        population=population,
        outcomes=outcomes,
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


def _prior_weeks_gate(
    *,
    schedule: pd.DataFrame,
    population: pd.DataFrame,
    measurement_as_of: str,
    as_of: str,
    target_week: int | None = None,
) -> int:
    """Require every earlier slate to be settled for the requested live cutoff."""
    cutoff = pd.Timestamp(as_of)
    measured_at = pd.Timestamp(measurement_as_of)
    if cutoff.tzinfo is None or measured_at.tzinfo is None:
        raise LiveSourceError("forecast and measurement cutoffs must be timezone-aware")
    cutoff = cutoff.tz_convert("UTC")
    measured_at = measured_at.tz_convert("UTC")
    season = schedule[schedule["season"].eq(2026)].copy()
    season["kickoff_utc"] = pd.to_datetime(season["kickoff_utc"], utc=True)
    upcoming = season[season["kickoff_utc"].gt(cutoff)]
    if upcoming.empty:
        raise LiveSourceError("no future 2026 slate remains at the forecast cutoff")
    if target_week is None:
        target_week = int(upcoming["week"].min())
    if not upcoming["week"].eq(target_week).any():
        raise LiveSourceError(f"requested Week {target_week} has no future games")
    prior = season[season["week"].lt(target_week)]
    certified = population[
        population["season"].eq(2026) & population["week"].lt(target_week)
    ]
    if prior["game_id"].duplicated().any() or certified["game_id"].duplicated().any():
        raise LiveSourceError("prior-week schedule or measurement duplicates a game")
    if set(prior["game_id"].astype(int)) != set(certified["game_id"].astype(int)):
        raise LiveSourceError("prior-week measurement coverage is incomplete")
    if (
        not certified.empty
        and not (
            certified["schedule_completed"].astype(bool)
            & certified["outcome_valid"].astype(bool)
        ).all()
    ):
        raise LiveSourceError("prior-week outcomes are not all final")
    if not prior.empty:
        ready_at = prior["kickoff_utc"].max() + pd.Timedelta(hours=6)
        if measured_at < ready_at or cutoff < ready_at:
            raise LiveSourceError("prior-week football evidence is not yet available")
    return target_week


def _validate_schedule_matches_population(
    *, schedule: pd.DataFrame, population: pd.DataFrame
) -> None:
    """Bind certified completed games to schedule facts; future games are targets."""
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

    left = (
        schedule_2026[schedule_2026["game_id"].isin(population_2026["game_id"])]
        .sort_values("game_id", kind="mergesort")
        .reset_index(drop=True)
    )
    right = population_2026.sort_values("game_id", kind="mergesort").reset_index(
        drop=True
    )
    if not left.equals(right):
        differing = [
            column for column in columns if not left[column].equals(right[column])
        ]
        raise LiveSourceError(
            "schedule_source_mismatch: completed 2026 schedule differs from certified "
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
    target_week: int | None = None,
    include_historical_features: bool = True,
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
    for side in ("home", "away"):
        schedule[f"{side}_team"] = schedule[f"{side}_team"].map(canonical_team)
    if {"home_classification", "away_classification"} <= set(schedule):
        schedule = schedule[
            schedule["home_classification"].eq("fbs")
            & schedule["away_classification"].eq("fbs")
        ].copy()
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
    target_week = _prior_weeks_gate(
        schedule=schedule,
        population=population,
        measurement_as_of=str((measurement.get("identity") or {}).get("as_of", "")),
        as_of=as_of,
        target_week=target_week,
    )
    states = _team_states(storage, rating)
    if not states["candidate_id"].eq(REQUIRED_RATING_CANDIDATE).any():
        raise LiveSourceError("Contract 08 output lacks the retained candidate")
    rating_outputs = rating.get("output_refs") or {}
    measurement_outputs = measurement.get("output_refs") or {}
    historical_measurement_uri = str(
        (rating.get("parents") or {}).get("historical_measurement_manifest_uri")
        or (bridge.get("parents") or {}).get("measurement_manifest_uri")
        or ""
    )
    historical_measurement = _read_json(storage, historical_measurement_uri)[0]
    historical_outputs = historical_measurement.get("output_refs") or {}
    if (
        not {"priors"} <= set(rating_outputs)
        or not {"observations", "snapshots", "terminal"} <= set(measurement_outputs)
        or "terminal" not in historical_outputs
    ):
        raise LiveSourceError(
            "current rating reconstruction lacks certified prior or terminal outputs"
        )
    observations = _stream_output(
        storage,
        name="observations",
        value=measurement_outputs["observations"],
        progress=lambda *_args, **_kwargs: None,
    )
    snapshots = _stream_output(
        storage,
        name="snapshots",
        value=measurement_outputs["snapshots"],
        progress=lambda *_args, **_kwargs: None,
    )
    terminal = _stream_output(
        storage,
        name="terminal",
        value=measurement_outputs["terminal"],
        progress=lambda *_args, **_kwargs: None,
    )
    priors = _read_frame(storage, rating_outputs["priors"], "priors")
    historical_terminal = _stream_output(
        storage,
        name="terminal",
        value=historical_outputs["terminal"],
        progress=lambda *_args, **_kwargs: None,
    )
    target_teams = set(
        schedule.loc[schedule["week"].eq(target_week), "home_team"].astype(str)
    ) | set(schedule.loc[schedule["week"].eq(target_week), "away_team"].astype(str))
    current_states = build_current_team_states(
        population=population,
        observations=observations,
        snapshots=snapshots,
        terminal=terminal,
        priors=priors,
        historical_terminal=historical_terminal,
        as_of=as_of,
        target_week=target_week,
        target_teams=target_teams,
    )
    verify_current_state(
        population=population,
        observations=observations,
        snapshots=snapshots,
        terminal=terminal,
        priors=priors,
        historical_terminal=historical_terminal,
        current=current_states,
        target_week=target_week,
        target_teams=target_teams,
    )
    historical_features = (
        _historical_features(storage, bridge) if include_historical_features else None
    )
    historical_population, historical_events = _population_and_events(
        storage,
        _read_json(
            storage,
            str((bridge.get("parents") or {}).get("measurement_manifest_uri", "")),
        )[0],
    )
    target_schedule = schedule[
        schedule["season"].eq(2026) & schedule["week"].eq(target_week)
    ].copy()
    target_schedule = target_schedule[
        ~target_schedule["game_id"].isin(population["game_id"])
    ]
    # Offset rows are emitted for scheduled targets, but unusable target rows
    # never advance the evidence accumulator.
    target_schedule = target_schedule.assign(
        forecast_eligible=True,
        schedule_completed=False,
        outcome_valid=False,
        measurement_usable=False,
    )
    combined_population = pd.concat(
        [historical_population, population, target_schedule],
        ignore_index=True,
        sort=False,
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
        current_states,
        offsets.offsets,
        as_of=as_of,
        target_week=target_week,
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
        variance = values.get("2025", values.get(2025))
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
