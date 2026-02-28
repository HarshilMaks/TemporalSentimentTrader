"""Ensemble model — weighted voting across XGBoost, LightGBM, and TFT/LSTM."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from backend.ml.models.xgboost_model import XGBoostModel
from backend.ml.models.lightgbm_model import LightGBMModel
from backend.ml.models.tft_model import TFTModel

logger = logging.getLogger(__name__)

SIGNAL_LABELS = {0: "BUY", 1: "HOLD", 2: "SELL"}
WEIGHTS = {"xgboost": 0.40, "lightgbm": 0.30, "tft": 0.30}
CONFIDENCE_THRESHOLD = 0.70  # Production threshold


class EnsembleModel:
    """Weighted voting ensemble for BUY/SELL/HOLD classification.

    XGBoost (40%) + LightGBM (30%) + TFT/LSTM (30%).
    Only emits BUY or SELL when confidence > 0.7, otherwise HOLD.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or WEIGHTS
        self.xgb = XGBoostModel()
        self.lgb = LightGBMModel()
        self.tft = TFTModel()

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        X_train_seq: Optional[np.ndarray] = None,
        y_train_seq: Optional[np.ndarray] = None,
        X_val_seq: Optional[np.ndarray] = None,
        y_val_seq: Optional[np.ndarray] = None,
    ):
        """Train all sub-models.

        Args:
            X_train/y_train: flat feature vectors for tree models
            X_train_seq/y_train_seq: 3-D sequences for TFT/LSTM
        """
        logger.info("Training XGBoost...")
        self.xgb.train(X_train, y_train, X_val, y_val)

        logger.info("Training LightGBM...")
        self.lgb.train(X_train, y_train, X_val, y_val)

        if X_train_seq is not None and y_train_seq is not None:
            logger.info("Training TFT/LSTM...")
            self.tft.train(X_train_seq, y_train_seq, X_val_seq, y_val_seq)
        else:
            logger.info("No sequence data provided — TFT will use uniform fallback")

    def predict(self, X_flat: np.ndarray, X_seq: Optional[np.ndarray] = None) -> List[Dict]:
        """Run ensemble prediction.

        Args:
            X_flat: (n_samples, n_features) for tree models
            X_seq: (n_samples, seq_len, n_features) for TFT — optional

        Returns:
            List of dicts with signal, confidence, and per-model scores.
        """
        proba = self.predict_proba(X_flat, X_seq)
        results = []
        for i in range(len(proba)):
            confidence = float(np.max(proba[i]))
            raw_signal = int(np.argmax(proba[i]))
            # Only emit BUY/SELL if confident enough, else HOLD
            if confidence < CONFIDENCE_THRESHOLD:
                signal = "HOLD"
            else:
                signal = SIGNAL_LABELS[raw_signal]
            results.append({
                "signal": signal,
                "confidence": confidence,
                "buy_prob": float(proba[i][0]),
                "hold_prob": float(proba[i][1]),
                "sell_prob": float(proba[i][2]),
            })
        return results

    def predict_proba(self, X_flat: np.ndarray, X_seq: Optional[np.ndarray] = None) -> np.ndarray:
        """Return weighted-average (n_samples, 3) probabilities."""
        xgb_p = self.xgb.predict_proba(X_flat)
        lgb_p = self.lgb.predict_proba(X_flat)

        if X_seq is not None:
            tft_p = self.tft.predict_proba(X_seq)
        else:
            tft_p = np.full((len(X_flat), 3), 1.0 / 3)

        combined = (
            self.weights["xgboost"] * xgb_p
            + self.weights["lightgbm"] * lgb_p
            + self.weights["tft"] * tft_p
        )
        return combined

    def save(self, directory: str):
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        self.xgb.save(str(d / "xgboost_model.pkl"))
        self.lgb.save(str(d / "lightgbm_model.pkl"))
        self.tft.save(str(d / "lstm_model.pt"))

    def load(self, directory: str):
        d = Path(directory)
        self.xgb.load(str(d / "xgboost_model.pkl"))
        self.lgb.load(str(d / "lightgbm_model.pkl"))
        tft_path = d / "lstm_model.pt"
        if tft_path.exists():
            self.tft.load(str(tft_path))
