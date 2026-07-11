"""Listing 8-2: correlate the injected fault with the telemetry response.

This is the analysis step, and it has two halves. First, the steady-state
hypothesis: did the service stay inside its SLO (p99 latency and error rate)
while the fault was active? Second, the detector: did the Chapter 6 anomaly
detector light up during the window you injected the fault into? The two answers
are independent. The service can breach its SLO while the detector stays quiet,
or hold its SLO while the detector fires, and each combination tells you
something different, so the analysis reports both.
"""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

FEATURE_DROP = ["service_name", "window_start", "label"]


def check_hypothesis(metrics, p99_latency_ms_max=500.0, error_rate_max=0.01):
    """Evaluate the steady-state hypothesis over the captured fault window.

    `metrics` is the fault-window slice of the Chapter 3 feature table in real
    units: a `request_latency_ms` column in milliseconds and an `error_rate`
    column as a fraction. This is the half of the analysis the detector check
    does not do. The detector lighting up says the fault was visible; the
    hypothesis says whether the service stayed inside its SLO while the fault
    was active.
    """
    p99_ms = float(np.percentile(metrics["request_latency_ms"], 99))
    error_rate = float(metrics["error_rate"].mean())
    latency_ok = p99_ms < p99_latency_ms_max
    error_ok = error_rate < error_rate_max
    held = latency_ok and error_ok
    return {
        "p99_latency_ms": round(p99_ms, 1),
        "error_rate": round(error_rate, 4),
        "latency_pass": latency_ok,
        "error_pass": error_ok,
        "verdict": "PASS" if held else "FAIL",
    }


def score_anomalies(df, train_mask=None, seed=42):
    """Fit the Chapter 6 Isolation Forest and score every captured window.

    With `train_mask` the model is fit on those rows only, the Chapter 6
    discipline of training on normal-only windows. Because you injected the
    fault you know which windows are nominal, so the detector is fit on the
    fault-free baseline and then scores the whole capture. That is what lets a
    genuine blind spot stay quiet, instead of a model fit on the fault window
    memorizing the very thing it is supposed to catch.
    """
    features = df[[c for c in df.columns if c not in FEATURE_DROP]].to_numpy()
    fit_rows = features if train_mask is None else features[train_mask]
    model = IsolationForest(n_estimators=100, contamination=0.1,
                            random_state=seed)
    model.fit(fit_rows)
    # Negate: score_samples is lower for more anomalous (Chapter 6 convention).
    return -model.score_samples(features)


def fault_response(df, fault):
    """Compare anomaly scores inside the fault window to the rest."""
    in_window = (
        (df["service_name"] == fault["service"])
        & (df["window_start"] >= fault["start"])
        & (df["window_start"] < fault["end"])
    ).to_numpy()
    # Fit the detector on the normal-only baseline (Chapter 6 style), score all.
    scores = score_anomalies(df, train_mask=~in_window)
    return {
        "mean_score_in_fault": round(float(scores[in_window].mean()), 3),
        "mean_score_baseline": round(float(scores[~in_window].mean()), 3),
        "detector_lit_up": bool(
            scores[in_window].mean() > scores[~in_window].mean() + scores.std()
        ),
    }


if __name__ == "__main__":
    from make_telemetry import make_telemetry

    df, fault = make_telemetry()
    print("fault response:", fault_response(df, fault))
