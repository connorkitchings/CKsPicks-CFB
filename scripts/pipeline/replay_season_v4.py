#!/usr/bin/env python3
"""Replay a completed season week-by-week with a frozen selection-time bundle.

Executes the operational weekly loop (generate -> publish -> freeze -> score ->
score_to_db) against an isolated Preview database using explicit immutable
input refs: certified point-in-time Gold, the Silver schedule, provider market
snapshots canonicalized from Bronze betting lines, and Silver game outcomes.
Each week's cutoff precedes its first kickoff so the replay is point-in-time
correct, and every freeze records the historical-replay line-coverage waiver.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.catalog import catalog_connection_url, register_dataset_version
from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetRef,
    build_dataset_version,
    canonicalize_market_quotes_frame,
    read_dataset,
)
from cks_picks_cfb.data.silver.builders import normalize_market_quotes
from cks_picks_cfb.data.storage import get_storage

FREEZE_WAIVER = "historical replay: provider line availability"


def _code_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode()))


def _write_immutable_json(storage, uri: str, payload: bytes) -> None:
    if storage.exists(uri):
        if storage.read_bytes(uri) != payload:
            raise FileExistsError(f"Immutable replay ref changed: {uri}")
    else:
        storage.write_bytes(payload, uri)


def build_market_refs(
    storage,
    *,
    year: int,
    games: pd.DataFrame,
    snapshots_ref_uri: str,
    quotes_ref_uri: str,
    environment: str,
    as_of: datetime,
) -> tuple[DatasetRef, DatasetRef]:
    """Register immutable market_quotes and market_snapshots refs from Bronze."""
    if storage.exists(snapshots_ref_uri) and storage.exists(quotes_ref_uri):
        return (
            _ref(storage, snapshots_ref_uri),
            _ref(storage, quotes_ref_uri),
        )
    quotes = storage.read_index("raw/betting_lines", {"year": year})
    if not quotes:
        raise SystemExit(f"No Bronze betting_lines captures for {year}")
    backfilled_weeks: list[int] = []
    for row in quotes:
        if pd.notna(row.get("captured_at")):
            continue
        week = int(row.get("week"))
        manifest_uri = f"raw/betting_lines/year={year}/week={week}/manifest.json"
        write_time = json.loads(storage.read_bytes(manifest_uri).decode()).get(
            "write_time"
        )
        if write_time is None:
            raise SystemExit(f"Bronze manifest has no write_time: {manifest_uri}")
        stamp = pd.to_datetime(write_time, utc=True, errors="raise")
        # Match the strict inferred quote format (%Y-%m-%dT%H:%M:%S.%f%z).
        row["captured_at"] = stamp.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        if week not in backfilled_weeks:
            backfilled_weeks.append(week)
    if backfilled_weeks:
        print(
            "Backfilled missing quote captured_at from Bronze manifest "
            f"write_time for weeks: {sorted(backfilled_weeks)}"
        )
    valued = [
        row
        for row in quotes
        if row.get("spread") is not None
        or row.get("over_under") is not None
        or row.get("total") is not None
    ]
    dropped = len(quotes) - len(valued)
    if dropped:
        print(f"Dropping {dropped} quotes with neither a spread nor a total")
    normalized = normalize_market_quotes(valued)
    schedule_ids = set(games["game_id"].astype(int))
    quotes = normalized[normalized["game_id"].astype(int).isin(schedule_ids)].merge(
        games[["game_id", "season", "week"]].drop_duplicates("game_id"),
        on="game_id",
        how="left",
    )
    snapshots = canonicalize_market_quotes_frame(quotes)
    unlined = sorted(schedule_ids - set(snapshots["game_id"].astype(int)))
    if unlined:
        raise SystemExit(f"Provider lines do not cover scheduled games: {unlined[:10]}")
    snapshots = snapshots.copy()
    snapshots["market_captured_at"] = pd.to_datetime(
        snapshots["market_captured_at"], utc=True, errors="raise", format="mixed"
    ).dt.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    config_identity = {
        "replay_market_source": f"raw/betting_lines/year={year}",
        "policy": "consensus_then_median_v1",
        "timing": "provider_recorded_lines_postseason_capture",
        "captured_at_backfilled_weeks": sorted(backfilled_weeks),
    }
    quotes_ref, quotes_manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="market_quotes",
            parent_refs=(),
            code_sha=_code_sha(),
            config_sha=hashlib.sha256(
                json.dumps(config_identity, sort_keys=True).encode()
            ).hexdigest(),
            as_of=as_of,
            schema_version="market_quotes_v1",
            tier="silver",
        ),
        records=quotes.to_dict("records"),
        partitions={"seasons": [year]},
        coverage={**config_identity, "quote_rows": int(len(quotes))},
    )
    register_dataset_version(
        catalog_connection_url(environment), quotes_ref, quotes_manifest
    )
    payload = json.dumps(asdict(quotes_ref), indent=2, sort_keys=True).encode()
    _write_immutable_json(storage, quotes_ref_uri, payload)
    ref, manifest = build_dataset_version(
        storage,
        build=BuildRequest(
            dataset="market_snapshots",
            parent_refs=(),
            code_sha=_code_sha(),
            config_sha=hashlib.sha256(
                json.dumps(config_identity, sort_keys=True).encode()
            ).hexdigest(),
            as_of=as_of,
            schema_version="market_snapshots_v1",
            tier="silver",
        ),
        records=snapshots.to_dict("records"),
        partitions={"seasons": [year]},
        coverage={
            **config_identity,
            "lined_games": int(len(snapshots)),
            "schedule_games": int(len(games)),
        },
    )
    register_dataset_version(catalog_connection_url(environment), ref, manifest)
    payload = json.dumps(asdict(ref), indent=2, sort_keys=True).encode()
    _write_immutable_json(storage, snapshots_ref_uri, payload)
    return ref, quotes_ref


def write_input_refs(
    storage,
    *,
    pipeline_run_id: str,
    year: int,
    games_ref: DatasetRef,
    market_ref: DatasetRef,
    quotes_ref: DatasetRef,
    gold_ref: DatasetRef,
    environment: str,
) -> str:
    entities = (
        ("games", games_ref),
        ("betting_lines", market_ref),
        ("betting_lines_quotes", quotes_ref),
        ("point_in_time_matchups", gold_ref),
    )
    refs = [{"entity": entity, "year": year, **asdict(ref)} for entity, ref in entities]
    uri = f"artifacts/{environment}/pipeline-runs/{pipeline_run_id}/input_refs.json"
    _write_immutable_json(
        storage, uri, json.dumps(refs, indent=2, sort_keys=True).encode()
    )
    return uri


def run_step(argv: list[str], env: dict[str, str]) -> None:
    print("+", " ".join(argv), flush=True)
    subprocess.run(argv, check=True, env=env)


def week_cutoff(games: pd.DataFrame, *, year: int, week: int) -> str:
    """Return the ISO cutoff one second before a week's first kickoff."""
    week_games = games[
        (games["season"].astype(int) == int(year))
        & (games["week"].astype(int) == int(week))
    ]
    if week_games.empty:
        raise SystemExit(f"No schedule rows for {year} week {week}")
    kickoff_column = (
        "start_date" if "start_date" in week_games.columns else "kickoff_utc"
    )
    kickoffs = [
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        for value in week_games[kickoff_column]
        if pd.notna(value)
    ]
    if not kickoffs:
        raise SystemExit(f"No kickoff timestamps for {year} week {week}")
    return (min(kickoffs).astimezone(timezone.utc) - timedelta(seconds=1)).isoformat()


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), default="preview"
    )
    parser.add_argument("--config", default="conf/weekly_bets/v4_2025_replay.yaml")
    parser.add_argument("--feature-ref-uri", required=True)
    parser.add_argument("--games-ref-uri", required=True)
    parser.add_argument("--outcomes-ref-uri", required=True)
    parser.add_argument("--market-snapshots-ref-uri", required=True)
    parser.add_argument("--market-quotes-ref-uri", required=True)
    parser.add_argument("--weeks", help="Comma-separated weeks (default: all)")
    parser.add_argument("--run-prefix", default=None)
    parser.add_argument("--skip-market-build", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="Required to run the replay against the production database.",
    )
    args = parser.parse_args()

    if args.environment == "production" and not args.confirm_production:
        raise SystemExit("Production replays require --confirm-production")
    if args.environment == "production":
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise SystemExit("DATABASE_URL is not set")
    else:
        db_url = os.getenv("PREVIEW_DATABASE_URL")
        if not db_url:
            raise SystemExit(
                "PREVIEW_DATABASE_URL must identify an isolated Neon branch"
            )
        if db_url == os.getenv("DATABASE_URL"):
            raise SystemExit("PREVIEW_DATABASE_URL must not equal DATABASE_URL")

    storage = get_storage(environment=args.environment)
    gold_ref = _ref(storage, args.feature_ref_uri)
    games_ref = _ref(storage, args.games_ref_uri)
    # Validate the outcomes ref up front so failures surface before any week runs.
    _ref(storage, args.outcomes_ref_uri)
    if gold_ref.dataset != "point_in_time_matchups_v5":
        raise SystemExit(
            f"Replay Gold must be point_in_time_matchups_v5; got {gold_ref.dataset}"
        )

    games = read_dataset(storage, games_ref)
    games = games[games["season"].astype(int) == args.year]
    if games.empty:
        raise SystemExit(f"Schedule ref has no {args.year} rows")
    weeks = (
        sorted(int(w) for w in args.weeks.split(",") if w.strip())
        if args.weeks
        else sorted(int(w) for w in games["week"].dropna().unique())
    )
    run_prefix = args.run_prefix or f"v4replay-{args.year}"

    # Deterministic build time for the market datasets: the last kickoff of
    # the replayed season, so rebuilds reproduce identical refs.
    market_as_of = max(
        datetime.fromisoformat(week_cutoff(games, year=args.year, week=week))
        for week in weeks
    )
    snapshots_uri = args.market_snapshots_ref_uri
    quotes_uri = args.market_quotes_ref_uri
    if args.skip_market_build and not (
        storage.exists(snapshots_uri) and storage.exists(quotes_uri)
    ):
        raise SystemExit("--skip-market-build requires existing market refs")
    market_ref, quotes_ref = (
        (_ref(storage, snapshots_uri), _ref(storage, quotes_uri))
        if args.skip_market_build
        else build_market_refs(
            storage,
            year=args.year,
            games=games,
            snapshots_ref_uri=snapshots_uri,
            quotes_ref_uri=quotes_uri,
            environment=args.environment,
            as_of=market_as_of,
        )
    )
    print(f"Market refs: {market_ref.version_id} / {quotes_ref.version_id}")

    env = {
        **os.environ,
        "DATABASE_URL": db_url,
        "CFB_ARTIFACT_ENV": args.environment,
    }
    for week in weeks:
        as_of = week_cutoff(games, year=args.year, week=week)
        pipeline_run_id = f"replay-{args.year}-v4-w{week}"
        run_id = f"{run_prefix}-w{week}"
        refs_uri = write_input_refs(
            storage,
            pipeline_run_id=pipeline_run_id,
            year=args.year,
            games_ref=games_ref,
            market_ref=market_ref,
            quotes_ref=quotes_ref,
            gold_ref=gold_ref,
            environment=args.environment,
        )
        print(
            f"Replaying {args.year} week {week}: run={run_id} as_of={as_of}",
            flush=True,
        )
        steps = [
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
            [
                sys.executable,
                "scripts/pipeline/publish_to_db.py",
                "--year",
                str(args.year),
                "--week",
                str(week),
                "--run-id",
                run_id,
                "--config",
                args.config,
                "--state",
                "published",
                "--from-artifact",
            ],
            [
                sys.executable,
                "scripts/pipeline/freeze_week.py",
                "--year",
                str(args.year),
                "--week",
                str(week),
                "--waiver",
                FREEZE_WAIVER,
            ],
            [
                sys.executable,
                "scripts/pipeline/score_weekly_bets.py",
                "--year",
                str(args.year),
                "--week",
                str(week),
                "--run-id",
                run_id,
                "--outcomes-ref-uri",
                args.outcomes_ref_uri,
                "--from-artifact",
                "--upload-artifact",
            ],
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
        ]
        if args.dry_run:
            for step in steps:
                print("dry-run +", " ".join(step))
            continue
        for step in steps:
            run_step(step, env)
    print(f"Replayed {len(weeks)} weeks into the {args.environment} database.")


if __name__ == "__main__":
    main()
