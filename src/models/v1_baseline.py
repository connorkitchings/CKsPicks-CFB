"""Baseline linear model implementation for Day 1."""

from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error


class V1BaselineModel:
    def __init__(self, alpha=1.0):
        self.model = Ridge(alpha=alpha)
        self.features = [
            "home_adj_off_epa_pp",
            "home_adj_def_epa_pp",
            "away_adj_off_epa_pp",
            "away_adj_def_epa_pp",
        ]

    def fit(self, df):
        # Drop rows with missing target
        df_clean = df.dropna(subset=["spread_target"])
        x = df_clean[self.features].fillna(0)
        y = df_clean["spread_target"]

        print(f"DEBUG: X shape: {x.shape}, Y shape: {y.shape}")
        print(f"DEBUG: X min: {x.min().values}, X max: {x.max().values}")
        print(f"DEBUG: Y min: {y.min()}, Y max: {y.max()}")

        self.model.fit(x, y)
        print("Model trained.")
        print(f"Coefficients: {dict(zip(self.features, self.model.coef_))}")
        print(f"Intercept: {self.model.intercept_}")

    def predict(self, df):
        x = df[self.features].fillna(0)
        print(f"DEBUG PREDICT: X shape: {x.shape}")
        print(f"DEBUG PREDICT: X min: {x.min().values}, X max: {x.max().values}")
        return self.model.predict(x)

    def evaluate(self, df):
        # Drop rows with missing target for evaluation
        df_clean = df.dropna(subset=["spread_target"])
        preds = self.predict(df_clean)
        actuals = df_clean["spread_target"]
        rmse = np.sqrt(mean_squared_error(actuals, preds))
        mae = mean_absolute_error(actuals, preds)
        return {"rmse": rmse, "mae": mae}

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, path)
        print(f"Model saved to {path}")
