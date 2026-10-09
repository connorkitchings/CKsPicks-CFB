"""Expected provider requests from a reviewed inventory, never the attempt ledger."""

import hashlib
import io
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from cks_picks_cfb.data.week_policy import (
    WeekPolicySpec,
    build_policy_rows,
    policy_config_sha,
)
from cks_picks_cfb.quality.loaders import request_key

WEEKLY_ENTITIES = ("plays", "game_stats")


def read_pinned_schedule(
    storage: Any, ref: Mapping[str, Any], *, season: int
) -> pd.DataFrame:
    """Read exact schedule bytes, including FBS–FCS games absent from Silver games."""
    from cks_picks_cfb.data.lake import DatasetRef
    from cks_picks_cfb.quality.loaders import read_quality_dataset

    if ref.get("dataset") != "games":
        raise ValueError("Inventory schedule must be games")
    if ref.get("schema_version") != "raw_games_snapshot_v1":
        return read_quality_dataset(storage, DatasetRef(**ref))
    uri = ref.get("uri")
    if uri != f"raw/games/year={season}/part-0.parquet":
        raise ValueError("Raw schedule URI differs from inventory season")
    raw = storage.read_bytes(uri)
    digest = hashlib.sha256(raw).hexdigest()
    if ref.get("content_sha") != digest or ref.get("version_id") != digest[:24]:
        raise ValueError("Raw schedule bytes differ from pinned identity")
    schedule = pd.read_parquet(io.BytesIO(raw))
    return schedule.rename(
        columns={"id": "game_id", "week": "provider_week", "start_date": "kickoff_utc"}
    )


def build_expected_request_inventory(
    schedule: pd.DataFrame,
    *,
    schedule_ref: Mapping[str, Any],
    policy: WeekPolicySpec,
    season: int,
    canonical_week: int,
    entities: Sequence[str] = WEEKLY_ENTITIES,
    season_type: str = "regular",
    classification: str = "fbs",
) -> dict[str, Any]:
    """Derive weekly requests from a pinned schedule, never the attempts table."""
    if not schedule_ref.get("version_id") or not schedule_ref.get("content_sha"):
        raise ValueError("Pinned schedule identity is required")
    if set(entities) - set(WEEKLY_ENTITIES) or not entities:
        raise ValueError("Unsupported or empty weekly entity set")
    if len(set(entities)) != len(entities):
        raise ValueError("Duplicate weekly entity")
    required = {"season", "game_id", "provider_week", "kickoff_utc"}
    if required - set(schedule):
        raise ValueError(f"Schedule lacks {sorted(required - set(schedule))}")
    scoped = schedule.loc[schedule["season"].eq(season)].copy()
    if "season_type" in scoped:
        scoped = scoped.loc[scoped["season_type"].eq(season_type)].copy()
    if {"home_classification", "away_classification"} <= set(scoped):
        scoped = scoped.loc[
            scoped["home_classification"].eq(classification)
            | scoped["away_classification"].eq(classification)
        ].copy()
    if "completed" in scoped:
        completed = scoped["completed"].fillna(False).astype(bool)
    elif {"home_points", "away_points"} <= set(scoped):
        completed = scoped["home_points"].notna() & scoped["away_points"].notna()
    else:
        raise ValueError("Pinned schedule needs completed status or both final scores")
    completed_ids = set(scoped.loc[completed, "game_id"].astype(int))
    if scoped.duplicated("game_id").any():
        raise ValueError("Pinned schedule has duplicate game IDs")
    assigned = build_policy_rows(scoped, policy, season=season)
    selected = assigned.loc[assigned["canonical_week"].eq(canonical_week)]
    if selected.empty:
        raise ValueError("Pinned schedule has no games for canonical week")
    requests = []
    for entity in entities:
        for provider_week, group in selected.groupby("provider_week", sort=True):
            requests.append(
                {
                    "provider": "cfbd",
                    "entity": entity,
                    "required_completed_game_ids": sorted(
                        completed_ids & set(group["game_id"].astype(int))
                    ),
                    "parameters": {
                        "year": season,
                        "season_type": season_type,
                        "week": int(provider_week),
                        "canonical_week": canonical_week,
                        "classification": classification,
                        "expected_game_ids": sorted(
                            group["game_id"].astype(int).tolist()
                        ),
                    },
                }
            )
    inventory = {
        "schema_version": "cfbd_expected_requests_v1",
        "season": season,
        "canonical_week": canonical_week,
        "schedule_ref": dict(schedule_ref),
        "week_policy_version": policy.policy_version,
        "week_policy_sha256": policy_config_sha(policy, season=season),
        "requests": requests,
    }
    expected_request_keys(inventory, season)
    return inventory


def verify_expected_request_inventory(
    storage: Any, manifest: Mapping[str, Any]
) -> None:
    """Rebuild an R2 inventory from its immutable schedule and policy sources."""
    from pathlib import Path

    from cks_picks_cfb.data.week_policy import load_week_policy_spec

    ref = manifest["schedule_ref"]
    policy_path = Path(manifest["week_policy_path"])
    if not policy_path.is_relative_to(Path("conf/policy")):
        raise ValueError("Inventory week policy must be repository policy")
    policy = load_week_policy_spec(policy_path)
    schedule = read_pinned_schedule(storage, ref, season=int(manifest["season"]))
    expected = build_expected_request_inventory(
        schedule,
        schedule_ref=manifest["schedule_ref"],
        policy=policy,
        season=int(manifest["season"]),
        canonical_week=int(manifest["canonical_week"]),
        entities=tuple(dict.fromkeys(item["entity"] for item in manifest["requests"])),
    )
    for field in ("requests", "week_policy_version", "week_policy_sha256"):
        if manifest.get(field) != expected[field]:
            raise ValueError(f"Expected-request inventory differs from pinned {field}")


def expected_request_keys(manifest: Mapping[str, Any], year: int) -> set[str]:
    """Validate the independent request inventory and return exact request identities.

    Parameters use the same full identity as SourceRequest, including expected game
    ids and provider/canonical weeks. A request from a smaller slate cannot satisfy it.
    The schedule reference binds the inventory to an immutable schedule, rather than
    to the subset of games already present in the serving database.
    """
    if manifest.get("schema_version") != "cfbd_expected_requests_v1":
        raise ValueError("unknown expected-request inventory schema")
    if manifest.get("season") != year:
        raise ValueError("expected-request inventory season differs")
    ref = manifest.get("schedule_ref", {})
    if not ref.get("version_id") or not ref.get("content_sha"):
        raise ValueError("expected-request inventory needs a pinned schedule_ref")
    requests = manifest.get("requests")
    if not isinstance(requests, list) or not requests:
        raise ValueError("expected-request inventory must not be empty")
    keys = set()
    for item in requests:
        parameters = item.get("parameters")
        if (
            item.get("provider") != "cfbd"
            or not item.get("entity")
            or not isinstance(parameters, Mapping)
            or parameters.get("year") != year
        ):
            raise ValueError("invalid expected CFBD request")
        completed = item.get("required_completed_game_ids", [])
        expected_ids = parameters.get("expected_game_ids", [])
        if not isinstance(completed, list) or not set(completed) <= set(expected_ids):
            raise ValueError("completed game ids are outside the expected schedule")
        key = request_key(item["entity"], parameters)
        if key in keys:
            raise ValueError("duplicate expected request")
        keys.add(key)
    return keys
