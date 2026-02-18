"""
Baseline model training for stock price/return prediction.

Trains XGBoost and LightGBM models on engineered features with:
- Feature importance tracking
- Classification metrics (accuracy, precision, recall, F1)
- Regression metrics (MAE, RMSE, R²)
- Financial metrics (Sharpe ratio, max drawdown)

Usage:
    from backend.ml.training.baseline_training import BaselineTrainer
    
    trainer = BaselineTrainer()
    trainer.prepare_data(X, y, problem_type='classification')
    xgb_results = trainer.train_xgboost()
    lgb_results = trainer.train_lightgbm()
    trainer.compare_models()
    trainer.end_experiment()
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
import pandas as pd
import xgboost as xgb
from lightgbm import LGBMRegressor, LGBMClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

from backend.ml.tracking.mlflow_logger import get_mlflow_logger

logger = logging.getLogger(__name__)


def calculate_sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
    """
    Calculate Sharpe ratio from returns.
    
    Args:
        returns: Array of returns
        risk_free_rate: Annual risk-free rate (default 2%)
    
    Returns:
        Sharpe ratio
    """
    if len(returns) < 2:
        return 0.0
    
    excess_returns = returns - risk_free_rate / 252
    return float(np.sqrt(252) * np.mean(excess_returns) / (np.std(excess_returns) + 1e-8))


def calculate_max_drawdown(returns: np.ndarray) -> float:
    """
    Calculate maximum drawdown from returns.
    
    Args:
        returns: Array of returns
    
    Returns:
        Maximum drawdown (negative value)
    """
    cumulative = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (cumulative - running_max) / running_max
    return float(np.min(drawdown))


class BaselineTrainer:
    """Trains baseline (XGBoost + LightGBM) models with comprehensive metrics."""

    def __init__(
        self,
        exp_name: str = "baseline_training",
        tracking_uri: Optional[str] = None,
        problem_type: str = "classification",
    ):
        """
        Initialize baseline trainer.

        Args:
            exp_name: MLflow experiment name
            tracking_uri: MLflow tracking server URI (optional)
            problem_type: 'classification' or 'regression'
        """
        self.logger = get_mlflow_logger(exp_name, tracking_uri)
        self.problem_type = problem_type
        self.models = {}
        self.results = {}
        self.feature_names = None
        self.X_train = None
        self.y_train = None
        self.X_test = None
        self.y_test = None

    def prepare_data(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: Optional[np.ndarray] = None,
        y_test: Optional[np.ndarray] = None,
        feature_names: Optional[list] = None,
    ):
        """Prepare and validate training data."""
        self.X_train = X_train
        self.y_train = y_train
        self.X_test = X_test
        self.y_test = y_test
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X_train.shape[1])]

        logger.info(f"Data prepared: train_shape={X_train.shape}, test_shape={X_test.shape if X_test is not None else None}")

    def _log_classification_metrics(
        self,
        model_name: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_pred_proba: Optional[np.ndarray] = None,
    ):
        """Log classification metrics."""
        metrics = {
            f"{model_name}.accuracy": float(accuracy_score(y_true, y_pred)),
            f"{model_name}.precision": float(precision_score(y_true, y_pred, average="weighted", zero_division=0)),
            f"{model_name}.recall": float(recall_score(y_true, y_pred, average="weighted", zero_division=0)),
            f"{model_name}.f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        }

        self.logger.log_metrics_final(metrics)
        return metrics

    def _log_regression_metrics(
        self,
        model_name: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ):
        """Log regression metrics."""
        mse = mean_squared_error(y_true, y_pred)
        mae = mean_absolute_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)

        metrics = {
            f"{model_name}.mse": float(mse),
            f"{model_name}.rmse": float(np.sqrt(mse)),
            f"{model_name}.mae": float(mae),
            f"{model_name}.r2": float(r2),
        }

        self.logger.log_metrics_final(metrics)
        return metrics

    def _log_financial_metrics(
        self,
        model_name: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ):
        """
        Log financial metrics (Sharpe ratio, max drawdown).
        
        Assumes y_true and y_pred are returns or price changes.
        """
        try:
            sharpe = calculate_sharpe_ratio(y_pred)
            max_dd = calculate_max_drawdown(y_pred)

            metrics = {
                f"{model_name}.sharpe_ratio": float(sharpe),
                f"{model_name}.max_drawdown": float(max_dd),
            }

            self.logger.log_metrics_final(metrics)
            return metrics
        except Exception as e:
            logger.warning(f"Could not calculate financial metrics: {e}")
            return {}

    def _log_feature_importance(
        self,
        model_name: str,
        model: Union[xgb.XGBRegressor, LGBMRegressor, LGBMClassifier],
    ):
        """Log feature importance scores."""
        try:
            if hasattr(model, "feature_importances_"):
                importances = model.feature_importances_
            elif hasattr(model, "get_booster"):
                importances = model.get_booster().get_score()
            else:
                return

            importance_dict = {}
            if isinstance(importances, dict):
                importance_dict = {
                    f"{model_name}.feat_{k}": float(v) for k, v in importances.items()
                }
            else:
                importance_dict = {
                    f"{model_name}.feat_{self.feature_names[i]}": float(importances[i])
                    for i in range(len(importances))
                    if i < len(self.feature_names)
                }

            top_features = sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)[:10]
            logger.info(f"Top 10 features for {model_name}: {top_features}")

            self.logger.log_metrics_final(importance_dict)
        except Exception as e:
            logger.warning(f"Could not log feature importance: {e}")

    def train_xgboost(
        self,
        hyperparams: Optional[Dict[str, Any]] = None,
        cv_folds: int = 5,
    ) -> Dict[str, Any]:
        """
        Train XGBoost model.

        Args:
            hyperparams: Custom hyperparameters
            cv_folds: Cross-validation folds

        Returns:
            Training results dictionary
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

        prefixed_params = {f"xgboost.{k}": v for k, v in default_params.items()}
        self.logger.log_params(prefixed_params)

        logger.info("Training XGBoost model...")
        start_time = time.time()

        model = xgb.XGBRegressor(**default_params)
        model.fit(self.X_train, self.y_train, eval_metric="mae", verbose=False)

        training_time = time.time() - start_time
        self.logger.log_metrics_final({"xgboost.training_time_seconds": float(training_time)})

        y_pred_train = model.predict(self.X_train)

        cv_scores = cross_val_score(model, self.X_train, self.y_train, cv=cv_folds, scoring="r2")
        self.logger.log_metrics_final(
            {
                "xgboost.cv_mean_r2": float(cv_scores.mean()),
                "xgboost.cv_std_r2": float(cv_scores.std()),
            }
        )

        results = {
            "model": model,
            "training_time": training_time,
            "cv_score": cv_scores.mean(),
        }

        if self.X_test is not None and self.y_test is not None:
            y_pred_test = model.predict(self.X_test)

            if self.problem_type == "classification":
                self._log_classification_metrics("xgboost", self.y_test, np.round(y_pred_test))
            else:
                self._log_regression_metrics("xgboost", self.y_test, y_pred_test)
                self._log_financial_metrics("xgboost", self.y_test, y_pred_test)

            results["test_predictions"] = y_pred_test

        self._log_feature_importance("xgboost", model)
        self.models["xgboost"] = model
        self.results["xgboost"] = results

        logger.info(f"XGBoost training completed in {training_time:.2f}s")
        return results

    def train_lightgbm(
        self,
        hyperparams: Optional[Dict[str, Any]] = None,
        cv_folds: int = 5,
    ) -> Dict[str, Any]:
        """
        Train LightGBM model.

        Args:
            hyperparams: Custom hyperparameters
            cv_folds: Cross-validation folds

        Returns:
            Training results dictionary
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

        prefixed_params = {f"lightgbm.{k}": v for k, v in default_params.items()}
        self.logger.log_params(prefixed_params)

        logger.info("Training LightGBM model...")
        start_time = time.time()

        if self.problem_type == "classification":
            model = LGBMClassifier(**default_params)
        else:
            model = LGBMRegressor(**default_params)

        model.fit(self.X_train, self.y_train)

        training_time = time.time() - start_time
        self.logger.log_metrics_final({"lightgbm.training_time_seconds": float(training_time)})

        y_pred_train = model.predict(self.X_train)

        cv_scores = cross_val_score(model, self.X_train, self.y_train, cv=cv_folds, scoring="r2")
        self.logger.log_metrics_final(
            {
                "lightgbm.cv_mean_r2": float(cv_scores.mean()),
                "lightgbm.cv_std_r2": float(cv_scores.std()),
            }
        )

        results = {
            "model": model,
            "training_time": training_time,
            "cv_score": cv_scores.mean(),
        }

        if self.X_test is not None and self.y_test is not None:
            y_pred_test = model.predict(self.X_test)

            if self.problem_type == "classification":
                self._log_classification_metrics("lightgbm", self.y_test, y_pred_test)
            else:
                self._log_regression_metrics("lightgbm", self.y_test, y_pred_test)
                self._log_financial_metrics("lightgbm", self.y_test, y_pred_test)

            results["test_predictions"] = y_pred_test

        self._log_feature_importance("lightgbm", model)
        self.models["lightgbm"] = model
        self.results["lightgbm"] = results

        logger.info(f"LightGBM training completed in {training_time:.2f}s")
        return results

    def compare_models(self) -> Dict[str, Any]:
        """
        Compare trained models and log comparison metrics.

        Returns:
            Comparison summary
        """
        if not self.X_test is None or not self.y_test is not None:
            logger.warning("Test data not provided, skipping comparison")
            return {}

        comparison = {
            "xgboost": self.results.get("xgboost", {}),
            "lightgbm": self.results.get("lightgbm", {}),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(f"Model comparison: {json.dumps(comparison, indent=2, default=str)}")
        self.logger.log_metrics_final({"comparison_timestamp": time.time()})

        return comparison

    def end_experiment(self):
        """End the MLflow experiment run."""
        self.logger.end_run()
        logger.info("Baseline training experiment ended")
