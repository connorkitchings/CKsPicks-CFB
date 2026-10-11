#!/usr/bin/env python3
"""Print the registered authorizations and bundle approvals of exact runs (read-only).

A rollback packet restores runs that were released earlier, so it must carry their
authorization rows and bundle approvals exactly as registered. This reads them and
prints the two spec fragments the packet builder takes::

    zsh scripts/ops/with_production_pipeline_env.sh env PYTHONPATH=src:. \\
        uv run python scripts/pipeline/export_v5_registered_releases.py \\
        --environment production --run 0=<run id> --run 1=<run id> ...

The connection is read-only. Output: ``registered_authorizations`` (week -> row) and
``registered_bundles`` (rows).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.ops.v5_intended_update_release import AUTH_COLUMNS

BUNDLE_COLUMNS = (
    "approval_id",
    "model_id",
    "inference_bundle_sha256",
    "first_live_season",
    "first_live_week",
    "decision_ref",
)


class ExportError(RuntimeError):
    """A requested run has no single exact registered release."""


def export(cur, *, environment: str, runs: dict[int, str]) -> dict:
    authorizations: dict[str, dict] = {}
    for week, run_id in sorted(runs.items()):
        cur.execute(
            "SELECT "
            + ", ".join(AUTH_COLUMNS)
            + " FROM v5_intended_update_release_authorizations "
            "WHERE environment = %s AND season = 2026 AND week = %s "
            "AND prediction_run_id = %s",
            (environment, week, run_id),
        )
        rows = cur.fetchall()
        if len(rows) != 1:
            raise ExportError(
                f"Week {week} run {run_id}: expected one registered authorization, "
                f"found {len(rows)}"
            )
        authorizations[str(week)] = dict(zip(AUTH_COLUMNS, rows[0], strict=True))
    pairs = sorted(
        {
            (row["model_id"], row["inference_bundle_sha256"])
            for row in authorizations.values()
        }
    )
    bundles = []
    for model_id, sha in pairs:
        cur.execute(
            "SELECT " + ", ".join(BUNDLE_COLUMNS) + " FROM v5_model_bundle_approvals "
            "WHERE model_id = %s AND inference_bundle_sha256 = %s",
            (model_id, sha),
        )
        rows = cur.fetchall()
        if len(rows) != 1:
            raise ExportError(
                f"bundle {sha[:12]}: expected one registered approval, found {len(rows)}"
            )
        bundles.append(dict(zip(BUNDLE_COLUMNS, rows[0], strict=True)))
    return {"registered_authorizations": authorizations, "registered_bundles": bundles}


def _parse_runs(items: list[str]) -> dict[int, str]:
    runs: dict[int, str] = {}
    for item in items:
        week, _, run_id = item.partition("=")
        if not week.isdigit() or not run_id or int(week) in runs:
            raise SystemExit(f"--run must be WEEK=RUN_ID, once per week: {item!r}")
        runs[int(week)] = run_id
    return runs


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    parser.add_argument("--run", action="append", default=[], metavar="WEEK=RUN_ID")
    args = parser.parse_args()
    runs = _parse_runs(args.run)
    if not runs:
        raise SystemExit("at least one --run is required")
    key = "PREVIEW_DATABASE_URL" if args.environment == "preview" else "DATABASE_URL"
    url = os.getenv(key)
    if not url:
        raise SystemExit(f"{key} is required")
    with (
        psycopg.connect(url, options="-c default_transaction_read_only=on") as conn,
        conn.cursor() as cur,
    ):
        try:
            result = export(cur, environment=args.environment, runs=runs)
        except ExportError as exc:
            raise SystemExit(str(exc)) from exc
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
