"""Train the Chapter 6/9 anomaly detector and save it for MLServer's SKLearn runtime.

Same IsolationForest as Chapter 9, persisted with joblib so MLServer (which is
KServe's sklearn serving runtime) can load and serve it through the V2 Open
Inference Protocol. Run: python train.py
"""
from __future__ import annotations

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest


def make_data(seed=42):
    rng = np.random.default_rng(seed)
    normal = rng.normal(0.0, 1.0, size=(800, 6))
    anomalous = rng.normal(3.0, 1.0, size=(80, 6))
    return np.vstack([normal, anomalous])


def main():
    X = make_data()
    model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
    model.fit(X)
    joblib.dump(model, "anomaly-detector.joblib")
    print("saved anomaly-detector.joblib")


if __name__ == "__main__":
    main()
