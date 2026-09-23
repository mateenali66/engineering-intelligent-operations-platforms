"""Listing 3-3. Feature-extraction job: telemetry lake -> feature table.

Reads OTLP-derived metric records from the S3 training lake, windows them into
fixed buckets, mean-aggregates per (service, window), and writes a tabular
feature table. This file is the literal handoff artifact to Chapter 6: Chapter 6
trains anomaly detectors on exactly the schema this job emits.

The author's benchmark (Paper 5, IEEE Access, vol. 14, pp. 93576 to 93608,
2026, DOI 10.1109/ACCESS.2026.3705430; data at
https://doi.org/10.5281/zenodo.19462083) found that mean-aggregated metric
features over short windows are a surprisingly strong signal, so this job
leads with the mean and keeps count and p95 as companions. Window size is the
single knob that moves results the most; 30 seconds is the default here.

Pinned dependencies (see README.md):
    python==3.12
    pandas==2.2.3
    pyarrow==17.0.0
    s3fs==2024.10.0

Run:
    python extract_features.py \
        --input s3://telemetry-lake/otel/2026/06/18/ \
        --output s3://telemetry-lake/features/2026/06/18/features.parquet \
        --window-seconds 30

Smoke test (no cluster, no S3):
    python run_smoke.py
"""
from __future__ import annotations

import argparse

import pandas as pd

# Output schema (the contract Chapter 6 consumes), one row per
# (service_name, window_start):
#   service_name    str       emitting service
#   window_start    datetime  left edge of the window, UTC
#   <feature>_mean  float     mean of the feature's per-interval values
#   <feature>_p95   float     95th percentile of those per-interval values,
#                             NOT the p95 of individual requests
#   sample_count    int       raw points in the window
#   label           int       0 = nominal, 1 = injected-fault window
# Each point is one spanmetrics flush interval: request_latency_ms is that
# interval's average latency, and the counts are that interval's totals.

# Metric names as they land in the lake, mapped to feature-column names.
# The left-hand names are what the spanmetrics connector in Listing 3-2
# emits (verified against OpenTelemetry Demo 2.0 on collector-contrib
# 0.135.0) after flatten_otlp.py derives .avg/.count/.error_count records
# from the duration histogram. If your services emit different names,
# change the left-hand side; nothing else knows the raw names.
METRIC_COLUMNS = {
    "traces.span.metrics.duration.avg": "request_latency_ms",
    "traces.span.metrics.duration.count": "request_count",
    "traces.span.metrics.duration.error_count": "error_count",
}


def load_lake(input_uri: str) -> pd.DataFrame:
    """Read one or more OTLP-derived parquet files from the S3 lake.

    The Collector's awss3 exporter writes OTLP protobuf; an upstream batch job
    (companion repo: feature-job/flatten_otlp.py) flattens it into one parquet
    row per metric data point with columns: timestamp, service_name,
    metric_name, value. Here we read the already-flattened parquet, which is
    what the lab produces.
    """
    df = pd.read_parquet(input_uri, engine="pyarrow")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def window_and_aggregate(df: pd.DataFrame, window_seconds: int) -> pd.DataFrame:
    """Window per service, then mean-aggregate. Mean is the strong feature."""
    # One row per (service, timestamp) with a column per metric; aggfunc
    # only resolves the rare duplicate point. The "plain mean" the chapter
    # refers to is the groupby mean over the window, computed below.
    df = df.pivot_table(
        index=["service_name", "timestamp"],
        columns="metric_name",
        values="value",
        aggfunc="mean",
    ).reset_index()
    df = df.rename(columns=METRIC_COLUMNS)

    freq = f"{window_seconds}s"
    df["window_start"] = df["timestamp"].dt.floor(freq)

    present = [c for c in METRIC_COLUMNS.values() if c in df.columns]
    grouped = df.groupby(["service_name", "window_start"])

    agg = grouped[present].mean().add_suffix("_mean")
    p95 = grouped[present].quantile(0.95).add_suffix("_p95")
    count = grouped.size().rename("sample_count")

    features = pd.concat([agg, p95, count], axis=1).reset_index()
    return features


def report_coverage(features: pd.DataFrame) -> None:
    """Refuse to ship a feature table whose feature columns are empty.

    A metric-name mismatch does not raise; it yields a column of nulls
    (Section 3.6's silent quality failure). Count non-null values per
    expected column and fail loudly when a column carries nothing.
    """
    empty = []
    for name in METRIC_COLUMNS.values():
        col = f"{name}_mean"
        filled = int(features[col].notna().sum()) if col in features else 0
        print(f"coverage {col}: {filled}/{len(features)} rows non-null")
        if filled == 0:
            empty.append(col)
    if empty:
        raise SystemExit(
            f"empty feature columns {empty}: the lake does not carry "
            "the metric names METRIC_COLUMNS expects"
        )


def attach_labels(features: pd.DataFrame, fault_windows_csv: str | None) -> pd.DataFrame:
    """Mark windows that overlap a known fault interval as label=1.

    fault_windows_csv has columns: service_name, start, end. Everything else is
    label=0. Labels are scarce, which is the prevalence problem Chapter 6 has to
    handle; here we just attach what ground truth exists.
    """
    features["label"] = 0
    if not fault_windows_csv:
        return features

    faults = pd.read_csv(fault_windows_csv, parse_dates=["start", "end"])
    for _, row in faults.iterrows():
        hit = (
            (features["service_name"] == row["service_name"])
            & (features["window_start"] >= row["start"])
            & (features["window_start"] <= row["end"])
        )
        features.loc[hit, "label"] = 1
    return features


def main() -> None:
    parser = argparse.ArgumentParser(description="OTLP lake -> feature table")
    parser.add_argument("--input", required=True, help="S3 prefix of flattened parquet")
    parser.add_argument("--output", required=True, help="S3 URI for the feature table")
    parser.add_argument("--window-seconds", type=int, default=30)
    parser.add_argument("--fault-windows", default=None, help="optional labels CSV")
    args = parser.parse_args()

    raw = load_lake(args.input)
    features = window_and_aggregate(raw, args.window_seconds)
    features = attach_labels(features, args.fault_windows)
    report_coverage(features)

    features = features.sort_values(["service_name", "window_start"])
    features.to_parquet(args.output, engine="pyarrow", index=False)

    print(
        f"wrote {len(features)} rows, "
        f"{features['service_name'].nunique()} services, "
        f"{int(features['label'].sum())} labeled-fault windows "
        f"-> {args.output}"
    )


if __name__ == "__main__":
    main()
