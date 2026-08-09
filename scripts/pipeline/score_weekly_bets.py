import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
from cks_picks_cfb.artifacts import (
    dataframe_csv_bytes,
    local_prediction_path,
    local_scored_path,
    prediction_run_manifest_path,
    read_csv_artifact,
    read_json_artifact,
    read_verified_csv_artifact,
    scored_run_artifact_path,
    scored_run_manifest_path,
    sha256_bytes,
    write_json_artifact,
)
from cks_picks_cfb.data.storage import get_storage

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None


def resolve_frozen_run(conn_url: str, year: int, week: int) -> str:
    """Resolve the sole frozen/scored run from the Neon control plane."""
    if psycopg is None:
        raise RuntimeError("psycopg is required to resolve the frozen run")
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT run_id FROM prediction_runs "
                "WHERE season = %s AND week = %s AND state IN ('frozen', 'scored') "
                "ORDER BY frozen_at DESC NULLS LAST LIMIT 1",
                (year, week),
            )
            row = cur.fetchone()
    if not row:
        raise RuntimeError(f"No frozen prediction run for {year} week {week}")
    return str(row[0])


def load_week_scores(year, week):
    storage = get_storage()
    games = pd.DataFrame.from_records(storage.read_index("raw/games", {"year": year}))
    if games.empty:
        return games
    if "id" not in games.columns and "game_id" in games.columns:
        games = games.rename(columns={"game_id": "id"})
    week_games = games[games["week"] == week].copy()

    # Ensure we have scores
    if (
        "home_points" not in week_games.columns
        or "away_points" not in week_games.columns
    ):
        print(f"Warning: No score columns found for Week {week}")
        return week_games

    # Filter to completed games (non-null scores)
    week_games = week_games.dropna(subset=["home_points", "away_points"])

    return week_games[["id", "home_points", "away_points"]]


def score_bets(bets_df, scores_df):
    # Merge scores
    scored = bets_df.merge(scores_df, left_on="game_id", right_on="id", how="left")

    # Calculate Results
    scored["home_margin"] = scored["home_points"] - scored["away_points"]
    scored["total_score"] = scored["home_points"] + scored["away_points"]

    # Spread Result (Home Margin - (-Line)) = Home Margin + Line
    # If > 0 => Home Cover
    # If < 0 => Away Cover
    # If = 0 => Push

    def get_spread_result(row):
        if pd.isna(row["home_points"]) or pd.isna(row["home_team_spread_line"]):
            return None

        margin = row["home_points"] - row["away_points"]
        line = row["home_team_spread_line"]
        cover_margin = margin + line

        bet_side = str(row.get("Spread Bet", "")).lower()

        if cover_margin > 0:
            return (
                "Win"
                if bet_side == "home"
                else "Loss"
                if bet_side == "away"
                else "No Bet"
            )
        elif cover_margin < 0:
            return (
                "Loss"
                if bet_side == "home"
                else "Win"
                if bet_side == "away"
                else "No Bet"
            )
        else:
            return "Push"

    def get_total_result(row):
        if pd.isna(row["total_score"]) or pd.isna(row["total_line"]):
            return None

        score = row["total_score"]
        line = row["total_line"]
        bet_side = str(row.get("Total Bet", "")).lower()

        if score > line:
            return (
                "Win"
                if bet_side == "over"
                else "Loss"
                if bet_side == "under"
                else "No Bet"
            )
        elif score < line:
            return (
                "Loss"
                if bet_side == "over"
                else "Win"
                if bet_side == "under"
                else "No Bet"
            )
        else:
            return "Push"

    scored["Spread Bet Result"] = scored.apply(get_spread_result, axis=1)
    scored["Total Bet Result"] = scored.apply(get_total_result, axis=1)

    # For compatibility with publish_review, add numeric results?
    # publish_review uses:
    # all_games_df["Spread Result"] + all_games_df["Total Result"] to reconstruct scores?
    # Wait, publish_review lines 248-253:
    # all_games_df["home_points"] = (all_games_df["Spread Result"] + all_games_df["Total Result"]) / 2
    # This implies "Spread Result" and "Total Result" in the CSV are actually the SCORES?
    # Let's check `publish_review.py` again.
    # It reads `bets_scored.csv`.
    # It calculates `home_points` and `away_points` FROM `Spread Result` and `Total Result`.
    # This is weird naming.
    # Let's look at `publish_review.py` lines 248-253 again.
    # home_points = (Spread Result + Total Result) / 2
    # away_points = (Total Result - Spread Result) / 2
    # This means:
    # Total Result = home + away
    # Spread Result = home - away
    # So "Spread Result" column should be the actual game margin (Home - Away).
    # And "Total Result" column should be the actual game total (Home + Away).

    scored["Spread Result"] = scored["home_margin"]
    scored["Total Result"] = scored["total_score"]

    return scored


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Score Weekly Bets")
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument(
        "--predictions-csv",
        type=Path,
        default=None,
        help="Override ephemeral working-copy predictions CSV path.",
    )
    parser.add_argument(
        "--from-artifact",
        action="store_true",
        help="Read predictions from durable storage instead of local working-copy CSV.",
    )
    parser.add_argument(
        "--prediction-artifact-path",
        type=str,
        default=None,
        help="Explicit durable prediction path; otherwise --from-artifact requires the frozen manifest.",
    )
    parser.add_argument("--run-id", help="Explicit frozen run ID override.")
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Override ephemeral working-copy scored CSV path.",
    )
    parser.add_argument(
        "--upload-artifact",
        action="store_true",
        help="Also write the scored CSV to durable storage (R2/S3/local backend).",
    )
    args = parser.parse_args()

    year = args.year
    week = args.week

    print(f"Scoring bets for {year} Week {week}...")

    # Load Bets
    bets_path = args.predictions_csv or local_prediction_path(year, week)
    frozen_manifest = None
    if args.from_artifact and not args.prediction_artifact_path:
        try:
            run_id = args.run_id or resolve_frozen_run(
                os.environ.get("DATABASE_URL", ""), year, week
            )
            frozen_manifest = read_json_artifact(
                prediction_run_manifest_path(year, week, run_id)
            )
            artifact_path = str(frozen_manifest["artifact_uri"])
        except Exception as exc:
            raise SystemExit(
                f"No frozen prediction manifest for {year} week {week}: {exc}"
            ) from exc
    else:
        artifact_path = args.prediction_artifact_path or ""

    if frozen_manifest:
        try:
            bets_df = read_verified_csv_artifact(frozen_manifest)
        except Exception as exc:
            raise SystemExit(
                f"Could not verify frozen artifact {artifact_path}: {exc}"
            ) from exc
        print(f"Loaded verified frozen artifact {artifact_path}")
    elif args.from_artifact or args.prediction_artifact_path:
        try:
            bets_df = read_csv_artifact(artifact_path)
        except Exception as exc:
            raise SystemExit(
                f"Could not load prediction artifact {artifact_path}: {exc}"
            ) from exc
        print(f"Loaded predictions from durable artifact {artifact_path}")
    else:
        if not bets_path.exists():
            raise SystemExit(f"No bets file found at {bets_path}")
        bets_df = pd.read_csv(bets_path)

    if bets_df.empty:
        raise SystemExit(f"No bets available for {year} Week {week}")

    # Load Scores
    scores_df = load_week_scores(year, week)
    if scores_df.empty:
        raise SystemExit(f"No completed scores available for {year} Week {week}")

    # Score
    scored_df = score_bets(bets_df, scores_df)

    # Save
    output_path = args.output_csv or local_scored_path(year, week)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    scored_df.to_csv(output_path, index=False)
    print(f"Saved scored bets to {output_path}")

    if args.upload_artifact:
        run_id = (
            str(frozen_manifest["run_id"])
            if frozen_manifest
            else str(scored_df.get("run_id", pd.Series(["legacy"])).iloc[0])
        )
        scored_path = scored_run_artifact_path(year, week, run_id)
        manifest_path = scored_run_manifest_path(year, week, run_id)
        storage = get_storage()
        scored_bytes = dataframe_csv_bytes(scored_df)
        manifest_payload = {
            "schema_version": "scored_run_v1",
            "run_id": run_id,
            "season": year,
            "week": week,
            "artifact_uri": scored_path,
            "artifact_sha256": sha256_bytes(scored_bytes),
            "source_prediction_artifact": artifact_path,
        }
        artifact_exists = storage.exists(scored_path)
        manifest_exists = storage.exists(manifest_path)
        if artifact_exists != manifest_exists:
            raise FileExistsError(
                f"Partial scored run requires reconciliation: {run_id}"
            )
        if artifact_exists:
            if (
                storage.read_bytes(scored_path) != scored_bytes
                or read_json_artifact(manifest_path, storage) != manifest_payload
            ):
                raise FileExistsError(f"Immutable scored run collision: {run_id}")
        else:
            storage.write_bytes(scored_bytes, scored_path)
            write_json_artifact(manifest_payload, manifest_path, storage)
        print(f"Uploaded durable scored artifact to {scored_path}")


if __name__ == "__main__":
    main()
