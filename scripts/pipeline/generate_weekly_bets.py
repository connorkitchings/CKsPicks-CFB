import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import mlflow
import numpy as np
import pandas as pd
from omegaconf import OmegaConf

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
from cks_picks_cfb.artifacts import (
    dataframe_csv_bytes,
    local_prediction_path,
    prediction_run_features_path,
    sha256_bytes,
    write_prediction_run,
)
from cks_picks_cfb.data.lake import DatasetRef, read_dataset
from cks_picks_cfb.data.storage import get_storage
from cks_picks_cfb.features.point_in_time import build_point_in_time_matchups
from cks_picks_cfb.features.selector import select_features
from cks_picks_cfb.model_bundle import (
    load_model_artifact,
    load_model_bundle_v2,
    predict_with_model_bundle_v2,
)
from cks_picks_cfb.utils.mlflow_tracking import setup_mlflow


def main():
    parser = argparse.ArgumentParser(description="Generate Weekly Bets")
    parser.add_argument(
        "--config",
        type=str,
        default="conf/weekly_bets/v2_champion.yaml",
        help="Path to config file",
    )
    parser.add_argument(
        "--adjustment-iteration",
        type=int,
        default=2,
        help="Opponent-adjustment iteration to load (default=2; falls back to legacy layout if missing)",
    )
    parser.add_argument("--year", type=int, help="Override year from config")
    parser.add_argument("--week", type=int, help="Override week from config")
    parser.add_argument(
        "--as-of",
        default=None,
        help="Point-in-time data cutoff recorded in the run manifest (ISO-8601).",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Ephemeral working CSV path (defaults under CFB_WORK_ROOT or the OS temp directory).",
    )
    parser.add_argument(
        "--upload-artifact",
        action="store_true",
        help="Also write the predictions CSV to durable storage (R2/S3/local backend).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Immutable run identifier. Defaults to a UTC timestamp plus random suffix.",
    )
    parser.add_argument(
        "--run-state",
        choices=("preview", "published"),
        default="preview",
        help="Initial durable run state.",
    )
    parser.add_argument(
        "--dataset-refs-uri",
        help="Immutable JSON list of exact DatasetRefs selected by orchestration.",
    )
    args = parser.parse_args()

    # Load Config
    cfg = OmegaConf.load(args.config)
    print(f"Loaded config from {args.config}")

    year = args.year if args.year is not None else cfg.year
    week = args.week if args.week is not None else cfg.week
    run_id = args.run_id or (
        f"{year}w{week}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    )
    production_mode = os.getenv("CFB_ARTIFACT_ENV", "production") == "production"
    spread_threshold = cfg.spread_edge_threshold
    # Support dual-threshold betting strategy (default + high confidence)
    spread_threshold_high = cfg.get("spread_edge_threshold_high_conf", spread_threshold)
    total_threshold = cfg.total_edge_threshold

    print(f"Generating bets for {year} Week {week}")
    print(
        f"Thresholds: Spread={spread_threshold} (default), {spread_threshold_high} (high conf), Total={total_threshold}"
    )

    setup_mlflow()
    storage = get_storage()
    routing_bundle = None
    input_dataset_refs: list[dict] = []
    explicit_reader = None
    gold_inference_df = None
    market_snapshots_df = None
    if cfg.get("model_bundle_v2"):
        routing_bundle = load_model_bundle_v2(cfg.model_bundle_v2, storage=storage)
        if args.dataset_refs_uri:
            configured_refs = json.loads(
                storage.read_bytes(args.dataset_refs_uri).decode("utf-8")
            )
        else:
            raise ValueError(
                "model_bundle_v2 inference requires --dataset-refs-uri selected "
                "for this pipeline run"
            )
        ref_map: dict[tuple[str, int], DatasetRef] = {}
        frame_cache: dict[str, list[dict]] = {}
        for item in configured_refs:
            ref = DatasetRef(
                dataset=str(item["dataset"]),
                version_id=str(item["version_id"]),
                schema_version=str(item["schema_version"]),
                content_sha=str(item["content_sha"]),
                uri=str(item["uri"]),
            )
            entity = str(item["entity"])
            ref_year = int(item["year"])
            ref_map[(entity, ref_year)] = ref
            input_dataset_refs.append(
                {
                    "entity": entity,
                    "year": ref_year,
                    "dataset": ref.dataset,
                    "version_id": ref.version_id,
                    "schema_version": ref.schema_version,
                    "content_sha": ref.content_sha,
                    "uri": ref.uri,
                }
            )
            if entity == "point_in_time_matchups" and ref_year == year:
                gold_inference_df = read_dataset(storage, ref)
            if entity == "betting_lines" and ref_year == year:
                market_snapshots_df = read_dataset(storage, ref)

        def explicit_reader(entity: str, ref_year: int):
            key = (entity, ref_year)
            if key not in ref_map:
                raise KeyError(f"No explicit dataset reference for {entity}/{ref_year}")
            ref = ref_map[key]
            if ref.version_id not in frame_cache:
                frame_cache[ref.version_id] = read_dataset(storage, ref).to_dict(
                    "records"
                )
            return frame_cache[ref.version_id]

    # Load Models and Feature Configs
    # Support both MLflow registry (legacy) and local paths (V2)

    # Spread compatibility model is not loaded when the frozen bundle is active.
    if routing_bundle is not None:
        spread_model = None
        spread_model_sha = routing_bundle.manifest_sha256
        spread_feat_path = "conf/features/matchup_v1.yaml"
    elif (
        "models" in cfg
        and "spread" in cfg.models
        and (cfg.models.spread.get("artifact_uri") or cfg.models.spread.get("path"))
    ):
        print("Loading checksummed spread model artifact")
        spread_model, spread_model_sha = load_model_artifact(
            cfg.models.spread, require_durable=production_mode
        )
        spread_feat_path = cfg.models.spread.get(
            "features", "conf/features/ppr_v1.yaml"
        )
    else:
        if production_mode:
            raise ValueError(
                "Production inference requires a checksummed durable spread artifact"
            )
        spread_model_name = cfg.model_registry.spread_models[0]
        print(f"Loading Spread Model from MLflow: {spread_model_name}")
        spread_model = mlflow.pyfunc.load_model(
            f"models:/{spread_model_name}/Production"
        )
        spread_model_sha = hashlib.sha256(
            f"mlflow:{spread_model_name}:Production".encode()
        ).hexdigest()
        spread_feat_path = "conf/features/ppr_v1.yaml"

    print(f"Loading Spread Features from: {spread_feat_path}")
    spread_feat_cfg = OmegaConf.load(spread_feat_path)
    # Check for overrides in main config
    if "features" in cfg:
        # If main config has feature params (e.g. alpha), merge them
        if "params" in cfg.features:
            spread_feat_cfg["params"] = cfg.features.params

    # Total compatibility model is not loaded when the frozen bundle is active.
    if routing_bundle is not None:
        total_model = None
        total_model_sha = routing_bundle.manifest_sha256
        total_feat_path = "conf/features/matchup_v1.yaml"
    elif (
        "models" in cfg
        and "total" in cfg.models
        and (cfg.models.total.get("artifact_uri") or cfg.models.total.get("path"))
    ):
        print("Loading checksummed total model artifact")
        total_model, total_model_sha = load_model_artifact(
            cfg.models.total, require_durable=production_mode
        )
        total_feat_path = cfg.models.total.get(
            "features", "conf/features/standard_v1.yaml"
        )
    else:
        if production_mode:
            raise ValueError(
                "Production inference requires a checksummed durable total artifact"
            )
        total_model_name = cfg.model_registry.total_models[0]
        print(f"Loading Total Model from MLflow: {total_model_name}")
        total_model = mlflow.pyfunc.load_model(f"models:/{total_model_name}/Production")
        total_model_sha = hashlib.sha256(
            f"mlflow:{total_model_name}:Production".encode()
        ).hexdigest()
        total_feat_path = "conf/features/standard_v1.yaml"

    print(f"Loading Total Features from: {total_feat_path}")
    total_feat_cfg = OmegaConf.load(total_feat_path)
    if "features" in cfg and "params" in cfg.features:
        total_feat_cfg["params"] = cfg.features.params

    spread_full_cfg = OmegaConf.create({"features": spread_feat_cfg})
    total_full_cfg = OmegaConf.create({"features": total_feat_cfg})
    model_bundle_sha = (
        routing_bundle.manifest_sha256
        if routing_bundle is not None
        else hashlib.sha256(
            f"{spread_model_sha}:{total_model_sha}".encode("utf-8")
        ).hexdigest()
    )

    # Load Data
    # For V2, we might need to pass feature params (alpha, type) to load function
    # load_week_data currently doesn't support alpha...
    # But wait, load_week_data loads `team_week_adj` which assumes PRE-CALCULATED stats.
    # The pipeline step `run_pipeline_generic` calculated `team_week_adj` for specific iterations.
    # Recency type=recency in `matchup_v1` implies we rely on `v2_recency` to load data?
    # NO. `generate_weekly_bets` expects `adjustment_iteration` to load from `team_week_adj`.
    # `matchup_v1` has `params: type: recency, alpha: 0.3`.
    # `v2_recency.py` calculates stats ON THE FLY or loads them.
    # THE V2 PIPELINE for `matchup_v1` works differently than V1 `load_weekly_team_features`.

    # We need to detect if configs require V2 Recency loading
    use_recency = False
    alpha = 0.5
    if "features" in cfg and cfg.features.get("type") == "recency":
        use_recency = True
        alpha = cfg.features.get("alpha", 0.5)

    try:
        if gold_inference_df is not None:
            print("Using explicit point-in-time Gold feature dataset...")
            data_df = gold_inference_df[
                (gold_inference_df["season"].astype(int) == int(year))
                & (gold_inference_df["week"].astype(int) == int(week))
            ].copy()
            if data_df.empty:
                raise SystemExit(f"Gold dataset has no rows for {year} week {week}")
            if market_snapshots_df is not None and not market_snapshots_df.empty:
                market = market_snapshots_df.copy()
                market = market.sort_values(
                    [
                        column
                        for column in ("market_captured_at", "captured_at")
                        if column in market
                    ]
                ).drop_duplicates("game_id", keep="last")
                market = market.rename(
                    columns={
                        "spread_line": "home_team_spread_line",
                        "spread": "home_team_spread_line",
                        "total": "total_line",
                    }
                )
                market_columns = [
                    column
                    for column in (
                        "game_id",
                        "home_team_spread_line",
                        "total_line",
                        "market_snapshot_id",
                    )
                    if column in market
                ]
                data_df = data_df.drop(
                    columns=[
                        column for column in market_columns if column != "game_id"
                    ],
                    errors="ignore",
                ).merge(market[market_columns], on="game_id", how="left")
            if "id" not in data_df and "game_id" in data_df:
                data_df = data_df.rename(columns={"game_id": "id"})
        elif use_recency:
            print(f"Using V2 Recency Loading (alpha={alpha})...")
            from cks_picks_cfb.features.v2_recency import load_v2_recency_data

            # load_v2_recency_data loads the WHOLE YEAR. We filter for week.
            full_year_df = load_v2_recency_data(
                year,
                alpha=alpha,
                iterations=args.adjustment_iteration,
                for_prediction=True,
                dataset_reader=explicit_reader,
            )
            if full_year_df is None or full_year_df.empty:
                raise SystemExit("No data found via V2 Recency loader.")

            # Filter for requested week
            data_df = full_year_df[full_year_df["week"] == week].copy()
            # Rename columns if needed? load_v2_recency_data returns `home_...` `away_...` compatible with training.
            # Does it have `id` for game_id?
            # It has `game_id`.
            if "id" not in data_df.columns and "game_id" in data_df.columns:
                data_df = data_df.rename(columns={"game_id": "id"})

            # Ensure betting lines are there (load_v2_recency_data merges them)
            if (
                "home_team_spread_line" not in data_df.columns
                and "spread_line" in data_df.columns
            ):
                data_df = data_df.rename(
                    columns={"spread_line": "home_team_spread_line"}
                )

        else:
            raise NotImplementedError("Legacy loading not supported in V2 pipeline.")

        storage = get_storage()
        team_rows = storage.read_index("raw/teams", {"year": year})
        fbs_teams = {
            str(record.get("school"))
            for record in team_rows
            if str(record.get("classification", "")).lower() == "fbs"
        }
        schedule_rows = storage.read_index("raw/games", {"year": year})
        expected_ids = {
            int(record.get("id", record.get("game_id")))
            for record in schedule_rows
            if int(record.get("week", -1)) == week
            and record.get("home_team") in fbs_teams
            and record.get("away_team") in fbs_teams
        }
        data_df = data_df[
            data_df["home_team"].isin(fbs_teams) & data_df["away_team"].isin(fbs_teams)
        ].copy()
        actual_ids = set(pd.to_numeric(data_df["id"], errors="raise").astype(int))
        if actual_ids != expected_ids:
            missing = sorted(expected_ids - actual_ids)
            unexpected = sorted(actual_ids - expected_ids)
            raise RuntimeError(
                "FBS-vs-FBS prediction coverage mismatch: "
                f"missing={missing[:10]} unexpected={unexpected[:10]}"
            )

        if data_df.empty:
            raise SystemExit(f"No games found for Week {week}.")

        # Calculate missing tempo features (needed only for V1 models usually, but checking anyway)
        if (
            "home_plays_per_game" in data_df.columns
            and "away_plays_per_game" in data_df.columns
        ):
            data_df["tempo_contrast"] = (
                data_df["home_plays_per_game"] - data_df["away_plays_per_game"]
            )
            data_df["tempo_total"] = (
                data_df["home_plays_per_game"] + data_df["away_plays_per_game"]
            )
        else:
            # print("Warning: plays_per_game missing, cannot calculate tempo features.")
            data_df["tempo_contrast"] = 0.0
            data_df["tempo_total"] = 0.0

        # Check for weather features
        weather_defaults = {
            "temperature": 70.0,
            "wind_speed": 5.0,
            "precipitation": 0.0,
        }
        for col, default_val in weather_defaults.items():
            if col not in data_df.columns:
                # print(f"Warning: {col} missing, filling with default {default_val}")
                data_df[col] = default_val

        # Reset index to ensure alignment with predictions array
        data_df = data_df.reset_index(drop=True)

        # Quick feature magnitude sanity check to catch extreme values that can trigger sklearn warnings
        def _log_feature_magnitudes(df, label, top_n=5):
            numeric_cols = df.select_dtypes(include=["number"])
            if numeric_cols.empty:
                return
            max_abs = numeric_cols.abs().max().sort_values(ascending=False)
            top = max_abs.head(top_n)
            joined = ", ".join(f"{k}={v:.2f}" for k, v in top.items())
            print(f"[sanity] Top |{label}| feature magnitudes: {joined}")

        # Remove non-informative identifiers/metadata before feeding models
        drop_cols = [
            "home_id",
            "away_id",
            "venue_id",
            "attendance",
            "home_postgame_elo",
            "away_postgame_elo",
        ]
        feature_df = data_df.drop(
            columns=[c for c in drop_cols if c in data_df], errors="ignore"
        )

        _log_feature_magnitudes(feature_df, "raw")

        # Clip extreme pass YPP matchup features to reduce numerical instabilities in linear solvers.
        pass_cols = [
            "home_adj_off_pass_ypp",
            "home_adj_def_pass_ypp",
            "away_adj_off_pass_ypp",
            "away_adj_def_pass_ypp",
        ]
        clip_bounds = (
            -15.0,
            15.0,
        )  # approx 99th percentile; conservative symmetric cap
        for col in pass_cols:
            if col in feature_df.columns:
                feature_df[col] = feature_df[col].clip(*clip_bounds)

        _log_feature_magnitudes(feature_df, "raw_clipped")

        spread_model_versions = pd.Series(
            cfg.get("model_id", "unknown"), index=feature_df.index
        )
        total_model_versions = spread_model_versions.copy()
        route_high_confidence = pd.Series(True, index=feature_df.index)
        if routing_bundle is not None:
            routed = predict_with_model_bundle_v2(
                routing_bundle, feature_df, storage=storage
            )
            spread_preds = routed["predicted_spread"].to_numpy()
            total_preds = routed["predicted_total"].to_numpy()
            spread_model_versions = routed["spread_model_version"]
            total_model_versions = routed["total_model_version"]
            route_high_confidence = (
                routed["spread_high_confidence_eligible"]
                & routed["total_high_confidence_eligible"]
            )
        else:
            # Legacy development fallback. Production bundle inference never
            # loads or executes these repository-local/MLflow models.
            x_spread = select_features(feature_df, spread_full_cfg)
            _log_feature_magnitudes(x_spread, "spread_features")
            assert spread_model is not None
            spread_preds = spread_model.predict(x_spread)
            if (
                "models" in cfg
                and "spread" in cfg.models
                and "calibration_offset" in cfg.models.spread
            ):
                offset = cfg.models.spread.calibration_offset
                print(f"Applying Spread Calibration Offset: {offset}")
                spread_preds = spread_preds + offset
            x_total = select_features(feature_df, total_full_cfg)
            _log_feature_magnitudes(x_total, "total_features")
            assert total_model is not None
            total_preds = total_model.predict(x_total)

        # The preseason model is opt-in.  It can only affect output when a
        # complete, immutable source snapshot and validated model bundle exist.
        # Any issue leaves the established recency fallback untouched.
        preseason_cfg = cfg.get("preseason")
        if (
            routing_bundle is None
            and preseason_cfg
            and preseason_cfg.get("enabled", False)
        ):
            try:
                from cks_picks_cfb.preseason import (
                    blend_early_season_predictions,
                    build_preseason_matchups,
                    load_preseason_models,
                    predict_preseason,
                    snapshot_is_complete,
                )

                as_of = preseason_cfg.get("as_of")
                model_path = preseason_cfg.get("model_path")
                if not as_of or not model_path:
                    raise ValueError(
                        "preseason.as_of and preseason.model_path are required"
                    )
                storage = get_storage()
                if not snapshot_is_complete(storage, year, str(as_of)):
                    raise RuntimeError(
                        f"Preseason snapshot {year}/{as_of} is incomplete; using recency fallback"
                    )
                if production_mode:
                    raise ValueError(
                        "Production preseason routing must come from model_bundle_v2"
                    )
                if not Path(model_path).exists():
                    raise FileNotFoundError(
                        f"Preseason model bundle not found: {model_path}"
                    )

                preseason_df = build_preseason_matchups(
                    storage,
                    year=year,
                    as_of=str(as_of),
                    include_targets=False,
                )
                preseason_df = preseason_df[preseason_df["week"] == week].copy()
                if "game_id" not in preseason_df:
                    raise ValueError("Preseason matchups have no game_id column")
                preseason_df = preseason_df.set_index("game_id")
                game_ids = data_df["id"].tolist()
                missing_games = [
                    game_id for game_id in game_ids if game_id not in preseason_df.index
                ]
                if missing_games:
                    raise ValueError(
                        f"Preseason snapshot has no matchup rows for {len(missing_games)} games"
                    )
                preseason_df = preseason_df.loc[game_ids].reset_index()
                preseason_bundle = load_preseason_models(model_path)
                validation = preseason_bundle.get("validation", {})
                if not validation.get("promotion_pass", False):
                    raise RuntimeError(
                        "Preseason model has not passed its locked-holdout promotion gate"
                    )
                preseason_spread, preseason_total = predict_preseason(
                    preseason_bundle, preseason_df
                )
                spread_weights = {
                    int(key): float(value)
                    for key, value in (
                        preseason_cfg.get("spread_blend_weights")
                        or preseason_bundle.get("spread_blend_weights", {})
                    ).items()
                }
                total_weights = {
                    int(key): float(value)
                    for key, value in (
                        preseason_cfg.get("total_blend_weights")
                        or preseason_bundle.get("total_blend_weights", {})
                    ).items()
                }
                spread_preds = blend_early_season_predictions(
                    preseason_spread,
                    spread_preds,
                    data_df.get(
                        "home_current_season_games", pd.Series(0, index=data_df.index)
                    ),
                    data_df.get(
                        "away_current_season_games", pd.Series(0, index=data_df.index)
                    ),
                    spread_weights,
                )
                total_preds = blend_early_season_predictions(
                    preseason_total,
                    total_preds,
                    data_df.get(
                        "home_current_season_games", pd.Series(0, index=data_df.index)
                    ),
                    data_df.get(
                        "away_current_season_games", pd.Series(0, index=data_df.index)
                    ),
                    total_weights,
                )
                print(
                    f"Applied guarded preseason model for {year} Week {week} "
                    f"(snapshot {as_of})."
                )
            except Exception as exc:
                print(f"Preseason model unavailable; using recency fallback: {exc}")

        # Construct Bets DataFrame
        bets = []
        for idx, row in data_df.iterrows():
            game_id = row["id"]
            home = row["home_team"]
            away = row["away_team"]

            pred_spread = spread_preds[idx]
            pred_total = total_preds[idx]

            book_spread = row.get("home_team_spread_line")
            book_total = row.get("total_line")
            high_confidence_eligible = bool(route_high_confidence.iloc[idx])
            home_count = pd.to_numeric(
                row.get("home_current_season_games", 0), errors="coerce"
            )
            away_count = pd.to_numeric(
                row.get("away_current_season_games", 0), errors="coerce"
            )
            home_count = 0 if pd.isna(home_count) else int(home_count)
            away_count = 0 if pd.isna(away_count) else int(away_count)

            # Spread Bet (Dual-Threshold Strategy)
            if pd.notna(book_spread):
                # Spread Logic: Edge = abs(Pred - (-Line)) = abs(Pred + Line)
                # Bet Home if Pred > -Line
                edge = pred_spread + book_spread
                edge_abs = abs(edge)

                # Determine side and confidence based on dual thresholds
                if edge > 0:
                    bet_side = "Home"
                else:
                    bet_side = "Away"

                # Assign confidence based on which threshold is crossed
                if edge_abs >= spread_threshold_high:
                    bet_conf = "High"
                elif edge_abs >= spread_threshold:
                    bet_conf = "Medium"
                else:
                    bet_side = "No Bet"
                    bet_conf = ""

                bets.append(
                    {
                        "game_id": game_id,
                        "Game": f"{away} @ {home}",
                        "Spread Bet": bet_side,
                        "home_team_spread_line": book_spread,
                        "Spread Prediction": pred_spread,
                        "edge_spread": abs(edge),
                        "Spread Confidence": bet_conf,
                        "total_line": book_total,
                        "Total Prediction": pred_total,
                        "edge_total": 0.0,  # Placeholder
                        "Total Bet": "No Bet",  # Placeholder
                        "high_confidence_eligible": high_confidence_eligible,
                        "home_completed_games": home_count,
                        "away_completed_games": away_count,
                        "prediction_regime": row.get(
                            "prediction_regime", "established"
                        ),
                        "spread_model_version": spread_model_versions.iloc[idx],
                        "total_model_version": total_model_versions.iloc[idx],
                        "market_snapshot_id": row.get("market_snapshot_id"),
                        "market_policy_version": row.get("market_policy_version"),
                        "spread_selection_rule": row.get("spread_selection_rule"),
                        "total_selection_rule": row.get("total_selection_rule"),
                        "spread_provider_count": row.get("spread_provider_count", 0),
                        "total_provider_count": row.get("total_provider_count", 0),
                        "source_quote_ids": row.get("source_quote_ids", "[]"),
                        "market_captured_at": row.get("market_captured_at"),
                        "run_id": run_id,
                    }
                )
            else:
                bets.append(
                    {
                        "game_id": game_id,
                        "Game": f"{away} @ {home}",
                        "Spread Bet": "No Bet",
                        "home_team_spread_line": None,
                        "Spread Prediction": pred_spread,
                        "edge_spread": 0.0,
                        "Spread Confidence": "",
                        "total_line": book_total,
                        "Total Prediction": pred_total,
                        "edge_total": 0.0,
                        "Total Bet": "No Bet",
                        "high_confidence_eligible": high_confidence_eligible,
                        "home_completed_games": home_count,
                        "away_completed_games": away_count,
                        "prediction_regime": row.get(
                            "prediction_regime", "established"
                        ),
                        "spread_model_version": spread_model_versions.iloc[idx],
                        "total_model_version": total_model_versions.iloc[idx],
                        "market_snapshot_id": row.get("market_snapshot_id"),
                        "market_policy_version": row.get("market_policy_version"),
                        "spread_selection_rule": row.get("spread_selection_rule"),
                        "total_selection_rule": row.get("total_selection_rule"),
                        "spread_provider_count": row.get("spread_provider_count", 0),
                        "total_provider_count": row.get("total_provider_count", 0),
                        "source_quote_ids": row.get("source_quote_ids", "[]"),
                        "market_captured_at": row.get("market_captured_at"),
                        "run_id": run_id,
                    }
                )

            # Total Bet
            if pd.notna(book_total):
                # Total Logic: Edge = abs(Pred - Line)
                # Bet Over if Pred > Line
                edge_t = pred_total - book_total

                last_bet = bets[-1]
                last_bet["edge_total"] = abs(edge_t)

                if edge_t > total_threshold:
                    last_bet["Total Bet"] = "Over"
                elif edge_t < -total_threshold:
                    last_bet["Total Bet"] = "Under"
                else:
                    last_bet["Total Bet"] = "No Bet"

        # Save
        bets_df = pd.DataFrame(bets)

        # Add extra cols
        bets_df = bets_df.merge(
            data_df[["id", "start_date", "home_team", "away_team"]],
            left_on="game_id",
            right_on="id",
            how="left",
        )
        bets_df["Date"] = pd.to_datetime(bets_df["start_date"]).dt.strftime("%Y-%m-%d")
        bets_df["Time"] = pd.to_datetime(bets_df["start_date"]).dt.strftime("%H:%M:%S")
        bets_df["Home Team"] = bets_df["home_team"]
        bets_df["Away Team"] = bets_df["away_team"]

        # Add std dev columns if available (placeholder for now as models don't output it yet)
        bets_df["predicted_spread_std_dev"] = np.nan
        bets_df["predicted_total_std_dev"] = np.nan

        output_path = args.output_csv or local_prediction_path(year, week)
        output_dir = output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        bets_df.to_csv(output_path, index=False)
        print(f"Saved bets to {output_path}")

        if args.upload_artifact:
            try:
                code_sha = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            except (OSError, subprocess.CalledProcessError):
                code_sha = os.getenv("VERCEL_GIT_COMMIT_SHA", "unknown")
            config_bytes = Path(args.config).read_bytes()
            data_as_of = (
                args.as_of
                or pd.to_datetime(data_df["start_date"], utc=True).min().isoformat()
            )
            feature_snapshot = build_point_in_time_matchups(
                data_df,
                season=year,
                as_of=data_as_of,
                provenance={
                    "feature_config": str(spread_feat_path),
                    "adjustment_iteration": str(args.adjustment_iteration),
                    "code_sha": code_sha,
                },
            )
            feature_bytes = dataframe_csv_bytes(feature_snapshot)
            feature_uri = prediction_run_features_path(year, week, run_id)
            storage = get_storage()
            if storage.exists(feature_uri):
                if storage.read_bytes(feature_uri) != feature_bytes:
                    raise FileExistsError(
                        f"Immutable feature snapshot collision: {feature_uri}"
                    )
            else:
                storage.write_bytes(feature_bytes, feature_uri)
            lined_games = int(
                bets_df[["home_team_spread_line", "total_line"]]
                .notna()
                .all(axis=1)
                .sum()
            )
            payload = write_prediction_run(
                bets_df,
                year=year,
                week=week,
                run_id=run_id,
                manifest={
                    "state": args.run_state,
                    "data_as_of": data_as_of,
                    "feature_snapshot_uri": feature_uri,
                    "feature_snapshot_sha256": sha256_bytes(feature_bytes),
                    "expected_games": int(len(data_df)),
                    "predicted_games": int(
                        bets_df[["Spread Prediction", "Total Prediction"]]
                        .notna()
                        .all(axis=1)
                        .sum()
                    ),
                    "lined_games": lined_games,
                    "code_sha": code_sha,
                    "config_sha": hashlib.sha256(config_bytes).hexdigest(),
                    "model_bundle_sha256": (
                        routing_bundle.manifest_sha256
                        if routing_bundle is not None
                        else model_bundle_sha
                    ),
                    "input_dataset_refs": input_dataset_refs,
                    "source_config": str(args.config),
                    "system_name": cfg.get("system_name", "CKsPicks Model"),
                    "model_id": cfg.get("model_id", "unknown"),
                    "validation": {
                        "all_predictions_present": bool(
                            bets_df[["Spread Prediction", "Total Prediction"]]
                            .notna()
                            .all(axis=None)
                        ),
                        "line_coverage_complete": lined_games == len(data_df),
                    },
                },
            )
            print(
                "Uploaded immutable prediction run "
                f"{run_id} to {payload['artifact_uri']}"
            )

    except Exception as e:
        print(f"Error processing week {week}: {e}")
        import traceback

        traceback.print_exc()
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
