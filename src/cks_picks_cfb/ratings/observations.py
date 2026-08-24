"""Long-form raw team-game measurement observations from immutable parents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from cks_picks_cfb.ratings.contracts import (
    OBSERVATION_COLUMNS,
    OBSERVATION_SCHEMA_VERSION,
    MeasurementConfig,
    MeasurementContractError,
    assert_no_market_fields,
)

_BYPLAY_REQUIRED = (
    "season",
    "week",
    "game_id",
    "drive_number",
    "play_number",
    "offense",
    "defense",
    "st",
    "penalty",
    "twopoint",
    "play_type",
    "garbage",
    "ppa",
    "success",
    "yards_gained",
    "turnover",
)
_DRIVES_REQUIRED = (
    "season",
    "week",
    "game_id",
    "drive_number",
    "offense",
    "defense",
    "start_yards_to_goal",
    "had_scoring_opportunity",
    "points",
    "points_on_opps",
)
_NON_COUNT_PLAY_TYPES = ("Timeout", "Uncategorized", "placeholder", "End Period")


@dataclass(frozen=True)
class ObservationBuildResult:
    frame: pd.DataFrame
    audit: dict[str, Any]


def _require_columns(
    frame: pd.DataFrame, required: tuple[str, ...], label: str
) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise MeasurementContractError(f"{label} missing columns: {missing}")


def _derive_is_drive_play(byplay: pd.DataFrame) -> pd.Series:
    return (
        (byplay.get("st", 0) == 0)
        & (byplay.get("penalty", 0) == 0)
        & (byplay.get("twopoint", 0) == 0)
        & (~byplay["play_type"].astype(str).isin(_NON_COUNT_PLAY_TYPES))
    ).astype(int)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _authentic_game_times(
    byplay: pd.DataFrame, drives: pd.DataFrame, config: MeasurementConfig
) -> dict[tuple[int, int], str]:
    """Return genuine source-availability times only when every parent has one."""
    candidates = [
        column
        for column in config.authentic_timestamp_columns
        if column in byplay.columns and column in drives.columns
    ]
    if not candidates:
        return {}
    column = candidates[0]
    result: dict[tuple[int, int], str] = {}
    for key, plays in byplay.groupby(["season", "game_id"]):
        drive_rows = drives[
            (drives["season"] == key[0]) & (drives["game_id"] == key[1])
        ]
        values = pd.concat(
            [
                pd.to_datetime(plays[column], utc=True, errors="coerce"),
                pd.to_datetime(drive_rows[column], utc=True, errors="coerce"),
            ],
            ignore_index=True,
        )
        if not values.empty and values.notna().all():
            result[(int(key[0]), int(key[1]))] = values.max().isoformat()
    return result


def build_measurement_observations(
    *,
    byplay: pd.DataFrame,
    drives: pd.DataFrame,
    games: pd.DataFrame,
    outcomes: pd.DataFrame,
    reconciled_team_game: pd.DataFrame,
    config: MeasurementConfig,
    as_of: datetime,
    code_sha: str,
    config_sha: str,
    parent_ref_shas: str,
) -> ObservationBuildResult:
    """Build one raw observation per game, team, measurement, and role."""
    for label, frame, required in (
        ("byplay", byplay, _BYPLAY_REQUIRED),
        ("drives", drives, _DRIVES_REQUIRED),
        (
            "games",
            games,
            (
                "season",
                "game_id",
                "week",
                "kickoff_utc",
                "home_team",
                "away_team",
                "completed",
            ),
        ),
        ("outcomes", outcomes, ("season", "game_id", "completed")),
        ("reconciled_team_game", reconciled_team_game, ("season", "game_id", "team")),
    ):
        _require_columns(frame, required, label)
        assert_no_market_fields(frame.columns, context=f"{label} parent columns")

    games = games.copy()
    if games.duplicated(["season", "game_id"]).any():
        raise MeasurementContractError("games parent contains duplicate game keys")
    forbidden = set(
        pd.to_numeric(games["season"], errors="coerce").dropna().astype(int)
    ) & set(config.forbidden_seasons)
    if forbidden:
        raise MeasurementContractError(
            f"games parent contains forbidden seasons: {sorted(forbidden)}"
        )

    as_of = as_of if as_of.tzinfo else as_of.replace(tzinfo=timezone.utc)
    as_of = as_of.astimezone(timezone.utc)

    games["season"] = pd.to_numeric(games["season"], errors="coerce").astype("Int64")
    games["kickoff_ts"] = pd.to_datetime(
        games["kickoff_utc"], utc=True, errors="coerce"
    )
    status = (
        games["status"].astype(str).str.lower().str.strip()
        if "status" in games.columns
        else pd.Series("", index=games.index)
    )
    outcome_completed = (
        outcomes.set_index(["season", "game_id"])["completed"].astype(bool)
        if not outcomes.empty
        else pd.Series(dtype=bool)
    )
    reconciled_teams = (
        reconciled_team_game.groupby(["season", "game_id"])["team"].apply(set).to_dict()
        if not reconciled_team_game.empty
        else {}
    )

    audit: dict[str, Any] = {
        "excluded_games": [],
        "season_counts": {},
        "out_of_scope_season_games": {},
        "quality_flag_counts": {},
    }
    in_scope = games["season"].isin(config.known_seasons)
    for season, count in (
        games.loc[~in_scope, "season"].value_counts().sort_index().items()
    ):
        audit["out_of_scope_season_games"][int(season)] = int(count)

    scheduled = games.loc[in_scope].copy()
    scheduled["_status"] = status.loc[in_scope]
    scheduled = scheduled.reset_index(drop=True)
    eligible_games: list[dict[str, Any]] = []
    for position, row in enumerate(
        scheduled[
            [
                "season",
                "week",
                "game_id",
                "kickoff_ts",
                "home_team",
                "away_team",
                "completed",
            ]
        ].itertuples(index=False)
    ):
        season = int(row.season)
        game_id = int(row.game_id)
        reason = None
        if pd.isna(row.kickoff_ts):
            reason = "missing_kickoff"
        elif scheduled.loc[position, "_status"] in config.excluded_statuses:
            reason = "cancelled_or_postponed"
        elif not bool(row.completed):
            reason = "incomplete"
        elif (season, game_id) not in outcome_completed.index:
            reason = "missing_outcome"
        elif not bool(outcome_completed.loc[(season, game_id)]):
            reason = "outcome_incomplete"
        elif row.kickoff_ts > as_of:
            if bool(row.completed):
                raise MeasurementContractError(
                    f"Completed game {game_id} kicks off after the as-of cutoff; "
                    "parents contradict the point-in-time build"
                )
            reason = "kickoff_after_as_of"
        elif reconciled_teams.get((season, game_id)) != {row.home_team, row.away_team}:
            reason = "unreconciled"
        if reason is None:
            eligible_games.append(
                {
                    "season": season,
                    "week": int(row.week),
                    "game_id": game_id,
                    "kickoff": row.kickoff_ts,
                    "home_team": row.home_team,
                    "away_team": row.away_team,
                }
            )
        else:
            audit["excluded_games"].append(
                {"season": season, "game_id": game_id, "reason": reason}
            )

    eligible_ids = {(game["season"], game["game_id"]) for game in eligible_games}
    byplay["season"] = pd.to_numeric(byplay["season"], errors="coerce").astype("Int64")
    drives["season"] = pd.to_numeric(drives["season"], errors="coerce").astype("Int64")
    byplay["game_id"] = pd.to_numeric(byplay["game_id"], errors="coerce").astype("Int64")
    drives["game_id"] = pd.to_numeric(drives["game_id"], errors="coerce").astype("Int64")
    byplay = byplay[
        byplay.apply(lambda row: (int(row["season"]), int(row["game_id"])) in eligible_ids, axis=1)
    ].copy()
    drives = drives[
        drives.apply(lambda row: (int(row["season"]), int(row["game_id"])) in eligible_ids, axis=1)
    ].copy()

    byplay["is_drive_play"] = _derive_is_drive_play(byplay)
    garbage = pd.to_numeric(byplay["garbage"], errors="coerce")
    byplay["eligible"] = (byplay["is_drive_play"] == 1) & (garbage == 0)

    quality: dict[tuple[int, int], list[str]] = {}
    ambiguous = byplay[(byplay["is_drive_play"] == 1) & garbage.isna()]
    for season, game_id in ambiguous[["season", "game_id"]].drop_duplicates().itertuples(index=False):
        quality.setdefault((int(season), int(game_id)), []).append("garbage_flag_missing")
    eligible_plays = byplay[byplay["eligible"]]

    ppa = pd.to_numeric(eligible_plays["ppa"], errors="coerce")
    success = pd.to_numeric(eligible_plays["success"], errors="coerce")
    yards = pd.to_numeric(eligible_plays["yards_gained"], errors="coerce")
    turnover = pd.to_numeric(eligible_plays["turnover"], errors="coerce")
    eligible_plays = eligible_plays.assign(
        ppa_num=ppa,
        ppa_denom=ppa.notna().astype(int),
        success_num=((success == 1) & success.notna()).astype(int),
        success_denom=success.notna().astype(int),
        explosive_num=(yards >= 20).astype(int),
        turnover_num=(turnover == 1).astype(int),
    )
    for season, game_id in eligible_plays.loc[ppa.isna(), ["season", "game_id"]].drop_duplicates().itertuples(index=False):
        quality.setdefault((int(season), int(game_id)), []).append("ppa_missing_on_eligible_plays")
    for season, game_id in eligible_plays.loc[success.isna(), ["season", "game_id"]].drop_duplicates().itertuples(index=False):
        quality.setdefault((int(season), int(game_id)), []).append("success_missing_on_eligible_plays")

    play_agg_off = eligible_plays.groupby(["season", "game_id", "offense"]).agg(
        epa_num=("ppa_num", "sum"),
        epa_denom=("ppa_denom", "sum"),
        success_num=("success_num", "sum"),
        success_denom=("success_denom", "sum"),
        explosive_num=("explosive_num", "sum"),
        turnover_num=("turnover_num", "sum"),
        plays=("ppa_num", "size"),
    )
    play_agg_def = eligible_plays.groupby(["season", "game_id", "defense"]).agg(
        epa_num=("ppa_num", "sum"),
        epa_denom=("ppa_denom", "sum"),
        success_num=("success_num", "sum"),
        success_denom=("success_denom", "sum"),
        explosive_num=("explosive_num", "sum"),
        turnover_num=("turnover_num", "sum"),
        plays=("ppa_num", "size"),
    )

    eligible_drive_plays = (
        eligible_plays.groupby(["season", "game_id", "drive_number", "offense", "defense"])
        .size()
        .rename("eligible_plays")
        .reset_index()
    )
    drives = drives.merge(
        eligible_drive_plays,
        on=["season", "game_id", "drive_number", "offense", "defense"],
        how="inner",
    )
    drives = drives[drives["eligible_plays"] > 0].copy()
    start_field = pd.to_numeric(drives["start_yards_to_goal"], errors="coerce")
    drives["start_own_goal_distance"] = 100 - start_field
    drives["scoring_opportunity"] = (
        pd.to_numeric(drives["had_scoring_opportunity"], errors="coerce").fillna(0) == 1
    )
    missing_start = drives["start_own_goal_distance"].isna()
    for season, game_id in drives.loc[missing_start, ["season", "game_id"]].drop_duplicates().itertuples(index=False):
        quality.setdefault((int(season), int(game_id)), []).append("start_field_position_missing")
    drives_with_start = drives[~missing_start]
    drive_agg_off = drives_with_start.groupby(["season", "game_id", "offense"]).agg(
        start_sum=("start_own_goal_distance", "sum"),
        drives_count=("start_own_goal_distance", "size"),
    )
    drive_agg_def = drives_with_start.groupby(["season", "game_id", "defense"]).agg(
        start_sum=("start_own_goal_distance", "sum"),
        drives_count=("start_own_goal_distance", "size"),
    )
    opportunities_off = drives[drives["scoring_opportunity"]]
    opp_agg_off = opportunities_off.groupby(["season", "game_id", "offense"]).agg(
        opp_points=("points_on_opps", "sum"),
        opp_count=("points_on_opps", "size"),
    )
    opp_agg_def = opportunities_off.groupby(["season", "game_id", "defense"]).agg(
        opp_points=("points_on_opps", "sum"),
        opp_count=("points_on_opps", "size"),
    )
    drive_plays_off = eligible_drive_plays.groupby(["season", "game_id", "offense"]).agg(
        plays=("eligible_plays", "sum"),
        drives_count=("eligible_plays", "size"),
    )

    has_any_plays = (
        set(zip(byplay["season"].astype(int), byplay["game_id"].astype(int)))
        if not byplay.empty
        else set()
    )

    def _numerator_denominator(
        measurement_id: str, season: int, game_id: int, team: str, role: str
    ) -> tuple[float, float]:
        if measurement_id == "epa_per_play":
            agg = play_agg_off if role == "offense" else play_agg_def
            if (season, game_id, team) in agg.index:
                row = agg.loc[(season, game_id, team)]
                return float(row["epa_num"]), float(row["epa_denom"])
        elif measurement_id == "success_rate":
            agg = play_agg_off if role == "offense" else play_agg_def
            if (season, game_id, team) in agg.index:
                row = agg.loc[(season, game_id, team)]
                return float(row["success_num"]), float(row["success_denom"])
        elif measurement_id == "explosive_rate_20":
            agg = play_agg_off if role == "offense" else play_agg_def
            if (season, game_id, team) in agg.index:
                row = agg.loc[(season, game_id, team)]
                return float(row["explosive_num"]), float(row["plays"])
        elif measurement_id == "turnover_rate":
            agg = play_agg_off if role == "offense" else play_agg_def
            if (season, game_id, team) in agg.index:
                row = agg.loc[(season, game_id, team)]
                return float(row["turnover_num"]), float(row["plays"])
        elif measurement_id == "points_per_scoring_opportunity":
            agg = opp_agg_off if role == "offense" else opp_agg_def
            if (season, game_id, team) in agg.index:
                row = agg.loc[(season, game_id, team)]
                return float(row["opp_points"]), float(row["opp_count"])
        elif measurement_id == "average_start_field_position":
            agg = drive_agg_off if role == "offense" else drive_agg_def
            if (season, game_id, team) in agg.index:
                row = agg.loc[(season, game_id, team)]
                return float(row["start_sum"]), float(row["drives_count"])
        elif measurement_id == "plays_per_drive":
            if role == "offense" and (season, game_id, team) in drive_plays_off.index:
                row = drive_plays_off.loc[(season, game_id, team)]
                return float(row["plays"]), float(row["drives_count"])
        return 0.0, 0.0

    authentic_times = _authentic_game_times(byplay, drives, config)
    records: list[dict[str, Any]] = []
    season_counts: dict[int, dict[str, int]] = {}
    for game in eligible_games:
        game_id = game["game_id"]
        game_key = (game["season"], game_id)
        flags = sorted(set(quality.get(game_key, [])))
        for flag in flags:
            audit["quality_flag_counts"][flag] = (
                audit["quality_flag_counts"].get(flag, 0) + 1
            )
        counts = season_counts.setdefault(
            game["season"],
            {"eligible_games": 0, "observed_rows": 0, "missing_rows": 0},
        )
        counts["eligible_games"] += 1
        source_missing = (game["season"], game_id) not in has_any_plays
        for spec in config.measurements:
            for role in spec.roles:
                for team, opponent, side in (
                    (game["home_team"], game["away_team"], "home"),
                    (game["away_team"], game["home_team"], "away"),
                ):
                    numerator, denominator = _numerator_denominator(
                        spec.measurement_id, game["season"], game_id, team, role
                    )
                    if denominator > 0:
                        coverage_status = "observed"
                        missing_reason = None
                        raw_value = numerator / denominator
                    else:
                        coverage_status = "missing"
                        missing_reason = (
                            "source_evidence_missing"
                            if source_missing
                            else "zero_denominator"
                        )
                        raw_value = None
                    records.append(
                        {
                            "season": game["season"],
                            "week": game["week"],
                            "game_id": game_id,
                            "kickoff_utc": game["kickoff"].isoformat(),
                            "team": team,
                            "opponent": opponent,
                            "side": side,
                            "measurement_id": spec.measurement_id,
                            "unit_role": role,
                            "numerator": float(numerator),
                            "denominator": float(denominator),
                            "raw_value": raw_value,
                            "exposure_unit": spec.exposure_unit,
                            "effective_at": authentic_times.get(game_key),
                            "temporal_status": (
                                "authentic"
                                if game["season"] in config.authentic_seasons
                                and game_key in authentic_times
                                else "reconstructed"
                            ),
                            "eligible_after": authentic_times.get(game_key),
                            "coverage_status": coverage_status,
                            "missing_reason": missing_reason,
                            "quality_flags": ";".join(flags) if flags else None,
                            "measurement_schema_version": OBSERVATION_SCHEMA_VERSION,
                            "measurement_design_id": config.design_id,
                            "parent_ref_shas": parent_ref_shas,
                            "code_sha": code_sha,
                            "config_sha": config_sha,
                        }
                    )
                    counts[
                        "observed_rows"
                        if coverage_status == "observed"
                        else "missing_rows"
                    ] += 1

    frame = (
        pd.DataFrame.from_records(records, columns=OBSERVATION_COLUMNS)
        if records
        else pd.DataFrame(columns=OBSERVATION_COLUMNS)
    )
    if records:
        frame = frame.sort_values(
            ["season", "kickoff_utc", "game_id", "team", "measurement_id", "unit_role"],
            kind="mergesort",
        ).reset_index(drop=True)
    audit["season_counts"] = season_counts
    return ObservationBuildResult(frame=frame, audit=audit)
