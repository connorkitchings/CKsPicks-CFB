"""Provider-neutral Silver normalizers and dataset builders."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from datetime import datetime
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from cks_picks_cfb.data.lake import (
    BuildRequest,
    DatasetManifest,
    DatasetRef,
    SourceCapture,
    build_dataset_version,
    canonicalize_market_quotes_frame,
)
from cks_picks_cfb.data.schema_contracts import schema_for, validate_frame
from cks_picks_cfb.data.silver.contracts import (
    LEGACY_TIMESTAMP_STATUS,
    SILVER_CONTRACTS,
    SilverValidationError,
)
from cks_picks_cfb.data.storage import StorageBackend


def _rename_common(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    renames = {}
    for col in result.columns:
        if not col.startswith("__"):
            snake = re.sub(
                r"([a-z0-9])([A-Z])",
                r"\1_\2",
                re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", col),
            ).lower()
            if snake != col and snake not in result.columns:
                renames[col] = snake
    if renames:
        result = result.rename(columns=renames)
    renames = {}
    if "id" in result and "game_id" not in result:
        renames["id"] = "game_id"
    if "year" in result and "season" not in result:
        renames["year"] = "season"
    if "start_date" in result and "kickoff_utc" not in result:
        renames["start_date"] = "kickoff_utc"
    return result.rename(columns=renames)


def normalize_games(
    records: Sequence[Mapping[str, Any]], *, week_policy: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Normalize provider games, preserving provider week and applying policy.

    ``provider_week`` always retains the provider-reported value. ``week`` is
    the canonical week: identical to the provider week unless a versioned
    ``schedule_week_policy`` frame supplies an explicit ``canonical_week``.
    """
    frame = _rename_common(pd.DataFrame.from_records(records))
    required = SILVER_CONTRACTS["games"].required_columns | {
        "home_classification",
        "away_classification",
    }
    missing = sorted(required - (set(frame.columns) | {"provider_week"}))
    if missing:
        raise SilverValidationError(f"games missing columns: {missing}")
    frame["kickoff_utc"] = pd.to_datetime(
        frame["kickoff_utc"], utc=True, errors="raise"
    )
    frame["week"] = pd.to_numeric(frame["week"], errors="raise").astype(int)
    frame["season"] = pd.to_numeric(frame["season"], errors="raise").astype(int)
    frame["provider_week"] = frame["week"]
    fbs = frame["home_classification"].astype(str).str.casefold().eq("fbs") & frame[
        "away_classification"
    ].astype(str).str.casefold().eq("fbs")
    frame = frame[fbs].copy()
    if frame.empty:
        raise SilverValidationError("games contains no FBS-vs-FBS rows")
    if week_policy is not None:
        policy = week_policy[
            ["season", "game_id", "provider_week", "canonical_week"]
        ].copy()
        if policy.duplicated(["season", "game_id"]).any():
            raise SilverValidationError(
                "schedule week policy contains duplicate season/game_id rows"
            )
        merged = frame.merge(
            policy,
            on=["season", "game_id"],
            how="left",
            suffixes=("", "_policy"),
            validate="many_to_one",
        )
        unmatched = merged["canonical_week"].isna()
        if unmatched.any():
            missing_ids = sorted(merged.loc[unmatched, "game_id"].astype(int))
            raise SilverValidationError(
                f"schedule week policy does not cover games: {missing_ids[:10]}"
            )
        mismatched = merged["provider_week"] != merged["provider_week_policy"]
        if mismatched.any():
            conflict_ids = sorted(merged.loc[mismatched, "game_id"].astype(int))
            raise SilverValidationError(
                "schedule week policy provider_week conflicts for games: "
                f"{conflict_ids[:10]}"
            )
        merged["week"] = merged["canonical_week"].astype(int)
        frame = merged.drop(columns=["canonical_week", "provider_week_policy"])
    return frame.sort_values(["season", "kickoff_utc", "game_id"]).reset_index(
        drop=True
    )


def normalize_fbs_involved_games(
    records: Sequence[Mapping[str, Any]], *, week_policy: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Build the research schedule denominator without narrowing to FBS-FBS."""
    frame = _rename_common(pd.DataFrame.from_records(records))
    required = SILVER_CONTRACTS["fbs_involved_games"].required_columns | {
        "home_classification",
        "away_classification",
    }
    missing = sorted(
        required
        - (
            set(frame.columns)
            | {"provider_week", "population", "classification_unresolved"}
        )
    )
    if missing:
        raise SilverValidationError(f"fbs_involved_games missing columns: {missing}")
    frame["kickoff_utc"] = pd.to_datetime(
        frame["kickoff_utc"], utc=True, errors="raise"
    )
    frame["season"] = pd.to_numeric(frame["season"], errors="raise").astype(int)
    if frame["season"].eq(2020).any():
        raise SilverValidationError("fbs_involved_games rejects forbidden 2020 rows")
    frame["week"] = pd.to_numeric(frame["week"], errors="raise").astype(int)
    frame["provider_week"] = frame["week"]
    home = frame["home_classification"].astype("string").str.casefold()
    away = frame["away_classification"].astype("string").str.casefold()
    known_fbs = home.eq("fbs") | away.eq("fbs")
    unresolved = home.isna() | away.isna()
    frame["population"] = "excluded_non_fbs"
    frame.loc[known_fbs & home.eq("fbs") & away.eq("fbs"), "population"] = "fbs_fbs"
    frame.loc[known_fbs & ~unresolved & ~home.eq(away), "population"] = "fbs_fcs"
    frame.loc[unresolved, "population"] = "unresolved"
    frame["classification_unresolved"] = unresolved
    frame["season_type"] = frame["season_type"].astype(str).str.casefold()
    frame = frame[frame["population"].isin({"fbs_fbs", "fbs_fcs", "unresolved"})].copy()
    if frame.empty:
        raise SilverValidationError(
            "fbs_involved_games contains no target or unresolved rows"
        )
    if week_policy is not None:
        policy = week_policy[["season", "game_id", "provider_week", "canonical_week"]]
        frame = frame.merge(
            policy,
            on=["season", "game_id", "provider_week"],
            how="left",
            validate="many_to_one",
        )
        if frame["canonical_week"].isna().any():
            raise SilverValidationError(
                "schedule week policy does not cover fbs_involved_games"
            )
        frame["week"] = frame.pop("canonical_week").astype(int)
    if frame.duplicated(["season", "game_id"]).any():
        raise SilverValidationError(
            "fbs_involved_games contains duplicate season/game_id rows"
        )
    return frame.sort_values(["season", "kickoff_utc", "game_id"]).reset_index(
        drop=True
    )


def normalize_plays(
    records: Sequence[Mapping[str, Any]], *, games: pd.DataFrame | None = None
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source in records:
        wrapper = dict(source)
        raw = wrapper.get("provider_record", wrapper.get("raw_data", wrapper))
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = ast.literal_eval(raw)
        if isinstance(raw, Mapping):
            row = {}
            for k, v in raw.items():
                snake = re.sub(
                    r"([a-z0-9])([A-Z])",
                    r"\1_\2",
                    re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", k),
                ).lower()
                row[snake] = v
            for k, v in wrapper.items():
                if k not in ("provider_record", "raw_data"):
                    snake = re.sub(
                        r"([a-z0-9])([A-Z])",
                        r"\1_\2",
                        re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", k),
                    ).lower()
                    if snake not in row or row[snake] is None:
                        row[snake] = v
            if "canonical_week" in wrapper and wrapper["canonical_week"] is not None:
                row["week"] = wrapper["canonical_week"]
            if "clock" in row:
                clock = row.pop("clock")
                if isinstance(clock, Mapping):
                    row.setdefault("clock_minutes", clock.get("minutes"))
                    row.setdefault("clock_seconds", clock.get("seconds"))
            if "id" in row and "play_id" not in row:
                row["play_id"] = row.pop("id")
            rows.append(row)
        else:
            rows.append(wrapper)

    frame = _rename_common(pd.DataFrame.from_records(rows))
    if "play_id" not in frame and "id" in frame:
        frame["play_id"] = frame.pop("id")

    if games is not None and "game_id" in frame:
        if "season" not in frame or frame["season"].isna().any():
            game_season_map = dict(zip(games["game_id"], games["season"]))
            if "season" not in frame:
                frame["season"] = frame["game_id"].map(game_season_map)
            else:
                frame["season"] = frame["season"].fillna(
                    frame["game_id"].map(game_season_map)
                )
        if "week" not in frame or frame["week"].isna().any():
            game_week_map = dict(zip(games["game_id"], games["week"]))
            if "week" not in frame:
                frame["week"] = frame["game_id"].map(game_week_map)
            else:
                frame["week"] = frame["week"].fillna(
                    frame["game_id"].map(game_week_map)
                )

    required = SILVER_CONTRACTS["plays"].required_columns
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SilverValidationError(f"plays missing columns: {missing}")
    if frame["week"].isna().any():
        raise SilverValidationError("plays contains an unresolved week")
    frame["week"] = pd.to_numeric(frame["week"], errors="raise").astype(int)
    if "season" in frame:
        frame["season"] = pd.to_numeric(frame["season"], errors="raise").astype(int)
    if frame.duplicated(["game_id", "play_id"]).any():
        raise SilverValidationError("plays contains duplicate game_id/play_id keys")
    if games is not None:
        known = set(games["game_id"])
        unknown = set(frame["game_id"]) - known
        if unknown:
            if not (set(frame["game_id"]) & known):
                raise SilverValidationError(
                    f"plays reference unknown games: {sorted(unknown)[:10]}"
                )
            frame = frame[frame["game_id"].isin(known)].copy()
    return frame.sort_values(["season", "week", "game_id", "play_id"]).reset_index(
        drop=True
    )


def normalize_market_quotes(
    records: Sequence[Mapping[str, Any]], *, games: pd.DataFrame | None = None
) -> pd.DataFrame:
    flattened = []
    for record in records:
        row = dict(record)
        line = row.pop("line_data", None)
        if isinstance(line, str):
            try:
                decoded = ast.literal_eval(line)
            except (SyntaxError, ValueError) as exc:
                raise SilverValidationError(
                    "market quote line_data is not a valid mapping"
                ) from exc
            if not isinstance(decoded, Mapping):
                raise SilverValidationError("market quote line_data is not a mapping")
            line = decoded
        nested_lines = row.pop("lines", None)
        if isinstance(nested_lines, Sequence) and not isinstance(
            nested_lines, (str, bytes)
        ):
            for nested_line in nested_lines:
                if not isinstance(nested_line, Mapping):
                    continue
                nested_row = dict(row)
                nested_row.update(nested_line)
                nested_row.setdefault("game_id", nested_row.get("id"))
                flattened.append(nested_row)
            continue
        if isinstance(line, Mapping):
            row.update(line)
        if (
            "captured_at" not in row
            and row.get("__captured_at") is not None
            and row.get("__capture_provider") == "cfbd"
        ):
            row["captured_at"] = row["__captured_at"]
        if "quote_id" not in row:
            identity = json.dumps(
                {
                    "capture": row.get("__capture_id"),
                    "game_id": row.get("game_id"),
                    "provider": row.get("provider"),
                    "spread": row.get("spread"),
                    "total": row.get("over_under", row.get("total")),
                },
                sort_keys=True,
                default=str,
            )
            row["quote_id"] = hashlib.sha256(identity.encode()).hexdigest()[:32]
        flattened.append(row)
    frame = _rename_common(pd.DataFrame.from_records(flattened))
    frame = frame.rename(
        columns={
            "formattedSpread": "formatted_spread",
            "spreadOpen": "spread_open",
            "overUnder": "over_under",
            "overUnderOpen": "over_under_open",
            "homeMoneyline": "home_moneyline",
            "awayMoneyline": "away_moneyline",
        }
    )
    required = SILVER_CONTRACTS["market_quotes"].required_columns
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SilverValidationError(f"market_quotes missing columns: {missing}")
    if frame.duplicated(["quote_id"]).any():
        raise SilverValidationError("market_quotes contains duplicate quote IDs")
    frame["captured_at"] = pd.to_datetime(
        frame["captured_at"], utc=True, errors="raise"
    )
    if "over_under" in frame and "total" not in frame:
        frame["total"] = frame["over_under"]
    if games is not None and "season" not in frame:
        frame = frame.merge(
            games[["game_id", "season", "week"]].drop_duplicates("game_id"),
            on="game_id",
            how="left",
        )
    has_value = (
        frame.get("spread", pd.Series(index=frame.index, dtype=float)).notna()
        | frame.get("total", pd.Series(index=frame.index, dtype=float)).notna()
    )
    if not has_value.all():
        raise SilverValidationError("market quote has neither a spread nor a total")
    return frame.sort_values(["game_id", "captured_at", "provider"]).reset_index(
        drop=True
    )


def normalize_market_snapshots(
    records: Sequence[Mapping[str, Any]], *, games: pd.DataFrame | None = None
) -> pd.DataFrame:
    frame = _rename_common(pd.DataFrame.from_records(records)).rename(
        columns={
            "snapshot_id": "market_snapshot_id",
            "captured_at": "market_captured_at",
        }
    )
    if games is not None and "season" not in frame:
        game_context = games[["game_id", "season", "week"]].drop_duplicates("game_id")
        frame = frame.merge(game_context, on="game_id", how="left")
    if "market_captured_at" in frame:
        frame["market_captured_at"] = pd.to_datetime(
            frame["market_captured_at"], utc=True, errors="raise"
        )
    return frame


def normalize_legacy_market_references(
    records: Sequence[Mapping[str, Any]], *, games: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Preserve untimestamped legacy betting-line exports as inert references.

    Every row is stamped with the adjudicated flags that keep it out of
    canonical markets, leans, grades, ROI, model selection, and features.
    """
    rows: list[dict[str, Any]] = []
    for record in records:
        row = dict(record)
        line = row.pop("line_data", None)
        if isinstance(line, Mapping):
            row.update(line)
        if row.get("__capture_provider") != "legacy_cfbd_export":
            raise SilverValidationError(
                "legacy_market_references only accepts legacy_cfbd_export "
                f"captures, got {row.get('__capture_provider')!r}"
            )
        if row.get("captured_at") is not None:
            raise SilverValidationError(
                "record carries an authentic captured_at and is eligible for "
                "canonical market_quotes; refusing to quarantine it as legacy"
            )
        if not row.get("__capture_id"):
            raise SilverValidationError(
                "legacy market row lacks source capture provenance"
            )
        if not row.get("__source_uri") or not row.get("__source_sha256"):
            raise SilverValidationError(
                "legacy market row lacks source object/checksum provenance"
            )
        flattened = _rename_common(pd.DataFrame.from_records([row])).iloc[0].to_dict()
        spread = flattened.get("spread")
        total = flattened.get("total", flattened.get("over_under"))
        if spread is None and total is None:
            continue
        rows.append(
            {
                "season": flattened.get("season"),
                "provider_week": flattened.get("week"),
                "game_id": flattened.get("game_id"),
                "provider": flattened.get("provider"),
                "spread": spread,
                "total": total,
                "spread_open": flattened.get("spread_open"),
                "total_open": flattened.get("over_under_open"),
                "home_moneyline": flattened.get("home_moneyline"),
                "away_moneyline": flattened.get("away_moneyline"),
                "formatted_spread": flattened.get("formatted_spread"),
                "season_type": flattened.get("season_type"),
                "source_capture_id": row["__capture_id"],
                "source_uri": row["__source_uri"],
                "source_sha256": row["__source_sha256"],
                "timestamp_status": LEGACY_TIMESTAMP_STATUS,
                "exact_replay_eligible": False,
                "grading_eligible": False,
                "lean_eligible": False,
            }
        )
    frame = pd.DataFrame.from_records(rows)
    if frame.empty:
        raise SilverValidationError("legacy_market_references contains no rows")
    frame["season"] = pd.to_numeric(frame["season"], errors="raise").astype(int)
    frame["provider_week"] = pd.to_numeric(
        frame["provider_week"], errors="raise"
    ).astype(int)
    if games is not None:
        unknown = set(frame["game_id"]) - set(games["game_id"])
        if unknown:
            raise SilverValidationError(
                f"legacy market rows reference unknown games: {sorted(unknown)[:10]}"
            )
    return frame.sort_values(
        ["season", "provider_week", "game_id", "provider"]
    ).reset_index(drop=True)


def normalize_schedule_week_policy(
    records: Sequence[Mapping[str, Any]], *, games: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Validate a versioned canonical-week assignment for every scheduled game."""
    frame = pd.DataFrame.from_records(records)
    required = SILVER_CONTRACTS["schedule_week_policy"].required_columns
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SilverValidationError(f"schedule_week_policy missing columns: {missing}")
    frame["kickoff_utc"] = pd.to_datetime(
        frame["kickoff_utc"], utc=True, errors="raise"
    )
    for column in ("season", "provider_week", "canonical_week"):
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(int)
    if (frame["canonical_week"] < 0).any() or (frame["provider_week"] < 0).any():
        raise SilverValidationError("schedule weeks must be non-negative")
    if frame.duplicated(["season", "game_id"]).any():
        raise SilverValidationError(
            "schedule_week_policy contains duplicate season/game_id rows"
        )
    if games is not None:
        schedule = games[["season", "game_id", "provider_week"]].drop_duplicates()
        merged = frame.merge(
            schedule,
            on=["season", "game_id"],
            how="left",
            suffixes=("", "_schedule"),
            validate="one_to_one",
        )
        unknown = merged["provider_week_schedule"].isna()
        if unknown.any():
            unknown_ids = sorted(merged.loc[unknown, "game_id"].astype(int))
            raise SilverValidationError(
                f"schedule week policy references unknown games: {unknown_ids[:10]}"
            )
        mismatch = merged["provider_week"] != merged["provider_week_schedule"]
        if mismatch.any():
            conflict_ids = sorted(merged.loc[mismatch, "game_id"].astype(int))
            raise SilverValidationError(
                "schedule week policy provider_week conflicts with schedule: "
                f"{conflict_ids[:10]}"
            )
        uncovered = set(map(tuple, schedule[["season", "game_id"]].to_numpy()))
        covered = set(map(tuple, frame[["season", "game_id"]].to_numpy()))
        missing_games = sorted(uncovered - covered)
        if missing_games:
            raise SilverValidationError(
                "schedule week policy must assign a canonical week to every "
                f"game; missing: {missing_games[:10]}"
            )
        frame = merged.drop(columns=["provider_week_schedule"])
    return frame.sort_values(["season", "kickoff_utc", "game_id"]).reset_index(
        drop=True
    )


def normalize_teams(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame.from_records(records).rename(
        columns={"id": "team_id", "school": "team", "year": "season"}
    )
    return frame


def normalize_team_aliases(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    rows = []
    for record in records:
        team = record.get("school", record.get("team"))
        if not team:
            raise SilverValidationError("team alias source lacks canonical team name")
        aliases = [team]
        for key in ("alternate_names", "alt_name_1", "alt_name_2", "alt_name_3"):
            value = record.get(key)
            aliases.extend(
                value if isinstance(value, list) else [value] if value else []
            )
        for alias in dict.fromkeys(str(value) for value in aliases if value):
            rows.append(
                {
                    "provider": "cfbd",
                    "provider_name": alias,
                    "team": str(team),
                }
            )
    return pd.DataFrame.from_records(rows)


def normalize_game_outcomes(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    frame = _rename_common(pd.DataFrame.from_records(records))
    required = SILVER_CONTRACTS["game_outcomes"].required_columns
    if missing := sorted(required - set(frame.columns)):
        raise SilverValidationError(f"game outcomes missing columns: {missing}")
    return (
        frame[sorted(required)]
        .sort_values(["season", "game_id"])
        .reset_index(drop=True)
    )


def normalize_venues(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame.from_records(records).rename(columns={"id": "venue_id"})


def normalize_team_game_stats(
    records: Sequence[Mapping[str, Any]], *, games: pd.DataFrame | None = None
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source in records:
        wrapper = dict(source)
        raw = wrapper.get("provider_record", wrapper.get("raw_data", wrapper))
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = ast.literal_eval(raw)
        if not isinstance(raw, Mapping):
            raise SilverValidationError("team_game_stats record is not an object")
        game_id = raw.get("id", raw.get("game_id", wrapper.get("game_id")))
        season = wrapper.get("season", wrapper.get("year", raw.get("season")))
        week = wrapper.get(
            "canonical_week",
            wrapper.get("request_week", wrapper.get("week", raw.get("week"))),
        )
        teams = raw.get("teams")
        if not isinstance(teams, list) or len(teams) != 2:
            raise SilverValidationError(
                f"team_game_stats game {game_id} does not contain exactly two teams"
            )
        for team in teams:
            if not isinstance(team, Mapping):
                raise SilverValidationError("team_game_stats team is not an object")
            row = {
                "season": season,
                "week": week,
                "game_id": game_id,
                "team_id": team.get("teamId", team.get("team_id")),
                "team": team.get("team"),
                "conference": team.get("conference"),
                "home_away": team.get("homeAway", team.get("home_away")),
                "points": team.get("points"),
            }
            for stat in team.get("stats", []):
                if not isinstance(stat, Mapping) or not stat.get("category"):
                    raise SilverValidationError("team stat lacks a category")
                slug = re.sub(
                    r"[^a-z0-9]+",
                    "_",
                    re.sub(r"(?<!^)(?=[A-Z])", "_", str(stat["category"])).lower(),
                ).strip("_")
                row[slug] = stat.get("stat")
            rows.append(row)
    frame = pd.DataFrame.from_records(rows)
    if games is not None and "game_id" in frame:
        if "season" not in frame or frame["season"].isna().any():
            game_season_map = dict(zip(games["game_id"], games["season"]))
            if "season" not in frame:
                frame["season"] = frame["game_id"].map(game_season_map)
            else:
                frame["season"] = frame["season"].fillna(
                    frame["game_id"].map(game_season_map)
                )
        if "week" not in frame or frame["week"].isna().any():
            game_week_map = dict(zip(games["game_id"], games["week"]))
            if "week" not in frame:
                frame["week"] = frame["game_id"].map(game_week_map)
            else:
                frame["week"] = frame["week"].fillna(
                    frame["game_id"].map(game_week_map)
                )
    if frame.duplicated(["season", "game_id", "team"]).any():
        raise SilverValidationError("team_game_stats contains duplicate team/game rows")
    return frame.sort_values(["season", "week", "game_id", "team"]).reset_index(
        drop=True
    )


def normalize_data_corrections(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame.from_records(records).copy()
    if "field" in frame and "changed_field" not in frame:
        frame = frame.rename(columns={"field": "changed_field"})
    if "approved_at" in frame:
        frame["approved_at"] = pd.to_datetime(
            frame["approved_at"], utc=True, errors="raise"
        )
    if "record_key" in frame:
        for index, value in frame["record_key"].items():
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError as exc:
                    raise SilverValidationError(
                        "correction record_key is invalid JSON"
                    ) from exc
            if not isinstance(value, Mapping):
                raise SilverValidationError("correction record_key must be an object")
            frame.at[index, "record_key"] = dict(value)
    return frame


def normalize_weather(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    frame = _rename_common(pd.DataFrame.from_records(records))
    if "observed_at" not in frame:
        source = next(
            (
                column
                for column in ("captured_at", "forecast_at", "kickoff_utc")
                if column in frame
            ),
            None,
        )
        if source:
            frame["observed_at"] = frame[source]
    if "observed_at" in frame:
        frame["observed_at"] = pd.to_datetime(
            frame["observed_at"], utc=True, errors="raise"
        )
    return frame


def normalize_preseason_inputs(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    frame = _rename_common(pd.DataFrame.from_records(records))
    if "team" not in frame:
        source = next(
            (column for column in ("school", "offense") if column in frame), None
        )
        if source:
            frame = frame.rename(columns={source: "team"})
    if "as_of" not in frame and "__captured_at" in frame:
        frame["as_of"] = frame["__captured_at"]
    if "as_of" in frame:
        frame["as_of"] = pd.to_datetime(frame["as_of"], utc=True, errors="raise")
    keys = ["season", "team", "as_of"]
    if set(keys).issubset(frame) and frame.duplicated(keys).any():
        frame = (
            frame.groupby(keys, as_index=False, dropna=False)
            .agg({column: "first" for column in frame.columns if column not in keys})
            .reset_index(drop=True)
        )
    return frame


NORMALIZERS: dict[str, Callable[..., pd.DataFrame]] = {
    "teams": normalize_teams,
    "venues": normalize_venues,
    "games": normalize_games,
    "fbs_involved_games": normalize_fbs_involved_games,
    "game_outcomes": normalize_game_outcomes,
    "team_aliases": normalize_team_aliases,
    "schedule_revisions": normalize_games,
    "plays": normalize_plays,
    "team_game_stats": normalize_team_game_stats,
    "market_quotes": normalize_market_quotes,
    "market_snapshots": normalize_market_snapshots,
    "legacy_market_references": normalize_legacy_market_references,
    "schedule_week_policy": normalize_schedule_week_policy,
    "weather_observations": normalize_weather,
    "preseason_team_inputs": normalize_preseason_inputs,
    "data_corrections": normalize_data_corrections,
}


def validate_contract(dataset: str, frame: pd.DataFrame) -> dict[str, Any]:
    if dataset not in SILVER_CONTRACTS:
        raise SilverValidationError(f"Unknown Silver dataset: {dataset}")
    contract = SILVER_CONTRACTS[dataset]
    missing = sorted(contract.required_columns - set(frame.columns))
    duplicate_count = (
        int(frame.duplicated(list(contract.key_columns)).sum())
        if set(contract.key_columns).issubset(frame.columns)
        else -1
    )
    validation = {
        "required_columns": not missing,
        "unique_keys": duplicate_count == 0,
        "nonempty": not frame.empty,
        "missing_columns": missing,
        "duplicate_key_count": duplicate_count,
    }
    if missing or duplicate_count != 0 or frame.empty:
        raise SilverValidationError(f"{dataset} contract failed: {validation}")
    return validation


def build_silver_version(
    storage: StorageBackend,
    *,
    dataset: str,
    records: Sequence[Mapping[str, Any]],
    source_captures: Sequence[SourceCapture],
    as_of: datetime,
    code_sha: str,
    config_sha: str,
    context: Mapping[str, Any] | None = None,
) -> tuple[DatasetRef, DatasetManifest]:
    """Normalize and build a Silver version from explicit Bronze captures."""
    if not source_captures:
        raise SilverValidationError("Silver builds require at least one Bronze capture")
    normalizer = NORMALIZERS.get(dataset)
    kwargs = dict(context or {})
    if dataset == "market_snapshots":
        quotes = normalize_market_quotes(records, games=kwargs.get("games"))
        frame = canonicalize_market_quotes_frame(quotes)
        if kwargs.get("games") is not None:
            frame = frame.merge(
                kwargs["games"][["game_id", "season", "week"]].drop_duplicates(
                    "game_id"
                ),
                on="game_id",
                how="left",
            )
    else:
        if normalizer:
            import inspect

            sig = inspect.signature(normalizer)
            filtered = {
                key: value for key, value in kwargs.items() if key in sig.parameters
            }
            frame = normalizer(records, **filtered)
        else:
            frame = pd.DataFrame.from_records(records)
    if dataset == "schedule_revisions" and "captured_at" not in frame:
        frame["captured_at"] = max(
            capture.captured_at for capture in source_captures
        ).isoformat()
    contract = SILVER_CONTRACTS[dataset]
    validation = validate_contract(dataset, frame)
    schema = schema_for(dataset, contract.schema_version)
    validation.update(validate_frame(frame, schema))
    return build_dataset_version(
        storage,
        build=BuildRequest(
            dataset=dataset,
            parent_refs=(),
            source_capture_ids=tuple(capture.capture_id for capture in source_captures),
            code_sha=code_sha,
            config_sha=config_sha,
            as_of=as_of,
            schema_version=contract.schema_version,
            tier="silver",
            schema_sha=schema.sha256,
        ),
        records=frame.to_dict("records"),
        partitions={
            "seasons": sorted(frame["season"].dropna().astype(int).unique().tolist())
            if "season" in frame
            else []
        },
        coverage={"source_capture_count": len(source_captures)},
        validation=validation,
        event_time_column="kickoff_utc" if "kickoff_utc" in frame else None,
    )
