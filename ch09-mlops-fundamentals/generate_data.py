"""Generate the telemetry dataset that Listing 9-1 versions with DVC.

Writes data/telemetry.csv from the same synthetic feature distribution train.py
uses, so the file is reproducible: the fixed seed always yields byte-identical
data, which is exactly what lets DVC pin it to a stable content hash. The six
columns are the features; the last column is the label.
"""

from __future__ import annotations

import os

import numpy as np


def make_data(seed=42):
    """Synthetic telemetry features with labels, matching train.py."""
    rng = np.random.default_rng(seed)
    normal = rng.normal(0.0, 1.0, size=(800, 6))
    anomalous = rng.normal(3.0, 1.0, size=(80, 6))
    X = np.vstack([normal, anomalous])
    y = np.concatenate([np.zeros(800), np.ones(80)])
    return X, y


def main():
    X, y = make_data()
    os.makedirs("data", exist_ok=True)
    header = ",".join([f"f{i}" for i in range(X.shape[1])] + ["label"])
    rows = np.column_stack([X, y])
    np.savetxt(
        "data/telemetry.csv", rows, delimiter=",", header=header,
        comments="", fmt="%.6f",
    )
    print(f"wrote data/telemetry.csv ({rows.shape[0]} rows)")


if __name__ == "__main__":
    main()
