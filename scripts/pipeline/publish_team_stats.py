#!/usr/bin/env python3
"""Publish pre-game team season stats and national ranks to Neon.

Reads the validated Silver ``byplay``, ``drives``, ``games`` and
``game_outcomes`` datasets for a season, builds the FBS-vs-FBS stats for games
completed *before* ``--as-of-week`` (see ``cks_picks_cfb.data.team_stats``),
and upserts them into ``team_season_stats``. It never touches runs or
predictions. Always do a dry run first:

    PYTHONPATH=src:. uv run python scripts/pipeline/publish_team_stats.py \\
        --season 2026 --as-of-week 5 --environment preview --dry-run

Use ``--weeks 1-5`` to backfill several snapshots in one transaction (week 0
has no earlier games, so it never has a snapshot). Every row records the Silver
version ids that built it (``source_versions``); pin them with
``--byplay-version`` etc. to rebuild an old snapshot exactly. The dry run prints the Silver column names, coverage, null counts and sample
rows, and writes nothing. Production writes go through the restricted pipeline
login: ``scripts/ops/with_production_pipeline_env.sh`` sets DATABASE_URL.
Re-run for the new week whenever a week's finals are certified.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.data.team_stats import (
    UPSERT_TEAM_STAT_SQL,
    TeamStatsContractError,
    build_team_season_stats,
    to_upsert_records,
)

URL_ENV = {"preview": "PREVIEW_DATABASE_URL", "production": "DATABASE_URL"}


def parse_weeks(spec: str) -> list[int]:
    """``"5"``, ``"1-5"`` or ``"1,3,5"`` (ranges allowed in lists) -> sorted weeks."""
    weeks: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-", 1))
            if lo > hi:
                raise ValueError(f"Bad week range: {part}")
            weeks.update(range(lo, hi + 1))
        else:
            weeks.add(int(part))
    if not weeks:
        raise ValueError("No weeks given")
    return sorted(weeks)


def _silver_ref(
    cur: psycopg.Cursor, dataset: str, season: int, version_id: str | None
) -> DatasetRef:
    """Pinned version (must be validated Silver) or the latest for the season."""
    if version_id is None:
        return _latest_silver_ref(cur, dataset, season)
    cur.execute(
        "SELECT dataset, version_id, schema_version, content_sha, uri "
        "FROM catalog.dataset_versions "
        "WHERE dataset = %s AND version_id LIKE %s AND tier = 'silver' "
        "AND state = 'validated' LIMIT 2",
        (dataset, f"{version_id}%"),
    )
    rows = cur.fetchall()
    if len(rows) != 1:
        raise LookupError(
            f"Silver {dataset} version {version_id!r} matched {len(rows)} validated rows"
        )
    row = rows[0]
    return DatasetRef(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]))


def _latest_silver_ref(cur: psycopg.Cursor, dataset: str, season: int) -> DatasetRef:
    cur.execute(
        "SELECT dataset, version_id, schema_version, content_sha, uri "
        "FROM catalog.dataset_versions "
        "WHERE dataset = %s AND tier = 'silver' AND state = 'validated' "
        "AND partitions @> %s::jsonb "
        "ORDER BY as_of DESC, created_at DESC LIMIT 1",
        (dataset, json.dumps({"seasons": [season]})),
    )
    row = cur.fetchone()
    if not row:
        raise LookupError(f"No validated Silver {dataset} dataset found for {season}")
    return DatasetRef(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]))


def _fbs_teams(cur: psycopg.Cursor, season: int, teams_frame) -> tuple[set[str], str]:
    """FBS membership: Silver ``teams.classification`` if present, else Neon games."""
    if teams_frame is not None and {"team", "classification"} <= set(
        teams_frame.columns
    ):
        fbs = teams_frame[
            teams_frame["classification"].astype(str).str.lower() == "fbs"
        ]
        if not fbs.empty:
            return set(fbs["team"].astype(str)), "silver.teams.classification"
    cur.execute(
        "SELECT home_team FROM games WHERE season = %s "
        "UNION SELECT away_team FROM games WHERE season = %s",
        (season, season),
    )
    return {str(r[0]) for r in cur.fetchall()}, "neon.games (fallback)"


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument(
        "--as-of-week",
        type=int,
        help="Snapshot for week N = games completed before week N's slate",
    )
    parser.add_argument(
        "--weeks",
        help="Several snapshots at once, e.g. 1-5 or 2,4 (instead of --as-of-week)",
    )
    for name in ("byplay", "drives", "games", "game_outcomes", "teams"):
        parser.add_argument(
            f"--{name.replace('_', '-')}-version",
            help=f"Pin the Silver {name} version id (prefix ok); default: latest",
        )
    parser.add_argument("--environment", choices=sorted(URL_ENV), required=True)
    parser.add_argument("--database-url", help="Override the environment's URL")
    parser.add_argument("--dry-run", action="store_true", help="Report; write nothing")
    args = parser.parse_args()
    if (args.as_of_week is None) == (args.weeks is None):
        parser.error("give exactly one of --as-of-week or --weeks")
    try:
        weeks = [args.as_of_week] if args.weeks is None else parse_weeks(args.weeks)
    except ValueError as exc:
        parser.error(str(exc))

    url = args.database_url or os.getenv(URL_ENV[args.environment])
    if not url:
        print(
            f"Set {URL_ENV[args.environment]} or pass --database-url", file=sys.stderr
        )
        return 2
    storage = get_storage(environment=args.environment)

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            pins = {
                name: getattr(args, f"{name}_version")
                for name in ("byplay", "drives", "games", "game_outcomes", "teams")
            }
            refs = {
                name: _silver_ref(cur, name, args.season, pins[name])
                for name in ("byplay", "drives", "games", "game_outcomes")
            }
            try:
                teams_ref = _silver_ref(cur, "teams", args.season, pins["teams"])
                teams = read_dataset(storage, teams_ref)
            except LookupError:
                if pins["teams"]:
                    raise
                teams_ref = None
                teams = None
        source_versions = {name: ref.version_id for name, ref in refs.items()}
        if teams_ref is not None:
            source_versions["teams"] = teams_ref.version_id
        print(f"Source versions: {json.dumps(source_versions)}")
        frames = {name: read_dataset(storage, ref) for name, ref in refs.items()}
        for name, frame in frames.items():
            print(
                f"Silver {name} {refs[name].version_id}: columns {sorted(frame.columns)}"
            )
        with conn.cursor() as cur:
            fbs, fbs_source = _fbs_teams(cur, args.season, teams)
        print(f"FBS teams: {len(fbs)} (from {fbs_source})")
        all_records: list[dict] = []
        for week in weeks:
            try:
                result = build_team_season_stats(
                    byplay=frames["byplay"],
                    drives=frames["drives"],
                    games=frames["games"],
                    outcomes=frames["game_outcomes"],
                    fbs_teams=fbs,
                    season=args.season,
                    as_of_week=week,
                )
            except TeamStatsContractError as exc:
                print(
                    f"Cannot build team stats for week {week}: {exc}", file=sys.stderr
                )
                return 3
            print(f"== as_of_week {week} ==")
            print(json.dumps(result.report, indent=2, default=str))
            frame = result.frame
            if frame.empty:
                print("No rows: nothing qualifies before this week.")
                continue
            print("Null values by metric:")
            print(
                frame.groupby(["role", "metric"])["value"]
                .apply(lambda s: int(s.isna().sum()))
                .to_string()
            )
            print(frame.head(5).to_string())
            all_records.extend(to_upsert_records(frame, source_versions))
        if args.dry_run:
            print(
                f"Dry run: {len(all_records)} rows would be written; nothing written."
            )
            return 0
        if not all_records:
            print("Nothing to write.")
            return 0
        with conn.cursor() as cur:
            cur.executemany(UPSERT_TEAM_STAT_SQL, all_records)
        conn.commit()
        print(
            f"Upserted {len(all_records)} team_season_stats rows "
            f"for weeks {weeks} ({args.environment})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
