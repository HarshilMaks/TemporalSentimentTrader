"""TFT and LSTM training on 30-day sequences with MLflow tracking.

Rewritten from TensorFlow to PyTorch to match the runtime model in
``backend/ml/models/tft_model.py``.  Both training and inference now
use the same framework — no mixed dependencies.

Usage::

    trainer = TFTTrainer()
    trainer.prepare_sequences(X, y, seq_length=30)
    tft_results = trainer.train_tft()
    lstm_results = trainer.train_lstm()
    trainer.compare_with_baseline()
    trainer.end_experiment()
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import psutil
import torch
import torch.nn as nn
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

from backend.ml.tracking.mlflow_logger import get_mlflow_logger

logger = logging.getLogger(__name__)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


# ── Sequence builder ────────────────────────────────────────────────────────

class SequenceBuilder:
    """Convert flat features into overlapping sequences for deep learning."""

    def __init__(self, seq_length: int = 30):
        self.seq_length = seq_length
        self.scaler = StandardScaler()

    def build_sequences(
        self, X: np.ndarray, y: np.ndarray, test_split: float = 0.2,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        X_scaled = self.scaler.fit_transform(X)
        X_seq, y_seq = [], []
        for i in range(len(X_scaled) - self.seq_length):
            X_seq.append(X_scaled[i : i + self.seq_length])
            y_seq.append(y[i + self.seq_length])
        X_seq = np.array(X_seq)
        y_seq = np.array(y_seq)
        split = int(len(X_seq) * (1 - test_split))
        return X_seq[:split], X_seq[split:], y_seq[:split], y_seq[split:]


# ── PyTorch models ──────────────────────────────────────────────────────────

class _TFTBlock(nn.Module):
    """Simplified Temporal Fusion Transformer: Dense → MultiHeadAttention → FFN → Pool → Output."""

    def __init__(self, n_features: int, hidden: int = 64, n_heads: int = 4):
        super().__init__()
        self.input_proj = nn.Linear(n_features, hidden)
        self.attn = nn.MultiheadAttention(hidden, n_heads, dropout=0.2, batch_first=True)
        self.norm1 = nn.LayerNorm(hidden)
        self.ffn = nn.Sequential(
            nn.Linear(hidden, hidden * 2), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden * 2, hidden),
        )
        self.norm2 = nn.LayerNorm(hidden)
        self.head = nn.Sequential(
            nn.Linear(hidden, hidden // 2), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_proj(x)
        attn_out, _ = self.attn(x, x, x)
        x = self.norm1(x + attn_out)
        x = self.norm2(x + self.ffn(x))
        x = x.mean(dim=1)  # global average pooling over sequence
        return self.head(x)


class _LSTMRegressor(nn.Module):
    """2-layer LSTM regressor for comparison."""

    def __init__(self, n_features: int, hidden: int = 64):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden, num_layers=2, batch_first=True, dropout=0.2)
        self.head = nn.Sequential(
            nn.Linear(hidden, hidden // 2), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden // 2, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (h_n, _) = self.lstm(x)
        return self.head(h_n[-1])


# ── Trainer ─────────────────────────────────────────────────────────────────

class TFTTrainer:
    """Trains TFT and LSTM models on sequential data with MLflow logging."""

    def __init__(self, exp_name: str = "tft_training", tracking_uri: Optional[str] = None):
        self.logger = get_mlflow_logger(exp_name, f"tft_{int(time.time())}", "tft", "deep_learning")
        self.seq_builder: Optional[SequenceBuilder] = None
        self.models: Dict[str, nn.Module] = {}
        self.results: Dict[str, Dict] = {}
        self.X_train_seq: Optional[np.ndarray] = None
        self.X_test_seq: Optional[np.ndarray] = None
        self.y_train_seq: Optional[np.ndarray] = None
        self.y_test_seq: Optional[np.ndarray] = None
        self.baseline_results: Optional[Dict] = None

    def prepare_sequences(
        self, X: np.ndarray, y: np.ndarray, seq_length: int = 30, test_split: float = 0.2,
    ):
        self.seq_builder = SequenceBuilder(seq_length)
        self.X_train_seq, self.X_test_seq, self.y_train_seq, self.y_test_seq = (
            self.seq_builder.build_sequences(X, y, test_split)
        )
        logger.info(f"Sequences: train={self.X_train_seq.shape}, test={self.X_test_seq.shape}")
        self.logger.log_params({
            "sequence_length": seq_length,
            "train_sequences": int(self.X_train_seq.shape[0]),
            "test_sequences": int(self.X_test_seq.shape[0]),
            "num_features": int(self.X_train_seq.shape[2]),
        })

    # ── internal helpers ────────────────────────────────────────────────────

    def _train_model(
        self, model: nn.Module, tag: str, epochs: int, batch_size: int, lr: float,
    ) -> Dict[str, Any]:
        model = model.to(DEVICE)
        optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        criterion = nn.MSELoss()

        X_t = torch.FloatTensor(self.X_train_seq).to(DEVICE)
        y_t = torch.FloatTensor(self.y_train_seq).unsqueeze(1).to(DEVICE)
        dataset = torch.utils.data.TensorDataset(X_t, y_t)
        loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

        start_time = time.time()
        start_mem = psutil.Process().memory_info().rss / 1024 / 1024

        model.train()
        final_loss = 0.0
        for epoch in range(epochs):
            total_loss = 0.0
            for xb, yb in loader:
                optimizer.zero_grad()
                loss = criterion(model(xb), yb)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            final_loss = total_loss / len(loader)
            if (epoch + 1) % 5 == 0:
                logger.info(f"[{tag}] Epoch {epoch+1}/{epochs}  loss={final_loss:.4f}")

        training_time = time.time() - start_time
        peak_mem = psutil.Process().memory_info().rss / 1024 / 1024

        # Evaluate
        model.eval()
        with torch.no_grad():
            X_test_t = torch.FloatTensor(self.X_test_seq).to(DEVICE)
            y_pred = model(X_test_t).cpu().numpy().flatten()

        mse = mean_squared_error(self.y_test_seq, y_pred)
        mae = mean_absolute_error(self.y_test_seq, y_pred)
        r2 = r2_score(self.y_test_seq, y_pred)

        metrics = {
            f"{tag}.training_time_seconds": training_time,
            f"{tag}.memory_used_mb": peak_mem - start_mem,
            f"{tag}.peak_memory_mb": peak_mem,
            f"{tag}.test_mse": float(mse),
            f"{tag}.test_mae": float(mae),
            f"{tag}.test_r2": float(r2),
            f"{tag}.test_rmse": float(np.sqrt(mse)),
            f"{tag}.final_train_loss": final_loss,
        }
        self.logger.log_metrics_final(metrics)

        result = {
            "model": model, "training_time": training_time,
            "memory_used": peak_mem - start_mem,
            "test_mse": mse, "test_mae": mae, "test_r2": r2,
        }
        self.models[tag] = model
        self.results[tag] = result
        logger.info(f"[{tag}] Done: time={training_time:.1f}s  R²={r2:.4f}")
        return result

    # ── public API ──────────────────────────────────────────────────────────

    def train_tft(
        self, epochs: int = 20, batch_size: int = 32, hidden: int = 64, n_heads: int = 4,
    ) -> Dict[str, Any]:
        self.logger.log_params({
            "tft.epochs": epochs, "tft.batch_size": batch_size,
            "tft.hidden": hidden, "tft.n_heads": n_heads,
        })
        model = _TFTBlock(self.X_train_seq.shape[2], hidden, n_heads)
        return self._train_model(model, "tft", epochs, batch_size, lr=0.001)

    def train_lstm(
        self, epochs: int = 20, batch_size: int = 32, lstm_units: int = 64,
    ) -> Dict[str, Any]:
        self.logger.log_params({
            "lstm.epochs": epochs, "lstm.batch_size": batch_size, "lstm.units": lstm_units,
        })
        model = _LSTMRegressor(self.X_train_seq.shape[2], lstm_units)
        return self._train_model(model, "lstm", epochs, batch_size, lr=0.001)

    def set_baseline_results(self, baseline_results: Dict[str, Any]):
        self.baseline_results = baseline_results

    def compare_with_baseline(self) -> Dict[str, Any]:
        comparison = {"timestamp": datetime.now().isoformat(), "models_trained": list(self.results.keys())}
        all_results = dict(self.results)
        if self.baseline_results:
            all_results.update(self.baseline_results)
        for name, r in all_results.items():
            for key in ("test_r2", "test_mae", "training_time", "memory_used"):
                if key in r:
                    comparison[f"{name}_{key}"] = r[key]
        logger.info(f"Comparison:\n{json.dumps(comparison, indent=2, default=str)}")
        return comparison

    def end_experiment(self):
        self.logger.end_run()
        logger.info("TFT training experiment ended")
