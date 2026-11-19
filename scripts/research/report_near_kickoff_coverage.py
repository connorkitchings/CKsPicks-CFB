"""Report matchup coverage for one registered near-kickoff capture.

Uses the hash-pinned FBS-vs-FBS schedule from the supplied revision. Reads only
Preview storage and catalog. Emits JSON suitable for a research receipt.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import source_capture_by_id
from cks_picks_cfb.data.lake import read_source_capture
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.data.the_odds_api import NEAR_KICKOFF_ENTITY
from cks_picks_cfb.season.inputs import frame

EASTERN = ZoneInfo("America/New_York")


def slot_coverage(
    schedule: pd.DataFrame, quotes: pd.DataFrame, captured_at: datetime
) -> dict:
    captured = pd.Timestamp(captured_at).tz_convert("UTC")
    kickoff = pd.to_datetime(schedule["kickoff_utc"], utc=True, errors="raise")
    on_day = (
        kickoff.dt.tz_convert(EASTERN).dt.date == captured.tz_convert(EASTERN).date()
    )
    eligible = schedule.loc[on_day & (kickoff > captured)].assign(kickoff_utc=kickoff)
    eligible = eligible.set_index("game_id", verify_integrity=True).sort_index()
    has_line = quotes.reindex(columns=["game_id", "spread", "total"]).set_index(
        "game_id"
    )
    coverage = (
        has_line.notna()
        .groupby(level=0)
        .any()
        .reindex(eligible.index, fill_value=False)
    )
    games = [
        {
            "game_id": int(game_id),
            "away_team": game.away_team,
            "home_team": game.home_team,
            "kickoff_utc": game.kickoff_utc.isoformat(),
            "minutes_to_kickoff": round(
                (game.kickoff_utc - captured).total_seconds() / 60, 2
            ),
            "spread": bool(coverage.at[game_id, "spread"]),
            "total": bool(coverage.at[game_id, "total"]),
        }
        for game_id, game in eligible.iterrows()
    ]
    return {
        "eligible_games": len(games),
        "spread_games": sum(game["spread"] for game in games),
        "total_games": sum(game["total"] for game in games),
        "both_targets_games": sum(game["spread"] and game["total"] for game in games),
        "unmatched_game_ids": [
            int(game_id) for game_id in eligible.index.difference(quotes["game_id"])
        ],
        "games": games,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--week", required=True, type=int)
    parser.add_argument("--revision", required=True, type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    load_dotenv(args.env_file)
    if os.getenv("CFB_STORAGE_BACKEND") != "r2":
        parser.error("requires CFB_STORAGE_BACKEND=r2")
    required = (
        "PREVIEW_DATABASE_URL",
        "CFB_R2_PREVIEW_BUCKET",
        "CFB_R2_PREVIEW_ACCOUNT_ID",
        "CFB_R2_PREVIEW_ACCESS_KEY",
        "CFB_R2_PREVIEW_SECRET_KEY",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        parser.error(f"missing Preview configuration: {', '.join(missing)}")
    revision = json.loads(args.revision.read_bytes())
    schedule_ref = revision["inputs"]["schedule"]
    storage = get_storage(environment="preview")
    capture = source_capture_by_id(os.environ["PREVIEW_DATABASE_URL"], args.capture_id)
    if capture.entity != NEAR_KICKOFF_ENTITY:
        parser.error("capture is outside the analysis-only near-kickoff entity")
    schedule = frame(storage, schedule_ref)
    schedule = schedule.loc[
        (schedule["season"] == revision["season"]) & (schedule["week"] == args.week)
    ]
    if schedule.empty:
        parser.error("revision does not cover requested week")
    quotes = read_source_capture(storage, capture)
    if not schedule["game_id"].isin(quotes["game_id"]).any():
        parser.error("capture has no game IDs from requested revision and week")
    report = slot_coverage(schedule, quotes, capture.captured_at)
    report.update(
        capture_id=capture.capture_id,
        uri=capture.uri,
        sha256=capture.object_sha,
        captured_at=capture.captured_at.isoformat(),
        quote_rows=capture.row_count,
        scheduled_week_games=len(schedule),
        board_matches=quotes["game_id"].nunique(),
        provider_unmatched_quote_rows=capture.response_metadata.get("unmatched_events"),
        schedule_sha256=schedule_ref["sha256"],
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
