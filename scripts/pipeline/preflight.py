#!/usr/bin/env python3
"""Preflight checks for the 2026 weekly operating path."""

from __future__ import annotations

import argparse
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from omegaconf import OmegaConf

from cks_picks_cfb.artifacts import (
    local_prediction_path,
    local_scored_path,
    read_json_artifact,
)
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.data.week_policy import canonical_week_overrides_for_season
from cks_picks_cfb.model_bundle import load_model_artifact, load_model_bundle_v2
from cks_picks_cfb.model_bundle_v3 import load_model_bundle_v3
from cks_picks_cfb.ops.data_audit import latest_gold_feature_ref
from cks_picks_cfb.preseason import snapshot_is_complete

REQUIRED_DB_TABLES = [
    "games",
    "game_results",
    "system_stats",
    "prediction_runs",
    "predictions",
    "prediction_grades",
    "market_snapshots",
    "current_week",
]

REQUIRED_CONTROL_TABLES = [
    "catalog.dataset_versions",
    "catalog.source_captures",
    "ops.pipeline_runs",
    "ops.pipeline_steps",
    "ops.activation_history",
]


def _ok(message: str) -> None:
    print(f"OK  {message}")


def _fail(message: str, failures: list[str]) -> None:
    print(f"ERR {message}")
    failures.append(message)


def _warn(message: str) -> None:
    print(f"WARN {message}")


def check_storage(*, allow_local: bool, failures: list[str]) -> None:
    if not os.getenv("CFBD_API_KEY"):
        _fail("CFBD_API_KEY is not set; weekly ingestion will fail.", failures)

    backend = os.getenv("CFB_STORAGE_BACKEND", "local").lower()
    if backend != "r2" and not allow_local:
        _fail(
            "CFB_STORAGE_BACKEND must be 'r2' for the 2026 MVP weekly path "
            "(use --allow-local for local-only development).",
            failures,
        )
        return

    if backend == "r2":
        environment = os.getenv("CFB_ARTIFACT_ENV", "production").lower()
        prefix = "CFB_R2_PREVIEW" if environment == "preview" else "CFB_R2"
        required = [
            f"{prefix}_BUCKET",
            f"{prefix}_ACCOUNT_ID",
            f"{prefix}_ACCESS_KEY",
            f"{prefix}_SECRET_KEY",
        ]
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            _fail(f"Missing R2 environment variables: {', '.join(missing)}", failures)
            return

    try:
        storage = get_storage()
    except Exception as exc:
        _fail(f"Storage backend failed to initialize: {exc}", failures)
        return

    _ok(f"Storage backend initialized: {storage.describe()}")


def check_database(*, skip_db: bool, failures: list[str]) -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        _fail("DATABASE_URL is not set.", failures)
        return

    if skip_db:
        _warn("Skipping live database schema check (--skip-db).")
        return

    try:
        import psycopg

        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                for table in [*REQUIRED_DB_TABLES, *REQUIRED_CONTROL_TABLES]:
                    cur.execute("SELECT to_regclass(%s)", (table,))
                    exists = cur.fetchone()[0] is not None
                    if not exists:
                        _fail(f"Neon table is missing: {table}", failures)
                cur.execute("SELECT season, week FROM current_week WHERE id = 1")
                row = cur.fetchone()
                if row:
                    _ok(f"Neon current_week row exists: season={row[0]} week={row[1]}")
                else:
                    _fail("Neon current_week singleton row is missing.", failures)
                cur.execute(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'current_week' AND column_name = 'active_run_id'"
                )
                if cur.fetchone() is None:
                    _fail(
                        "Neon schema is missing current_week.active_run_id.", failures
                    )
    except Exception as exc:
        _fail(f"Database schema check failed: {exc}", failures)


def check_deploy_config(failures: list[str]) -> None:
    if Path("vercel.json").exists():
        _fail(
            "Root vercel.json exists; Vercel should use Root Directory = web/.",
            failures,
        )
    else:
        _ok("No root vercel.json; Vercel Root Directory should be web/.")

    if not Path("web/package.json").exists():
        _fail("web/package.json is missing.", failures)
    else:
        _ok("web/package.json found.")


def _parse_as_of(as_of: str) -> tuple[date, datetime]:
    """Return the snapshot date and an inclusive UTC timestamp cutoff."""
    if "T" not in as_of and " " not in as_of:
        try:
            snapshot_date = date.fromisoformat(as_of)
        except ValueError as exc:
            raise ValueError("AS_OF must be an ISO date or timestamp.") from exc
        return snapshot_date, datetime.combine(
            snapshot_date, datetime.max.time(), tzinfo=timezone.utc
        )
    normalized = as_of.removesuffix("Z") + ("+00:00" if as_of.endswith("Z") else "")
    try:
        cutoff = datetime.fromisoformat(normalized)
    except ValueError:
        raise ValueError("AS_OF must be an ISO date or timestamp.") from None
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    return cutoff.date(), cutoff.astimezone(timezone.utc)


def check_model_bundle(config_path: Path, as_of: str, failures: list[str]) -> None:
    if not config_path.is_file():
        _fail(f"Weekly configuration is missing: {config_path}", failures)
        return
    try:
        cfg = OmegaConf.load(config_path)
        storage = get_storage()
        if cfg.get("model_bundle_v2") and cfg.get("model_bundle_v3"):
            raise ValueError(
                "Weekly configuration may select only one model bundle version"
            )
        if cfg.get("model_bundle_v3"):
            bundle = load_model_bundle_v3(cfg.model_bundle_v3, storage=storage)
            bundle_label = "model_bundle_v3"
        elif cfg.get("model_bundle_v2"):
            bundle = load_model_bundle_v2(cfg.model_bundle_v2, storage=storage)
            bundle_label = "model_bundle_v2"
        else:
            bundle = None
            bundle_label = ""
        if bundle is not None:
            for item in bundle.feature_dataset_refs:
                ref = DatasetRef(
                    dataset=str(item["dataset"]),
                    version_id=str(item["version_id"]),
                    schema_version=str(item["schema_version"]),
                    content_sha=str(item["content_sha"]),
                    uri=str(item["uri"]),
                )
                read_dataset(storage, ref)
                manifest_path = ref.uri.rsplit("/", 1)[0] + "/manifest.json"
                manifest = read_json_artifact(manifest_path, storage)
                _, cutoff = _parse_as_of(as_of)
                manifest_as_of = datetime.fromisoformat(str(manifest["as_of"]))
                if manifest_as_of.tzinfo is None:
                    manifest_as_of = manifest_as_of.replace(tzinfo=timezone.utc)
                if manifest_as_of > cutoff:
                    raise ValueError(
                        f"Dataset {ref.version_id} is later than the configured cutoff"
                    )
            _ok(
                f"{bundle_label} verified ({len(bundle.routes)} routes; "
                f"{len(bundle.feature_dataset_refs)} training feature datasets)."
            )
            return
        checksums = []
        for target in ("spread", "total"):
            spec = cfg.models[target]
            required_metadata = (
                "schema_version",
                "feature_version",
                "training_years",
                "code_sha",
                "promotion_report",
            )
            missing_metadata = [key for key in required_metadata if not spec.get(key)]
            if missing_metadata:
                raise ValueError(
                    f"{target} model metadata missing: {', '.join(missing_metadata)}"
                )
            feature_path = Path(str(spec.features))
            if not feature_path.is_file():
                raise FileNotFoundError(
                    f"{target} feature config missing: {feature_path}"
                )
            _, checksum = load_model_artifact(
                spec, storage=storage, require_durable=True
            )
            artifact_manifest = read_json_artifact(
                f"{spec.artifact_uri}.manifest.json", storage
            )
            expected_manifest = {
                "sha256": str(spec.sha256),
                "feature_version": str(spec.feature_version),
                "feature_schema_version": str(spec.schema_version),
                "training_years": str(spec.training_years),
                "code_sha": str(spec.code_sha),
                "promotion_report": str(spec.promotion_report),
            }
            mismatches = [
                key
                for key, expected in expected_manifest.items()
                if str(artifact_manifest.get(key)) != expected
            ]
            if mismatches:
                raise ValueError(
                    f"{target} artifact manifest mismatch: {', '.join(mismatches)}"
                )
            checksums.append(f"{target}={checksum[:12]}")
        _ok(f"Durable model bundle verified ({', '.join(checksums)}).")
    except Exception as exc:
        _fail(f"Durable model bundle check failed: {exc}", failures)


def _prior_only_fallback_is_ready(
    *, year: int, week: int, config_path: Path, failures: list[str]
) -> bool:
    """Verify an explicit prior-only fallback against immutable Gold inputs."""
    cfg = OmegaConf.load(config_path)
    preseason = cfg.get("preseason") or {}
    if preseason.get("input_policy") != "prior_only_fallback":
        return False
    required = [
        str(column) for column in preseason.get("prior_only_required_features", [])
    ]
    if not required:
        _fail("prior_only_fallback has no required feature list.", failures)
        return False
    conn_url = os.getenv("DATABASE_URL")
    if not conn_url:
        _fail("DATABASE_URL is required to validate prior_only_fallback.", failures)
        return False
    try:
        ref = latest_gold_feature_ref(conn_url, mode="model-ready")
        frame = read_dataset(get_storage(), ref)
        season = pd.to_numeric(frame["season"], errors="coerce")
        weeks = pd.to_numeric(frame["week"], errors="coerce")
        rows = frame.loc[(season == year) & (weeks == week)]
        missing_columns = sorted(set(required) - set(rows.columns))
        if missing_columns or rows.empty:
            _fail(
                "prior_only_fallback is missing Week "
                f"{week} Gold inputs: {missing_columns or 'no schedule rows'}",
                failures,
            )
            return False
        incomplete = rows[required].isna().any(axis=1).sum()
        if incomplete:
            _warn(
                "prior_only_fallback has "
                f"{int(incomplete)} rows requiring the frozen model imputer; "
                "they must remain display-only."
            )
    except Exception as exc:
        _fail(f"prior_only_fallback validation failed: {exc}", failures)
        return False
    _warn("Using explicit prior_only_fallback; high confidence must remain disabled.")
    return True


def check_week_data(
    year: int, week: int, as_of: str, config_path: Path, failures: list[str]
) -> None:
    try:
        snapshot_date, _ = _parse_as_of(as_of)
    except ValueError as exc:
        _fail(str(exc), failures)
        return
    try:
        storage = get_storage()
        teams = storage.read_index("raw/teams", {"year": year})
        games = storage.read_index("raw/games", {"year": year})
        canonical_week = canonical_week_overrides_for_season(year)
        fbs = {
            str(row.get("school"))
            for row in teams
            if str(row.get("classification", "")).lower() == "fbs"
        }
        week_games = [
            row
            for row in games
            if canonical_week.get(
                int(row.get("id", row.get("game_id", -1))),
                int(row.get("week", -1)),
            )
            == week
            and row.get("home_team") in fbs
            and row.get("away_team") in fbs
        ]
        if not week_games:
            _fail(f"No FBS-vs-FBS games found for {year} week {week}.", failures)
        else:
            game_ids = [row.get("id") for row in week_games]
            if any(game_id is None for game_id in game_ids) or len(
                set(game_ids)
            ) != len(game_ids):
                _fail("Schedule has missing or duplicate game IDs.", failures)
            else:
                _ok(f"Schedule has {len(week_games)} unique FBS-vs-FBS games.")
        snapshot_as_of = snapshot_date.isoformat()
        if not snapshot_is_complete(storage, year, snapshot_as_of):
            if not _prior_only_fallback_is_ready(
                year=year, week=week, config_path=config_path, failures=failures
            ):
                _fail(
                    f"Point-in-time preseason snapshot is incomplete: {year}/{snapshot_as_of}",
                    failures,
                )
        else:
            _ok(
                f"Point-in-time preseason snapshot is complete: {year}/{snapshot_as_of}"
            )
    except Exception as exc:
        _fail(f"Week data readiness check failed: {exc}", failures)


def report_artifact_paths(year: int, week: int) -> None:
    print("\nArtifact paths")
    print(f"  local predictions: {local_prediction_path(year, week)}")
    print(
        "  prediction runs: "
        f"artifacts/<environment>/predictions/year={year}/week={week}/run_id=<run_id>/"
    )
    print("  active/frozen authority: Neon prediction_runs/current_week")
    print(f"  local scored: {local_scored_path(year, week)}")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Weekly pipeline preflight checks.")
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument(
        "--as-of", required=True, help="Point-in-time cutoff (ISO date or timestamp)"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("conf/weekly_bets/v2_champion.yaml"),
    )
    parser.add_argument(
        "--allow-local",
        action="store_true",
        help="Allow CFB_STORAGE_BACKEND=local for development checks.",
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip live Neon connection/schema checks.",
    )
    args = parser.parse_args()

    failures: list[str] = []
    print(f"Preflight for {args.year} week {args.week}")
    check_storage(allow_local=args.allow_local, failures=failures)
    check_database(skip_db=args.skip_db, failures=failures)
    check_deploy_config(failures)
    check_model_bundle(args.config, args.as_of, failures)
    check_week_data(args.year, args.week, args.as_of, args.config, failures)
    report_artifact_paths(args.year, args.week)

    if failures:
        print("\nPreflight failed.")
        raise SystemExit(1)

    print("\nPreflight passed.")


if __name__ == "__main__":
    main()
