#!/usr/bin/env python3
"""Fail closed unless prepared Gold and projected ratings cover the target week."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import psycopg
from dotenv import load_dotenv

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.runtime import resolve_runtime_target
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.preseason_features import canonical_team

_RATING_AVAILABILITY = timedelta(hours=6)


def _ref(storage, uri: str) -> DatasetRef:
    return DatasetRef(**json.loads(storage.read_bytes(uri).decode("utf-8")))


def _manifest(storage, ref: DatasetRef) -> dict[str, object]:
    manifest_uri = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
    return json.loads(storage.read_bytes(manifest_uri).decode("utf-8"))


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (
        parsed.replace(tzinfo=timezone.utc)
        if parsed.tzinfo is None
        else parsed.astimezone(timezone.utc)
    )


def _rating_rows(
    conn_url: str, *, year: int, week: int, as_of: datetime
) -> list[tuple]:
    """Read projected generations without changing the serving database."""
    with psycopg.connect(
        conn_url, options="-c default_transaction_read_only=on"
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_run_id, source_manifest_sha256, team, "
                "snapshot_class, cutoff_utc, created_at "
                "FROM v5_rating_snapshots "
                "WHERE season = %s AND cutoff_utc <= %s "
                "AND ((snapshot_class = 'current' AND week < %s) "
                "OR (snapshot_class = 'pregame' AND week = 0 AND game_id IS NULL))",
                (year, as_of, week),
            )
            return cur.fetchall()


def _rating_currency(
    rows: list[tuple],
    *,
    target_teams: set[str],
    completed_games: pd.DataFrame,
    as_of: datetime,
) -> dict[str, str]:
    """Require one complete projected generation for the target slate."""
    target_teams = {name for team in target_teams if (name := canonical_team(team))}
    if not target_teams:
        raise ValueError("Ratings gate has no target-week teams")
    current = [row for row in rows if row[3] == "current"]
    preseason = [row for row in rows if row[3] == "pregame"]
    completed = completed_games.copy()
    if completed.empty:
        latest_game = None
        experienced: set[str] = set()
    else:
        if completed["kickoff_utc"].isna().any():
            raise ValueError("Completed games lack kickoff timestamps")
        kickoffs = pd.to_datetime(completed["kickoff_utc"], utc=True, errors="raise")
        eligible = completed.loc[kickoffs.lt(pd.Timestamp(as_of))]
        latest_game = (
            pd.to_datetime(eligible["kickoff_utc"], utc=True).max().to_pydatetime()
            if not eligible.empty
            else None
        )
        experienced = {
            name
            for team in pd.concat([eligible["home_team"], eligible["away_team"]])
            if (name := canonical_team(team))
        }

    if latest_game is not None:
        if not current:
            raise ValueError(
                "Ratings are missing: no current projected generation for the target cutoff. "
                "Refresh ratings and run project-v5-ratings before prepare-week."
            )
        cutoff = max(_utc(str(row[4])) for row in current)
        selected = [row for row in current if _utc(str(row[4])) == cutoff]
        identities = {(str(row[0]), str(row[1])) for row in selected}
        if len(identities) != 1:
            raise ValueError(
                "Ratings are ambiguous: latest cutoff has multiple manifests"
            )
        run_id, sha = identities.pop()
        if cutoff < latest_game + _RATING_AVAILABILITY:
            raise ValueError(
                "Ratings are stale: latest rating snapshot cutoff is "
                f"{cutoff.isoformat()}, but the latest completed kickoff is "
                f"{latest_game.isoformat()} (plus six-hour availability). "
                "Refresh ratings and run project-v5-ratings before prepare-week."
            )
    else:
        if not preseason:
            raise ValueError(
                "Ratings are missing: no projected preseason baseline. "
                "Run project-v5-ratings before prepare-week."
            )
        newest = max(_utc(str(row[5])) for row in preseason)
        identities = {
            (str(row[0]), str(row[1]))
            for row in preseason
            if _utc(str(row[5])) == newest
        }
        if len(identities) != 1:
            raise ValueError(
                "Ratings are ambiguous: latest preseason baseline has multiple manifests"
            )
        run_id, sha = identities.pop()
        selected = [
            row for row in preseason if (str(row[0]), str(row[1])) == (run_id, sha)
        ]
        cutoffs = {_utc(str(row[4])) for row in selected}
        if len(cutoffs) != 1:
            raise ValueError(
                "Ratings are ambiguous: preseason baseline has multiple cutoffs"
            )
        cutoff = cutoffs.pop()

    if cutoff > as_of:
        raise ValueError("Ratings cutoff is later than the requested as_of")
    if len(sha) != 64:
        raise ValueError("Ratings generation has an invalid manifest SHA")
    current_teams = [canonical_team(row[2]) for row in selected if row[3] == "current"]
    baseline_teams = [
        canonical_team(row[2])
        for row in preseason
        if (str(row[0]), str(row[1])) == (run_id, sha)
    ]
    if len(current_teams) != len(set(current_teams)) or len(baseline_teams) != len(
        set(baseline_teams)
    ):
        raise ValueError("Ratings generation has duplicate team snapshots")
    missing_current = (target_teams & experienced) - set(current_teams)
    missing_preseason = (target_teams - experienced) - set(baseline_teams)
    if missing_current or missing_preseason:
        raise ValueError(
            "Ratings generation lacks target-team coverage: "
            f"current={sorted(missing_current)}, preseason={sorted(missing_preseason)}. "
            "Refresh ratings and run project-v5-ratings before prepare-week."
        )
    return {
        "rating_cutoff_utc": cutoff.isoformat(),
        "rating_manifest_sha256": sha,
    }


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
    target_games = current_games[current_games["week"].astype(int) == args.week]
    target_teams = set(target_games["home_team"].dropna().astype(str)) | set(
        target_games["away_team"].dropna().astype(str)
    )
    try:
        conn_url = resolve_runtime_target(args.environment).database_url
        rating_rows = _rating_rows(
            conn_url, year=args.year, week=args.week, as_of=_utc(args.as_of)
        )
        rating_summary = _rating_currency(
            rating_rows,
            target_teams=target_teams,
            completed_games=completed_games,
            as_of=_utc(args.as_of),
        )
    except (psycopg.Error, RuntimeError, ValueError) as exc:
        raise SystemExit(f"Ratings readiness failed: {exc}") from exc
    print(
        json.dumps(
            {
                "state": "ready",
                "year": args.year,
                "week": args.week,
                "target_game_count": len(target_ids),
                "completed_game_count": len(completed_games),
                "gold_version_id": gold_ref.version_id,
                **rating_summary,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
