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
from src.config import get_data_root
from src.features.selector import select_features

# from src.models.features import load_weekly_team_features
from src.utils.local_storage import LocalStorage
from src.utils.mlflow_tracking import setup_mlflow


def load_week_data(year, week, adjustment_iteration: int = 2):
    data_root = get_data_root()
    raw = LocalStorage(data_root=data_root, file_format="csv", data_type="raw")

    # Load features (align with training split defaults; fall back to legacy layout)
    team_features = load_weekly_team_features(
        year, week, data_root, adjustment_iteration=adjustment_iteration
    )
    if team_features is None:
        raise ValueError("No team features found")

    # Load games
    games = pd.DataFrame.from_records(raw.read_index("games", {"year": year}))
    week_games = games[games["week"] == week].copy()
    week_games = week_games.drop_duplicates(subset=["id"], keep="last")

    # Merge features
    home_feats = team_features.add_prefix("home_")
    away_feats = team_features.add_prefix("away_")

    merged = week_games.merge(
        home_feats,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )
    merged = merged.merge(
        away_feats,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
    )

    # Promote game-level weather columns (per-game values duplicated across teams)
    for col in ["temperature", "wind_speed", "precipitation"]:
        home_col = f"home_{col}"
        away_col = f"away_{col}"
        if home_col in merged.columns or away_col in merged.columns:
            merged[col] = merged.get(home_col)
            if away_col in merged.columns:
                merged[col] = merged[col].combine_first(merged[away_col])

    # Load lines
    lines = pd.DataFrame.from_records(
        raw.read_index("betting_lines", {"year": year, "week": week})
    )
    if not lines.empty:
        # Simple dedupe
        lines = lines.sort_values("provider").groupby("game_id", as_index=False).first()
        # Rename cols if needed
        rename_map = {"over_under": "total_line", "spread": "home_team_spread_line"}
        lines = lines.rename(columns=rename_map)
        merged = merged.merge(lines, left_on="id", right_on="game_id", how="left")

    return merged


def main():
    parser = argparse.ArgumentParser(description="Generate Weekly Bets")
    parser.add_argument(
        "--config",
        type=str,
        default="conf/weekly_bets/default.yaml",
        help="Path to config file",
    )
    parser.add_argument(
        "--adjustment-iteration",
        type=int,
        default=2,
        help="Opponent-adjustment iteration to load (default=2; falls back to legacy layout if missing)",
    )
    args = parser.parse_args()

    # Load Config
    cfg = OmegaConf.load(args.config)
    print(f"Loaded config from {args.config}")

    year = cfg.year
    week = cfg.week
    spread_threshold = cfg.spread_edge_threshold
    total_threshold = cfg.total_edge_threshold

    print(f"Generating bets for {year} Week {week}")
    print(f"Thresholds: Spread={spread_threshold}, Total={total_threshold}")

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
            from src.features.v2_recency import load_v2_recency_data

            # load_v2_recency_data loads the WHOLE YEAR. We filter for week.
            full_year_df = load_v2_recency_data(
                year,
                alpha=alpha,
                iterations=args.adjustment_iteration,
                for_prediction=True,
            )
            if full_year_df is None or full_year_df.empty:
                print("No data found via V2 Recency loader.")
                return

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
            print(f"No games found for Week {week}. Exiting.")
            return

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

        # Predict Spread
        # For V2 models (linear), we need to ensure features match exactly
        x_spread = select_features(data_df, spread_full_cfg)
        spread_preds = spread_model.predict(x_spread)

        # Predict Total
        x_total = select_features(data_df, total_full_cfg)
        total_preds = total_model.predict(x_total)

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

            # Spread Bet
            if pd.notna(book_spread):
                # Spread Logic: Edge = abs(Pred - (-Line)) = abs(Pred + Line)
                # Bet Home if Pred > -Line
                edge = pred_spread + book_spread

                if edge > spread_threshold:
                    bet_side = "Home"
                    bet_conf = "High"
                elif edge < -spread_threshold:
                    bet_side = "Away"
                    bet_conf = "High"
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

        output_dir = Path(f"data/production/predictions/{year}")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"CFB_week{week}_bets.csv"
        bets_df.to_csv(output_path, index=False)
        print(f"Saved bets to {output_path}")

    except Exception as e:
        print(f"Error processing week {week}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
