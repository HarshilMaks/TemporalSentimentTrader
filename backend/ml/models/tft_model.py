"""TFT/LSTM model wrapper with unified interface for ensemble.

Uses a lightweight PyTorch LSTM for sequence-based classification.
The tft_training.py handles full TFT training with MLflow; this wrapper
provides the predict/save/load interface needed by the ensemble and predictor.
"""

import logging
import pickle
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.warning("PyTorch not available — TFTModel will use fallback averaging")


class _LSTMClassifier(nn.Module):
    """Simple LSTM for BUY/HOLD/SELL classification on 30-day sequences."""

    def __init__(self, n_features: int, hidden: int = 64, n_classes: int = 3):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, num_layers=2, batch_first=True, dropout=0.2)
        self.fc = nn.Sequential(
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden // 2, n_classes),
        )

    def forward(self, x):
        _, (h_n, _) = self.lstm(x)
        return self.fc(h_n[-1])


class TFTModel:
    """Sequence model wrapper matching XGBoostModel/LightGBMModel interface.

    Input to predict/predict_proba must be 3-D: (n_samples, seq_length, n_features).
    """

    def __init__(self, n_features: int = 25, hidden: int = 64, seq_length: int = 30):
        self.n_features = n_features
        self.hidden = hidden
        self.seq_length = seq_length
        self.is_trained = False
        self._model: Optional[Any] = None
        self._device = "cpu"

        if HAS_TORCH:
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = _LSTMClassifier(n_features, hidden).to(self._device)

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 20,
        batch_size: int = 32,
        lr: float = 0.001,
    ):
        if not HAS_TORCH or self._model is None:
            logger.warning("PyTorch unavailable — skipping TFT training")
            return

        self._model.train()
        optimizer = torch.optim.Adam(self._model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()

        X_t = torch.FloatTensor(X_train).to(self._device)
        y_t = torch.LongTensor(y_train).to(self._device)

        dataset = torch.utils.data.TensorDataset(X_t, y_t)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

        for epoch in range(epochs):
            total_loss = 0.0
            for xb, yb in loader:
                optimizer.zero_grad()
                loss = criterion(self._model(xb), yb)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            if (epoch + 1) % 5 == 0:
                logger.info(f"Epoch {epoch+1}/{epochs}  loss={total_loss/len(loader):.4f}")

        self.is_trained = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        proba = self.predict_proba(X)
        return np.argmax(proba, axis=1)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return (n_samples, 3) probabilities for [BUY, HOLD, SELL]."""
        if not HAS_TORCH or self._model is None or not self.is_trained:
            # Fallback: uniform probabilities
            return np.full((len(X), 3), 1.0 / 3)

        self._model.eval()
        with torch.no_grad():
            X_t = torch.FloatTensor(X).to(self._device)
            logits = self._model(X_t)
            proba = torch.softmax(logits, dim=1).cpu().numpy()
        return proba

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if HAS_TORCH and self._model is not None:
            torch.save(
                {"state_dict": self._model.state_dict(), "n_features": self.n_features, "hidden": self.hidden},
                path,
            )
        else:
            with open(path, "wb") as f:
                pickle.dump({"is_trained": self.is_trained}, f)

    def load(self, path: str):
        if HAS_TORCH:
            checkpoint = torch.load(path, map_location=self._device, weights_only=False)
            self.n_features = checkpoint["n_features"]
            self.hidden = checkpoint["hidden"]
            self._model = _LSTMClassifier(self.n_features, self.hidden).to(self._device)
            self._model.load_state_dict(checkpoint["state_dict"])
            self.is_trained = True
        else:
            self.is_trained = False
