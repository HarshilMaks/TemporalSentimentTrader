"""
Ensemble model training with MLflow experiment tracking.

Trains XGBoost and LightGBM models on preprocessed features, logs all experiments
to MLflow, and saves models with complete metadata including feature snapshot IDs.

Usage:
    from backend.ml.tracking.mlflow_logger import get_mlflow_logger
    from backend.ml.training.train_ensemble import EnsembleTrainer
    
    trainer = EnsembleTrainer()
    xgb_model = trainer.train_xgboost(X_train, y_train)
    lgb_model = trainer.train_lightgbm(X_train, y_train)
"""

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import xgboost as xgb
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import cross_val_score

from backend.ml.tracking.mlflow_logger import get_mlflow_logger

logger = logging.getLogger(__name__)


class EnsembleTrainer:
    """Trains and logs ensemble models with MLflow integration."""

    def __init__(self, exp_name: str = "ensemble_training", tracking_uri: Optional[str] = None):
        """
        Initialize ensemble trainer.

        Args:
            exp_name: MLflow experiment name
            tracking_uri: MLflow tracking server URI (optional)
        """
        self.logger = get_mlflow_logger(exp_name, tracking_uri)
        self.models = {}
        self.feature_snapshot_id = None

    def set_feature_snapshot_id(self, snapshot_id: str):
        """Set the feature snapshot ID for experiment tracking."""
        self.feature_snapshot_id = snapshot_id
        logger.info(f"Feature snapshot ID set to: {snapshot_id}")

    def _log_hyperparameters(self, model_name: str, params: Dict[str, Any]):
        """Log model hyperparameters."""
        prefixed_params = {f"{model_name}.{k}": v for k, v in params.items()}
        self.logger.log_params(prefixed_params)

    def _log_metrics(
        self,
        model_name: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_pred_train: Optional[np.ndarray] = None,
        y_true_train: Optional[np.ndarray] = None,
    ):
        """
        Log model performance metrics.

        Args:
            model_name: Model identifier (xgboost, lightgbm)
            y_true: Ground truth test values
            y_pred: Predicted test values
            y_pred_train: Predicted training values (optional)
            y_true_train: Ground truth training values (optional)
        """
        test_mse = mean_squared_error(y_true, y_pred)
        test_mae = mean_absolute_error(y_true, y_pred)
        test_r2 = r2_score(y_true, y_pred)

        metrics = {
            f"{model_name}.test_mse": float(test_mse),
            f"{model_name}.test_mae": float(test_mae),
            f"{model_name}.test_r2": float(test_r2),
            f"{model_name}.test_rmse": float(np.sqrt(test_mse)),
        }

        if y_pred_train is not None and y_true_train is not None:
            train_mse = mean_squared_error(y_true_train, y_pred_train)
            train_mae = mean_absolute_error(y_true_train, y_pred_train)
            train_r2 = r2_score(y_true_train, y_pred_train)

            metrics.update(
                {
                    f"{model_name}.train_mse": float(train_mse),
                    f"{model_name}.train_mae": float(train_mae),
                    f"{model_name}.train_r2": float(train_r2),
                    f"{model_name}.train_rmse": float(np.sqrt(train_mse)),
                }
            )

        self.logger.log_metrics_final(metrics)
        logger.info(f"Logged metrics for {model_name}: {metrics}")

    def train_xgboost(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: Optional[np.ndarray] = None,
        y_test: Optional[np.ndarray] = None,
        hyperparams: Optional[Dict[str, Any]] = None,
        cv_folds: int = 5,
    ) -> xgb.XGBRegressor:
        """
        Train XGBoost model with MLflow logging.

        Args:
            X_train: Training features
            y_train: Training target
            X_test: Test features (optional)
            y_test: Test target (optional)
            hyperparams: XGBoost hyperparameters (optional)
            cv_folds: Number of cross-validation folds

        Returns:
            Trained XGBoost model
        """
        default_params = {
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
        }

        if hyperparams:
            default_params.update(hyperparams)

        self._log_hyperparameters("xgboost", default_params)

        logger.info("Training XGBoost model...")
        model = xgb.XGBRegressor(**default_params)
        model.fit(X_train, y_train, eval_metric="mae", verbose=False)

        y_pred_train = model.predict(X_train)

        cv_scores = cross_val_score(model, X_train, y_train, cv=cv_folds, scoring="r2")
        self.logger.log_metrics_final(
            {
                "xgboost.cv_mean_r2": float(cv_scores.mean()),
                "xgboost.cv_std_r2": float(cv_scores.std()),
            }
        )

        if X_test is not None and y_test is not None:
            y_pred_test = model.predict(X_test)
            self._log_metrics("xgboost", y_test, y_pred_test, y_pred_train, y_train)

        self.models["xgboost"] = model
        logger.info("XGBoost training completed")
        return model

    def train_lightgbm(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: Optional[np.ndarray] = None,
        y_test: Optional[np.ndarray] = None,
        hyperparams: Optional[Dict[str, Any]] = None,
        cv_folds: int = 5,
    ) -> LGBMRegressor:
        """
        Train LightGBM model with MLflow logging.

        Args:
            X_train: Training features
            y_train: Training target
            X_test: Test features (optional)
            y_test: Test target (optional)
            hyperparams: LightGBM hyperparameters (optional)
            cv_folds: Number of cross-validation folds

        Returns:
            Trained LightGBM model
        """
        default_params = {
            "n_estimators": 100,
            "max_depth": 6,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
            "verbose": -1,
        }

        if hyperparams:
            default_params.update(hyperparams)

        self._log_hyperparameters("lightgbm", default_params)

        logger.info("Training LightGBM model...")
        model = LGBMRegressor(**default_params)
        model.fit(X_train, y_train)

        y_pred_train = model.predict(X_train)

        cv_scores = cross_val_score(model, X_train, y_train, cv=cv_folds, scoring="r2")
        self.logger.log_metrics_final(
            {
                "lightgbm.cv_mean_r2": float(cv_scores.mean()),
                "lightgbm.cv_std_r2": float(cv_scores.std()),
            }
        )

        if X_test is not None and y_test is not None:
            y_pred_test = model.predict(X_test)
            self._log_metrics("lightgbm", y_test, y_pred_test, y_pred_train, y_train)

        self.models["lightgbm"] = model
        logger.info("LightGBM training completed")
        return model

    def save_model(
        self,
        model: Any,
        model_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        save_dir: Optional[Path] = None,
    ) -> Path:
        """
        Save trained model with metadata.

        Args:
            model: Trained model object
            model_name: Model identifier
            metadata: Additional metadata to save
            save_dir: Directory to save model (optional)

        Returns:
            Path to saved model
        """
        if save_dir is None:
            save_dir = Path("models") / datetime.now().strftime("%Y%m%d_%H%M%S")

        save_dir.mkdir(parents=True, exist_ok=True)

        model_path = save_dir / f"{model_name}_model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        metadata_dict = {
            "model_name": model_name,
            "feature_snapshot_id": self.feature_snapshot_id,
            "trained_at": datetime.now().isoformat(),
            **(metadata or {}),
        }

        metadata_path = save_dir / f"{model_name}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata_dict, f, indent=2)

        self.logger.log_artifact(str(model_path))
        self.logger.log_artifact(str(metadata_path))

        logger.info(f"Model saved to {model_path}")
        logger.info(f"Metadata saved to {metadata_path}")

        return model_path

    def train_ensemble(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: Optional[np.ndarray] = None,
        y_test: Optional[np.ndarray] = None,
        xgb_params: Optional[Dict[str, Any]] = None,
        lgb_params: Optional[Dict[str, Any]] = None,
        save_models: bool = True,
        save_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Train full ensemble (XGBoost + LightGBM) with MLflow logging.

        Args:
            X_train: Training features
            y_train: Training target
            X_test: Test features (optional)
            y_test: Test target (optional)
            xgb_params: XGBoost hyperparameters (optional)
            lgb_params: LightGBM hyperparameters (optional)
            save_models: Whether to save trained models
            save_dir: Directory to save models (optional)

        Returns:
            Dictionary with trained models and results
        """
        logger.info("=" * 60)
        logger.info("Starting ensemble training pipeline")
        logger.info("=" * 60)

        if self.feature_snapshot_id:
            self.logger.log_params({"feature_snapshot_id": self.feature_snapshot_id})

        xgb_model = self.train_xgboost(X_train, y_train, X_test, y_test, xgb_params)

        lgb_model = self.train_lightgbm(X_train, y_train, X_test, y_test, lgb_params)

        results = {"xgboost": xgb_model, "lightgbm": lgb_model}

        if save_models:
            self.save_model(xgb_model, "xgboost", save_dir=save_dir)
            self.save_model(lgb_model, "lightgbm", save_dir=save_dir)

        logger.info("=" * 60)
        logger.info("Ensemble training completed")
        logger.info("=" * 60)

        return results

    def end_experiment(self):
        """End the MLflow experiment run."""
        self.logger.end_run()
        logger.info("MLflow run ended")
