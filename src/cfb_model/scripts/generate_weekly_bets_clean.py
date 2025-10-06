"""Generate weekly ATS recommendations using trained models and betting policy (clean)."""

from __future__ import annotations

import argparse
import os
import sys
from math import erf

import joblib
import numpy as np
import pandas as pd

from cfb_model.config import get_data_root
from cfb_model.data.storage.local_storage import LocalStorage
from cfb_model.models.features import (
    build_feature_list,
)


def load_ensemble_models(model_year: int, model_dir: str) -> dict[str, list]:
    """Load all models for a given year, grouped by target."""
    ensemble_dir = os.path.join(model_dir, str(model_year))
    if not os.path.isdir(ensemble_dir):
        raise FileNotFoundError(f"Model directory not found: {ensemble_dir}")

    models = {"spread": [], "total": []}
    for file_name in os.listdir(ensemble_dir):
        if file_name.endswith(".joblib"):
            model_path = os.path.join(ensemble_dir, file_name)
            model = joblib.load(model_path)
            name_lower = file_name.lower()
            if name_lower.startswith("spread_") or (
                "spread" in name_lower and "total" not in name_lower
            ):
                models["spread"].append(model)
            elif (
                name_lower.startswith("total_")
                or name_lower.startswith("ridge_total")
                or ("total" in name_lower and "spread" not in name_lower)
            ):
                models["total"].append(model)

    if not models["spread"]:
        raise FileNotFoundError(f"No spread models found in {ensemble_dir}")
    if not models["total"]:
        raise FileNotFoundError(f"No total models found in {ensemble_dir}")

    print(
        f"Loaded {len(models['spread'])} spread models and {len(models['total'])} total models."
    )
    return models


def _reduce_betting_lines(lines_df: pd.DataFrame) -> pd.DataFrame:
    """Reduce betting_lines to one row per game, preferring provider == 'consensus'.

    Unlike the previous implementation, this retains all columns provided by the
    selected provider row (e.g., potential moneyline or odds fields) so that
    downstream sizing logic (Kelly) has access to prices when available.
    """
    if lines_df.empty:
        return lines_df
    df = lines_df.copy()
    # Prefer provider == 'consensus' when available
    if "provider" in df.columns:
        df["provider_rank"] = np.where(
            df["provider"].astype(str).str.lower() == "consensus", 0, 1
        )
    else:
        df["provider_rank"] = 1
    df = (
        df.sort_values(["game_id", "provider_rank"])  # consensus first
        .groupby("game_id", as_index=False)
        .first()
    )
    # Normalize a couple of critical column names but retain the rest
    rename_map = {"over_under": "total_line", "spread": "home_team_spread_line"}
    for old, new in rename_map.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})
    return df


def load_week_dataset(
    year: int, week: int, data_root: str | None = None
) -> pd.DataFrame:
    """Load per-game features for a specific week from the cache and merge betting lines."""
    resolved_root = data_root or get_data_root()
    processed = LocalStorage(
        data_root=resolved_root, file_format="csv", data_type="processed"
    )
    raw = LocalStorage(data_root=resolved_root, file_format="csv", data_type="raw")

    # 1. Load pre-calculated features from the cache
    team_feature_records = processed.read_index(
        "team_week_adj", {"year": year, "week": week}
    )
    if not team_feature_records:
        raise ValueError(
            f"No cached weekly adjusted stats found for year {year}, week {week}"
        )

    team_features_df = pd.DataFrame.from_records(team_feature_records)

    # 2. Load raw games for the entire year and then filter by week
    all_game_records = raw.read_index("games", {"year": year})
    if not all_game_records:
        raise ValueError(f"No raw games found for year {year}")

    all_games_df = pd.DataFrame.from_records(all_game_records)
    week_games_df = all_games_df[all_games_df["week"] == week].copy()
    if week_games_df.empty:
        raise ValueError(
            f"No raw games found for year {year}, week {week} after filtering"
        )

    # 3. Merge features into the games DataFrame for home and away teams
    home_features = team_features_df.add_prefix("home_")
    away_features = team_features_df.add_prefix("away_")

    merged_df = week_games_df.merge(
        home_features,
        left_on=["season", "home_team"],
        right_on=["home_season", "home_team"],
        how="left",
    )
    merged_df = merged_df.merge(
        away_features,
        left_on=["season", "away_team"],
        right_on=["away_season", "away_team"],
        how="left",
    )
    merged_df = merged_df.drop(columns=["home_season", "away_season"], errors="ignore")

    # 4. Load and merge betting lines for the week
    lines_records = raw.read_index("betting_lines", {"year": year})
    lines_df = (
        pd.DataFrame.from_records(lines_records) if lines_records else pd.DataFrame()
    )
    if not lines_df.empty:
        lines_df = _reduce_betting_lines(lines_df)
        week_game_ids = merged_df["id"].unique()
        lines_for_week = lines_df[lines_df["game_id"].isin(week_game_ids)]
        merged_df = merged_df.merge(
            lines_for_week, left_on=["id"], right_on=["game_id"], how="left"
        )

    # Derive same_conference for spread feature parity with training
    if (
        "home_conference" in merged_df.columns
        and "away_conference" in merged_df.columns
    ):
        merged_df["same_conference"] = (
            merged_df["home_conference"].astype(str)
            == merged_df["away_conference"].astype(str)
        ).astype(int)
    elif "conference_game" in merged_df.columns:
        try:
            merged_df["same_conference"] = merged_df["conference_game"].astype(int)
        except Exception:
            merged_df["same_conference"] = 0
    else:
        merged_df["same_conference"] = 0

    return merged_df


def generate_predictions(model, X: pd.DataFrame) -> pd.Series:  # noqa: N803
    return pd.Series(model.predict(X), index=X.index)


def _norm_cdf(x):  # accepts scalar or array-like
    arr = np.asarray(x, dtype=float)
    erf_vec = np.vectorize(erf)
    return 0.5 * (1.0 + erf_vec(arr / np.sqrt(2.0)))


def _american_to_b(odds: float | int | None) -> float | None:
    """Convert American odds to 'b' (profit per unit) for Kelly. Returns None if not usable."""
    try:
        if odds is None or (isinstance(odds, float) and np.isnan(odds)):
            return None
        odds = float(odds)
        if odds > 0:
            return odds / 100.0
        if odds < 0:
            return 100.0 / abs(odds)
        return None
    except Exception:
        return None


def apply_betting_policy(
    predictions_df: pd.DataFrame,
    *,
    spread_edge_threshold: float = 5.0,
    total_edge_threshold: float = 5.5,
    spread_std_dev_threshold: float | None = None,
    total_std_dev_threshold: float | None = None,
    min_games_played: int = 2,
    fractional_kelly: float = 0.25,
    kelly_cap: float = 0.25,
    base_unit_fraction: float = 0.02,
    default_american_price: int = -110,
    single_bet_cap: float = 0.05,
) -> pd.DataFrame:
    """Apply MVP betting policy and generate reasons for decisions."""
    df = predictions_df.copy()

    # 1. Calculate Edges
    df["expected_home_margin"] = -df["home_team_spread_line"]
    df["edge_spread"] = (df["predicted_spread"] - df["expected_home_margin"]).abs()
    df["edge_total"] = (df["predicted_total"] - df["total_line"]).abs()

    # 2. Determine Bet Reasons
    df["spread_bet_reason"] = "Bet Placed"
    df["total_bet_reason"] = "Bet Placed"

    # Check for ineligible games first (prefer FBS-only counts if present)
    home_count = (
        df.get("home_fbs_games_played")
        if "home_fbs_games_played" in df.columns
        else df.get("home_games_played", 0)
    )
    away_count = (
        df.get("away_fbs_games_played")
        if "away_fbs_games_played" in df.columns
        else df.get("away_games_played", 0)
    )
    ineligible_games = (home_count < min_games_played) | (away_count < min_games_played)
    df.loc[ineligible_games, ["spread_bet_reason", "total_bet_reason"]] = (
        "No Bet - Min Games"
    )

    # Check other conditions only for eligible games
    eligible_mask = ~ineligible_games

    if spread_std_dev_threshold is not None:
        low_conf_spread = df["predicted_spread_std_dev"] > spread_std_dev_threshold
        df.loc[eligible_mask & low_conf_spread, "spread_bet_reason"] = (
            "No Bet - Low Confidence"
        )

    if total_std_dev_threshold is not None:
        low_conf_total = df["predicted_total_std_dev"] > total_std_dev_threshold
        df.loc[eligible_mask & low_conf_total, "total_bet_reason"] = (
            "No Bet - Low Confidence"
        )

    small_edge_spread = df["edge_spread"] < spread_edge_threshold
    df.loc[eligible_mask & small_edge_spread, "spread_bet_reason"] = (
        "No Bet - Small Edge"
    )

    small_edge_total = df["edge_total"] < total_edge_threshold
    df.loc[eligible_mask & small_edge_total, "total_bet_reason"] = "No Bet - Small Edge"

    # 3. Determine Bet Decisions
    df["bet_spread"] = "none"
    spread_bet_mask = df["spread_bet_reason"] == "Bet Placed"
    df.loc[spread_bet_mask, "bet_spread"] = np.where(
        df.loc[spread_bet_mask, "predicted_spread"]
        > df.loc[spread_bet_mask, "expected_home_margin"],
        "home",
        "away",
    )

    df["bet_total"] = "none"
    total_bet_mask = df["total_bet_reason"] == "Bet Placed"
    df.loc[total_bet_mask, "bet_total"] = np.where(
        df.loc[total_bet_mask, "predicted_total"]
        > df.loc[total_bet_mask, "total_line"],
        "over",
        "under",
    )

    # --- 4. Kelly Sizing ---
    # Spread win probability
    spread_sigma = df.get("predicted_spread_std_dev", pd.Series(7.0, index=df.index))
    z_spread = (
        df["predicted_spread"] - df["expected_home_margin"]
    ) / spread_sigma.replace(0, np.nan)
    p_cover_home = _norm_cdf(z_spread)
    p_cover_away = 1.0 - p_cover_home

    # Total win probability
    total_sigma = df.get("predicted_total_std_dev", pd.Series(10.0, index=df.index))
    z_total = (df["predicted_total"] - df["total_line"]) / total_sigma.replace(
        0, np.nan
    )
    p_over = _norm_cdf(z_total)
    p_under = 1.0 - p_over

    def _pick_price(row, side: str) -> float:
        # ... (rest of the function is unchanged)
        return float(default_american_price)

    k_spread, k_total, units_spread, units_total = [], [], [], []
    ph, pa, po, pu = map(np.asarray, [p_cover_home, p_cover_away, p_over, p_under])

    for j, (idx, row) in enumerate(df.iterrows()):
        # Spread sizing
        f_spread = 0.0
        if row["bet_spread"] in ("home", "away"):
            p = ph[j] if row["bet_spread"] == "home" else pa[j]
            b = _american_to_b(_pick_price(row, row["bet_spread"])) or _american_to_b(
                default_american_price
            )
            if b is not None:
                p = float(np.clip(p, 1e-6, 1 - 1e-6))
                f_uncapped = max((b * p - (1.0 - p)) / b, 0.0)
                f_capped = min(f_uncapped, float(kelly_cap))
                f_spread = float(
                    min(float(fractional_kelly) * f_capped, single_bet_cap)
                )
        k_spread.append(f_spread)
        units_spread.append(
            round(f_spread / base_unit_fraction, 2) if base_unit_fraction > 0 else 0.0
        )

        # Total sizing
        f_total = 0.0
        if row["bet_total"] in ("over", "under"):
            p = po[j] if row["bet_total"] == "over" else pu[j]
            b_t = _american_to_b(_pick_price(row, row["bet_total"])) or _american_to_b(
                default_american_price
            )
            if b_t is not None:
                p = float(np.clip(p, 1e-6, 1 - 1e-6))
                f_uncapped_t = max((b_t * p - (1.0 - p)) / b_t, 0.0)
                f_capped_t = min(f_uncapped_t, float(kelly_cap))
                f_total = float(
                    min(float(fractional_kelly) * f_capped_t, single_bet_cap)
                )
        k_total.append(f_total)
        units_total.append(
            round(f_total / base_unit_fraction, 2) if base_unit_fraction > 0 else 0.0
        )

    df["kelly_fraction_spread"] = k_spread
    df["kelly_fraction_total"] = k_total
    df["bet_units_spread"] = units_spread
    df["bet_units_total"] = units_total

    return df


def generate_csv_report(predictions_df: pd.DataFrame, output_path: str) -> None:
    """Write the weekly CSV report using the new standardized format."""
    report_df = predictions_df.copy()

    # 1. Ensure game_date is in datetime format
    report_df["game_date_dt"] = pd.to_datetime(report_df["start_date"])

    # 2. Create new formatted columns
    report_df["Year"] = report_df["season"]
    report_df["Week"] = report_df["week"]
    report_df["Date"] = report_df["game_date_dt"].dt.strftime("%Y-%m-%d")
    report_df["Time"] = report_df["game_date_dt"].dt.strftime("%H:%M:%S")
    report_df["Game"] = report_df["away_team"] + " @ " + report_df["home_team"]
    report_df["game_id"] = report_df["id"]

    # Format spread to show "Team +/- Spread"
    report_df["Spread"] = report_df.apply(
        lambda row: f"{row['home_team']} {row['home_team_spread_line']:+.1f}"
        if pd.notna(row["home_team_spread_line"])
        else "",
        axis=1,
    )

    report_df["Over/Under"] = report_df["total_line"]
    report_df["Spread Prediction"] = report_df["predicted_spread"]
    report_df["Total Prediction"] = report_df["predicted_total"]
    report_df["Spread Bet"] = report_df["bet_spread"]
    report_df["Total Bet"] = report_df["bet_total"]

    # 3. Select and order the final columns
    final_cols = [
        "game_id",
        "Year",
        "Week",
        "Date",
        "Time",
        "Game",
        "home_team",
        "away_team",
        "Spread",
        "home_team_spread_line",
        "Over/Under",
        "total_line",
        "Spread Prediction",
        "Total Prediction",
        # Confidence (std dev) and edges
        "predicted_spread_std_dev",
        "predicted_total_std_dev",
        "edge_spread",
        "edge_total",
        # Bet decisions and units
        "Spread Bet",
        "bet_units_spread",
        "spread_bet_reason",
        "Total Bet",
        "bet_units_total",
        "total_bet_reason",
    ]
    final_report_df = report_df[[col for col in final_cols if col in report_df.columns]]

    # 4. Save the report
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_report_df.to_csv(output_path, index=False)
    print(f"Weekly betting report saved to {output_path}")


def main() -> None:
    """Generate and save weekly betting recommendations.

    This script orchestrates the end-to-end process for a given week:
    1.  Loads all trained ensemble models for the specified year.
    2.  Loads the cached, point-in-time weekly feature dataset.
    3.  Generates spread and total predictions using the model ensembles.
    4.  Calculates prediction confidence (standard deviation) across ensembles.
    5.  (Optional) Generates SHAP explanations for top predictive features.
    6.  Applies a betting policy to filter predictions based on edge and confidence.
    7.  Calculates bet sizes using a fractional Kelly criterion.
    8.  Writes the final recommendations to a CSV report.
    """
    parser = argparse.ArgumentParser(
        description="Generate weekly CFB betting recommendations (clean)."
    )
    parser.add_argument(
        "--year", type=int, required=True, help="Season year for predictions"
    )
    parser.add_argument(
        "--week", type=int, required=True, help="Week number for predictions"
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Absolute path to the data root directory",
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="./models",
        help="Directory with trained models",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./reports",
        help="Directory to save the weekly report",
    )
    parser.add_argument(
        "--spread-threshold",
        type=float,
        default=6.0,
        help="Edge threshold (in points) for spread bets (default: 6.0)",
    )
    parser.add_argument(
        "--total-threshold",
        type=float,
        default=6.0,
        help="Edge threshold (in points) for totals bets (default: 6.0)",
    )
    parser.add_argument(
        "--spread-std-dev-threshold",
        type=float,
        default=3.0,
        help="Standard deviation threshold for spread bets (default: 3.0)",
    )
    parser.add_argument(
        "--total-std-dev-threshold",
        type=float,
        default=1.5,
        help="Standard deviation threshold for total bets (default: 1.5)",
    )
    parser.add_argument(
        "--kelly-fraction",
        type=float,
        default=0.25,
        help="Fractional Kelly to apply (default: 0.25)",
    )
    parser.add_argument(
        "--kelly-cap",
        type=float,
        default=0.25,
        help="Cap on raw Kelly fraction before applying fractional Kelly (default: 0.25)",
    )
    parser.add_argument(
        "--base-unit-fraction",
        type=float,
        default=0.02,
        help="Bankroll fraction that defines 1 unit (default: 0.02 = 2%)",
    )
    args = parser.parse_args()

    try:
        print(f"Loading ensemble models for year {args.year}...")
        models = load_ensemble_models(args.year, args.model_dir)

        print(f"Loading dataset for year {args.year}, week {args.week}...")
        df = load_week_dataset(args.year, args.week, args.data_root)
        print(
            f"Loaded {len(df)} games for week {args.week} with columns: {sorted(df.columns)[:8]} ..."
        )

        # Build feature list similar to training
        feature_list = build_feature_list(df)
        print(f"Using {len(feature_list)} features")
        if not feature_list:
            print("No usable features found in dataset. Exiting.")
            sys.exit(0)

        # Drop rows missing any required feature columns
        df_clean = df.dropna(subset=feature_list)
        if df_clean.empty:
            print("No games with complete feature data this week.")
            sys.exit(0)

        x = df_clean[feature_list].astype("float64")

        # --- Ensemble Prediction ---
        print("Generating ensemble predictions...")
        # Align features to each model's training features when available
        spread_predictions = []
        for m in models["spread"]:
            req = list(getattr(m, "feature_names_in_", [])) or feature_list
            # Ensure all required columns exist; fill missing with 0.0
            x_m = df_clean.reindex(columns=req, fill_value=0.0).astype("float64")
            spread_predictions.append(pd.Series(m.predict(x_m), index=df_clean.index))
        if not spread_predictions:
            print("No valid spread predictions due to feature mismatch. Exiting.")
            sys.exit(0)
        df_clean["predicted_spread"] = np.mean(spread_predictions, axis=0)
        df_clean["predicted_spread_std_dev"] = np.std(spread_predictions, axis=0)

        total_predictions = []
        for m in models["total"]:
            req = list(getattr(m, "feature_names_in_", [])) or feature_list
            x_m = df_clean.reindex(columns=req, fill_value=0.0).astype("float64")
            total_predictions.append(pd.Series(m.predict(x_m), index=df_clean.index))
        if not total_predictions:
            print("No valid total predictions due to feature mismatch. Exiting.")
            sys.exit(0)
        df_clean["predicted_total"] = np.mean(total_predictions, axis=0)
        df_clean["predicted_total_std_dev"] = np.std(total_predictions, axis=0)

        print("Generating SHAP explanations...")
        try:
            import shap

            # Use the first model in each ensemble for SHAP explanations as a representative
            spread_model = models["spread"][0]
            # Some sklearn pipelines are not directly callable by shap; fall back to predict function
            spread_explainer = shap.Explainer(
                getattr(spread_model, "predict", spread_model), x
            )
            spread_shap_values = spread_explainer(x).values
            spread_shap_df = (
                pd.DataFrame(spread_shap_values, columns=x.columns, index=x.index)
                .apply(pd.to_numeric, errors="coerce")
                .fillna(0.0)
            )

            top_spread_features = []
            for index, row in spread_shap_df.iterrows():
                top_features = row.abs().nlargest(3).index
                reasons = [f"{feat}: {row[feat]:+.2f}" for feat in top_features]
                top_spread_features.append(reasons)

            spread_reasons_df = pd.DataFrame(
                top_spread_features,
                index=df_clean.index,
                columns=["spread_reason_1", "spread_reason_2", "spread_reason_3"],
            )
            df_clean = df_clean.join(spread_reasons_df)

            total_model = models["total"][0]
            total_explainer = shap.Explainer(
                getattr(total_model, "predict", total_model), x
            )
            total_shap_values = total_explainer(x).values
            total_shap_df = (
                pd.DataFrame(total_shap_values, columns=x.columns, index=x.index)
                .apply(pd.to_numeric, errors="coerce")
                .fillna(0.0)
            )

            top_total_features = []
            for index, row in total_shap_df.iterrows():
                top_features = row.abs().nlargest(3).index
                reasons = [f"{feat}: {row[feat]:+.2f}" for feat in top_features]
                top_total_features.append(reasons)

            total_reasons_df = pd.DataFrame(
                top_total_features,
                index=df_clean.index,
                columns=["total_reason_1", "total_reason_2", "total_reason_3"],
            )
            df_clean = df_clean.join(total_reasons_df)
        except Exception as shap_err:
            # If SHAP fails (e.g., unsupported model pipeline), proceed without explanations
            print(
                f"SHAP explanation generation failed: {shap_err}. Proceeding without explanations."
            )
            for col in [
                "spread_reason_1",
                "spread_reason_2",
                "spread_reason_3",
                "total_reason_1",
                "total_reason_2",
                "total_reason_3",
            ]:
                if col not in df_clean.columns:
                    df_clean[col] = ""

        print("Applying betting policy...")
        final_df = apply_betting_policy(
            df_clean,
            spread_edge_threshold=args.spread_threshold,
            total_edge_threshold=args.total_threshold,
            spread_std_dev_threshold=args.spread_std_dev_threshold,
            total_std_dev_threshold=args.total_std_dev_threshold,
            min_games_played=2,
            fractional_kelly=args.kelly_fraction,
            kelly_cap=args.kelly_cap,
            base_unit_fraction=args.base_unit_fraction,
            single_bet_cap=0.05,
        )

        output_path = os.path.join(
            args.output_dir, str(args.year), f"CFB_week{args.week}_bets.csv"
        )
        print("Writing CSV report...")
        generate_csv_report(final_df, output_path)
        print("Done.")

    except Exception as e:
        print(
            f"Error during weekly bet generation for year {args.year}, week {args.week}: {e}"
        )
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
