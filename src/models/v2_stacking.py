"""Stacking Ensemble Model (Linear + XGBoost + Meta-Learner)."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import KFold


class V2StackingModel:
    def __init__(self, features=None, models=None, meta_model_params=None, cv=5):
        """
        Stacking Ensemble.
        Args:
            features: List of feature names.
            models: List of model configs (base models).
            meta_model_params: Params for the meta-learner (Logistic Regression).
            cv: Number of folds for generating OOF predictions.
        """
        self.features = features
        self.cv = cv
        self.base_model_configs = models if models else []
        self.meta_model_params = meta_model_params if meta_model_params else {}

        # We store trained base models for final inference
        self.final_base_models = []
        # Meta model
        self.meta_model = LogisticRegression(**self.meta_model_params)

    def _get_base_model(self, m_cfg):
        m_type = m_cfg.get("type")
        m_params = m_cfg.get("params", {})

        if m_type == ("linear" or "linear_regression"):
            from src.models.v1_baseline import V1BaselineModel

            return V1BaselineModel(features=self.features, **m_params)
        elif m_type == "xgboost":
            from src.models.v2_xgboost import V2XGBoostModel

            if "early_stopping_rounds" in m_params:
                del m_params["early_stopping_rounds"]
            return V2XGBoostModel(features=self.features, **m_params)
        elif m_type == "catboost":
            from src.models.v2_catboost import V2CatBoostModel

            return V2CatBoostModel(features=self.features, **m_params)
        else:
            raise ValueError(f"Unknown base model type: {m_type}")

    def fit(self, df):
        """
        1. Split df into K-Folds.
        2. For each fold, train base models on train_idx, predict on val_idx.
        3. Collect OOF predictions (meta-features).
        4. Train Meta-Model on OOF predictions -> Target (Cover binary).
        5. Refit Base Models on FULL dataset for future inference.
        """
        # Data Prep
        df_clean = df.dropna(subset=["spread_target", "spread_line"])
        x_data = df_clean[self.features]
        # Target for Regression (Margin)
        y_reg = df_clean["spread_target"]

        # Target for Meta (Did Home Cover?)
        # Home Cover = (Actual Margin + Spread Line) > 0 ?
        # Assuming spread_line is Home +/-. e.g. -7.
        # Margin 10. 10 + (-7) = 3 > 0. Cover.
        vegas_line = df_clean["spread_line"]
        # Wait, usually we bet against the line.
        # Cover = Match Outcome.
        # Let's frame Meta Problem: Should we bet Home?
        # Target = 1 if Home Covers, 0 if Away Covers.

        vegas_margin = -1 * vegas_line
        y_binary = (y_reg > vegas_margin).astype(int)

        print(f"Training Stacking Ensemble (CV={self.cv})...")
        kf = KFold(n_splits=self.cv, shuffle=True, random_state=42)

        oof_preds = np.zeros((len(df_clean), len(self.base_model_configs)))

        # OOF Loop
        for fold, (train_idx, val_idx) in enumerate(kf.split(x_data, y_binary)):
            print(f"  Fold {fold + 1}/{self.cv}")
            # Identify indices

            # Temporary dataframe for fit() compatibility if models expect df
            # Create subset DFs
            df_train_fold = df_clean.iloc[train_idx]
            df_val_fold = df_clean.iloc[val_idx]  # for predict

            for i, m_cfg in enumerate(self.base_model_configs):
                model = self._get_base_model(m_cfg)
                model.fit(df_train_fold)
                preds = model.predict(df_val_fold)
                oof_preds[val_idx, i] = preds

        # Train Meta-Model on OOF Predictions
        # Input to Meta: [Pred_Model_1, Pred_Model_2, Spread_Line]
        # Including Spread Line provides context (is it a huge underdog?)
        meta_x = pd.DataFrame(
            oof_preds,
            columns=[f"pred_{i}" for i in range(len(self.base_model_configs))],
        )
        meta_x["spread_line"] = vegas_line.values

        print("Training Meta-Model (Logistic Regression)...")
        self.meta_model.fit(meta_x, y_binary)
        print(f"Meta-Model Coefs: {self.meta_model.coef_}")

        # Refit Base Models on Full Data
        self.final_base_models = []
        print("Refitting Base Models on Full Data...")
        for m_cfg in self.base_model_configs:
            model = self._get_base_model(m_cfg)
            model.fit(df_clean)
            self.final_base_models.append(model)

    def predict(self, df):
        # We need to return margin predictions for metrics,
        # BUT our meta-model returns Probability of Cover.
        # To make this compatible with existing 'evaluate' pipeline which expects Margin,
        # we can return the weighted average of base models,
        # OR we can hack it: 'evaluate' calculates metrics from margin.

        # The prompt asks for Stacking to decide *when* to trust.
        # Evaluation usually assumes we bet based on Margin > Line.

        # Let's return the Margin prediction of the "Primary" base model,
        # filtered by the Meta-Model confidence?

        # Or simpler:
        # Return Average Margin of Base Models.
        # But allow acess to 'predict_proba' for betting logic.

        # Existing pipeline just calls evaluate().
        # Let's override evaluate() to use Meta-Model probabilities for betting.

        # For 'predict', let's return average margin for RMSE calculation.
        base_preds = []
        for model in self.final_base_models:
            base_preds.append(model.predict(df))

        return np.mean(base_preds, axis=0)

    def evaluate(self, df):
        df_clean = df.dropna(subset=["spread_target", "spread_line"])
        actuals = df_clean["spread_target"]
        vegas_line = df_clean["spread_line"]
        vegas_margin = -1 * vegas_line

        # Generate Features for Meta-Model
        base_preds = []
        for model in self.final_base_models:
            base_preds.append(model.predict(df_clean))

        # Margin prediction (for RMSE) is simple average
        avg_margin_pred = np.mean(base_preds, axis=0)

        # Meta Inputs
        meta_x = pd.DataFrame(
            np.column_stack(base_preds),
            columns=[f"pred_{i}" for i in range(len(self.base_model_configs))],
        )
        meta_x["spread_line"] = vegas_line.values

        # Meta Probs (Prob of Home Cover)
        probs = self.meta_model.predict_proba(meta_x)[:, 1]

        metrics = {}
        metrics["rmse"] = np.sqrt(mean_squared_error(actuals, avg_margin_pred))
        metrics["mae"] = mean_absolute_error(actuals, avg_margin_pred)

        # Betting Logic using Meta-Probs
        # If Prob(Home Cover) > 0.5 + threshold -> Bet Home
        # If Prob(Home Cover) < 0.5 - threshold -> Bet Away (i.e. Prob Away Cover > 0.5+thresh)

        threshold = 0.0  # Strict > 50%

        bet_home = probs > (0.5 + threshold)
        bet_away = probs < (0.5 - threshold)

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
        print(f"Stacking model saved to {path}")
