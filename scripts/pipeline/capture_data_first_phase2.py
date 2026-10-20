#!/usr/bin/env python3
"""Plan or execute bounded, Preview-only data-first source capture."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import cfbd
import pandas as pd
import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import (
    catalog_connection_url,
    register_source_capture,
    source_capture_by_id,
)
from cks_picks_cfb.data.data_first_phase2 import (
    CaptureRequest,
    active_pregame_request_plan,
    execute_with_bounded_retries,
    historical_request_plan,
    merge_schedule_observations,
    validate_postseason_schedule_capture,
)
from cks_picks_cfb.data.lake import capture_provider_records, read_source_capture
from cks_picks_cfb.data.storage import get_storage

OUTPUT_ROOT = "artifacts/research/data-first-football-v1/phase2/capture/runs"


def _git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _plain(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    raise TypeError(f"CFBD record cannot be serialized: {type(value)!r}")


def _immutable_json(storage, uri: str, value: dict[str, Any]) -> None:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode()
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"immutable capture artifact collision: {uri}")
        return
    storage.write_bytes(payload, uri)


def _existing_request_shas(conn_url: str, candidates: list[CaptureRequest]) -> set[str]:
    result: set[str] = set()
    with psycopg.connect(conn_url) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        with conn.cursor() as cur:
            cur.execute(
                "SELECT request FROM catalog.source_captures WHERE state='registered'"
            )
            for (request,) in cur.fetchall():
                stored = dict(request or {})
                parameters = dict(stored.get("parameters") or {})
                for candidate in candidates:
                    if (
                        stored.get("provider") == candidate.provider
                        and stored.get("endpoint") == candidate.endpoint
                        and str(stored.get("entity") or "").endswith(candidate.entity)
                        and all(
                            parameters.get(key) == value
                            for key, value in candidate.parameters.items()
                        )
                    ):
                        result.add(candidate.request_sha)
    return result


def _fetch(client: cfbd.ApiClient, request: CaptureRequest) -> list[dict[str, Any]]:
    endpoints = {
        "GamesApi.get_games": (cfbd.GamesApi, "get_games"),
        "GamesApi.get_game_team_stats": (cfbd.GamesApi, "get_game_team_stats"),
        "PlaysApi.get_plays": (cfbd.PlaysApi, "get_plays"),
        "TeamsApi.get_teams": (cfbd.TeamsApi, "get_teams"),
        "PlayersApi.get_returning_production": (
            cfbd.PlayersApi,
            "get_returning_production",
        ),
        "CoachesApi.get_coaches": (cfbd.CoachesApi, "get_coaches"),
        "RecruitingApi.get_team_recruiting_rankings": (
            cfbd.RecruitingApi,
            "get_team_recruiting_rankings",
        ),
    }
    api_class, method_name = endpoints[request.endpoint]
    method = getattr(api_class(client), method_name)
    rows = method(**dict(request.parameters), _request_timeout=60)
    return [_plain(row) for row in rows]


def _quota(client: cfbd.ApiClient, required: int) -> dict[str, Any]:
    info = cfbd.InfoApi(client).get_user_info(_request_timeout=30)
    remaining = info.remaining_calls
    if remaining is None or int(remaining) < required:
        raise RuntimeError(
            f"CFBD quota is insufficient: remaining={remaining}, required={required}"
        )
    return {
        "tier_name": info.tier_name,
        "monthly_limit": info.monthly_limit,
        "remaining_before": int(remaining),
        "used_before": info.used_calls,
        "reset_at": info.reset_at,
    }


def _supplemental_schedule(
    storage, conn_url: str, capture_ids: list[str]
) -> list[pd.DataFrame]:
    frames = []
    for capture_id in capture_ids:
        capture = source_capture_by_id(conn_url, capture_id)
        validate_postseason_schedule_capture(capture)
        frames.append(read_source_capture(storage, capture))
    return frames


def _schedule(
    storage, audit_prefix: str, conn_url: str, capture_ids: list[str]
) -> pd.DataFrame:
    uri = f"{audit_prefix.rstrip('/')}/schedule-denominator.parquet"
    schedule = pd.read_parquet(io.BytesIO(storage.read_bytes(uri)))
    if not capture_ids:
        return schedule
    return merge_schedule_observations(
        schedule, _supplemental_schedule(storage, conn_url, capture_ids)
    )


def _plan(args, storage, conn_url: str) -> list[CaptureRequest]:
    if args.kind == "pregame":
        return active_pregame_request_plan(args.season)
    schedule = _schedule(
        storage, args.audit_prefix, conn_url, list(args.schedule_capture_id or [])
    )
    candidates = historical_request_plan(schedule)
    existing = _existing_request_shas(conn_url, candidates)
    return historical_request_plan(schedule, existing_request_shas=existing)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("historical", "pregame"), required=True)
    parser.add_argument("--mode", choices=("dry-run", "apply"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--environment", choices=("preview",), required=True)
    parser.add_argument("--audit-prefix")
    parser.add_argument("--schedule-capture-id", action="append", default=[])
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--max-requests", type=int, required=True)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--expected-code-sha")
    args = parser.parse_args()
    if os.getenv("CFB_STORAGE_BACKEND", "").casefold() != "r2":
        raise RuntimeError("Phase 2 capture requires CFB_STORAGE_BACKEND=r2")
    if args.environment != "preview":
        raise RuntimeError("Phase 2 capture requires --environment preview")
    if args.kind == "historical" and not args.audit_prefix:
        raise ValueError("historical capture requires --audit-prefix")
    if args.kind != "historical" and args.schedule_capture_id:
        raise ValueError("--schedule-capture-id is only valid for historical capture")
    if not 1 <= args.max_attempts <= 5:
        raise ValueError("--max-attempts must be between 1 and 5")
    if args.mode == "apply" and args.expected_code_sha != _git_sha():
        raise ValueError("apply requires --expected-code-sha equal to committed HEAD")
    storage = get_storage(environment="preview")
    conn_url = catalog_connection_url("preview")
    requests = _plan(args, storage, conn_url)
    if len(requests) > args.max_requests:
        raise RuntimeError(
            f"planned {len(requests)} requests exceeds --max-requests={args.max_requests}"
        )
    plan = {
        "schema_version": "data_first_phase2_capture_plan_v1",
        "kind": args.kind,
        "run_id": args.run_id,
        "request_count": len(requests),
        "requests": [
            asdict(request) | {"request_sha": request.request_sha}
            for request in requests
        ],
    }
    if args.mode == "dry-run":
        print(json.dumps(plan, indent=2, sort_keys=True))
        return
    client = cfbd.ApiClient(cfbd.Configuration(access_token=os.environ["CFBD_API_KEY"]))
    quota = _quota(client, len(requests))
    prefix = f"{OUTPUT_ROOT}/{args.run_id}"
    results = []
    for request in requests:
        result_uri = f"{prefix}/requests/{request.request_sha}.json"
        if storage.exists(result_uri):
            results.append(json.loads(storage.read_bytes(result_uri)))
            continue
        captured_at = datetime.now(timezone.utc)
        rows = None
        errors = []
        attempts = 0
        try:
            rows, attempts, errors = execute_with_bounded_retries(
                lambda: _fetch(client, request), max_attempts=args.max_attempts
            )
            if rows:
                manifest = asdict(request)
                capture = capture_provider_records(
                    storage,
                    provider=request.provider,
                    entity=f"data_first_{request.entity}",
                    records=rows,
                    captured_at=captured_at,
                    effective_at=captured_at if args.kind == "pregame" else None,
                    request=manifest,
                    response_metadata={
                        "timing_class": "authentic_pregame"
                        if args.kind == "pregame"
                        else "historically_reconstructed",
                        "phase": "data_first_phase2",
                    },
                )
                register_source_capture(conn_url, capture)
                result = {
                    "request_sha": request.request_sha,
                    "state": "captured",
                    "capture_id": capture.capture_id,
                    "row_count": capture.row_count,
                    "captured_at": capture.captured_at.isoformat(),
                    "attempts": attempts,
                    "attempt_errors": errors,
                }
            else:
                result = {
                    "request_sha": request.request_sha,
                    "state": "empty_provider_response",
                    "capture_id": None,
                    "row_count": 0,
                    "captured_at": captured_at.isoformat(),
                    "attempts": attempts,
                    "attempt_errors": errors,
                }
        except Exception as exc:
            result = {
                "request_sha": request.request_sha,
                "state": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc)[-2000:],
                "captured_at": captured_at.isoformat(),
                "attempts": args.max_attempts,
                "attempt_errors": errors,
            }
        _immutable_json(storage, result_uri, result)
        results.append(result)
    failed = [row for row in results if row["state"] != "captured"]
    manifest = {
        **plan,
        "schema_version": "data_first_phase2_capture_run_v2",
        "environment": args.environment,
        "state": "complete" if not failed else "complete_with_gaps",
        "code_sha": args.expected_code_sha,
        "quota": quota,
        "results": results,
        "failed_or_empty_count": len(failed),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    _immutable_json(storage, f"{prefix}/manifest.json", manifest)
    print(json.dumps({"state": manifest["state"], "prefix": prefix}, sort_keys=True))
    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
