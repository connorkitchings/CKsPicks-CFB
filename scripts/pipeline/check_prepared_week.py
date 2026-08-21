#!/usr/bin/env python3
"""Fail closed unless a prepared Gold ref covers the target week point-in-time."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode("utf-8")))


def _manifest(storage, ref: DatasetRef) -> dict[str, object]:
    manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    return json.loads(storage.read_bytes(manifest_uri).decode("utf-8"))


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--games-ref-uri", required=True)
    parser.add_argument("--outcomes-ref-uri", required=True)
    parser.add_argument("--gold-ref-uri", required=True)
    parser.add_argument(
        "--environment", choices=("preview", "production"), required=True
    )
    args = parser.parse_args()
    storage = get_storage(environment=args.environment)
    games_ref = _ref(storage, args.games_ref_uri)
    outcomes_ref = _ref(storage, args.outcomes_ref_uri)
    gold_ref = _ref(storage, args.gold_ref_uri)
    if gold_ref.dataset != "point_in_time_matchups":
        raise SystemExit(f"Prepared Gold has wrong dataset: {gold_ref.dataset}")
    gold_manifest = _manifest(storage, gold_ref)
    if _utc(str(gold_manifest["as_of"])) < _utc(args.as_of):
        raise SystemExit("Prepared Gold is stale relative to the requested cutoff")
    games = read_dataset(storage, games_ref)
    outcomes = read_dataset(storage, outcomes_ref)
    gold = read_dataset(storage, gold_ref)
    current_games = games[games["season"].astype(int) == args.year].copy()
    target_ids = set(
        current_games.loc[current_games["week"].astype(int) == args.week, "game_id"]
        .astype(int)
        .tolist()
    )
    if not target_ids:
        raise SystemExit("Prepared schedule has no target-week games")
    gold_ids = set(
        gold.loc[
            (gold["season"].astype(int) == args.year)
            & (gold["week"].astype(int) == args.week),
            "game_id",
        ]
        .astype(int)
        .tolist()
    )
    if target_ids != gold_ids:
        raise SystemExit(
            f"Target-week Gold coverage mismatch: schedule={len(target_ids)} gold={len(gold_ids)}"
        )
    score_columns = {"home_points", "away_points"}
    if not score_columns.issubset(current_games.columns):
        raise SystemExit("Prepared schedule does not expose completed-game scores")
    completed_games = current_games.dropna(subset=sorted(score_columns))
    final_outcomes = outcomes[
        (outcomes["season"].astype(int) == args.year)
        & outcomes["completed"].fillna(False)
    ]
    if set(completed_games["game_id"].astype(int)) != set(
        final_outcomes["game_id"].astype(int)
    ):
        raise SystemExit("Completed schedule games disagree with immutable outcomes")
    target = gold[
        (gold["season"].astype(int) == args.year)
        & (gold["week"].astype(int) == args.week)
    ]
    feature_columns = [
        column
        for column in gold.columns
        if column.startswith(("home_off_", "home_def_", "away_off_", "away_def_"))
    ]
    if not feature_columns:
        raise SystemExit("Prepared Gold contains no current-season team features")
    for side in ("home", "away"):
        experienced = target[f"{side}_completed_games"].astype(int) > 0
        if (
            experienced.any()
            and target.loc[experienced, feature_columns].isna().all(axis=1).any()
        ):
            raise SystemExit(f"Prepared Gold is missing {side} current-season features")
    if not pd.api.types.is_numeric_dtype(target["home_completed_games"]):
        raise SystemExit("Prepared Gold routing columns are invalid")
    print(
        json.dumps(
            {
                "state": "ready",
                "year": args.year,
                "week": args.week,
                "target_game_count": len(target_ids),
                "completed_game_count": len(completed_games),
                "gold_version_id": gold_ref.version_id,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
