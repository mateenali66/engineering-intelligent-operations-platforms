"""Cluster-free smoke test for the Chapter 3 feature pipeline.

Feeds a synthetic OTLP MetricsData fixture (fixtures/otlp_metrics_sample.json,
shaped like what the Listing 3-2 gateway writes to the lake: spanmetrics delta
histograms and calls sums for two demo services, plus a runtime gauge) through
flatten_otlp and extract_features, then asserts every expected feature column
comes out populated. This is the regression guard for the silent-empty-column
failure Section 3.6 warns about: if the metric names in METRIC_COLUMNS ever
drift from what the collector writes, this test fails instead of the lab
shipping a feature-free feature table.

Run (from this directory):
    python run_smoke.py
"""
from __future__ import annotations

import pathlib
import tempfile

import pandas as pd
from google.protobuf import json_format
from opentelemetry.proto.metrics.v1.metrics_pb2 import MetricsData

import extract_features
import flatten_otlp


def main() -> None:
    here = pathlib.Path(__file__).parent
    fixture = (here / "fixtures" / "otlp_metrics_sample.json").read_text()
    data = json_format.Parse(fixture, MetricsData())

    # Flatten exactly as the lake job does: protobuf bytes in, rows out.
    rows = flatten_otlp.flatten_object(data.SerializeToString())
    df = flatten_otlp.collapse_series(pd.DataFrame(rows))
    names = set(df["metric_name"])
    for expected in extract_features.METRIC_COLUMNS:
        assert expected in names, f"missing {expected}; flattened: {sorted(names)}"

    # Round-trip through parquet and the feature job's own loader.
    with tempfile.TemporaryDirectory() as tmp:
        flat_path = f"{tmp}/flat.parquet"
        df.to_parquet(flat_path, engine="pyarrow", index=False)
        lake = extract_features.load_lake(flat_path)

    features = extract_features.window_and_aggregate(lake, 30)
    features = extract_features.attach_labels(features, None)
    extract_features.report_coverage(features)  # raises on any empty column

    assert len(features) >= 4, f"expected >= 4 windows, got {len(features)}"
    for name in extract_features.METRIC_COLUMNS.values():
        col = f"{name}_mean"
        assert col in features.columns, f"missing column {col}"
        assert features[col].notna().all(), f"nulls in {col}"

    # The fixture injects errors into payment only.
    errors = features.groupby("service_name")["error_count_mean"].max()
    assert errors["payment"] > 0, "payment errors did not survive the pipeline"
    assert errors["checkout"] == 0.0, "checkout should have zero errors"

    print("smoke: ok")


if __name__ == "__main__":
    main()
