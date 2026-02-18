"""
Temporal Fusion Transformer (TFT) and advanced model training.

Trains TFT, LSTM, and other deep learning models on 30-day sequences with:
- Performance comparison vs tree models
- Computational cost tracking
- Training time profiling
- Sequence-based time series modeling

Usage:
    from backend.ml.training.tft_training import TFTTrainer
    
    trainer = TFTTrainer()
    trainer.prepare_sequences(X_features, y_targets, seq_length=30)
    tft_results = trainer.train_tft()
    lstm_results = trainer.train_lstm()
    trainer.compare_with_baseline()
    trainer.end_experiment()
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import psutil
import tensorflow as tf
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

from backend.ml.tracking.mlflow_logger import get_mlflow_logger

logger = logging.getLogger(__name__)

try:
    import tensorflow_addons as tfa
    HAS_TFA = True
except ImportError:
    HAS_TFA = False
    logger.warning("tensorflow_addons not available, some features may be limited")


class SequenceBuilder:
    """Convert flat features into sequences for deep learning models."""

    def __init__(self, seq_length: int = 30):
        """
        Initialize sequence builder.

        Args:
            seq_length: Length of sequences (default 30 days)
        """
        self.seq_length = seq_length
        self.scaler = StandardScaler()

    def build_sequences(
        self,
        X: np.ndarray,
        y: np.ndarray,
        test_split: float = 0.2,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Build overlapping sequences from time series data.

        Args:
            X: Features array (num_samples, num_features)
            y: Target array (num_samples,)
            test_split: Test set fraction

        Returns:
            X_train_seq, X_test_seq, y_train_seq, y_test_seq
        """
        X_scaled = self.scaler.fit_transform(X)

        X_seq = []
        y_seq = []

        for i in range(len(X_scaled) - self.seq_length):
            X_seq.append(X_scaled[i : i + self.seq_length])
            y_seq.append(y[i + self.seq_length])

        X_seq = np.array(X_seq)
        y_seq = np.array(y_seq)

        split_idx = int(len(X_seq) * (1 - test_split))

        return (
            X_seq[:split_idx],
            X_seq[split_idx:],
            y_seq[:split_idx],
            y_seq[split_idx:],
        )


class TFTTrainer:
    """Trains TFT and LSTM models on sequential data."""

    def __init__(
        self,
        exp_name: str = "tft_training",
        tracking_uri: Optional[str] = None,
    ):
        """
        Initialize TFT trainer.

        Args:
            exp_name: MLflow experiment name
            tracking_uri: MLflow tracking server URI (optional)
        """
        self.logger = get_mlflow_logger(exp_name, tracking_uri)
        self.seq_builder = None
        self.models = {}
        self.results = {}
        self.X_train_seq = None
        self.X_test_seq = None
        self.y_train_seq = None
        self.y_test_seq = None
        self.baseline_results = None

    def prepare_sequences(
        self,
        X: np.ndarray,
        y: np.ndarray,
        seq_length: int = 30,
        test_split: float = 0.2,
    ):
        """
        Prepare sequential data for deep learning models.

        Args:
            X: Features array
            y: Target array
            seq_length: Sequence length
            test_split: Test set fraction
        """
        self.seq_builder = SequenceBuilder(seq_length)
        self.X_train_seq, self.X_test_seq, self.y_train_seq, self.y_test_seq = (
            self.seq_builder.build_sequences(X, y, test_split)
        )

        logger.info(
            f"Sequences prepared: train_shape={self.X_train_seq.shape}, "
            f"test_shape={self.X_test_seq.shape}"
        )

        self.logger.log_params(
            {
                "sequence_length": seq_length,
                "train_sequences": int(self.X_train_seq.shape[0]),
                "test_sequences": int(self.X_test_seq.shape[0]),
                "num_features": int(self.X_train_seq.shape[2]),
            }
        )

    def _get_system_metrics(self) -> Dict[str, float]:
        """Get current CPU and memory usage."""
        process = psutil.Process()
        return {
            "cpu_percent": float(process.cpu_percent()),
            "memory_mb": float(process.memory_info().rss / 1024 / 1024),
        }

    def _build_tft_model(
        self,
        seq_length: int,
        num_features: int,
        hidden_units: int = 64,
        num_heads: int = 4,
    ) -> tf.keras.Model:
        """
        Build Temporal Fusion Transformer model.

        Args:
            seq_length: Sequence length
            num_features: Number of input features
            hidden_units: Hidden layer units
            num_heads: Attention heads

        Returns:
            Compiled Keras model
        """
        inputs = tf.keras.Input(shape=(seq_length, num_features))

        x = tf.keras.layers.Dense(hidden_units, activation="relu")(inputs)
        x = tf.keras.layers.Dropout(0.2)(x)

        # Multi-head self-attention
        mha = tf.keras.layers.MultiHeadAttention(
            num_heads=num_heads,
            key_dim=hidden_units // num_heads,
            dropout=0.2,
        )
        attn_output = mha(x, x)
        attn_output = tf.keras.layers.Add()([x, attn_output])
        attn_output = tf.keras.layers.LayerNormalization()(attn_output)

        # Feed-forward network
        ffn = tf.keras.Sequential([
            tf.keras.layers.Dense(hidden_units * 2, activation="relu"),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(hidden_units),
        ])
        ffn_output = ffn(attn_output)
        x = tf.keras.layers.Add()([attn_output, ffn_output])
        x = tf.keras.layers.LayerNormalization()(x)

        x = tf.keras.layers.GlobalAveragePooling1D()(x)
        x = tf.keras.layers.Dense(hidden_units // 2, activation="relu")(x)
        x = tf.keras.layers.Dropout(0.2)(x)
        outputs = tf.keras.layers.Dense(1)(x)

        model = tf.keras.Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss="mse",
            metrics=["mae"],
        )

        return model

    def _build_lstm_model(
        self,
        seq_length: int,
        num_features: int,
        lstm_units: int = 64,
    ) -> tf.keras.Model:
        """
        Build LSTM model for comparison.

        Args:
            seq_length: Sequence length
            num_features: Number of input features
            lstm_units: LSTM units

        Returns:
            Compiled Keras model
        """
        inputs = tf.keras.Input(shape=(seq_length, num_features))

        x = tf.keras.layers.LSTM(lstm_units, activation="relu", return_sequences=True)(inputs)
        x = tf.keras.layers.Dropout(0.2)(x)
        x = tf.keras.layers.LSTM(lstm_units // 2, activation="relu")(x)
        x = tf.keras.layers.Dropout(0.2)(x)
        x = tf.keras.layers.Dense(lstm_units // 2, activation="relu")(x)
        x = tf.keras.layers.Dropout(0.2)(x)
        outputs = tf.keras.layers.Dense(1)(x)

        model = tf.keras.Model(inputs=inputs, outputs=outputs)
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss="mse",
            metrics=["mae"],
        )

        return model

    def train_tft(
        self,
        epochs: int = 20,
        batch_size: int = 32,
        hidden_units: int = 64,
        num_heads: int = 4,
    ) -> Dict[str, Any]:
        """
        Train Temporal Fusion Transformer.

        Args:
            epochs: Number of training epochs
            batch_size: Batch size
            hidden_units: Hidden layer units
            num_heads: Attention heads

        Returns:
            Training results dictionary
        """
        logger.info("Building TFT model...")
        model = self._build_tft_model(
            self.X_train_seq.shape[1],
            self.X_train_seq.shape[2],
            hidden_units,
            num_heads,
        )

        self.logger.log_params({
            "tft.epochs": epochs,
            "tft.batch_size": batch_size,
            "tft.hidden_units": hidden_units,
            "tft.num_heads": num_heads,
        })

        logger.info("Training TFT model...")
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024

        history = model.fit(
            self.X_train_seq,
            self.y_train_seq,
            batch_size=batch_size,
            epochs=epochs,
            validation_split=0.2,
            verbose=0,
        )

        training_time = time.time() - start_time
        peak_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_used = peak_memory - start_memory

        y_pred_test = model.predict(self.X_test_seq, verbose=0)
        mse = mean_squared_error(self.y_test_seq, y_pred_test)
        mae = mean_absolute_error(self.y_test_seq, y_pred_test)
        r2 = r2_score(self.y_test_seq, y_pred_test)

        metrics = {
            "tft.training_time_seconds": float(training_time),
            "tft.memory_used_mb": float(memory_used),
            "tft.peak_memory_mb": float(peak_memory),
            "tft.test_mse": float(mse),
            "tft.test_mae": float(mae),
            "tft.test_r2": float(r2),
            "tft.test_rmse": float(np.sqrt(mse)),
            "tft.final_train_loss": float(history.history["loss"][-1]),
            "tft.final_val_loss": float(history.history["val_loss"][-1]),
        }

        self.logger.log_metrics_final(metrics)

        results = {
            "model": model,
            "history": history,
            "training_time": training_time,
            "memory_used": memory_used,
            "test_mse": mse,
            "test_mae": mae,
            "test_r2": r2,
        }

        self.models["tft"] = model
        self.results["tft"] = results

        logger.info(
            f"TFT training completed: time={training_time:.2f}s, "
            f"memory={memory_used:.2f}MB, R²={r2:.4f}"
        )

        return results

    def train_lstm(
        self,
        epochs: int = 20,
        batch_size: int = 32,
        lstm_units: int = 64,
    ) -> Dict[str, Any]:
        """
        Train LSTM model for comparison.

        Args:
            epochs: Number of training epochs
            batch_size: Batch size
            lstm_units: LSTM units

        Returns:
            Training results dictionary
        """
        logger.info("Building LSTM model...")
        model = self._build_lstm_model(
            self.X_train_seq.shape[1],
            self.X_train_seq.shape[2],
            lstm_units,
        )

        self.logger.log_params({
            "lstm.epochs": epochs,
            "lstm.batch_size": batch_size,
            "lstm.lstm_units": lstm_units,
        })

        logger.info("Training LSTM model...")
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024

        history = model.fit(
            self.X_train_seq,
            self.y_train_seq,
            batch_size=batch_size,
            epochs=epochs,
            validation_split=0.2,
            verbose=0,
        )

        training_time = time.time() - start_time
        peak_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_used = peak_memory - start_memory

        y_pred_test = model.predict(self.X_test_seq, verbose=0)
        mse = mean_squared_error(self.y_test_seq, y_pred_test)
        mae = mean_absolute_error(self.y_test_seq, y_pred_test)
        r2 = r2_score(self.y_test_seq, y_pred_test)

        metrics = {
            "lstm.training_time_seconds": float(training_time),
            "lstm.memory_used_mb": float(memory_used),
            "lstm.peak_memory_mb": float(peak_memory),
            "lstm.test_mse": float(mse),
            "lstm.test_mae": float(mae),
            "lstm.test_r2": float(r2),
            "lstm.test_rmse": float(np.sqrt(mse)),
            "lstm.final_train_loss": float(history.history["loss"][-1]),
            "lstm.final_val_loss": float(history.history["val_loss"][-1]),
        }

        self.logger.log_metrics_final(metrics)

        results = {
            "model": model,
            "history": history,
            "training_time": training_time,
            "memory_used": memory_used,
            "test_mse": mse,
            "test_mae": mae,
            "test_r2": r2,
        }

        self.models["lstm"] = model
        self.results["lstm"] = results

        logger.info(
            f"LSTM training completed: time={training_time:.2f}s, "
            f"memory={memory_used:.2f}MB, R²={r2:.4f}"
        )

        return results

    def set_baseline_results(self, baseline_results: Dict[str, Any]):
        """
        Set baseline model results for comparison.

        Args:
            baseline_results: Dictionary with xgboost/lightgbm results
        """
        self.baseline_results = baseline_results
        logger.info("Baseline results set for comparison")

    def compare_with_baseline(self) -> Dict[str, Any]:
        """
        Compare deep learning models with baseline (tree) models.

        Returns:
            Comparison summary
        """
        comparison = {
            "timestamp": datetime.now().isoformat(),
            "models_trained": list(self.results.keys()),
        }

        all_results = dict(self.results)
        if self.baseline_results:
            all_results.update(self.baseline_results)

        # Build comparison metrics
        for model_name, result in all_results.items():
            if "test_r2" in result:
                comparison[f"{model_name}_r2"] = result["test_r2"]
            if "test_mae" in result:
                comparison[f"{model_name}_mae"] = result["test_mae"]
            if "training_time" in result:
                comparison[f"{model_name}_training_time_s"] = result["training_time"]
            if "memory_used" in result:
                comparison[f"{model_name}_memory_used_mb"] = result["memory_used"]

        logger.info(f"Model comparison:\n{json.dumps(comparison, indent=2, default=str)}")
        return comparison

    def end_experiment(self):
        """End the MLflow experiment run."""
        self.logger.end_run()
        logger.info("TFT training experiment ended")
