#!/usr/bin/env python3
"""
Publish weekly predictions from CSV into the Neon Postgres database
that powers the Vercel web app.

Reads: an ephemeral working CSV, or the active immutable run manifest in R2.
Writes: immutable prediction_runs/predictions plus compatibility games rows;
        activation updates current_week in the same database transaction.

Requires DATABASE_URL environment variable (Neon connection string).

Usage:
    PYTHONPATH=. uv run python scripts/pipeline/publish_to_db.py \\
        --year 2026 --week 1
    PYTHONPATH=. uv run python scripts/pipeline/publish_to_db.py \\
        --year 2026 --week 1 --config conf/weekly_bets/v2_champion.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from cks_picks_cfb.artifacts import (
    local_prediction_path,
    prediction_run_manifest_path,
    read_csv_artifact,
    read_json_artifact,
    read_verified_csv_artifact,
)
from cks_picks_cfb.ops.lease import assert_active_pipeline_lease

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "psycopg not installed. Run: uv sync  (psycopg[binary] is in pyproject.toml)"
    ) from exc


# ---------------------------------------------------------------------------
# Team name normalization (must match publish_picks.py / web app)
# ---------------------------------------------------------------------------

TEAM_LOGO_MAP = {
    "Sam Houston": "Sam Houston State",
    "UL Monroe": "Louisiana Monroe",
    "Massachusetts": "UMass",
    "App State": "Appalachian State",
    "San José State": "San Jose State",
    "UTSA": "UT San Antonio",
    "Hawai'i": "Hawai_i",
    "Hawaii": "Hawai_i",
    "Hawai i": "Hawai_i",
    "UConn": "Connecticut",
    "Southern Miss": "Southern Mississippi",
    "Texas A&M": "Texas A&M",
}


# ---------------------------------------------------------------------------
# Prediction row parsing
# ---------------------------------------------------------------------------


def _safe_float(val) -> float | None:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
        out = float(val)
        return None if pd.isna(out) else out
    except (TypeError, ValueError):
        return None


def _safe_bool(val, *, default: bool = True) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in {"1", "true", "t", "yes", "y"}:
        return True
    if s in {"0", "false", "f", "no", "n"}:
        return False
    return default


def _derive_lean(row: pd.Series) -> tuple[str | None, float | None]:
    """
    Return (spread_lean, edge_spread) for a prediction row.

    predicted_spread  = predicted HOME margin (+home wins, -home loses)
    home_team_spread_line = market line on home team (+home dog, -home favorite)

    Lean: bet HOME if predicted_spread > -home_team_spread_line else AWAY
    Edge: |predicted_spread + home_team_spread_line|
    """
    pred = _safe_float(row.get("Spread Prediction"))
    line = _safe_float(row.get("home_team_spread_line"))
    if pred is None or line is None:
        return None, None
    lean = "home" if pred > -line else "away"
    edge = abs(pred + line)
    return lean, edge


def _derive_total_lean(row: pd.Series) -> tuple[str | None, float | None]:
    pred = _safe_float(row.get("Total Prediction"))
    line = _safe_float(row.get("total_line"))
    if pred is None or line is None:
        return None, None
    lean = "over" if pred > line else "under"
    edge = abs(pred - line)
    return lean, edge


def prepare_predictions(df: pd.DataFrame) -> pd.DataFrame:
    """Add canonical derived columns to a predictions dataframe."""
    # Coerce numeric columns
    for col in [
        "home_team_spread_line",
        "total_line",
        "Spread Prediction",
        "Total Prediction",
        "predicted_spread_std_dev",
        "predicted_total_std_dev",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Parse start date
    if "start_date" in df.columns:
        df["start_date_dt"] = pd.to_datetime(
            df["start_date"], utc=True, errors="coerce"
        )
    else:
        df["start_date_dt"] = pd.NaT

    # Derive leans + edges (drop any CSV-provided edge columns first so derived
    # values are the single source of truth and don't collide on concat).
    for col in ("edge_spread", "edge_total"):
        if col in df.columns:
            df = df.drop(columns=[col])

    lean_edge = df.apply(_derive_lean, axis=1, result_type="expand")
    lean_edge.columns = ["spread_lean", "edge_spread"]
    df = pd.concat([df, lean_edge], axis=1)

    total_lean_edge = df.apply(_derive_total_lean, axis=1, result_type="expand")
    total_lean_edge.columns = ["total_lean", "edge_total"]
    df = pd.concat([df, total_lean_edge], axis=1)

    return df


def load_predictions(csv_path: Path) -> pd.DataFrame:
    """Load the weekly predictions CSV and add derived columns."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Predictions CSV not found: {csv_path}")

    return prepare_predictions(pd.read_csv(csv_path))


def load_predictions_artifact(artifact_path: str) -> pd.DataFrame:
    """Load predictions from durable storage and add derived columns."""
    return prepare_predictions(read_csv_artifact(artifact_path))


# ---------------------------------------------------------------------------
# Postgres upsert
# ---------------------------------------------------------------------------

UPSERT_SQL = """
INSERT INTO games (
    game_id, season, week, start_date,
    home_team, away_team,
    home_team_spread_line, total_line,
    predicted_spread, predicted_total,
    predicted_spread_std_dev, predicted_total_std_dev,
    spread_lean, total_lean, edge_spread, edge_total,
    high_confidence, source_config, system_name, model_id,
    inserted_at, updated_at
) VALUES (
    %(game_id)s, %(season)s, %(week)s, %(start_date)s,
    %(home_team)s, %(away_team)s,
    %(home_team_spread_line)s, %(total_line)s,
    %(predicted_spread)s, %(predicted_total)s,
    %(predicted_spread_std_dev)s, %(predicted_total_std_dev)s,
    %(spread_lean)s, %(total_lean)s, %(edge_spread)s, %(edge_total)s,
    %(high_confidence)s, %(source_config)s, %(system_name)s, %(model_id)s,
    NOW(), NOW()
)
ON CONFLICT (game_id) DO UPDATE SET
    season = EXCLUDED.season,
    week = EXCLUDED.week,
    start_date = EXCLUDED.start_date,
    home_team = EXCLUDED.home_team,
    away_team = EXCLUDED.away_team,
    home_team_spread_line = EXCLUDED.home_team_spread_line,
    total_line = EXCLUDED.total_line,
    predicted_spread = EXCLUDED.predicted_spread,
    predicted_total = EXCLUDED.predicted_total,
    predicted_spread_std_dev = EXCLUDED.predicted_spread_std_dev,
    predicted_total_std_dev = EXCLUDED.predicted_total_std_dev,
    spread_lean = EXCLUDED.spread_lean,
    total_lean = EXCLUDED.total_lean,
    edge_spread = EXCLUDED.edge_spread,
    edge_total = EXCLUDED.edge_total,
    high_confidence = EXCLUDED.high_confidence,
    source_config = EXCLUDED.source_config,
    system_name = EXCLUDED.system_name,
    model_id = EXCLUDED.model_id,
    updated_at = NOW()
"""

UPDATE_CURRENT_WEEK_SQL = """
INSERT INTO current_week (id, season, week, active_run_id, updated_at)
VALUES (1, %(season)s, %(week)s, %(run_id)s, NOW())
ON CONFLICT (id) DO UPDATE SET
    season = EXCLUDED.season,
    week = EXCLUDED.week,
    active_run_id = EXCLUDED.active_run_id,
    updated_at = NOW()
"""

INSERT_RUN_SQL = """
INSERT INTO prediction_runs (
    run_id, season, week, state,
    expected_games, predicted_games, lined_games,
    data_as_of, source_config, system_name, model_id,
    code_sha, config_sha, model_bundle_sha256,
    artifact_uri, artifact_sha256, input_dataset_refs, validation,
    published_at
) VALUES (
    %(run_id)s, %(season)s, %(week)s, %(state)s,
    %(expected_games)s, %(predicted_games)s, %(lined_games)s,
    %(data_as_of)s, %(source_config)s, %(system_name)s, %(model_id)s,
    %(code_sha)s, %(config_sha)s, %(model_bundle_sha256)s,
    %(artifact_uri)s, %(artifact_sha256)s, %(input_dataset_refs)s::jsonb,
    %(validation)s::jsonb,
    CASE WHEN %(state)s = 'published' THEN NOW() ELSE NULL END
)
ON CONFLICT (run_id) DO NOTHING
"""

INSERT_PREDICTION_SQL = """
INSERT INTO predictions (
    run_id, game_id,
    home_team_spread_line, total_line,
    predicted_spread, predicted_total,
    predicted_spread_std_dev, predicted_total_std_dev,
    spread_lean, total_lean, edge_spread, edge_total,
    high_confidence, high_confidence_eligible,
    home_completed_games, away_completed_games, regime,
    spread_model_version, total_model_version, market_snapshot_id
) VALUES (
    %(run_id)s, %(game_id)s,
    %(home_team_spread_line)s, %(total_line)s,
    %(predicted_spread)s, %(predicted_total)s,
    %(predicted_spread_std_dev)s, %(predicted_total_std_dev)s,
    %(spread_lean)s, %(total_lean)s, %(edge_spread)s, %(edge_total)s,
    %(high_confidence)s, %(high_confidence_eligible)s,
    %(home_completed_games)s, %(away_completed_games)s, %(regime)s,
    %(spread_model_version)s, %(total_model_version)s, %(market_snapshot_id)s
)
ON CONFLICT (run_id, game_id) DO NOTHING
"""

INSERT_MARKET_SNAPSHOT_SQL = """
INSERT INTO market_snapshots (
    snapshot_id, game_id, captured_at, spread, total,
    spread_rule, total_rule, spread_provider_count, total_provider_count,
    source_quote_ids, policy_version
) VALUES (
    %(market_snapshot_id)s, %(game_id)s, %(market_captured_at)s,
    %(home_team_spread_line)s, %(total_line)s, %(spread_selection_rule)s,
    %(total_selection_rule)s, %(spread_provider_count)s,
    %(total_provider_count)s, %(source_quote_ids)s::jsonb,
    %(market_policy_version)s
)
ON CONFLICT (snapshot_id) DO NOTHING
"""


def _row_to_record(
    row: pd.Series,
    *,
    season: int,
    week: int,
    high_conf_threshold: float,
    source_config: str,
    system_name: str,
    model_id: str,
) -> dict:
    start_dt = row.get("start_date_dt")
    if pd.isna(start_dt):
        start_dt = datetime.now(timezone.utc)
    else:
        start_dt = start_dt.to_pydatetime()

    edge_spread = _safe_float(row.get("edge_spread"))
    eligible = _safe_bool(row.get("high_confidence_eligible"), default=True)
    high_conf = bool(
        eligible and edge_spread is not None and edge_spread >= high_conf_threshold
    )

    home_completed = int(_safe_float(row.get("home_completed_games")) or 0)
    away_completed = int(_safe_float(row.get("away_completed_games")) or 0)
    market_snapshot_id = row.get("market_snapshot_id")
    if pd.isna(market_snapshot_id):
        market_snapshot_id = None
    source_quote_ids = row.get("source_quote_ids", "[]")
    if isinstance(source_quote_ids, str):
        source_quote_ids = json.loads(source_quote_ids)
    if not isinstance(source_quote_ids, list) or not all(
        isinstance(quote_id, str) for quote_id in source_quote_ids
    ):
        raise ValueError("source_quote_ids must be a JSON array of strings")
    market_captured_at = pd.to_datetime(
        row.get("market_captured_at"), utc=True, errors="coerce"
    )
    if pd.isna(market_captured_at):
        market_captured_at = datetime.now(timezone.utc)
    else:
        market_captured_at = market_captured_at.to_pydatetime()
    regime = str(row.get("prediction_regime") or "established")
    if regime not in {
        "preseason",
        "one_game",
        "two_games",
        "three_games",
        "game_1",
        "game_2",
        "game_3",
        "established",
    }:
        raise ValueError(f"Unsupported prediction regime: {regime}")

    return {
        "game_id": int(row["game_id"]),
        "season": season,
        "week": week,
        "start_date": start_dt,
        "home_team": str(row["home_team"]),
        "away_team": str(row["away_team"]),
        "home_team_spread_line": _safe_float(row.get("home_team_spread_line")),
        "total_line": _safe_float(row.get("total_line")),
        "predicted_spread": _safe_float(row.get("Spread Prediction")),
        "predicted_total": _safe_float(row.get("Total Prediction")),
        "predicted_spread_std_dev": _safe_float(row.get("predicted_spread_std_dev")),
        "predicted_total_std_dev": _safe_float(row.get("predicted_total_std_dev")),
        "spread_lean": row.get("spread_lean"),
        "total_lean": row.get("total_lean"),
        "edge_spread": edge_spread,
        "edge_total": _safe_float(row.get("edge_total")),
        "high_confidence": high_conf,
        "high_confidence_eligible": eligible,
        "home_completed_games": home_completed,
        "away_completed_games": away_completed,
        "regime": regime,
        "spread_model_version": row.get("spread_model_version") or model_id,
        "total_model_version": row.get("total_model_version") or model_id,
        "market_snapshot_id": market_snapshot_id,
        "market_captured_at": market_captured_at,
        "market_policy_version": row.get("market_policy_version")
        or "consensus_then_median_v1",
        "spread_selection_rule": row.get("spread_selection_rule"),
        "total_selection_rule": row.get("total_selection_rule"),
        "spread_provider_count": int(
            _safe_float(row.get("spread_provider_count")) or 0
        ),
        "total_provider_count": int(_safe_float(row.get("total_provider_count")) or 0),
        "source_quote_ids": json.dumps(source_quote_ids),
        "source_config": source_config,
        "system_name": system_name,
        "model_id": model_id,
    }


def publish_week(
    df: pd.DataFrame,
    conn_url: str,
    *,
    season: int,
    week: int,
    high_conf_threshold: float,
    source_config: str,
    system_name: str,
    model_id: str,
    update_current: bool,
    run_manifest: dict | None = None,
    state: str = "published",
) -> int:
    """Transactionally insert an immutable run and optionally activate it."""
    if state not in {"preview", "published"}:
        raise ValueError(f"Unsupported initial run state: {state}")
    manifest = dict(run_manifest or {})
    run_id = str(manifest.get("run_id") or f"legacy-{season}-w{week}")
    if df["game_id"].isna().any() or df["game_id"].duplicated().any():
        raise ValueError("Prediction run has missing or duplicate game IDs")
    if manifest:
        if int(manifest.get("row_count", -1)) != len(df):
            raise ValueError(
                "Prediction artifact row count does not match its manifest"
            )
        if int(manifest.get("expected_games", -1)) != len(df):
            raise ValueError("Prediction run does not cover the expected schedule")
        if int(manifest.get("predicted_games", -1)) != len(df):
            raise ValueError("Prediction run has missing model outputs")
        validation = manifest.get("validation", {})
        if validation.get("all_predictions_present") is not True:
            raise ValueError("Prediction run failed output validation")
        if "run_id" in df and set(df["run_id"].astype(str)) != {run_id}:
            raise ValueError("Prediction rows do not match the manifest run ID")
    run_record = {
        "run_id": run_id,
        "season": season,
        "week": week,
        "state": state,
        "expected_games": int(manifest.get("expected_games", len(df))),
        "predicted_games": int(manifest.get("predicted_games", len(df))),
        "lined_games": int(
            manifest.get(
                "lined_games",
                df[["home_team_spread_line", "total_line"]].notna().all(axis=1).sum(),
            )
        ),
        "data_as_of": manifest.get("data_as_of")
        or datetime.now(timezone.utc).isoformat(),
        "source_config": source_config,
        "system_name": system_name,
        "model_id": model_id,
        "code_sha": manifest.get("code_sha"),
        "config_sha": manifest.get("config_sha"),
        "model_bundle_sha256": manifest.get("model_bundle_sha256"),
        "artifact_uri": manifest.get("artifact_uri", "legacy-local"),
        "artifact_sha256": manifest.get("artifact_sha256", "legacy"),
        "input_dataset_refs": json.dumps(manifest.get("input_dataset_refs", [])),
        "validation": json.dumps(manifest.get("validation", {})),
    }
    with psycopg.connect(conn_url) as conn:
        with conn.cursor() as cur:
            assert_active_pipeline_lease(cur)
            cur.execute(
                "SELECT state FROM prediction_runs WHERE run_id = %s", (run_id,)
            )
            existing = cur.fetchone()
            if existing and existing[0] in {"frozen", "scored"}:
                raise RuntimeError(
                    f"Prediction run {run_id} is immutable ({existing[0]})"
                )
            cur.execute(INSERT_RUN_SQL, run_record)
            if existing and existing[0] == "preview" and state == "published":
                cur.execute(
                    """
                    UPDATE prediction_runs
                    SET state = 'published', published_at = NOW()
                    WHERE run_id = %s AND state = 'preview'
                    """,
                    (run_id,),
                )
            count = 0
            for _, row in df.iterrows():
                if pd.isna(row.get("game_id")):
                    continue
                record = _row_to_record(
                    row,
                    season=season,
                    week=week,
                    high_conf_threshold=high_conf_threshold,
                    source_config=source_config,
                    system_name=system_name,
                    model_id=model_id,
                )
                cur.execute(UPSERT_SQL, record)
                if record["market_snapshot_id"]:
                    cur.execute(INSERT_MARKET_SNAPSHOT_SQL, record)
                cur.execute(INSERT_PREDICTION_SQL, {**record, "run_id": run_id})
                count += 1

            if update_current:
                cur.execute(
                    UPDATE_CURRENT_WEEK_SQL,
                    {"season": season, "week": week, "run_id": run_id},
                )
                cur.execute(
                    "INSERT INTO ops.activation_history "
                    "(environment, season, week, run_id, action, metadata) "
                    "VALUES (%s, %s, %s, %s, 'publish', %s::jsonb) "
                    "ON CONFLICT (run_id, action) DO NOTHING",
                    (
                        os.getenv("CFB_ARTIFACT_ENV", "production"),
                        season,
                        week,
                        run_id,
                        json.dumps({"state": state}),
                    ),
                )

            conn.commit()
    return count


def request_site_revalidation() -> None:
    """Trigger signed on-demand revalidation; five-minute ISR remains fallback."""
    url = os.getenv("CFB_REVALIDATION_URL")
    secret = os.getenv("REVALIDATION_SECRET")
    if not url or not secret:
        return
    payload = json.dumps(
        {"timestamp": int(time.time() * 1000), "path": "/"}, separators=(",", ":")
    ).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    response = requests.post(
        url,
        data=payload,
        headers={
            "content-type": "application/json",
            "x-cks-signature": signature,
        },
        timeout=10,
    )
    response.raise_for_status()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_provenance(config_path: Path | None) -> tuple[str, str, str, float]:
    """Read system_name, model_id, source_config, high-conf threshold from yaml.

    Returns (source_config, system_name, model_id, high_conf_threshold).
    """
    default_threshold = 8.0  # mirrors v2_champion.yaml spread_edge_threshold_high_conf
    default_name = "CKsPicks Model"
    default_id = "unknown"

    if config_path is None or not config_path.exists():
        return (
            str(config_path) if config_path else "",
            default_name,
            default_id,
            default_threshold,
        )

    try:
        from omegaconf import OmegaConf

        cfg = OmegaConf.load(config_path)
        name = cfg.get("system_name", default_name)
        mid = cfg.get("model_id", default_id)
        threshold = float(cfg.get("spread_edge_threshold_high_conf", default_threshold))
        return (str(config_path), name, mid, threshold)
    except Exception as exc:
        print(f"WARNING: could not read config {config_path}: {exc}")
        return (str(config_path), default_name, default_id, default_threshold)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Publish weekly predictions from CSV to Neon Postgres."
    )
    parser.add_argument("--year", type=int, required=True, help="Season year")
    parser.add_argument("--week", type=int, required=True, help="Week number")
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Override ephemeral working-copy CSV path.",
    )
    parser.add_argument(
        "--from-artifact",
        action="store_true",
        help="Read predictions from durable storage instead of local working-copy CSV.",
    )
    parser.add_argument(
        "--artifact-path",
        type=str,
        default=None,
        help="Explicit durable prediction CSV path (legacy/backfill only).",
    )
    parser.add_argument(
        "--run-id",
        help="Explicit immutable prediction run ID (required with --from-artifact).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("conf/weekly_bets/v2_champion.yaml"),
        help="Path to weekly_bets YAML (for system_name, model_id, high-conf threshold)",
    )
    parser.add_argument(
        "--no-update-current",
        action="store_true",
        help="Do not update the current_week singleton (useful for backfills)",
    )
    parser.add_argument(
        "--state",
        choices=("preview", "published"),
        default="published",
        help="Initial database run state.",
    )
    args = parser.parse_args()

    conn_url = os.environ.get("DATABASE_URL")
    if not conn_url:
        raise SystemExit(
            "DATABASE_URL not set. Add it to .env (see web/.env.example for format)."
        )

    csv_path = args.csv or local_prediction_path(args.year, args.week)
    run_manifest = None
    if args.from_artifact and not args.artifact_path:
        if not args.run_id:
            raise SystemExit("--run-id is required with --from-artifact")
        manifest_path = prediction_run_manifest_path(args.year, args.week, args.run_id)
        run_manifest = read_json_artifact(manifest_path)
        artifact_path = str(run_manifest["artifact_uri"])
    else:
        artifact_path = args.artifact_path or ""

    source_config, system_name, model_id, high_conf_threshold = _load_provenance(
        args.config
    )

    source = artifact_path if args.from_artifact or args.artifact_path else csv_path
    print(f"Publishing {args.year} week {args.week} from {source}")
    print(f"  source_config       = {source_config}")
    print(f"  system_name         = {system_name}")
    print(f"  model_id            = {model_id}")
    print(f"  high_conf_threshold = {high_conf_threshold} pts")

    if run_manifest:
        df = prepare_predictions(read_verified_csv_artifact(run_manifest))
    elif args.from_artifact or args.artifact_path:
        df = load_predictions_artifact(artifact_path)
    else:
        df = load_predictions(csv_path)
    print(f"  loaded {len(df)} rows from CSV")

    count = publish_week(
        df,
        conn_url,
        season=args.year,
        week=args.week,
        high_conf_threshold=high_conf_threshold,
        source_config=source_config,
        system_name=system_name,
        model_id=model_id,
        update_current=not args.no_update_current,
        run_manifest=run_manifest,
        state=args.state,
    )
    if not args.no_update_current:
        try:
            request_site_revalidation()
        except requests.RequestException as exc:
            print(
                f"WARNING: on-demand revalidation failed; ISR fallback remains: {exc}"
            )
    verb = "Published" if not args.no_update_current else "Backfilled"
    print(
        f"✅ {verb} {count} games for {args.year} week {args.week} "
        f"(current_week {'updated' if not args.no_update_current else 'unchanged'})"
    )


if __name__ == "__main__":
    main()
