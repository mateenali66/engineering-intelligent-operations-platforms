# Chapter 10: ML Pipeline Orchestration

Code for Chapter 10. The chapter expresses one logical pipeline, `anomaly-detector-retrain`
(ingest, train, evaluate, register the Chapter 6 detector into the Chapter 9 MLflow registry),
three ways: as a Kubeflow Pipelines v2 graph, an Airflow 3 asset-driven DAG, and a
ZenML pipeline you can move between orchestrators. A fourth lab uses DVC to show caching.

Each lab lives in its own directory with its own pinned `requirements.txt`. They are kept
apart on purpose: `apache-airflow` and `zenml` cannot be installed in the same environment
(they pin incompatible `asgiref` ranges), so each lab gets a clean venv and its own CI job.

| Listing | File | What it shows |
|---|---|---|
| 10-1 | `lab1-kfp/pipeline.py` | A four-component KFP v2 pipeline compiled to the backend-agnostic IR (`pipeline.yaml`) |
| 10-2 | `lab2-airflow/dags/retrain_dag.py` | An Airflow 3 asset-triggered DAG that retrains when the feature-table asset updates (producer content-hashes the data so identical bytes emit no event) |
| 10-3 | `lab4-dvc/dvc.yaml` | A DVC pipeline whose stages re-run only when their inputs change |
| 10-4 | `lab3-zenml/pipeline.py` | The same steps as an orchestrator-agnostic ZenML pipeline, swappable by stack |

## Pinned versions (verified June 2026)

- `kfp==2.16.1`, `apache-airflow==3.2.2`, `zenml[local]==0.95.1`, `dvc==3.67.1`
- shared model stack: `scikit-learn==1.9.0`, `numpy==2.4.6`, `pandas==2.3.3`, `pyarrow==24.0.0`, `mlflow==3.14.0` with `skops==0.14.0` (0.15.0 rejects sklearn tree types when MLflow saves the model)

Airflow 3.2.x is the first line that supports Python 3.14; on a Python 3.12 or 3.13 runner,
Airflow 3.1.x also works. The other three labs run on 3.12 through 3.14.

## Run each lab

Lab 1, Kubeflow Pipelines v2 (compile only, no cluster needed):

```bash
cd lab1-kfp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python pipeline.py          # writes pipeline.yaml, the compiled IR
```

Lab 2, Airflow 3 asset DAG (parse check and a full run, no scheduler needed):

```bash
cd lab2-airflow
python3.12 -m venv .venv && source .venv/bin/activate
pip install "apache-airflow==3.2.2" --constraint \
  https://raw.githubusercontent.com/apache/airflow/constraints-3.2.2/constraints-3.12.txt
pip install -r requirements.txt
AIRFLOW__CORE__LOAD_EXAMPLES=False python parse_check.py    # DagBag parse, both DAGs
./run_dags.sh    # producer, then retrain; gates on AUC >= 0.90 and registers a version
```

Install Airflow with its constraints file. A plain `pip install -r requirements.txt`
parses the DAGs but pulls web-framework versions Airflow 3.2.2 cannot run tasks with.

To run the DAGs for real, point `AIRFLOW_HOME` at this directory, `airflow db migrate`,
then `airflow dags test refresh_features` first (it writes the feature table the retrain
reads), then `airflow dags test retrain_anomaly_detector`. The register step reads
`MLFLOW_TRACKING_URI` and defaults to `sqlite:///mlflow.db` in the current working
directory, which reaches the Chapter 9 registry only when every process shares that
directory; on a cluster, set `MLFLOW_TRACKING_URI` to a reachable MLflow server.

Lab 3, ZenML pipeline and stack swap:

```bash
cd lab3-zenml
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ZENML_ANALYTICS_OPT_IN=false
python pipeline.py          # runs on the default local stack
# swap to a second orchestrator without touching the pipeline code:
zenml orchestrator register local2 --flavor=local
zenml stack register local_stack_2 -o local2 -a default
zenml stack set local_stack_2 && python pipeline.py
zenml stack set default
```

The `[local]` extra is required; plain `zenml` raises an ImportError on the local store.

Lab 4, DVC caching:

```bash
cd lab4-dvc
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
git init && dvc init        # dvc init needs a git repo
dvc repro                   # both stages run
dvc repro                   # both stages skip: "didn't change, skipping"
# edit train.py, then:
dvc repro                   # only train re-runs; prepare is cached
```

## CI

The root workflow runs one job per lab: `ch10-kfp` (compile + IR-shape assert),
`ch10-airflow` (DagBag parse, then both DAGs run with `airflow dags test` and `run_dags.sh` checks the gated registration), `ch10-zenml` (local pipeline run), and `ch10-dvc`
(`dvc repro` twice, second run must skip). All are headless: no cloud, no GPU, no
live Kubernetes cluster, no Airflow scheduler.
