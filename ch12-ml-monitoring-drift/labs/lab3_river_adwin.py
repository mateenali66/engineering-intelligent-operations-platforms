"""Listing 12-1: streaming drift detection with River's ADWIN.

The NannyML and Evidently labs are batch: they compare a reference window to an
analysis window. A monitoring sidecar also needs an ONLINE detector that flags a
change point as samples arrive one at a time. River's ADWIN (ADaptive WINdowing,
Bifet and Gavalda 2007) does exactly that: feed it a scalar per step, and it
maintains an adaptive window, signalling when the recent mean diverges from the
older mean.

Here the scalar is a 1-D projection of the Chapter 6 monitoring signal: the
detector's per-window anomaly score. The stream is stable for the first half,
then shifts up (a new fault regime). ADWIN should flag the change shortly after
the shift. The API, verified on river 0.25.0: drift.ADWIN(), detector.update(x)
per step, then read detector.drift_detected.
"""

from __future__ import annotations

import numpy as np
from river import drift


def make_stream(n_stable=1000, n_shifted=1000, seed=42):
    """Stable low-anomaly-score regime, then a shifted higher-score regime."""
    rng = np.random.default_rng(seed)
    stable = rng.normal(0.30, 0.10, n_stable)   # nominal anomaly scores
    shifted = rng.normal(0.70, 0.10, n_shifted)  # new fault regime, higher scores
    return np.concatenate([stable, shifted]), n_stable


def detect(stream):
    """Feed the stream into ADWIN; return every flagged change-point index."""
    detector = drift.ADWIN()
    change_points = []
    for i, value in enumerate(stream):
        detector.update(value)
        if detector.drift_detected:
            change_points.append(i)
    return change_points, detector


def run():
    stream, true_change = make_stream()
    change_points, detector = detect(stream)
    return {
        "true_change_index": true_change,
        "detected_change_points": change_points,
        "first_detection": change_points[0] if change_points else None,
        "n_detections": detector.n_detections,
    }


if __name__ == "__main__":
    r = run()
    print(f"true change point injected at index : {r['true_change_index']}")
    print(f"ADWIN flagged change points         : {r['detected_change_points']}")
    print(f"first detection at index            : {r['first_detection']}")
    if r["first_detection"] is not None:
        lag = r["first_detection"] - r["true_change_index"]
        print(f"detection lag after the true shift  : {lag} samples")
