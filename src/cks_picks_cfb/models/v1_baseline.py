"""Baseline linear model implementation for Day 1."""

from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error


class V1BaselineModel:
    def __init__(
        self,
        alpha=1.0,
        features=None,
        target="spread_target",
        l1_ratio=None,
        fit_intercept=True,
    ):
        # If l1_ratio is provided, use ElasticNet; otherwise, Ridge
        if l1_ratio is not None:
            self.model = ElasticNet(
                alpha=alpha, l1_ratio=l1_ratio, fit_intercept=fit_intercept
            )
        else:
            self.model = Ridge(alpha=alpha, fit_intercept=fit_intercept)
        self.target = target
        if not features:
            raise ValueError("V1BaselineModel requires a 'features' list.")
        self.features = features

    def fit(self, df):
        # Drop rows with missing target
        df_clean = df.dropna(subset=[self.target])
        x = df_clean[self.features].replace([np.inf, -np.inf], 0).fillna(0)
        y = df_clean[self.target]

        print(f"DEBUG: X shape: {x.shape}, Y shape: {y.shape}")
        print("DEBUG: Feature Stats:")
        print(x.describe())
        print(f"DEBUG: Y min: {y.min()}, Y max: {y.max()}")

        self.model.fit(x, y)
        print("Model trained.")
        print(f"Coefficients: {dict(zip(self.features, self.model.coef_))}")
        print(f"Intercept: {self.model.intercept_}")

    def predict(self, df):
        x = df[self.features].replace([np.inf, -np.inf], 0).fillna(0)
        print(f"DEBUG PREDICT: X shape: {x.shape}")
        print(f"DEBUG PREDICT: X min: {x.min().values}, X max: {x.max().values}")
        return self.model.predict(x)

    def evaluate(self, df):
        # Drop rows with missing target for evaluation
        df_clean = df.dropna(subset=[self.target])
        preds = self.predict(df_clean)
        actuals = df_clean[self.target]

        # Metrics
        rmse = np.sqrt(mean_squared_error(actuals, preds))
        mae = mean_absolute_error(actuals, preds)

        metrics = {"rmse": rmse, "mae": mae}

        wins = 0
        losses = 0
        n_bets = 0

        if self.target == "spread_target" and "spread_line" in df_clean.columns:
            vegas_line = df_clean["spread_line"]
            vegas_margin = -1 * vegas_line
            bet_home = preds > vegas_margin
            bet_away = preds < vegas_margin
            home_cover = actuals > vegas_margin
            away_cover = actuals < vegas_margin

            wins = (bet_home & home_cover) | (bet_away & away_cover)
            losses = (bet_home & away_cover) | (bet_away & home_cover)

        elif self.target == "total_target" and "total_line" in df_clean.columns:
            vegas_line = df_clean["total_line"]
            bet_over = preds > vegas_line
            bet_under = preds < vegas_line

            outcome_over = actuals > vegas_line
            outcome_under = actuals < vegas_line

            wins = (bet_over & outcome_over) | (bet_under & outcome_under)
            losses = (bet_over & outcome_under) | (bet_under & outcome_over)

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
        joblib.dump(self.model, path)
        print(f"Model saved to {path}")

    def load(self, path):
        self.model = joblib.load(path)
        print(f"Model loaded from {path}")
