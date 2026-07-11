"""Flatten OTLP-protobuf metric objects from the S3 lake into tabular parquet.

The Collector's awss3 exporter (marshaler: otlp_proto) writes OpenTelemetry
MetricsData protobuf objects to S3, partitioned by time. This job reads those
objects and emits one parquet row per numeric metric data point, with columns:
timestamp, service_name, metric_name, value. extract_features.py (Listing 3-3)
reads exactly that flattened parquet, so run this first.

Gauges and sums flatten directly. Histograms, which is how request latency
arrives (the spanmetrics duration metric from Listing 3-2 is a histogram),
flatten into derived records per data point: <name>.count and <name>.sum,
plus <name>.error_count for series the spanmetrics connector marks with
status.code=STATUS_CODE_ERROR. collapse_series() then sums those across
attribute series per (timestamp, service) and derives <name>.avg, the
per-interval average latency the feature job maps to request_latency_ms.
Listing 3-2 runs the connector with delta temporality, so every data point
is a per-interval measurement, not a running total since process start.

Pinned dependencies (see README.md):
    python==3.12
    pandas==2.2.3
    pyarrow==17.0.0
    s3fs==2024.10.0
    opentelemetry-proto==1.27.0

Run:
    python flatten_otlp.py \
        --input s3://telemetry-lake/otel/2026/06/18/ \
        --output s3://telemetry-lake/flat/2026/06/18/metrics.parquet

Smoke test (no cluster, no S3):
    python run_smoke.py
"""
from __future__ import annotations

import argparse

import pandas as pd
import s3fs
from opentelemetry.proto.metrics.v1.metrics_pb2 import MetricsData

# Suffixes of the histogram-derived records that collapse_series() sums.
DERIVED_SUFFIXES = (".count", ".sum", ".error_count")


def _service_name(resource) -> str:
    for attr in resource.attributes:
        if attr.key == "service.name":
            return attr.value.string_value or "unknown"
    return "unknown"


def _is_error(data_point) -> bool:
    """spanmetrics marks errored series with status.code=STATUS_CODE_ERROR."""
    for attr in data_point.attributes:
        if attr.key == "status.code":
            return attr.value.string_value == "STATUS_CODE_ERROR"
    return False


def _points(metric):
    """Yield (metric_name, time_unix_nano, value) for numeric metric types."""
    if metric.HasField("gauge") or metric.HasField("sum"):
        data = metric.gauge if metric.HasField("gauge") else metric.sum
        for dp in data.data_points:
            value = dp.as_double if dp.HasField("as_double") else float(dp.as_int)
            yield metric.name, dp.time_unix_nano, value
    elif metric.HasField("histogram"):
        # Request latency arrives here. Emit count/sum (and the errored
        # count) per data point; collapse_series() finishes the job.
        for dp in metric.histogram.data_points:
            yield f"{metric.name}.count", dp.time_unix_nano, float(dp.count)
            if dp.HasField("sum"):
                yield f"{metric.name}.sum", dp.time_unix_nano, dp.sum
            if _is_error(dp):
                yield f"{metric.name}.error_count", dp.time_unix_nano, float(dp.count)
    # summaries and exponential histograms are not used by this lab


def flatten_object(raw: bytes) -> list[dict]:
    data = MetricsData()
    data.ParseFromString(raw)
    rows: list[dict] = []
    for rm in data.resource_metrics:
        service = _service_name(rm.resource)
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                for name, time_nano, value in _points(metric):
                    rows.append(
                        {
                            "timestamp": pd.Timestamp(time_nano, unit="ns", tz="UTC"),
                            "service_name": service,
                            "metric_name": name,
                            "value": value,
                        }
                    )
    return rows


def collapse_series(df: pd.DataFrame) -> pd.DataFrame:
    """Sum histogram-derived records across attribute series, derive the avg.

    The spanmetrics connector emits one histogram series per (span.name,
    status.code), so one service reports several data points per interval.
    Counts and sums add across series. The derived <name>.avg is the summed
    sum over the summed count, and <name>.error_count is guaranteed present
    (zero when nothing errored), so the feature job's error column cannot
    go silently missing.
    """
    if df.empty:
        return df
    derived = df["metric_name"].str.endswith(DERIVED_SUFFIXES)
    if not derived.any():
        return df
    wide = df[derived].pivot_table(
        index=["timestamp", "service_name"],
        columns="metric_name",
        values="value",
        aggfunc="sum",
    )
    for base in {c[: -len(".count")] for c in wide.columns if c.endswith(".count")}:
        if f"{base}.sum" in wide.columns:
            wide[f"{base}.avg"] = wide[f"{base}.sum"] / wide[f"{base}.count"]
        err = f"{base}.error_count"
        wide[err] = wide[err].fillna(0.0) if err in wide.columns else 0.0
    flat = wide.reset_index().melt(
        id_vars=["timestamp", "service_name"],
        var_name="metric_name",
        value_name="value",
    ).dropna(subset=["value"])
    return pd.concat([df[~derived], flat], ignore_index=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="OTLP protobuf -> flat parquet")
    parser.add_argument("--input", required=True, help="S3 prefix of OTLP objects")
    parser.add_argument("--output", required=True, help="S3 URI for flat parquet")
    args = parser.parse_args()

    fs = s3fs.S3FileSystem()
    rows: list[dict] = []
    for path in fs.glob(args.input.rstrip("/") + "/**"):
        if fs.isdir(path):
            continue
        with fs.open(path, "rb") as handle:
            rows.extend(flatten_object(handle.read()))

    df = collapse_series(pd.DataFrame(rows))
    df.to_parquet(args.output, engine="pyarrow", index=False)
    print(f"flattened {len(df)} data points -> {args.output}")


if __name__ == "__main__":
    main()
