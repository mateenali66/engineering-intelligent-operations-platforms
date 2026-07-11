"""Listing 12-3: Evidently drift report exported as Prometheus gauges.

Evidently is mid-migration to a unified Report/Dataset object. This lab uses the
CURRENT 0.7.x API, verified by running it against evidently 0.7.21:

  - build a DataDefinition over the Chapter 6 numeric feature columns,
  - wrap reference and current slices as evidently Datasets,
  - run a Report([DataDriftPreset()]); report.run(current, reference) returns a
    snapshot,
  - read snapshot.dict()["metrics"]: a list whose first item is
    DriftedColumnsCount (value = {count, share}) and whose ValueDrift(column=...)
    items each carry a scalar drift score.

Those numbers become Prometheus gauges via prometheus_client. Every gauge
carries a model="anomaly-detector" label: that label is the series identity the
12.7 alert rule and Grafana dashboard select on, and it is what lets a second
model become a second label value instead of a second dashboard. No Prometheus
server is needed: the lab sets gauge values and (optionally) serves them on a
localhost HTTP endpoint you can curl, then tears it down. In production the same
gauges are scraped by Prometheus and alerted on (see the alert rule in 12.7).
"""

from __future__ import annotations

import re

from evidently import DataDefinition, Dataset
from evidently.core.report import Report
from evidently.presets import DataDriftPreset
from prometheus_client import CollectorRegistry, Gauge

from make_streams import FEATURE_NAMES, make_streams

_VALUE_DRIFT = re.compile(r"ValueDrift\(column=([^,]+),")

MODEL_NAME = "anomaly-detector"


def compute_drift(reference_df, current_df):
    """Run the Evidently 0.7.x drift report and return parsed metrics."""
    data_def = DataDefinition(numerical_columns=FEATURE_NAMES)
    ref_ds = Dataset.from_pandas(reference_df[FEATURE_NAMES], data_definition=data_def)
    cur_ds = Dataset.from_pandas(current_df[FEATURE_NAMES], data_definition=data_def)

    report = Report([DataDriftPreset()])
    snapshot = report.run(cur_ds, ref_ds)  # run(current, reference)

    drifted_count = 0
    drifted_share = 0.0
    per_column = {}
    for metric in snapshot.dict()["metrics"]:
        name = metric["metric_name"]
        value = metric["value"]
        if name.startswith("DriftedColumnsCount"):
            drifted_count = int(value["count"])
            drifted_share = float(value["share"])
        else:
            match = _VALUE_DRIFT.match(name)
            if match:
                per_column[match.group(1)] = float(value)
    return {
        "drifted_columns": drifted_count,
        "drift_share": drifted_share,
        "per_column_drift": per_column,
    }


def export_gauges(metrics, registry=None):
    """Set Prometheus gauges from the parsed drift metrics. Returns the registry.

    All three gauges are labeled with the model they describe, matching the
    ml_estimated_roc_auc gauge from the CBPE lab, so the alert rule and the
    dashboard can select ml_drift_share{model="anomaly-detector"} and match.
    """
    registry = registry or CollectorRegistry()
    g_count = Gauge(
        "ml_drift_drifted_columns",
        "Number of feature columns Evidently flagged as drifted",
        ["model"],
        registry=registry,
    )
    g_share = Gauge(
        "ml_drift_share",
        "Share of feature columns flagged as drifted (0..1)",
        ["model"],
        registry=registry,
    )
    g_col = Gauge(
        "ml_drift_score",
        "Per-column drift score (Wasserstein distance, normed)",
        ["model", "feature"],
        registry=registry,
    )
    g_count.labels(model=MODEL_NAME).set(metrics["drifted_columns"])
    g_share.labels(model=MODEL_NAME).set(metrics["drift_share"])
    for feature, score in metrics["per_column_drift"].items():
        g_col.labels(model=MODEL_NAME, feature=feature).set(score)
    return registry


def run():
    reference, _stable, shifted = make_streams()
    metrics = compute_drift(reference, shifted)
    registry = export_gauges(metrics)
    return metrics, registry


if __name__ == "__main__":
    from prometheus_client import generate_latest

    metrics, registry = run()
    print("Evidently drift metrics (reference vs shifted current):")
    print(f"  drifted columns: {metrics['drifted_columns']} / {len(FEATURE_NAMES)}")
    print(f"  drift share    : {metrics['drift_share']:.2f}")
    print("  per-column drift scores (Wasserstein, normed):")
    for feature, score in metrics["per_column_drift"].items():
        print(f"    {feature:32s} {score:.3f}")

    print("\nPrometheus exposition (/metrics) excerpt:")
    text = generate_latest(registry).decode()
    for line in text.splitlines():
        if line.startswith("ml_drift") and not line.startswith("ml_drift_score{"):
            print("  " + line)
    # Show a couple of the per-column gauge lines too.
    shown = [ln for ln in text.splitlines() if ln.startswith("ml_drift_score{")][:3]
    for line in shown:
        print("  " + line)
