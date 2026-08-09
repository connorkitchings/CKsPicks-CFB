import argparse
import os
import sys
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from omegaconf import OmegaConf

# Add project root to path
sys.path.append(os.getcwd())
# noqa: E402
from cks_picks_cfb.artifacts import (
    local_prediction_path,
    prediction_artifact_path,
    write_csv_artifact,
)
from cks_picks_cfb.features.selector import select_features
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
        "--output-csv",
        type=Path,
        default=None,
        help="Working-copy CSV path. Defaults to data/production/predictions/{year}/CFB_week{week}_bets.csv",
    )
    parser.add_argument(
        "--upload-artifact",
        action="store_true",
        help="Also write the predictions CSV to durable storage (R2/S3/local backend).",
    )
    args = parser.parse_args()

    # Load Config
    cfg = OmegaConf.load(args.config)
    print(f"Loaded config from {args.config}")

    year = args.year if args.year is not None else cfg.year
    week = args.week if args.week is not None else cfg.week
    spread_threshold = cfg.spread_edge_threshold
    # Support dual-threshold betting strategy (default + high confidence)
    spread_threshold_high = cfg.get("spread_edge_threshold_high_conf", spread_threshold)
    total_threshold = cfg.total_edge_threshold

    print(f"Generating bets for {year} Week {week}")
    print(
        f"Thresholds: Spread={spread_threshold} (default), {spread_threshold_high} (high conf), Total={total_threshold}"
    )

    setup_mlflow()

    # Load Models and Feature Configs
    # Support both MLflow registry (legacy) and local paths (V2)

    # Spread
    if "models" in cfg and "spread" in cfg.models and "path" in cfg.models.spread:
        print(f"Loading Spread Model from local path: {cfg.models.spread.path}")
        from joblib import load

        spread_model = load(cfg.models.spread.path)
        spread_feat_path = cfg.models.spread.get(
            "features", "conf/features/ppr_v1.yaml"
        )
    else:
        spread_model_name = cfg.model_registry.spread_models[0]
        print(f"Loading Spread Model from MLflow: {spread_model_name}")
        spread_model = mlflow.pyfunc.load_model(
            f"models:/{spread_model_name}/Production"
        )
        spread_feat_path = "conf/features/ppr_v1.yaml"

    print(f"Loading Spread Features from: {spread_feat_path}")
    spread_feat_cfg = OmegaConf.load(spread_feat_path)
    # Check for overrides in main config
    if "features" in cfg:
        # If main config has feature params (e.g. alpha), merge them
        if "params" in cfg.features:
            spread_feat_cfg["params"] = cfg.features.params

    # Total
    if "models" in cfg and "total" in cfg.models and "path" in cfg.models.total:
        print(f"Loading Total Model from local path: {cfg.models.total.path}")
        from joblib import load

        total_model = load(cfg.models.total.path)
        total_feat_path = cfg.models.total.get(
            "features", "conf/features/standard_v1.yaml"
        )
    else:
        total_model_name = cfg.model_registry.total_models[0]
        print(f"Loading Total Model from MLflow: {total_model_name}")
        total_model = mlflow.pyfunc.load_model(f"models:/{total_model_name}/Production")
        total_feat_path = "conf/features/standard_v1.yaml"

    print(f"Loading Total Features from: {total_feat_path}")
    total_feat_cfg = OmegaConf.load(total_feat_path)
    if "features" in cfg and "params" in cfg.features:
        total_feat_cfg["params"] = cfg.features.params

    spread_full_cfg = OmegaConf.create({"features": spread_feat_cfg})
    total_full_cfg = OmegaConf.create({"features": total_feat_cfg})

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
        if use_recency:
            print(f"Using V2 Recency Loading (alpha={alpha})...")
            from cks_picks_cfb.features.v2_recency import load_v2_recency_data

            # load_v2_recency_data loads the WHOLE YEAR. We filter for week.
            full_year_df = load_v2_recency_data(
                year,
                alpha=alpha,
                iterations=args.adjustment_iteration,
                for_prediction=True,
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

        # Predict Spread
        # For V2 models (linear), we need to ensure features match exactly
        x_spread = select_features(feature_df, spread_full_cfg)
        _log_feature_magnitudes(x_spread, "spread_features")
        spread_preds = spread_model.predict(x_spread)

        # Apply Calibration Offset
        if (
            "models" in cfg
            and "spread" in cfg.models
            and "calibration_offset" in cfg.models.spread
        ):
            offset = cfg.models.spread.calibration_offset
            print(f"Applying Spread Calibration Offset: {offset}")
            spread_preds = spread_preds + offset

        # Predict Total
        x_total = select_features(feature_df, total_full_cfg)
        _log_feature_magnitudes(x_total, "total_features")
        total_preds = total_model.predict(x_total)

        # The preseason model is opt-in.  It can only affect output when a
        # complete, immutable source snapshot and validated model bundle exist.
        # Any issue leaves the established recency fallback untouched.
        preseason_cfg = cfg.get("preseason")
        if preseason_cfg and preseason_cfg.get("enabled", False):
            try:
                from cks_picks_cfb.data.storage import get_storage
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
                weights = {
                    int(key): float(value)
                    for key, value in (
                        preseason_cfg.get("blend_weights")
                        or preseason_bundle.get("blend_weights", {})
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
                    weights,
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
                    weights,
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
            high_confidence_eligible = bool(row.get("high_confidence_eligible", True))

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
            artifact_path = prediction_artifact_path(year, week)
            write_csv_artifact(bets_df, artifact_path)
            print(f"Uploaded durable predictions artifact to {artifact_path}")

    except Exception as e:
        print(f"Error processing week {week}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
