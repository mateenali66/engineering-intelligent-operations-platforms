"""Listing 8-4: export fault-labeled windows as Chapter 6 training data.

This is the flywheel made literal. A chaos experiment knows exactly which windows
were faulted, because it injected them, so it can attach the ground-truth label
the unsupervised Chapter 6 setup never had. The output is the exact Chapter 6
feature-table schema, so it loads straight back into the Chapter 6 detector as
labeled training and evaluation data. Every experiment makes the detector sharper.
"""

from __future__ import annotations

import os


def label_windows(df, fault):
    """Attach label=1 to the injected fault windows, 0 elsewhere, then emit
    the Chapter 6 feature-table schema unchanged."""
    out = df.copy()
    is_fault = (
        (out["service_name"] == fault["service"])
        & (out["window_start"] >= fault["start"])
        & (out["window_start"] < fault["end"])
    )
    out["label"] = is_fault.astype(int)
    return out


def export_training_data(df, fault, path):
    """Write the labeled feature table as parquet for the Chapter 6 detector."""
    labeled = label_windows(df, fault)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    labeled.to_parquet(path, index=False)
    return labeled


if __name__ == "__main__":
    from make_telemetry import make_telemetry

    df, fault = make_telemetry()
    labeled = export_training_data(df, fault, "data/fault_labeled.parquet")
    n_fault = int(labeled["label"].sum())
    print(f"wrote data/fault_labeled.parquet: {len(labeled)} windows, "
          f"{n_fault} labeled as fault ({labeled['label'].mean():.1%})")
