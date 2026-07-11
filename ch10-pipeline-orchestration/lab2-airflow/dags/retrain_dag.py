"""Listing 10-2: the anomaly-detector-retrain pipeline as an Airflow 3 asset-driven DAG.

Two DAGs. The first runs the feature refresh on a daily clock but hashes the bytes and
marks the asset updated only when they change, so identical data emits no event. The
second is scheduled on that asset, so it runs when the data actually changes, not on a
clock of its own. This is the data-aware model from Section 10.3 made runnable: the
retrain triggers on a real asset update and registers a new anomaly-detector version
into the Chapter 9 registry (tracking URI from MLFLOW_TRACKING_URI, sqlite by default).

Airflow 3 moved the authoring surface to the Task SDK (airflow.sdk). Dataset is now Asset.
"""
from __future__ import annotations

from airflow.sdk import DAG, Asset, task

# The addressable dataset. Its update is the trigger signal for the retrain DAG.
features = Asset("file:///tmp/aiosp/features.parquet")


with DAG(dag_id="refresh_features", schedule="@daily", catchup=False):
    @task(outlets=[features])  # succeeding marks the asset updated; skipping does not
    def refresh():
        import hashlib
        import os

        import numpy as np
        import pandas as pd
        from airflow.sdk.exceptions import AirflowSkipException
        os.makedirs("/tmp/aiosp", exist_ok=True)
        rng = np.random.default_rng(42)
        rows = np.vstack([rng.normal(0, 1, (800, 6)), rng.normal(3, 1, (80, 6))])
        df = pd.DataFrame(rows, columns=[f"f{i}" for i in range(6)])
        df["label"] = ([0] * 800) + ([1] * 80)
        # Content-hash short-circuit: emit the asset event only when the bytes move,
        # so the consumer retrains on real change, not on every @daily producer run.
        digest = hashlib.sha256(pd.util.hash_pandas_object(df).values.tobytes()).hexdigest()
        marker = "/tmp/aiosp/features.sha256"
        if os.path.exists(marker) and open(marker).read() == digest:
            raise AirflowSkipException("feature bytes unchanged; asset not updated")
        df.to_parquet("/tmp/aiosp/features.parquet")
        open(marker, "w").write(digest)

    refresh()


with DAG(dag_id="retrain_anomaly_detector", schedule=[features], catchup=False):  # event-driven
    @task
    def train_and_register():
        import os

        import mlflow
        import mlflow.sklearn
        import pandas as pd
        from sklearn.ensemble import IsolationForest
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import train_test_split
        df = pd.read_parquet("/tmp/aiosp/features.parquet")
        y = df.pop("label").to_numpy()
        X = df.to_numpy()
        # Held-out split, the same one Chapter 9 registered on; never score the gate on training rows.
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.3, stratify=y, random_state=42
        )
        clf = IsolationForest(n_estimators=100, contamination=0.1, random_state=42).fit(X_train)
        auc = float(roc_auc_score(y_val, -clf.score_samples(X_val)))
        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
        mlflow.set_experiment("aiosp-anomaly-detector")
        with mlflow.start_run():
            mlflow.log_metric("auc", auc)
            mlflow.sklearn.log_model(sk_model=clf, name="model",
                                     registered_model_name="anomaly-detector")

    train_and_register()
