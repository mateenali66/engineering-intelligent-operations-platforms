"""Synthetic monitoring streams in the Chapter 6 feature-table style.

Chapter 6 ships a parquet feature table, one row per (service, window), with
<metric>_mean / <metric>_p95 columns and a binary `label` (1 = injected fault).
The detector is an unsupervised IsolationForest. For Chapter 12 we generate
three slices in the SAME schema and seeding style (numpy default_rng(42)):

  reference : the period the monitor was calibrated on (stable).
  analysis_stable : a later period with the same distribution (no drift).
  analysis_shifted : a later period where the numeric features have drifted
      (covariate shift) AND the fault prevalence has risen, the regime that
      should make a trained classifier silently lose accuracy.

The same generator feeds Lab 1 (NannyML), Lab 2 (Evidently), and a 1-D
projection feeds Lab 3 (River).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Chapter 6 metric set. Two columns per metric (mean, p95) -> 10 numeric
# features, the same shape the Chapter 6 loader keeps.
METRICS = [
    "cpu_utilization",
    "memory_working_set_bytes",
    "request_latency_ms",
    "request_rate",
    "error_rate",
]
FAULT_METRICS = ("memory_working_set_bytes", "request_latency_ms", "error_rate")
FEATURE_NAMES = [f"{m}_{stat}" for m in METRICS for stat in ("mean", "p95")]


def _make_slice(rng, n, anomaly_rate, fault_gain=2.5, noise=1.0):
    """One feature-table slice in the Chapter 6 schema.

    Faults push the three fault metrics UP by `fault_gain` standard deviations.
    A larger gain separates anomalies cleanly; a smaller gain buries them in the
    normal traffic. The reference period uses a clean gain so the monitored
    classifier learns a sharp, confident boundary, the realistic starting point.
    """
    labels = (rng.random(n) < anomaly_rate).astype(int)
    data = {}
    for m in METRICS:
        base = rng.normal(0.0, noise, n)
        if m in FAULT_METRICS:
            base = base + labels * rng.normal(fault_gain, 0.5, n)
        data[f"{m}_mean"] = base
        data[f"{m}_p95"] = base + np.abs(rng.normal(0.5, 0.2, n))
    df = pd.DataFrame(data)
    df["label"] = labels
    return df


def make_streams(seed=42):
    """Return (reference, analysis_stable, analysis_shifted) DataFrames.

    The shifted slice models concept drift: a new fault mode whose anomalies
    barely lift the fault metrics (fault_gain=0.6) and sit on top of the normal
    traffic the reference classifier learned. The classifier keeps predicting
    "normal" with high confidence, so it silently misses the new anomalies. CBPE
    reads that over-confidence and estimates a LOWER ROC AUC without ever seeing
    a label, which is the whole point of label-free monitoring.
    """
    rng = np.random.default_rng(seed)
    reference = _make_slice(rng, n=3000, anomaly_rate=0.20, fault_gain=2.5)
    analysis_stable = _make_slice(rng, n=3000, anomaly_rate=0.20, fault_gain=2.5)
    analysis_shifted = _make_slice(
        rng, n=3000, anomaly_rate=0.40, fault_gain=0.6, noise=1.4
    )
    return reference, analysis_stable, analysis_shifted


if __name__ == "__main__":
    ref, stable, shifted = make_streams()
    print(f"features={len(FEATURE_NAMES)}")
    print(f"reference      : {ref.shape} prevalence {ref['label'].mean():.0%}")
    print(f"analysis_stable: {stable.shape} prevalence {stable['label'].mean():.0%}")
    print(f"analysis_shift : {shifted.shape} prevalence {shifted['label'].mean():.0%}")
