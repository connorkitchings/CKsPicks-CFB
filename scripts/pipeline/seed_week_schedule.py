#!/usr/bin/env python3
"""Seed a week's schedule rows into Neon ``games`` before its first publication.

The publish-boundary gate ``publish.pre.schedule_coverage`` takes the week's schedule from
Neon ``games``, and ``publish_to_db.py`` writes predictions into that same table. A week that
has never been published therefore has no schedule, and its first run is refused for "extra"
games. This seeds schedule-only rows (no predictions, lines or run) from a source lock, never
overwriting a row that exists, so an operator's partial-slate override means what it says:
the run may omit scheduled games and may not add games that are not scheduled.

    zsh scripts/ops/with_preview_env.sh zsh -c 'DATABASE_URL="$PREVIEW_DATABASE_URL" \\
        exec uv run python scripts/pipeline/seed_week_schedule.py \\
        --source-lock <lock> --week 6 --environment preview'          # dry run
    ... add --apply to write.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

SEED_SQL = """
INSERT INTO games (
    game_id, season, week, start_date, home_team, away_team, inserted_at, updated_at
) VALUES (
    %(game_id)s, %(season)s, %(week)s, %(start_date)s, %(home_team)s, %(away_team)s,
    NOW(), NOW()
)
ON CONFLICT (game_id) DO NOTHING
"""
URL_ENV = {"preview": "DATABASE_URL", "production": "DATABASE_URL"}


def schedule_rows(lock: dict[str, Any], week: int) -> list[dict[str, Any]]:
    """The lock's rows for ``week``: provider names, kickoff as given, no finals."""
    columns = lock["games"]["columns"]
    rows = []
    for raw in lock["games"]["rows"]:
        item = dict(zip(columns, raw, strict=True))
        if int(item["week"]) != week:
            continue
        rows.append(
            {
                "game_id": int(item["game_id"]),
                "season": 2026,
                "week": week,
                "start_date": item["start_date"],
                "home_team": item["home_team"],
                "away_team": item["away_team"],
            }
        )
    if not rows:
        raise ValueError(f"the lock has no games for week {week}")
    if len({row["game_id"] for row in rows}) != len(rows):
        raise ValueError("the lock duplicates a game")
    return rows


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-lock", type=Path, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--environment", choices=sorted(URL_ENV), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    import psycopg

    rows = schedule_rows(json.loads(args.source_lock.read_text()), args.week)
    url = os.getenv(URL_ENV[args.environment])
    if not url:
        raise SystemExit("DATABASE_URL is required (use the restricted pipeline login)")
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, session_user")
            identity = cur.fetchone()
            cur.execute(
                "SELECT game_id FROM games WHERE season = 2026 AND week = %s",
                (args.week,),
            )
            existing = {int(r[0]) for r in cur.fetchall()}
            new = [row for row in rows if row["game_id"] not in existing]
            print(
                json.dumps(
                    {
                        "environment": args.environment,
                        "role": list(identity),
                        "week": args.week,
                        "lock_games": len(rows),
                        "already_in_neon": len(existing),
                        "to_insert": len(new),
                        "apply": args.apply,
                    }
                )
            )
            if not args.apply:
                return 0
            cur.executemany(SEED_SQL, new)
            cur.execute(
                "SELECT COUNT(*) FROM games WHERE season = 2026 AND week = %s",
                (args.week,),
            )
            total = int(cur.fetchone()[0])
            if total != len(existing | {r["game_id"] for r in rows}):
                raise RuntimeError("seeded schedule does not read back")
        conn.commit()
    print(
        f"seeded {len(new)} schedule rows for week {args.week}; {total} now scheduled"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
