# Chapter 9: MLOps Fundamentals for Platform Engineers

A minimal but complete local MLOps stack: version a dataset with DVC, track and
register a model with MLflow 3, and gate promotion with GitHub Actions. The model
registered is the Chapter 6 anomaly detector, so Part III starts by formalizing
the lifecycle of the Part II models.

| Listing | File | What it is |
|---|---|---|
| Listing 9-1 | `version-data.sh` | Version a dataset with DVC, backed by a local remote (swap for MinIO or S3 in production); calls `generate_data.py` to produce the dataset |
| Listing 9-2 | `train.py` | Train the Chapter 6 detector on a training split, score AUC on a held-out slice, log to MLflow 3, and register it as `anomaly-detector` |
| Listing 9-3 | `.github/workflows/model-validation-gate.yml` | A GitHub Actions gate that blocks promotion on a metric regression (runs `produce_metrics.py`, then `scripts/validate_metric.py`) |

## Run it

```bash
pip install -r requirements.txt          # pinned, CI-tested versions
python run_smoke.py                       # train + register + gate, end to end
# -> auc=0.998  registered=anomaly-detector  uri=models:/m-...
#    registry has anomaly-detector v1
#    validation gate: passes on hold, blocks on regression
#    smoke: ok

# the MLflow UI (optional), against the same SQLite store
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

Run commands from this directory (`ch09-mlops-fundamentals/`). `train.py` and
`run_smoke.py` use a SQLite-backed tracking store (`sqlite:///mlflow.db`) because
the MLflow Model Registry does not work on the bare file store. The registered
`anomaly-detector` model is the hard contract Chapter 10 builds on: its
orchestrated pipeline logs models into this same registry.

## The DVC listing

`version-data.sh` (Listing 9-1) runs the whole data-versioning leg on a laptop:
`generate_data.py` writes `data/telemetry.csv`, and the remote is a local
directory, so no object store is needed. It still needs a Git repo (DVC commits
its pointer to Git), so it is not run in CI, but it completes end to end locally.
The generated `.dvc` pointer file looks like this (a content hash plus path,
which is all Git tracks):

```yaml
outs:
- md5: ac83d5e8906d239a1798757f0fa94472
  size: 57863
  hash: md5
  path: telemetry.csv
```

In production, swap the local remote for S3-compatible object storage. Credentials
then go to `.dvc/config.local` via `dvc remote modify --local`, which is
git-ignored, never the tracked `.dvc/config`.

## Pinned versions

See `requirements.txt`. Tested against MLflow 3.14.0, scikit-learn 1.9.0,
numpy 2.4.6, DVC 3.67.1 (the DVC `[s3]` extra is needed only when you move the
remote to MinIO or S3; the local-directory remote in the listing needs plain DVC).
The sample workflow pins `actions/checkout@v7.0.1` and `actions/setup-python@v7.0.0`, the same versions as the root CI.

## MLflow 3 note

Model logging in MLflow 3 takes `name=`, not the deprecated `artifact_path=`
(still works, emits a warning). Models are first-class `LoggedModel` entities, and
MLflow 3 also ships a prompt registry for the GenAI side, developed in Part IV.
