# MLflow Setup Guide - Step by Step

## Overview
MLflow is an open-source platform for managing ML experiments, tracking metrics, versioning models, and deploying them to production.

---

## ✅ STEP 1: Install MLflow

```bash
uv pip install mlflow
```

**What this does:**
- Downloads MLflow library (experiment tracking framework)
- Installs dependencies: Flask, SQLAlchemy, requests, etc.
- Available in virtual environment

**Verify installation:**
```bash
python -c "import mlflow; print(mlflow.__version__)"
```

---

## ✅ STEP 2: Create MLflow Logger Module

Done! File created: `backend/ml/tracking/mlflow_logger.py`

This module provides:
- **MLflowLogger class**: Wraps MLflow API with convenience methods
- **Feature snapshot tracking**: Hash of feature engineering version
- **Experiment management**: Create/get experiments
- **Parameter logging**: Hyperparameters
- **Metric logging**: Training metrics with steps
- **Artifact logging**: Models, plots, configs

---

## 🚀 STEP 3: How to Use MLflow Logger

### **Basic Usage**

```python
from backend.ml.tracking.mlflow_logger import get_mlflow_logger

# Start experiment tracking
logger = get_mlflow_logger(
    experiment_name="stock_prediction_xgboost",
    run_name="xgboost_v1_2026-02-18",
    model_name="xgboost",
    model_type="xgboost",
    feature_snapshot_id="abc123def456..."
)

# Log hyperparameters
logger.log_params(
    learning_rate=0.1,
    max_depth=6,
    n_estimators=100,
    subsample=0.8
)

# Log metrics
logger.log_metrics(
    accuracy=0.92,
    precision=0.89,
    recall=0.85,
    f1=0.87,
    auc_roc=0.95
)

# Log feature snapshot
features = {
    'feature_count': 23,
    'feature_names': ['price', 'volume', 'rsi', ...],
    'feature_types': {'price': 'float', 'volume': 'int', ...},
    'version': '1.0',
    'engineer_date': '2026-02-18'
}
logger.log_feature_snapshot(features)

# Log dataset stats
stats = {
    'train_size': 1000,
    'val_size': 200,
    'test_size': 200,
    'feature_count': 23,
    'target_mean': 0.52
}
logger.log_dataset_stats(stats)

# Log trained model
logger.log_model(
    model=trained_xgboost_model,
    model_path="models/xgboost.pkl",
    model_type="xgboost"
)

# Log artifacts (plots, reports)
logger.log_artifacts("results/plots/")

# End the run
logger.end_run(status="FINISHED")
```

---

## 📊 STEP 4: Configure MLflow Backend

### **Option A: Local Development (Default)**

```python
# Uses local filesystem backend at ./mlruns/
logger = MLflowLogger(
    experiment_name="stock_prediction",
    tracking_uri="file:./mlruns"  # or None (default)
)
```

**File structure created:**
```
mlruns/
├── 0/                          # Experiment folder
│   ├── .attributes/
│   └── abc123def456.../        # Run folder
│       ├── params/             # Logged parameters
│       ├── metrics/            # Logged metrics
│       └── artifacts/          # Models, plots, configs
```

---

### **Option B: Local MLflow Server (Development + UI)**

Start MLflow server:
```bash
mlflow server --host 127.0.0.1 --port 5000
```

This starts a web UI at `http://localhost:5000`

Then use in code:
```python
logger = MLflowLogger(
    experiment_name="stock_prediction",
    tracking_uri="http://localhost:5000"
)
```

**What you see in UI:**
- ✅ All experiments listed
- ✅ All runs with metrics compared side-by-side
- ✅ Hyperparameters visualized
- ✅ Artifacts downloadable
- ✅ Model versions tracked

---

### **Option C: Remote Production Server (Staging)**

For staging/production, use managed MLflow:

```python
# Option 1: AWS S3 + Postgres backend
logger = MLflowLogger(
    experiment_name="stock_prediction",
    tracking_uri="postgresql://user:pass@prod-mlflow-db.aws.rds.amazonaws.com/mlflow",
    tags={
        "environment": "production",
        "team": "ml-platform"
    }
)

# Option 2: GCP Vertex AI + GCS
# (Similar setup with GCP credentials)
```

---

## 🔍 STEP 5: Understand Each Component

### **A. Feature Snapshot ID**
```python
features = {
    'feature_count': 23,
    'feature_names': ['price', 'volume', 'rsi', 'macd', ...],
    'version': '1.0'
}
snapshot_id = logger.log_feature_snapshot(features)
# Returns: "abc123def456..." (MD5 hash)
```

**Why track this?**
- Know which feature version trained which model
- Detect when features changed
- Reproduce exact same features for retraining

---

### **B. Hyperparameters**
```python
logger.log_params(
    learning_rate=0.1,      # How much to adjust weights
    max_depth=6,            # Tree depth limit
    n_estimators=100,       # Number of trees
    subsample=0.8,          # Sample 80% of data per tree
    colsample_bytree=0.8    # Use 80% of features per tree
)
```

**What MLflow stores:**
- Each parameter as separate key-value pair
- Searchable (find runs with learning_rate=0.1)
- Comparable (which params gave best results?)

---

### **C. Metrics**
```python
# Log final metrics
logger.log_metrics(
    accuracy=0.92,          # Overall correct predictions
    precision=0.89,         # Of bullish predictions, how many were correct
    recall=0.85,            # Of actual bullish cases, how many were caught
    f1=0.87,                # Harmonic mean of precision & recall
    auc_roc=0.95            # Area under ROC curve (0.5-1.0, higher=better)
)

# Log step-based metrics (training progress)
for epoch in range(100):
    loss = train_one_epoch()
    accuracy = validate()
    logger.log_step_metrics(
        step=epoch,
        train_loss=loss,
        val_accuracy=accuracy
    )
```

**MLflow stores:**
- Each metric value over time
- Can visualize training curves
- Compare metric progression across runs

---

### **D. Artifacts**
```python
# Log model file
logger.log_model(
    model=trained_model,
    model_path="models/xgboost.pkl",
    model_type="xgboost"
)

# Log plots directory
logger.log_artifacts("results/plots/")
# Logs: accuracy.png, confusion_matrix.png, feature_importance.png

# Log config file
logger.log_artifact_file("config/model_config.yaml")

# Log JSON results
logger.log_dict_artifact(
    {
        'best_threshold': 0.5,
        'backtest_sharpe': 1.23,
        'max_drawdown': -0.15
    },
    "results.json"
)
```

**What gets stored:**
- Actual model files (can be downloaded + reloaded)
- Visualization images
- Configuration files
- JSON reports

---

## 🎯 STEP 6: Real Training Example

```python
from backend.ml.tracking.mlflow_logger import get_mlflow_logger
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import hashlib
import json

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: PREPARE
# ═══════════════════════════════════════════════════════════════════════════════

# Load features (from feature engineering)
X, y = load_features_and_targets()  # Shape: (1200, 23)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

# Create feature snapshot
feature_info = {
    'feature_count': X_train.shape[1],
    'feature_names': list(X.columns),
    'feature_types': {col: str(X[col].dtype) for col in X.columns},
    'version': '1.0',
    'engineer_date': '2026-02-18'
}
snapshot_json = json.dumps(feature_info, sort_keys=True)
snapshot_id = hashlib.md5(snapshot_json.encode()).hexdigest()

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: START MLFLOW TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

logger = get_mlflow_logger(
    experiment_name="stock_prediction_xgboost",
    run_name=f"xgboost_v1_{datetime.now().strftime('%Y-%m-%d')}",
    model_name="xgboost",
    model_type="xgboost",
    feature_snapshot_id=snapshot_id
)

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: LOG HYPERPARAMETERS & DATASET
# ═══════════════════════════════════════════════════════════════════════════════

# Hyperparameters
hyperparams = {
    'learning_rate': 0.1,
    'max_depth': 6,
    'n_estimators': 100,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'random_state': 42
}
logger.log_params(**hyperparams)

# Feature snapshot
logger.log_feature_snapshot(feature_info)

# Dataset statistics
logger.log_dataset_stats({
    'train_size': len(X_train),
    'test_size': len(X_test),
    'feature_count': X_train.shape[1],
    'target_mean': y_train.mean(),
    'class_balance_bullish': (y_train == 1).sum() / len(y_train)
})

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: TRAIN MODEL & LOG STEP METRICS
# ═══════════════════════════════════════════════════════════════════════════════

model = xgb.XGBClassifier(**hyperparams)

# Training with step-based logging
for epoch in range(10):
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=0
    )
    
    # Predict on validation set
    y_pred = model.predict(X_test)
    
    # Calculate metrics
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred)
    rec = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    
    # Log metrics at this step
    logger.log_step_metrics(
        step=epoch,
        accuracy=acc,
        precision=prec,
        recall=rec,
        f1=f1
    )

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: LOG FINAL METRICS & MODEL
# ═══════════════════════════════════════════════════════════════════════════════

# Final test metrics
y_pred_final = model.predict(X_test)
logger.log_metrics(
    accuracy=accuracy_score(y_test, y_pred_final),
    precision=precision_score(y_test, y_pred_final),
    recall=recall_score(y_test, y_pred_final),
    f1=f1_score(y_test, y_pred_final)
)

# Log the trained model
logger.log_model(
    model=model,
    model_path="models/xgboost.pkl",
    model_type="xgboost"
)

# Log plots & artifacts
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix

# Create confusion matrix plot
cm = confusion_matrix(y_test, y_pred_final)
plt.imshow(cm, cmap='Blues')
plt.title('Confusion Matrix')
plt.savefig('results/confusion_matrix.png')

logger.log_artifacts('results/')

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: END RUN
# ═══════════════════════════════════════════════════════════════════════════════

logger.end_run(status="FINISHED")

print(f"✅ Experiment tracked in MLflow!")
print(f"Run ID: {logger.run_id}")
print(f"View at: http://localhost:5000")
```

---

## 🔍 STEP 7: View Results

### **Option A: File System (Terminal)**
```bash
cat mlruns/0/abc123def456.../params/learning_rate
# Output: 0.1

cat mlruns/0/abc123def456.../metrics/accuracy
# Output: 0.92
```

### **Option B: MLflow Web UI**
```bash
mlflow server --host 127.0.0.1 --port 5000
# Open: http://localhost:5000
```

**In the UI, you'll see:**
- ✅ Experiment "stock_prediction_xgboost" listed
- ✅ Run "xgboost_v1_2026-02-18" with all metrics
- ✅ Parameters: learning_rate=0.1, max_depth=6, etc.
- ✅ Metrics chart: accuracy trending up over epochs
- ✅ Feature snapshot ID: abc123def456...
- ✅ Artifacts: Download confusion_matrix.png, model

---

## 🎓 Key Concepts Summary

| Concept | Purpose | Example |
|---------|---------|---------|
| **Experiment** | Container for related runs | "stock_prediction_xgboost" |
| **Run** | Single training execution | "xgboost_v1_2026-02-18" |
| **Feature Snapshot ID** | Hash of feature version | "abc123def456..." |
| **Parameters** | Hyperparameters (fixed) | learning_rate=0.1 |
| **Metrics** | Performance scores | accuracy=0.92 |
| **Step Metrics** | Metrics over training | epoch 0→1→2, loss decreasing |
| **Artifacts** | Files (models, plots, configs) | xgboost.pkl, confusion.png |

---

## ⚙️ Configuration

Add to `backend/config/settings.py`:

```python
class Settings(BaseSettings):
    # MLflow Configuration
    MLFLOW_TRACKING_URI: str = "file:./mlruns"  # or http://localhost:5000
    MLFLOW_EXPERIMENT_NAME: str = "stock_prediction"
    MLFLOW_BACKEND: str = "local"  # or "remote"
    
    # MLflow Remote (if using remote backend)
    MLFLOW_POSTGRES_URI: Optional[str] = None
    MLFLOW_S3_BUCKET: Optional[str] = None
```

---

## 🚀 Next Steps

1. ✅ MLflow installed
2. ✅ MLflowLogger created
3. ⏭️ Integrate into training scripts (Phase 2)
4. ⏭️ Set up remote backend for production
5. ⏭️ Create model registry for versioning

