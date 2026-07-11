"""Generate a small synthetic feature table with the Chapter 3 schema.

This lets the pipeline and CI run end to end without downloading the 58 MB
Zenodo deposit or a GPU. The real benchmark uses the OpenTelemetry Demo data
mirrored at Zenodo concept DOI 10.5281/zenodo.19462083. The synthetic rows here
share the Chapter 3 output schema (one row per service and window) so the same
loader, models, and evaluation harness run unchanged on either source.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

METRICS = [
    "cpu_utilization",
    "memory_working_set_bytes",
    "request_latency_ms",
    "request_rate",
    "error_rate",
]
SERVICES = ["checkout", "payment", "cart"]  # OpenTelemetry Demo services


def make_feature_table(n_windows=600, anomaly_rate=0.25, seed=42):
    """Return a DataFrame matching the Chapter 3 feature-table schema."""
    rng = np.random.default_rng(seed)
    rows = n_windows * len(SERVICES)
    labels = (rng.random(rows) < anomaly_rate).astype(int)

    data = {}
    for m in METRICS:
        base = rng.normal(0.0, 1.0, rows)
        # Faults push memory and latency up; anomalies sit on-manifold at higher
        # magnitude, the regime where reconstruction autoencoders can invert.
        if m in ("memory_working_set_bytes", "request_latency_ms", "error_rate"):
            base = base + labels * rng.normal(3.0, 0.5, rows)
        data[f"{m}_mean"] = base
        data[f"{m}_p95"] = base + np.abs(rng.normal(0.5, 0.2, rows))

    df = pd.DataFrame(data)
    df["sample_count"] = rng.integers(15, 25, rows)
    df["service_name"] = rng.choice(SERVICES, rows)
    df["window_start"] = pd.date_range(
        "2026-06-18T14:00:00Z", periods=rows, freq="30s"
    )
    df["label"] = labels
    return df


if __name__ == "__main__":
    table = make_feature_table()
    out = "data/features.parquet"
    table.to_parquet(out, index=False)
    print(f"wrote {out}: {len(table)} rows, "
          f"{int(table['label'].sum())} anomalous "
          f"({table['label'].mean():.0%} prevalence)")
