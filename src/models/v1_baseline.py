"""Baseline linear model implementation for Day 1."""

from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error


class V1BaselineModel:
    def __init__(self, alpha=1.0, features=None):
        self.model = Ridge(alpha=alpha)
        self.features = (
            features
            if features
            else [
                "home_adj_off_epa_pp",
                "home_adj_def_epa_pp",
                "away_adj_off_epa_pp",
                "away_adj_def_epa_pp",
            ]
        )

    def fit(self, df):
        # Drop rows with missing target
        df_clean = df.dropna(subset=["spread_target"])
        x = df_clean[self.features].replace([np.inf, -np.inf], 0).fillna(0)
        y = df_clean["spread_target"]

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
        df_clean = df.dropna(subset=["spread_target"])
        preds = self.predict(df_clean)
        actuals = df_clean["spread_target"]

        # Metrics
        rmse = np.sqrt(mean_squared_error(actuals, preds))
        mae = mean_absolute_error(actuals, preds)

        # Hit Rate & ROI
        # Bet Home if pred > spread_line?
        # Wait, target is (Home - Away).
        # We are predicting the MARGIN.
        # To calculate betting ROI, we need the Vegas Line (spread_line).
        # If df has 'spread_line' (Home - Away line from Vegas), we can compare.
        # Assuming 'spread_line' column exists (standard in games df).

        metrics = {"rmse": rmse, "mae": mae}

        if "spread_line" in df_clean.columns:
            # My Spread Pred: positive means Home wins by X
            # Vegas Spread Line: usually presented as "Home -7" -> Line is -7?
            # Or "Home +3" -> Line is +3?
            # In our data, 'spread_line' is usually "Home Points - Away Points" expectation?
            # CFBD convention: 'spread_line' is typically Home Team spread.
            # e.g. -7 means Home is favored by 7.
            # So Target (Home - Away) should be compared to -1 * spread_line?
            # Wait. If Home favored by 7, score 27-20. Margin +7.
            # Spread line -7.
            # Margin + Line = 7 + (-7) = 0. Push.
            # So if (Margin + Line) > 0 -> Home Cover.

            # Let's verify convention.
            # If spread_line is -7 (Home Favored).
            # Pred Margin is +10.
            # We think Home wins by 10. Vegas thinks Home wins by 7.
            # We bet Home.
            # If Margin is +10. Home covers. Win.

            vegas_line = df_clean["spread_line"]

            # Edge: Pred Margin - (-1 * Vegas Line)?
            # No, usually spread_line in CFBD is "Home +/-".
            # If spread_line is -7. Vegas says Home Margin is +7.
            # So Vegas Margin = -1 * spread_line.
            vegas_margin = -1 * vegas_line

            # Bet Home if Pred Margin > Vegas Margin
            bet_home = preds > vegas_margin
            bet_away = preds < vegas_margin

            # Outcome
            # Home Cover if Actual Margin > Vegas Margin
            home_cover = actuals > vegas_margin
            away_cover = actuals < vegas_margin

            wins = (bet_home & home_cover) | (bet_away & away_cover)
            losses = (bet_home & away_cover) | (bet_away & home_cover)

            n_bets = wins.sum() + losses.sum()
            if n_bets > 0:
                hit_rate = wins.sum() / n_bets
                # ROI at -110
                # Win: +0.909 units. Loss: -1.0 units.
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
