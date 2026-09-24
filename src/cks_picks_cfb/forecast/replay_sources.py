"""Certified, point-in-time sources for retrospective 2026 V5 forecasts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd

from cks_picks_cfb.data.data_first_live_forecast_v1 import (
    BRIDGE_MANIFEST_URI,
    verify_application_parents,
)
from cks_picks_cfb.data.data_first_phase2d import verify_signed_payload
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.forecast.live_sources import (
    _population_and_events,
    _team_states,
    _validate_schedule_matches_population,
)
from cks_picks_cfb.forecast.offsets import build_offsets
from cks_picks_cfb.forecast.replay import ReplayFrame, build_replay_application_frame
from cks_picks_cfb.preseason_features import canonical_team


class ReplaySourceError(ValueError):
    """A replay parent lacks certified lineage or complete schedule coverage."""


def _signed(storage: Any, uri: str) -> tuple[dict[str, Any], str]:
    raw = storage.read_bytes(uri)
    payload = json.loads(raw)
    verify_signed_payload(payload, label=uri)
    return payload, hashlib.sha256(raw).hexdigest()


def load_replay_sources(
    storage: Any,
    *,
    measurement_uri: str,
    rating_uri: str,
    bundle_uri: str,
    bundle_sha256: str,
) -> tuple[ReplayFrame, dict[str, Any], dict[str, str]]:
    """Reconstruct every eligible 2026 game from the exact 07/08/11C parents."""
    measurement, measurement_sha = _signed(storage, measurement_uri)
    rating, rating_sha = _signed(storage, rating_uri)
    bridge, bridge_sha = _signed(storage, BRIDGE_MANIFEST_URI)
    verify_application_parents(
        measurement=measurement,
        measurement_uri=measurement_uri,
        measurement_raw_sha256=measurement_sha,
        rating_replay=rating,
        rating_replay_uri=rating_uri,
        rating_replay_raw_sha256=rating_sha,
        bridge=bridge,
        bridge_uri=BRIDGE_MANIFEST_URI,
        bridge_raw_sha256=bridge_sha,
    )
    certification_uri = f"{measurement_uri.rsplit('/', 1)[0]}/certification.json"
    certification, _ = _signed(storage, certification_uri)
    if (
        certification.get("manifest_sha256") != measurement.get("certification_sha256")
        or certification.get("all_checks_passed") is not True
    ):
        raise ReplaySourceError("2026 measurement certification differs")
    verifier_uri = f"{rating_uri.rsplit('/', 1)[0]}/verification/verifier-manifest.json"
    rating_verifier, _ = _signed(storage, verifier_uri)
    if (
        rating_verifier.get("state") != "verified"
        or rating_verifier.get("retained_manifest_raw_sha256") != rating_sha
    ):
        raise ReplaySourceError("2026 rating replay lacks independent verification")
    raw_bundle = storage.read_bytes(bundle_uri)
    if hashlib.sha256(raw_bundle).hexdigest() != bundle_sha256:
        raise ReplaySourceError("pinned inference bundle checksum differs")
    bundle = json.loads(raw_bundle)
    verify_signed_payload(bundle, label="V5 inference bundle")
    if (
        bundle.get("bridge_manifest_uri") != BRIDGE_MANIFEST_URI
        or bundle.get("bridge_manifest_raw_sha256") != bridge_sha
    ):
        raise ReplaySourceError("inference bundle has another accepted bridge")
    repair_uri = str(measurement.get("repair_manifest_uri") or "")
    repair, repair_sha = _signed(storage, repair_uri)
    if repair_sha != measurement.get("repair_manifest_raw_sha256"):
        raise ReplaySourceError("2026 measurement repair parent changed")
    schedule_value = (
        (repair.get("parents") or {}).get("season_2026_inputs") or {}
    ).get("schedule_ref") or {}
    schedule = read_dataset(
        storage,
        DatasetRef(
            **{
                name: schedule_value[name]
                for name in (
                    "dataset",
                    "version_id",
                    "schema_version",
                    "content_sha",
                    "uri",
                )
            }
        ),
    )
    for side in ("home", "away"):
        schedule[f"{side}_team"] = schedule[f"{side}_team"].map(canonical_team)
    if {"home_classification", "away_classification"} <= set(schedule):
        schedule = schedule[
            schedule["home_classification"].eq("fbs")
            & schedule["away_classification"].eq("fbs")
        ].copy()
    population, events = _population_and_events(storage, measurement)
    _validate_schedule_matches_population(schedule=schedule, population=population)
    latest_week = int(population["week"].max())
    expected = set(
        schedule.loc[schedule["week"].le(latest_week), "game_id"].astype(int)
    )
    actual = set(population["game_id"].astype(int))
    if expected != actual:
        raise ReplaySourceError("2026 replay population omits a completed slate game")
    historical_uri = str((bridge.get("parents") or {})["measurement_manifest_uri"])
    historical, historical_sha = _signed(storage, historical_uri)
    if historical_sha != bridge["parents"]["measurement_manifest_raw_sha256"]:
        raise ReplaySourceError("historical measurement parent changed")
    prior_population, prior_events = _population_and_events(storage, historical)
    offsets = build_offsets(
        pd.concat([prior_population, population], ignore_index=True, sort=False),
        pd.concat([prior_events, events], ignore_index=True, sort=False),
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
    replay = build_replay_application_frame(
        population,
        _team_states(storage, rating),
        offsets.offsets,
    )
    parents = {
        "measurement_uri": measurement_uri,
        "measurement_raw_sha256": measurement_sha,
        "rating_uri": rating_uri,
        "rating_raw_sha256": rating_sha,
        "bridge_uri": BRIDGE_MANIFEST_URI,
        "bridge_raw_sha256": bridge_sha,
        "bundle_uri": bundle_uri,
        "bundle_sha256": bundle_sha256,
        "schedule_uri": str(schedule_value["uri"]),
        "schedule_content_sha256": str(schedule_value["content_sha"]),
        "rating_verifier_uri": verifier_uri,
        "certification_uri": certification_uri,
    }
    return replay, bundle, parents
