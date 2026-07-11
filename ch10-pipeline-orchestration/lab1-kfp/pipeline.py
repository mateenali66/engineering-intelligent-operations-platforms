"""Listing 10-1: the anomaly-detector-retrain pipeline as a Kubeflow Pipelines v2 graph.

Four components (ingest, train, evaluate, register) compiled to a backend-agnostic
IR YAML. The compile needs no cluster, so CI runs it in seconds. On a real Kubeflow
backend each component becomes one pod, and the register step writes a new version of
anomaly-detector into the Chapter 9 MLflow registry.

Run:
    python pipeline.py            # writes pipeline.yaml (the compiled IR)
"""
from kfp import compiler, dsl

# Pin the base image so the listing is warning-clean and reproducible.
BASE = "python:3.12"


@dsl.component(base_image=BASE,
               packages_to_install=["pandas==2.3.3", "pyarrow==24.0.0", "numpy==2.4.6"])
def ingest(features: dsl.Output[dsl.Dataset]):
    """Read the windowed feature table the Chapter 3 job wrote to the telemetry lake."""
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(42)
    rows = np.vstack([rng.normal(0, 1, (800, 6)), rng.normal(3, 1, (80, 6))])
    df = pd.DataFrame(rows, columns=[f"f{i}" for i in range(6)])
    df["label"] = ([0] * 800) + ([1] * 80)
    df.to_parquet(features.path)


@dsl.component(base_image=BASE,
               packages_to_install=["scikit-learn==1.9.0", "pandas==2.3.3", "pyarrow==24.0.0"])
def train(features: dsl.Input[dsl.Dataset], model: dsl.Output[dsl.Model]) -> float:
    """Fit the Chapter 6 Isolation Forest; return AUC under the Chapter 6 sign convention."""
    import joblib
    import pandas as pd
    from sklearn.ensemble import IsolationForest
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split
    df = pd.read_parquet(features.path)
    y = df.pop("label").to_numpy()
    X = df.to_numpy()
    # Held-out split, the same one Chapter 9 registered on; never score the gate on training rows.
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.3, stratify=y, random_state=42
    )
    clf = IsolationForest(n_estimators=100, contamination=0.1, random_state=42).fit(X_train)
    auc = float(roc_auc_score(y_val, -clf.score_samples(X_val)))
    joblib.dump(clf, model.path)
    return auc


@dsl.component(base_image=BASE)
def evaluate(auc: float, baseline: float = 0.90) -> bool:
    """Gate on the registered baseline; register only when the new model clears it."""
    return auc >= baseline


@dsl.component(base_image=BASE,
               packages_to_install=["mlflow==3.14.0", "scikit-learn==1.9.0"])
def register(model: dsl.Input[dsl.Model], auc: float):
    """Log and register a new anomaly-detector version into the Chapter 9 registry.

    Reads the tracking URI from MLFLOW_TRACKING_URI. The sqlite default fits the
    local, single-directory path; on a real backend each component is its own pod,
    so point this at a reachable MLflow server to reach the durable registry.
    """
    import os

    import joblib
    import mlflow
    import mlflow.sklearn
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
    mlflow.set_experiment("aiosp-anomaly-detector")
    clf = joblib.load(model.path)
    with mlflow.start_run():
        mlflow.log_metric("auc", auc)
        mlflow.sklearn.log_model(sk_model=clf, name="model",
                                 registered_model_name="anomaly-detector")


@dsl.pipeline(name="anomaly-detector-retrain")
def retrain_pipeline():
    ingested = ingest()
    trained = train(features=ingested.outputs["features"])
    passed = evaluate(auc=trained.outputs["Output"])
    with dsl.If(passed.output == True, name="baseline-cleared"):  # noqa: E712
        register(model=trained.outputs["model"], auc=trained.outputs["Output"])


if __name__ == "__main__":
    compiler.Compiler().compile(retrain_pipeline, "pipeline.yaml")
    print("compiled pipeline.yaml")
