"""Listing 9-2: train the Chapter 6 detector, then log and register it to MLflow.

This takes the anomaly detector from Chapter 6 and wraps it in the model
lifecycle: an experiment run that records the parameters, the metric, and the
model itself, then registers that model under a name so it can be promoted and
served. It trains on the file Listing 9-1 versions with DVC and tags the run
with that file's md5, the same hash the .dvc pointer records, so a registered
version traces back to the exact dataset version it was trained on. MLflow 3 changed the model-logging call: pass `name=`, not the
deprecated `artifact_path=`. The registry needs a database-backed store, so the
tracking URI points at SQLite, not the bare file store.
"""

from __future__ import annotations

import hashlib
import os

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


DATASET = "data/telemetry.csv"  # the file Listing 9-1 tracks with DVC


def load_dataset(path=DATASET):
    """Return (X, y, md5) for the DVC-tracked dataset: six features, then label."""
    if not os.path.exists(path):
        import generate_data  # same seed, so the same bytes and the same hash
        generate_data.main()
    with open(path, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()  # equals the .dvc pointer's md5
    rows = np.loadtxt(path, delimiter=",", skiprows=1)
    return rows[:, :-1], rows[:, -1], md5


def split(X, y):
    """Hold out 30 percent for evaluation. Never score the gate on training
    data: a model measured on the rows it was fit on reports an inflated metric.
    The CI gate re-scores the incumbent on this same slice."""
    return train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)


def main():
    X, y, dataset_md5 = load_dataset()
    X_train, X_val, y_train, y_val = split(X, y)
    params = {"n_estimators": 100, "contamination": 0.1, "random_state": 42}

    with mlflow.start_run():
        model = IsolationForest(**params)
        # Fit on normal rows only, as Chapter 6 requires: a detector that trains
        # on the anomalies learns them as normal. The labels mark which rows.
        model.fit(X_train[y_train == 0])
        # Score the held-out slice, not the training rows. Chapter 6 sign convention.
        auc = roc_auc_score(y_val, -model.score_samples(X_val))

        mlflow.log_params(params)
        mlflow.log_metric("auc", auc)
        # The link from this run back to the dataset version in Git and DVC.
        mlflow.set_tags({"dataset.path": DATASET, "dataset.md5": dataset_md5})

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
