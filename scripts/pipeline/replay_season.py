#!/usr/bin/env python3
"""Replay immutable weekly runs into an isolated preview database."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from cks_picks_cfb.data.storage import get_storage


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--environment", choices=("preview",), required=True)
    parser.add_argument("--config", default="conf/weekly_bets/v2_champion.yaml")
    args = parser.parse_args()

    preview_url = os.getenv("PREVIEW_DATABASE_URL")
    if not preview_url:
        raise SystemExit("PREVIEW_DATABASE_URL must identify an isolated Neon branch")
    if preview_url == os.getenv("DATABASE_URL"):
        raise SystemExit("PREVIEW_DATABASE_URL must not equal DATABASE_URL")

    games = get_storage().read_index("raw/games", {"year": args.year})
    weeks = sorted({int(row["week"]) for row in games if row.get("week") is not None})
    if not weeks:
        raise SystemExit(f"No schedule weeks found for {args.year}")

    env = {
        **os.environ,
        "DATABASE_URL": preview_url,
        "CFB_ARTIFACT_ENV": "preview",
    }
    for week in weeks:
        print(f"Replaying {args.year} week {week}", flush=True)
        week_starts = [
            datetime.fromisoformat(str(row["start_date"]).replace("Z", "+00:00"))
            for row in games
            if int(row.get("week", -1)) == week and row.get("start_date")
        ]
        if not week_starts:
            raise RuntimeError(f"No kickoff timestamps for {args.year} week {week}")
        as_of = (
            min(week_starts).astimezone(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
        pipeline_run_id = f"replay-{args.year}-w{week}"
        run_id = f"replay-{args.year}-w{week}-v1"
        refs_uri = f"artifacts/preview/pipeline-runs/{pipeline_run_id}/input_refs.json"
        subprocess.run(
            [
                sys.executable,
                "scripts/pipeline/snapshot_week_inputs.py",
                "--year",
                str(args.year),
                "--week",
                str(week),
                "--as-of",
                as_of,
                "--pipeline-run-id",
                pipeline_run_id,
            ],
            check=True,
            env=env,
        )
        subprocess.run(
            [
                sys.executable,
                "scripts/pipeline/generate_weekly_bets.py",
                "--config",
                args.config,
                "--year",
                str(args.year),
                "--week",
                str(week),
                "--as-of",
                as_of,
                "--run-id",
                run_id,
                "--run-state",
                "published",
                "--dataset-refs-uri",
                refs_uri,
                "--upload-artifact",
            ],
            check=True,
            env=env,
        )
        subprocess.run(
            [
                sys.executable,
                "scripts/pipeline/publish_to_db.py",
                "--year",
                str(args.year),
                "--week",
                str(week),
                "--run-id",
                run_id,
                "--state",
                "published",
                "--from-artifact",
            ],
            check=True,
            env=env,
        )
        subprocess.run(
            [
                sys.executable,
                "scripts/pipeline/freeze_week.py",
                "--year",
                str(args.year),
                "--week",
                str(week),
                "--waiver",
                "historical replay: preserve provider line availability",
            ],
            check=True,
            env=env,
        )
        subprocess.run(
            [
                sys.executable,
                "scripts/pipeline/score_weekly_bets.py",
                "--year",
                str(args.year),
                "--week",
                str(week),
                "--run-id",
                run_id,
                "--from-artifact",
                "--upload-artifact",
            ],
            check=True,
            env=env,
        )
        subprocess.run(
            [
                sys.executable,
                "scripts/pipeline/score_to_db.py",
                "--year",
                str(args.year),
                "--week",
                str(week),
                "--run-id",
                run_id,
                "--from-artifact",
            ],
            check=True,
            env=env,
        )
    print(f"Replayed {len(weeks)} weeks into the isolated preview database.")


if __name__ == "__main__":
    main()
