"""XGBoost Model Wrapper for V2 Pipeline."""

from pathlib import Path

import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error


class V2XGBoostModel:
    def __init__(self, features=None, target="spread_target", **params):
        """
        Wrapper for XGBoostRegressor.
        Args:
            features: List of feature names to use.
            target: The target column name ('spread_target' or 'total_target').
            **params: XGBoost hyperparameters.
        """
        self.features = features
        self.target = target
        self.params = params
        self.model = xgb.XGBRegressor(
            **{k: v for k, v in params.items() if k != "early_stopping_rounds"}
        )

    def fit(self, df):
        df_clean = df.dropna(subset=[self.target])

        if self.features:
            x = df_clean[self.features]
        else:
            raise ValueError("V2XGBoostModel requires explicit features list")

        y = df_clean[self.target]

        early_stopping_rounds = self.params.get("early_stopping_rounds", None)
        if early_stopping_rounds:
            # Simple train/eval split for early stopping, ideally should use a dedicated validation set
            split_idx = int(len(x) * 0.8)
            x_train, x_val = x[:split_idx], x[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]
            self.model.fit(
                x_train,
                y_train,
                eval_set=[(x_val, y_val)],
                early_stopping_rounds=early_stopping_rounds,
                verbose=False,
            )
        else:
            self.model.fit(x, y)

    def predict(self, df):
        if self.features:
            x = df[self.features]
        else:
            raise ValueError("V2XGBoostModel requires explicit features list")

        return self.model.predict(x)

    def evaluate(self, df):
        df_clean = df.dropna(subset=[self.target])
        preds = self.predict(df_clean)
        actuals = df_clean[self.target]

        metrics = {}
        metrics["rmse"] = np.sqrt(mean_squared_error(actuals, preds))
        metrics["mae"] = mean_absolute_error(actuals, preds)

        # Betting Metrics (Hit Rate & ROI)
        if self.target == "spread_target" and "spread_line" in df_clean.columns:
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
        else:
            metrics["hit_rate"] = 0.0
            metrics["roi"] = 0.0
            metrics["n_bets"] = 0

        return metrics

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(path))
