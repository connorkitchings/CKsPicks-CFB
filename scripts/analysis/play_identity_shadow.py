"""Shadow builds for the play-identity impact diff (read-only; no write of any kind).

Runs the unchanged v1 pipeline twice per collision season on the collision games only:
the historical ``keep="first"`` input, and an input that retains every distinct provider
play under shadow sequence numbers (see ``shadow_retained``). Differences are matched by
provider play ID, never by displayed sequence.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from scripts.analysis.play_identity_impact import (
    SEQ,
    diff_frames,
    legacy_dedup,
    members_digest,
    order_diagnostics,
    remap_source_tokens,
    shadow_retained,
    source_play_ids,
)

NULLABLE_PPA = True  # rebuild.silver.PIPELINE_CONFIG["nullable_ppa"]


def token_lookup(plays: pd.DataFrame, season: int) -> dict[str, str]:
    ids = source_play_ids(plays["play_id"])
    return {
        f"{season}:{g}:{d}:{p}": i
        for g, d, p, i in zip(
            plays["game_id"].astype(int),
            plays["drive_number"].astype(int),
            plays["play_number"].astype(int),
            ids,
        )
    }


def attach_ids(frame: pd.DataFrame, plays: pd.DataFrame) -> pd.DataFrame:
    lookup = (
        plays[SEQ]
        .astype(int)
        .assign(source_play_id=source_play_ids(plays["play_id"]).to_numpy())
    )
    keyed = frame.assign(**{k: frame[k].astype(int) for k in SEQ}).merge(
        lookup, on=SEQ, how="left", validate="many_to_one"
    )
    if keyed["source_play_id"].isna().any():
        raise ValueError("by-play rows without a provider play ID")
    return keyed


def drive_keys(byplay: pd.DataFrame, drives: pd.DataFrame) -> pd.DataFrame:
    members = (
        byplay.groupby(["game_id", "drive_number", "offense", "defense"], sort=True)[
            "source_play_id"
        ]
        .apply(lambda ids: sorted(ids))
        .rename("members")
        .reset_index()
    )
    merged = drives.merge(
        members, on=["game_id", "drive_number", "offense", "defense"], how="left"
    )
    merged["members"] = merged["members"].map(
        lambda m: m if isinstance(m, list) else []
    )
    merged["drive_key"] = [
        members_digest([str(g), str(o), str(d)] + m)
        for g, o, d, m in zip(
            merged["game_id"], merged["offense"], merged["defense"], merged["members"]
        )
    ]
    merged["member_count"] = merged["members"].map(len)
    return merged.drop(columns="members")


def build_variant(
    plays: pd.DataFrame, *, season: int, games: pd.DataFrame, frames: dict
) -> dict[str, Any]:
    from cks_picks_cfb.features.pipeline import build_preaggregation_pipeline
    from cks_picks_cfb.ratings.possession_measurements import build_measurements

    byplay, drives, team_game, _ = build_preaggregation_pipeline(
        plays,
        games_df=games.rename(columns={"kickoff_utc": "start_date"}),
        teams_df=frames.get("teams"),
        venues_df=None,
        weather_df=None,
        corrections_df=frames.get("data_corrections"),
        nullable_ppa=NULLABLE_PPA,
    )
    population = games[
        ["season", "week", "game_id", "home_team", "away_team", "kickoff_utc"]
    ].assign(forecast_eligible=True)
    measured = build_measurements(
        byplay=byplay, population=population, scope="historical"
    )
    lookup = token_lookup(plays, season)
    byplay = attach_ids(byplay, plays)
    drives = drive_keys(byplay, drives)
    possessions = remap_source_tokens(measured.possessions, lookup)
    possessions["possession_key"] = [
        members_digest([str(g), str(o)] + sorted(json.loads(ids)))
        for g, o, ids in zip(
            possessions["game_id"],
            possessions["offense"],
            possessions["source_play_ids"],
        )
    ]
    scoring = remap_source_tokens(measured.scoring_events, lookup)
    return {
        "byplay": byplay,
        "drives": drives,
        "team_game": team_game,
        "possessions": possessions,
        "scoring_events": scoring,
        "observations": measured.observations,
    }


def fidelity(historical: dict[str, Any], legacy: dict[str, pd.DataFrame]) -> dict:
    """Does the shadow historical build match the pinned legacy Silver for these games?"""
    out: dict[str, Any] = {}
    keys = {"byplay": SEQ, "drives": ["game_id", "drive_number", "offense", "defense"]}
    for name, key in keys.items():
        new = historical[name].drop(
            columns=["source_play_id", "drive_key", "member_count"], errors="ignore"
        )
        old = legacy[name]
        columns = [c for c in new.columns if c in old.columns and c not in key]
        merged = new.merge(
            old, on=key, suffixes=("_new", "_legacy"), how="outer", indicator=True
        )
        report: dict[str, Any] = {
            "rows_new": int(len(new)),
            "rows_legacy": int(len(old)),
            "unmatched_rows": int((merged["_merge"] != "both").sum()),
            "differing_columns": {},
        }
        both = merged[merged["_merge"] == "both"]
        for column in columns:
            left, right = both[f"{column}_new"], both[f"{column}_legacy"]
            differ = ~((left == right) | (left.isna() & right.isna()))
            if differ.any():
                detail: dict[str, Any] = {"rows": int(differ.sum())}
                if column == "ppa":
                    detail["legacy_zero_new_null"] = int(
                        (differ & right.eq(0) & left.isna()).sum()
                    )
                report["differing_columns"][column] = detail
        out[name] = report
    return out


def dataset_diffs(h: dict[str, Any], r: dict[str, Any]) -> dict[str, Any]:
    return {
        "byplay": diff_frames(
            h["byplay"],
            r["byplay"],
            ["source_play_id"],
            ignore=("drive_number", "play_number"),
        ),
        "drives": diff_frames(
            h["drives"], r["drives"], ["drive_key"], ignore=("drive_number",)
        ),
        "team_game": diff_frames(h["team_game"], r["team_game"], ["game_id", "team"]),
        "possessions": diff_frames(
            h["possessions"],
            r["possessions"],
            ["possession_key"],
            ignore=("drive_number", "source_play_ids"),
        ),
        "scoring_events": diff_frames(
            h["scoring_events"],
            r["scoring_events"],
            ["source_event_id", "team"],
            ignore=("drive_number",),
        ),
        "observations": diff_frames(
            h["observations"],
            r["observations"],
            ["game_id", "team", "measurement_id", "unit_role"],
        ),
    }


def reached_teams(
    datasets: dict[str, Any], games: pd.DataFrame
) -> list[dict[str, Any]]:
    """Games, weeks and teams whose team-game values differ (the rating inputs)."""
    changed: dict[tuple[int, str], set[str]] = {}
    for cell in datasets["observations"]["changed_cells"]:
        game, team, measurement, _role = cell["key"]
        changed.setdefault((int(game), str(team)), set()).add(str(measurement))
    info = games.set_index("game_id")[["season", "week", "home_team", "away_team"]]
    return [
        {
            "season": int(info.at[game, "season"]),
            "week": int(info.at[game, "week"]),
            "game_id": game,
            "team": team,
            "measurements": sorted(measurements),
        }
        for (game, team), measurements in sorted(changed.items())
    ]


def run_shadow(*, storage, blocks, plays_cache, collision_games, ref) -> dict[str, Any]:
    from cks_picks_cfb.data.lake import read_dataset

    seasons: dict[str, Any] = {}
    for season in sorted(plays_cache):
        games_in_scope = sorted(collision_games[season])
        parents = {p["dataset"]: p for p in blocks[season]["parents"]}
        frames = {
            name: read_dataset(storage, ref(parents[name]))
            for name in ("fbs_involved_games", "teams", "data_corrections")
        }
        games = frames["fbs_involved_games"]
        games = games[games["game_id"].isin(games_in_scope)].reset_index(drop=True)
        corrections = frames["data_corrections"]
        touching = 0
        if "record_key" in corrections:
            touching = int(
                corrections["record_key"]
                .astype(str)
                .map(lambda k: any(str(g) in k for g in games_in_scope))
                .sum()
            )
        plays = plays_cache[season]
        plays = plays[plays["game_id"].isin(games_in_scope)].reset_index(drop=True)
        historical_in = legacy_dedup(plays)
        retained_in = shadow_retained(plays)
        built = {
            "historical": build_variant(
                historical_in, season=season, games=games, frames=frames
            ),
            "retained": build_variant(
                retained_in, season=season, games=games, frames=frames
            ),
        }
        legacy_entry = blocks[season]["legacy_comparison"]
        legacy = {
            name: read_dataset(storage, ref(legacy_entry[name]))
            for name in ("byplay", "drives")
        }
        legacy = {
            name: frame[frame["game_id"].isin(games_in_scope)]
            for name, frame in legacy.items()
        }
        unresolved_ids = {
            item["source_play_id"] for item in order_diagnostics(plays)["unresolved"]
        }
        kept = source_play_ids(retained_in["play_id"]).isin(unresolved_ids).to_numpy()
        built["retained_excluding_unresolved"] = build_variant(
            retained_in.loc[~kept], season=season, games=games, frames=frames
        )
        h, r = built["historical"], built["retained"]
        renumbered = retained_in.merge(
            plays[["play_id", "drive_number", "play_number"]],
            on="play_id",
            suffixes=("_shadow", "_original"),
        )
        datasets = dataset_diffs(h, r)
        excluding = dataset_diffs(h, built["retained_excluding_unresolved"])
        removed = plays.loc[~plays.index.isin(historical_in.index)]
        removed_ids = source_play_ids(removed["play_id"]).tolist()
        kept_twin = plays.merge(
            removed[SEQ].assign(__removed=True), on=SEQ, how="inner"
        )
        twins = {
            (int(g), int(d), int(p)): sorted(source_play_ids(grp["play_id"]).tolist())
            for (g, d, p), grp in kept_twin.groupby(SEQ)
        }
        removed_report = [
            {
                "game_id": int(row.game_id),
                "period": None if pd.isna(row.period) else int(row.period),
                "drive_number": int(row.drive_number),
                "play_number": int(row.play_number),
                "source_play_id": pid,
                "kept_by_historical_dedup": [
                    t
                    for t in twins[
                        (int(row.game_id), int(row.drive_number), int(row.play_number))
                    ]
                    if t != pid
                ],
                "offense": str(row.offense),
                "play_type": str(row.play_type),
                "scoring": bool(row.scoring),
                "ppa": None if pd.isna(row.ppa) else float(row.ppa),
                "provider_drive_id": str(row.drive_id),
            }
            for row, pid in zip(removed.itertuples(), removed_ids)
        ]
        reach = reached_teams(datasets, games)
        seasons[str(season)] = {
            "games": games_in_scope,
            "plays_in_games": int(len(plays)),
            "historical_input_plays": int(len(historical_in)),
            "retained_input_plays": int(len(retained_in)),
            "plays_removed_by_historical_dedup": int(len(plays) - len(historical_in)),
            "shadow_renumbered_plays": int(
                (
                    (
                        renumbered["drive_number_shadow"]
                        != renumbered["drive_number_original"]
                    )
                    | (
                        renumbered["play_number_shadow"]
                        != renumbered["play_number_original"]
                    )
                ).sum()
            ),
            "corrections_touching_games": touching,
            "fidelity_to_pinned_legacy": fidelity(h, legacy),
            "removed_by_historical_dedup": removed_report,
            "removed_summary": {
                "plays": len(removed_report),
                "with_non_null_ppa": sum(x["ppa"] is not None for x in removed_report),
                "scoring": sum(x["scoring"] for x in removed_report),
            },
            "datasets": datasets,
            "datasets_excluding_unresolved_plays": excluding,
            "unresolved_plays_excluded": sorted(unresolved_ids),
            "descendant_reach": reach,
        }
    return {
        "method": "unchanged v1 pipeline on the collision games; retained variant uses shadow sequence numbers",
        "seasons": seasons,
    }
