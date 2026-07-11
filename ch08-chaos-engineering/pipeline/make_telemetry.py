"""Generate synthetic telemetry with a known injected-fault window.

This stands in for the Chapter 3 telemetry captured during a chaos experiment,
without needing a live cluster. The schema matches the Chapter 6 feature table
exactly, so the labeled output of this chapter round-trips into the Chapter 6
detector. The key difference from Chapter 6: here the fault window is KNOWN,
because we injected it, which is the ground-truth label chaos manufactures.
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


def make_telemetry(n_windows=120, fault_start=80, fault_len=8,
                   target="payment", seed=42):
    """Return (telemetry_df, fault). The fault is the injected ground truth."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2026-06-18T14:00:00Z")
    rows = []
    for w in range(n_windows):
        window_start = start + pd.Timedelta(seconds=30 * w)
        in_fault = fault_start <= w < fault_start + fault_len
        for svc in SERVICES:
            hit = in_fault and svc == target  # only the target service degrades
            base = {m: rng.normal(0.0, 1.0) for m in METRICS}
            if hit:
                # A pod-kill / stress signature: memory, latency, errors climb.
                base["memory_working_set_bytes"] += rng.normal(4.0, 0.4)
                base["request_latency_ms"] += rng.normal(3.5, 0.4)
                base["error_rate"] += rng.normal(3.0, 0.4)
            row = {}
            for m in METRICS:
                row[f"{m}_mean"] = base[m]
                row[f"{m}_p95"] = base[m] + abs(rng.normal(0.5, 0.2))
            row["sample_count"] = int(rng.integers(15, 25))
            row["service_name"] = svc
            row["window_start"] = window_start
            rows.append(row)
    df = pd.DataFrame(rows)
    fault = {
        "service": target,
        "start": start + pd.Timedelta(seconds=30 * fault_start),
        "end": start + pd.Timedelta(seconds=30 * (fault_start + fault_len)),
    }
    return df, fault


if __name__ == "__main__":
    df, fault = make_telemetry()
    print(f"telemetry: {len(df)} rows, {df['service_name'].nunique()} services")
    print(f"injected fault: {fault['service']} "
          f"from {fault['start']} to {fault['end']}")
