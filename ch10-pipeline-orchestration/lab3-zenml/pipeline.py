"""Listing 10-4: the same anomaly-detector-retrain steps as a ZenML pipeline.

The orchestrator is never named in this code. That is the point: the same @pipeline
runs on whatever stack is active. Swap the stack on the command line and rerun, and the
four steps move to a different orchestrator without a code change. See README.md for the
stack-swap commands that prove portability.

Run:
    python pipeline.py            # runs the steps on the active ZenML stack
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from typing_extensions import Annotated
from zenml import pipeline, step


@step
def ingest() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    rows = np.vstack([rng.normal(0, 1, (800, 6)), rng.normal(3, 1, (80, 6))])
    df = pd.DataFrame(rows, columns=[f"f{i}" for i in range(6)])
    df["label"] = ([0] * 800) + ([1] * 80)
    return df


@step
def train(df: pd.DataFrame) -> Annotated[float, "auc"]:
    y = df["label"].to_numpy()
    X = df.drop(columns="label").to_numpy()
    # Held-out split, the same one Chapter 9 registered on; never score the gate on training rows.
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=42
    )
    # Fit on normal rows only, as Chapter 6 requires: a detector that trains on
    # the anomalies learns them as normal. The labels mark which rows those are.
    clf = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
    clf.fit(X_train[y_train == 0])
    return float(roc_auc_score(y_val, -clf.score_samples(X_val)))


@pipeline
def anomaly_detector_retrain():
    df = ingest()
    train(df)


if __name__ == "__main__":
    anomaly_detector_retrain()
