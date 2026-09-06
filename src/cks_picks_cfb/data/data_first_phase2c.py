"""Pure lineage and immutable-artifact contracts for Phase 2c."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from cks_picks_cfb.data.data_first_phase2 import DEVELOPMENT_SEASONS, FORBIDDEN_SEASONS

RUN_ID_SUFFIX = "phase2c-expanded-silver-v1"
IDENTITY_SCHEMA = "data_first_phase2c_run_identity_v1"
CHECKPOINT_SCHEMA = "data_first_phase2c_season_checkpoint_v1"
REF_SET_SCHEMA = "data_first_phase2c_ref_set_v1"
OUTPUT_DATASETS = (
    "fbs_involved_games",
    "game_outcomes",
    "plays",
    "team_game_stats",
    "byplay",
    "drives",
    "reconciled_team_game",
    "source_reconciliation",
)


class Phase2cError(ValueError):
    """Raised when sealed Phase 2c lineage cannot be verified."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def parse_manifest(
    *, uri: str, raw_bytes: bytes, allowed_states: set[str], label: str
) -> tuple[dict[str, Any], dict[str, str]]:
    """Parse a sealed JSON manifest and retain its physical checksum."""
    try:
        raw = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Phase2cError(f"{label} manifest is malformed: {uri}") from exc
    if not isinstance(raw, dict) or raw.get("state") not in allowed_states:
        raise Phase2cError(f"{label} manifest is not sealed in an allowed state: {uri}")
    return raw, {
        "uri": uri,
        "raw_sha256": sha256_bytes(raw_bytes),
        "declared_sha256": str(raw.get("manifest_sha256") or ""),
    }


def r1_capture_ids(
    source_set: Mapping[str, Any], *, season: int, entity: str
) -> list[str]:
    matches = [
        row
        for row in source_set.get("entries", [])
        if int(row.get("season", -1)) == season and row.get("entity") == entity
    ]
    if len(matches) != 1:
        raise Phase2cError(f"R1 source set must contain one {season}/{entity} entry")
    ids = [str(value) for value in matches[0].get("capture_ids", [])]
    if not ids or len(ids) != len(set(ids)):
        raise Phase2cError(f"R1 source set has invalid {season}/{entity} captures")
    return sorted(ids)


def require_exact_regular_lineage(
    source_set: Mapping[str, Any],
    regular: Mapping[str, Mapping[int, Sequence[str]]],
) -> None:
    """Require Phase 1 regular captures to equal the certified R1 source set."""
    for entity, by_season in regular.items():
        for season in DEVELOPMENT_SEASONS:
            actual = sorted(str(value) for value in by_season.get(season, ()))
            expected = r1_capture_ids(source_set, season=season, entity=entity)
            if actual != expected:
                raise Phase2cError(
                    f"Phase 1/R1 regular capture mismatch for {season}/{entity}"
                )


def build_run_identity(
    *,
    run_id: str,
    environment: str,
    as_of: str,
    code_sha: str,
    configuration: Mapping[str, Any],
    input_manifests: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    if not run_id.endswith(RUN_ID_SUFFIX):
        raise Phase2cError(f"run_id must end with {RUN_ID_SUFFIX}")
    if environment != "preview":
        raise Phase2cError("Phase 2c identity requires Preview")
    if not code_sha:
        raise Phase2cError("Phase 2c identity requires a committed code SHA")
    identity = {
        "schema_version": IDENTITY_SCHEMA,
        "run_id": run_id,
        "environment": environment,
        "as_of": as_of,
        "code_sha": code_sha,
        "configuration": dict(configuration),
        "configuration_sha256": sha256_value(configuration),
        "input_manifests": [dict(item) for item in input_manifests],
        "seasons": list(DEVELOPMENT_SEASONS),
        "forbidden_seasons": list(FORBIDDEN_SEASONS),
        "output_datasets": list(OUTPUT_DATASETS),
    }
    identity["identity_sha256"] = sha256_value(identity)
    return identity


def require_identical_identity(
    existing: Mapping[str, Any], expected: Mapping[str, Any]
) -> None:
    if canonical_bytes(existing) != canonical_bytes(expected):
        raise Phase2cError("immutable Phase 2c run identity collision")


def checkpoint_payload(
    *, identity: Mapping[str, Any], entry: Mapping[str, Any]
) -> dict[str, Any]:
    outputs = entry.get("outputs") or {}
    if set(outputs) != set(OUTPUT_DATASETS):
        raise Phase2cError("Phase 2c checkpoint must contain all eight outputs")
    checkpoint = {
        "schema_version": CHECKPOINT_SCHEMA,
        "state": "complete",
        "identity_sha256": identity["identity_sha256"],
        "run_id": identity["run_id"],
        "season": entry["season"],
        "entry": dict(entry),
    }
    checkpoint["checkpoint_sha256"] = sha256_value(checkpoint)
    return checkpoint


def ref_set_payload(
    *, identity: Mapping[str, Any], entries: Sequence[Mapping[str, Any]], state: str
) -> dict[str, Any]:
    if state not in {"dry_run", "complete"}:
        raise Phase2cError(f"unsupported ref set state: {state}")
    seasons = [int(entry["season"]) for entry in entries]
    if seasons != list(DEVELOPMENT_SEASONS):
        raise Phase2cError("Phase 2c ref set must contain every permitted season once")
    if state == "complete":
        for entry in entries:
            if set((entry.get("outputs") or {})) != set(OUTPUT_DATASETS):
                raise Phase2cError("complete Phase 2c ref set requires all outputs")
    payload = {
        "schema_version": REF_SET_SCHEMA,
        "state": state,
        "identity": dict(identity),
        "entries": [dict(entry) for entry in entries],
    }
    payload["manifest_sha256"] = sha256_value(payload)
    return payload


def omission_reasons(
    *,
    missing_plays: Sequence[int],
    missing_stats: Sequence[int],
    declared_regular_plays: Sequence[int],
    postseason_game_ids: Sequence[int],
) -> dict[str, list[dict[str, int | str]]]:
    declared = set(int(value) for value in declared_regular_plays)
    postseason = set(int(value) for value in postseason_game_ids)
    play_rows = []
    for game_id in sorted(int(value) for value in missing_plays):
        if game_id in postseason:
            raise Phase2cError("postseason play detail is missing")
        if game_id not in declared:
            raise Phase2cError(
                "missing play detail is not an R1-declared regular omission"
            )
        play_rows.append({"game_id": game_id, "reason": "provider_response_omission"})
    stat_rows = []
    for game_id in sorted(int(value) for value in missing_stats):
        if game_id in postseason:
            raise Phase2cError("postseason team-stat detail is missing")
        stat_rows.append({"game_id": game_id, "reason": "provider_response_omission"})
    return {"plays": play_rows, "team_game_stats": stat_rows}


def require_expected_dry_run(entries: Sequence[Mapping[str, Any]]) -> None:
    if len(entries) != len(DEVELOPMENT_SEASONS):
        raise Phase2cError("dry-run does not contain ten seasons")
    games = outcomes = regular = postseason = fbs_fbs = fbs_fcs = 0
    for entry in entries:
        counts = entry["row_counts"]
        games += int(counts["fbs_involved_games"])
        outcomes += int(counts["game_outcomes"])
        regular += int(entry["season_type"].get("regular", 0))
        postseason += int(entry["season_type"].get("postseason", 0))
        fbs_fbs += int(entry["population"].get("fbs_fbs", 0))
        fbs_fcs += int(entry["population"].get("fbs_fcs", 0))
        if int(entry["reconciliation"].get("blocking", 0)):
            raise Phase2cError("dry-run has blocking reconciliation conflicts")
    expected = (8936, 8936, 8521, 415, 7792, 1144)
    if (games, outcomes, regular, postseason, fbs_fbs, fbs_fcs) != expected:
        raise Phase2cError(
            "dry-run corpus counts do not match the approved Phase 2c denominator"
        )
