"""Listing 7-2: cost-anomaly detection, reusing the Chapter 6 detector.

This is the same Isolation Forest detector from Chapter 6 (Listing 6-2), pointed
at the spend series instead of service telemetry. The only new work is turning a
one-dimensional spend series into a small feature window: the day's spend, its
deviation from a rolling baseline, and the day-over-day change. The same sign
convention applies: score_samples is lower for more anomalous, so negate it.
"""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import IsolationForest


def spend_features(daily, window=7):
    """Turn a daily spend Series into rolling cost features, one row per day."""
    roll_mean = daily.rolling(window, min_periods=1).mean()
    roll_std = daily.rolling(window, min_periods=1).std().fillna(0.0)
    feats = pd.DataFrame({
        "spend": daily,
        "deviation": (daily - roll_mean),
        "z_score": (daily - roll_mean) / (roll_std + 1e-6),
        "pct_change": daily.pct_change().fillna(0.0),
    })
    return feats


def detect_cost_anomalies(daily, contamination=0.05, seed=42):
    """Flag spend-anomaly days. Returns a frame with the score and the flag."""
    feats = spend_features(daily)
    model = IsolationForest(
        n_estimators=100, contamination=contamination, random_state=seed
    )
    model.fit(feats.to_numpy())
    # Negate: score_samples is lower for more anomalous (Chapter 6 convention).
    scores = -model.score_samples(feats.to_numpy())
    flagged = (model.predict(feats.to_numpy()) == -1)
    return pd.DataFrame(
        {"spend": daily, "anomaly_score": scores, "flagged": flagged},
        index=daily.index,
    )


if __name__ == "__main__":
    from ingest import load_daily_spend

    daily = load_daily_spend("data/billing_focus.csv")
    result = detect_cost_anomalies(daily)
    spikes = result[result["flagged"]]
    print(f"flagged {len(spikes)} spend-anomaly days of {len(result)}")
    print(spikes[["spend", "anomaly_score"]].round(2).to_string())
