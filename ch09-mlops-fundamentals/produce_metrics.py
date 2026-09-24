"""Materialize the two metrics the CI gate compares.

The gate script (validate_metric.py) reads metrics/current.json and
metrics/baseline.json; something has to write them on the PR. This step does:

  current.json  = the candidate this PR produces (train.py, held-out AUC).
  baseline.json = the incumbent (the @production model, or the latest version
                  if none is promoted yet), re-scored on the same held-out slice.

Both numbers come from the same rows. Comparing the candidate's AUC with the
AUC the incumbent logged when it was trained would compare two different
holdouts, and once the data changes that gap says nothing about which model is
better. The incumbent is loaded *before* this run registers the candidate, so
the candidate never grades itself. On the first PR there is no incumbent yet,
so the baseline bootstraps to the candidate's own metric: the gate passes and
seeds the registry. In CI without a persistent tracking server every run
starts from an empty SQLite store, so the baseline bootstraps each time; point
MLFLOW_TRACKING_URI at a real MLflow server to gate against the true incumbent.
"""

from __future__ import annotations

import json
import os

import mlflow
import mlflow.sklearn
from mlflow import MlflowClient
from sklearn.metrics import roc_auc_score

import train

TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")


def load_incumbent(client):
    """The model to beat: @production if set, else the latest version, else None."""
    try:
        version = client.get_model_version_by_alias("anomaly-detector", "production")
    except mlflow.exceptions.MlflowException:
        versions = client.search_model_versions("name='anomaly-detector'")
        if not versions:
            return None
        version = max(versions, key=lambda v: int(v.version))
    return mlflow.sklearn.load_model(f"models:/anomaly-detector/{version.version}")


def holdout_auc(model):
    """AUC of a model on the held-out slice train.py evaluates the candidate on."""
    X, y, _ = train.load_dataset()
    _, X_val, _, y_val = train.split(X, y)
    return roc_auc_score(y_val, -model.score_samples(X_val))


def write(name, auc):
    with open(f"metrics/{name}.json", "w") as f:
        json.dump({"auc": auc}, f)


def main():
    mlflow.set_tracking_uri(TRACKING_URI)
    client = MlflowClient()

    incumbent = load_incumbent(client)  # load the incumbent before we register
    current = train.main()              # train, evaluate on held-out slice, register
    # Same rows for both: re-score the incumbent, never reuse its logged AUC.
    baseline = holdout_auc(incumbent) if incumbent is not None else current

    os.makedirs("metrics", exist_ok=True)
    write("current", current)
    write("baseline", baseline)
    print(f"current auc={current:.4f}  baseline auc={baseline:.4f}")


if __name__ == "__main__":
    main()
