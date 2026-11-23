"""Build an outcome-free, reconstructed pregame drive sample for totals research."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.play_filters import eligible_possession_play_mask
from cks_picks_cfb.preseason_features import canonical_team
from cks_picks_cfb.ratings.possession_measurements import build_possession_ledger
from cks_picks_cfb.ratings_lab.artifacts import open_research_storage, sha256
from cks_picks_cfb.ratings_lab.contracts import DEVELOPMENT_SEASONS

GAME = ["season", "game_id"]
DRIVE = [*GAME, "drive_number", "offense"]
FORECAST_COLUMNS = [
    *GAME,
    "week",
    "kickoff_utc",
    "home_team",
    "away_team",
    "completed_game_stage",
]
COUNTS = [
    "eligible_drives",
    "opportunity_known_drives",
    "opportunities",
    "opportunities_with_known_points",
    "opportunity_points",
    "starts",
    "start_yards",
]
METRICS = (
    "opportunities_per_eligible_drive",
    "points_per_opportunity",
    "starting_yards_to_goal",
)


def measure_drives(plays, possessions, scoring):
    """Combine V5 eligibility and score attribution with positional play evidence."""
    plays = plays.copy()
    plays["offense"] = plays["offense"].map(canonical_team)
    plays["position"] = pd.to_numeric(plays["yards_to_goal"], errors="coerce")
    plays["position"] = plays["position"].where(plays["position"].between(0, 100))
    plays = plays.sort_values([*DRIVE, "play_number"])
    starts = plays.drop_duplicates(DRIVE).set_index(DRIVE)["position"]
    eligible = plays.loc[eligible_possession_play_mask(plays)].copy()
    eligible["down"] = pd.to_numeric(eligible["down"], errors="coerce")
    eligible["known"] = eligible["down"].between(2, 4) | (
        eligible["down"].eq(1) & eligible["position"].notna()
    )
    eligible["created"] = eligible["down"].eq(1) & eligible["position"].lt(40)
    positions = eligible.groupby(DRIVE, sort=False).agg(
        known=("known", "all"), created=("created", "any")
    )

    drives = possessions.loc[
        possessions["possession_eligible"]
        & possessions["period_class"].eq("regulation")
        & possessions["quality_reason"].isna()
    ][[*DRIVE, "defense"]].copy()
    drives = drives.join(positions, on=DRIVE, validate="one_to_one")
    drives = drives.join(starts, on=DRIVE, validate="one_to_one")
    if drives[["known", "created"]].isna().any().any():
        raise ValueError("eligible ledger drive is missing matching eligible plays")
    drives["known"] |= drives["created"]

    # Allocated PATs can have a different event drive number. Use the ledger's
    # associated source play, including scoring plays excluded from eligibility.
    plays["possession_source_id"] = (
        plays[["season", "game_id", "drive_number", "play_number"]]
        .astype(int)
        .astype(str)
        .agg(":".join, axis=1)
    )
    points = scoring.loc[
        scoring["scoring_category"].eq("eligible_regulation_offense"),
        ["associated_possession_id", "score_increment"],
    ].merge(
        plays[[*DRIVE, "possession_source_id"]],
        left_on="associated_possession_id",
        right_on="possession_source_id",
        how="left",
        validate="many_to_one",
    )
    if points["possession_source_id"].isna().any():
        raise ValueError("eligible score is missing its associated source play")
    drives = drives.join(
        points.groupby(DRIVE)["score_increment"].sum().rename("points"),
        on=DRIVE,
        validate="one_to_one",
    )
    unresolved = (
        scoring.loc[scoring["scoring_category"].eq("unresolved"), [*GAME, "team"]]
        .drop_duplicates()
        .rename(columns={"team": "offense"})
        .assign(unresolved=True)
    )
    drives = drives.merge(unresolved, on=[*GAME, "offense"], how="left")
    drives["points"] = drives["points"].fillna(0).where(drives["unresolved"].isna())

    return drives[[*DRIVE, "defense", "position", "known", "created", "points"]]


def reconcile_and_count(drives, scoring, finals):
    """Mask finishing when the full score ledger differs from validated finals."""
    recorded = scoring.groupby([*GAME, "team"], as_index=False)["score_increment"].sum()
    actual = pd.concat(
        [
            finals[[*GAME, f"{side}_team", f"{side}_points"]].rename(
                columns={f"{side}_team": "team", f"{side}_points": "final"}
            )
            for side in ("home", "away")
        ],
        ignore_index=True,
    )
    comparison = actual.merge(
        recorded, on=[*GAME, "team"], how="left", validate="one_to_one"
    )
    comparison["matches"] = comparison["final"].eq(
        comparison["score_increment"].fillna(0)
    )
    matched = comparison.groupby(GAME)["matches"].all().rename("finals_reconciled")
    drives = drives.join(matched, on=GAME, validate="many_to_one")
    drives["finals_reconciled"] = drives["finals_reconciled"].eq(True)
    drives["points"] = drives["points"].where(drives["finals_reconciled"])

    drives["eligible_drives"] = 1
    drives["opportunity_known_drives"] = drives["known"].astype(int)
    drives["opportunities"] = drives["created"].astype(int)
    drives["opportunities_with_known_points"] = (
        drives["created"] & drives["points"].notna()
    ).astype(int)
    drives["opportunity_points"] = drives["points"].where(drives["created"], 0)
    drives["starts"] = drives["position"].notna().astype(int)
    drives["start_yards"] = drives["position"]
    return drives


def load_point_in_time_data(forecasts, source_games, drive_counts):
    """Use prior-week games after their reconstructed six-hour availability lag."""
    sample = forecasts.copy()
    sample["kickoff_utc"] = pd.to_datetime(sample["kickoff_utc"], utc=True)
    source_games = source_games.copy()
    source_games["available_utc"] = pd.to_datetime(
        source_games["kickoff_utc"], utc=True
    ) + pd.Timedelta(hours=6)
    sample["cutoff_utc"] = sample.groupby(["season", "week"])["kickoff_utc"].transform(
        "min"
    )
    for role, source_team in (("off", "offense"), ("def", "defense")):
        history = (
            drive_counts.groupby([*GAME, source_team], as_index=False)[COUNTS]
            .sum()
            .rename(columns={source_team: "team"})
            .merge(
                source_games[[*GAME, "week", "available_utc"]],
                on=GAME,
                validate="many_to_one",
            )
        )
        for side in ("home", "away"):
            for (season, week), slate in sample.groupby(["season", "week"]):
                cutoff = slate["cutoff_utc"].iloc[0]
                earlier = history.loc[
                    history["season"].eq(season)
                    & history["week"].lt(week)
                    & history["available_utc"].lt(cutoff)
                ]
                counts = (
                    earlier.groupby("team")[COUNTS].sum().reindex(slate[f"{side}_team"])
                )
                counts.index = slate.index
                prefix = f"{side}_{role}_"
                for column in COUNTS:
                    sample.loc[slate.index, prefix + column] = counts[column]
                eligible = counts["eligible_drives"]
                opportunities = counts["opportunities"]
                rates = (
                    opportunities
                    / eligible.where(
                        eligible.gt(0) & eligible.eq(counts["opportunity_known_drives"])
                    ),
                    counts["opportunity_points"]
                    / opportunities.where(
                        opportunities.gt(0)
                        & opportunities.eq(counts["opportunities_with_known_points"])
                        & eligible.eq(counts["opportunity_known_drives"])
                    ),
                    counts["start_yards"]
                    / counts["starts"].where(counts["starts"].gt(0)),
                )
                for metric, rate in zip(METRICS, rates, strict=True):
                    sample.loc[slate.index, prefix + metric] = rate
    return sample


def _development_frame(path):
    # Inspect partition identity before loading any wide frame. Only selected
    # columns are read and the approved seasons are checked again below.
    seasons = pd.read_parquet(path, columns=["season"])["season"]
    if seasons.empty or not set(seasons).issubset(DEVELOPMENT_SEASONS):
        raise ValueError("forecast frame must contain development seasons only")
    return pd.read_parquet(path, columns=FORECAST_COLUMNS).reset_index(drop=True)


def build_sample(forecasts, drives, scoring, forecast_frame, membership_dir):
    finals = pd.read_parquet(
        forecast_frame,
        columns=[
            *GAME,
            "home_team",
            "away_team",
            "outcome_valid",
            "home_points",
            "away_points",
        ],
    )
    finals = finals.loc[finals["outcome_valid"].eq(True)]
    drives = reconcile_and_count(drives, scoring, finals)
    counts = drives.groupby([*GAME, "offense", "defense"], as_index=False)[COUNTS].sum()
    sample = load_point_in_time_data(forecasts, forecasts, counts)
    sample, coverage, member_hashes = coverage_by_population(sample, membership_dir)
    return sample, coverage, member_hashes, drives


def coverage_by_population(sample, membership_dir):
    """Classify the same season-specific game populations used by the audit."""
    sample = sample.copy()
    member_hashes = {}
    fbs = set()
    for season in sorted(sample["season"].unique()):
        raw = (membership_dir / f"teams_{season}.json").read_bytes()
        member_hashes[str(season)] = sha256(raw)
        fbs.update(
            (season, canonical_team(team["school"]))
            for team in json.loads(raw)
            if team.get("classification") == "fbs" or team["school"] == "Notre Dame"
        )
    home_fbs = pd.MultiIndex.from_frame(sample[["season", "home_team"]]).isin(fbs)
    away_fbs = pd.MultiIndex.from_frame(sample[["season", "away_team"]]).isin(fbs)
    sample["population"] = "other"
    sample.loc[home_fbs & away_fbs, "population"] = "fbs_vs_fbs"
    sample.loc[home_fbs ^ away_fbs, "population"] = "fbs_vs_fcs"
    sample["stage"] = sample["completed_game_stage"].clip(upper=4)
    metrics = [
        f"{side}_{role}_{metric}"
        for side in ("home", "away")
        for role in ("off", "def")
        for metric in METRICS
    ]
    for metric in METRICS:
        sample[f"all_units_{metric}"] = (
            sample[[column for column in metrics if column.endswith(metric)]]
            .notna()
            .all(axis=1)
        )
    grouped = sample.groupby(["season", "stage", "population"])
    joint_metrics = [f"all_units_{metric}" for metric in METRICS]
    coverage = (
        grouped.size()
        .rename("games")
        .to_frame()
        .join(grouped[metrics].count())
        .join(grouped[joint_metrics].sum())
    )
    return sample.drop(columns=joint_metrics), coverage, member_hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecast-frame", type=Path, required=True)
    parser.add_argument("--silver-summary", type=Path, required=True)
    parser.add_argument("--rebuild-root", type=Path, required=True)
    parser.add_argument("--membership-dir", type=Path, required=True)
    parser.add_argument("--postseason-ids", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    forecasts = _development_frame(args.forecast_frame)
    postseason = set(map(tuple, json.loads(args.postseason_ids.read_bytes())))
    forecasts = forecasts.loc[
        ~pd.MultiIndex.from_frame(forecasts[GAME]).isin(postseason)
    ].reset_index(drop=True)
    if forecasts.empty or forecasts.duplicated(GAME).any():
        raise ValueError("duplicate or missing forecast game identities")

    storage = open_research_storage()
    root = json.loads(args.rebuild_root.read_bytes())
    silver_bytes = args.silver_summary.read_bytes()
    rebuild_prefix = f"rebuild/6a/{root['run_id']}"
    if sha256(silver_bytes) != root["objects"][f"{rebuild_prefix}/silver/summary.json"]:
        raise ValueError("Silver summary hash differs from the rebuild root")
    forecast_sha = sha256(args.forecast_frame.read_bytes())
    if (
        forecast_sha
        != root["objects"][f"{rebuild_prefix}/forecast/feature_frame.parquet"]
    ):
        raise ValueError("forecast frame hash differs from the rebuild root")
    refs = {}
    for entry in json.loads(silver_bytes)["seasons"]:
        ref = DatasetRef(**entry["datasets"]["byplay"]["ref"])
        if root["objects"].get(ref.uri) != ref.content_sha:
            raise ValueError("byplay hash differs from the rebuild root")
        refs[int(entry["season"])] = ref
    games = forecasts[[*GAME, "week", "kickoff_utc"]]
    audits = []
    event_audits = []
    for season in sorted(forecasts["season"].unique()):
        print(f"Reading pinned {season} plays", flush=True)
        season_games = games.loc[games["season"].eq(season)]
        plays = read_dataset(storage.source, refs[season])
        plays = plays.loc[plays["game_id"].isin(season_games["game_id"])]
        possessions, events = build_possession_ledger(
            byplay=plays, population=season_games
        )
        audits.append(measure_drives(plays, possessions, events))
        event_audits.append(events)
    scoring = pd.concat(event_audits, ignore_index=True)
    sample, coverage, member_hashes, drives = build_sample(
        forecasts,
        pd.concat(audits, ignore_index=True),
        scoring,
        args.forecast_frame,
        args.membership_dir,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sample.to_parquet(args.output_dir / "sample.parquet", index=False)
    drives.to_parquet(args.output_dir / "drive_audit.parquet", index=False)
    scoring.to_parquet(args.output_dir / "scoring_audit.parquet", index=False)
    coverage.to_csv(args.output_dir / "coverage.csv")
    pins = {
        "forecast_frame_sha256": forecast_sha,
        "membership_sha256": member_hashes,
        "postseason_sha256": sha256(args.postseason_ids.read_bytes()),
        "rebuild_root_sha256": sha256(args.rebuild_root.read_bytes()),
        "silver_summary_sha256": sha256(silver_bytes),
        "byplay": {
            str(s): refs[s].__dict__ for s in sorted(forecasts["season"].unique())
        },
    }
    (args.output_dir / "inputs.json").write_text(json.dumps(pins, indent=2) + "\n")


if __name__ == "__main__":
    main()
