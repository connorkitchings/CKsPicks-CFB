"""CatBoost Classifier for direct P(Cover) prediction.

Unlike the regression models (which predict point margin then derive cover probability),
this model directly predicts the probability that the home team covers the spread.

Target: 1 if Home covers (actual_margin > vegas_margin), 0 otherwise
Betting logic: bet home if P(Cover) > 0.524 (breakeven), away if P(Cover) < 0.476
"""

from pathlib import Path

from catboost import CatBoostClassifier
from sklearn.metrics import log_loss, roc_auc_score


class V2ClassifierModel:
    def __init__(self, features=None, target="cover_target", **params):
        """
        CatBoost-based classifier for direct cover probability prediction.

        Args:
            features: List of feature names (should include spread_line for context).
            target: Unused - target is always derived from spread_target + spread_line.
            **params: CatBoost hyperparameters (loss_function should be Logloss).
        """
        self.features = features
        self.target = target  # kept for interface compatibility
        self.params = params
        self.model = CatBoostClassifier(**params)

    def _make_binary_target(self, df):
        """Create binary cover target from spread data.

        home_covered = 1 if home team covers (actual_margin > vegas_margin)
        vegas_margin = -1 * spread_line (e.g. spread_line=-7 → vegas_margin=7)
        """
        vegas_margin = -1 * df["spread_line"]
        return (df["spread_target"] > vegas_margin).astype(int)

    def fit(self, df):
        df_clean = df.dropna(subset=["spread_target", "spread_line"])

        if self.features:
            x = df_clean[self.features]
        else:
            raise ValueError("V2ClassifierModel requires explicit features list")

        y = self._make_binary_target(df_clean)

        cover_rate = y.mean()
        print(f"Cover rate in train: {cover_rate:.3f} ({y.sum()}/{len(y)} games)")

        self.model.fit(x, y, verbose=100)

    def predict_proba(self, df):
        """Return P(home covers) for each game."""
        if self.features:
            x = df[self.features]
        else:
            raise ValueError("V2ClassifierModel requires explicit features list")
        return self.model.predict_proba(x)[:, 1]

    def predict(self, df):
        """Return predicted class (1 = bet home, 0 = bet away). Alias for compatibility."""
        return (self.predict_proba(df) > 0.5).astype(int)

    def evaluate(self, df, threshold=0.024):
        """
        Evaluate classifier performance for betting.

        Args:
            df: Test dataframe with spread_target and spread_line columns.
            threshold: Edge threshold above 50% to place a bet.
                       Default 0.024 → bet when P(Cover) > 0.524 or < 0.476.

        Returns:
            Dictionary of metrics: hit_rate, roi, n_bets, auc, log_loss, calibration_error.
        """
        df_clean = df.dropna(subset=["spread_target", "spread_line"])

        probs = self.predict_proba(df_clean)
        y_true = self._make_binary_target(df_clean)

        vegas_margin = -1 * df_clean["spread_line"]
        actuals = df_clean["spread_target"]

        home_cover = actuals > vegas_margin
        away_cover = actuals < vegas_margin

        # Betting logic: bet with edge
        bet_home = probs > (0.5 + threshold)
        bet_away = probs < (0.5 - threshold)

        wins = (bet_home & home_cover) | (bet_away & away_cover)
        losses = (bet_home & away_cover) | (bet_away & home_cover)

        n_bets = int(wins.sum() + losses.sum())
        metrics = {}

        # Betting metrics
        if n_bets > 0:
            metrics["hit_rate"] = float(wins.sum() / n_bets)
            profit = (wins.sum() * 0.90909) - losses.sum()
            metrics["roi"] = float(profit / n_bets)
            metrics["n_bets"] = n_bets
        else:
            metrics["hit_rate"] = 0.0
            metrics["roi"] = 0.0
            metrics["n_bets"] = 0

        # Classification quality metrics
        metrics["auc"] = float(roc_auc_score(y_true, probs))
        metrics["log_loss"] = float(log_loss(y_true, probs))

        # Calibration: mean predicted prob vs actual cover rate
        metrics["calibration_error"] = float(abs(probs.mean() - y_true.mean()))

        # Coverage stats
        metrics["n_bet_home"] = int(bet_home.sum())
        metrics["n_bet_away"] = int(bet_away.sum())
        metrics["avg_edge"] = (
            float(abs(probs - 0.5)[bet_home | bet_away].mean()) if n_bets > 0 else 0.0
        )

        # RMSE/MAE not applicable but add stubs for MLflow schema consistency
        metrics["rmse"] = 0.0
        metrics["mae"] = 0.0

        return metrics

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(path))
