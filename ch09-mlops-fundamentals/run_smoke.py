"""End-to-end MLOps-fundamentals smoke test (CI entry point).

Trains and registers the detector to a real MLflow registry, confirms the
registered model exists, then runs the validation gate on a passing metric and a
regressing one, asserting it blocks only the regression. This is the lab
Chapter 10 builds on, so the registry has to actually work, not just illustrate.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import mlflow
from mlflow import MlflowClient

import train


def write_metrics(current_auc, baseline_auc):
    os.makedirs("metrics", exist_ok=True)
    with open("metrics/current.json", "w") as f:
        json.dump({"auc": current_auc}, f)
    with open("metrics/baseline.json", "w") as f:
        json.dump({"auc": baseline_auc}, f)


def gate_exit_code():
    """Run the validation gate as a subprocess; return its exit code."""
    return subprocess.run(
        [sys.executable, "scripts/validate_metric.py"], check=False
    ).returncode


def main():
    auc = train.main()
    print(f"trained and registered, auc={auc:.3f}")

    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    client = MlflowClient()
    versions = client.search_model_versions("name='anomaly-detector'")
    assert versions, "anomaly-detector must be in the registry for Chapter 10"
    print(f"registry has anomaly-detector v{versions[0].version}")

    # The gate passes when the new model holds or beats the baseline.
    write_metrics(current_auc=0.95, baseline_auc=0.94)
    assert gate_exit_code() == 0, "gate should pass when the metric holds"

    # The gate blocks promotion when the metric regresses.
    write_metrics(current_auc=0.80, baseline_auc=0.94)
    assert gate_exit_code() == 1, "gate should block a metric regression"
    print("validation gate: passes on hold, blocks on regression")
    print("smoke: ok")


if __name__ == "__main__":
    main()
