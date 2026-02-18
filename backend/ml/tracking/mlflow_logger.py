"""
MLflow Experiment Tracking Logger

Handles logging of model training experiments, metrics, parameters, and artifacts.
Supports local dev and remote staging configurations.

Usage:
    logger = MLflowLogger(experiment_name="stock_prediction_xgboost")
    logger.start_run(model_name="xgboost_v1", tags={"model_type": "tree"})
    logger.log_params(learning_rate=0.1, max_depth=6)
    logger.log_metrics(accuracy=0.92, f1=0.88)
    logger.log_artifacts("models/xgboost.pkl")
    logger.end_run()
"""

import mlflow
import mlflow.xgboost
import mlflow.lightgbm
import mlflow.pytorch
from pathlib import Path
from typing import Dict, Any, Optional
import json
from datetime import datetime
import hashlib
import os


class MLflowLogger:
    """
    Enterprise-grade experiment tracking logger.
    
    Supports:
    - Local dev tracking (file-based backend)
    - Remote staging/prod (Postgres + artifact storage)
    - Multi-model logging (XGBoost, LightGBM, PyTorch)
    - Feature snapshot tracking
    - Comprehensive metrics logging
    """
    
    def __init__(
        self,
        experiment_name: str,
        tracking_uri: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ):
        """
        Initialize MLflow logger.
        
        Args:
            experiment_name: Name of the experiment (e.g., "stock_prediction_xgboost")
            tracking_uri: MLflow tracking server URI
                - None: Use local ./mlruns/ directory
                - "http://localhost:5000": Local MLflow server
                - "postgres://user:pass@host/db": Remote backend
            tags: Global tags for all runs in this experiment
        """
        self.experiment_name = experiment_name
        self.tracking_uri = tracking_uri or "file:./mlruns"
        self.tags = tags or {}
        self.run_id = None
        self.run_name = None
        
        # Set tracking URI
        mlflow.set_tracking_uri(self.tracking_uri)
        
        # Create or get experiment
        try:
            experiment = mlflow.get_experiment_by_name(experiment_name)
            if experiment is None:
                self.experiment_id = mlflow.create_experiment(experiment_name)
            else:
                self.experiment_id = experiment.experiment_id
        except Exception as e:
            print(f"⚠️ Warning: Could not set experiment: {e}")
            self.experiment_id = "0"
    
    def start_run(
        self,
        run_name: str,
        model_name: str,
        model_type: str,
        feature_snapshot_id: Optional[str] = None
    ) -> str:
        """
        Start a new MLflow run.
        
        Args:
            run_name: Human-readable run name (e.g., "xgboost_v1_2026-02-18")
            model_name: Model identifier (e.g., "xgboost", "lightgbm", "tft")
            model_type: Model type for auto-logging (e.g., "xgboost", "lightgbm", "pytorch")
            feature_snapshot_id: Hash of feature engineering version
            
        Returns:
            run_id: MLflow run ID
        """
        mlflow.set_experiment(self.experiment_name)
        
        # Start run
        self.run_id = mlflow.start_run(run_name=run_name).info.run_id
        self.run_name = run_name
        
        # Log global tags
        for key, value in self.tags.items():
            mlflow.set_tag(key, value)
        
        # Log model metadata
        mlflow.set_tag("model_name", model_name)
        mlflow.set_tag("model_type", model_type)
        mlflow.set_tag("timestamp", datetime.now().isoformat())
        
        # Log feature snapshot if provided
        if feature_snapshot_id:
            mlflow.set_tag("feature_snapshot_id", feature_snapshot_id)
        
        print(f"✅ MLflow run started: {self.run_id}")
        return self.run_id
    
    def log_params(self, **params) -> None:
        """
        Log hyperparameters.
        
        Args:
            **params: Key-value hyperparameters
                e.g., learning_rate=0.1, max_depth=6, n_estimators=100
        """
        for key, value in params.items():
            mlflow.log_param(key, value)
        print(f"✅ Logged {len(params)} parameters")
    
    def log_metrics(self, **metrics) -> None:
        """
        Log training/validation metrics.
        
        Args:
            **metrics: Key-value metrics
                e.g., accuracy=0.92, precision=0.89, recall=0.85, f1=0.87
        """
        for key, value in metrics.items():
            mlflow.log_metric(key, value)
        print(f"✅ Logged {len(metrics)} metrics")
    
    def log_step_metrics(self, step: int, **metrics) -> None:
        """
        Log metrics at a specific training step.
        
        Args:
            step: Training step/epoch number
            **metrics: Metrics to log with step
        """
        for key, value in metrics.items():
            mlflow.log_metric(key, value, step=step)
    
    def log_feature_snapshot(self, features: Dict[str, Any]) -> str:
        """
        Log feature engineering snapshot.
        
        Args:
            features: Dict of feature metadata
                {
                    'feature_count': 23,
                    'feature_names': ['price', 'volume', ...],
                    'feature_types': {'price': 'float', ...},
                    'version': '1.0',
                    'engineer_date': '2026-02-18'
                }
        
        Returns:
            snapshot_id: Hash of feature snapshot
        """
        # Create snapshot hash
        snapshot_json = json.dumps(features, sort_keys=True)
        snapshot_id = hashlib.md5(snapshot_json.encode()).hexdigest()
        
        # Log feature metadata
        mlflow.log_dict(features, "feature_snapshot.json")
        mlflow.set_tag("feature_snapshot_id", snapshot_id)
        mlflow.log_param("feature_count", features.get('feature_count', 0))
        
        print(f"✅ Logged feature snapshot: {snapshot_id}")
        return snapshot_id
    
    def log_dataset_stats(self, stats: Dict[str, Any]) -> None:
        """
        Log dataset statistics.
        
        Args:
            stats: Dataset metadata
                {
                    'train_size': 1000,
                    'val_size': 200,
                    'test_size': 200,
                    'feature_count': 23,
                    'target_mean': 0.52,
                    'class_balance': {'bullish': 0.52, 'bearish': 0.48}
                }
        """
        mlflow.log_dict(stats, "dataset_stats.json")
        for key, value in stats.items():
            if isinstance(value, (int, float)):
                mlflow.log_param(f"dataset_{key}", value)
        print(f"✅ Logged dataset statistics")
    
    def log_model(
        self,
        model,
        model_path: str,
        model_type: str = "xgboost"
    ) -> None:
        """
        Log trained model artifact.
        
        Args:
            model: Trained model object
            model_path: Path to save model (e.g., "models/xgboost.pkl")
            model_type: Model framework ("xgboost", "lightgbm", "pytorch")
        """
        if model_type == "xgboost":
            mlflow.xgboost.log_model(model, "model")
        elif model_type == "lightgbm":
            mlflow.lightgbm.log_model(model, "model")
        elif model_type == "pytorch":
            mlflow.pytorch.log_model(model, "model")
        else:
            # Generic artifact
            mlflow.log_artifact(model_path, "model")
        
        print(f"✅ Logged {model_type} model")
    
    def log_artifacts(self, artifact_dir: str) -> None:
        """
        Log artifacts directory (plots, reports, etc).
        
        Args:
            artifact_dir: Path to artifacts directory
                e.g., "results/plots/" contains accuracy.png, confusion.png
        """
        if Path(artifact_dir).exists():
            mlflow.log_artifacts(artifact_dir)
            print(f"✅ Logged artifacts from {artifact_dir}")
        else:
            print(f"⚠️ Artifact directory not found: {artifact_dir}")
    
    def log_artifact_file(self, file_path: str, artifact_path: str = None) -> None:
        """
        Log a single artifact file.
        
        Args:
            file_path: Path to file
            artifact_path: Optional subdirectory in MLflow
        """
        mlflow.log_artifact(file_path, artifact_path)
        print(f"✅ Logged artifact: {file_path}")
    
    def log_dict_artifact(self, data: Dict[str, Any], name: str) -> None:
        """
        Log a dictionary as JSON artifact.
        
        Args:
            data: Dictionary to log
            name: Artifact name (e.g., "config.json", "results.json")
        """
        mlflow.log_dict(data, name)
        print(f"✅ Logged dict artifact: {name}")
    
    def end_run(self, status: str = "FINISHED") -> str:
        """
        End the current MLflow run.
        
        Args:
            status: Run status ("FINISHED", "FAILED", "KILLED")
        
        Returns:
            run_id: MLflow run ID
        """
        mlflow.end_run(status=status)
        print(f"✅ MLflow run ended: {self.run_id}")
        return self.run_id
    
    def get_run_info(self) -> Dict[str, Any]:
        """
        Get current run information.
        
        Returns:
            Dictionary with run details
        """
        if not self.run_id:
            return {}
        
        run = mlflow.get_run(self.run_id)
        return {
            'run_id': run.info.run_id,
            'experiment_id': run.info.experiment_id,
            'status': run.info.status,
            'params': run.data.params,
            'metrics': run.data.metrics,
            'tags': run.data.tags
        }
    
    @staticmethod
    def compare_runs(experiment_id: str, metric_name: str = "accuracy"):
        """
        Compare all runs in an experiment.
        
        Args:
            experiment_id: MLflow experiment ID
            metric_name: Metric to compare by (e.g., "accuracy")
        
        Returns:
            List of runs sorted by metric (highest first)
        """
        experiment = mlflow.get_experiment(experiment_id)
        runs = mlflow.search_runs(experiment_ids=[experiment_id])
        
        # Sort by metric
        runs = runs.sort_values(f"metrics.{metric_name}", ascending=False)
        return runs


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_mlflow_logger(
    experiment_name: str,
    run_name: str,
    model_name: str,
    model_type: str,
    feature_snapshot_id: Optional[str] = None
) -> MLflowLogger:
    """
    Convenience function to create and start an MLflow logger.
    
    Usage:
        logger = get_mlflow_logger(
            experiment_name="stock_prediction",
            run_name="xgboost_v1_2026-02-18",
            model_name="xgboost",
            model_type="xgboost",
            feature_snapshot_id="abc123..."
        )
        logger.log_params(learning_rate=0.1, max_depth=6)
        logger.log_metrics(accuracy=0.92)
    """
    logger = MLflowLogger(experiment_name=experiment_name)
    logger.start_run(
        run_name=run_name,
        model_name=model_name,
        model_type=model_type,
        feature_snapshot_id=feature_snapshot_id
    )
    return logger
