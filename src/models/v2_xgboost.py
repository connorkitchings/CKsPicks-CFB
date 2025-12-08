"""XGBoost Model Wrapper for V2 Pipeline."""

from pathlib import Path

import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error


class V2XGBoostModel:
    def __init__(self, features=None, **params):
        """
        Wrapper for XGBRegressor.
        Args:
            features: List of feature names to use.
            **params: XGBoost hyperparameters.
        """
        self.features = features
        self.model = xgb.XGBRegressor(**params)
        self.params = params

    def fit(self, df):
        # Drop rows with missing target
        df_clean = df.dropna(subset=["spread_target"])

        # Select features
        if self.features:
            x = df_clean[self.features]
        else:
            raise ValueError("V2XGBoostModel requires explicit features list")

        y = df_clean["spread_target"]

        # Fit model
        self.model.fit(x, y, verbose=True)

    def predict(self, df):
        if self.features:
            x = df[self.features]
        else:
            # Fallback (shouldn't happen in V2)
            # Try to infer from columns if they match features (risky)
            raise ValueError("V2XGBoostModel requires explicit features list")

        return self.model.predict(x)

    def evaluate(self, df):
        df_clean = df.dropna(subset=["spread_target"])
        preds = self.predict(df_clean)
        actuals = df_clean["spread_target"]

        metrics = {}

        # Standard Metrics
        metrics["rmse"] = np.sqrt(mean_squared_error(actuals, preds))
        metrics["mae"] = mean_absolute_error(actuals, preds)

        # Betting Metrics (Hit Rate & ROI)
        if "spread_line" in df_clean.columns:
            vegas_line = df_clean["spread_line"]
            vegas_margin = -1 * vegas_line

            bet_home = preds > vegas_margin
            bet_away = preds < vegas_margin

            home_cover = actuals > vegas_margin
            away_cover = actuals < vegas_margin

            wins = (bet_home & home_cover) | (bet_away & away_cover)
            losses = (bet_home & away_cover) | (bet_away & home_cover)

            n_bets = wins.sum() + losses.sum()
            if n_bets > 0:
                hit_rate = wins.sum() / n_bets
                profit = (wins.sum() * 0.90909) - losses.sum()
                roi = profit / n_bets

                metrics["hit_rate"] = hit_rate
                metrics["roi"] = roi
                metrics["n_bets"] = n_bets
            else:
                metrics["hit_rate"] = 0.0
                metrics["roi"] = 0.0
                metrics["n_bets"] = 0

        return metrics

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # XGBoost requires .json or .ubj extension usually, or just use save_model
        save_path = str(path)
        if not save_path.endswith(".json"):
            save_path += ".json"
        self.model.save_model(save_path)
