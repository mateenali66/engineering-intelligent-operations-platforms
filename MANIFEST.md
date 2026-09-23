# Companion Code Manifest

This file lists, chapter by chapter, what the companion code was tested against, how CI tests it, and what CI does not run. Every version below is copied from a pin in this repo, and the file that holds it is named next to it. CI is the workflow at `.github/workflows/ci.yml`. It runs 22 jobs on GitHub-hosted `ubuntu-22.04` runners, using the action versions in the shared baseline below. The repo's rule is that every listing in the book is exercised in CI. Some are executed, some are validated only (lint, parse or compile), and live cloud or cluster paths that CI cannot run are marked as such. Each chapter section says which of these applies to each listing.

## Shared baseline

- **GitHub Actions** (from `.github/workflows/ci.yml`)
  - `actions/checkout@v7.0.1` in every job.
  - `actions/setup-python@v7.0.0` in every job except `iac-policy`, which needs no Python.
  - `actions/cache@v6.1.0` in `ch15-rag` (model download cache).
  - `actions/upload-artifact@v7.0.1` in `ch14-iacgen` (SARIF build artifact).
  - `github/codeql-action/upload-sarif@v4` in `ch14-iacgen`. This one is pinned to a major tag only. It runs only when the repository is public.
- **Python versions used by jobs**
  - Python 3.12 in 19 jobs. Python 3.14 in `ch13-llmops` and `ch14-iacgen`. No Python setup in `iac-policy`.
- **Lint tools**
  - ruff 0.9.10 (`pip install ruff==0.9.10` in every job except `yaml-lint`, `iac-clean`, `iac-insecure` and `iac-policy`).
  - yamllint 1.35.1 (`pip install yamllint==1.35.1` in `yaml-lint`, `ch12-monitoring`, `ch13-llmops` and `ch17-platform`).
  - yamllint config in every job: `extends: default`, `line-length` max 120, `document-start` disabled. `ch17-platform` also sets `comments: {min-spaces-from-content: 1}`.
- **Triggers**
  - Push and pull request to `main`. Every job gates the build except `iac-insecure`.

## Chapter 1: The Convergence of AI and Operations

- **CI jobs**
  - `yaml-lint`.
- **Tested versions**
  - None pinned. `ch01-convergence/README.md` points to the root README for prerequisites.
- **What CI runs**
  - yamllint on `inference-service.yaml` (Listing 1-1) and `otel-collector-teaser.yaml` (Listing 1-2). This is validation only.
- **Expected output**
  - yamllint exits 0. No success line is printed.
- **Fixtures**
  - None.
- **Not run in CI**
  - Both files are teasers "not meant to be applied as-is" (README), so CI never applies them. The runnable versions are `ch03-observability/collector-config/otel-collector-config.yaml` (Chapter 3) and `ch11-model-serving/` (Chapter 11).
- **Local tests outside CI**
  - None.

## Chapter 2: Platform Engineering as the Foundation

- **CI jobs**
  - `yaml-lint`.
- **Tested versions**
  - No package pins. The README asks for Node.js 22 or 24 and says `create-app` records the Backstage release in the generated `backstage.json`.
  - Templates use `scaffolder.backstage.io/v1beta3` (README).
- **What CI runs**
  - yamllint on `catalog-info.yaml` (Listing 2-1), `org.yaml`, `scaffolder-templates/service/template.yaml` (Listing 2-2) and `scaffolder-templates/model/template.yaml` (printed in Section 2.8).
- **Expected output**
  - yamllint exits 0. No success line is printed.
- **Fixtures**
  - None.
- **Not run in CI**
  - `scaffolder-templates/model/skeleton/inference-service.yaml` (Listing 2-3) is excluded from yamllint because its Jinja2 `{%- if %}` blocks are not valid YAML (ci.yml header). The ci.yml header says it "is tested at runtime by the Backstage scaffolder, not statically".
  - The two skeleton `catalog-info.yaml` files and `scaffolder-templates/service/skeleton/otel_setup.py` are not linted, compiled or run by CI. None of them is a numbered listing (README).
  - The live lab needs Node.js, a GitHub personal access token with `repo` and `workflow` scopes, and a GitHub org or account you control (README).
- **Local tests outside CI**
  - The five-step "Run the lab" section in the README (create a Backstage app, register the files, scaffold a service).

## Chapter 3: Observability for Intelligent Systems

- **CI jobs**
  - `yaml-lint`, `ch03-python`.
- **Tested versions**
  - Python packages, pinned in `ch03-observability/requirements.txt` and in the `ch03-python` install step: pandas 2.2.3, pyarrow 17.0.0, s3fs 2024.10.0, drain3 0.9.11, opentelemetry-proto 1.27.0.
  - Collector image `otel/opentelemetry-collector-contrib:0.135.0` in `operator/otel-collector-cr.yaml` and `operator/trace-affinity-test/gateway-test-cr.yaml`.
  - Operator `v0.135.0` and cert-manager `v1.21.2` in `operator/trace-affinity-test/run.sh`.
  - The README table also lists Prometheus 3.5.0, Grafana Tempo 2.8.2, Grafana Loki 3.5.5, Grafana 11.6.0 and OpenTelemetry Demo 2.0.x. These are stated in the README only, not pinned in a file CI uses.
- **What CI runs**
  - `yaml-lint` lints `collector-config/otel-collector-config.yaml` and `operator/otel-collector-cr.yaml`.
  - `yaml-lint` then parses both files and asserts that no pipeline running `tail_sampling` also exports to `awss3`.
  - `ch03-python` runs ruff on `feature-job/` and `log-features/`, then `py_compile` on `extract_features.py`, `flatten_otlp.py`, `run_smoke.py` and `drain_templates.py`.
  - It runs `log-features/drain_templates.py` end to end.
  - It runs `feature-job/run_smoke.py`, which pushes a synthetic OTLP fixture through `flatten_otlp` and `extract_features` and asserts every feature column is populated.
- **Expected output**
  - `lake never tail-sampled: ok` (yaml-lint step) and `smoke: ok` (run_smoke.py).
  - `learned templates:` and `per-window template counts:` (drain_templates.py).
- **Fixtures**
  - `feature-job/fixtures/otlp_metrics_sample.json` is a synthetic OTLP MetricsData fixture. Its docstring says it is shaped like what the Listing 3-2 gateway writes to the lake: spanmetrics delta histograms and calls sums for two demo services, plus a runtime gauge.
- **Not run in CI**
  - The `__main__` paths of `extract_features.py` and `flatten_otlp.py` need S3 I/O. CI covers them only through the smoke test's local parquet round trip (ci.yml comment).
  - The full lab needs a Kubernetes cluster with the OpenTelemetry Operator, the OpenTelemetry Demo, Prometheus, Tempo, Loki, Grafana and an S3 bucket (README "Run the lab").
- **Local tests outside CI**
  - `operator/trace-affinity-test/run.sh` checks that every span of a trace reaches the same gateway replica. It creates a three-node kind cluster, installs cert-manager v1.21.2 and Operator v0.135.0, deploys the repo's agent resource and a two-replica gateway test double, and sends 40 split traces. Then it scales the gateway to three replicas and checks again. It needs docker, kind, kubectl and python3 (the README adds PyYAML). It deletes the cluster on exit.
  - Its checker `check_affinity.py` prints `traces: N  whole on one replica: N  split: N  per replica: {...}` and exits 1 if any trace split.

## Chapter 4: Infrastructure as Code in the AI Era

- **CI jobs**
  - `iac-clean` (gating), `iac-insecure` (non-gating), `iac-policy`, `yaml-lint`.
- **Tested versions**
  - Checkov 3.3.1, pinned in `ch04-iac-ai-era/versions.md` and in the `iac-clean` and `iac-insecure` install steps.
  - Trivy 0.71.1, pinned in `versions.md` and in the `iac-clean` and `iac-insecure` install steps.
  - Conftest 0.68.2, pinned in `versions.md` and in the `iac-policy` install step.
  - Terraform 1.15.6, OpenTofu 1.12.3, hashicorp/aws 6.58.0 (`~> 6.0`), hashicorp/kubernetes 2.x (`~> 2.0`), Python 3.12, all in `versions.md`.
  - `required_version = ">= 1.9"`, aws `~> 6.0` and kubernetes `~> 2.0` in `clean-module/versions.tf`.
  - `nvcr.io/nvidia/k8s-device-plugin:v0.17.0` in `k8s/nvidia-device-plugin.yaml` and `clean-module/device-plugin.tf`.
- **What CI runs**
  - `yaml-lint` lints `k8s/nvidia-device-plugin.yaml` (Listing 4-1).
  - `iac-clean` runs Checkov on `clean-module/` (any failed check fails the build) and `trivy config` at HIGH,CRITICAL with `--exit-code 1`.
  - `iac-insecure` runs the same two scans on `generated-module/` with `continue-on-error: true`. It exists to keep failing.
  - `iac-policy` runs `conftest test` with `policy/s3_encryption.rego` on three fixtures. `pass_clean_module.json` and `pass_differently_named_sse.json` must pass. `deny_no_sse.json` must be denied (shell negation).
- **Expected output**
  - The jobs print no custom success line. Success is exit 0, and for the deny fixture a Conftest failure.
- **Fixtures**
  - `policy/testdata/*.json` are trimmed from real `terraform show -json` output made with Terraform 1.15.6 and AWS provider 6.58.0 (ci.yml comment). Only the S3 bucket and SSE entries are kept, values unmodified.
  - `pass_clean_module` comes from `clean-module`, `deny_no_sse` from `generated-module`. `pass_differently_named_sse` comes from a two-resource module whose SSE label differs from the bucket label.
- **Not run in CI**
  - Terraform and OpenTofu are not installed in CI. The README lab steps `terraform init`, `plan` and `show -json` are not run. The repo does not state what credentials the plan step needs.
  - `k8s/nvidia-device-plugin.yaml` (Listing 4-1) is lint only. CI does not apply it to a cluster. Its Terraform twin `clean-module/device-plugin.tf` is scanned as part of `clean-module/`.
  - `.github/workflows/iac-scan.yml` is a non-executing reference copy. Its header says it backs Listing 4-4, that subdirectory workflows never run, and that the logic lives in the root `ci.yml`.
  - `prompts.md` needs a model to reproduce the generation step.
- **Local tests outside CI**
  - The four-step "Run the lab" block in the README.

## Chapter 5: Introduction to AIOps

- **CI jobs**
  - `ch05-python`, `yaml-lint`.
- **Tested versions**
  - `decide.py` is standard library only. No requirements file.
  - `registry.k8s.io/kubectl:v1.31.0` and `curlimages/curl:8.11.1` in `remediation/restart-deployment.yaml`.
  - Argo Workflows v4.1.4 is stated in the README as the tested version (kind cluster). It is not pinned in a file.
- **What CI runs**
  - `ch05-python` runs ruff on `decision/`, `py_compile` on `decide.py`, then runs `decide.py`, which executes its built-in assertion suite.
  - `yaml-lint` lints `remediation/restart-deployment.yaml` and `remediation/rbac.yaml`.
- **Expected output**
  - `ENQUEUE: restart-deployment`, a series of `PAGE: ...` lines, then `ok` (README and `decide.py`).
- **Fixtures**
  - The assertion cases are built into `decide.py`.
- **Not run in CI**
  - Applying the Argo `WorkflowTemplate` and RBAC needs a cluster with Argo Workflows (README).
- **Local tests outside CI**
  - `kubectl apply` of the two remediation files, per the README.

## Chapter 6: Building Anomaly Detection Pipelines

- **CI jobs**
  - `ch06-python`.
- **Tested versions**
  - `ch06-anomaly-detection/requirements.txt`: numpy 2.4.6, pandas 2.3.3, pyarrow 24.0.0, scikit-learn 1.9.0, joblib 1.5.3, torch 2.12.1, fastapi 0.138.0, pydantic 2.12.5, uvicorn[standard] 0.49.0, httpx 0.28.1.
  - CI installs `torch==2.12.1` from the PyTorch CPU index, then the other pins except joblib, which it does not install explicitly.
- **What CI runs**
  - ruff on the chapter directory, `py_compile` on every `.py` file, then `run_smoke.py`.
  - The smoke test trains Isolation Forest, the autoencoders, DAGMM and Deep SVDD on a synthetic slice, asserts the AUC gate and density separation, and saves the detector.
- **Expected output**
  - `saved detector -> artifacts/detector.joblib`, then `smoke: ok`.
- **Fixtures**
  - `pipeline/make_synthetic.py` generates a small feature table in the Chapter 3 schema. `run_smoke.py` writes it to `data/features.parquet`.
- **Not run in CI**
  - The leaderboard numbers reproduce from the Zenodo deposit (concept DOI 10.5281/zenodo.19462083), not from CI (README and ci.yml comment).
  - `serving/score_service.py` is compiled but not started in CI.
- **Local tests outside CI**
  - `uvicorn serving.score_service:app` plus the `curl` calls to `/healthz` and `/score` in the README.

## Chapter 7: FinOps Meets AIOps

- **CI jobs**
  - `ch07-python`.
- **Tested versions**
  - `ch07-finops-aiops/requirements.txt` and the CI install step: numpy 2.4.6, pandas 2.3.3, scikit-learn 1.9.0, statsmodels 0.14.6.
- **What CI runs**
  - ruff, `py_compile` on every `.py` file, then `run_smoke.py`. It ingests synthetic FOCUS billing, flags the spend spike with the Chapter 6 detector and forecasts with SARIMAX.
  - `right_size` sizes the next 7 days from the forecast's 80% upper bound under a 75% utilization ceiling and caps a cut at 25% (`pipeline/forecast.py`). The smoke test asserts the action is `hold`, then exercises the `downsize` and `scale up` branches on the same forecast. It also runs `pipeline/backtest.py`, which refits weekly once it has 28 days of history and counts how often actual spend exceeded the one-week 80% upper bound (14 of 85 normal days on this data).
  - The business case is an explicitly illustrative 20% cut. The cut, implementation cost and run cost are assumptions, not model output (`run_smoke.py`, README). The smoke test asserts a finite payback.
- **Expected output**
  - Lines starting `daily spend:`, `flagged ... spend-anomaly days`, `14-day forecast mean`, `right-sizing:`, `backtest: actual above the one-week 80% upper bound on 14 of 85 normal days (16%)`, `business case (illustrative 20% cut):`, `cost per transaction $`, then `smoke: ok`.
- **Fixtures**
  - `pipeline/make_billing.py` generates a synthetic FOCUS billing export with an injected spend spike.
- **Not run in CI**
  - Nothing further. Prophet and the Temporal Fusion Transformer are discussed in the chapter but are not in the code (README).
- **Local tests outside CI**
  - None.

## Chapter 8: AI-Driven Chaos Engineering

- **CI jobs**
  - `ch08-python`, `yaml-lint`.
- **Tested versions**
  - `ch08-chaos-engineering/requirements.txt` and the CI install step: numpy 2.4.6, pandas 2.3.3, pyarrow 24.0.0, scikit-learn 1.9.0, PyYAML 6.0.2.
  - Chaos Mesh 2.8.2 is named in the requirements comment, and the README says 2.8.x. LitmusChaos 3.x. Neither is installed in CI.
  - Manifests target `chaos-mesh.org/v1alpha1`.
- **What CI runs**
  - `yaml-lint` lints `experiments/pod-kill.yaml` and `experiments/network-delay.yaml`.
  - `ch08-python` runs ruff, `py_compile`, then `run_smoke.py`. It parses both manifests, injects a fault, checks the steady-state hypothesis, confirms the Chapter 6 detector responds, runs the review gate, and round-trips the exported labels through Chapter 6's own loader.
- **Expected output**
  - `manifest pod-kill: PodChaos ok`, `hypothesis:`, `fault response:`, `review gate (risky):`, `Chapter 6 loaded it: ...`, then `smoke: ok`.
- **Fixtures**
  - `pipeline/make_telemetry.py` generates synthetic telemetry with a known injected-fault window.
  - The hypothesis check uses a small fixture of real-scale measurements with a held and a breached case (README).
- **Not run in CI**
  - Applying the experiments needs a cluster with Chaos Mesh 2.8.x and the `chaos-testing` namespace (README).
- **Local tests outside CI**
  - The README's `kubectl get pods ... -l app.kubernetes.io/component=payment` selector check before applying.

## Chapter 9: MLOps Fundamentals for Platform Engineers

- **CI jobs**
  - `ch09-python`.
- **Tested versions**
  - `ch09-mlops-fundamentals/requirements.txt`: mlflow 3.14.0, skops 0.14.0, scikit-learn 1.9.0, numpy 2.4.6, dvc[s3] 3.67.1.
  - CI installs mlflow 3.14.0, skops 0.14.0, scikit-learn 1.9.0 and numpy 2.4.6, then `dvc==3.67.1` (without the `[s3]` extra) for the DVC step.
  - `.github/workflows/model-validation-gate.yml` pins `actions/checkout@v7.0.1`, `actions/setup-python@v7.0.0` and Python 3.12.
- **What CI runs**
  - ruff, `py_compile`, then `run_smoke.py`. It trains the detector on the DVC-tracked `data/telemetry.csv` and tags the run with `dataset.md5`, registers it to a SQLite-backed MLflow 3 registry, confirms the version exists, and runs `scripts/validate_metric.py` on a passing and a regressing metric. It then promotes the version with `promote.py` and walks the trail from `@production` back to the dataset hash (Table 9-4).
  - It copies the chapter to a temp dir, makes a throwaway Git repo, and runs `version-data.sh` (Listing 9-1) against its local-directory remote. It asserts `data/telemetry.csv.dvc` exists and that `dvc status --cloud` reports the data in sync.
- **Expected output**
  - `trained and registered, auc=...`, `registry has anomaly-detector v1`, `validation gate: passes on hold, blocks on regression`, `trail: dataset md5 -> run ... -> v1 -> @production (approved by model-quality owner)`, then `smoke: ok`.
  - `dvc listing: ok` (DVC step).
- **Fixtures**
  - `generate_data.py` writes a synthetic `data/telemetry.csv` from a fixed seed. `train.py` calls it when the file is missing. The file's md5 equals the md5 in the DVC pointer.
- **Not run in CI**
  - The production MinIO or S3 remote for `version-data.sh` is not exercised. CI uses the local-directory remote at `/tmp/aiosp-dvcstore` (README, script comments).
  - `.github/workflows/model-validation-gate.yml` (Listing 9-3) sits in a chapter subdirectory, so GitHub does not execute it. CI runs its validation script through the smoke test instead.
- **Local tests outside CI**
  - `version-data.sh` inside your own Git repo, as in the README. CI runs the same script in a throwaway repo.
  - `mlflow ui --backend-store-uri sqlite:///mlflow.db` (README).

## Chapter 10: ML Pipeline Orchestration

- **CI jobs**
  - `ch10-kfp`, `ch10-airflow`, `ch10-zenml`, `ch10-dvc`.
- **Tested versions**
  - `lab1-kfp/requirements.txt`: kfp 2.16.1, PyYAML 6.0.2. Component base image `python:3.12` and in-component pins (pandas 2.3.3, pyarrow 24.0.0, numpy 2.4.6, scikit-learn 1.9.0, mlflow 3.14.0, skops 0.14.0) in `lab1-kfp/pipeline.py`.
  - `lab2-airflow/requirements.txt`: apache-airflow 3.2.2, mlflow 3.14.0, skops 0.14.0, scikit-learn 1.9.0, pandas 2.3.3, pyarrow 24.0.0, numpy 2.4.6. CI first installs `apache-airflow==3.2.2` with `constraints-3.2.2/constraints-3.12.txt`.
  - `lab3-zenml/requirements.txt`: zenml[local] 0.95.1, scikit-learn 1.9.0, pandas 2.3.3, pyarrow 24.0.0, numpy 2.4.6.
  - `lab4-dvc/requirements.txt`: dvc 3.67.1, scikit-learn 1.9.0, pandas 2.3.3, pyarrow 24.0.0, numpy 2.4.6.
- **What CI runs**
  - `ch10-kfp` runs ruff, `python pipeline.py`, then asserts the IR has `components`, `deploymentSpec`, `root`, `schemaVersion` and `sdkVersion`, with `schemaVersion` 2.1.0.
  - `ch10-airflow` runs ruff, `parse_check.py` (DagBag parse), then `run_dags.sh`, which runs the retrain twice on the same features and requires exactly one version (Listing 10-2 is idempotent under retries), then changes one feature value and requires a second version.
  - `ch10-zenml` runs ruff, then `python pipeline.py` on the default local stack with analytics off and a temp config path.
  - `ch10-dvc` runs ruff, copies the lab to a temp dir, runs `git init` and `dvc init`, runs `dvc repro` twice, and greps the second run for `didn't change, skipping`.
- **Expected output**
  - `compiled pipeline.yaml` and `IR ok` (kfp). `DagBag ok: both DAGs parsed with no import errors` and `registered anomaly-detector vN, auc=...` (Airflow).
  - `didn't change, skipping` on the second `dvc repro`. The ZenML job prints no custom success line.
- **Fixtures**
  - Every lab generates the same synthetic feature table in code (`numpy.default_rng(42)`, 800 normal and 80 anomalous rows).
- **Not run in CI**
  - No Kubeflow cluster, Airflow scheduler, cloud or GPU (README CI section).
  - The ZenML stack swap to a second orchestrator is shown as CLI only (ci.yml comment).
- **Local tests outside CI**
  - `lab2-airflow/run_dags.sh` also runs in CI. It runs both DAGs with no scheduler in a temp `AIRFLOW_HOME`, gates on the 0.90 AUC baseline, runs the retrain a second time on the same features and requires one version, then changes one feature value and requires a second version above the baseline.
  - The ZenML stack-swap commands and the "edit train.py, rerun dvc repro" step in the README.

## Chapter 11: Model Serving and Inference at Scale

- **CI jobs**
  - `ch11-serving`, `yaml-lint`.
- **Tested versions**
  - `ch11-model-serving/serving/requirements.txt`: mlserver 1.7.1, mlserver-sklearn 1.7.1, scikit-learn 1.9.0, numpy 2.4.6, httpx 0.28.1.
  - Python 3.12 in the `ch11-serving` job.
  - The README states KServe v0.19.x (`serving.kserve.io/v1beta1`) and vLLM 0.23.x. These are not pinned in a file.
  - `inferenceservice-vllm-llm.yaml` uses `storageUri: "hf://Qwen/Qwen2.5-0.5B-Instruct"`.
- **What CI runs**
  - `yaml-lint` lints the three `manifests/` files.
  - `ch11-serving` runs ruff, then `run_smoke.py`. It trains, starts MLServer, posts a V2 infer request and asserts `[1, -1]`.
  - It then runs `train.py`, starts `mlserver`, waits for the model ready endpoint, runs `loadtest.py --requests 200`, and asserts at least four numeric table rows.
- **Expected output**
  - `V2 infer ok: predictions=[1, -1]  (1=inlier, -1=anomaly)` and `smoke: ok`.
  - The load test prints a table with the header `concurrency p50_ms p99_ms req/s`.
- **Fixtures**
  - `serving/train.py` trains the IsolationForest on synthetic data.
- **Not run in CI**
  - The three KServe manifests are lint only. The sklearn and canary manifests need a KServe and Knative cluster. The vLLM manifest needs a GPU node (README, ci.yml).
  - The MinIO upload and cluster `storageUri` pull are statically verified only (README).
- **Local tests outside CI**
  - `kubectl apply` of the three manifests into `kserve-test` (README).
  - The registry-to-`model.joblib` repackage command. The README says it is execution-verified, but not in CI.

## Chapter 12: ML Monitoring and Drift Detection

- **CI jobs**
  - `ch12-monitoring`.
- **Tested versions**
  - `ch12-ml-monitoring-drift/labs/requirements.txt`: nannyml 0.13.1, evidently 0.7.21, river 0.25.0, prometheus-client 0.25.0, scikit-learn 1.9.0.
  - The same file says pandas 3.0.3, numpy 2.5.0 and scipy 1.18.0 come in transitively. They are not pinned.
  - promtool from Prometheus 3.12.0 (`PROM_VER=3.12.0` in ci.yml).
  - Python 3.12.
- **What CI runs**
  - ruff, then `py_compile` on `lab4_phoenix_genai_eval.py`.
  - `run_smoke.py` runs labs 1 to 3 (NannyML CBPE, Evidently to Prometheus gauges, River ADWIN) and cross-checks every `ml_*` alert and panel selector against the exported series.
  - yamllint on `alerts/ml-monitoring-rules.yaml` and its test file.
  - `promtool check rules` and `promtool test rules`, then a JSON parse of `grafana/ml-monitoring-dashboard.json`.
- **Expected output**
  - `lab1 CBPE: ...`, `lab2 Evidently: ...`, `lab3 ADWIN: ...`, `wiring: N alert/panel selectors match exported series`, then `smoke: ok`.
- **Fixtures**
  - `labs/make_streams.py` generates three synthetic slices in the Chapter 6 schema with `numpy.default_rng(42)`: a reference period, a stable analysis period and a shifted analysis period.
- **Not run in CI**
  - `lab4_phoenix_genai_eval.py` (Listing 12-4) is compile only. It needs a Phoenix server and an LLM API key.
- **Local tests outside CI**
  - Each lab can be run alone from `labs/` (README).

## Chapter 13: LLMOps, A New Operational Discipline

- **CI jobs**
  - `ch13-llmops`.
- **Tested versions**
  - `ch13-llmops-discipline/labs/requirements.txt`: opentelemetry-api 1.42.1, opentelemetry-sdk 1.42.1, opentelemetry-semantic-conventions 0.63b1, opentelemetry-exporter-otlp 1.42.1, deepeval 4.0.6, pytest 8.4.2.
  - Python 3.14.
- **What CI runs**
  - ruff, then `py_compile` on `lab2_ragas_online.py`.
  - `run_smoke.py` with `OTEL_SEMCONV_STABILITY_OPT_IN=gen_ai_latest_experimental`. It asserts the GenAI span and its `gen_ai.*` attributes, the DeepEval exact-match gate (1.0 good, 0.0 regressed), and the cost meter (budget crossed, downshift, refusal).
  - `pytest lab2_eval_gate.py -q`.
  - yamllint on `redteam/promptfooconfig.yaml`.
- **Expected output**
  - `lab1 span: ...`, `lab2 gate: ...`, `lab3 cost: ...`, `lab3 ledger: ...`, then `smoke: ok`.
- **Fixtures**
  - Lab 1 uses a stubbed chat function that returns a canned completion.
- **Not run in CI**
  - The Langfuse OTLP export in lab 1 needs a collector or Langfuse endpoint.
  - The G-Eval judge in lab 2 and `lab2_ragas_online.py` need an LLM judge. Ragas is not pinned or installed, because `ragas==0.4.3` cannot import offline (requirements comment).
  - A live `promptfoo eval` needs Node/npm and an LLM provider key such as `OPENAI_API_KEY` (README).
- **Local tests outside CI**
  - `promptfoo eval -c redteam/promptfooconfig.yaml` (README).

## Chapter 14: Building LLM-Powered DevOps Tools

- **CI jobs**
  - `ch14-iacgen`.
- **Tested versions**
  - `ch14-llm-devops-tools/iacgen/requirements.txt`: checkov 3.3.1, pytest 8.3.4.
  - Trivy 0.71.1 and Conftest 0.68.2, installed as binaries in the `ch14-iacgen` job.
  - ruff 0.9.10, installed in the job.
  - Python 3.14.
- **What CI runs**
  - ruff over the `iacgen/` directory.
  - It warms the Trivy checks bundle once. Later scans use `--skip-check-update`.
  - It asserts that `fixtures/rev1_insecure` fails Trivy and that `fixtures/rev2_hardened` passes Checkov and Trivy.
  - `run_smoke.py` runs the bounded loop, the OPA gate, SARIF validation and the degradation illustration. `pytest tests/ -q` follows (9 tests in `tests/test_iacgen.py`).
  - It runs the three chapter labs as printed: `labs/lab1_generate_scan.py`, `labs/lab2_loop_gate_sarif.py` and `labs/lab3_degradation.py`.
  - The loop fails closed. UNKNOWN (unranked) findings count as blocking alongside HIGH and CRITICAL (`BLOCKING_SEVERITIES` in `iacgen/scanners.py`). A scanner error blocks convergence (`iacgen/loop.py`). A Conftest error or unparseable output fails the gate (`iacgen/gate.py`). SARIF maps UNKNOWN to `error` (`iacgen/sarif.py`).
  - `conftest test` must deny `rev1_insecure/plan.json` and pass `rev2_hardened/plan.json`.
  - `python -m iacgen ... --max-passes 3 --sarif iacgen.sarif`, then a check that the SARIF version is 2.1.0.
  - It uploads the SARIF to code scanning (public repo only) and archives it as a build artifact.
- **Expected output**
  - From `run_smoke.py`, as recorded in `ch14-llm-devops-tools/README.md`: `loop pass 1: 15 blocking (18 total)`, `loop final pass 2: 0 blocking`, `OPA gate: PASS`, `SARIF 2.1.0: valid, 1 result(s), written to disk`, `degradation (illustrative): uncapped 15 -> 28 -> 43; capped stops at 1 pass`, `smoke: ok`. The smoke test asserts the shape (the first pass blocks, the last pass is 0, the uncapped counts rise), not the exact numbers.
  - From the CLI (`iacgen/cli.py`): the loop trace, `planned changes (review these, not just the scan):` followed by the plan's resource changes, `SARIF: N result(s) written to ...` and `RESULT: PASS (converged within budget, OPA gate passed)`. The CI step then prints `SARIF 2.1.0 OK, N result(s)`.
- **Fixtures**
  - `fixtures/rev1_insecure`, `rev2_hardened`, `degrade_a_policy_wildcard` and `degrade_b_back_to_acl` are recorded Terraform. `rev1_insecure` and `rev2_hardened` also have recorded `plan.json`.
  - `generate()` and `repair()` return these recorded fixtures instead of calling an LLM.
- **Not run in CI**
  - `production_generate` and `production_repair` in `iacgen/generate.py` are live-LLM shapes and are never called (README).
  - Listing 14-3 is a deterministic illustration. The README says it does not reproduce the paper's +37.6% figure, which needs a live LLM.
- **Local tests outside CI**
  - The README shows how to run the same lab scripts locally with the pinned binaries in `./.tools`. CI runs them too.

## Chapter 15: RAG Architectures for Operations

- **CI jobs**
  - `ch15-rag`.
- **Tested versions**
  - `ch15-rag-operations/requirements.txt`: psycopg[binary] 3.3.4, pgvector 0.4.2, sentence-transformers 5.6.0, flashrank 0.2.10, pytest 8.4.2, trulens-core 2.8.1.
  - Service image `pgvector/pgvector:pg17` in ci.yml. The ci.yml comment and requirements file say it bundles pgvector extension 0.8.3.
  - Python 3.12.
- **What CI runs**
  - A Postgres and pgvector service container starts first.
  - ruff, then `py_compile` on `incidentcopilot/eval_ragas.py` and `incidentcopilot/agent.py`.
  - `run_smoke.py` runs schema and ingest, dense against hybrid retrieval, rerank, the contextual A/B and the deterministic eval gate.
  - `pytest tests/ -q`.
- **Expected output**
  - `smoke: ok`. The README gives `5 passed` for pytest.
- **Fixtures**
  - `corpus/` holds 9 synthetic runbooks and postmortems, `queries.json` and `contexts.json`.
  - `contexts.json` holds pre-recorded per-chunk context strings, so the A/B runs with no API key.
  - Models `all-MiniLM-L6-v2` and `ms-marco-TinyBERT-L-2-v2` are downloaded on first run and cached in CI.
- **Not run in CI**
  - LLM answer generation, the live Ragas judge, the TruLens feedback judges and the LangGraph `create_agent` loop are validation only.
  - The requirements file names `langchain==1.3.10` and `langgraph==1.2.6` for running `agent.py` locally with a key. These are not installed.
  - Production embeddings, Cohere Rerank and the context writer need a key (README).
- **Local tests outside CI**
  - `labs/lab1_hybrid_retrieval.py` through `lab4_eval_gate.py` against a local `pgvector/pgvector:pg17` container (README). CI does not run these files directly.

## Chapter 16: Securing and Governing AI Systems

- **CI jobs**
  - `ch16-guardrails`.
- **Tested versions**
  - `ch16-securing-governing-ai/requirements.txt`: fastapi 0.138.0, uvicorn[standard] 0.49.0, httpx2 2.4.0, pydantic 2.13.4, pytest 9.1.1.
  - `requirements-presidio.txt` (optional local run, not a CI job): presidio-analyzer 2.2.362, presidio-anonymizer 2.2.362, en_core_web_sm 3.8.0 wheel.
  - Named in comments only, not installed in CI: NeMo Guardrails 0.22.0, Guardrails AI 0.10.2, and the optional local supply-chain tools modelscan 0.8.8, model-signing 1.1.1 and cyclonedx-bom 7.3.0.
  - Python 3.12.
- **What CI runs**
  - ruff, then `py_compile` on `lab_promptguard.py`, `lab_llamaguard.py` and `lab_presidio.py`.
  - `run_smoke.py` runs the proxy, the attack harness and the pickle demo.
  - `pytest tests/ -q`.
- **Expected output**
  - Lines `A direct jailbreak:` through `G paraphrased jailbreak (bypass):`, `H internal service (authenticated):`, `I self-granted trust flag: HTTP ..., rejected`, then `smoke: ok`.
  - The README gives `16 passed` for pytest.
- **Fixtures**
  - The LLM is stubbed (`stub_llm` in `guardrails/proxy.py`).
  - The pickle demo uses a harmless payload.
- **Not run in CI**
  - Prompt Guard 2 needs a gated Hugging Face download and a token. Llama Guard 4 is a 12B model needing about 24 GB of GPU memory.
  - Presidio NER is probabilistic and optional. Guardrails AI and NeMo Guardrails need an LLM or hub token. AWS Bedrock and Azure managed guardrails need cloud credentials (README).
- **Local tests outside CI**
  - `python guardrails/lab_pickle_danger.py` (README). It also runs inside the smoke test.
  - The optional Presidio path (`pip install -r requirements-presidio.txt` plus the spaCy wheel) and the supply-chain tools are local runs only (requirements comments).

## Chapter 17: The Unified Ops Platform

- **CI jobs**
  - `ch17-platform`.
- **Tested versions**
  - `ch17-unified-ops-platform/requirements.txt`: opentelemetry-api 1.42.1, opentelemetry-sdk 1.42.1, opentelemetry-semantic-conventions 0.63b1, PyYAML 6.0.2, pytest 8.4.2.
  - Python 3.12.
  - `setup.sh`: kind v0.32.0, Argo CD 3.4.4 (install manifest `v3.4.4`), KServe 0.19.0 (`v0.19.0` install script), Backstage Helm chart 2.8.2.
  - Collector image `otel/opentelemetry-collector-contrib:0.135.0` in `platform/observability/otel-collector.yaml`, the same pin as Chapter 3. A comment in that file says its config validates with `otelcol-contrib validate` on this image.
  - `platform/inference/incident-copilot.yaml` uses `hf://Qwen/Qwen2.5-7B-Instruct`. The two sklearn workloads use `gs://kfserving-examples/models/sklearn/1.0/model`.
- **What CI runs**
  - ruff and yamllint over `platform/`.
  - `run_smoke.py` runs the convergence check over the manifests and the unified infra and gen_ai trace.
  - `pytest tests/ -q`, including five negative tests where the convergence check must fail on a divergent workload (ci.yml, README).
- **Expected output**
  - `convergence: PASS (serving, delivery, observability all shared)`, then `unified trace: PASS (infra + gen_ai in one trace, cost=$...)`, then `smoke: ok`.
- **Fixtures**
  - The real GitOps manifests under `platform/` are the test input.
  - The trace uses fixed token counts (220 in, 38 out) asserted by the smoke test.
- **Not run in CI**
  - `setup.sh` needs Docker, kind and your own Git remote in `AIOSP_REPO_URL`.
  - The live KServe Hugging Face or vLLM serving of the Copilot needs a GPU node.
  - The Backstage portal is not deployed (README, ci.yml).
- **Local tests outside CI**
  - `setup.sh`. Its header says the first run rewrites the placeholder `repoURL` and stops, and the second run creates the kind cluster, installs Argo CD and KServe, applies the Collector and applies the app-of-apps root.
  - `python -m aiosp.convergence` and `python -m aiosp.tracing` (README).

## Chapter 18: The Future of Intelligent Operations

- **CI jobs**
  - `ch18-future`.
- **Tested versions**
  - `ch18-future-intelligent-ops/requirements.txt`: pytest 8.4.2. The code is standard library only.
  - Python 3.12.
- **What CI runs**
  - ruff, then `run_smoke.py` and `pytest tests/ -q`. They assert propose-only behavior, no self-approval, that only human-approved changes reconcile, and that the red button halts the agent.
- **Expected output**
  - `1. agent proposed 2 PRs; cluster unchanged: PASS` through `4. red button halts the agent; nothing changes: PASS`, then `smoke: ok`.
- **Fixtures**
  - Deterministic in-memory models in `agentops/`. No external data.
- **Not run in CI**
  - A real LLM agent and the OpenTelemetry agent semantic conventions, which are still in Development (README, ci.yml).
- **Local tests outside CI**
  - `python labs/lab1_agent_remediation.py` (README). CI does not run this file directly.

## Known dependency notes

- **skops 0.14.0.** mlflow pulls `skops<1` for sklearn model serialization. skops 0.15.0 (Sep 2026) rejects sklearn tree types as untrusted on save, so the labs pin 0.14.0 (`ch09-mlops-fundamentals/requirements.txt`, `ch10-pipeline-orchestration/lab2-airflow/requirements.txt`, ch10 README).
- **Airflow constraints.** Install `apache-airflow==3.2.2` with its official `constraints-3.12.txt` first. Without it, pip pulls newer web-framework packages that parse DAGs but fail when a task runs (`lab2-airflow/requirements.txt`, ch10 README, ci.yml).
- **Airflow and ZenML apart.** They pin incompatible `asgiref` ranges, so each ch10 lab has its own venv and CI job (ch10 README).
- **ZenML extra.** The `[local]` extra is required. Plain `zenml` raises an ImportError on the local store (ch10 README).
- **Python 3.12 for ch11.** MLServer 1.7.1's uvloop/asyncio stack breaks on 3.14 (ci.yml, ch11 README).
- **Python 3.12 for ch12.** NannyML 0.13.1 pins `python <3.13` (ch12 requirements and README).
- **Python 3.12 for ch15.** The torch, onnxruntime and transformers stack resolves most reliably on 3.12 (ch15 requirements).
- **Python 3.12 for ch16.** The optional Presidio and modelscan tools cap below 3.14 and 3.13, so one interpreter serves all of them locally (ch16 requirements, ci.yml). `presidio-analyzer` is marked `Requires-Python >=3.10,<3.14`, and modelscan 0.8.8 `<3.13`.
- **spaCy model install.** Install `en_core_web_sm` from the wheel URL, not `spacy download`, which has an undeclared click dependency (`requirements-presidio.txt`).
- **Python 3.14 for ch13 and ch14.** opentelemetry 1.42.1 and deepeval 4.0.6 install cleanly on 3.14 (ch13 requirements, ci.yml).
- **Ragas not installed.** `ragas==0.4.3` imports `langchain_community.chat_models.vertexai`, which langchain-community removed, so Ragas files are compile-checked only (ch13 and ch15 requirements).
- **Scanner pins.** Checkov, Trivy and Conftest are pinned because an unpinned scanner that updates its rules overnight changes the build with no code change (`ch04-iac-ai-era/versions.md`, ch14 requirements).
- **Checkov gating.** `--hard-fail-on HIGH` can pass real findings because many community checks carry no severity. Gate on any failed check (`versions.md`, ci.yml).
- **OpenTelemetry Collector 0.135.0 in ch03.** `awss3`, `tail_sampling` and the `spanmetrics` connector ship only in contrib. The core image refuses to start with them. The `METRIC_COLUMNS` names were verified against OpenTelemetry Demo 2.0 on contrib 0.135.0 (ch03 README).
- **Loki exporter.** The standalone `loki` exporter was removed from contrib. Listing 3-2 uses `otlphttp` to Loki's `/otlp` endpoint (ch03 README).
- **prometheusremotewrite.** It needs Prometheus started with `--web.enable-remote-write-receiver` (ch03 README).
- **MLflow registry.** It needs a SQLite-backed store, because it does not work on the bare file store (ch09 README).
- **MLflow 3 logging.** Use `name=`, not the deprecated `artifact_path=` (ch09 README).
