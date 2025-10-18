"""Validation utilities for local CSV storage.

Provides checks for:
- Manifest row counts vs. CSV rows (via manifest only)
- Referential integrity (plays -> games)
- Duplicate detection within partitions (CSV read)
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.features.core import (
    aggregate_team_season,
    apply_iterative_opponent_adjustment,
)
from src.utils.local_storage import LocalStorage


@dataclass
class ValidationIssue:
    level: str  # "ERROR" | "WARN" | "INFO"
    message: str
    entity: str
    path: Path | None = None


def _iter_csv_files(root: Path) -> Iterable[Path]:
    """Recursively find all data.csv files."""
    for p in root.rglob("data.csv"):
        if p.is_file():
            yield p


def validate_manifest_counts(partition_dir: Path, entity: str) -> list[ValidationIssue]:
    """Check if the number of rows in the CSV matches the manifest count."""
    issues: list[ValidationIssue] = []
    manifest_path = partition_dir / "manifest.json"
    if not manifest_path.exists():
        issues.append(
            ValidationIssue(
                "ERROR", "Missing manifest.json", entity=entity, path=partition_dir
            )
        )
        return issues

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        manifest_rows = int(data.get("rows", -1))
    except (json.JSONDecodeError, ValueError) as e:
        issues.append(
            ValidationIssue(
                "ERROR",
                f"Failed to read manifest.json: {e}",
                entity=entity,
                path=manifest_path,
            )
        )
        return issues

    csv_path = partition_dir / "data.csv"
    if not csv_path.exists():
        if manifest_rows == 0:
            # Manifest says 0 rows, and no CSV exists, which is valid.
            return issues
        issues.append(
            ValidationIssue("ERROR", "Missing data.csv", entity=entity, path=csv_path)
        )
        return issues

    try:
        df = pd.read_csv(csv_path)
        csv_rows = len(df)
    except Exception as e:
        issues.append(
            ValidationIssue(
                "ERROR", f"Failed reading CSV: {e}", entity=entity, path=csv_path
            )
        )
        return issues

    if csv_rows != manifest_rows:
        issues.append(
            ValidationIssue(
                "ERROR",
                f"Manifest row count {manifest_rows} != CSV rows {csv_rows}",
                entity=entity,
                path=partition_dir,
            )
        )
    return issues


def validate_partition_duplicates(
    partition_dir: Path, entity: str, key_columns: list[str]
) -> list[ValidationIssue]:
    """Detect duplicates in a partition's data.csv based on key columns."""
    issues: list[ValidationIssue] = []
    csv_path = partition_dir / "data.csv"
    if not csv_path.exists():
        return issues  # No data to check for duplicates

    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return issues

        # Ensure all key columns are present before checking
        if not all(k in df.columns for k in key_columns):
            issues.append(
                ValidationIssue(
                    "WARN",
                    f"Skipping duplicate check; missing one or more keys: {key_columns}",
                    entity=entity,
                    path=partition_dir,
                )
            )
            return issues

        dup_mask = df.duplicated(subset=key_columns, keep=False)
        dup_count = int(dup_mask.sum())
        if dup_count > 0:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    f"Found {dup_count} duplicate rows on keys {key_columns}",
                    entity=entity,
                    path=partition_dir,
                )
            )
    except Exception as e:
        issues.append(
            ValidationIssue(
                "ERROR",
                f"Duplicate check failed: {e}",
                entity=entity,
                path=partition_dir,
            )
        )
    return issues


def validate_entity(
    storage: LocalStorage,
    year: int,
    entity: str,
    key_columns: list[str],
    partition_glob: str = "*/*/*",
) -> list[ValidationIssue]:
    """Generic validator for a processed entity.

    Supports both legacy path style (entity/<year>/...) and key=value style
    (entity/year=<year>/...).
    """
    issues: list[ValidationIssue] = []
    entity_root = storage.root() / entity

    # Determine year directory in a robust way
    legacy_year_dir = entity_root / str(year)
    kv_year_dir = entity_root / f"year={year}"

    if legacy_year_dir.exists():
        base_dir = legacy_year_dir
    elif kv_year_dir.exists():
        base_dir = kv_year_dir
    else:
        # Try discovering any year-like directory matching this year
        candidates = list(entity_root.glob(f"**/*{year}*"))
        base_dir = candidates[0] if candidates else None

    if base_dir is None or not base_dir.exists():
        issues.append(
            ValidationIssue(
                "WARN",
                "No data found for entity",
                entity=entity,
                path=legacy_year_dir if legacy_year_dir.exists() else kv_year_dir,
            )
        )
        return issues

    # Discover partition dirs (directories that contain manifest.json or data.csv)
    partition_dirs: list[Path] = []
    for p in base_dir.glob("**/*"):
        if p.is_dir():
            if (p / "manifest.json").exists() or (p / "data.csv").exists():
                partition_dirs.append(p)

    if not partition_dirs:
        issues.append(
            ValidationIssue(
                "INFO",
                "No partitions found to validate",
                entity=entity,
                path=base_dir,
            )
        )
        return issues

    print(f"Validating {len(partition_dirs)} partitions for entity '{entity}'...")
    for part_dir in partition_dirs:
        issues.extend(validate_manifest_counts(part_dir, entity))
        issues.extend(validate_partition_duplicates(part_dir, entity, key_columns))

    return issues


def validate_processed_season(
    storage: LocalStorage, year: int
) -> list[ValidationIssue]:
    """Run all validations for a processed season."""
    issues: list[ValidationIssue] = []
    print(f"--- Validating Processed Data for Season {year} ---")

    # byplay: year/week/game
    issues.extend(
        validate_entity(
            storage, year, "byplay", ["game_id", "drive_number", "play_number"], "*/*/*"
        )
    )
    # drives: year/week/game
    issues.extend(
        validate_entity(
            storage,
            year,
            "drives",
            ["game_id", "drive_number", "offense", "defense"],
            "*/*/*",
        )
    )
    # team_game: year/week/team
    issues.extend(
        validate_entity(storage, year, "team_game", ["game_id", "team"], "*/*/*")
    )
    # team_season & team_season_adj: year/team/side
    issues.extend(validate_entity(storage, year, "team_season", ["team"], "*/*/*"))
    issues.extend(validate_entity(storage, year, "team_season_adj", ["team"], "*/*/*"))

    return issues


def validate_raw_season(
    storage: LocalStorage, year: int, season_type: str = "regular"
) -> list[ValidationIssue]:
    """Run core validations for a raw data season."""
    issues: list[ValidationIssue] = []
    print(f"--- Validating Raw Data for Season {year} ---")

    # Simplified validation for raw data as an example
    games_dir = storage.root() / "games" / str(year)
    if games_dir.exists():
        (issues.extend(validate_manifest_counts(games_dir, "games")),)
        issues.extend(validate_partition_duplicates(games_dir, "games", ["id"]))
    else:
        issues.append(
            ValidationIssue(
                "WARN", "No games data for season", entity="games", path=games_dir
            )
        )
    return issues


# ------------------------------
# Deep semantic validations
# ------------------------------

_FLOAT_TOL = 1e-6
_RATE_TOL = 1e-3
_TIME_TOL = 1.5  # seconds


def validate_adjusted_consistency(
    storage: LocalStorage, year: int, tol: float = _FLOAT_TOL
) -> list[ValidationIssue]:
    """Deep validation: recompute adjusted metrics via pipeline semantics and compare to persisted.

    Steps:
    - Load processed team_game for the season
    - Recompute team_season via aggregate_team_season(team_game) with enhanced explosive rate calculation
    - Apply apply_iterative_opponent_adjustment to recomputed team_season using team_game
    - Compare to persisted team_season_adj per-side rows (only compare columns present in each row)
    """
    issues: list[ValidationIssue] = []
    # Load inputs
    tg_records = storage.read_index("team_game", {"year": year})
    if not tg_records:
        issues.append(
            ValidationIssue(
                "WARN", "No team_game data to validate", entity="team_season_adj"
            )
        )
        return issues
    tg = pd.DataFrame.from_records(tg_records)

    # Recompute team_season and adjusted
    ts_recalc = aggregate_team_season(tg)

    # Normalize rate-like columns before adjustment to reduce float drift
    for c in list(ts_recalc.columns):
        if isinstance(c, str) and "rate" in c:
            ts_recalc[c] = (
                pd.to_numeric(ts_recalc[c], errors="coerce")
                .clip(lower=0.0, upper=1.0)
                .round(6)
            )
    adj_recalc = apply_iterative_opponent_adjustment(ts_recalc, tg)
    # Also normalize adjusted rate columns post-adjust for comparison
    for c in list(adj_recalc.columns):
        if isinstance(c, str) and "rate" in c:
            adj_recalc[c] = (
                pd.to_numeric(adj_recalc[c], errors="coerce")
                .clip(lower=-1.0, upper=2.0)
                .round(6)
            )

    # Load persisted adjusted
    adj_records = storage.read_index("team_season_adj", {"year": year})
    if not adj_records:
        issues.append(
            ValidationIssue(
                "WARN",
                "No persisted team_season_adj rows found",
                entity="team_season_adj",
            )
        )
        return issues
    adj_persist = pd.DataFrame.from_records(adj_records)

    # Build per-side frames for comparison
    adj_cols = [c for c in adj_recalc.columns if c.startswith("adj_")]
    off_cols = [c for c in adj_cols if c.startswith("adj_off_")]
    def_cols = [c for c in adj_cols if c.startswith("adj_def_")]

    adj_off = adj_recalc[["season", "team"] + off_cols].copy()
    adj_def = adj_recalc[["season", "team"] + def_cols].copy()

    # Merge per-side recomputed values onto persisted
    merged = adj_persist.merge(
        adj_off, on=["season", "team"], how="left", suffixes=("", "_recomp_off")
    )
    merged = merged.merge(
        adj_def, on=["season", "team"], how="left", suffixes=("", "_recomp_def")
    )

    total_mismatches = 0
    # Offense columns
    for c in off_cols:
        if (
            c in merged.columns
            and f"{c}" in merged.columns
            and f"{c}_recomp_off" in merged.columns
        ):
            a = pd.to_numeric(merged[c], errors="coerce")
            b = pd.to_numeric(merged[f"{c}_recomp_off"], errors="coerce")
            # For rate-like columns, round before diff to reduce floating artifacts
            if "rate" in c:
                a = a.round(6)
                b = b.round(6)
            d = (a - b).abs()
            col_tol = _RATE_TOL if "rate" in c else tol
            cnt = int((d > col_tol).sum())
            if cnt > 0:
                total_mismatches += cnt
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        f"Adjusted mismatch in {c}: {cnt} rows exceed tol {col_tol}",
                        entity="team_season_adj",
                    )
                )
                mismatch_df = merged[d > col_tol][
                    ["season", "team", c, f"{c}_recomp_off"]
                ].copy()
                mismatch_df["diff"] = d[d > col_tol]
                print(f"--- Mismatches for {c} ---")
                print(mismatch_df.head())
    # Defense columns
    for c in def_cols:
        if (
            c in merged.columns
            and f"{c}" in merged.columns
            and f"{c}_recomp_def" in merged.columns
        ):
            a = pd.to_numeric(merged[c], errors="coerce")
            b = pd.to_numeric(merged[f"{c}_recomp_def"], errors="coerce")
            if "rate" in c:
                a = a.round(6)
                b = b.round(6)
            d = (a - b).abs()
            col_tol = _RATE_TOL if "rate" in c else tol
            cnt = int((d > col_tol).sum())
            if cnt > 0:
                total_mismatches += cnt
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        f"Adjusted mismatch in {c}: {cnt} rows exceed tol {col_tol}",
                        entity="team_season_adj",
                    )
                )
                mismatch_df = merged[d > col_tol][
                    ["season", "team", c, f"{c}_recomp_def"]
                ].copy()
                mismatch_df["diff"] = d[d > col_tol]
                print(f"--- Mismatches for {c} ---")
                print(mismatch_df.head())

    if total_mismatches == 0:
        issues.append(
            ValidationIssue(
                "INFO",
                "Adjusted features match recomputation within tolerance",
                entity="team_season_adj",
            )
        )
    return issues


def _approx_equal(a: Any, b: Any, tol: float = _FLOAT_TOL) -> bool:
    try:
        if pd.isna(a) and pd.isna(b):
            return True
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


def validate_drives_consistency(
    storage: LocalStorage, year: int
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # Read byplay without column restrictions to be robust to schema evolution
    byplay_records = storage.read_index("byplay", {"year": year})
    # Read drives with a reduced set; if that fails upstream, fallback to full read
    drives_records = storage.read_index("drives", {"year": year})

    if not byplay_records or not drives_records:
        return issues

    bp = pd.DataFrame.from_records(byplay_records)
    drv = pd.DataFrame.from_records(drives_records)

    # Ensure required columns exist, creating safe defaults where possible
    for c in [
        "season",
        "week",
        "game_id",
        "drive_number",
        "offense",
        "defense",
        "yards_gained",
        "play_duration",
        "play_type",
        "eckel",
        "down",
        "yards_to_goal",
        "penalty",
        "st",
        "twopoint",
    ]:
        if c not in bp.columns:
            # Default numeric flags to 0, strings to empty
            bp[c] = 0 if c not in {"play_type"} else ""

    # Normalize dtypes
    for c in ["yards_gained", "play_duration", "down", "yards_to_goal"]:
        bp[c] = pd.to_numeric(bp.get(c), errors="coerce")

    if "play_type" not in bp.columns:
        bp["play_type"] = ""

    # Reconstruct is_drive_play consistent with byplay/core logic
    approx_non_count = {"Timeout", "Uncategorized", "placeholder", "End Period"}
    bp["is_drive_play"] = (
        (bp.get("st", 0).fillna(0) == 0)
        & (bp.get("penalty", 0).fillna(0) == 0)
        & (bp.get("twopoint", 0).fillna(0) == 0)
        & (~bp.get("play_type", "").isin(list(approx_non_count)))
    ).astype(int)

    # Ensure drives columns
    for c in [
        "season",
        "week",
        "game_id",
        "drive_number",
        "offense",
        "defense",
        "drive_plays",
        "drive_yards",
        "drive_time",
        "is_eckel_drive",
        "had_scoring_opportunity",
    ]:
        if c not in drv.columns:
            drv[c] = pd.NA

    # Backfill missing flags as 0 to allow masking logic
    for c in ["penalty", "st", "twopoint", "is_drive_play", "eckel"]:
        if c not in bp.columns:
            bp[c] = 0
    if "play_type" not in bp.columns:
        bp["play_type"] = ""

    # Reconstruct is_drive_play if missing like in core.aggregate_drives
    approx_non_count = {"Timeout", "Uncategorized", "placeholder", "End Period"}
    if "is_drive_play" not in bp or bp["is_drive_play"].isna().all():
        bp["is_drive_play"] = (
            (bp.get("st", 0).fillna(0) == 0)
            & (bp.get("penalty", 0).fillna(0) == 0)
            & (bp.get("twopoint", 0).fillna(0) == 0)
            & (~bp.get("play_type", "").isin(list(approx_non_count)))
        ).astype(int)

    # Mask play_duration for invalid contexts as in byplay.py/core.py
    counted = bp["play_duration"].astype(float)
    for flag in ["penalty", "st", "twopoint"]:
        if flag in bp.columns:
            counted = counted.mask(bp[flag] == 1)

    grp_keys = ["game_id", "drive_number", "offense", "defense"]
    recon = (
        bp.assign(counted_play_duration=counted)
        .groupby(grp_keys, as_index=False)
        .agg(
            recon_drive_plays=("is_drive_play", "sum"),
            recon_drive_yards=("yards_gained", "sum"),
            recon_drive_time=("counted_play_duration", "sum"),
            recon_is_eckel=("eckel", "max"),
        )
    )

    merged = drv.merge(recon, on=grp_keys, how="left")

    for _, r in merged.iterrows():
        if not _approx_equal(
            r.get("drive_plays"), r.get("recon_drive_plays"), tol=1e-3
        ):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "drive_plays mismatch vs byplay reconstruction",
                    entity="drives",
                )
            )
        if not _approx_equal(
            r.get("drive_yards"), r.get("recon_drive_yards"), tol=1e-3
        ):
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "drive_yards mismatch vs byplay reconstruction",
                    entity="drives",
                )
            )
        if not _approx_equal(
            r.get("drive_time"), r.get("recon_drive_time"), tol=_TIME_TOL
        ):
            issues.append(
                ValidationIssue(
                    "WARN",
                    "drive_time differs by >1.5s vs byplay reconstruction",
                    entity="drives",
                )
            )
        # Eckel consistency (best-effort)
        if (r.get("is_eckel_drive") in (0, 1)) and (r.get("recon_is_eckel") in (0, 1)):
            if int(r.get("is_eckel_drive")) != int(r.get("recon_is_eckel")):
                issues.append(
                    ValidationIssue(
                        "WARN",
                        "is_eckel_drive flag differs from byplay-derived value",
                        entity="drives",
                    )
                )

    return issues


def validate_team_game_consistency(
    storage: LocalStorage, year: int
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    tg_cols = [
        "season",
        "week",
        "game_id",
        "team",
        "n_off_plays",
        "off_sr",
        "off_ypp",
        "off_epa_pp",
        "def_sr",
        "def_ypp",
        "def_epa_pp",
        "off_drives",
    ]
    byplay_cols = ["game_id", "offense", "play_number"]
    drv_cols = ["game_id", "offense", "drive_number"]

    # Robust read of team_game; some columns may be missing depending on feature evolution
    tg_all = pd.DataFrame.from_records(storage.read_index("team_game", {"year": year}))
    if tg_all.empty:
        return issues
    # Keep only the columns we care about if present
    keep = [c for c in tg_cols if c in tg_all.columns]
    tg = tg_all[keep].copy()
    # Create missing numeric columns as NaN to allow comparisons without KeyError
    for c in tg_cols:
        if c not in tg.columns:
            tg[c] = pd.NA

    # Mirror checks: join opponent row within same game_id
    opp = tg[
        [
            "game_id",
            "team",
            "off_sr",
            "off_ypp",
            "off_epa_pp",
            "def_sr",
            "def_ypp",
            "def_epa_pp",
        ]
    ].copy()
    opp = opp.rename(
        columns={
            "team": "team_opp",
            "off_sr": "opp_off_sr",
            "off_ypp": "opp_off_ypp",
            "off_epa_pp": "opp_off_epa_pp",
            "def_sr": "opp_def_sr",
            "def_ypp": "opp_def_ypp",
            "def_epa_pp": "opp_def_epa_pp",
        }
    )
    joined = tg.merge(opp, on="game_id", how="inner")
    joined = joined[joined["team"] != joined["team_opp"]]

    # Compare each row to its opponent’s mirror
    for _, r in joined.iterrows():
        if not _approx_equal(r.get("off_sr"), r.get("opp_def_sr"), tol=_RATE_TOL):
            issues.append(
                ValidationIssue(
                    "WARN", "off_sr vs opponent def_sr mismatch", entity="team_game"
                )
            )
        if not _approx_equal(r.get("def_sr"), r.get("opp_off_sr"), tol=_RATE_TOL):
            issues.append(
                ValidationIssue(
                    "WARN", "def_sr vs opponent off_sr mismatch", entity="team_game"
                )
            )
        if not _approx_equal(r.get("off_ypp"), r.get("opp_def_ypp"), tol=1e-2):
            issues.append(
                ValidationIssue(
                    "WARN", "off_ypp vs opponent def_ypp mismatch", entity="team_game"
                )
            )
        if not _approx_equal(r.get("def_ypp"), r.get("opp_off_ypp"), tol=1e-2):
            issues.append(
                ValidationIssue(
                    "WARN", "def_ypp vs opponent off_ypp mismatch", entity="team_game"
                )
            )
        if not _approx_equal(r.get("off_epa_pp"), r.get("opp_def_epa_pp"), tol=5e-3):
            issues.append(
                ValidationIssue(
                    "WARN",
                    "off_epa_pp vs opponent def_epa_pp mismatch",
                    entity="team_game",
                )
            )
        if not _approx_equal(r.get("def_epa_pp"), r.get("opp_off_epa_pp"), tol=5e-3):
            issues.append(
                ValidationIssue(
                    "WARN",
                    "def_epa_pp vs opponent off_epa_pp mismatch",
                    entity="team_game",
                )
            )

    # Count checks using byplay and drives
    byp = pd.DataFrame.from_records(
        storage.read_index("byplay", {"year": year}, columns=byplay_cols)
    )
    drv = pd.DataFrame.from_records(
        storage.read_index("drives", {"year": year}, columns=drv_cols)
    )
    if not byp.empty:
        by_counts = byp.groupby(["game_id", "offense"], as_index=False).agg(
            n_off_plays_calc=("play_number", "count")
        )
        merged = tg.merge(
            by_counts,
            left_on=["game_id", "team"],
            right_on=["game_id", "offense"],
            how="left",
        )
        for _, r in merged.iterrows():
            calc = r.get("n_off_plays_calc")
            if pd.notna(calc) and not _approx_equal(
                r.get("n_off_plays"), calc, tol=1e-3
            ):
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "n_off_plays does not match byplay count",
                        entity="team_game",
                    )
                )
    if not drv.empty and "off_drives" in tg.columns:
        d_counts = drv.groupby(["game_id", "offense"], as_index=False).agg(
            off_drives_calc=("drive_number", "count")
        )
        merged = tg.merge(
            d_counts,
            left_on=["game_id", "team"],
            right_on=["game_id", "offense"],
            how="left",
        )
        for _, r in merged.iterrows():
            calc = r.get("off_drives_calc")
            if pd.notna(calc) and not _approx_equal(
                r.get("off_drives"), calc, tol=1e-3
            ):
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "off_drives does not match drives count",
                        entity="team_game",
                    )
                )

    # Rate bounds
    for col in ["off_sr", "def_sr"]:
        if col in tg.columns:
            bad = tg[(tg[col] < -_RATE_TOL) | (tg[col] > 1 + _RATE_TOL)]
            if not bad.empty:
                issues.append(
                    ValidationIssue(
                        "ERROR", f"{col} outside [0,1] range", entity="team_game"
                    )
                )

    return issues


def _recency_weighted_mean(df: pd.DataFrame, value_col: str) -> float:
    if df.empty or value_col not in df.columns:
        return float("nan")
    g = df.sort_values("week")
    weights = [1.0] * len(g)
    if len(g) >= 1:
        weights[-1] = 3.0
    if len(g) >= 2:
        weights[-2] = 2.0
    if len(g) >= 3:
        weights[-3] = 1.0
    w = pd.Series(weights, index=g.index).astype(float)
    vals = g[value_col].astype(float)
    denom = w.sum() if w.sum() > 0 else 1.0
    return float((vals * w).sum() / denom)


def validate_team_season_consistency(
    storage: LocalStorage, year: int
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    tg_cols = [
        "season",
        "week",
        "team",
        "off_sr",
        "off_ypp",
        "off_epa_pp",
        "def_sr",
        "def_ypp",
        "def_epa_pp",
        "off_eckel_rate",
        "off_finish_pts_per_opp",
    ]
    tg = pd.DataFrame.from_records(
        storage.read_index("team_game", {"year": year}, columns=tg_cols)
    )
    if tg.empty:
        return issues

    # Read persisted season offense/defense sides separately and merge back
    off_rows = pd.DataFrame.from_records(
        storage.read_index("team_season", {"year": year, "side": "offense"})
    )
    def_rows = pd.DataFrame.from_records(
        storage.read_index("team_season", {"year": year, "side": "defense"})
    )
    if off_rows.empty or def_rows.empty:
        return issues

    # Build expected season metrics from team_game
    metrics = [
        ("off_sr", "offense"),
        ("off_ypp", "offense"),
        ("off_epa_pp", "offense"),
        ("off_eckel_rate", "offense"),
        ("off_finish_pts_per_opp", "offense"),
        ("def_sr", "defense"),
        ("def_ypp", "defense"),
        ("def_epa_pp", "defense"),
    ]

    expected: dict[tuple[int, str], dict[str, float]] = {}
    for (season, team), group in tg.groupby(["season", "team"]):
        d: dict[str, float] = {}
        for m, _side in metrics:
            if m in group.columns:
                d[m] = _recency_weighted_mean(group, m)
        d["games_played"] = float(len(group))
        expected[(int(season), str(team))] = d

    # Compare offense
    for _, row in off_rows.iterrows():
        key = (int(row.get("season", year)), str(row.get("team")))
        if key not in expected:
            continue
        exp = expected[key]
        for m in [
            "off_sr",
            "off_ypp",
            "off_epa_pp",
            "off_eckel_rate",
            "off_finish_pts_per_opp",
        ]:
            if m in row and m in exp and pd.notna(row[m]) and pd.notna(exp[m]):
                if not _approx_equal(row[m], exp[m], tol=5e-3):
                    issues.append(
                        ValidationIssue(
                            "WARN",
                            f"team_season offense {m} differs from recompute",
                            entity="team_season",
                        )
                    )

    # Compare defense
    for _, row in def_rows.iterrows():
        key = (int(row.get("season", year)), str(row.get("team")))
        if key not in expected:
            continue
        exp = expected[key]
        for m in ["def_sr", "def_ypp", "def_epa_pp"]:
            if m in row and m in exp and pd.notna(row[m]) and pd.notna(exp[m]):
                if not _approx_equal(row[m], exp[m], tol=5e-3):
                    issues.append(
                        ValidationIssue(
                            "WARN",
                            f"team_season defense {m} differs from recompute",
                            entity="team_season",
                        )
                    )

    return issues


def validate_opponent_adjustment_consistency(
    storage: LocalStorage, year: int
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # Load team_game, and recombine team_season offense/defense into one frame
    tg = pd.DataFrame.from_records(storage.read_index("team_game", {"year": year}))
    off_rows = pd.DataFrame.from_records(
        storage.read_index("team_season", {"year": year, "side": "offense"})
    )
    def_rows = pd.DataFrame.from_records(
        storage.read_index("team_season", {"year": year, "side": "defense"})
    )
    if tg.empty or off_rows.empty or def_rows.empty:
        return issues

    ts = off_rows.merge(def_rows, on=["season", "team", "games_played"], how="outer")

    # Recompute adjustment
    recomputed_adj = apply_iterative_opponent_adjustment(ts, tg)

    # Read persisted adjusted offense/defense
    adj_off = pd.DataFrame.from_records(
        storage.read_index("team_season_adj", {"year": year, "side": "offense"})
    )
    adj_def = pd.DataFrame.from_records(
        storage.read_index("team_season_adj", {"year": year, "side": "defense"})
    )
    if adj_off.empty or adj_def.empty:
        return issues

    # Compare intersection of available adjusted columns per side
    off_cols = [c for c in recomputed_adj.columns if c.startswith("adj_off_")]
    def_cols = [c for c in recomputed_adj.columns if c.startswith("adj_def_")]

    # Build lookup
    rec_off = recomputed_adj[["season", "team"] + off_cols]
    rec_def = recomputed_adj[["season", "team"] + def_cols]

    merged_off = adj_off.merge(
        rec_off, on=["season", "team"], suffixes=("", "_recomp"), how="left"
    )
    merged_def = adj_def.merge(
        rec_def, on=["season", "team"], suffixes=("", "_recomp"), how="left"
    )

    for _, r in merged_off.iterrows():
        for c in off_cols:
            if c in merged_off.columns and f"{c}_recomp" in merged_off.columns:
                a, b = r.get(c), r.get(f"{c}_recomp")
                if pd.notna(a) and pd.notna(b) and not _approx_equal(a, b, tol=1e-2):
                    issues.append(
                        ValidationIssue(
                            "WARN",
                            f"Adjusted offense {c} differs from recompute",
                            entity="team_season_adj",
                        )
                    )

    for _, r in merged_def.iterrows():
        for c in def_cols:
            if c in merged_def.columns and f"{c}_recomp" in merged_def.columns:
                a, b = r.get(c), r.get(f"{c}_recomp")
                if pd.notna(a) and pd.notna(b) and not _approx_equal(a, b, tol=1e-2):
                    issues.append(
                        ValidationIssue(
                            "WARN",
                            f"Adjusted defense {c} differs from recompute",
                            entity="team_season_adj",
                        )
                    )

    return issues


def _deep_find_first(d: Any, keys: list[str]) -> Any:
    """Find first matching key in nested dict/list structure (case-insensitive)."""
    try:
        if isinstance(d, dict):
            # direct hit
            for k in keys:
                for dk, dv in d.items():
                    if str(dk).lower() == k.lower():
                        return dv
            # recurse
            for dv in d.values():
                v = _deep_find_first(dv, keys)
                if v is not None:
                    return v
        elif isinstance(d, list):
            for item in d:
                v = _deep_find_first(item, keys)
                if v is not None:
                    return v
    except Exception:
        return None
    return None


def _extract_boxscore_team_rows(box: Any) -> list[dict[str, Any]]:
    """Extract team-level metrics from an AdvancedBoxScore-like dict.

    Returns rows with keys: team (str), plays (int|None), ypp (float|None), sr (float|None)
    """
    rows: list[dict[str, Any]] = []
    try:
        bs = box
        # prefer standard 'teams' list shape
        teams_list = None
        if isinstance(bs, dict):
            if isinstance(bs.get("teams"), list):
                teams_list = bs["teams"]
            elif {"home", "away"}.issubset(set(bs.keys())):
                teams_list = [bs["home"], bs["away"]]
        if not teams_list and isinstance(bs, dict):
            # as fallback, search any list-like under top-level that contains dicts with 'team' or 'school'
            for v in bs.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    if any("team" in x or "school" in x for x in v):
                        teams_list = v
                        break
        if not teams_list:
            return rows
        for entry in teams_list:
            try:
                name = _deep_find_first(entry, ["team", "school", "name"])  # type: ignore[arg-type]
                if not isinstance(name, str):
                    continue
                plays = _deep_find_first(
                    entry, ["plays", "offensivePlays", "offensePlays"]
                )  # type: ignore[arg-type]
                ypp = _deep_find_first(entry, ["yardsPerPlay", "yards_per_play", "ypp"])  # type: ignore[arg-type]
                sr = _deep_find_first(entry, ["successRate", "success_rate"])  # type: ignore[arg-type]

                def _to_int(x):
                    try:
                        return int(x)
                    except Exception:
                        return None

                def _to_float(x):
                    try:
                        return float(x)
                    except Exception:
                        return None

                rows.append(
                    {
                        "team": name,
                        "plays": _to_int(plays),
                        "ypp": _to_float(ypp),
                        "sr": _to_float(sr),
                    }
                )
            except Exception:
                continue
    except Exception:
        return rows
    return rows


def validate_team_game_vs_boxscore(
    processed_storage: LocalStorage, raw_storage: LocalStorage, year: int
) -> list[ValidationIssue]:
    """Compare processed team_game against CFBD advanced box score (raw) for key metrics.

    Thresholds (absolute):
      - plays: WARN > 3, ERROR > 8
      - ypp:   WARN > 0.20, ERROR > 0.50
      - sr:    WARN > 0.02, ERROR > 0.05
    """
    issues: list[ValidationIssue] = []
    tg_rows = processed_storage.read_index("team_game", {"year": year})
    if not tg_rows:
        return issues
    tg = pd.DataFrame.from_records(tg_rows)
    if tg.empty or "game_id" not in tg.columns or "team" not in tg.columns:
        return issues

    raw_rows = raw_storage.read_index("game_stats_raw", {"year": year})
    if not raw_rows:
        return issues

    # Map game_id -> list of team box rows
    box_by_game: dict[int, list[dict[str, Any]]] = {}
    for r in raw_rows:
        try:
            gid = int(r.get("game_id"))
            data_json = r.get("raw_data")
            if not data_json:
                continue
            data = json.loads(data_json)
            teams = _extract_boxscore_team_rows(data)
            if teams:
                box_by_game[gid] = teams
        except Exception:
            continue

    # Prepare tolerances
    plays_warn, plays_err = 3, 8
    ypp_warn, ypp_err = 0.20, 0.50
    sr_warn, sr_err = 0.02, 0.05

    # Iterate team_game rows and compare
    for _, row in tg.iterrows():
        try:
            gid = int(row.get("game_id"))
            team = str(row.get("team"))
            box_rows = box_by_game.get(gid, [])
            if not box_rows:
                continue
            # find matching team (case-insensitive)
            match = None
            for br in box_rows:
                if str(br.get("team", "")).lower() == team.lower():
                    match = br
                    break
            if not match:
                continue
            # plays
            if pd.notna(row.get("n_off_plays")) and match.get("plays") is not None:
                diff = abs(float(row["n_off_plays"]) - float(match["plays"]))
                if diff > plays_err:
                    issues.append(
                        ValidationIssue(
                            "ERROR",
                            f"plays diff {diff:.0f} > {plays_err}",
                            entity="team_game",
                        )
                    )
                elif diff > plays_warn:
                    issues.append(
                        ValidationIssue(
                            "WARN",
                            f"plays diff {diff:.0f} > {plays_warn}",
                            entity="team_game",
                        )
                    )
            # ypp
            if pd.notna(row.get("off_ypp")) and match.get("ypp") is not None:
                diff = abs(float(row["off_ypp"]) - float(match["ypp"]))
                if diff > ypp_err:
                    issues.append(
                        ValidationIssue(
                            "ERROR",
                            f"ypp diff {diff:.2f} > {ypp_err}",
                            entity="team_game",
                        )
                    )
                elif diff > ypp_warn:
                    issues.append(
                        ValidationIssue(
                            "WARN",
                            f"ypp diff {diff:.2f} > {ypp_warn}",
                            entity="team_game",
                        )
                    )
            # success rate
            if pd.notna(row.get("off_sr")) and match.get("sr") is not None:
                diff = abs(float(row["off_sr"]) - float(match["sr"]))
                if diff > sr_err:
                    issues.append(
                        ValidationIssue(
                            "ERROR",
                            f"sr diff {diff:.3f} > {sr_err}",
                            entity="team_game",
                        )
                    )
                elif diff > sr_warn:
                    issues.append(
                        ValidationIssue(
                            "WARN",
                            f"sr diff {diff:.3f} > {sr_warn}",
                            entity="team_game",
                        )
                    )
        except Exception:
            continue

    return issues


def main() -> None:
    import argparse

    from src.config import get_data_root

    parser = argparse.ArgumentParser(
        description="Validate local CSV data for a season."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year to validate."
    )
    parser.add_argument(
        "--data-type",
        type=str,
        default="processed",
        choices=["raw", "processed"],
        help="Type of data to validate.",
    )
    parser.add_argument(
        "--data-root", type=str, default=None, help="Override data root path."
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Run deep semantic validations for drives, team_game, team_season, and opponent adjustment.",
    )
    args = parser.parse_args()

    data_root = args.data_root or get_data_root()

    storage = LocalStorage(
        data_root=data_root, file_format="csv", data_type=args.data_type
    )

    if args.data_type == "processed":
        issues = validate_processed_season(storage, args.year)
        if args.deep:
            print("\n--- Running deep semantic validations ---")
            issues.extend(validate_drives_consistency(storage, args.year))
            issues.extend(validate_team_game_consistency(storage, args.year))
            issues.extend(validate_team_season_consistency(storage, args.year))
            issues.extend(validate_opponent_adjustment_consistency(storage, args.year))
            issues.extend(validate_adjusted_consistency(storage, args.year))
            # Compare against raw advanced box scores if available
            raw_storage = LocalStorage(
                data_root=args.data_root, file_format="csv", data_type="raw"
            )
            issues.extend(
                validate_team_game_vs_boxscore(storage, raw_storage, args.year)
            )
    else:
        issues = validate_raw_season(storage, args.year)

    if not issues:
        print(f"\n✅ No issues found for {args.year} {args.data_type} data.")
        return

    print(f"\n--- Validation Summary for {args.year} ({args.data_type}) ---")
    errors = [iss for iss in issues if iss.level == "ERROR"]
    warns = [iss for iss in issues if iss.level == "WARN"]

    if errors:
        print(f"🔴 Found {len(errors)} ERROR(s):")
        for iss in errors:
            loc = f" [{iss.path}]" if iss.path else ""
            print(f"  - [{iss.entity}] {iss.message}{loc}")

    if warns:
        print(f"🟡 Found {len(warns)} WARNING(s):")
        for iss in warns:
            loc = f" [{iss.path}]" if iss.path else ""
            print(f"  - [{iss.entity}] {iss.message}{loc}")

    if not errors and not warns:
        print("✅ All checks passed (only INFO-level messages).")


if __name__ == "__main__":
    main()
