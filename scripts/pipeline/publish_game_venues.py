#!/usr/bin/env python3
"""Publish venue, city and state per game to Neon ``game_venues``.

Reads the validated Silver ``games`` (venue_id, neutral_site) and ``venues``
(name, city, state, country_code, timezone) datasets for a season, joins them,
and upserts one row per game that already exists in Neon ``games``. Venue facts
do not depend on prediction runs, so this never touches runs or predictions.

Run once per season and again after a schedule change. Always do a dry run first:

    PYTHONPATH=src:. uv run python scripts/pipeline/publish_game_venues.py \\
        --season 2026 --environment preview --dry-run

The dry run prints the Silver column names, a coverage report and sample rows,
and writes nothing. Production writes go through the restricted pipeline login:
``scripts/ops/with_production_pipeline_env.sh`` sets DATABASE_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.game_venues import (
    GAME_ID,
    GAME_VENUE_ID,
    UPSERT_GAME_VENUE_SQL,
    VENUE_ID,
    MissingVenueColumnsError,
    apply_venue_supplement,
    build_game_venue_rows,
    require_venue_cities,
)
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.quality import run_stage
from cks_picks_cfb.quality.publish import finalize as finalize_quality
from cks_picks_cfb.quality.publish import raise_if_blocked

URL_ENV = {"preview": "PREVIEW_DATABASE_URL", "production": "DATABASE_URL"}


def _latest_silver_ref(
    cur: psycopg.Cursor,
    dataset: str,
    season: int | None,
    version_id: str | None = None,
) -> DatasetRef:
    """Return the pinned ``version_id`` or, without a pin, the newest validated one.

    The newest validated ``venues`` version is not a reliable choice: Silver holds one
    version per capture year, so the last one created can lack current stadiums.
    Pass ``version_id`` to pin an exact, reviewed version.
    """
    query = (
        "SELECT dataset, version_id, schema_version, content_sha, uri "
        "FROM catalog.dataset_versions "
        "WHERE dataset = %s AND tier = 'silver' AND state = 'validated' "
    )
    params: list[object] = [dataset]
    if version_id is not None:
        query += "AND version_id = %s "
        params.append(version_id)
    if season is not None:
        query += "AND partitions @> %s::jsonb "
        params.append(json.dumps({"seasons": [season]}))
    query += "ORDER BY as_of DESC, created_at DESC LIMIT 1"
    cur.execute(query, params)
    row = cur.fetchone()
    if not row:
        raise LookupError(f"No validated Silver {dataset} dataset found")
    return DatasetRef(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]))


def _require_unique_sources(games, venues, game_ids):
    """Reject ambiguous source joins before the legacy transform deduplicates."""
    game_key = next((key for key in GAME_ID if key in games.columns), None)
    game_venue = next((key for key in GAME_VENUE_ID if key in games.columns), None)
    venue_key = next((key for key in VENUE_ID if key in venues.columns), None)
    if game_key is None or game_venue is None or venue_key is None:
        return  # The transform reports missing required columns.
    selected = games[games[game_key].isin(game_ids)]
    if selected[game_key].duplicated().any():
        raise ValueError("duplicate Silver game IDs in publication slate")
    selected_venues = venues[venues[venue_key].isin(selected[game_venue])]
    if selected_venues[venue_key].duplicated().any():
        raise ValueError("duplicate Silver venue IDs in publication slate")


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--environment", choices=sorted(URL_ENV), required=True)
    parser.add_argument("--database-url", help="Override the environment's URL")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report coverage; write nothing"
    )
    parser.add_argument(
        "--games-version",
        help="Pin the exact validated Silver games version_id (recommended)",
    )
    parser.add_argument(
        "--venues-version",
        help="Pin the exact validated Silver venues version_id (recommended)",
    )
    parser.add_argument(
        "--require-city",
        action="store_true",
        help="Fail dry run/publication on incomplete city coverage",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Write only games that have no game_venues row yet; existing rows are never touched",
    )
    parser.add_argument(
        "--supplement",
        help="Reviewed JSON list of venue records that fills venue ids Silver lacks",
    )
    args = parser.parse_args()

    url = args.database_url or os.getenv(URL_ENV[args.environment])
    if not url:
        print(
            f"Set {URL_ENV[args.environment]} or pass --database-url", file=sys.stderr
        )
        return 2
    storage = get_storage(environment=args.environment)

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            games_ref = _latest_silver_ref(
                cur, "games", args.season, args.games_version
            )
            venues_ref = _latest_silver_ref(cur, "venues", None, args.venues_version)
            cur.execute("SELECT game_id FROM games WHERE season = %s", (args.season,))
            neon_ids = [int(r[0]) for r in cur.fetchall()]
            if args.only_missing:
                cur.execute("SELECT game_id FROM game_venues")
                have = {int(r[0]) for r in cur.fetchall()}
                neon_ids = [g for g in neon_ids if g not in have]
                print(f"--only-missing: {len(neon_ids)} games without a venue row")
        games = read_dataset(storage, games_ref)
        venues = read_dataset(storage, venues_ref)
        if args.supplement:
            venues, added = apply_venue_supplement(
                venues, json.loads(open(args.supplement).read())
            )
            print(f"supplement {args.supplement}: filled venue ids {added}")
        print(f"Silver games  {games_ref.version_id}: columns {sorted(games.columns)}")
        print(
            f"Silver venues {venues_ref.version_id}: columns {sorted(venues.columns)}"
        )
        try:
            _require_unique_sources(games, venues, neon_ids)
            rows, report = build_game_venue_rows(games, venues, neon_ids)
        except MissingVenueColumnsError as exc:
            print(f"Cannot build venue rows: {exc}", file=sys.stderr)
            return 3
        quality_ctx = {"venue_payload": rows, "venue_game_ids": neon_ids}
        pre_run = run_stage("publish", quality_ctx, prefix="publish.pre.venue_payload")
        identity = {
            "kind": "game_venues",
            "season": args.season,
            "environment": args.environment,
            "venues_version": venues_ref.version_id,
            "games_version": games_ref.version_id,
            "games_content_sha": games_ref.content_sha,
            "venues_content_sha": venues_ref.content_sha,
        }
        pre_receipt = finalize_quality(
            pre_run, identity={**identity, "phase": "pre-write"}
        )
        print(f"quality pre-write receipt: {pre_receipt['_path']}")
        if args.require_city or not args.dry_run:
            # A real write always requires a city for every game; a dry run only
            # does when asked, so coverage can still be reported.
            require_venue_cities(rows, neon_ids)
            raise_if_blocked(pre_run, "pre-write")
        report["source_versions"] = {
            "games": games_ref.version_id,
            "venues": venues_ref.version_id,
        }
        report["source_hashes"] = {
            "games": games_ref.content_sha,
            "venues": venues_ref.content_sha,
        }
        print(json.dumps(report, indent=2))
        for row in rows[:5]:
            print(json.dumps(row, default=str))
        if args.dry_run:
            print("Dry run: nothing written.")
            return 0
        with conn.cursor() as cur:
            cur.executemany(UPSERT_GAME_VENUE_SQL, rows)
            cur.execute(
                "SELECT game_id, city FROM game_venues WHERE game_id = ANY(%s)",
                (neon_ids,),
            )
            post_run = run_stage(
                "publish",
                {**quality_ctx, "venue_readback": cur.fetchall()},
                prefix="publish.post.venues",
            )
            post_receipt = finalize_quality(
                post_run, identity={**identity, "phase": "post-write"}
            )
            print(f"quality post-write receipt: {post_receipt['_path']}")
            raise_if_blocked(post_run, "post-write")
        conn.commit()
        print(f"Upserted {len(rows)} game_venues rows ({args.environment}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
