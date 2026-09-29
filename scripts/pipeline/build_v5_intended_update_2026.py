#!/usr/bin/env python3
"""Build a complete, immutable 2026 intended-update rating season manifest."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.audit.corpus import concat_all, read_any
from cks_picks_cfb.data.data_first_phase2d import signed_payload, verify_signed_payload
from cks_picks_cfb.data.lake import canonical_frame_digest
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.forecast.live_sources import _read_frame, load_live_forecast_sources
from cks_picks_cfb.ratings.possession_intended_update import IntendedUpdate
from cks_picks_cfb.ratings_lab.artifacts import canonical_json
from cks_picks_cfb.ratings_lab.corpus import PINS
from contracts.teams import TEAM_LOGO_MAP

OUTPUT_ROOT = (
    "artifacts/research/data-first-football-v1/possession-v1/intended-update-2026/runs"
)
SCHEMA_VERSION = "v5_intended_update_2026_rating_manifest_v1"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_signed(storage: Any, uri: str, expected_sha: str) -> dict[str, Any]:
    raw = storage.read_bytes(uri)
    if _sha(raw) != expected_sha:
        raise ValueError(f"certified source checksum changed: {uri}")
    value = json.loads(raw)
    verify_signed_payload(value, label=uri)
    return value


def _inputs(
    lock: dict[str, Any], cache: Path | None
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if cache is not None:
        schedule = pd.read_parquet(cache / "schedule.parquet")
        observations = pd.read_parquet(cache / "live_measurement_observations.parquet")
        priors = pd.read_parquet(cache / "live_rating_priors.parquet")
        terminal = pd.read_parquet(cache / "terminal.parquet")
    else:
        if os.getenv("CFB_STORAGE_BACKEND") != "r2":
            raise ValueError("2026 rating artifact requires CFB_STORAGE_BACKEND=r2")
        storage = get_storage(environment="preview")
        parent = lock["research_source_import"]
        replay_parents = parent["replay_parents"]
        measurement = _read_signed(
            storage,
            replay_parents["measurement_uri"],
            replay_parents["measurement_raw_sha256"],
        )
        rating = _read_signed(
            storage,
            replay_parents["rating_uri"],
            replay_parents["rating_raw_sha256"],
        )
        historical_uri, historical_sha = PINS["measurement"]
        historical = _read_signed(storage, historical_uri, historical_sha)
        live_manifest = _read_signed(
            storage, parent["live_manifest_uri"], parent["live_manifest_sha256"]
        )
        live = load_live_forecast_sources(
            storage=storage,
            measurement_uri=replay_parents["measurement_uri"],
            rating_uri=replay_parents["rating_uri"],
            schedule_uri=replay_parents["schedule_uri"],
            bridge_uri=replay_parents["bridge_uri"],
            as_of=live_manifest["identity"]["as_of"],
            target_week=int(lock["active_week"]["week"]),
            include_historical_features=False,
        )
        schedule = live["schedule"]
        observations = _read_frame(
            storage, measurement["output_refs"]["observations"], "observations"
        )
        priors = _read_frame(storage, rating["output_refs"]["priors"], "priors")
        terminal = concat_all(read_any(storage, historical["output_refs"]["terminal"]))
    names = lock["games"]["columns"]
    locked_games = [dict(zip(names, row, strict=True)) for row in lock["games"]["rows"]]
    game_ids = {int(row["game_id"]) for row in locked_games}
    schedule = schedule[schedule.game_id.astype(int).isin(game_ids)].copy()
    if len(schedule) != len(game_ids) or set(schedule.game_id.astype(int)) != game_ids:
        raise ValueError("2026 rating schedule differs from locked game keys")
    schedule["kickoff_utc"] = pd.to_datetime(schedule.kickoff_utc, utc=True)
    for row in locked_games:
        candidate = schedule[schedule.game_id.eq(int(row["game_id"]))].iloc[0]
        if (
            int(candidate.week) != int(row["week"])
            or str(candidate.home_team)
            != TEAM_LOGO_MAP.get(str(row["home_team"]), str(row["home_team"]))
            or str(candidate.away_team)
            != TEAM_LOGO_MAP.get(str(row["away_team"]), str(row["away_team"]))
            or pd.Timestamp(candidate.kickoff_utc) != pd.Timestamp(row["start_date"])
        ):
            raise ValueError("2026 schedule differs from locked production game")
    if len(priors) != 276 or priors.duplicated(["team", "unit_role"]).any():
        raise ValueError("certified preseason priors changed")
    observations = observations[observations.game_id.astype(int).isin(game_ids)].copy()
    return schedule, observations, priors, terminal


def _parquet(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False, compression="zstd")
    return buffer.getvalue()


def _generation_digest(frame: pd.DataFrame, columns: list[str]) -> str:
    ordered = frame.sort_values(
        ["season", "week", "game_id", "team"], kind="mergesort", na_position="first"
    )
    return canonical_frame_digest(ordered, columns=columns)


def build(
    *,
    run_id: str,
    code_sha: str,
    source_lock: Path,
    output: Path,
    cache: Path | None = None,
    previous_manifest: Path | None = None,
) -> dict[str, Any]:
    if not re.fullmatch(r"v5-intended-update-2026-[a-z0-9-]+", run_id):
        raise ValueError("invalid 2026 intended-update run ID")
    forbidden = Path(__file__).resolve().parents[2] / "data"
    if output.resolve() == forbidden or forbidden in output.resolve().parents:
        raise ValueError("rating output cannot use repository ./data")
    lock_raw = source_lock.read_bytes()
    lock = json.loads(lock_raw)
    if lock.get("schema_version") != "v5_intended_update_2026_source_lock_v1":
        raise ValueError("unknown 2026 source lock")
    cutoffs = {
        int(week): str(cutoff) for week, cutoff in lock["post_week_cutoffs"].items()
    }
    if sorted(cutoffs) != list(range(max(cutoffs) + 1)):
        raise ValueError("post-week cutoffs must be continuous from Week 0")
    schedule, observations, priors, terminal = _inputs(lock, cache)
    engine = IntendedUpdate(
        schedule=schedule,
        observations=observations,
        priors=priors,
        historical_terminal=terminal,
    )
    pregame = engine.pregame()
    game_count = len(schedule)
    if (
        len(pregame.rating_states) != 4 * game_count
        or len(pregame.team_states) != 2 * game_count
    ):
        raise ValueError("2026 pregame rating population changed")
    current_roles = []
    current_teams = []
    for week, cutoff in sorted(cutoffs.items()):
        generation = engine.current(post_week=week, cutoff_utc=cutoff)
        current_roles.append(generation.rating_states)
        current_teams.append(generation.team_states)
    current_role = pd.concat(current_roles, ignore_index=True)
    current_team = pd.concat(current_teams, ignore_index=True)
    if len(current_team) != 138 * len(cutoffs) or len(current_role) != 276 * len(
        cutoffs
    ):
        raise ValueError("2026 current generations do not cover all 138 teams")
    generations = {}
    team_columns = [
        "season",
        "week",
        "game_id",
        "cutoff_utc",
        "team",
        "offense_rating",
        "offense_variance",
        "defense_rating",
        "defense_variance",
        "overall_rating",
        "overall_variance",
    ]
    for week in range(6):
        part = pregame.team_states[pregame.team_states.week.eq(week)]
        if not part.empty:
            generations[f"pregame_w{week}"] = _generation_digest(part, team_columns)
    for post_week in cutoffs:
        part = current_team[current_team.week.eq(post_week + 1)]
        generations[f"current_post_w{post_week}"] = _generation_digest(
            part, team_columns
        )
    if previous_manifest:
        previous = json.loads(previous_manifest.read_bytes())
        verify_signed_payload(previous, label="previous 2026 rating manifest")
        for name, digest in previous["generation_hashes"].items():
            if generations.get(name) != digest:
                raise ValueError(f"previous rating generation drifted: {name}")
    output.mkdir(parents=True, exist_ok=True)
    frames = {
        "priors": priors.sort_values(["team", "unit_role"], kind="mergesort"),
        "pregame_roles": pregame.rating_states,
        "pregame_teams": pregame.team_states,
        "current_roles": current_role,
        "current_teams": current_team,
    }
    prefix = f"{OUTPUT_ROOT}/{run_id}"
    refs = {}
    for name, frame in frames.items():
        raw = _parquet(frame)
        (output / f"{name}.parquet").write_bytes(raw)
        refs[name] = {
            "uri": f"{prefix}/{name}.parquet",
            "raw_sha256": _sha(raw),
            "rows": len(frame),
        }
    manifest = signed_payload(
        {
            "schema_version": SCHEMA_VERSION,
            "state": "frozen",
            "identity": {
                "run_id": run_id,
                "season": 2026,
                "environment": "preview",
                "code_sha": code_sha,
            },
            "candidate_id": "ppp__rho_0_60__exposure__game_at_cutoff_v1",
            "parents": {
                "source_lock_sha256": _sha(lock_raw),
                "source_lock_name": source_lock.name,
                "historical_measurement_manifest_sha256": PINS["measurement"][1],
                "measurement_manifest_sha256": lock["research_2026_measurement_sha256"],
                "accepted_rating_manifest_sha256": lock["research_2026_rating_sha256"],
                "schedule_content_sha256": lock["research_source_import"][
                    "replay_parents"
                ]["schedule_content_sha256"],
            },
            "output_refs": refs,
            "generation_hashes": generations,
            "post_week_cutoffs": {str(week): cutoff for week, cutoff in cutoffs.items()},
            "pregame_games": game_count,
            "current_teams_per_generation": 138,
            "production_activation_authorized": False,
        }
    )
    (output / "rating-manifest.json").write_bytes(canonical_json(manifest))
    return manifest


def _write_once(storage: Any, uri: str, raw: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != raw:
            raise ValueError(f"immutable rating object collision: {uri}")
        return
    storage.write_bytes(raw, uri)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-code-sha", required=True)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--local-output", type=Path, required=True)
    parser.add_argument("--local-cache", type=Path)
    parser.add_argument("--previous-manifest", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preflight-evidence", type=Path)
    args = parser.parse_args()
    if args.apply and args.local_cache:
        raise ValueError("rating publication must re-read certified R2 parents")
    manifest = build(
        run_id=args.run_id,
        code_sha=args.expected_code_sha,
        source_lock=args.source_lock,
        output=args.local_output,
        cache=args.local_cache,
        previous_manifest=args.previous_manifest,
    )
    if not args.apply:
        print(json.dumps(manifest, sort_keys=True))
        return
    if (
        not args.preflight_evidence
        or json.loads(args.preflight_evidence.read_bytes()) != manifest
    ):
        raise ValueError("rating apply differs from reviewed preflight")
    actual_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain=v1"], text=True
    ).strip()
    if dirty or actual_sha != args.expected_code_sha:
        raise ValueError("rating publication requires expected clean committed code")
    storage = get_storage(environment="preview")
    for name, ref in manifest["output_refs"].items():
        _write_once(
            storage, ref["uri"], (args.local_output / f"{name}.parquet").read_bytes()
        )
    uri = f"{OUTPUT_ROOT}/{args.run_id}/rating-manifest.json"
    _write_once(storage, uri, (args.local_output / "rating-manifest.json").read_bytes())
    print(
        json.dumps(
            {"manifest_uri": uri, "manifest_raw_sha256": _sha(storage.read_bytes(uri))}
        )
    )


if __name__ == "__main__":
    main()
