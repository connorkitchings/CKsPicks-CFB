#!/usr/bin/env python3
"""Atomically select an exact, separately authorized successor run set."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.ops.lease import assert_active_pipeline_lease
from cks_picks_cfb.ops.public_selection import select_week_runs_batch
from cks_picks_cfb.ops.v5_release import assert_v5_database_environment


def _weeks(value: dict[str, str]) -> dict[int, str]:
    result = {int(week): str(run_id) for week, run_id in value.items()}
    if len(result) != len(value) or not all(result.values()):
        raise ValueError("batch packet has duplicate weeks or empty run IDs")
    return result


def _selected(cur, season: int, weeks: list[int]) -> dict[int, str | None]:
    cur.execute(
        "SELECT week, run_id FROM site_week_selections "
        "WHERE season = %s AND week = ANY(%s)",
        (season, weeks),
    )
    found = {int(week): str(run_id) for week, run_id in cur.fetchall()}
    return {week: found.get(week) for week in weeks}


def run(*, packet: dict, apply: bool) -> dict:
    if packet.get("schema_version") in {
        "v5_intended_update_batch_selection_v2",
        "v5_intended_update_batch_rollback_v2",
    }:
        return _run_v2(packet=packet, apply=apply)
    if packet.get("schema_version") != "v5_intended_update_batch_selection_v1":
        raise ValueError("unknown successor batch packet")
    season = int(packet["season"])
    before = _weeks(packet["expected_current_runs"])
    after = _weeks(packet["replacement_runs"])
    if (
        season != 2026
        or set(before) != set(after)
        or sorted(after) != list(range(max(after) + 1))
    ):
        raise ValueError(
            "successor packet does not cover complete Weeks 0 through active"
        )
    if set(before.values()) & set(after.values()):
        raise ValueError("replacement packet reuses an original run")
    environment = packet["environment"]
    if environment not in {"preview", "production"}:
        raise ValueError("invalid batch environment")
    if os.getenv("CFB_ARTIFACT_ENV") != environment:
        raise ValueError("batch packet environment differs from active artifact context")
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        raise ValueError("v2 batch selection requires immutable R2 storage")
    if (
        apply
        and environment == "production"
        and not str(packet.get("decision_ref") or "").strip()
    ):
        raise ValueError("production batch requires a separate exact release decision")
    key = "PREVIEW_DATABASE_URL" if environment == "preview" else "DATABASE_URL"
    url = os.getenv(key)
    if not url:
        raise ValueError(f"{key} is required")
    options = None if apply else "-c default_transaction_read_only=on"
    with psycopg.connect(url, options=options) as conn:
        with conn.cursor() as cur:
            if apply:
                assert_v5_database_environment(cur, environment)
                assert_active_pipeline_lease(cur)
            observed = _selected(cur, season, sorted(before))
            if observed != before:
                raise ValueError(
                    "current public selection differs from packet rollback set"
                )
            if not apply:
                return {
                    "state": "preflight",
                    "environment": environment,
                    "season": season,
                    "current": observed,
                    "candidate": after,
                }
            changed = select_week_runs_batch(
                cur,
                season=season,
                runs_by_week=after,
                reason=f"V5 intended-update batch: {packet['decision_ref']}",
                environment=environment,
            )
            if changed != before or _selected(cur, season, sorted(after)) != after:
                raise ValueError("atomic selection readback differs")
        conn.commit()
    return {
        "state": "selected",
        "environment": environment,
        "season": season,
        "prior_runs": changed,
        "selected_runs": after,
    }


def _run_v2(*, packet: dict, apply: bool) -> dict:
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.ops.v5_batch_selection_v2 import (
        apply_v2_packet,
        preflight_v2_packet,
    )

    environment = packet.get("environment")
    if environment not in {"preview", "production"}:
        raise ValueError("invalid batch environment")
    key = "PREVIEW_DATABASE_URL" if environment == "preview" else "DATABASE_URL"
    url = os.getenv(key)
    if not url:
        raise ValueError(f"{key} is required")
    storage = get_storage(environment=environment)
    options = None if apply else "-c default_transaction_read_only=on"
    with psycopg.connect(url, options=options) as conn:
        with conn.cursor() as cur:
            result = (
                apply_v2_packet(
                    cur, packet, environment=environment, storage=storage
                )
                if apply
                else preflight_v2_packet(
                    cur, packet, environment=environment, storage=storage
                )
            )
        if apply:
            conn.commit()
    return result


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run(packet=json.loads(args.packet.read_bytes()), apply=args.apply),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
