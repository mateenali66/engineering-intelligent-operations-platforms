#!/usr/bin/env bash
# Run both DAGs of Listing 10-2 end to end with no scheduler: the producer writes
# the feature table and marks the asset updated, the consumer retrains, gates on
# the 0.90 AUC baseline, and registers a version. Then runs the retrain again on
# the same features, the state a retry sees after a crash that followed
# registration, and fails unless there is still exactly one version, above the
# baseline. Finally it changes one feature value and runs the retrain again, and
# fails unless that registers a second version: the retry guard must block only
# repeats, not real new data.
set -euo pipefail
cd "$(dirname "$0")"
WORK=$(mktemp -d)
export AIRFLOW_HOME="$WORK/airflow"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__DAGS_FOLDER="$PWD/dags"
export MLFLOW_TRACKING_URI="sqlite:///$WORK/mlflow.db"
rm -rf /tmp/aiosp

airflow db migrate >/dev/null
airflow dags reserialize >/dev/null
airflow dags test refresh_features >/dev/null
airflow dags test retrain_anomaly_detector >/dev/null
airflow dags test retrain_anomaly_detector >/dev/null  # retry on the same input
python - <<'PY'
import mlflow

n = len(mlflow.MlflowClient().search_model_versions("name='anomaly-detector'"))
assert n == 1, f"retry registered a duplicate: {n} versions"
PY

# New data: change one value so the feature hash moves, then retrain.
python - <<'PY'
import pandas as pd

df = pd.read_parquet("/tmp/aiosp/features.parquet")
df.loc[0, "f0"] += 0.5
df.to_parquet("/tmp/aiosp/features.parquet")
PY
airflow dags test retrain_anomaly_detector >/dev/null

python - <<'PY'
import mlflow

versions = mlflow.MlflowClient().search_model_versions("name='anomaly-detector'")
assert versions, "no anomaly-detector version was registered"
assert len(versions) == 2, f"changed features should add one version: {len(versions)}"
client = mlflow.MlflowClient()
for v in versions:
    auc = client.get_run(v.run_id).data.metrics["auc"]
    assert auc >= 0.90, f"version {v.version} registered below the baseline: {auc}"
    print(f"registered anomaly-detector v{v.version}, auc={auc:.3f}")
PY
