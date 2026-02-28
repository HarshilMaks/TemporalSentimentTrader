"""Predictor — loads ensemble models and runs inference."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from backend.ml.models.ensemble import EnsembleModel

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = "data/models/ensemble_latest"


class Predictor:
    """Load trained ensemble and produce predictions."""

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir or DEFAULT_MODEL_DIR
        self.ensemble: Optional[EnsembleModel] = None

    def load_models(self) -> bool:
        """Load ensemble from saved artifacts. Returns True if successful."""
        path = Path(self.model_dir)
        if not path.exists():
            logger.warning(f"Model directory not found: {path}. Using untrained ensemble.")
            self.ensemble = EnsembleModel()
            return False

        try:
            self.ensemble = EnsembleModel()
            self.ensemble.load(str(path))
            logger.info(f"Ensemble loaded from {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load models: {e}")
            self.ensemble = EnsembleModel()
            return False

    def predict_single(
        self, ticker: str, features: np.ndarray, features_seq: Optional[np.ndarray] = None
    ) -> Dict:
        """Predict for a single ticker.

        Args:
            ticker: Stock symbol
            features: 1-D feature vector (n_features,)
            features_seq: Optional 3-D sequence (1, seq_len, n_features) for TFT

        Returns:
            Dict with signal, confidence, per-model probabilities.
        """
        if self.ensemble is None:
            self.load_models()

        X_flat = features.reshape(1, -1)
        X_seq = features_seq if features_seq is not None else None

        results = self.ensemble.predict(X_flat, X_seq)
        result = results[0]
        result["ticker"] = ticker
        return result

    def predict_batch(
        self,
        tickers: List[str],
        features_matrix: np.ndarray,
        sequences: Optional[np.ndarray] = None,
    ) -> List[Dict]:
        """Predict for multiple tickers.

        Args:
            tickers: List of stock symbols
            features_matrix: (n_tickers, n_features)
            sequences: Optional (n_tickers, seq_len, n_features) for TFT

        Returns:
            List of prediction dicts, one per ticker.
        """
        if self.ensemble is None:
            self.load_models()

        results = self.ensemble.predict(features_matrix, sequences)
        for i, ticker in enumerate(tickers):
            results[i]["ticker"] = ticker
        return results
