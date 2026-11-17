#!/usr/bin/env python3
"""Capture live The Odds API NCAAF quotes for one week into immutable Bronze.

Estimate-first: without ``--confirm`` the script prints the credit estimate
and exits without contacting the provider. With ``--confirm`` it issues
exactly one live board request (~2 credits with regions=us x spreads+totals),
matches events strictly against the week's Silver games schedule (ambiguous
matches raise; unmatched events are logged and skipped, never guessed), and
writes an immutable Bronze capture registered to the current ingestion run
(``CFB_INGESTION_RUN_ID`` or a generated ID).

``--near-kickoff`` registers the same board under the separate analysis-only entity
``market_quotes_near_kickoff`` (see docs/ops/weekly_runbook.md).

Requires THE_ODDS_API_KEY, DATABASE_URL, and storage credentials.

Usage:
    PYTHONPATH=.:src uv run python scripts/data/fetch_odds_api_market_quotes.py \\
        --year 2026 --week 2
    PYTHONPATH=.:src uv run python scripts/data/fetch_odds_api_market_quotes.py \\
        --year 2026 --week 2 --confirm
    PYTHONPATH=.:src uv run python scripts/data/fetch_odds_api_market_quotes.py \\
        --year 2026 --week 12 --near-kickoff --confirm
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from cks_picks_cfb.data.catalog import (  # noqa: E402
    begin_ingestion_run,
    dataset_ref_for_partition_as_of,
    finish_ingestion_run,
    register_source_capture,
)
from cks_picks_cfb.data.lake import capture_provider_records, read_dataset  # noqa: E402
from cks_picks_cfb.data.storage import get_storage  # noqa: E402
from cks_picks_cfb.data.the_odds_api import (  # noqa: E402
    LIVE_CREDITS_PER_REQUEST,
    MARKET_QUOTES_ENTITY,
    NEAR_KICKOFF_ENTITY,
    TheOddsAPIAdapter,
    match_odds_events_to_schedule,
)
from scripts.ops.near_kickoff_slot import expected_slot_game_ids  # noqa: E402

PROVIDER = "the_odds_api"
#: Near-kickoff only: minimum share of the slot day's not-yet-started games that
#: must have quotes, else the run fails (a thin board is a failed capture).
MIN_MATCH_RATIO = 0.80
UNMATCHED_SAMPLE_SIZE = 5


def unmatched_summary(unmatched: list[str], *, near_kickoff: bool) -> str:
    """Warning text; near-kickoff boards carry hundreds of off-week events."""
    if not near_kickoff:
        return (
            f"WARNING: {len(unmatched)} board events did not match the week "
            f"schedule and were skipped: {sorted(set(unmatched))}"
        )
    names = sorted(set(unmatched))
    return (
        f"WARNING: {len(unmatched)} board events did not match the week schedule "
        f"and were skipped (sample of {min(len(names), UNMATCHED_SAMPLE_SIZE)}: "
        f"{names[:UNMATCHED_SAMPLE_SIZE]})"
    )


def match_ratio_failure(
    expected: set[str], matched: set[str], min_ratio: float
) -> str | None:
    """Failure message when too few expected games have quotes, else ``None``."""
    if not expected:
        return None
    found = len(expected & matched)
    ratio = found / len(expected)
    if ratio >= min_ratio:
        return None
    return (
        f"Matched-games check failed: {found} of {len(expected)} games kicking "
        f"off later today (Eastern) have quotes (ratio {ratio:.2f} < "
        f"{min_ratio:.2f}); the capture is registered but its run is failed so "
        "the backup slot retries"
    )


def _week_schedule(conn_url: str, year: int, week: int) -> pd.DataFrame:
    as_of = datetime.now(timezone.utc).isoformat()
    ref = dataset_ref_for_partition_as_of(
        conn_url, "games", as_of, partitions={"seasons": [year]}
    )
    frame = read_dataset(get_storage(), ref)
    frame = frame[
        (frame["season"].astype(int) == year) & (frame["week"].astype(int) == week)
    ]
    if "start_date" not in frame and "kickoff_utc" in frame:
        frame = frame.rename(columns={"kickoff_utc": "start_date"})
    required = {"game_id", "home_team", "away_team", "start_date"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SystemExit(f"Silver games schedule missing columns: {missing}")
    return frame[list(required)].drop_duplicates("game_id")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Authorize the paid live request (one request, ~2 credits).",
    )
    parser.add_argument(
        "--near-kickoff",
        action="store_true",
        help=(
            "Register the capture as analysis-only near-kickoff evidence "
            f"(entity {NEAR_KICKOFF_ENTITY}); the revision builders never select it. "
            f"Default: the weekly {MARKET_QUOTES_ENTITY} capture."
        ),
    )
    parser.add_argument(
        "--min-match-ratio",
        type=float,
        default=MIN_MATCH_RATIO,
        help=(
            "Near-kickoff only: fail when fewer than this share of today's "
            f"not-yet-started games have quotes (default {MIN_MATCH_RATIO}); "
            "0 disables, for manual early captures."
        ),
    )
    parser.add_argument(
        "--regions",
        type=str,
        default="us",
        help="Provider region scope (default: us).",
    )
    args = parser.parse_args()
    entity = NEAR_KICKOFF_ENTITY if args.near_kickoff else MARKET_QUOTES_ENTITY

    conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is not set")

    schedule = _week_schedule(conn_url, args.year, args.week)
    if schedule.empty:
        raise SystemExit(
            f"Silver games schedule has no rows for {args.year} week {args.week}"
        )

    estimate = {
        "live_requests": 1,
        "estimated_credits": LIVE_CREDITS_PER_REQUEST,
        "games_in_week": int(len(schedule)),
    }
    print(estimate)
    if not args.confirm:
        print("Estimate only: no provider request was made (pass --confirm to spend)")
        return

    adapter = TheOddsAPIAdapter()
    response = adapter.fetch_live(entity, {"regions": args.regions})

    events_by_id: dict[str, dict] = {}
    for record in response.records:
        event_id = str(record.get("source_event_id") or "")
        if not event_id or event_id in events_by_id:
            continue
        events_by_id[event_id] = {
            "id": event_id,
            "home_team": record.get("home_team"),
            "away_team": record.get("away_team"),
            "commence_time": record.get("kickoff_utc"),
        }
    matches = match_odds_events_to_schedule(
        list(events_by_id.values()), schedule, allow_prefix=True
    )

    matched_records = []
    unmatched = []
    for record in response.records:
        event_id = str(record.get("source_event_id") or "")
        game_id = matches.get(event_id)
        if game_id is None:
            unmatched.append(f"{record.get('away_team')} @ {record.get('home_team')}")
            continue
        row = dict(record)
        row["game_id"] = game_id
        matched_records.append(row)
    if unmatched:
        print(unmatched_summary(unmatched, near_kickoff=args.near_kickoff))
    if not matched_records:
        raise SystemExit(
            "The live board matched no scheduled games for "
            f"{args.year} week {args.week}"
        )

    failure = None
    if args.near_kickoff:
        failure = match_ratio_failure(
            expected_slot_game_ids(datetime.now(timezone.utc), schedule),
            {str(game_id) for game_id in matches.values()},
            args.min_match_ratio,
        )

    storage = get_storage()
    ingestion_run_id = os.getenv("CFB_INGESTION_RUN_ID") or f"{uuid4().hex}"
    begin_ingestion_run(
        conn_url,
        ingestion_run_id=ingestion_run_id,
        provider=PROVIDER,
        entity=entity,
        request={"requests": [dict(response.request)]},
    )
    try:
        capture = capture_provider_records(
            storage,
            provider=PROVIDER,
            entity=entity,
            records=matched_records,
            captured_at=response.captured_at,
            effective_at=response.effective_at,
            request=response.request,
            provider_api_version=response.provider_api_version,
            response_metadata={
                **dict(response.response_metadata),
                "matched_events": len(matches),
                "unmatched_events": len(unmatched),
            },
        )
        register_source_capture(conn_url, capture, ingestion_run_id=ingestion_run_id)
        # A failed ratio check still registers the (immutable, analysis-only)
        # capture, but marks the run failed so the slot is not counted done.
        finish_ingestion_run(
            conn_url,
            ingestion_run_id,
            succeeded=failure is None,
            error_category="MatchRatioBelowThreshold" if failure else None,
            error_detail=failure,
        )
    except Exception as exc:
        finish_ingestion_run(
            conn_url,
            ingestion_run_id,
            succeeded=False,
            error_category=type(exc).__name__,
            error_detail=str(exc),
        )
        raise

    print(
        f"Captured {len(matched_records)} the_odds_api quotes "
        f"({len(matches)} events) as {capture.capture_id}"
    )
    if failure:
        raise SystemExit(failure)


if __name__ == "__main__":
    main()
