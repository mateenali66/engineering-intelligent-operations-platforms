"""Materialize the two metrics the CI gate compares.

The gate script (validate_metric.py) reads metrics/current.json and
metrics/baseline.json; something has to write them on the PR. This step does:

  current.json  = the candidate this PR produces (train.py, held-out AUC).
  baseline.json = the AUC of the model already registered (the incumbent).

The baseline is read from the registry *before* this run registers the
candidate, so the candidate never grades itself. On the first PR there is no
incumbent yet, so the baseline bootstraps to the candidate's own metric: the
gate passes and seeds the registry. In CI without a persistent tracking server
every run starts from an empty SQLite store, so the baseline bootstraps each
time; point MLFLOW_TRACKING_URI at a real MLflow server to gate against the
true incumbent.
"""

from __future__ import annotations

import json
import os

import mlflow
from mlflow import MlflowClient

import train

TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")


def incumbent_auc(client):
    """Highest AUC among versions already registered, or None if there are none."""
    aucs = []
    for v in client.search_model_versions("name='anomaly-detector'"):
        auc = client.get_run(v.run_id).data.metrics.get("auc")
        if auc is not None:
            aucs.append(auc)
    return max(aucs) if aucs else None


def write(name, auc):
    with open(f"metrics/{name}.json", "w") as f:
        json.dump({"auc": auc}, f)


def main():
    mlflow.set_tracking_uri(TRACKING_URI)
    client = MlflowClient()

    baseline = incumbent_auc(client)   # read the incumbent before we register
    current = train.main()             # train, evaluate on held-out slice, register
    if baseline is None:
        baseline = current             # first PR: no incumbent, so seed the baseline

    os.makedirs("metrics", exist_ok=True)
    write("current", current)
    write("baseline", baseline)
    print(f"current auc={current:.4f}  baseline auc={baseline:.4f}")


if __name__ == "__main__":
    main()
