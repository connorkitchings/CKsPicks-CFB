"""
This module provides an ensemble model that averages predictions from multiple base models.
"""

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin


class EnsembleModel(BaseEstimator, RegressorMixin):
    """
    A simple ensemble model that averages predictions from multiple base models.
    """

    def __init__(self, models: list):
        self.models = models
        # Expose feature_names_in_ from the first model for compatibility with
        # downstream scripts that check for this attribute.
        if models:
            if hasattr(models[0], "feature_names_in_"):
                self.feature_names_in_ = models[0].feature_names_in_
            elif hasattr(models[0], "feature_names_"):
                self.feature_names_in_ = models[0].feature_names_

    def fit(self, x, y):
        # This wrapper assumes models are already fitted.
        # If we wanted to support fitting, we would loop through models and fit them.
        # Store feature names from the first model if available
        if self.models and hasattr(self.models[0], "feature_names_"):
            self.feature_names_in_ = self.models[0].feature_names_

        return self

    def predict(self, x):
        if not self.models:
            raise ValueError("No models in ensemble.")

        preds = [m.predict(x) for m in self.models]
        return np.mean(preds, axis=0)
