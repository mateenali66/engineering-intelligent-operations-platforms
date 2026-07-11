"""Listing 6-1: load the Chapter 3 feature table and make a leakage-safe split.

Chapter 3 ships a parquet feature table, one row per (service_name,
window_start), with <metric>_mean / <metric>_p95 columns, a sample_count, and a
label (0 nominal, 1 injected-fault). Chapter 6 trains on the numeric columns and
keeps service_name, window_start, and label as metadata.

Leakage-safe means two things: the scaler is fit on NORMAL training rows only,
and the test set is held out before any thresholding. The detector never sees a
test-set anomaly during training or scaling.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

META_COLUMNS = ["service_name", "window_start", "label"]


@dataclass
class Dataset:
    X_train: np.ndarray  # scaled, normal-only training rows
    X_test: np.ndarray   # scaled, held-out mixed rows
    y_test: np.ndarray   # 0/1 labels for the test rows
    feature_names: list
    scaler: StandardScaler


def load_feature_table(path):
    """Return (X, y, feature_names) from the parquet feature table."""
    df = pd.read_parquet(path)
    feature_names = [c for c in df.columns if c not in META_COLUMNS]
    X = df[feature_names].to_numpy(dtype="float32")
    y = df["label"].to_numpy(dtype="int64")
    return X, y, feature_names


def leakage_safe_split(X, y, feature_names, test_frac=0.3, seed=42):
    """Train on normal-only rows; fit the scaler on those rows only."""
    rng = np.random.default_rng(seed)
    n = len(X)
    test_idx = rng.choice(n, size=int(n * test_frac), replace=False)
    is_test = np.zeros(n, dtype=bool)
    is_test[test_idx] = True

    # Training rows are the NORMAL rows outside the test split.
    train_mask = (~is_test) & (y == 0)

    scaler = StandardScaler().fit(X[train_mask])  # normal-only fit
    return Dataset(
        X_train=scaler.transform(X[train_mask]),
        X_test=scaler.transform(X[is_test]),
        y_test=y[is_test],
        feature_names=feature_names,
        scaler=scaler,
    )


if __name__ == "__main__":
    X, y, names = load_feature_table("data/features.parquet")
    ds = leakage_safe_split(X, y, names)
    print(f"features: {len(names)} columns")
    print(f"train (normal-only): {ds.X_train.shape}")
    print(f"test (mixed): {ds.X_test.shape}, "
          f"prevalence {ds.y_test.mean():.0%}")
