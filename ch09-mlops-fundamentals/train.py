"""Listing 9-2: train the Chapter 6 detector, then log and register it to MLflow.

This takes the anomaly detector from Chapter 6 and wraps it in the model
lifecycle: an experiment run that records the parameters, the metric, and the
model itself, then registers that model under a name so it can be promoted and
served. MLflow 3 changed the model-logging call: pass `name=`, not the
deprecated `artifact_path=`. The registry needs a database-backed store, so the
tracking URI points at SQLite, not the bare file store.
"""

from __future__ import annotations

import mlflow
import mlflow.sklearn
import numpy as np
from mlflow.models import infer_signature
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

# A database-backed store: the Model Registry does not work on the file store.
mlflow.set_tracking_uri("sqlite:///mlflow.db")
mlflow.set_experiment("aiosp-anomaly-detector")


def make_data(seed=42):
    """Synthetic telemetry features with labels, standing in for Chapter 6 data."""
    rng = np.random.default_rng(seed)
    normal = rng.normal(0.0, 1.0, size=(800, 6))
    anomalous = rng.normal(3.0, 1.0, size=(80, 6))
    X = np.vstack([normal, anomalous])
    y = np.concatenate([np.zeros(800), np.ones(80)])
    return X, y


def main():
    X, y = make_data()
    # Hold out 30 percent for evaluation. Never score the gate on training data:
    # a model measured on the rows it was fit on reports an inflated metric.
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=42
    )
    params = {"n_estimators": 100, "contamination": 0.1, "random_state": 42}

    with mlflow.start_run():
        model = IsolationForest(**params)
        model.fit(X_train)
        # Score the held-out slice, not the training rows. Chapter 6 sign convention.
        auc = roc_auc_score(y_val, -model.score_samples(X_val))

        mlflow.log_params(params)
        mlflow.log_metric("auc", auc)

        signature = infer_signature(X_train, model.predict(X_train))
        # MLflow 3: 'name', not 'artifact_path'. registered_model_name registers
        # the model in the same call, creating version 1 (or the next version).
        logged = mlflow.sklearn.log_model(
            sk_model=model,
            name="model",
            signature=signature,
            registered_model_name="anomaly-detector",
        )

    print(f"auc={auc:.3f}  registered=anomaly-detector  uri={logged.model_uri}")
    return auc


if __name__ == "__main__":
    main()
