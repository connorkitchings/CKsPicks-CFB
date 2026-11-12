#!/usr/bin/env python3
"""Decide whether a near-kickoff Odds API capture should run now.

Used by ``.github/workflows/near-kickoff-capture.yml`` (analysis-only closing-line
evidence, contract docs/plans/2026-11-12/01-near-kickoff-line-capture.md). Reads
the stored Silver schedule and the catalog (read-only, no provider call), prints
the decision and, when ``GITHUB_OUTPUT`` is set, writes ``action``, ``week``,
``slot_id`` and ``reason`` for later workflow steps.

A *slot* is one Eastern calendar day with a kickoff in Weeks 12 to 15. Each slot is
scheduled twice (primary and backup); the capture is idempotent per slot, so the
backup skips when the primary succeeded and runs when the primary failed or never
fired. Sunday and Monday belong to the weekly season update and never get a slot.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd  # noqa: E402

SEASON = 2026
FIRST_WEEK = 12
LAST_WEEK = 15
#: Midweek (Tuesday to Friday) slots captured per week; keeps the budget at
#: 4 weeks x (1 Saturday + 2 midweek) x 2 credits = 24 credits.
MAX_MIDWEEK_SLOTS_PER_WEEK = 2
EASTERN = ZoneInfo("America/New_York")
SATURDAY = 5
WEEKLY_RUN_WEEKDAYS = (6, 0)  # Sunday and Monday (weekly-season-update.yml)
RUN_ID_PREFIX = "near-kickoff-"
_SLOT_IN_RUN_ID = re.compile(rf"^{RUN_ID_PREFIX}(\d{{4}}-w\d{{2}}-\d{{8}})-")


@dataclass(frozen=True)
class SlotDecision:
    action: str  # "capture" or "skip"
    reason: str
    slot_id: str | None = None
    week: int | None = None


def slot_id_for(season: int, week: int, day) -> str:
    return f"{season}-w{week:02d}-{day:%Y%m%d}"


def expected_slot_game_ids(now: datetime, schedule: pd.DataFrame) -> set[str]:
    """Games of ``schedule`` kicking off later in the Eastern day of ``now``.

    ``schedule`` needs ``game_id`` and ``start_date``. These are the games a slot's
    capture is expected to quote; the capture's matched-games check counts them.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    kickoffs = pd.to_datetime(schedule["start_date"], utc=True, errors="raise")
    today = pd.Timestamp(now).tz_convert(EASTERN).date()
    upcoming = (kickoffs.dt.tz_convert(EASTERN).dt.date == today) & (
        kickoffs > pd.Timestamp(now)
    )
    return {str(game_id) for game_id in schedule.loc[upcoming, "game_id"]}


def completed_slot_ids(ingestion_run_ids: Collection[str]) -> set[str]:
    """Slots whose capture succeeded, from succeeded near-kickoff run ids."""
    return {
        match.group(1)
        for run_id in ingestion_run_ids
        if (match := _SLOT_IN_RUN_ID.match(run_id))
    }


def decide_slot(
    now: datetime,
    schedule: pd.DataFrame,
    completed: Collection[str],
    *,
    season: int = SEASON,
) -> SlotDecision:
    """Capture or skip, for the slot of ``now``'s Eastern day.

    ``schedule`` needs ``week`` and ``start_date`` (kickoff, UTC-parsable).
    ``completed`` holds slot ids whose capture already succeeded.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = pd.Timestamp(now).tz_convert(EASTERN)
    if local.weekday() in WEEKLY_RUN_WEEKDAYS:
        return SlotDecision("skip", "Sunday and Monday belong to the weekly update")
    kickoffs = pd.to_datetime(schedule["start_date"], utc=True, errors="raise")
    on_day = schedule.assign(_kickoff=kickoffs)[
        kickoffs.dt.tz_convert(EASTERN).dt.date == local.date()
    ]
    if on_day.empty:
        return SlotDecision("skip", "no kickoff on this Eastern day")
    in_weeks = on_day[on_day["week"].astype(int).between(FIRST_WEEK, LAST_WEEK)]
    if in_weeks.empty:
        return SlotDecision("skip", f"outside weeks {FIRST_WEEK} to {LAST_WEEK}")
    earliest = in_weeks.sort_values("_kickoff").iloc[0]
    week = int(earliest["week"])
    if pd.Timestamp(now) >= earliest["_kickoff"]:
        return SlotDecision(
            "skip", "earliest kickoff has passed; not near-kickoff", week=week
        )
    slot_id = slot_id_for(season, week, local.date())
    if slot_id in completed:
        return SlotDecision("skip", "slot already captured", slot_id, week)
    if local.weekday() != SATURDAY:
        prefix = f"{season}-w{week:02d}-"
        midweek_done = [
            done
            for done in completed
            if done.startswith(prefix)
            and datetime.strptime(done.rsplit("-", 1)[1], "%Y%m%d").weekday()
            != SATURDAY
        ]
        if len(midweek_done) >= MAX_MIDWEEK_SLOTS_PER_WEEK:
            return SlotDecision("skip", "midweek slot cap reached", slot_id, week)
    return SlotDecision("capture", "kickoff ahead in slot window", slot_id, week)


def _load_schedule_and_completed(conn_url: str, season: int):
    import psycopg

    from cks_picks_cfb.data.catalog import dataset_ref_for_partition_as_of
    from cks_picks_cfb.data.lake import read_dataset
    from cks_picks_cfb.data.storage import get_storage
    from cks_picks_cfb.data.the_odds_api import NEAR_KICKOFF_ENTITY

    as_of = datetime.now(timezone.utc).isoformat()
    ref = dataset_ref_for_partition_as_of(
        conn_url, "games", as_of, partitions={"seasons": [season]}
    )
    frame = read_dataset(get_storage(), ref)
    frame = frame[frame["season"].astype(int) == season]
    if "start_date" not in frame and "kickoff_utc" in frame:
        frame = frame.rename(columns={"kickoff_utc": "start_date"})
    with psycopg.connect(conn_url) as conn:
        rows = conn.execute(
            "SELECT ingestion_run_id FROM catalog.ingestion_runs "
            "WHERE entity = %s AND state = 'succeeded' "
            "AND ingestion_run_id LIKE %s",
            (NEAR_KICKOFF_ENTITY, f"{RUN_ID_PREFIX}%"),
        ).fetchall()
    return (
        frame[["week", "start_date"]].dropna(),
        completed_slot_ids({str(row[0]) for row in rows}),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=SEASON)
    args = parser.parse_args()
    conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        raise SystemExit("DATABASE_URL is not set")
    schedule, completed = _load_schedule_and_completed(conn_url, args.season)
    decision = decide_slot(
        datetime.now(timezone.utc), schedule, completed, season=args.season
    )
    print(decision)
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"action={decision.action}\n")
            handle.write(f"reason={decision.reason}\n")
            handle.write(f"week={decision.week or ''}\n")
            handle.write(f"slot_id={decision.slot_id or ''}\n")


if __name__ == "__main__":
    main()
