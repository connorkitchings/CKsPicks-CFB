"""Ensemble Model Wrapper for V2 Pipeline."""

from pathlib import Path

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error


class V2EnsembleModel:
    def __init__(self, features=None, models=None, weights=None):
        """
        Weighted Ensemble Model.
        Args:
            features: List of feature names.
            models: List of model configuration dicts (type, params).
            weights: List of weights (sum to 1.0 recommended).
        """
        self.features = features
        self.weights = weights
        self.sub_models = []

        if not models:
            raise ValueError("V2EnsembleModel requires a list of 'models' configs")

        # Instantiate sub-models
        for m_cfg in models:
            m_type = m_cfg.get("type")
            m_params = m_cfg.get("params", {})

            if m_type == "linear_regression":
                from src.models.v1_baseline import V1BaselineModel

                model = V1BaselineModel(features=features, **m_params)
            elif m_type == "xgboost":
                from src.models.v2_xgboost import V2XGBoostModel

                # cleanup params for XGB
                if "early_stopping_rounds" in m_params:
                    del m_params["early_stopping_rounds"]
                model = V2XGBoostModel(features=features, **m_params)
            elif m_type == "catboost":
                from src.models.v2_catboost import V2CatBoostModel

                model = V2CatBoostModel(features=features, **m_params)
            else:
                raise ValueError(f"Unknown sub-model type in ensemble: {m_type}")

            self.sub_models.append(model)

        if self.weights is None:
            self.weights = [1.0 / len(self.sub_models)] * len(self.sub_models)

        if len(self.weights) != len(self.sub_models):
            raise ValueError("Number of weights must match number of models")

    def fit(self, df):
        print(f"Training Ensemble with {len(self.sub_models)} models...")
        for i, model in enumerate(self.sub_models):
            print(f"Training sub-model {i + 1} ({type(model).__name__})...")
            model.fit(df)

    def predict(self, df):
        # Gather predictions from all models
        preds_list = []
        for model in self.sub_models:
            preds_list.append(model.predict(df))

        # Weighted Average
        final_preds = np.zeros_like(preds_list[0])
        for preds, weight in zip(preds_list, self.weights):
            final_preds += preds * weight

        return final_preds

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
        import joblib

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        print(f"Ensemble model saved to {path}")
        print(f"Ensemble model saved to {path}")
