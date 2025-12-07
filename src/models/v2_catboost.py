from pathlib import Path

"""CatBoost Model Wrapper for V2 Pipeline."""
import numpy as np
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


class V2CatBoostModel:
    def __init__(self, features=None, **params):
        """
        Wrapper for CatBoostRegressor.
        Args:
            features: List of feature names to use.
            **params: CatBoost hyperparameters.
        """
        self.features = features
        self.model = CatBoostRegressor(**params)
        self.params = params

    def fit(self, df):
        # Drop rows with missing target
        df_clean = df.dropna(subset=["spread_target"])

        # Select features
        if self.features:
            x = df_clean[self.features]
        else:
            # Fallback if no features specified (shouldn't happen in V2)
            raise ValueError("V2CatBoostModel requires explicit features list")

        y = df_clean["spread_target"]

        print(f"DEBUG: X shape: {x.shape}, Y shape: {y.shape}")

        # Fit model
        self.model.fit(x, y, verbose=100)

    def predict(self, df):
        if self.features:
            x = df[self.features]
        else:
            raise ValueError("V2CatBoostModel requires explicit features list")

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
            # spread_line is Home Spread (e.g. -7 means Home favored by 7)
            # We predict Home Margin (Home - Away)
            # Vegas Margin = -1 * spread_line (e.g. -7 line -> Vegas expects +7 margin)
            vegas_line = df_clean["spread_line"]
            vegas_margin = -1 * vegas_line

            # Bet Home if Pred Margin > Vegas Margin
            bet_home = preds > vegas_margin
            bet_away = preds < vegas_margin

            # Outcome
            home_cover = actuals > vegas_margin
            away_cover = actuals < vegas_margin

            wins = (bet_home & home_cover) | (bet_away & away_cover)
            losses = (bet_home & away_cover) | (bet_away & home_cover)

            n_bets = wins.sum() + losses.sum()
            if n_bets > 0:
                hit_rate = wins.sum() / n_bets
                # ROI at -110
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
        self.model.save_model(str(path))
