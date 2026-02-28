"""LightGBM model wrapper with unified interface for ensemble."""

import pickle
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from lightgbm import LGBMClassifier

logger = logging.getLogger(__name__)

DEFAULT_PARAMS = {
    "n_estimators": 150,
    "num_leaves": 31,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "verbose": -1,
}


class LightGBMModel:
    """LightGBM wrapper for BUY/SELL/HOLD classification."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        merged = {**DEFAULT_PARAMS, **(params or {})}
        self.model = LGBMClassifier(objective="multiclass", num_class=3, **merged)
        self.is_trained = False

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ):
        fit_kwargs: Dict[str, Any] = {}
        if X_val is not None and y_val is not None:
            fit_kwargs["eval_set"] = [(X_val, y_val)]
        self.model.fit(X_train, y_train, **fit_kwargs)
        self.is_trained = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return class labels: 0=BUY, 1=HOLD, 2=SELL."""
        if not self.is_trained:
            return np.ones(len(X), dtype=int)  # HOLD
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return (n_samples, 3) probabilities for [BUY, HOLD, SELL]."""
        if not self.is_trained:
            return np.full((len(X), 3), 1.0 / 3)
        return self.model.predict_proba(X)

    def get_feature_importance(self) -> Optional[np.ndarray]:
        if not self.is_trained:
            return None
        return self.model.feature_importances_

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self.model, f)

    def load(self, path: str):
        with open(path, "rb") as f:
            self.model = pickle.load(f)
        self.is_trained = True
