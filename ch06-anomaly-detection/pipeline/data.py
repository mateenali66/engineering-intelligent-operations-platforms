"""Listing 6-1: load the Chapter 3 feature table and make a normal-only split.

Chapter 3 ships a parquet feature table, one row per (service_name,
window_start), with <metric>_mean / <metric>_p95 columns, a sample_count, and a
label (0 nominal, 1 injected-fault). Chapter 6 trains on the numeric columns and
keeps service_name, window_start, and label as metadata.

The split guarantees two things: the scaler is fit on NORMAL training rows only,
and the test set is held out before any thresholding, so the detector never sees
a test-set anomaly during training or scaling. It does not by itself make train
and test independent. Neighbouring windows from one fault run are correlated, so
on real telemetry pass ``groups`` (a fault-repetition ID, or a time block from
``time_blocks``) and whole groups are held out together. The Chapter 6 benchmark
holds out whole fault repetitions; a deployment check holds out the latest time
blocks with ``chronological=True``. A random row split is only sound when rows
are independent, as in the synthetic slice the smoke test uses.
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


def time_blocks(path, freq="1h"):
    """One group ID per row: the start of the time block it falls in."""
    starts = pd.read_parquet(path, columns=["window_start"])["window_start"]
    return starts.dt.floor(freq).to_numpy()


def normal_only_split(X, y, feature_names, groups=None, test_frac=0.3,
                      chronological=False, seed=42):
    """Hold out a test set, then train and scale on normal rows only.

    groups gives one ID per row, a fault repetition or a time block, and
    whole groups are held out so one run never sits on both sides. With
    chronological=True the latest groups are held out, as in deployment.
    With no groups every row is its own group, a random row split that is
    only sound when rows are independent.
    """
    if groups is None:
        groups = np.arange(len(X))
    ids = np.unique(groups)  # sorted, so time blocks run oldest first
    n_test = max(1, int(len(ids) * test_frac))
    if chronological:
        test_ids = ids[-n_test:]
    else:
        test_ids = np.random.default_rng(seed).choice(ids, n_test, replace=False)
    is_test = np.isin(groups, test_ids)

    # Training rows are the NORMAL rows outside the held-out groups.
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
    ds = normal_only_split(X, y, names)
    print(f"features: {len(names)} columns")
    print(f"train (normal-only): {ds.X_train.shape}")
    print(f"test (mixed): {ds.X_test.shape}, "
          f"prevalence {ds.y_test.mean():.0%}")
